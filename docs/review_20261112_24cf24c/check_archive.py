"""Read fixed Git evidence only. Never execute the archived research or host scripts."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = '24cf24cbea76d08011e3933b3b11c48dd7588b7b'
PREFIX = 'docs/ali_h_v1_research/'
BASE = 'docs/review_20261112_availability/'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def blob(path):
    return git('show', TARGET + ':' + path)


manifest = json.loads(blob(PREFIX + 'manifest.json'))
integrity = []
for name, record in manifest['artifacts'].items():
    assert '/' not in name and name not in ('.', '..')
    raw = blob(PREFIX + name)
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == record['sha256'] and len(raw) == record['bytes']
    integrity.append({'name': name, 'sha256': digest, 'bytes': len(raw), 'ok': True})
assert len(integrity) == 5
source = blob(PREFIX + 'ali_h_v1.py')
assert hashlib.sha256(source).hexdigest() == manifest['code_sha256']
results = []
for key, suffix in [('A', ''), ('B', 'predicted_pose/')]:
    original_bytes = blob(BASE + suffix + 'availability_frames.jsonl.gz')
    original = [json.loads(line) for line in gzip.decompress(original_bytes).splitlines()]
    shadow = [json.loads(line) for line in blob(PREFIX + 'shadow_' + key + '.jsonl').splitlines()]
    t0 = json.loads(blob(PREFIX + 't0_' + key + '.json'))
    assert len(original) == len(shadow) == t0['population']['frames']
    assert hashlib.sha256(original_bytes).hexdigest() == manifest['runs'][key]['frames_sha256'] == t0['inputs']['frames_sha256']
    assert hashlib.sha256(blob(BASE + suffix + 'receipt.json')).hexdigest() == t0['inputs']['receipt_sha256']
    assert hashlib.sha256(blob(BASE + suffix + 'run_summary.json')).hexdigest() == t0['inputs']['summary_sha256']
    reason_counts = Counter()
    sources = Counter()
    blocks = set()
    status_counts = Counter()
    for raw, saved in zip(original, shadow):
        assert (raw['run_id'], raw['kf_id'], raw['pose_stamp_ns'], raw['scan_stamp_ns']) == (saved['run_id'], saved['kf_id'], saved['pose_stamp_ns'], saved['scan_stamp_ns'])
        assert saved['old']['status'] == raw['status'] and saved['old']['nis_source'] == raw['nis']['source']
        assert saved['old']['nis_reference'] == raw['nis']['selected_reference_source']
        assert saved['support']['supported_fraction'] == raw['support'].get('supported_fraction')
        assert saved['shadow']['state'] == 'UNKNOWN' and saved['shadow']['scope'] == 'NONE'
        assert saved['channels']['I']['present'] is False and saved['channels']['I']['qualification'] == 'NOT_AVAILABLE'
        assert saved['block_id'] == raw['pose_stamp_ns'] // 500_000_000
        blocks.add(saved['block_id']); status_counts[saved['shadow']['state']] += 1
        for channel in ('M', 'T'):
            item = saved['channels'][channel]
            if item['present']:
                assert item['source'] == ('node_map' if channel == 'M' else 'prev_scan')
                assert item['fresh'] is True and item['score'] == raw['nis']['effective_nis']
                sources[channel + '_all'] += 1
                if raw['status'] == 'UNAVAILABLE':
                    sources[channel + '_unavailable'] += 1
        if raw['status'] == 'UNAVAILABLE':
            reason_counts.update(saved['old']['reasons'])
    assert len(blocks) == t0['population']['blocks']
    assert dict(reason_counts) == t0['old_unavailable_reasons']
    assert dict(status_counts) == t0['state_counts_by_frame']
    for channel in ('M', 'T'):
        assert sources[channel + '_all'] == t0['channel_availability'][channel + '_present']
        assert sources[channel + '_unavailable'] == t0['channel_availability'][channel + '_present_in_unavailable']
    grouped = {}
    for saved in shadow:
        grouped.setdefault(saved['block_id'], []).append(saved)
    block_statuses = {channel: Counter() for channel in ('M', 'T', 'I')}
    for block_id, group in grouped.items():
        contexts = {saved['map_support'] for saved in group}
        expected_context = next(iter(contexts)) if len(contexts) == 1 else 'MIXED'
        recorded_block = next(b for b in t0['blocks'] if b['block_id'] == block_id)
        assert recorded_block['context'] == expected_context
        for channel in ('M', 'T'):
            present = sum(saved['channels'][channel]['present'] for saved in group)
            assert present == recorded_block['fresh_count'][channel]
            derived = 'MISSING' if present == 0 else 'UNQUALIFIED/OUT_OF_SUPPORT' if len(contexts) > 1 else 'UNQUALIFIED/BLOCKED'
            block_statuses[channel][derived] += 1
        block_statuses['I']['NOT_AVAILABLE'] += 1
    block_statuses = {channel: dict(counts) for channel, counts in block_statuses.items()}
    assert block_statuses == t0['block_channel_status']
    assert {b['block_id'] for b in t0['blocks']} == blocks
    assert sum(b['n_frames'] for b in t0['blocks']) == len(shadow)
    results.append({'run': key, 'frames': len(original), 'blocks': len(blocks), 'status_counts': dict(status_counts),
                    'source_counts': dict(sources), 'old_unavailable_reasons': dict(reason_counts),
                    'block_channel_status': block_statuses, 'identity_old_fields_source_scores_match': True,
                    'calibration': t0['calibration'], 'missing_items': t0['missing_items']})
t1 = json.loads(blob(PREFIX + 't1_selftest.json'))
t2 = json.loads(blob(PREFIX + 't2_prep_selftest.json'))
print('SELFTEST_SCHEMA', json.dumps({'T1': t1, 'T2': t2}, ensure_ascii=False))
result = {'target': TARGET, 'exit': 0,
          'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_24cf24c/check_archive.py',
          'scope': 'Research artifacts checksum and saved-row consistency, not independent execution of observer/selftests or true classification validation',
          'integrity': integrity, 'code_hash_matches_manifest': True,
          'runs': results, 'selftest_recorded': {'T1': t1, 'T2': t2},
          'selftests_independently_executed': False,
          'no_original_archive_changes': not bool(git('diff', '--name-only', 'be35af9', TARGET, '--', BASE).strip()),
          'no_shared_algorithm_changes': not bool(git('diff', '--name-only', 'be35af9', TARGET, '--', 'slam_recovery').strip()),
          'failure_runs_100744Z_101116Z': 'DEVELOPER_REPORTED_no_receipt_host_log_or_new_host_patch_in_target',
          'failure_root_cause': 'UNKNOWN_reported_plugin_error_and_different_environment_candidate_not_independently_verified',
          'motion_trace_and_T2T3_real_result': 'NOT_EXECUTED_no_new_artifacts_in_target',
          'independent_labels_normal_calibration_detection_net_benefit': 'NOT_EVALUABLE',
          'no_native_ros_bag_parameter_or_archive_code_execution': True}
output = Path(__file__).with_name('archive_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'selftest_recorded'}, ensure_ascii=False))
