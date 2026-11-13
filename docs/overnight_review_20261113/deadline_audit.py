"""Deadline evidence inventory, fixed Git objects only; no archived code execution."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = 'dff0057231a687a7271fd5e8e836aa68ae674d9f'
BASELINE = '43fcd2c1e7943ee42cae6e744ef869db1a74de99'
HASHES = {}


def blob(path):
    raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', MAIN + ':' + path])
    HASHES[path] = hashlib.sha256(raw).hexdigest()
    return raw


populations = []
prefix = 'docs/ali_h_v1_research/'
for tag in ('A', 'B'):
    x = json.loads(blob(prefix + 't0_' + tag + '.json'))
    blocks = x['blocks']
    assert all(b['state'] == 'UNKNOWN' for b in blocks)
    assert all(b['block_id'] == blocks[0]['block_id'] + i for i, b in enumerate(blocks))
    populations.append({'run': x['run_id'], 'population': x['population'],
                        'old_status': x['old_status'], 'state_counts': x['state_counts_by_frame'],
                        'unknown_block_exposure_s': len(blocks) * .5,
                        'longest_unknown_block_run_s': len(blocks) * .5,
                        'no_data_blocks': sum(b['n_frames'] == 0 for b in blocks),
                        'scope': 'separate archived population, not full-message or independent fault denominator'})
for filename in ('t2_summary.json', 't2_v11_summary.json'):
    x = json.loads(blob(prefix + filename))
    state = x['states']
    assert all(b['state'] == 'UNKNOWN' for b in x['blocks'])
    populations.append({'run': x['_meta']['run'], 'population': x['join']['availability_rows'],
                        'I_numeric_rows': x['channels']['I_present'],
                        'I_zero_eff_rows': x['channels']['I_zero_eff_rows'],
                        'qualification_layers': x['_meta']['i_qualification_layers'],
                        'unknown_blocks': state['unknown_blocks'],
                        'unknown_block_exposure_s': state['span_s'],
                        'longest_unknown_block_run_s': state['span_s'],
                        'tail_rows': state['tail_rows'], 'tail_blocks': state['tail_blocks'],
                        'tail_block_members': state['tail_rows_by_block'],
                        'e2_basis': x['_meta']['e2_basis'],
                        'not_evaluable': state['not_evaluable'],
                        'scope': 'block exposure is not continuous recovery or labelled normal/fault time'})
blocker = blob(prefix + '重大阻塞记录.md').decode()
assert '（未收到；确认后在此追加，不覆盖本条目）' in blocker
assert '不是 BLOCKER_RESOLVED 或实验通过' in blocker
summary = blob('docs/OVERNIGHT_RESULTS_20261113_S1.md').decode()
collab = blob('docs/COLLABORATION_STATUS.md').decode()
assert '下一交付（明天第一件事）' in collab
assert 'FAST-LIO2 最小可运行恢复切片' in collab
changed_core = subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only',
                                       BASELINE, MAIN, '--', 'slam_recovery']).decode().splitlines()
assert changed_core == ['slam_recovery/ros/recovery_node.py',
                        'slam_recovery/tests/test_recovery_node.py',
                        'slam_recovery/tests/test_repair_sync.py']
prewindow = subprocess.check_output(['git', '-C', str(ROOT), 'show', '-s', '--format=%cI',
                                    'd86e57df09c076e531cb2e4edabdc70daac6b668']).decode().strip()
assert prewindow == '2026-11-12T17:30:55+08:00'
result = {'window_utc8': ['2026-11-12T17:53:00+08:00', '2026-11-13T08:53:00+08:00'],
          'fetch_utc8': '2026-11-13T08:53:23.6578822+08:00', 'main': MAIN,
          'prewindow_baseline': BASELINE, 'prewindow_v6_delivered_at': prewindow,
          'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/overnight_review_20261113/deadline_audit.py <new-output>',
          'scope': 'fixed saved data inventory and accepted evidence time binding; no full CLI/host/old controls rerun',
          'populations': populations, 'core_changed_paths': changed_core,
          'ALI_H_online_wiring': 'NOT_IMPLEMENTED/NOT_EXECUTED in available deliveries',
          'independent_normal_calibration_and_labels': 'BLOCKED/NOT_AVAILABLE',
          'new_recovery_slice': 'PLAN_ONLY: S1 selected FAST-LIO2, implementation/execution not delivered',
          'actual_user_GitHub_confirmation': 'NOT_INDEPENDENTLY_VERIFIED; Codex-origin proposal is not label data or new approval',
          'remote_process_state': 'UNKNOWN: repository receipts only, no live remote measurement',
          'whole_window_runtime_peak_cost': 'UNAVAILABLE', 'hashes': HASHES}
output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('deadline_evidence.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'hashes'}, ensure_ascii=False, indent=2))
