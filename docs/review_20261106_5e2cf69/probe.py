"""Read-only boundary probes for section 9.11. Run from any directory with NumPy."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from slam_recovery.repair.point_mixture_repairer import filter_self_consistent_near_field_contaminants
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.validation.wilson_validator import evaluate_paired_sequential_benefit


def paired_example(total, available, small_min=4):
    node = OnlineRecoveryTransactionNode(min_paired_observations=small_min)
    rng = np.random.default_rng(12)
    reference = np.column_stack((rng.uniform(-1, 1, (90, 2)), np.zeros(90)))
    query = np.column_stack((rng.uniform(-1, 1, (80, 2)), np.zeros(80)))
    poses = {k: np.eye(4) for k in range(total)}
    incumbent = {k: np.eye(4) for k in range(available)}
    for k, pose in incumbent.items():
        pose[2, 3] = 0.25
        node.scan_buffer_body[k] = query
    node._measure_paired_evidence(poses, incumbent, np.eye(4), reference_world=reference)
    return node.last_paired_evidence


def filter_example(sheet_fraction):
    rng = np.random.default_rng(2026)
    n = 1000
    count = int(n * sheet_fraction)
    plane = np.column_stack((np.full(count, .35), rng.uniform(-.4, .4, (count, 2))))
    dirs = rng.normal(size=(n-count, 3))
    bg = dirs / np.linalg.norm(dirs, axis=1, keepdims=True) * rng.uniform(7, 10, (n-count, 1))
    points = np.column_stack((np.vstack((plane, bg)), np.full(n, 200.0)))
    mask, ratio, eigen, usable = filter_self_consistent_near_field_contaminants(points)
    points[:, 3] = rng.uniform(0, 255, n)
    other = filter_self_consistent_near_field_contaminants(points)
    return {"known_sheet": count, "estimated_fraction": float(ratio),
            "dropped_sheet": int(np.count_nonzero(~mask[:count])),
            "dropped_background": int(np.count_nonzero(~mask[count:])),
            "all_outputs_identical_after_changing_intensity": bool(np.array_equal(mask, other[0])
                and (ratio, eigen, usable) == tuple(other[1:]))}


def historical_b5():
    path = "slam_recovery/experiments/manifests/e3_orbslam3_second_host_benchmark.json"
    revisions = subprocess.check_output(["git", "log", "--reverse", "--format=%h", "HEAD", "--", path],
                                        cwd=ROOT, text=True).splitlines()
    def locate(obj):
        if isinstance(obj, dict):
            if "B5_Unvalidated_OpenLoop_Shift" in obj:
                yield obj["B5_Unvalidated_OpenLoop_Shift"]
            for child in obj.values():
                yield from locate(child)
    result = {}
    for rev in revisions:
        source = json.loads(subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT))
        result[rev] = [{k: row.get(k) for k in ("ate_rmse_m", "reentry_position_jump_m",
                                                "wilson_lower_bound", "rejection_reason")}
                       for row in locate(source) if row.get("ate_rmse_m") == 6.5554]
    return result


if __name__ == "__main__":
    jumps = {}
    for jump in (.40, .50, .5001):
        rep = evaluate_paired_sequential_benefit(np.ones(20), .5 * np.ones(20),
                                                  reentry_position_jump_m=jump)
        jumps[str(jump)] = {"approved": rep.approved, "reason": rep.reason}
    print(json.dumps({
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "provenance": "controlled function probes and versioned manifests; no sensor replay",
        "jump_m": jumps,
        "pairing": {f"{n}_keys_{a}_matched_base_{b}": paired_example(n, a, b)
                    for n, a, b in ((7, 4, 4), (8, 7, 4), (8, 8, 4), (8, 8, 10))},
        "synthetic_cloud": {str(f): filter_example(f) for f in (.2, .4)},
        "B5_hall01_archive": historical_b5(),
    }, indent=2, allow_nan=False))
