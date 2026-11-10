"""Small, dataset-free review probes; no ROS, bag, build, or production mutation.

The historical normal-path probe is adapted only for the new required anchor API.
Matrix examples disprove a claimed general bound; they are not field performance.
"""
import argparse
import contextlib
import subprocess
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np

BUNDLE = Path(__file__).resolve().parent
ROOT = BUNDLE.parents[1]
OLD = BUNDLE / "fixtures/normal_paths_original.py"
sys.path.insert(0, str(ROOT))

def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New JSON output path; existing files are refused")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; preserve prior evidence and choose a new path")
    subprocess.run(["git", "-C", str(ROOT), "diff", "--exit-code",
                    "493c5b3d056e5050af1a0fe915a1f749b3a81dd8", "--", "slam_recovery",
                    "docs/review_20261110_a7/a7_gauge_probes_fixed.py"], check=True)
    result = {"tested_commit": "493c5b3d056e5050af1a0fe915a1f749b3a81dd8",
              "scope": __doc__, "python": sys.version, "numpy": np.__version__}
    original = OLD.read_bytes()
    source = original.decode("utf-8")
    source = source.replace("ROOT = Path(__file__).resolve().parents[2]", f"ROOT = Path({str(ROOT)!r})")
    old_call = "weak_direction_frame=frame, info_before_frame=frame)"
    assert source.count(old_call) == 1
    source = source.replace(old_call,
                            "weak_direction_frame=frame, info_before_frame=frame, anchor_pose_world=np.eye(4))")
    namespace = {"__name__": "adapted_historical_normal_paths", "__file__": str(OLD)}
    exec(compile(source, str(OLD), "exec"), namespace)
    result["historical_probe_adapter"] = {
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "changes": ["Point ROOT at reviewed checkout", "Supply identity anchor required by current API"],
        "note": "Manager fixtures carry supplied passing evidence; these checks do not validate candidate quality."}
    checks = {}
    for name in ("partial_retry", "second_event", "late_arrival", "alarm_frame"):
        try:
            value = namespace[name]()
            value.pop("qualification", None)  # Old descriptive text asserted the old defect regardless of result.
            checks[name] = value
        except Exception as exc:
            checks[name] = {"passed": False, "error": repr(exc)}
    result["normal_paths"] = checks

    gauge = load_file("fixed_gauge_review", ROOT / "docs/review_20261110_a7/a7_gauge_probes_fixed.py")
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        gauge_rc = gauge.main()
    result["upstream_fixed_gauge_probe"] = {"exit_code": gauge_rc, "result": json.loads(capture.getvalue())}
    weak = np.array([0., 0., 0., 1., 0., 0.])
    before = np.diag([60., 60., 60., 1., 40., 40.])
    after = np.diag([60., 60., 60., 4., 5., 5.])
    gauges = [np.eye(4), gauge.se3(np.eye(3), [0., 2., 0.]),
              gauge.se3(np.eye(3), [0., 5., 0.]),
              gauge.se3(gauge.rot_z(30.), [.5, 2., -1.])]
    positives = [gauge.evaluate(weak, before, after, np.linalg.inv(after), T) for T in gauges]
    pos_ok = all(r["accepted"] for r in positives) and all(
        abs(r[k] - positives[0][k]) < 1e-9 for r in positives
        for k in ("info_before", "info_after", "covariance_norm"))
    result["gauge_positive_control"] = {"passed": pos_ok, "rows": positives,
                                        "note": "Synthetic positive control avoids vacuous invariance by universal refusal."}

    # A bag's max of per-frame minimum eigenvalues does not bound a fixed-direction quotient.
    a = np.diag([1., 5., 5.])
    b = np.diag([5., 1., 5.])
    v = np.array([1., 0., 0.])
    own_min_ceiling = max(float(np.linalg.eigvalsh(x)[0]) for x in (a, b))
    fixed_before = float(v @ a @ v)
    fixed_after = float(v @ ((a + b) / 2.) @ v)
    result["claimed_upper_bound_counterexample"] = {
        "matrix_a": a.tolist(), "matrix_b": b.tolist(),
        "max_per_frame_min_eigenvalue": own_min_ceiling,
        "trigger_direction_before": fixed_before, "candidate_fixed_direction_after": fixed_after,
        "after_ge_twice_before": fixed_after >= 2 * fixed_before,
        "claimed_bound_violated": fixed_after > own_min_ceiling,
        "interpretation": "Refutes the general bound only; does not establish any archived candidate is good or accepted."}

    from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
    from slam_recovery.ros.recovery_node import NativeClosedLoop
    node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0.)
    loop = NativeClosedLoop(node, "review-unavailable-probe")
    cloud = np.random.default_rng(13).normal(size=(100, 3))
    with patch.object(loop.nis, "measure", return_value=(None, "REVIEW_UNAVAILABLE", "NONE")), \
         patch.object(loop.nis, "support_reference", return_value=np.empty((0, 3))), \
         patch.object(node, "_frame_has_reference_support", return_value=False):
        for ts in (100_000_000, 200_000_000, 300_000_000):
            loop.on_pair(ts, np.eye(4), cloud)
    result["unavailable_trusted_ingest"] = {
        "detection_counts": loop.detection_counts, "detector_frames_fed": loop.frames_fed,
        "trusted_keys": sorted(node.tx_mgr.trusted_poses),
        "diagnostics": [{k: d[k] for k in ("kf_id", "detection_status", "detector_state")} for d in loop.diag],
        "note": "Forced unavailable measurement, zero confirmation margin to isolate state policy. This is not a real-world false-alarm/contamination rate."}
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if all(x["passed"] for x in checks.values()) and gauge_rc == 0 and pos_ok else 1

if __name__ == "__main__":
    sys.exit(main())
