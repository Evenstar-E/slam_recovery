"""Read only fixed Git archive bytes; no host, bag, archived code or algorithm execution."""
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'd86e57df09c076e531cb2e4edabdc70daac6b668'
BASELINE = 'fafbaf173b873502d248164adff8cd185dfa0dfc'
ARCHIVE = 'docs/review_20261112_four_host/'
PREFIX = ARCHIVE + 'boundary_checkpoint_final_20261112/'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def blob(path):
    return git('show', TARGET + ':' + path)


def read(name):
    return blob(PREFIX + name)


def js(name):
    return json.loads(read(name))


def rows(name):
    return [json.loads(line) for line in read(name).splitlines()]


def decimal_ns(value):
    return int(Decimal(value) * 1_000_000_000)


def fields(ack):
    return dict(re.findall(r'\b([a-z_]+)=([^\s]+)', ack))


def xyz(ack):
    return [float(x) for x in fields(ack)['state_pos'].split(',')]


changed = set(git('diff', '--name-only', BASELINE, TARGET, '--', ARCHIVE).decode().splitlines())
hashes = []
for line in blob(ARCHIVE + 'SHA256SUMS').decode().splitlines():
    expected, relative = line.split(maxsplit=1)
    relative = relative.removeprefix('./')
    assert '..' not in PurePosixPath(relative).parts and not relative.startswith('/')
    path = ARCHIVE + relative
    if path not in changed:
        continue
    actual = hashlib.sha256(blob(path)).hexdigest()
    hashes.append({'path': path, 'expected': expected, 'actual': actual, 'ok': expected == actual})
assert len(hashes) == 23 and all(h['ok'] for h in hashes)
assert changed - {h['path'] for h in hashes} == {ARCHIVE + 'SHA256SUMS'}
receipt = js('receipt.json')
summary = js('run_summary.json')
events = js('native_checkpoint_events.json')
lifecycle = js('lifecycle_events.json')
candidates = rows('candidates.jsonl')
details = rows('candidates_detail.jsonl')
icp = rows('icp_detail.jsonl')
relay = rows('relay_frames.jsonl')
episodes = summary['quarantine']['episode_detail']
diag = summary['frame_diagnostics']
assert len(candidates) == len(details) == len(episodes) == 2
assert len(diag) == summary['frames']['paired'] == 526
assert summary['lifecycle']['events'] == lifecycle
assert summary['native_checkpoint']['events'] == events
assert summary['native_checkpoint_actions'] == [e for e in events if e['command'] != 'status']
recorded_driver = read('recovery_node_source.sha256').decode().split()[0]
actual_driver = hashlib.sha256(blob('slam_recovery/ros/recovery_node.py')).hexdigest()
assert receipt['inputs']['recovery_node_source'] == recorded_driver == actual_driver
build_hashes = blob(ARCHIVE + 'host_change_boundary_checkpoint/new_binary_sha.txt').decode().splitlines()
assert receipt['inputs']['runtime_library_sha256'] == build_hashes[0].split()[0]
assert receipt['inputs']['host_binary_sha256'] == build_hashes[1].split()[0]
host = read('host.log').decode(errors='replace').splitlines()
ansi = re.compile(r'\x1b\[[0-9;]*m')
clean = [ansi.sub('', line) for line in host]


def evidence(pattern):
    return [{'line': i + 1, 'text': line} for i, line in enumerate(clean) if re.search(pattern, line)]


