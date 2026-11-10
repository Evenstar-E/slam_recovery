"""Check distribution arithmetic and fixed-direction versus own-weak-direction claims."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REV = "b5554ef5374a2995cf24d081cf2b1c8be614f9b5"
for relative in ("slam_recovery/core.py", "slam_recovery/validation/fim_and_holdout.py",
                 "slam_recovery/tests/test_tau_info_criterion.py"):
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{REV}:{relative}"])
    loaded = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(expected).digest() == hashlib.sha256(loaded).digest(), relative
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import (
    CandidateMap, Checkpoint, GateThresholds, QuarantineSegment,
    RecoveryMode, TangentFrame, evaluate_four_mode_gate,
)

blob = subprocess.check_output(["git", "-C", str(ROOT), "show",
    f"{REV}:docs/review_20261110_b10/tau_info_evidence/info_distribution_results.json"])
archive = json.loads(blob)
rows = []
for label, row in archive["bags"].items():
    n = row["frames"]
    floor = row["tau_abs_min_position"]
    ratio = row["ratio_feasibility"]
    assert np.isclose(floor["fraction_below"], floor["frames_below"] / n)
    assert np.isclose(ratio["fraction_above_that"], ratio["frames_above_that"] / n)
    assert np.isclose(ratio["max_before_that_can_still_pass"], row["weak_dir_info"]["max"] / 2)
    rows.append({"bag": label, "frames": n, "below_floor": floor["frames_below"],
                 "above_half_observed_own_weak_max": ratio["frames_above_that"],
                 "scope": "archive arithmetic only; not original scan recomputation"})

# A candidate's fixed trigger-direction projection is not its own minimum eigenvalue.
# SPD same-frame control; it proves an inference invalid, not that an actual bag repair exists.
world = TangentFrame("world", "rot_trans", "world")
v = np.array([0., 0., 0., 1., 0., 0.])
before = 45.4565
candidate_info = np.diag([300., 300., 300., 100., 38.8888888889, 38.8888888889])
checkpoint = Checkpoint("control", 0, 0, {}, [], np.zeros(3), np.zeros(3))
segment = QuarantineSegment(
    "control", checkpoint, 0, 4_000_000_000, v,
    np.diag([300., 300., 300., before, 60., 60.]), .1,
    weak_direction_frame=world, info_before_frame=world, anchor_pose_world=np.eye(4))
candidate = CandidateMap(
    "control", 0, {1: np.eye(4)}, candidate_info, np.linalg.inv(candidate_info), .1,
    info_after_frame=world, cov_after_frame=world,
    paired_benefit_approved=True, wilson_lower_bound=.9,
    reentry_pos_jump_m=.02, reentry_elapsed_s=0.)
report = evaluate_four_mode_gate(segment, candidate, GateThresholds())
own_weak = float(np.min(np.linalg.eigvalsh(candidate_info)))
fixed_projection = float(v @ candidate_info @ v)
assert own_weak < archive["bags"]["hall01_inj43_filtered"]["weak_dir_info"]["max"]
assert fixed_projection > 2 * before
assert report.accepted and report.mode == RecoveryMode.MODE2_ATOMIC_COMMIT
print(json.dumps({
    "target": REV, "production_modified": False, "archive_checks": rows,
    "same_basis_spd_control": {"before": before, "candidate_own_weak": own_weak,
        "candidate_trigger_direction_projection": fixed_projection,
        "translation_block_trace": float(np.trace(candidate_info[3:, 3:])),
        "posterior_cov_norm": report.posterior_cov_norm, "mode": report.mode.value,
        "accepted": report.accepted},
    "conclusion": "Observed maxima of per-frame own-weak values do not bound fixed-direction candidate values. Actual repair feasibility remains unknown.",
}, indent=2))
