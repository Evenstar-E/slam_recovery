"""Minimal exact reviewed-function controls; never run archived CLIs, selftests or host."""
import ast
import hashlib
import json
import math
from pathlib import Path
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = '24cf24cbea76d08011e3933b3b11c48dd7588b7b'


def blob(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', TARGET + ':' + path])


def functions(path, names):
    raw = blob(path)
    tree = ast.parse(raw)
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    namespace = {'np': np, 'math': math, 'Dict': dict, 'List': list, 'Optional': object,
                 'Any': object, 'Calibration': object}
    # Use actual target constant assignments, excluding path/output/import statements.
    constants = ('OLD_RUN_IDS', 'REQUIRED_TOP', 'REQUIRED_INPUTS', 'REQUIRED_EXPORTS',
                 'REQUIRED_DECL', 'VALID_STATE_ORDER', 'VALID_PERTURBATION')
    selected = [n for n in tree.body if isinstance(n, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id in constants for t in n.targets)]
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + selected + nodes,
                        type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), TARGET + ':' + path, 'exec'), namespace)
    return namespace, hashlib.sha256(raw).hexdigest()


prep, prep_sha = functions('docs/ali_h_v1_research/t2_input_check.py',
                            ['so3_log', 'e_i', 's_i', 'check_manifest', '_manifest'])
observer, observer_sha = functions('docs/ali_h_v1_research/ali_h_v1.py', ['classify_blocks'])
angle = .2
post = np.eye(4)
post[:3, :3] = [[math.cos(angle), -math.sin(angle), 0],
                [math.sin(angle), math.cos(angle), 0], [0, 0, 1]]
post[:3, 3] = [.1, 0, 0]
actual_e = prep['e_i'](np.eye(4), post)
# Closed-form inverse left Jacobian for this planar rotation/translation; independent of target helper.
expected_e = np.array([0., 0., angle, .1 * (angle / 2) / math.tan(angle / 2), -.1 * angle / 2, 0.])
assert np.allclose(actual_e, [0, 0, .2, .1, 0, 0]) and not np.allclose(actual_e, expected_e)
cov = np.diag([1., 1., 1., 1., 1e-6, 1.])
actual_s = prep['s_i'](actual_e, cov)['s']
expected_s = float(expected_e @ np.linalg.inv(cov) @ expected_e)
assert actual_s < 1 and expected_s > 20


def blk(bid, M='MISSING', T='MISSING', I='MISSING'):
    return {'block_id': bid, 'verdicts': {c: {'verdict': v, 'u': None}
                                        for c, v in zip(('M', 'T', 'I'), (M, T, I))}}


alarm_gap = observer['classify_blocks']([blk(10, M='ALARM'), blk(12, M='ALARM')], None)
normal_gap = observer['classify_blocks']([blk(10, T='NORMAL', I='NORMAL'), blk(12, T='NORMAL', I='NORMAL')], None)
explicit_missing = observer['classify_blocks']([blk(10, M='ALARM'), blk(11), blk(12, M='ALARM')], None)
assert alarm_gap[-1]['state'] == 'SUSPECT' and normal_gap[-1]['state'] == 'NORMAL_CONSISTENT'
assert explicit_missing[-1]['state'] == 'UNKNOWN'
assert [x['block_id'] for x in alarm_gap] == [10, 12]
left_manifest = prep['_manifest']()
ready = prep['check_manifest'](left_manifest)
assert left_manifest['declarations']['perturbation'] == 'left' and ready['status'] == 'READY'
pre = np.eye(4); pre[:3, :3] = [[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]]
post2 = pre.copy(); post2[:3, 3] = [1., 0., 0.]
right_e = prep['e_i'](pre, post2)
left_world_cov = np.diag([1., 1., 1., 100., 1., 1.])
wrong_score = prep['s_i'](right_e, left_world_cov)['s']
transport = np.zeros((6, 6)); transport[:3, :3] = pre[:3, :3].T; transport[3:, 3:] = pre[:3, :3].T
right_cov = transport @ left_world_cov @ transport.T
matched_score = prep['s_i'](right_e, right_cov)['s']
assert abs(wrong_score - 1.) < 1e-12 and abs(matched_score - .01) < 1e-12
result = {'target': TARGET, 'exit': 0,
          'command': 'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_24cf24c/run_checks.py',
          'loading': 'Only named reviewed target functions and literal constants compiled in memory; no archived module imports, CLIs, selftests, files or host execution',
          'source_sha256': {'t2_input_check.py': prep_sha, 'ali_h_v1.py': observer_sha},
          'se3_log_control': {'status': 'FAIL_REPRODUCED_NORMAL_NUMERIC', 'pose_rotation_rad': angle, 'translation_m': [.1, 0, 0],
                              'actual_e': actual_e.tolist(), 'contract_se3_log_e': expected_e.tolist(),
                              'actual_same_cov_score': actual_s, 'contract_same_cov_score': expected_s,
                              'scope': 'Synthetic physically matched right-tangent covariance, not actual host covariance or observed real misclassification'},
          'empty_block_control': {'status': 'FAIL_REPRODUCED_NORMAL_MISSING_WINDOW', 'M_alarm_blocks10_12': alarm_gap,
                                  'I_T_normal_blocks10_12': normal_gap, 'explicit_missing11_control': explicit_missing,
                                  'scope': 'Missing entire .5s block vs explicit missing, no real-trace classification claim'},
          'left_right_contract_control': {'status': 'FAIL_PREPARATION_READY_NOT_SUFFICIENT',
                                          'manifest_ready': ready, 'manifest_declarations': left_manifest['declarations'],
                                          'actual_right_residual': right_e.tolist(), 'left_cov_used_directly_score': wrong_score,
                                          'cov_transported_to_right_score': matched_score,
                                          'scope': 'Helpers allow inconsistent composition; true trace caller not delivered, not evidence actual runtime omitted transport'},
          'old_T0_all_UNKNOWN_result_unchanged': True,
          'no_native_ROS_bag_parameter_or_archived_CLI_execution': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
