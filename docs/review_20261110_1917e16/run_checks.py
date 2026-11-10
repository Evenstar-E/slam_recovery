"""Version-bound gate fixtures and archive arithmetic; no bag, ROS or tuning run."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
REV = "1917e1658a97b1cea11fa39056dbf5b5b390f973"
FILES = (
    "slam_recovery/core.py",
    "slam_recovery/sim/transaction_manager_node.py",
    "slam_recovery/validation/fim_and_holdout.py",
    "slam_recovery/tests/test_tau_info_criterion.py",
)
for relative in FILES:
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{REV}:{relative}"])
    loaded = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(expected).digest() == hashlib.sha256(loaded).digest(), relative
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery import core
from slam_recovery.tests import test_tau_info_criterion as fixtures

TEST_MODULES = (
    "test_tau_info_criterion", "test_a7_tangent_frames", "test_atomic_commit",
    "test_checkpoint_restore", "test_trusted_map_invariance",
)
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(
    "slam_recovery.tests." + name) for name in TEST_MODULES)
result = unittest.TextTestRunner(verbosity=1).run(suite)
assert result.wasSuccessful()

rows = []
for before, after in ((40.23, 34.47), (1.1019, 4.628), (.01, .05)):
    report = fixtures._judge(before, after)
    rows.append({"before": before, "after": after, "mode": report.mode.value,
                 "accepted": report.accepted, "cov_fixture": .02})
assert [row["accepted"] for row in rows] == [False, True, False]

# The new file says a floor above 3.09 excludes the onset class. Reuse its own onset
# candidate; change only this review-local threshold to test that claim, not to tune it.
source = (ROOT / "slam_recovery/tests/test_tau_info_criterion.py").read_text(encoding="utf-8")
needle = "return evaluate_four_mode_gate(seg, cand, GateThresholds())"
assert source.count(needle) == 1
namespace = {"__name__": "review_floor_claim"}
exec(compile(source.replace(needle,
    "return evaluate_four_mode_gate(seg, cand, GateThresholds(tau_abs_min=3.5))"),
    "review-local floor-claim fixture", "exec"), namespace)
floor_report = namespace["_judge"](1.1019, 4.628)
assert floor_report.accepted

blob = subprocess.check_output(["git", "-C", str(ROOT), "show",
    f"{REV}:docs/review_20261110_b10/tau_info_evidence/tau_info_offline_results.json"])
data = json.loads(blob)
archive = []
for label, row in data["trigger_classes"].items():
    node = row["node_cloud"]
    delta = node["weak_dir_info_body"] - row["recorded_weak_dir_info_before"]
    assert np.isclose(delta, row["reproduces_delta"], rtol=0, atol=1e-12)
    assert abs(row["match_delta_ns"]) <= 40_000_000
    assert row["reproduces_recorded"]
    levels = []
    for pitch, level in row["sampling_levels"].items():
        w = np.asarray(level["weak_direction_6d"])
        levels.append({"pitch": pitch, "points": level["points"],
                       "info": level["weak_dir_info_body"],
                       "rotation_component_norm": float(np.linalg.norm(w[:3])),
                       "same_direction_as_node_up_to_sign": bool(np.isclose(
                           abs(w @ np.asarray(node["weak_direction_6d"])), 1.0)),
                       "below_fim_neighbor_requirement": level["points"] < 16})
    archive.append({"label": label, "delta": delta, "levels": levels})

# Actual FIM implementation returns its fallback here, not a measured 0.001 floor.
from slam_recovery.validation import compute_6dof_point_to_plane_fim
fim, covariance, _, _, weak = compute_6dof_point_to_plane_fim(
    np.arange(36, dtype=float).reshape(12, 3), sigma_meas_m=.075)
assert np.array_equal(fim, np.eye(6) * .001)
assert float(weak @ fim @ weak) == .001

# A changed gate does not fix the unchanged producer: reuse the accepted old probe,
# bypassing only its old source-pin/main routine after checking current files above.
import runpy
producer = runpy.run_path(str(ROOT / "docs/review_20261110_21fa650/a7_node_cov_probe.py"))
cloud = np.random.default_rng(0).normal(size=(400, 3)) * .16
producer_rows = [producer["run_case"](cloud, y) for y in (0., 20.)]
assert producer_rows[0]["accepted"] is False and producer_rows[1]["accepted"] is True

out = {
    "target": REV, "loaded_core": core.__file__, "tests_run": result.testsRun,
    "tests_passed": result.wasSuccessful(),
    "scope": "synthetic fixtures and archived JSON arithmetic; original bag not rerun",
    "production_thresholds_modified_by_review": False, "gate_fixtures": rows,
    "floor_claim_control": {"review_local_floor": 3.5, "after": 4.628,
                           "accepted": floor_report.accepted},
    "archive_checks": archive, "twelve_point_fim_is_fallback": True,
    "reused_actual_node_producer_probe": producer_rows,
    "actual_node_gauge_flip_persists": True,
}
print(json.dumps(out, indent=2))
