"""Exact-target checkpoint metadata controls and bounded online archive reader."""
import ast
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
MAIN = 'd7cbbf5132f486b17f686709f6abda977c328941'
ARCHIVE = 'e991eaf6b390ec77e74753dbd5b926fb91589d8b'
PREFIX = 'docs/review_20261112_four_host/trace_online_fl_native_20261112T121127Z_497953/'


def blob(ref, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])


source = blob(MAIN, 'slam_recovery/ros/recovery_node.py')
tree = ast.parse(source)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeClosedLoop')
methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('_checkpoint_expectation', '_record_checkpoint_check')]
assert len(methods) == 2
ns = {}
mod = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + methods, type_ignores=[])
exec(compile(ast.fix_missing_locations(mod), MAIN + ':reviewed_checkpoint_methods', 'exec'), ns)
Control = type('Control', (), {m.name: ns[m.name] for m in methods})
loop = Control()
loop.scripted_trigger_stamps_ns = []
loop.confirmation_margin_ns = 20
synthetic_ep = SimpleNamespace(trigger_ts_ns=1_000, meta={})
action = {'command': 'restore', 'wall': 123.0}
loop._record_checkpoint_check(synthetic_ep, action)
initial = dict(synthetic_ep.meta['checkpoint_check'])
action.update(ok=True, ack='OK restore valid=1 stamp_ns=975 frame=1')
post_ack = dict(synthetic_ep.meta['checkpoint_check'])
assert initial['actual_stamp_ns'] is None and post_ack['actual_stamp_ns'] is None
loop.scripted_trigger_stamps_ns = [1_000]
loop._record_checkpoint_check(synthetic_ep, action)
scripted = dict(synthetic_ep.meta['checkpoint_check'])
assert scripted['status'] == 'MISMATCH' and scripted['expected_stamp_ns'] == 980
# A valid earlier processed-group snapshot is not the apply request's exact stamp.

receipt_raw = blob(ARCHIVE, PREFIX + 'receipt.json')
summary_raw = blob(ARCHIVE, PREFIX + 'run_summary.json')
receipt, summary = json.loads(receipt_raw), json.loads(summary_raw)
assert receipt['launch']['scripted_triggers_ns'] == receipt['launch']['scripted_triggers_s'] == ''
assert receipt['launch']['detection'] == 'on'
assert hashlib.sha256(source).hexdigest() == receipt['inputs']['recovery_node_source']
integrity = []
for line in blob(ARCHIVE, PREFIX + 'SHA256SUMS').decode().splitlines():
    expected, path = line.split(maxsplit=1)
    path = path.removeprefix('./')
    actual = hashlib.sha256(blob(ARCHIVE, PREFIX + path)).hexdigest()
    integrity.append({'name': path, 'expected': expected, 'actual': actual, 'matches': actual == expected})
avail_bytes = blob(ARCHIVE, PREFIX + 'availability_frames.jsonl.gz')
avail = [json.loads(line) for line in gzip.decompress(avail_bytes).splitlines() if line.strip()]
trace_raw = blob(ARCHIVE, PREFIX + 'host_logs/trace_cov.txt')
trace_lines = trace_raw.decode().splitlines()
headers = [s for s in trace_lines if s.startswith('#')]
fields = headers[1].removeprefix('# ').split()[:14]
assert fields[:9] == ['idx', 'rel_s', 'abs_ns', 'grp_idx', 'scan_first_ns', 'scan_last_ns', 'has_out', 'phase', 'eff']
idx = {k: fields.index(k) for k in fields}
rows = [s.split() for s in trace_lines if s and not s.startswith('#')]
episodes = []
for ep in summary['quarantine']['episode_detail']:
    cp = ep.get('native_checkpoint') or {}
    parsed = {k: int(v) for k, v in re.findall(r'\b(stamp_ns|frame|repair_applied|repair_dropped|replay_within_end|replay_suffix)=(-?\d+)', cp.get('ack', ''))}
    start = ep['quarantine_start_ns']
    repair = ep.get('repair_publish') or {}
    episodes.append({'index': ep['index'], 'trigger_ts_ns': ep['trigger_ts_ns'], 'quarantine_start_ns': start,
                     'candidate_frames': ep.get('candidate_frames'), 'committable_evidence_frames': ep.get('paired_evidence', {}).get('num_paired_frames'),
                     'checkpoint_check_recorded': ep.get('checkpoint_check'), 'native_action': cp,
                     'actual_ack': parsed, 'cp_minus_quarantine_start_ns': parsed['stamp_ns'] - start if parsed.get('stamp_ns', -1) > 0 else None,
                     'restore_disposition': ep.get('restore_disposition'), 'error': ep.get('error'),
                     'repair_published': repair.get('published'), 'repair_bias_z_m': repair.get('bias_z_m'),
                     'repair_scan_stamp_range': [min(repair['frames']), max(repair['frames'])] if repair.get('frames') else None,
                     'native_writeback_skipped': ep.get('native_writeback_skipped')})
