"""Read fixed Git archives only; no archived code, bag, host or ICP execution."""
from bisect import bisect_left
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'fafbaf173b873502d248164adff8cd185dfa0dfc'
BASE = 'docs/review_20261112_availability/'
NEW = BASE + 'reference_map_20261112_redo/'
OLD = BASE + 'reference_map_20261112/'
DIAG = BASE + 'predicted_pose/'


def blob(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', TARGET + ':' + path])


def manifest(prefix):
    result = []
    for line in blob(prefix + 'SHA256SUMS').decode().splitlines():
        expected, name = line.split(maxsplit=1)
        name = name.removeprefix('./')
        assert '..' not in PurePosixPath(name).parts and not name.startswith('/')
        actual = hashlib.sha256(blob(prefix + name)).hexdigest()
        result.append({'path': name, 'expected': expected, 'actual': actual, 'ok': expected == actual})
    return result


new_integrity = manifest(NEW)
assert len(new_integrity) == 12 and all(c['ok'] for c in new_integrity)
old_integrity = manifest(OLD)
assert [c['path'] for c in old_integrity if not c['ok']] == ['REPORT.md']
receipt = json.loads(blob(NEW + 'receipt.json'))
summary = json.loads(blob(NEW + 'run_summary.json'))
diag_receipt = json.loads(blob(DIAG + 'receipt.json'))
diag_summary = json.loads(blob(DIAG + 'run_summary.json'))
assert receipt['inputs']['recovery_node_source'] == hashlib.sha256(blob('slam_recovery/ros/recovery_node.py')).hexdigest()
assert receipt['inputs']['config_m2dgr_sha256'] == hashlib.sha256(blob(NEW + 'refmap_m2dgr.yaml')).hexdigest()
assert receipt['inputs']['bag_sha256'] == diag_receipt['inputs']['bag_sha256']
rows = [json.loads(line) for line in gzip.decompress(blob(DIAG + 'availability_frames.jsonl.gz')).splitlines()]
assert len(rows) == len(summary['frame_diagnostics']) == 544
assert [r['pose_stamp_ns'] for r in rows] == [r['ts_ns'] for r in summary['frame_diagnostics']]
assert all(row['run_id'] == diag_receipt['run_id'] for row in rows)
poses = []
for line in blob(NEW + 'lidar_poses.txt').decode().splitlines():
    fields = line.split()
    stamp_ns = int(Decimal(fields[0]) * 1_000_000_000)
    values = [float(v) for v in fields[1:]]
    assert len(values) == 7
    poses.append((stamp_ns, values))
stamps = [p[0] for p in poses]
assert len(poses) == 819 and all(a <= b for a, b in zip(stamps, stamps[1:]))
pcd = blob(NEW + 'all_downsampled_points.pcd')
head, raw = pcd.split(b'DATA binary\n', 1)
assert b'FIELDS x y z rgb' in head and b'SIZE 4 4 4 4' in head
xyz = [p[:3] for p in struct.iter_unpack('<fffI', raw)]
assert len(xyz) == 15647 and len(pcd) == 250534


def matched(row):
    stamp = row['pose_stamp_ns']
    j = bisect_left(stamps, stamp)
    options = [i for i in (j - 1, j) if 0 <= i < len(stamps)]
    i = min(options, key=lambda i: abs(stamps[i] - stamp))
    assert abs(stamps[i] - stamp) <= 1000, (row['kf_id'], stamps[i], stamp)
    return poses[i]


comparison = []
for row in rows:
    stamp, pose = matched(row)
    T = row['T_wb']
    diagnostic_position = [T[3], T[7], T[11]]
    comparison.append({'kf_id': row['kf_id'], 'stamp_ns': row['pose_stamp_ns'],
                       'pose_log_stamp_delta_ns': stamp - row['pose_stamp_ns'],
                       'diagnostic_position': diagnostic_position, 'map_run_position': pose[:3],
                       'unregistered_position_difference_m': math.dist(diagnostic_position, pose[:3])})
selected = []
for key in (22, 157, 228):
    row = next(r for r in rows if r['kf_id'] == key)
    T = row['T_wb']; support = row['support']
    distances = []
    for sample in support['points']:
        p = sample['body']
        world = [sum(T[i * 4 + k] * p[k] for k in range(3)) + T[i * 4 + 3] for i in range(3)]
        distances.append(min(math.dist(world, ref) for ref in xyz))
    count = sum(d <= 1.0 for d in distances)
    selected.append({**next(c for c in comparison if c['kf_id'] == key),
                     'support_population': support.get('points_total', support.get('sampled_query_count')),
                     'saved_samples': len(distances), 'within_1m': count,
                     'saved_sample_fraction': count / len(distances),
                     'median_distance_m': statistics.median(distances),
                     'partial_sample': support.get('points_total', support.get('sampled_query_count')) > len(distances),
                     'score_scope': 'Saved samples at recorded pose, identity gauge only; not independently registered/GT quality'})
max_comparison = max(comparison, key=lambda c: c['unregistered_position_difference_m'])
first_over_1m = next((c for c in comparison if c['unregistered_position_difference_m'] > 1), None)
host_lines = blob(NEW + 'host.log').decode(errors='replace').splitlines()
play_lines = blob(NEW + 'play.log').decode(errors='replace').splitlines()
assert any(line.strip() == 'Done.' for line in play_lines)
assert summary['native_checkpoint']['restores'] == summary['native_checkpoint']['reprocesses'] == 0
assert len(summary['quarantine']['trigger_ts_ns']) == 0
first_actions = [a for a in diag_summary['native_checkpoint_actions'] if a['command'] in ('hold', 'restore', 'resume')][:3]
result = {
    'target': TARGET, 'exit': 0,
    'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_fafbaf1/check_archive.py',
    'scope': 'Fixed Git hashes, pose timestamp population and three saved-sample distance checks. No ICP, GT or causal experiment.',
    'integrity': {'new_archive': new_integrity, 'new_matched': 12, 'new_total': 12,
                  'previous_archive': old_integrity, 'previous_matched': 10, 'previous_total': 11,
                  'previous_report_failure': 'Target appends section6 to REPORT but preserves original SHA256SUMS; other10 artifacts unchanged.'},
    'run': {'receipt': receipt, 'pairing': summary['pairing'], 'frames': summary['frames'], 'runtime': summary['runtime'],
            'first_paired_ns': summary['frame_diagnostics'][0]['ts_ns'], 'last_paired_ns': summary['frame_diagnostics'][-1]['ts_ns'],
            'pose_rows': len(poses), 'pose_start_ns': poses[0][0], 'pose_end_ns': poses[-1][0],
            'pose_span_s': (poses[-1][0] - poses[0][0]) * 1e-9,
            'pose_xyz_ranges': [[min(p[1][i] for p in poses), max(p[1][i] for p in poses)] for i in range(3)],
            'play_footer': play_lines[-7:], 'host_footer': host_lines[-3:],
            'host_last_snapshot_lines': [l for l in host_lines if 'snapshot stamp=' in l][-1:],
            'native_checkpoint_counters': {k: summary['native_checkpoint'][k] for k in ('snapshots', 'restores', 'reprocesses', 'holds', 'resumes', 'failures', 'snapshot_ack_timeouts')},
            'detection_enabled': summary['detection_enabled'], 'actual_repair_publish': summary['launch_args']['repair_publish']},
    'pcd': {'points': len(xyz), 'bytes': len(pcd), 'sha256': hashlib.sha256(pcd).hexdigest(),
            'raw_pcd': 'NOT_READ_remote_hash_only', 'quality': 'UNKNOWN_not_GT'},
    'diagnostic_run': {'run_id': diag_receipt['run_id'], 'inputs': diag_receipt['inputs'], 'launch': diag_receipt['launch'],
                       'native_checkpoint_counters': {k: diag_summary['native_checkpoint'][k] for k in ('restores', 'reprocesses', 'holds', 'resumes')},
                       'first_actions': first_actions},
    'comparability': {'same_input_bag_hash': True, 'same_host_binary_hash': True,
                      'same_runtime_library_hash': receipt['inputs']['runtime_library_sha256'] == diag_receipt['inputs']['runtime_library_sha256'],
                      'same_driver_hash': receipt['inputs']['recovery_node_source'] == diag_receipt['inputs']['recovery_node_source'],
                      'same_config_hash': receipt['inputs']['config_m2dgr_sha256'] == diag_receipt['inputs']['config_m2dgr_sha256'],
                      'same_544_pose_stamp_population': True,
                      'max_pose_log_rounding_delta_ns': max(abs(c['pose_log_stamp_delta_ns']) for c in comparison),
                      'maximum_unregistered_difference': max_comparison, 'first_over_1m_unregistered': first_over_1m,
                      'causal_verdict': 'UNKNOWN_intervention_host_library_driver_config_and_execution_differ_not_paired_control',
                      'independent_reference_rule': 'Different estimated trajectories do not alone invalidate an independent scene reference; registration, visible support and reference validity must be established. Do not force diagnostic poses into reference to manufacture agreement.'},
    'three_frame_saved_sample_controls': selected,
    'all_302_frames_or_icp_scoring': 'NOT_EXECUTED_no_new_complete_score_artifact',
    'ali_h_new_implementation_or_receipt': 'NOT_FOUND_in_development_delta',
    'no_native_bag_or_parameter_execution': True,
}
output = Path(__file__).with_name('archive_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ('integrity', 'diagnostic_run')}, ensure_ascii=False))
