"""Read target Git bytes only; never execute archived runners, hosts, or bags.
Run: python -I check_archive.py REPO [OUTPUT_JSON]
"""
import ast
import hashlib
import json
import re
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

REPO = sys.argv[1]
REV = '5f54a449650e203a1c1d3bba29486a8476fb53ae'
BASELINE = '70e3e7cab942839e88727579787c7210012ef5f9'
RUN_SOURCE = 'b1bce5ef7b3c4258f65371e32b4930f7ca2147ea'
BASE = 'docs/review_20261112_four_host/'
RUNS = ('two_event_armed_checkpoint_20261112', 'two_event_final_20261112')

def git(*args):
    return subprocess.check_output(['git', '-C', REPO, *args])

def read(path, rev=REV):
    return git('show', rev + ':' + path)

def load(path):
    return json.loads(read(path))

def jsonl(path):
    return [json.loads(line) for line in read(path).splitlines() if line.strip()]

def fields(ack):
    return dict(re.findall(r'(\w+)=([^\s]+)', ack))

def ns(text):
    return int(Decimal(text) * 1_000_000_000)

def scalar(d):
    return {k: v for k, v in d.items() if not isinstance(v, (dict, list))}

manifest = []
for line in read(BASE + 'SHA256SUMS').decode().splitlines():
    digest, rel = line.split(None, 1)
    manifest.append((digest, BASE + rel.strip().removeprefix('./')))
# Batch reads historical files solely for checksum integrity, not a repeated raw-run review.
p = subprocess.run(['git', '-C', REPO, 'cat-file', '--batch'],
                   input=('\n'.join(REV + ':' + path for _, path in manifest) + '\n').encode(),
                   stdout=subprocess.PIPE, check=True)
blob = p.stdout
pos = 0
mismatches = []
for expected, path in manifest:
    end = blob.index(b'\n', pos)
    header = blob[pos:end].split()
    if header[-1] == b'missing':
        mismatches.append({'path': path, 'error': 'missing'})
        pos = end + 1
        continue
    size = int(header[2])
    content = blob[end + 1:end + 1 + size]
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected:
        mismatches.append({'path': path, 'expected': expected, 'actual': actual})
    pos = end + 1 + size + 1

source_path = 'slam_recovery/ros/recovery_node.py'
source = read(source_path).decode()
run_source = read(source_path, RUN_SOURCE).decode()
tree = ast.parse(source)
run_tree = ast.parse(run_source)

def function(t, name):
    return next(n for n in ast.walk(t) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)

changed_entries = ('arm_scripted_checkpoints', '_open_episode', 'service', 'main')
entry_equivalence = {name: ast.dump(function(tree, name), include_attributes=False) ==
                    ast.dump(function(run_tree, name), include_attributes=False)
                    for name in changed_entries}
# Execute only the reviewed changed functions extracted from target Git bytes; no package imports.
namespace = {'time': time, 'np': SimpleNamespace(ndarray=object),
             'Optional': __import__('typing').Optional, 'Dict': dict, 'Any': object}
namespace['Episode'] = lambda *a, **k: SimpleNamespace(args=a, **k)
selected = [function(tree, name) for name in ('arm_scripted_checkpoints', '_open_episode', 'service')]
exec(compile(ast.Module(body=selected, type_ignores=[]), source_path + '@' + REV, 'exec'), namespace)
class Recorder:
    def __init__(self):
        self.calls = []
    def hold(self, stamp=None):
        self.calls.append(('hold', stamp))
    def snapshot_now(self, stamp):
        self.calls.append(('snapshot', stamp))
    def expire_pending(self, age):
        self.calls.append(('expire_pending', age))
    def poll(self):
        return None
    def tick(self, *a, **k):
        self.calls.append(('tick', None))
    def pending(self):
        return False
