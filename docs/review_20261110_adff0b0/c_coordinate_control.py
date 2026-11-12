"""One normal physical-coordinate control for isolated C2 research; no bag or parameter scan."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REV = '545340f6ddb3cb64d0ce8fe5dc886eb45868a01e'
PATH = 'docs/gate_method_research_20261110/c2_fim_spatial.py'
source = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{REV}:{PATH}'])
namespace = {'__name__': 'review_only', '__file__': str(ROOT / PATH)}
exec(compile(source, namespace['__file__'], 'exec'), namespace)
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.validation import compute_6dof_point_to_plane_fim

a = np.linspace(-3, 3, 25)
u, w = np.meshgrid(a, a)
u, w = u.ravel(), w.ravel()
pts = np.vstack([
    np.column_stack([np.full(len(u), -4.), u, w]),
    np.column_stack([u, np.full(len(u), -4.), w]),
    np.column_stack([u, w, np.full(len(u), -4.)]),
])
R = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
moved = pts @ R.T
v = np.array([0., 0., 0., 1., 0., 0.])
vg = np.r_[R @ v[:3], R @ v[3:]]
rows = []
for name, fn in (('production', compute_6dof_point_to_plane_fim),
                 ('C2_research', namespace['fim_spatial'])):
    info = fn(pts, sigma_meas_m=.075)[0]
    info_g = fn(moved, sigma_meas_m=.075)[0]
    q, qg = float(v @ info @ v), float(vg @ info_g @ vg)
    rows.append({'method': name, 'projection_original': q, 'projection_rotated': qg,
                 'relative_difference': abs(qg - q) / abs(q)})
assert np.isclose(rows[0]['projection_original'], rows[0]['projection_rotated'])
assert rows[1]['relative_difference'] > .03
patch_path = 'docs/gate_method_research_20261110/c2_fim_spatial.patch'
patch = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{REV}:{patch_path}'])
check = subprocess.run(['git', '-C', str(ROOT), 'apply', '--check', '-'],
                       input=patch, capture_output=True)
assert check.returncode != 0
print(json.dumps({'research': REV, 'scope': '1875 synthetic points, fixed direction rotated; no ROS/bag/tuning',
                  'rows': rows, 'patch_apply_check': {
                      'exit_code': check.returncode, 'stderr': check.stderr.decode().strip()}}, indent=2))
