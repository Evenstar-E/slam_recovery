"""Bounded corrected SE3 function and saved T2 result checks; no archived CLI or host run."""
import ast
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

# Existing numerical dependency outside isolated mode; no installation or archived imports.
sys.path.append('C:/Users/R26534/AppData/Roaming/Python/Python315/site-packages')
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'e351a0bdb5bbab4e543da31ca1092797f350dfce'
BASE = '560230c5012a7b7a0fe845c71a4549d0a3f52637'
ARCHIVE = '290aae8441fedc24dfbf316b8150880b63fae0b1'
PREFIX = 'docs/ali_h_v1_research/'
RUN = 'docs/review_20261112_four_host/trace_fl_native_20261112T115734Z_483777/'


def blob(ref, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])


def functions(ref, path, names, extra=None):
    tree = ast.parse(blob(ref, path))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    ns = {'np': np, 'math': math, **(extra or {})}
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(module, ref + ':reviewed_functions_only', 'exec'), ns)
    return ns


new = functions(TARGET, PREFIX + 't2_run.py', ('so3_exp', 'so3_left_jacobian_inv', 'exact_e'))
old = functions(BASE, PREFIX + 't2_run.py', ('so3_exp', 'exact_e'))
canonical = functions(TARGET, PREFIX + 't2_input_check.py', ('so3_log', '_hat', 'so3_left_jacobian_inv', 'e_i'), {'VALID_STATE_ORDER': ('rot_trans', 'trans_rot')})
angle, translation = .2, .1
Rpost = np.array([[math.cos(angle), -math.sin(angle), 0], [math.sin(angle), math.cos(angle), 0], [0, 0, 1]])
vec = np.array([0, 0, -angle, -translation, 0, 0])
pre, post = np.eye(4), np.eye(4)
post[:3, :3] = Rpost
post[0, 3] = translation
actual = new['exact_e'](vec, Rpost)
previous = old['exact_e'](vec, Rpost)
expected = np.array([0, 0, angle, translation * (angle / 2) / math.tan(angle / 2), -translation * angle / 2, 0])
assert np.allclose(actual, expected) and np.allclose(actual, canonical['e_i'](pre, post))
assert not np.allclose(previous, expected)
summary_raw = blob(TARGET, PREFIX + 't2_summary.json')
summary = json.loads(summary_raw)
previous_summary = json.loads(blob(BASE, PREFIX + 't2_summary.json'))
rows = [json.loads(line) for line in blob(TARGET, PREFIX + 't2_join.jsonl').splitlines() if line.strip()]
previous_rows = [json.loads(line) for line in blob(BASE, PREFIX + 't2_join.jsonl').splitlines() if line.strip()]
assert len(rows) == len(previous_rows) == 531
# Mapping, original diagnostics and full population were not changed by this numerical correction.
for a, b in zip(rows, previous_rows):
    assert {k: v for k, v in a.items() if k != 'i'} == {k: v for k, v in b.items() if k != 'i'}
assert summary['states'] == previous_summary['states']
assert summary['states']['unknown_blocks'] == summary['states']['blocks'] == 120
assert summary['states']['tail_rows'] == 47
assert Counter(row['shadow_state'] for row in rows) == Counter({'UNKNOWN': 531})
assert summary['_meta']['vec6_status'].startswith('NOT_VERIFIED')
assert summary['_meta']['join_status'] == 'HEURISTIC_UNPROVEN'
assert summary['_meta']['covariance_status'].startswith('NOT_AVAILABLE')
binding = {}
for key, path in [('trace_sha256', 'host_logs/trace_cov.txt'), ('receipt_sha256', 'receipt.json'), ('summary_sha256', 'run_summary.json')]:
    digest = hashlib.sha256(blob(ARCHIVE, RUN + path)).hexdigest()
    assert digest == summary['_meta'][key]
    binding[key] = digest
av = gzip.decompress(blob(ARCHIVE, RUN + 'availability_frames.jsonl.gz'))
assert hashlib.sha256(av).hexdigest() == summary['_meta']['availability_sha256']
binding['availability_uncompressed_sha256'] = hashlib.sha256(av).hexdigest()
present = [row['i'] for row in rows if row['i'].get('present')]
assert len(present) == summary['channels']['I_present'] == 504
norms, scores = np.array([i['e_norm'] for i in present]), np.array([i['s_i'] for i in present])
assert np.isclose(np.median(norms), summary['channels']['I_e_norm']['median'])
assert np.isclose(np.median(scores), summary['channels']['I_s']['median'])
assert np.isclose(np.max(norms), summary['channels']['I_e_norm']['max'])
assert np.isclose(np.max(scores), summary['channels']['I_s']['max'])
assert np.isclose(np.percentile(norms * norms, 90), summary['channels']['I_unit_energy']['p90'])
result = {
    'target': TARGET, 'base': BASE, 'archive': ARCHIVE,
    'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_e351a0b/run_checks.py',
    'isolated_import_default_numpy': 'UNAVAILABLE: ModuleNotFoundError; used explicitly named existing site-packages, no installation',
    'numerical_dependency': {'version': np.__version__, 'path': np.__file__},
    'corrected_SE3_control': {'status': 'PASS_LOCAL', 'previous': previous.tolist(), 'actual': actual.tolist(),
                            'expected': expected.tolist(), 'canonical_equal': True,
                            'scope': 'same ordinary matched synthetic pre/post; does not qualify real host vec6/pose join'},
    'T2_source_sha256': hashlib.sha256(blob(TARGET, PREFIX + 't2_run.py')).hexdigest(),
    'summary_sha256': hashlib.sha256(summary_raw).hexdigest(), 'input_binding': binding,
    'saved_rows': len(rows), 'non_I_fields_unchanged': True, 'states_unchanged': True,
    'saved_I_present_diagnostic_rows': len(present), 'saved_I_e_norm_median': float(np.median(norms)),
    'saved_I_s_diagnostic_median': float(np.median(scores)), 'saved_I_e_norm_max': float(np.max(norms)),
    'saved_I_s_diagnostic_max': float(np.max(scores)),
    'saved_aggregates_recomputed_from_join_rows': True, 'saved_tail_rows': summary['states']['tail_rows'],
    'saved_unknown_blocks': summary['states']['unknown_blocks'], 'saved_meta': summary['_meta'],
    'new_native_run': 'NONE_IN_DELTA', 'real_I_qualification': 'NOT_VERIFIED',
    'ALI_error_rates_and_benefit': 'NOT_EVALUABLE',
    'full_T2_CLI_208_tests_or_native_execution': False,
    'new_cost': 'DEVELOPER_REPORTED: no independent local full T2 timing/RSS measurement',
}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