cp = Recorder()
namespace['arm_scripted_checkpoints'](cp, [200, 100])
arm_order = cp.calls == [('hold', 100), ('snapshot', 100), ('hold', 200), ('snapshot', 200)]
cp.calls = []
loop = SimpleNamespace(cp=cp, confirmation_margin_ns=4_000_000_000,
                       _first_alarm_ts_ns=None, episodes=[])
namespace['_open_episode'](loop, 10_000_000_000, object(),
                           SimpleNamespace(t_start_ns=6_000_000_000))
open_cancel_order = cp.calls == [('expire_pending', 0.0), ('hold', None)]
cp.calls = []
loop.node = SimpleNamespace(tx_mgr=SimpleNamespace(active_quarantine=None))
loop._apply_lifecycle = lambda: None
loop.scripted_trigger_stamps_ns = [10_000_000_000]
loop.pending_decision = None
namespace['service'](loop)
scripted_no_tick = not any(c[0] == 'tick' for c in cp.calls)
loop.scripted_trigger_stamps_ns = []
namespace['service'](loop)
online_tick_preserved = any(c[0] == 'tick' for c in cp.calls)

results = []
for run in RUNS:
    prefix = BASE + run + '/'
    summary = load(prefix + 'run_summary.json')
    receipt = load(prefix + 'receipt.json')
    candidates = jsonl(prefix + 'candidates.jsonl')
    details = jsonl(prefix + 'candidates_detail.jsonl')
    icp = jsonl(prefix + 'icp_detail.jsonl')
    relay = jsonl(prefix + 'relay_frames.jsonl')
    events = load(prefix + 'native_checkpoint_events.json')
    life = load(prefix + 'lifecycle_events.json')
    episodes = summary['quarantine']['episode_detail']
    frames = summary['frame_diagnostics']
    stamps = [int(f['ts_ns']) for f in frames]
    host = read(prefix + 'host.log').decode(errors='replace')
    launch = read(prefix + 'launch_pair.sh').decode()
    snaps = re.findall(r'snapshot stamp=([\d.]+) frame=(\d+) voxels=(\d+) nodes=(\d+) points=(\d+)', host)
    replay = re.findall(r'reprocess #(\d+): (\d+) frames replayed over \[([\d.]+) \.\. ([\d.]+)\], repairs applied=(\d+) queued=(\d+), replayed_within_end=(\d+) replayed_suffix=(\d+) end_stamp=(\d+), map now (\d+) voxels/(\d+) points', host)
    assert len(snaps) == 2 and len(replay) == 1
    replay = replay[0]
    applied = re.findall(r'\[NATIVE_REPAIR\] applied by group end=([\d.]+) stamp=([\d.]+)', host)
    applied_stamps = [ns(x[1]) for x in applied]
    pub = episodes[0]['repair_publish']
    published_stamps = [int(s) for s in pub['frames']]
    relay_frames = [f for f in relay if f.get('event') == 'frame']
    shifted = [int(f['stamp_ns']) for f in relay_frames if f['shifted']]
    expected_declared = [int(x) for x in receipt['launch']['scripted_triggers_ns'].split(',')]
    checkpoints = []
    for i, ep in enumerate(episodes):
        event = next(e for e in events if e['command'] == ('reprocess' if i == 0 else 'restore'))
        status = fields(event['ack'])
        cp_stamp = int(status['stamp_ns'])
        checkpoints.append({
            'event': i + 1, 'trigger_ns': ep['trigger_ts_ns'],
            'quarantine_start_ns': ep['quarantine_start_ns'],
            'snapshot_log_ns': ns(snaps[i][0]), 'checkpoint_ack_ns': cp_stamp,
            'checkpoint_minus_trigger_ns': cp_stamp - ep['trigger_ts_ns'],
            'checkpoint_minus_quarantine_start_ns': cp_stamp - ep['quarantine_start_ns'],
            'checkpoint_no_later_than_trigger': cp_stamp <= ep['trigger_ts_ns'],
            'checkpoint_no_later_than_quarantine_start': cp_stamp <= ep['quarantine_start_ns'],
            'native_state_and_map_fully_equivalent': 'UNKNOWN'})
    closes = [e for e in life if e['event'] == 'wait_limit_closed']
    tail = [s for s in stamps if len(closes) == 2 and s > closes[1]['closed_ns']]
    reprocess_ack = fields(next(e for e in events if e['command'] == 'reprocess')['ack'])
    resumes = [e for e in events if e['command'] == 'resume']
    resume1_ack = fields(resumes[0]['ack'])
    source_digest = read(prefix + 'recovery_node_source.sha256').decode().split()[0]
    checks = {
        'run_id_receipt_summary_candidates_bound': receipt['run_id'] == summary['run_id'] and all(c['run_id'] == summary['run_id'] for c in candidates),
        'receipt_driver_equals_known_git_run_source': source_digest == receipt['inputs']['recovery_node_source'] == hashlib.sha256(run_source.encode()).hexdigest(),
        'receipt_driver_equals_target_source': source_digest == hashlib.sha256(source.encode()).hexdigest(),
        'declared_fired_candidate_episode_trigger_stamps_equal': expected_declared == summary['scripted_triggers']['declared_ns'] == [f['ts_ns'] for f in summary['scripted_triggers']['fired']] == [c['t_trigger_ns'] for c in candidates] == [e['trigger_ts_ns'] for e in episodes],
        'repair_published_received_applied_23': pub['published'] == pub['final_received'] == len(published_stamps) == len(applied_stamps) == int(reprocess_ack['repair_applied']) == 23,
        'published_and_applied_stamps_equal_at_host_double_precision': len(published_stamps) == len(applied_stamps) and all(abs(a-b) <= 256 for a,b in zip(published_stamps, applied_stamps)) and all(min(published_stamps, key=lambda p: abs(p-a)) == p for p,a in zip(published_stamps, applied_stamps)),
        'published_stamps_equal_actual_applied_stamps_exact_ns': published_stamps == applied_stamps,
        'all_repaired_stamps_in_shifted_population': set(published_stamps) <= set(shifted),
        'candidate_detail_population_bound': all(d['candidate_id'] == c['candidate_id'] and set(d['candidate_frame_ids']) == set(map(int, d['repaired_poses'])) and len(d['candidate_frame_ids']) == ep['candidate_frames'] and (not c['accepted'] or (set(d['candidate_frame_ids']) <= set(map(int, c['committed_pose_keys'] + c['deferred_pose_keys'])) and d['candidate_frame_ids'] == c['committed_pose_keys'])) for c, d, ep in zip(candidates, details, episodes)),
        'candidate_pose_and_published_scan_stamps_within_pair_window': all(abs(a-b) <= summary['pairing']['pair_window_ns'] for a, b in zip(details[0]['candidate_frame_ts_ns'], published_stamps)),
        'replay_total_equals_window_plus_suffix': int(replay[1]) == int(replay[6]) + int(replay[7]),
        'host_replay_counts_equal_ack': int(replay[6]) == int(reprocess_ack['replay_within_end']) and int(replay[7]) == int(reprocess_ack['replay_suffix']),
        'reprocess_resume_native_boundary_xyz_equal': reprocess_ack['state_pos'] == resume1_ack['state_pos'],
        'no_set_state_command': not any(e['command'] == 'set_state' for e in events),
        'lifecycle_archive_equals_summary': life == summary['lifecycle']['events'],
        'checkpoint_archive_equals_summary': events == summary['native_checkpoint']['events'],
        'pose_scan_pair_population_balances': summary['pairing']['paired'] + summary['pairing']['poses_unpaired'] == summary['pairing']['poses_received'] and summary['pairing']['paired'] + summary['pairing']['scans_unpaired'] == summary['pairing']['scans_received'],
        'launch_mentions_exact_run_and_trigger_stamps': receipt['run_id'] in launch and all(str(s) in launch for s in expected_declared),
    }
    results.append({
        'archive': run, 'run_id': summary['run_id'], 'checks': checks,
        'listed_file_hashes': sum(path.startswith(prefix) for _, path in manifest),
        'inputs': receipt['inputs'], 'full_package_source_identity': 'UNKNOWN (only driver Git source and host patch/library declaration bound)',
        'run_mode': summary['run_mode'], 'detection_enabled': summary['detection_enabled'],
        'declared_trigger_stamps': expected_declared, 'gate_candidates': [{k: c[k] for k in ('candidate_id', 't_trigger_ns', 't_decision_ns', 'mode', 'accepted', 'weak_dir_info_before', 'weak_dir_info_after', 'wilson_lower_bound')} | {'committed': len(c['committed_pose_keys']), 'deferred_at_decision': len(c['deferred_pose_keys'])} for c in candidates],
        'icp': [{k: x.get(k) for k in ('status', 'icp_converged', 'icp_residual', 'frames_candidate')} for x in icp],
        'repair': {'estimated_bias_z_m': pub['bias_z_m'], 'shift_z_m': pub['repair_shift_z_m'],
                   'published_received_applied': [pub['published'], pub['final_received'], int(reprocess_ack['repair_applied'])],
                   'shifted_scans': len(shifted), 'shifted_but_not_repaired_scans': len(set(shifted) - set(published_stamps)),
                   'leftover': int(replay[5]), 'baseline': pub.get('repair_received_baseline'),
                   'published_scan_stamps_sha256': hashlib.sha256(json.dumps(published_stamps, separators=(',', ':')).encode()).hexdigest(),
                   'actual_applied_log_stamps_sha256': hashlib.sha256(json.dumps(applied_stamps, separators=(',', ':')).encode()).hexdigest(),
                   'max_published_to_applied_log_precision_delta_ns': max(abs(a-b) for a,b in zip(published_stamps, applied_stamps)),
                   'stamp_matching_note': 'Exact integer published stamps are relay-bound; host prints double seconds (0..239 ns conversion difference), uniquely matched within one double ULP, not claimed bitwise-identical.'},
        'replay': {'groups': int(replay[1]), 'start_ns': ns(replay[2]), 'end_ns': ns(replay[3]),
                   'within_end': int(replay[6]), 'suffix': int(replay[7]),
                   'terminal_payload_ns': int(replay[8]), 'map_voxels': int(replay[9]), 'map_points': int(replay[10])},
        'checkpoints': checkpoints,
        'lifecycle': [{'event': x['event'], 'closed_ns': x.get('closed_ns'), 'from_state': x.get('from_state'),
                       'unresolved_frames': len(x.get('frames_unresolved', []))} for x in life],
        'final_state': summary['final_state'], 'quarantine_open_at_exit': summary['quarantine_open_at_exit'],
        'tail_after_e2_close_paired_frames': len(tail),
        'tail_after_e2_close_duration_s': (max(stamps)-closes[1]['closed_ns']) / 1e9 if len(closes) == 2 else None,
        'last_paired_stamp_ns': max(stamps), 'native_snapshot_counters': {k: summary['native_checkpoint'][k] for k in ('snapshots', 'snapshots_superseded', 'snapshot_ack_timeouts', 'failures')},
        'runtime': summary['runtime'], 'independent_recovery_quality': 'UNKNOWN',
        'command_sequence': [e['command'] for e in events],
    })

