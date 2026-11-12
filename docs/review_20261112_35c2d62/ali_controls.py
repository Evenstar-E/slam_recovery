"""Independent read-only controls: git blobs, reviewed functions only, no archive CLI/selftest."""
import ast
from collections import Counter
import copy
import gzip
import hashlib
import json
import math
import statistics
import subprocess
import sys

# Existing installed NumPy; -I still excludes cwd, script directory and PYTHONPATH.
sys.path.append('C:/Users/R26534/AppData/Roaming/Python/Python315/site-packages')
import numpy as np

ROOT = 'D:/REPAIR/slam_recovery_upstream'
TARGET = '35c2d62b6412d5b651ef6d211a5c8d16a77cc5f1'
BASE = 'e0d403b'
PREFIX = 'docs/ali_h_v1_research/'

def blob(ref, path):
    return subprocess.check_output(['git', '-C', ROOT, 'show', ref + ':' + path])

def reviewed(ref, path, names, constants, calibration=False):
    raw = blob(ref, path)
    tree = ast.parse(raw)
    ns = {'np': np, 'math': math, 'statistics': statistics}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for name in node.targets:
                if isinstance(name, ast.Name) and name.id in constants:
                    ns[name.id] = ast.literal_eval(node.value)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if calibration:
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Calibration')
        functions += [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('__init__', 'lookup')]
    assert set(names).issubset({n.name for n in functions})
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + functions, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), ref + ':' + path, 'exec'), ns)
    if calibration:
        ns['Calibration'] = type('Calibration', (), {name: ns.pop(name) for name in ('__init__', 'lookup')})
    return ns, hashlib.sha256(raw).hexdigest()

prep_names = ['check_manifest', 'so3_log', 'e_i', 's_i', 'unit_only', '_manifest']
prep_constants = ['OLD_RUN_IDS', 'REQUIRED_TOP', 'REQUIRED_INPUTS', 'REQUIRED_EXPORTS', 'REQUIRED_DECL', 'VALID_STATE_ORDER', 'VALID_PERTURBATION']
obs_names = ['_finite', 'map_support', '_channel_m', '_channel_t', '_channel_i', 'frame_record', 'old_reason', 'channel_verdict', 'classify_blocks', 'block_summary']
obs_constants = ['BLOCK_NS', 'ALARM_U', 'NORMAL_U', 'MIN_BLOCKS']
new, sha_p = reviewed(TARGET, PREFIX + 't2_input_check.py', prep_names + ['_hat', 'so3_left_jacobian_inv'], prep_constants)
old, _ = reviewed(BASE, PREFIX + 't2_input_check.py', prep_names, prep_constants)
obs, sha_o = reviewed(TARGET, PREFIX + 'ali_h_v1.py', obs_names, obs_constants, True)
old_obs, _ = reviewed(BASE, PREFIX + 'ali_h_v1.py', obs_names, obs_constants, True)
result = {'target': TARGET, 'base': BASE, 'numpy': np.__version__, 'source_sha256': {'t2_input_check.py': sha_p, 'ali_h_v1.py': sha_o}, 'scope': 'Reviewed named functions and literal constants compiled in memory. No archived imports, CLI/selftests, ROS, host, new trace, or repository writes.'}

# Independent SE(3) Exp oracle: power series of a 4x4 twist, not the target's Jacobian.
def exp_twist(w, rho):
    x, y, z = w
    X = np.zeros((4, 4)); X[:3, :3] = [[0, -z, y], [z, 0, -x], [-y, x, 0]]; X[:3, 3] = rho
    total = np.eye(4); term = np.eye(4)
    for k in range(1, 100):
        term = term @ X / k; total += term
        if np.linalg.norm(term) < 1e-18:
            break
    return total

