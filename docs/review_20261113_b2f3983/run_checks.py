"""Read-only fixed Git data/runner audit. Standard library; no archive imports or ROS."""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MAIN = 'b2f3983801e6113f3c3626df0d95783666e1c24f'
ARCHIVE = '4f205ef'
BASE = 'docs/review_20261112_four_host/'
P = BASE + 'fastlio2_independent_20261113/'
HASHES = {}


def blob(path):
    data = subprocess.check_output(['git', '-C', str(ROOT), 'show', ARCHIVE + ':' + path])
    HASHES[path] = hashlib.sha256(data).hexdigest()
    return data


def text(path):
    return blob(path).decode('utf-8', errors='replace')


def clean(data):
    return re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', data)


actual = json.loads(text(P + 'run2/analysis.json'))
shared = json.loads(text(BASE + 'fastlio2_shared_campus12_20261112/analysis.json'))
a, b = actual['/Odometry'], shared['topics']['/Odometry']
for key in ('messages', 'first_stamp_ns', 'last_stamp_ns', 'max_gap_s',
            'tail_after_E2_s', 'messages_after_E2'):
    assert a[key] == b[key]
assert actual['events_ns'] == shared['events_ns']
assert a['messages'] == actual['topics']['/Odometry'] == 4186
assert sum(actual['topics'].values()) == 12980
info = text(P + 'run2/bag_info.txt')
assert re.search(r'messages:\s+12980\b', info)
steps = sum(g['step_m'] for g in a['gaps_gt_1s'])
length_all = a['path_length_m'] + steps
assert abs(length_all - b['path_length_m']) < .1
pos_differences = {}
for event in ('E1', 'E2'):
    aa, bb = a['at_' + event], b['at_' + event]
    assert aa['stamp_ns'] == bb['stamp_ns']
    assert math.isclose((aa['stamp_ns'] - actual['events_ns'][event]) / 1e9,
                        aa['dt_to_declared_s'], abs_tol=1e-12)
    pos_differences[event] = math.sqrt(sum((x - y)**2 for x, y in zip(aa['pos'], bb['pos'])))
assert len(a['gaps_gt_1s']) == 2
for ga, gb in zip(a['gaps_gt_1s'], b['gaps_gt_1s']):
    assert all(ga[k] == gb[k] for k in ('from_ns', 'to_ns', 'dt_s'))

log = clean(text(P + 'run2/fastlio_node.log'))
log1 = clean(text(P + 'run1/fastlio_node.log'))
shared_log = clean(text(BASE + 'fastlio2_shared_campus12_20261112/fastlio_node.log'))
markers = {}
for label, pattern in [('sleep', 'Over-degeneracy has happened'),
                       ('rebuild', 'construct a new map'), ('imu_initial', 'IMU Initial Done')]:
    matches = [(i, l.strip()[:180]) for i, l in enumerate(log.splitlines(), 1) if pattern in l]
    markers[label] = {'count': len(matches), 'matches': matches}
assert markers['sleep']['count'] == markers['rebuild']['count'] == 2
runner = text(P + 'run_fastlio2_independent.sh')
runner_lines = runner.splitlines()
record_start = next(i for i, line in enumerate(runner_lines) if 'setsid rosbag record' in line)
record_command = '\n'.join(runner_lines[record_start:record_start + 3])
assert '/cloud_registered_body' in record_command and '/cloud_registered ' in record_command
runner_log = text(P + 'run2/runner.log')
record_log = text(P + 'run2/record.log')
binary = text(P + 'run2/binary_identity.txt')
source = text(P + 'source_identity.txt')
source_commit = re.search(r'source_commit (\w+)', source).group(1)
source_commit_subject = subprocess.check_output(
    ['git', '-C', str(ROOT), 'show', '-s', '--format=%s', source_commit]).decode().strip()
