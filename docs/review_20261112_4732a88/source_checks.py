"""Read bounded fixed Git evidence and reviewed manifest functions, never archive CLIs."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MAIN = '4732a881cfcb83dc5c59c9780bff955908364c00'
ARCHIVE = 'ffd4b13ce86d03556e389e42236e913d4701cf8d'
BASE = 'docs/review_20261112_four_host/'
HOST = BASE + 'host_change_trace_cov/'


def blob(ref, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])


raw = blob(MAIN, 'docs/ali_h_v1_research/t2_input_check.py')
tree = ast.parse(raw)
ns = {}
constants = {'OLD_RUN_IDS', 'REQUIRED_TOP', 'REQUIRED_INPUTS', 'REQUIRED_EXPORTS',
             'REQUIRED_DECL', 'VALID_STATE_ORDER', 'VALID_PERTURBATION'}
for node in tree.body:
    if isinstance(node, ast.Assign):
        for name in node.targets:
            if isinstance(name, ast.Name) and name.id in constants:
                ns[name.id] = ast.literal_eval(node.value)
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('check_manifest', '_manifest')]
assert len(functions) == 2
exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), MAIN + ':reviewed_manifest_functions', 'exec'), ns)
controls = []
for name in ('valid', 'detection_off', 'availability_disabled', 'support_null'):
    m = ns['_manifest'](covariance={'usable': False, 'reason': 'host_mixed_tangent_not_residual_covariance'})
    if name == 'detection_off':
        m['detection'] = 'off'
    elif name == 'availability_disabled':
        m['availability']['status_not_disabled'] = False
    elif name == 'support_null':
        m['availability']['support_non_null'] = False
    r = ns['check_manifest'](m)
    assert r['status'] == ('READY_UNIT_ONLY' if name == 'valid' else 'INCOMPLETE')
    controls.append({'name': name, 'result': r})
run = BASE + 'trace_fl_native_20261112T113855Z_464306/'
trace = blob(ARCHIVE, run + 'host_logs/trace_cov.txt')
lines = trace.decode().splitlines()
headers = [s for s in lines if s.startswith('#')]
rows = [s.split() for s in lines if s and not s.startswith('#')]
column_counts = Counter(len(r) for r in rows)
print('COLUMN_COUNTS', dict(column_counts))
# Use declared scalar field names; expand vec6 and 6x6 matrices separately.
scalar = headers[1].removeprefix('# ').split()[:14]
assert scalar == ['idx', 'rel_s', 'abs_ns', 'grp_idx', 'scan_first_ns', 'scan_last_ns', 'has_out', 'phase', 'eff', 'r_mean', 'r_med', 'r_abs_mean', 'r_chi2', 'r_chi2w']
pos = {name: scalar.index(name) for name in scalar}
phases = Counter(int(r[pos['phase']]) for r in rows)
has_out = Counter(int(r[pos['has_out']]) for r in rows)
replayed = [int(r[pos['idx']]) for r in rows if r[pos['phase']] == '1']
assert len(rows) == 1208 and phases[1] == 322 and has_out[1] == 1087
assert min(replayed) == 489 and max(replayed) == 810
integrity = []
for line in blob(ARCHIVE, run + 'SHA256SUMS').decode().splitlines():
    digest, name = line.split(maxsplit=1)
    name = name.removeprefix('./')
    actual = hashlib.sha256(blob(ARCHIVE, run + name)).hexdigest()
    integrity.append({'name': name, 'recorded': digest, 'actual': actual, 'matches': digest == actual})
common = blob(ARCHIVE, HOST + 'include_common_lib.h.v7u').decode()
assert 'a.rot_end = this->rot_end * Exp(state_add(0, 0), state_add(1, 0), state_add(2, 0));' in common
assert 'a.pos_end = this->pos_end + state_add.block<3, 1>(3, 0);' in common
assert 'a.block<3, 1>(3, 0) = this->pos_end - b.pos_end;' in common
probe = []
for i in range(1, 6):
    prefix = HOST + f'probe_v7s_{i}/'
    result = blob(ARCHIVE, prefix + 'result.txt').decode().strip()
    log = blob(ARCHIVE, prefix + 'host.log').decode(errors='replace')
    probe.append({'name': f'probe_v7s_{i}', 'saved_result': result,
                  'teardown_stack_smash': 'stack smashing detected' in log})
paths = subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '--name-only', ARCHIVE + ':' + HOST.rstrip('/')]).decode().splitlines()
payload = {'main_target': MAIN, 'archive_target': ARCHIVE,
           'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4732a88/source_checks.py',
           'manifest_source_sha256': hashlib.sha256(raw).hexdigest(), 'manifest_controls': controls,
           'buffered_run': {'run_id': 'fl_native_20261112T113855Z_464306', 'header_lines': len(headers),
                            'data_rows': len(rows), 'column_counts': dict(column_counts),
                            'incomplete_rows': [{'idx': int(r[pos['idx']]), 'columns': len(r),
                                                 'phase': int(r[pos['phase']])} for r in rows if len(r) != 92],
                            'columns': scalar, 'phase_counts': dict(phases),
                            'has_out_counts': dict(has_out), 'replay_idx_range': [min(replayed), max(replayed)],
                            'trace_sha256': hashlib.sha256(trace).hexdigest(), 'listed_SHA256SUMS': integrity},
           'host_mixed_state_convention': {'source': HOST + 'include_common_lib.h.v7u',
                                           'rotation': 'right body increment', 'translation': 'additive world increment',
                                           'raw_covariance_equals_pre_body_SE3_covariance': False,
                                           'residual_covariance_source': 'NOT_AVAILABLE_without_matched_conversion_and_source'},
           'startup_probes': probe, 'final_v7u_source_or_diff_names': [p for p in paths if 'v7u' in p],
           'full_final_LIVMapper_voxel_source_binding': 'NOT_AVAILABLE_in_this_archive; v7 sources only, no full v7u patch',
           'no_archive_code_ROS_host_bag_parameters': True}
output = Path(__file__).with_name('source_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(payload, ensure_ascii=False, indent=2))