post = np.eye(4); angle = .2
post[:3, :3] = [[math.cos(angle), -math.sin(angle), 0], [math.sin(angle), math.cos(angle), 0], [0, 0, 1]]
post[:3, 3] = [.1, 0, 0]
expected = np.array([0, 0, .2, .1 * (.2 / 2) / math.tan(.2 / 2), -.01, 0])
e_old = old['e_i'](np.eye(4), post); e_new = new['e_i'](np.eye(4), post)
assert np.max(np.abs(e_new - expected)) < 1e-12
P = np.diag([1., 1., 1., 1., 1e-6, 1.])
result['D1_planar'] = {'old_e': e_old.tolist(), 'new_e': e_new.tolist(), 'expected_e': expected.tolist(), 'old_s': old['s_i'](e_old, P)['s'], 'new_s': new['s_i'](e_new, P)['s']}
roundtrips = []
axis = np.array([.3, -.4, .5]); axis /= np.linalg.norm(axis)
rho = np.array([.11, -.07, .04])
pre = exp_twist(np.array([.13, .22, -.18]), np.array([1., -2., .3]))
world = exp_twist(np.array([-.4, .12, .09]), np.array([-3., .2, 1.]))
for th in [0., 1e-5, 8e-5, 2e-4, .2, .8]:
    w = th * axis; B = pre @ exp_twist(w, rho); truth = np.r_[w, rho]
    actual = new['e_i'](pre, B)
    err = float(np.max(np.abs(actual - truth)))
    invariant_err = float(np.max(np.abs(new['e_i'](world @ pre, world @ B) - actual)))
    order_err = float(np.max(np.abs(new['e_i'](pre, B, 'trans_rot') - np.r_[actual[3:], actual[:3]])))
    assert max(err, invariant_err, order_err) < 1e-10
    roundtrips.append({'theta': th, 'max_error': err, 'world_left_reexpression_error': invariant_err, 'order_error': order_err})
result['D1_normal_roundtrips'] = roundtrips

def blk(bid, M='MISSING', T='MISSING', I='MISSING'):
    return {'block_id': bid, 'verdicts': {c: {'verdict': v, 'u': None} for c, v in zip(('M', 'T', 'I'), (M, T, I))}}

def states(ns, blocks):
    return ns['classify_blocks'](blocks, None)

alarm_gap = [blk(10, M='ALARM'), blk(12, M='ALARM')]
normal_gap = [blk(10, T='NORMAL', I='NORMAL'), blk(12, T='NORMAL', I='NORMAL')]
assert states(old_obs, alarm_gap)[-1]['state'] == 'SUSPECT'
assert states(obs, alarm_gap)[-1]['state'] == 'UNKNOWN'
assert states(old_obs, normal_gap)[-1]['state'] == 'NORMAL_CONSISTENT'
assert states(obs, normal_gap)[-1]['state'] == 'UNKNOWN'
sequence = [blk(8, M='ALARM'), blk(9, M='ALARM'), blk(10, M='NO_DATA', T='NO_DATA', I='NO_DATA'), blk(11, M='ALARM'), blk(12, M='ALARM')]
r = states(obs, sequence)
assert [b['state'] for b in r] == ['UNKNOWN', 'SUSPECT', 'UNKNOWN', 'UNKNOWN', 'SUSPECT']
assert r[2]['reason_codes'] == ['NO_DATA_BLOCK'] and r[3]['last_suspect_block'] == 9
adjacent_controls = {'M_alarm': [blk(10, M='ALARM'), blk(11, M='ALARM')], 'I_alarm': [blk(10, I='ALARM'), blk(11, I='ALARM')], 'T_alarm': [blk(10, T='ALARM'), blk(11, T='ALARM')], 'I_T_normal': [blk(10, T='NORMAL', I='NORMAL'), blk(11, T='NORMAL', I='NORMAL')], 'I_M_normal': [blk(10, M='NORMAL', I='NORMAL'), blk(11, M='NORMAL', I='NORMAL')], 'T_only': [blk(10, T='NORMAL'), blk(11, T='NORMAL')]}
adjacent_results = {}
for name, seq in adjacent_controls.items():
    a, b = states(obs, seq), states(old_obs, seq)
    assert a == b
    adjacent_results[name] = {'state': a[-1]['state'], 'scope': a[-1]['scope']}