assert source_commit_subject == 'Record the FAST-LIVO2 stop and the FAST-LIO2 independent-build task'
process = text(P + 'run1/process_identity.txt')
assert '692359 /home/R26534/fastlio2_ws/devel/lib/fast_lio/fastlio_mapping' in process
build = text(P + 'build2.log')
assert 'Built target fastlio_mapping' in build
play = clean(text(P + 'run1/play.log'))
progress = [float(x) for x in re.findall(r'Duration:\s+([0-9.]+)', play)]
load = text(P + 'run2/loadavg.log')
entries = subprocess.check_output(
    ['git', '-C', str(ROOT), 'ls-tree', '-r', '--name-only', ARCHIVE, '--', P]).decode().splitlines()
missing = [p for p in ('run2/play.log', 'run2/frontend.bag', 'run2/frontend_sha256.txt',
                       'run2/cgroup_start.txt', 'run2/cgroup_120s.txt') if P + p not in entries]
report = {
    'main': MAIN, 'archive': subprocess.check_output(
        ['git', '-C', str(ROOT), 'rev-parse', ARCHIVE]).decode().strip(),
    'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_b2f3983/run_checks.py',
    'scope': 'fixed archived logs and saved summaries only, no actual bag parsing/host/code execution',
    'independent_workspace_evidence': {
        'build_target_finished': True, 'source_commit_declaration': source_commit,
        'source_commit_subject_in_this_repo': source_commit_subject,
        'source_declaration': source.splitlines(), 'run2_binary_identity': binary.splitlines(),
        'original_upstream_implementation_identity': 'NOT_VERIFIED',
        'run1_actual_process_in_new_workspace': True},
    'run1': {'progress_values': len(progress), 'last_duration_s': progress[-1] if progress else None,
             'has_done_marker': bool(re.search(r'\bDone\.?', play)),
             'imu_initial_markers': log1.count('IMU Initial Done'),
             'rebuild_markers': log1.count('construct a new map'),
             'zero_messages_reindex': 'DEVELOPER_REPORTED: no bag/reindex-info artifact here',
             'root_cause': 'UNKNOWN: load attribution and changed-recording claims not established'},
    'run2': {
        'shared_imu_initial_markers': shared_log.count('IMU Initial Done'),
        'run2_imu_initial_markers': log.count('IMU Initial Done'),
        'record_topics_actual': actual['topics'], 'messages_sum': sum(actual['topics'].values()),
        'bag_info_consistent_with_analysis': True, 'node_markers': markers,
        'saved_metrics_shared_compatible': True, 'position_differences_m': pos_differences,
        'event_to_first_output_s_not_outage': {ev: a['at_' + ev]['dt_to_declared_s'] for ev in ('E1', 'E2')},
        'actual_saved_outages': a['gaps_gt_1s'],
        'tail_after_E2_declared_s': a['tail_after_E2_s'], 'messages_after_E2_declared': a['messages_after_E2'],
        'continuous_tail': 'NOT_ESTABLISHED: includes the 26.899s gap after E2',
        'path_lengths_m': {'excluding_gaps': a['path_length_m'], 'gap_steps': steps,
                           'including_gaps': length_all, 'shared_including_gaps': b['path_length_m']},
        'runner_log_has_rate_120s': 'bag_duration_after_120s=' in runner_log,
        'runner_log_has_cgroup_delta': 'cgroup_throttled_delta=' in runner_log,
        'runner_records_clouds': True, 'record_command': record_command,
        'runner_log': runner_log.splitlines(), 'missing_originals': missing,
        'play_rate_092x': 'DEVELOPER_REPORTED_NOT_RECOMPUTED',
        'recovery_wiring': 'NOT_IMPLEMENTED'},
    'hashes': HASHES,
    'no_installation_production_edit_native_archive_CLI_execution': True}
import sys
output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'main': MAIN, 'archive': report['archive'],
                  'shared_imu_initial_markers': report['run2']['shared_imu_initial_markers'],
                  'run2_imu_initial_markers': report['run2']['run2_imu_initial_markers'],
                  'messages': a['messages'], 'saved_metrics_shared_compatible': True,
                  'missing_originals': missing, 'output': str(output)}, ensure_ascii=False, indent=2))
