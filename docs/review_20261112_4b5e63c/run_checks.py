"""Fixed Git v8 archive and reviewed checkpoint metadata controls; no native execution."""
import ast
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
MAIN = '4b5e63cbdba6b8e936a5d3b13fa6770c2d212424'
TRACE = '553e2b8b74f11ab675b3f0afc5d5565498268c99'
NEGATIVE = '8ca557555926b0aa24c31082e4bc78a9dbdac3b6'
PREFIX = 'docs/review_20261112_four_host/'


def blob(ref, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])


source = blob(MAIN, 'slam_recovery/ros/recovery_node.py')
cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'NativeClosedLoop')
names = ('_checkpoint_boundary', '_record_checkpoint_check', '_finalize_checkpoint_checks')
methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert len(methods) == 3
ns = {}
module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + methods, type_ignores=[])
exec(compile(ast.fix_missing_locations(module), MAIN + ':reviewed_checkpoint_metadata', 'exec'), ns)
Control = type('Control', (), {name: ns[name] for name in names})
controls = []
for name, ack, ok in [('before', 'OK restore valid=1 stamp_ns=975 frame=1', True),
                      ('late', 'OK restore valid=1 stamp_ns=990 frame=2', True),
                      ('failed_no_checkpoint', 'FAIL restore valid=0 stamp_ns=-1000000000 frame=0', False)]:
    ep = SimpleNamespace(trigger_ts_ns=1000, quarantine_start_ns=980, meta={})
    loop = Control(); loop.scripted_trigger_stamps_ns = []; loop.confirmation_margin_ns = 20; loop.episodes = [ep]
    action = {'command': 'restore'}
    loop._record_checkpoint_check(ep, action)
    assert ep.meta['checkpoint_check']['status'] == 'PENDING_ACK'
    action.update(ack=ack, ok=ok)
    loop._finalize_checkpoint_checks()
    entry = dict(ep.meta['checkpoint_check'])
    if name == 'before':
        assert entry['actual_stamp_ns'] == 975 and entry['status'] == 'AT_OR_BEFORE_BOUNDARY'
    elif name == 'late':
        assert entry['status'] == 'LATE_AFTER_BOUNDARY'
    else:
        assert entry['rollback_support'] == 'WITHIN_DECLARED_BOUNDARY'
    controls.append({'name': name, 'action': action, 'entry': entry,
                     'verdict': 'FAIL_REPRODUCED_invalid_FAIL_ACK_marked_supported' if not ok else 'PASS_LOCAL'})
p = PREFIX + 'trace_online_fl_native_20261112T124217Z_521833/'
receipt_raw, summary_raw = blob(TRACE, p + 'receipt.json'), blob(TRACE, p + 'run_summary.json')
receipt, summary = json.loads(receipt_raw), json.loads(summary_raw)
trace_raw = blob(TRACE, p + 'host_logs/trace_cov.txt')
lines = trace_raw.decode().splitlines()
header = next(l.removeprefix('# ').split() for l in lines if l.startswith('# idx '))
col = {name: i for i, name in enumerate(header[:15])}
assert header[:10] == ['idx', 'rel_s', 'abs_ns', 'grp_idx', 'scan_first_ns', 'scan_last_ns', 'n_scans', 'has_out', 'phase', 'eff']
rows = [l.split() for l in lines if l and not l.startswith('#')]
assert len(rows) == 736 and all(len(r) == 93 for r in rows)
av_raw = gzip.decompress(blob(TRACE, p + 'availability_frames.jsonl.gz'))
av = [json.loads(l) for l in av_raw.splitlines() if l.strip()]
assert len(av) == 444
matches = []
for a in av:
    stamp = a['scan_stamp_ns']
    ids = [int(r[col['grp_idx']]) for r in rows if int(r[col['scan_first_ns']]) - 512 <= stamp <= int(r[col['scan_last_ns']]) + 512]
    matches.append({'kf_id': a['kf_id'], 'scan_stamp_ns': stamp, 'groups': ids})