build_text = read(BASE + 'host_change_replay_suffix_ack/BUILD.md').decode()
build_log = read(BASE + 'host_change_replay_suffix_ack/host_build_v6.log').decode(errors='replace')
output = {
    'target': REV, 'baseline': BASELINE, 'mode': 'read-only Git bytes + Python -I; no archive script/host/bag/dependency install',
    'manifest': {'listed': len(manifest), 'matched': len(manifest)-len(mismatches), 'mismatches': mismatches},
    'source': {'target_driver_sha256': hashlib.sha256(source.encode()).hexdigest(),
               'run_driver_sha256': hashlib.sha256(run_source.encode()).hexdigest(), 'run_driver_git_revision': RUN_SOURCE,
               'changed_entry_ast_equal_run_and_target': entry_equivalence,
               'minimal_source_controls': {'arm_sorted_all_stamps': arm_order, 'open_cancels_before_hold': open_cancel_order,
                                           'scripted_rolling_disabled': scripted_no_tick, 'online_rolling_preserved': online_tick_preserved},
               'normal_minimal_boundary_scenario': {'trigger_ns': 10_000_000_000, 'quarantine_start_ns': 6_000_000_000,
                                                     'current_arm_ns': 10_000_000_000, 'unreverted_prefix_s': 4}},
    'build': {'command': 'catkin_make -j8 (archived only)', 'overall_exit_code': 1,
              'host_target_built_log_marker': 'Built target laser_mapping' in build_log,
              'abi_failure_retained': 'CXXABI_1.3.15' in build_log,
              'runtime_library_declared_in_build_matches_both_receipts': all(x['inputs']['runtime_library_sha256'].startswith('9e7d8cdf') and x['inputs']['runtime_library_sha256'].endswith('3b0a') for x in results),
              'clean_independent_rebuild': 'NOT_EXECUTED'},
    'runs': results,
    'source_only_unchanged_ack_failure_path': {'target_lines': '1852-1867',
        'changed_in_this_delta': False,
        'observation': 'collect None or FAIL is not required to be successful before suffix parsing; suffix missing falls through elif ep.frames to set_state. Old finding retained, not rerun and not asserted to have occurred in these new runs.'},
    'documentation_corrections': {'armed_REPORT_superseded_claim': 1, 'armed_archived_summary_superseded_actual': results[0]['native_snapshot_counters']['snapshots_superseded'],
        'final_REPORT_shifted_claim': 60, 'final_actual_relay_shifted': results[1]['repair']['shifted_scans'],
        'classification': 'nonblocking text corrections; no rerun needed'},
    'verdict': 'PARTIAL: final controlled repaired-input replay/suffix/resume/E2/tail executed; checkpoint legality at quarantine_start NOT satisfied; full-state equivalence/quality/automatic detection NOT established',
}
# Consistency checks reject integrity mismatches, while intentionally reporting the observed source
# difference and scientific checkpoint failure rather than hiding them behind an overall PASS.
observational_checks = {'receipt_driver_equals_target_source', 'published_stamps_equal_actual_applied_stamps_exact_ns'}
required_checks = [v for x in results for k,v in x['checks'].items() if k not in observational_checks]
assert not mismatches and all(required_checks), {'mismatches': mismatches, 'failed_checks': {x['archive']: [k for k,v in x['checks'].items() if not v and k not in observational_checks] for x in results}}
assert all(entry_equivalence.values()) and arm_order and open_cancel_order and scripted_no_tick and online_tick_preserved
assert all(not c['checkpoint_no_later_than_quarantine_start'] for x in results for c in x['checkpoints'])
text = json.dumps(output, ensure_ascii=False, indent=2) + '\n'
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(text, encoding='utf-8')
print(json.dumps({'manifest': output['manifest'], 'source_controls': output['source']['minimal_source_controls'],
                  'runs': [{'run': x['run_id'], 'replay_groups': x['replay']['groups'], 'repair': x['repair']['published_received_applied'],
                            'final': x['final_state'], 'tail_frames': x['tail_after_e2_close_paired_frames'],
                            'tail_s': x['tail_after_e2_close_duration_s'],
                            'checkpoint_late_vs_quarantine_s': [c['checkpoint_minus_quarantine_start_ns']/1e9 for c in x['checkpoints']]} for x in results],
                  'verdict': output['verdict']}, ensure_ascii=False))
