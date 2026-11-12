"""Isolated readback of new v3 repair/sham archives; no runner execution."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'e82d90041c090dcb8a9df6402ebfdb98f465a0b8'
BASE = 'd193680aa6f3bb7945e8bf01fdd2d8932819c49c'
PREFIX = 'docs/review_20261112_four_host/'
PAIR = PREFIX + 'injection_repair_20261112/freeze_ab/deferred_pair/'

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])
def blob(path, version=TARGET):
    return git('show', version + ':' + path)
def ns(text):
    s, n = text.split('.')
    return int(s) * 10**9 + int(n.ljust(9, '0'))

changed = set(git('diff', '--name-only', BASE, TARGET, '--', PREFIX).decode().splitlines())
checks = []
for line in blob(PREFIX + 'SHA256SUMS').decode().splitlines():
    expected, path = line.split(maxsplit=1)
    path = str(PurePosixPath(path.lstrip('*')))
    assert not path.startswith('/') and '..' not in PurePosixPath(path).parts
    if PREFIX + path in changed:
        checks.append({'path': path, 'ok': hashlib.sha256(blob(PREFIX + path)).hexdigest() == expected})
assert checks and all(c['ok'] for c in checks)
new_sha = blob(PREFIX + 'host_change_deferred_stamp/new_binary_sha.txt').decode().split()[0]
reference_populations = []
runs = []
for arm in ('repair', 'sham'):
    prefix = PAIR + arm + '/'
    summary = json.loads(blob(prefix + 'run_summary.json'))
    receipt = json.loads(blob(prefix + 'receipt.json'))
    inputs = receipt['inputs']
    detail = json.loads(blob(prefix + 'candidates_detail.jsonl').splitlines()[0])
    candidate = json.loads(blob(prefix + 'candidates.jsonl').splitlines()[0])
    episode = summary['quarantine']['episode_detail'][0]
    published = episode.get('repair_publish', {})
    events = json.loads(blob(prefix + 'native_checkpoint_events.json'))
    actions = [{k: e.get(k) for k in ('command', 'wall', 'ack_wall', 'ok', 'error', 'ack')}
               for e in events if e.get('command') in ('hold', 'reprocess', 'set_state', 'resume')]
    host = blob(prefix + 'host.log').decode(errors='replace').splitlines()
    replay_line = next(line for line in host if 'reprocess #1:' in line)
    match = re.search(r'(\d+) frames replayed over \[(\d+\.\d+) \.\. (\d+\.\d+)\], repairs applied=(\d+) queued=(\d+)(.*)', replay_line)
    assert match, replay_line
    attrs = {key: int(value) for key, value in re.findall(r'(replayed|truncated|end_stamp)=(\d+)', match[6])}
    deferred = [{'line': i, 'text': line} for i, line in enumerate(host, 1) if 'deferred apply' in line]
    snapshot = next(line['text'] for line in deferred if 'cmd=snapshot' in line['text'])
    cp_fields = {k: v for k, v in re.findall(r'([A-Za-z_]+)=([^ ]+)', snapshot)}
    recorded = blob(prefix + 'recovery_node_source.sha256').decode().split()[0]
    source_sha = hashlib.sha256(blob('slam_recovery/ros/recovery_node.py', 'b42544e')).hexdigest()
    target_sha = hashlib.sha256(blob('slam_recovery/ros/recovery_node.py')).hexdigest()
    assert recorded == source_sha == target_sha
    rows = [json.loads(line) for line in blob(prefix + 'relay_frames.jsonl').splitlines()]
    frames = [r for r in rows if r.get('event') == 'frame']
    shifted = {r['stamp_ns'] for r in frames if r['shifted']}
    reference_populations.append(detail['candidate_frame_ts_ns'])
    runs.append({'arm': arm, 'run_id': summary['run_id'], 'driver_sha': recorded, 'matches_target_driver': True,
                 'runtime_library_sha': inputs['runtime_library_sha256'], 'matches_recorded_build_sha': inputs['runtime_library_sha256'] == new_sha,
                 'input_hashes': {k: inputs.get(k) for k in ('bag_sha256', 'host_binary_sha256', 'config_m2dgr_sha256', 'config_camera_sha256')},
                 'launch': receipt['launch'], 'machine_load': receipt.get('machine_load_at_launch'),
                 'candidate': {'accepted': candidate['accepted'], 'count': len(detail['candidate_frame_ids']),
                               'pose_stamps_ns': detail['candidate_frame_ts_ns'],
                               'committed': len(candidate['committed_pose_keys']), 'deferred': len(candidate['deferred_pose_keys']),
                               'weak_before': candidate['weak_dir_info_before'], 'weak_after': candidate['weak_dir_info_after'],
                               'wilson': candidate['wilson_lower_bound'], 'holdout': candidate['holdout_nis']},
                 'freeze': episode.get('frame_freeze'), 'repair': {k: v for k, v in published.items() if k not in ('frames', 'per_frame')},
                 'published_scan_stamps_ns': published.get('frames', []),
                 'published_stamps_all_corrupted': set(published.get('frames', [])) <= shifted,
                 'relay': {'frames': len(frames), 'shifted': len(shifted), 'unshifted': len(frames) - len(shifted), 'window': rows[0]},
                 'deferred_apply': deferred, 'snapshot_fields': cp_fields,
                 'replay': {'frames': int(match[1]), 'start_ns': ns(match[2]), 'end_ns': ns(match[3]), 'applied': int(match[4]), 'queued': int(match[5]), **attrs},
                 'replay_log': replay_line,
                 'host_received_log_count': sum('[NATIVE_REPAIR] received' in line for line in host),
                 'host_applied_log_count': sum('[NATIVE_REPAIR] applied' in line for line in host),
                 'leftover_lines': [line for line in host if '[NATIVE_REPAIR] leftover' in line],
                 'actions': actions, 'frames': summary['frames'], 'episodes': summary['quarantine']['episodes'],
                 'second_and_later_events': summary['quarantine']['second_and_later_events'], 'detection_enabled': summary['detection_enabled'],
                 'lifecycle': {k: summary['lifecycle'].get(k) for k in ('state', 'wait_limit_ns', 'unresolved_segments')},
                 'lifecycle_events': [{k: e.get(k) for k in ('event', 'from_state', 'trusted_version')} for e in summary['lifecycle'].get('events', [])],
                 'native_failures': summary['native_checkpoint'].get('failures'), 'termination': receipt['termination']})
a, b = runs
cp_keys = ('frame', 'voxels', 'nodes', 'points', 'state_pos', 'stamp_ns')
comparison = {'same_candidate_pose_stamps': reference_populations[0] == reference_populations[1],
              'same_published_scan_stamps': a['published_scan_stamps_ns'] == b['published_scan_stamps_ns'],
              'same_replay_bounds_and_count': all(a['replay'][k] == b['replay'][k] for k in ('start_ns', 'end_ns', 'frames')),
              'snapshot_fields_equal': {k: a['snapshot_fields'].get(k) == b['snapshot_fields'].get(k) for k in cp_keys},
              'native_complete_state_or_map_bytes_equal': 'NOT_VERIFIED_no_full_checkpoint_state_or_map_bytes',
              'same_input_and_config_hashes': a['input_hashes'] == b['input_hashes'],
              'different_actual_consumed_suffix': [a['replay'].get('truncated'), b['replay'].get('truncated')]}
build = blob(PREFIX + 'host_change_deferred_stamp/host_build_v4.log').decode(errors='replace').splitlines()
payload = {'target': TARGET, 'base': BASE,
           'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_e82d900/check_archive.py',
           'exit': 0, 'scope': 'Archive Git bytes/hash and execution counters; no bag/native execution, no causal quality claim',
           'integrity': {'matched': len(checks), 'total': len(checks), 'bad': []},
           'runs': runs, 'comparison': comparison,
           'build_signals': [line for line in build if 'Built target laser_mapping' in line or 'CXXABI_' in line or 'Error ' in line or 'failed' in line],
           'unavailable_task_in_target': bool(git('ls-tree', '-r', '--name-only', TARGET, '--', 'docs/UNAVAILABLE_DIAGNOSTIC_TASK_20261112.md').strip())}
output = Path(__file__).with_name('archive_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'target': TARGET, 'integrity': payload['integrity'], 'comparison': comparison,
                  'runs': [{k: r[k] for k in ('arm', 'run_id', 'matches_target_driver', 'matches_recorded_build_sha', 'snapshot_fields', 'replay', 'frames', 'episodes', 'second_and_later_events', 'native_failures')} for r in runs],
                  'diagnostic_task_in_target': payload['unavailable_task_in_target']}, ensure_ascii=False, indent=2))