assert len(episodes) == 5
assert all(ep['checkpoint_check_recorded']['actual_stamp_ns'] is None for ep in episodes)
assert episodes[0]['cp_minus_quarantine_start_ns'] == 3900276288
assert episodes[1]['cp_minus_quarantine_start_ns'] == 3833658888
assert episodes[3]['actual_ack']['repair_applied'] == 42
assert episodes[3]['actual_ack']['repair_dropped'] == 0
assert episodes[3]['actual_ack']['replay_within_end'] == 759
assert episodes[3]['actual_ack']['replay_suffix'] == 615
assert episodes[4]['error'] is not None
pre = blob(ARCHIVE, PREFIX + 'host_logs/mat_pre.txt')
out = blob(ARCHIVE, PREFIX + 'host_logs/mat_out.txt')
result = {'main_target': MAIN, 'archive_target': ARCHIVE,
          'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_d7cbbf5/run_checks.py',
          'source_sha256': hashlib.sha256(source).hexdigest(), 'source_matches_receipt': True,
          'normal_async_metadata_control': {'initial': initial, 'after_event_ack_mutated': post_ack, 'verdict': 'FAIL_REPRODUCED_stale_scalar_copy'},
          'earlier_scripted_checkpoint_control': {'ack_stamp_ns': 975, 'declared_apply_stamp_ns': 980, 'record': scripted,
                                                'verdict': 'FAIL_METADATA_false_MISMATCH_for_legal_earlier_processed_group'},
          'archive_integrity': integrity, 'launch': receipt['launch'], 'library': receipt['inputs']['runtime_library_sha256'],
          'summary_pairing': summary['pairing'], 'gate_summary': summary.get('gate'), 'final_state': summary['final_state'],
          'quarantine_open_at_exit': summary['quarantine_open_at_exit'], 'lifecycle_unresolved': summary['lifecycle'].get('unresolved_segments'),
          'runtime': summary.get('runtime'), 'episodes': episodes,
          'availability': {'rows': len(avail), 'status': dict(Counter(a['status'] for a in avail)),
                           'computed': sum(a['nis'].get('computed') is True for a in avail),
                           'sha256': hashlib.sha256(avail_bytes).hexdigest()},
          'trace': {'headers': len(headers), 'physical_rows': len(rows), 'widths': dict(Counter(len(r) for r in rows)),
                    'scan_first_negative': sum(int(r[idx['scan_first_ns']]) < 0 for r in rows),
                    'phase': dict(Counter(r[idx['phase']] for r in rows)), 'has_out': dict(Counter(r[idx['has_out']] for r in rows)),
                    'sha256': hashlib.sha256(trace_raw).hexdigest()},
          'mat_pre_out': {'pre_rows': len(pre.splitlines()), 'out_rows': len(out.splitlines()),
                          'pre_sha256': hashlib.sha256(pre).hexdigest(), 'out_sha256': hashlib.sha256(out).hexdigest(),
                          'physical_update_pairing': 'NOT_VERIFIED_no_group_phase_identity'},
          'T2_result_files_main': subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-r', '--name-only', MAIN, '--', 'docs/ali_h_v1_research']).decode().splitlines(),
          'no_host_ROS_parameters_or_archived_CLI_execution': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ('episodes', 'T2_result_files_main', 'gate_summary', 'launch')}, ensure_ascii=False, indent=2))