snapshots = evidence(r'\[NATIVE_CHECKPOINT\] snapshot stamp=')
applications = evidence(r'\[NATIVE_CHECKPOINT\] deferred apply cmd=')
assert len(snapshots) == 2 and len(applications) == 4
closings = [e for e in lifecycle if e['event'] == 'wait_limit_closed']
assert len(closings) == 2 and all(e['from_state'] == 'ABORTED' for e in lifecycle if e['event'] == 'rearm')
boundaries = []
for i, ep in enumerate(episodes):
    native = ep['native_checkpoint']
    ack = fields(native['ack'])
    cp_ns = int(ack['stamp_ns'])
    cp_print = re.search(r'snapshot stamp=([0-9.]+)', snapshots[i]['text']).group(1)
    apply = [a for a in applications if 'cmd=snapshot ' in a['text']][i]
    stamp_fields = re.findall(r'stamp_ns=(-?\d+)', apply['text'])
    assert len(stamp_fields) == 2
    assert int(stamp_fields[0]) == ep['quarantine_start_ns']
    assert int(stamp_fields[1]) == cp_ns
    at_lio = re.search(r'at_lio=([0-9.]+)', apply['text']).group(1)
    assert cp_ns <= ep['quarantine_start_ns'] <= ep['trigger_ts_ns']
    assert decimal_ns(cp_print) == ep['incumbent_basis']['anchor_timestamp_ns']
    boundaries.append({'episode': i + 1, 'trigger_ns': ep['trigger_ts_ns'],
                       'quarantine_start_ns': ep['quarantine_start_ns'],
                       'checkpoint_ack_ns': cp_ns, 'checkpoint_minus_qstart_ns': cp_ns - ep['quarantine_start_ns'],
                       'checkpoint_minus_trigger_ns': cp_ns - ep['trigger_ts_ns'],
                       'checkpoint_printed_seconds': cp_print, 'printed_decimal_ns': decimal_ns(cp_print),
                       'ack_minus_printed_decimal_ns': cp_ns - decimal_ns(cp_print),
                       'application_group_printed_seconds': at_lio,
                       'application_group_minus_requested_ns': decimal_ns(at_lio) - ep['quarantine_start_ns'],
                       'result': 'PASS_THIS_RUN_checkpoint_label_before_boundary_and_later_actual_apply_confirmed',
                       'snapshot_evidence': snapshots[i], 'apply_evidence': apply,
                       'scope': 'Actual apply plus cp label/anchor/map counts checked; full native state/cache time equivalence requires source/state validation.'})

received = evidence(r'\[NATIVE_REPAIR\] received stamp=')
applied = evidence(r'\[NATIVE_REPAIR\] applied by group')
published = episodes[0]['repair_publish']['frames']
assert len(received) == len(applied) == len(published) == len(set(published)) == 23
received_matches = []
applied_matches = []
for lines, output in ((received, received_matches), (applied, applied_matches)):
    for line in lines:
        printed = re.search(r'(?:received stamp| stamp)=([0-9.]+)', line['text']).group(1)
        print_ns = decimal_ns(printed)
        candidates_ns = sorted(published, key=lambda n: abs(n - print_ns))
        expected = candidates_ns[0]
        assert abs(expected - print_ns) <= math.ulp(float(printed)) * 1e9 + 1  # decimal display rounds to one ns
        points = int(re.search(r'points=(\d+)', line['text']).group(1))
        output.append({'source_scan_ns': expected, 'printed_seconds': printed,
                       'print_minus_exact_ns': print_ns - expected, 'points': points, 'line': line['line']})