hist = Counter(len(m['groups']) for m in matches)
assert hist == Counter({1: 217, 2: 227})
report = json.loads(blob(MAIN, 'docs/ali_h_v1_research/t2_join_upgrade.json'))
assert hashlib.sha256(trace_raw).hexdigest() == report['_meta']['trace_sha256']
assert hashlib.sha256(av_raw).hexdigest() == report['_meta']['availability_sha256']
assert hashlib.sha256(receipt_raw).hexdigest() == report['_meta']['receipt_sha256']
assert hashlib.sha256(summary_raw).hexdigest() == report['_meta']['summary_sha256']
assert all(int(r[col['n_scans']]) == 1 and r[col['scan_first_ns']] == r[col['scan_last_ns']] for r in rows)
q = PREFIX + 'trace_online_fl_native_20261112T125406Z_533623/'
r2_raw, s2_raw = blob(NEGATIVE, q + 'receipt.json'), blob(NEGATIVE, q + 'run_summary.json')
r2, s2 = json.loads(r2_raw), json.loads(s2_raw)
episodes = []
for ep in s2['quarantine']['episode_detail']:
    check = ep.get('checkpoint_check') or {}
    action = ep.get('native_checkpoint') or {}
    episodes.append({'index': ep['index'], 'qstart': ep['quarantine_start_ns'], 'checkpoint_check': check,
                     'native_action': action, 'delta_ns': check['actual_stamp_ns'] - ep['quarantine_start_ns'] if check.get('actual_stamp_ns') is not None else None})
assert [ep['checkpoint_check']['status'] for ep in episodes] == ['LATE_AFTER_BOUNDARY', 'AT_OR_BEFORE_BOUNDARY', 'LATE_AFTER_BOUNDARY', 'LATE_AFTER_BOUNDARY']
result = {'main_target': MAIN, 'trace_archive': TRACE, 'negative_archive': NEGATIVE,
          'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4b5e63c/run_checks.py',
          'checkpoint_source_sha256': hashlib.sha256(source).hexdigest(), 'metadata_controls': controls,
          'v8': {'run_id': summary['run_id'], 'library': receipt['inputs']['runtime_library_sha256'],
                 'trace_sha256': hashlib.sha256(trace_raw).hexdigest(), 'saved_result_input_hashes_match': True,
                 'rows': len(rows), 'columns': 93, 'phase': dict(Counter(r[col['phase']] for r in rows)),
                 'has_out': dict(Counter(r[col['has_out']] for r in rows)), 'n_scans_all_one_and_first_equals_last': True,
                 'availability_rows': len(av), 'status': dict(Counter(a['status'] for a in av)),
                 'contains_with_512ns_match_counts': dict(hist), 'matches': matches,
                 'max_rel_s': max(float(r[col['rel_s']]) for r in rows),
                 'unique_update_post_pose_and_full_point_membership': 'NOT_VERIFIED; source header evidence improved but carried pcl_proc_next and two updates require explicit relation',
                 'gate': summary.get('gate'), 'runtime': summary.get('runtime')},
          'negative_run': {'run_id': s2['run_id'], 'source_hash_matches_de4360b': hashlib.sha256(blob('de4360b', 'slam_recovery/ros/recovery_node.py')).hexdigest() == r2['inputs']['recovery_node_source'],
                           'summary_sha256': hashlib.sha256(s2_raw).hexdigest(), 'gate': s2.get('gate'), 'paired': s2['pairing']['paired'],
                           'episodes': episodes, 'final_state': s2['final_state']},
          'full_tests_or_archived_CLI_executed': False, 'no_ROS_host_parameters_or_archived_CLI_execution': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k not in ('v8', 'negative_run')}, ensure_ascii=False, indent=2))
print('V8_SUMMARY', json.dumps({k: v for k, v in result['v8'].items() if k != 'matches'}, ensure_ascii=False))
print('NEGATIVE_DELTAS', [ep['delta_ns'] for ep in episodes])
