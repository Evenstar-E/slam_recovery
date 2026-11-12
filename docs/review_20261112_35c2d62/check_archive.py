"""Read fixed Git data only; never execute the archived research or host."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = '35c2d62b6412d5b651ef6d211a5c8d16a77cc5f1'
PREFIX = 'docs/ali_h_v1_research/'
BASE = 'docs/review_20261112_availability/'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def blob(path):
    return git('show', TARGET + ':' + path)


def data(path):
    return json.loads(blob(path))


manifest = data(PREFIX + 'manifest.json')
integrity = []
for name, item in manifest['artifacts'].items():
    assert '/' not in name and name not in ('.', '..')
    raw = blob(PREFIX + name)
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == item['sha256'] and len(raw) == item['bytes']
    integrity.append({'name': name, 'bytes': len(raw), 'sha256': digest})
assert len(integrity) == 5
assert hashlib.sha256(blob(PREFIX + 'ali_h_v1.py')).hexdigest() == manifest['code_sha256']
runs = []
for key, suffix in [('A', ''), ('B', 'predicted_pose/')]:
    raw = blob(BASE + suffix + 'availability_frames.jsonl.gz')
    rows = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    shadow = [json.loads(line) for line in blob(PREFIX + 'shadow_' + key + '.jsonl').splitlines()]
    t0 = data(PREFIX + 't0_' + key + '.json')
    receipt = data(BASE + suffix + 'receipt.json')
    assert len(rows) == len(shadow) == t0['population']['frames']
    assert hashlib.sha256(raw).hexdigest() == manifest['runs'][key]['frames_sha256']
    for original, saved in zip(rows, shadow):
        assert tuple(original[k] for k in ('run_id', 'kf_id', 'pose_stamp_ns', 'scan_stamp_ns')) == tuple(saved[k] for k in ('run_id', 'kf_id', 'pose_stamp_ns', 'scan_stamp_ns'))
        assert saved['shadow']['state'] == 'UNKNOWN'
        assert saved['channels']['I']['present'] is False
    frame_blocks = {row['pose_stamp_ns'] // 500_000_000 for row in rows}
    expected = set(range(min(frame_blocks), max(frame_blocks) + 1))
    actual = {block['block_id'] for block in t0['blocks']}
    assert actual == expected and t0['population']['blocks'] == len(expected)
    assert sum(block['n_frames'] for block in t0['blocks']) == len(rows)
    empty = [block for block in t0['blocks'] if block['block_id'] not in frame_blocks]
    assert all(block['n_frames'] == 0 and block['state'] == 'UNKNOWN' for block in empty)
    assert receipt['launch']['injection'] == 'NONE'
    runs.append({'run': key, 'frames': len(rows), 'saved_blocks': len(expected),
                 'frame_containing_blocks': len(frame_blocks), 'empty_blocks': empty,
                 'states': dict(Counter(s['shadow']['state'] for s in shadow)),
                 'injection': receipt['launch']['injection'],
                 'sigma_meas_m': receipt['launch']['sigma_meas_m']})
probe_files = git('ls-tree', '-r', '--name-only', TARGET, '--', 'docs/review_20261112_four_host/host_change_trace_cov').decode().splitlines()
ref = data(BASE + 'reference_map_20261112_redo/run_summary.json')
assert ref['detection_enabled'] is False and ref['parameters']['sigma_meas_m'] == 0.12
native = data('docs/review_20261112_four_host/boundary_checkpoint_final_20261112/native_checkpoint_events.json')
result = {'target': TARGET, 'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_35c2d62/check_archive.py',
          'integrity': integrity, 'code_hash_matches_manifest': True, 'runs': runs,
          'old_availability_unchanged': not bool(git('diff', '--name-only', 'e0d403b', TARGET, '--', BASE).strip()),
          'recorded_tests': {name: data(PREFIX + name) for name in ('t1_selftest.json', 't2_prep_selftest.json')},
          'archived_tests_executed': False, 'probe_and_patch_files_in_target': probe_files,
          'host_diagnosis': 'DEVELOPER_REPORTED; no trace_cov_v7.diff or probe artifacts in target',
          'host_root_cause': 'UNKNOWN; before first LIO does not exclude startup effects of changed code',
          'major_blocker': 'ALI-B2-NORMAL-LABELS-20261112-01; user confirmation absent in target',
          'normal_prefix_and_event_labels_required_for_full_evaluation': True,
          'native_checkpoint_event_schema': list(native) if isinstance(native, dict) else {'type': 'list', 'count': len(native)},
          'no_host_ROS_parameter_or_archived_code_execution': True}
output = Path(__file__).with_name('archive_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'recorded_tests'}, ensure_ascii=False, indent=2))
if isinstance(native, dict):
    events = native.get('events', [])
else:
    events = native
for event in events:
    if isinstance(event, dict) and event.get('command') in ('snapshot', 'restore'):
        print('NATIVE_EVENT', json.dumps(event, ensure_ascii=False))