assert {x['source_scan_ns'] for x in received_matches} == set(published)
assert {x['source_scan_ns'] for x in applied_matches} == set(published)
assert {x['source_scan_ns']: x['points'] for x in received_matches} == {x['source_scan_ns']: x['points'] for x in applied_matches}
replay_line = evidence(r'\[NATIVE_CHECKPOINT\] reprocess #')[0]
match = re.search(r'(\d+) frames replayed over \[([0-9.]+) .. ([0-9.]+)\].*replayed_within_end=(\d+) replayed_suffix=(\d+) end_stamp=(\d+), map now (\d+) voxels/(\d+) points', replay_line['text'])
total, start, end, within, suffix, replay_end_ns, voxels, points = match.groups()
total, within, suffix, replay_end_ns, voxels, points = map(int, (total, within, suffix, replay_end_ns, voxels, points))
assert total == within + suffix == 794
reprocess = next(e for e in events if e['command'] == 'reprocess')
resume1 = next(e for e in events if e['command'] == 'resume')
rp_fields = fields(reprocess['ack'])
assert int(rp_fields['repair_received']) == int(rp_fields['repair_applied']) == 23
assert int(rp_fields['repair_queued']) == int(rp_fields['repair_dropped']) == int(rp_fields['set_state']) == 0
assert int(rp_fields['replay_within_end']) == within and int(rp_fields['replay_suffix']) == suffix
assert replay_end_ns == episodes[0]['frame_freeze']['frozen_at_ns'] + 100_000_000
assert not any(e['command'] == 'set_state' for e in events)
relay_frames = [r for r in relay if r['event'] == 'frame']
shifted = {r['stamp_ns'] for r in relay_frames if r['shifted']}
assert len(relay_frames) == 598 and len(shifted) == 59 and set(published) <= shifted
unrepaired = sorted(shifted - set(published))
assert len(unrepaired) == 36
assert all(len(c['committed_pose_keys']) == (23 if i == 0 else 0) for i, c in enumerate(candidates))
population = []
for i, (ep, candidate, close) in enumerate(zip(episodes, candidates, closings)):
    assert details[i]['candidate_frame_ids'] == list(map(int, details[i]['repaired_poses'].keys()))
    assert len(details[i]['candidate_frame_ids']) == ep['candidate_frames']
    stamps = [d['ts_ns'] for d in diag]
    closed_ns = close['closed_ns']
    population.append({'episode': i + 1, 'mode': candidate['mode'], 'accepted': candidate['accepted'],
                       'decision_ns': candidate['t_decision_ns'], 'candidate_frames': ep['candidate_frames'],
                       'committed_keys': candidate['committed_pose_keys'],
                       'paired_benefit': ep['paired_evidence'], 'icp': icp[i],
                       'wait_closed_ns': closed_ns, 't_start_ns': close['t_start_ns'], 't_end_ns': close['t_end_ns'],
                       'unresolved_count': len(close['frames_unresolved']), 'unresolved_keys': close['frames_unresolved'],
                       'strictly_after_close_paired': sum(t > closed_ns for t in stamps),
                       'first_pair_after_close_ns': next((t for t in stamps if t > closed_ns), None),
                       'last_pair_ns': stamps[-1], 'close_to_last_pair_s': (stamps[-1] - closed_ns) / 1e9,
                       'trigger_to_end_inclusive_paired': sum(t >= ep['trigger_ts_ns'] for t in stamps),
                       'close_path': 'wait_limit_closed then rearm from ABORTED, not fully resolved commit_closed',
                       'native_command': ep['native_checkpoint']})
