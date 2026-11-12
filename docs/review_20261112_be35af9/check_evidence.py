"""Fixed-target old-trace qualification readback, not execution of ALI-H or host code."""
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'be35af983639cf97354c13b09fad79845754b491'
BASE = 'docs/review_20261112_availability/'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def blob(path):
    return git('show', TARGET + ':' + path)


runs = []
for name, suffix, expected in [('A', '', 402), ('B', 'predicted_pose/', 544)]:
    prefix = BASE + suffix
    raw = blob(prefix + 'availability_frames.jsonl.gz')
    rows = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    receipt = json.loads(blob(prefix + 'receipt.json'))
    assert len(rows) == expected and all(r['run_id'] == receipt['run_id'] for r in rows)
    status = Counter(r['status'] for r in rows)
    reasons = Counter(r['support']['reason'] for r in rows if r['status'] == 'UNAVAILABLE')
    derived_reasons = Counter()
    for row in rows:
        if row['status'] != 'UNAVAILABLE':
            continue
        support = row['support']
        if support.get('reference_points', 0) == 0:
            derived_reasons['empty_reference'] += 1
        elif support.get('supported_fraction', 0.0) < support.get('threshold_fraction', .6):
            derived_reasons['insufficient_support'] += 1
        else:
            derived_reasons['other_missing_evidence'] += 1
    unavailable_sources = Counter()
    all_sources = Counter()
    imu_keys = set()
    missing_nis = 0
    for row in rows:
        nis = row['nis']
        source = nis.get('selected_reference_source', 'none')
        finite_fresh = nis.get('source') == 'computed' and nis.get('raw_kind') == 'finite'
        value = nis.get('raw_value')
        finite_fresh = finite_fresh and value is not None and math.isfinite(float(value))
        channel = ('M_raw' if source == 'node_map' else 'T_raw' if source == 'prev_scan' else 'NONE') if finite_fresh else 'NONE'
        all_sources[channel] += 1
        if row['status'] == 'UNAVAILABLE':
            unavailable_sources[channel] += 1
        if not row.get('nis_present'):
            missing_nis += 1
        # Inspect only declared row and observation keys, not incidental free-text substring matches.
        for scope, values in [('row', row), ('nis', nis), ('support', row['support'])]:
            imu_keys.update(scope + '.' + key for key in values if any(token in key.lower() for token in ('imu', 'preupdate', 'innovation', 'bias_g', 'bias_a')))
    assert not imu_keys
    expected_counts = {'A': {'M_raw': 28, 'T_raw': 278, 'NONE': 1},
                       'B': {'M_raw': 137, 'T_raw': 274, 'NONE': 1}}
    assert dict(unavailable_sources) == expected_counts[name]
    runs.append({'run': name, 'run_id': receipt['run_id'], 'frames': len(rows),
                 'input_trace_sha256': hashlib.sha256(raw).hexdigest(), 'receipt_inputs': receipt['inputs'],
                 'status_counts': dict(status), 'unavailable_support_reason_counts': dict(reasons),
                 'unavailable_support_reasons_from_numeric_fields': dict(derived_reasons),
                 'nis_missing_all_frames': missing_nis,
                 'unavailable_fresh_raw_channel_counts': dict(unavailable_sources),
                 'all_fresh_raw_channel_counts': dict(all_sources),
                 'I_observation_keys': sorted(imu_keys), 'I_in_old_trace': 'NOT_AVAILABLE',
                 'M_or_T_raw_is_qualified_health_evidence': False,
                 'NORMAL_design_ceiling_without_real_I': 0,
                 'calibration_and_label_validity': 'NOT_EVALUABLE_no_new_independent_calibration_or_labels_checked',
                 'reported_all_UNKNOWN_shadow': 'DEVELOPER_REPORTED_not_independently_read_no_research_artifacts_in_target'})
research_paths = git('ls-tree', '-r', '--name-only', TARGET, '--', 'docs/ali_h_v1_research').decode().splitlines()
assert not research_paths
result = {'target': TARGET, 'exit': 0,
          'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_be35af9/check_evidence.py',
          'scope': 'Existing availability raw-source qualification only; no ALI-H implementation, selftests, host/bag or archived script execution',
          'runs': runs, 'research_artifacts_in_main': research_paths,
          'remote_exp_branch': 'NOT_LISTED_ls_remote_heads_exp_ali_h_v1_exit0_empty',
          'reported_research_commit_8c5b082': 'NOT_AVAILABLE_in_local_fetched_objects',
          'reported_T1_6_tests': 'NOT_EXECUTED_NOT_VERIFIED',
          'reported_existing_host_pre_post_logs': 'DEVELOPER_REPORTED_NOT_READ_remote_files_not_in_target',
          'proposed_motion_export': {'real_export': 'NOT_EXECUTED_in_target',
                                    'measurement_S': 'H_Pminus_Htranspose_plus_R_lives_in_measurement_space',
                                    'pose_eI': 'SE3_tangent_6D_covariance_must_live_in_same_tangent_not_direct_measurement_S',
                                    'pre_post_covariance': 'Pminus_and_Pplus_share_history_not_independent; not_naive_sum_for_eI',
                                    'missing_covariance': 'Preserve_unit_residual_and_UNKNOWN_qualification_no_identity_or_fake_probability'},
          'no_new_main_algorithm_changes': not bool(git('diff', '--name-only', 'd86e57d', TARGET, '--', 'slam_recovery').strip()),
          'new_15h_task_merged_in_target': subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', '2c838c7', TARGET], check=False).returncode == 0,
          'no_native_or_parameter_execution': True}
output = Path(__file__).with_name('evidence_checks.json')
if output.exists():
    previous = json.loads(output.read_text(encoding='utf-8'))
    assert previous['target'] == TARGET and previous['command'] == result['command']
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'runs'}, ensure_ascii=False))
print(json.dumps([{k: r[k] for k in ('run', 'frames', 'status_counts', 'unavailable_support_reason_counts', 'unavailable_fresh_raw_channel_counts', 'NORMAL_design_ceiling_without_real_I')} for r in runs], ensure_ascii=False))
