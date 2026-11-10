"""Small read-only checks of the archived research, not a bag replay or production change."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = '0edc3d76a43ddbed396eaf2dd2733f48d4ecffc4'
RESEARCH = 'b2892830a768ecc0c314536352e4a39748c583b5'
PREFIX = 'docs/gate_method_research_20261110/'


def blob(rev, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{rev}:{path}'])


for path in ('slam_recovery/core.py', 'slam_recovery/health/detector.py'):
    assert hashlib.sha256(blob(MAIN, path)).digest() == hashlib.sha256(
        (ROOT / path).read_bytes().replace(b'\r\n', b'\n')).digest(), path
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import HealthWindow
from slam_recovery.health.detector import JointHealthDetector

namespace = {'__name__': 'read_only_research_control', '__file__': str(ROOT / PREFIX / 'b1_health_prefix.py')}
exec(compile(blob(RESEARCH, PREFIX + 'b1_health_prefix.py'), namespace['__file__'], 'exec'), namespace)
research = namespace['Detector'](lambda t: 1.)
actual = JointHealthDetector()
research_states, actual_states = [], []
for i in range(25):
    research_states.append(research.step(i, 1.6))
    win = HealthWindow(
        t_start_ns=i, t_end_ns=i, min_eig_rot=100., min_eig_trans=100.,
        max_eig_rot_cov=.01, max_eig_trans_cov=.01, weak_dir_6d=np.ones(6) / np.sqrt(6),
        nis_mean=1.6, nis_q90=1.6 * 1.35, nis_cusum=0., loso_primary_conflict=0.,
        loso_aux_conflict=0., Cross_corr_lag_sec=0., loop_residual_spike=0.)
    actual_states.append(actual.step(win).state.value)
assert set(actual_states) == {'HEALTHY'}
assert research_states.index('SUSPECT') + 1 == 17

b1 = json.loads(blob(RESEARCH, PREFIX + 'b1_health_prefix.json'))['runs'][0]
b2 = json.loads(blob(RESEARCH, PREFIX + 'b2_rolling_scale.json'))
a = json.loads(blob(RESEARCH, PREFIX + 'a1_leg_attribution.json'))
receipt = json.loads((ROOT / 'docs/review_20261110_b10/native_loop_diagnosis_receipt.json').read_text())
manifest = json.loads((ROOT / 'docs/review_20261109_6b61c9d/single_factor_bags.json').read_text())
assert receipt['inputs']['bag_sha256'] == manifest['arms']['O']['sha256']
window = json.loads((ROOT / 'docs/review_20261109_bbc3dcb/room02_2x2_audit.json').read_text())['window']
span = (window['end_ns'] - window['onset_ns']) / 1e9
assert 19.659 < span
assert a['self_check']['rows'] == 18 and a['self_check']['reproduced'] == 17
assert len(a['summary']['blocked_on_cov']) == 4
print(json.dumps({
    'main': MAIN, 'research': RESEARCH,
    'scope': 'small arithmetic/source controls only; no archive replay, ROS, tuning or code changes',
    'constant_normalised_nis_1_6': {
        'frames': 25, 'actual_states': sorted(set(actual_states)),
        'research_first_suspect_frame': research_states.index('SUSPECT') + 1,
        'research_first_quarantine_frame': research_states.index('QUARANTINED') + 1},
    'baseline_recorded_x': b1['baseline']['first_suspect']['normalised_nis'],
    'undo_second_sigma_normalisation': b1['baseline']['first_suspect']['normalised_nis'] * b1['sigma0'] ** 2,
    'b1_pre_onset_judged': b1['B_v1']['pre_onset_judged'],
    'b1_pre_onset_total': b1['B_v1']['pre_onset_frames'],
    'b1_control_unjudged_span_s': b1['negative_control_contaminated_prefix']['unjudged_span_s'],
    'input_arm': 'O: background-only inside window; not original injected bag',
    'input_sha256': receipt['inputs']['bag_sha256'], 'nominal_window_s': span,
    'b2_last_quarantine_rel_onset_s': b2['scale_trajectory'][-1]['rel_onset_s'],
    'b2_scale_max': b2['fault_absorption']['scale_max_in_window'],
    'b2_scale_ratio': b2['fault_absorption']['drift_ratio_max_over_pre'],
    'a_self_check': {'rows': a['self_check']['rows'], 'reason_matches': a['self_check']['reproduced']},
    'a_summary': a['summary'],
}, indent=2))