negative_latency = [e for e in events if e.get('received_s', 0) < 0]
result = {
    'target': TARGET, 'baseline': BASELINE, 'exit': 0,
    'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_d86e57d/check_archive.py',
    'scope': 'New archive and changed four_host paths only; no algorithm/host execution or old-run replay',
    'integrity': {'matched': len(hashes), 'total': len(hashes), 'checks': hashes,
                  'new_run_files': sum(h['path'].startswith(PREFIX) for h in hashes),
                  'excluded_manifest_self': ARCHIVE + 'SHA256SUMS'},
    'identity': {'receipt': receipt, 'driver_matches_exact_target': True,
                 'library_and_binary_match_v6_build_declaration': True,
                 'raw_bag_library_binary_runtime_files': 'NOT_READ_remote_hash_declaration_only'},
    'boundaries': boundaries,
    'receipt_application_separation': {'deferred_arrangement_events': [e for e in events if 'deferred stamp=' in e.get('ack', '')],
                                      'actual_apply_host_lines': applications,
                                      'non_status_action_count': len(summary['native_checkpoint_actions']),
                                      'all_exported_events_count': len(events),
                                      'summary_copies_consistent_after_status_filter': True},
    'repair': {'published': 23, 'received': 23, 'applied': 23, 'leftover_evidence': evidence(r'\[NATIVE_REPAIR\] leftover'),
               'received_identity_matches': received_matches, 'applied_identity_matches': applied_matches,
               'stamp_precision': 'Printed double has <=one ULP plus one-ns decimal-rounding difference from exact scan_ns; no false exact-ns identity assertion',
               'repair_publish': episodes[0]['repair_publish'],
               'actual_pointcloud_bytes_or_full_record_layout': 'NOT_READ_no_wire_cloud_archive_in_this_run'},
    'replay': {'total_groups': total, 'within_end': within, 'suffix': suffix,
               'start_printed_seconds': start, 'end_printed_seconds': end,
               'end_stamp_ns': replay_end_ns, 'map_voxels': voxels, 'map_points': points,
               'replay_evidence': replay_line, 'point_population_evidence': evidence(r'\[NATIVE_CHECKPOINT\] replay points:'),
               'set_state_command_count': 0, 'writeback_skip': episodes[0].get('native_writeback_skipped'),
               'aggregate_population': 'PASS_244_plus550_equals794_reported_loop_processed',
               'all_input_identity_fate': 'UNKNOWN_no_per_group_identity_manifest_or_all_native_consumed_input_list',
               'reprocess_wall_duration_s': reprocess['ack_wall'] - reprocess['wall'],
               'reprocess_resume_xyz_distance_m': math.dist(xyz(reprocess['ack']), xyz(resume1['ack'])),
               'reprocess_xyz': xyz(reprocess['ack']), 'resume_xyz': xyz(resume1['ack']),
               'ack_delta_scope': 'Different command times; not instantaneous GT jump or full state equivalence'},
    'events': population,
    'tail': {'strict_close1_to_trigger2_paired': sum(closings[0]['closed_ns'] < d['ts_ns'] < episodes[1]['trigger_ts_ns'] for d in diag),
             'after_e2_close_paired': population[1]['strictly_after_close_paired'],
             'after_e2_close_span_to_last_s': population[1]['close_to_last_pair_s'],
             'e2_resume_event': [e for e in events if e['command'] == 'resume'][-1],
             'e2_restore_replay_or_held_history_identity': 'UNKNOWN_no_second_reprocess_or_explicit_suffix_replay_population_in_archive',
             'post_restore_future_output_is_not_full_rollback_catchup': True},
    'damage': {'relay_frames': len(relay_frames), 'shifted_actual': len(shifted), 'repair_scan_subset': len(published),
               'unrepaired_shifted': len(unrepaired), 'unrepaired_scan_stamps': unrepaired,
               'unrepaired_after_last_published': sum(t > max(published) for t in unrepaired),
               'shifted_in_e2_quarantine_or_later': sum(t >= episodes[1]['quarantine_start_ns'] for t in shifted),
               'injection_window': relay[0], 'scope': 'Controlled E1 injection only; E2 is lifecycle exercise without new injected fault'},
    'run': {'frames': summary['frames'], 'pairing': summary['pairing'], 'runtime': summary['runtime'],
            'first_pair_ns': diag[0]['ts_ns'], 'last_pair_ns': diag[-1]['ts_ns'],
            'final_state': summary['final_state'], 'quarantine_open_at_exit': summary['quarantine_open_at_exit'],
            'native_counters': {k: v for k, v in summary['native_checkpoint'].items() if k not in ('events', 'snapshot_ack_s')},
            'status_received_negative_s_events': negative_latency,
            'status_latency_scope': 'received_s reused stale receipt metadata for status entries; not usable measured RPC latency',
            'host_log_lines': len(clean), 'host_log_footer': clean[-5:],
            'graceful_host_exit': 'UNKNOWN_planned_group_kill_host_exit_null_no_clean_exit_marker',
            'build': {'library_declared_built': True, 'overall_exit': '1_DEVELOPER_REPORTED_vikit_test_ABI',
                      'evidence_path': ARCHIVE + 'host_change_boundary_checkpoint/BUILD.md'},
            'decision_errors': summary['decision_errors']},
    'scientific_boundary': {'automatic_detection': 'NOT_EXECUTED_detection_off_scripted',
                            'natural_fault_or_true_second_fault': 'NOT_EXECUTED',
                            'whole_native_state_map_equivalence': 'UNKNOWN_requires_source_and_state_evidence',
                            'independent_trajectory_map_net_quality': 'UNKNOWN_NOT_EVALUATED',
                            'held_group_or_unresolved_population_cannot_count_recovery_success': True},
    'no_native_ros_bag_parameter_or_archive_script_execution': True,
}
output = Path(__file__).with_name('archive_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'target': TARGET, 'exit': 0, 'hashes_matched': len(hashes),
                  'checkpoint_minus_qstart_ns': [b['checkpoint_minus_qstart_ns'] for b in boundaries],
                  'replay_groups': total, 'repair_applied': len(applied),
                  'unresolved_counts': [e['unresolved_count'] for e in population],
                  'tail_paired': population[1]['strictly_after_close_paired'],
                  'tail_span_s': population[1]['close_to_last_pair_s'],
                  'driver_matches_target': True}, ensure_ascii=False))
