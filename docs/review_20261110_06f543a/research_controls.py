"""Fixed-trigger direction is not candidate own-weak direction; no new gate/host experiment."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = '06f543a4679caecbc6043636f79b29dafa4584df'
RESEARCH = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', '2449c0b'], text=True).strip()
path = 'slam_recovery/core.py'
expected = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{MAIN}:{path}'])
assert hashlib.sha256(expected).digest() == hashlib.sha256(
    (ROOT / path).read_bytes().replace(b'\r\n', b'\n')).digest()
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import (CandidateMap, Checkpoint, GateThresholds, QuarantineSegment,
                                TangentFrame, evaluate_four_mode_gate)

# Reuse the previously published b5554ef normal SPD fixture, not a new model or candidate run.
frame = TangentFrame('world', 'rot_trans', 'world')
v = np.array([0., 0., 0., 1., 0., 0.])
info = np.diag([300., 300., 300., 100., 38.8888888889, 38.8888888889])
checkpoint = Checkpoint('control', 0, 0, {}, [], np.zeros(3), np.zeros(3))
segment = QuarantineSegment('control', checkpoint, 0, 4_000_000_000, v,
                            np.diag([300., 300., 300., 45.4565, 60., 60.]), .1,
                            weak_direction_frame=frame, info_before_frame=frame,
                            anchor_pose_world=np.eye(4))
candidate = CandidateMap('control', 0, {1: np.eye(4)}, info, np.linalg.inv(info), .1,
                         info_after_frame=frame, cov_after_frame=frame,
                         paired_benefit_approved=True, wilson_lower_bound=.9,
                         reentry_pos_jump_m=.02, reentry_elapsed_s=0.)
report = evaluate_four_mode_gate(segment, candidate, GateThresholds())
q = float(v @ info @ v)
lam_min = float(np.linalg.eigvalsh(info)[0])
assert report.accepted and q == 100. and not np.isclose(q, lam_min)

# F2-A is equivalent to lambda_min >= floor, not generally to the fixed-direction scalar.
a = np.diag([300., 300., 300., 100., 1., 60.])
b = np.diag([300., 300., 300., 100., 4., 60.])
assert v @ a @ v == v @ b @ v
m_a = int(np.sum(np.linalg.eigvalsh(a) < 2.))
m_b = int(np.sum(np.linalg.eigvalsh(b) < 2.))
assert m_a == 1 and m_b == 0

base = 'docs/gate_method_research_20261110/'
def data(name):
    return json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show',
                                               f'{RESEARCH}:{base}{name}']))
p1, p2 = data('p1_before_recompute.json'), data('p2_subspace_gate.json')
assert p1['validation'] == {'reproduced': 5, 'of': 5}
assert p2['scalar_vs_subspace']['rank_identical_positions'] == 24
assert p2['scalar_vs_subspace']['pearson_r'] == 1.
angles = [float(np.rad2deg(np.arccos(r['weak_direction_alignment_cos']))) for r in p1['rows']]
fixed_factors = [r['old_direction_in_new_matrix'] / r['before_old_recomputed'] for r in p1['rows']]
print(json.dumps({
    'main': MAIN, 'research': RESEARCH,
    'scope': 'local arithmetic and reused normal SPD fixture, no ROS/bag/new method/tuning',
    'reused_gate_fixture': {'trigger_projection': q, 'candidate_own_min': lam_min,
                            'actual_gate_projection': report.weak_dir_info_after,
                            'accepted': report.accepted},
    'same_fixed_projection_different_F2A': {'projection': 100., 'm_a': m_a, 'm_b': m_b},
    'p1_archive_arithmetic': {'reported_matches': 5, 'precision': '4 decimals and tolerance, not bitwise',
                              'scan_dt_ms': [r['scan_dt_ms'] for r in p1['rows']],
                              'max_direction_angle_deg': max(angles),
                              'fixed_direction_factor_spread': max(fixed_factors) / min(fixed_factors)},
    'p2_archive': {'rows': len(p2['rows']), 'pearson_r': 1., 'rank_matches': 24,
                   'object': 'each matrix own minimum eigenvector versus same matrix minimum eigenvalue'}
}, indent=2))
