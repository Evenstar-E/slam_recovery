"""Bounded T2 saved evidence and reviewed exact-e / closed-segment controls."""
import ast
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = '1e2529819d00a98f2083a261fd12431d7cedd4c6'
ARCHIVE = '290aae8441fedc24dfbf316b8150880b63fae0b1'
PREFIX = 'docs/ali_h_v1_research/'
RUN = 'docs/review_20261112_four_host/trace_fl_native_20261112T115734Z_483777/'


def blob(ref, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])


raw = blob(TARGET, PREFIX + 't2_run.py')
tree = ast.parse(raw)
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('so3_exp', 'exact_e')]
assert len(functions) == 2
ns = {'np': np, 'math': math}
exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), TARGET + ':reviewed_exact_e', 'exec'), ns)
angle, t = .2, .1
Rpost = np.array([[math.cos(angle), -math.sin(angle), 0], [math.sin(angle), math.cos(angle), 0], [0, 0, 1]])
vec = np.array([0, 0, -angle, -t, 0, 0])
actual = ns['exact_e'](vec, Rpost)
expected = np.array([0, 0, angle, t * (angle / 2) / math.tan(angle / 2), -t * angle / 2, 0])
assert np.allclose(actual, [0, 0, angle, t, 0, 0]) and not np.allclose(actual, expected)
summary_raw = blob(TARGET, PREFIX + 't2_summary.json')
summary = json.loads(summary_raw)
joined = [json.loads(line) for line in blob(TARGET, PREFIX + 't2_join.jsonl').splitlines() if line.strip()]
assert len(joined) == 531
binding = {}
for key, path in [('trace_sha256', 'host_logs/trace_cov.txt'), ('receipt_sha256', 'receipt.json'), ('summary_sha256', 'run_summary.json')]:
    digest = hashlib.sha256(blob(ARCHIVE, RUN + path)).hexdigest()
    assert digest == summary['_meta'][key]
    binding[key] = digest
av = gzip.decompress(blob(ARCHIVE, RUN + 'availability_frames.jsonl.gz'))
assert hashlib.sha256(av).hexdigest() == summary['_meta']['availability_sha256']
binding['availability_uncompressed_sha256'] = hashlib.sha256(av).hexdigest()
assert summary['_meta']['join_status'] == 'HEURISTIC_UNPROVEN'
assert summary['_meta']['covariance_status'].startswith('NOT_AVAILABLE')
assert summary['states']['unknown_blocks'] == summary['states']['blocks'] == 120
assert summary['states']['unknown_normal']['duration_s'] + summary['states']['unknown_post_e2']['duration_s'] == 60
assert summary['states']['tail_rows'] == 47
source = blob(TARGET, 'slam_recovery/ros/recovery_node.py')
cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'NativeClosedLoop')
decide = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'decide')
# Execute only reviewed entry guard, stopping before the unchanged decision body.
wrapper = ast.parse('def control(self):\n    pass\n').body[0]
wrapper.body = decide.body[:4]
assert isinstance(wrapper.body[-1], ast.If) and isinstance(wrapper.body[-1].test, ast.Compare)
wrapper.body.append(ast.Return(value=ast.Constant(value='CONTINUE_EXISTING_DECISION')))
module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
control_ns = {}
exec(compile(module, TARGET + ':reviewed_decision_entry_guard', 'exec'), control_ns)
checks = []
for active_id in (None, 'new-segment', 'same-segment'):
    ep = SimpleNamespace(decided=False, segment_id='same-segment', meta={})
    loop = SimpleNamespace(_open=ep, node=SimpleNamespace(tx_mgr=SimpleNamespace(active_quarantine=None if active_id is None else SimpleNamespace(segment_id=active_id))))
    outcome = control_ns['control'](loop)
    if active_id == 'same-segment':
        assert outcome == 'CONTINUE_EXISTING_DECISION'
    else:
        assert outcome is None and ep.meta['decision_skipped'] == 'SEGMENT_CLOSED_BEFORE_DECISION'
    checks.append({'active_id': active_id, 'outcome': outcome, 'decided': ep.decided, 'meta': ep.meta})
result = {'target': TARGET, 'archive_target': ARCHIVE,
          'command': 'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_1e25298/run_checks.py',
          'T2_source_sha256': hashlib.sha256(raw).hexdigest(),
          'exact_e_control': {'status': 'FAIL_REPRODUCED_missing_SE3_translation_Jacobian',
                              'host_mixed_vec_assumed_exact_pre_minus_post': vec.tolist(),
                              'actual': actual.tolist(), 'required_SE3_Log': expected.tolist(),
                              'scope': 'Synthetic matched pre/post control, not actual trace misclassification'},
          'T2_saved_result_binding': binding, 'saved_join_rows': len(joined),
          'saved_states': summary['states'], 'saved_channel_counts': {k: summary['channels'][k] for k in ('M_present_all', 'T_present_all', 'I_present', 'I_missing', 'I_s_status')},
          'saved_meta': summary['_meta'], 'closed_segment_guard_controls': checks,
          'raw_T2_CLI_or_206_tests_executed': False, 'new_native_run_after_guard_change': 'NOT_EXECUTED_in_delivered_e991eaf',
          'no_ROS_host_parameters_or_archived_CLI_execution': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
