"""One exact covariant control for the new research normalisation, not a bag/producer run."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = 'e2db4b3cfc2edda324c98a94e651f57888364719'
RESEARCH = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', '3e9f947'], text=True).strip()
path = 'slam_recovery/core.py'
expected = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{MAIN}:{path}'])
assert hashlib.sha256(expected).digest() == hashlib.sha256(
    (ROOT / path).read_bytes().replace(b'\r\n', b'\n')).digest()
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import transport, transport_information

# The direction is fixed in physical space. An exact transported SPD matrix has no sampling error.
info = np.diag([10., 20., 1., 40., 50., 60.])
v = np.array([0., 0., 1., 0., 0., 0.])
a = np.deg2rad(30.)
G = np.eye(4)
G[:3, :3] = [[np.cos(a), -np.sin(a), 0.], [np.sin(a), np.cos(a), 0.], [0., 0., 1.]]
rows = []
for label, shift in (('rotation_only', [0., 0., 0.]),
                     ('research_rotation_plus_translation', [2., -1., .5])):
    G[:3, 3] = shift
    vg = transport(v, G)
    moved_info = transport_information(info, G)
    original = float(v @ info @ v)
    fixed = float(vg @ moved_info @ vg)
    unit_vg = vg / np.linalg.norm(vg)
    renormalised = float(unit_vg @ moved_info @ unit_vg)
    assert np.isclose(fixed, original)
    rows.append({'case': label, 'translation': shift, 'transported_direction_norm': float(np.linalg.norm(vg)),
                 'original_projection': original, 'physical_fixed_projection': fixed,
                 'research_renormalised_projection': renormalised})
assert np.isclose(rows[1]['research_renormalised_projection'], 1. / 6.)
base = 'docs/gate_method_research_20261110/'
data = json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show',
                                          f'{RESEARCH}:{base}p2_subspace_gate.json']))
source = subprocess.check_output(['git', '-C', str(ROOT), 'show',
                                 f'{RESEARCH}:{base}p2_subspace_gate.py']).decode()
assert 'G = se3(deg, [2.0, -1.0, 0.5]) if deg else np.eye(4)' in source
assert 'vn_fixed = vn_fixed / np.linalg.norm(vn_fixed)' in source
print(json.dumps({'main': MAIN, 'research': RESEARCH,
                  'scope': 'exact SPD transport control only; no bag, raw producer or gate experiments',
                  'rows': rows,
                  'archive_controls_present': len(data['rotation_control']['sources']),
                  'loewner_definition_recorded': data['_meta']['form2_loewner_frozen'],
                  'limit': 'No claim that all archived percentage differences come from normalisation; C2 non-integration stands'}, indent=2))