result['D2'] = {'old_alarm_gap': states(old_obs, alarm_gap)[-1]['state'], 'new_alarm_gap': states(obs, alarm_gap)[-1]['state'], 'old_normal_gap': states(old_obs, normal_gap)[-1]['state'], 'new_normal_gap': states(obs, normal_gap)[-1]['state'], 'explicit_NO_DATA_and_recovery': r, 'unchanged_adjacent_controls': adjacent_results}

def fake_frame(bid, score=100.):
    return {'block_id': bid, 'map_support': 'LOW', 'old': {'status': 'UNAVAILABLE'}, 'channels': {c: {'name': c, 'present': c == 'M', 'fresh': c == 'M', 'score': score if c == 'M' else None, 'reason': None} for c in ('M', 'T', 'I')}}
frames = [fake_frame(10), fake_frame(12), fake_frame(13)]
original_frames = copy.deepcopy(frames)
cal = obs['Calibration']({('M', 'LOW'): list(range(1, 21))})
filled = obs['block_summary'](frames, cal)
assert [b['block_id'] for b in filled] == [10, 11, 12, 13]
assert [b['state'] for b in filled] == ['UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'SUSPECT']
assert filled[1]['n_frames'] == 0 and all(filled[1]['verdicts'][c]['verdict'] == 'NO_DATA' for c in ('M', 'T', 'I'))
assert frames == original_frames and sum(b['n_frames'] for b in filled) == len(frames)
result['D2_full_pipeline'] = [{k: b[k] for k in ('block_id', 'n_frames', 'context', 'state', 'reason_codes', 'last_suspect_block')} for b in filled]

# The old manifested left/world covariance is now rejected; correct right/pre_body is accepted.
m = old['_manifest'](); m['covariance'].update(frame='world', perturbation='left')
assert old['check_manifest'](m)['status'] == 'READY'
rejected = new['check_manifest'](m); assert rejected['status'] == 'INCOMPLETE'
manifest_cases = {'valid': new['_manifest']()}
for key, change in [('decl_left', ('declarations', 'perturbation', 'left')), ('cov_left', ('covariance', 'perturbation', 'left')), ('cov_world', ('covariance', 'frame', 'world'))]:
    c = new['_manifest'](); c[change[0]][change[1]] = change[2]; manifest_cases[key] = c
c = new['_manifest'](); del c['covariance']['frame']; manifest_cases['cov_frame_missing'] = c
c = new['_manifest'](covariance={'usable': False, 'reason': 'no_pose_block'}); manifest_cases['unit_only'] = c
c = copy.deepcopy(c); c['declarations']['perturbation'] = 'left'; manifest_cases['unit_only_left'] = c
manifest_results = {k: new['check_manifest'](v) for k, v in manifest_cases.items()}
assert manifest_results['valid']['status'] == 'READY'
assert all(manifest_results[k]['status'] == 'INCOMPLETE' for k in ('decl_left', 'cov_left', 'cov_world', 'cov_frame_missing'))
assert manifest_results['unit_only']['status'] == manifest_results['unit_only_left']['status'] == 'READY_UNIT_ONLY'
pre2 = np.eye(4); pre2[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
post2 = pre2.copy(); post2[:3, 3] = [1, 0, 0]
e = new['e_i'](pre2, post2)
Pw = np.diag([1., 1., 1., 100., 1., 1.]); A = np.zeros((6, 6)); A[:3, :3] = pre2[:3, :3].T; A[3:, 3:] = pre2[:3, :3].T
wrong = new['s_i'](e, Pw)['s']; matched = new['s_i'](e, A @ Pw @ A.T)['s']
assert abs(wrong - 1.) < 1e-12 and abs(matched - .01) < 1e-12
result['D3'] = {'old_left_world_status': old['check_manifest'](m), 'new_left_world_status': rejected, 'manifest_cases': manifest_results, 'right_residual': e.tolist(), 'direct_unmatched_helper_score': wrong, 'matched_covariance_score': matched, 'scope': 'Validator closes manifest mismatch; low-level s_i still assumes caller supplied matching covariance. No delivered trace caller.'}

# Read saved artifacts as data. Recompute blocks only with reviewed non-I T0 functions.
manifest = json.loads(blob(TARGET, PREFIX + 'manifest.json'))
assert manifest['code_sha256'] == sha_o
integrity = []
for name, metadata in manifest['artifacts'].items():
    data = blob(TARGET, PREFIX + name)
    ok = len(data) == metadata['bytes'] and hashlib.sha256(data).hexdigest() == metadata['sha256']
    assert ok
    integrity.append({'artifact': name, 'hash_and_size_match': ok})
result['saved_artifact_integrity'] = integrity
populations = []
for key, suffix in [('A', ''), ('B', 'predicted_pose/')]:
    raw = blob(TARGET, 'docs/review_20261112_availability/' + suffix + 'availability_frames.jsonl.gz')
    assert hashlib.sha256(raw).hexdigest() == manifest['runs'][key]['frames_sha256']
    rows = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
    frames = [obs['frame_record'](row, row['run_id']) for row in rows]
    blocks = obs['block_summary'](frames, obs['Calibration']())
    saved = json.loads(blob(TARGET, PREFIX + 't0_' + key + '.json'))
    shadow = [json.loads(line) for line in blob(TARGET, PREFIX + 'shadow_' + key + '.jsonl').splitlines()]
    old_blocks = old_obs['block_summary'](frames, old_obs['Calibration']())
    assert len(rows) == len(shadow) == saved['population']['frames']
    assert len(blocks) == saved['population']['blocks']
    assert [{k: b[k] for k in ('block_id', 'n_frames', 'context', 'median_score', 'fresh_count', 'state', 'scope', 'reason_codes')} for b in blocks] == saved['blocks']
    states_by_frame = Counter()
    channel_counts = {c: Counter() for c in ('M', 'T', 'I')}
    for b in blocks:
        states_by_frame[b['state']] += b['n_frames']
        for c in ('M', 'T', 'I'):
            v = b['verdicts'][c]; k = v['verdict']
            if v['calibration'] in ('BLOCKED', 'OUT_OF_SUPPORT', 'INCOMPLETE'):
                k += '/' + v['calibration']
            channel_counts[c][k] += 1
    assert dict(states_by_frame) == saved['state_counts_by_frame']
    assert {c: dict(v) for c, v in channel_counts.items()} == saved['block_channel_status']
    by_bid = {b['block_id']: b for b in blocks}
    for f, row in zip(frames, shadow):
        assert all(f[k] == row[k] for k in f)
        b = by_bid[f['block_id']]
        assert all(row['shadow'][k] == b[k] for k in ('state', 'scope', 'reason_codes', 'last_suspect_block'))
    populations.append({'run': key, 'frames': len(rows), 'old_observed_blocks': len(old_blocks), 'new_time_population_blocks': len(blocks), 'no_data_block_ids': [b['block_id'] for b in blocks if b['n_frames'] == 0], 'state_counts_by_frame': dict(states_by_frame), 'channel_counts': {c: dict(v) for c, v in channel_counts.items()}, 'saved_blocks_and_shadow_match_recomputed': True})
result['T0_independent_readonly_recomputation'] = populations
saved_tests = {}
for name in ['t1_selftest.json', 't2_prep_selftest.json']:
    tests = json.loads(blob(TARGET, PREFIX + name))
    saved_tests[name] = {'test_count': len(tests['tests']), 'saved_pass_count': sum(t['status'] == 'PASS' for t in tests['tests']), 'saved_failed': tests['failed'], 't2_real_status': tests.get('t2_real_status'), 'independently_executed_selftest': False}
result['saved_tests_not_executed'] = saved_tests

# Check a narrow behavioral delta, not a malformed-input matrix.
assert old_obs['block_summary']([], old_obs['Calibration']()) == []
try:
    obs['block_summary']([], obs['Calibration']())
except ValueError as exc:
    result['empty_population_delta'] = {'base': [], 'target_exception': str(exc), 'scope': 'Empty input batch only; not the nonempty A/B archive paths, no real trace failure claim.'}
else:
    raise AssertionError('Expected target min(empty) behavior')
print(json.dumps(result, ensure_ascii=False, indent=2))
