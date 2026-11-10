"""A7 normal gauge probes: real FIM producer plus correctly transported covariance."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np

from slam_recovery.core import (
    CandidateMap, Checkpoint, QuarantineSegment, TangentFrame, adjoint,
    evaluate_four_mode_gate, transport, transport_information,
)
from slam_recovery.validation import compute_6dof_point_to_plane_fim


def evaluate(v, before, after, covariance, translation_y):
    transform = np.eye(4)
    transform[1, 3] = translation_y
    frame = TangentFrame("world", "rot_trans", "world")
    checkpoint = Checkpoint("probe", 0, 0, {}, [], np.zeros(3), np.zeros(3))
    segment = QuarantineSegment(
        "segment", checkpoint, 0, 4_000_000_000,
        transport(v, transform), transport_information(before, transform), 0.1,
        weak_direction_frame=frame, info_before_frame=frame)
    ad = adjoint(transform)
    candidate = CandidateMap(
        "candidate", 0, {1: np.eye(4)}, transport_information(after, transform),
        ad @ covariance @ ad.T, 1.0, info_after_frame=frame,
        paired_benefit_approved=True, wilson_lower_bound=0.9, reentry_pos_jump_m=0.05)
    result = evaluate_four_mode_gate(segment, candidate)
    return {"translation_y_m": translation_y,
            "weak_vector_norm": float(np.linalg.norm(transport(v, transform))),
            "info_before": result.weak_dir_info_before,
            "info_after": result.weak_dir_info_after,
            "covariance_norm": result.posterior_cov_norm, "mode": result.mode.value}


def main():
    cloud = np.random.default_rng(0).normal(size=(400, 3))
    before, _, _, _, weak = compute_6dof_point_to_plane_fim(0.5 * cloud, sigma_meas_m=0.075)
    after, _, _, _, _ = compute_6dof_point_to_plane_fim(0.8 * cloud, sigma_meas_m=0.075)
    covariance = np.linalg.inv(after + np.eye(6) * 0.001)
    direction_results = [evaluate(weak, before, after, covariance, t) for t in (0.0, 2.0)]
    assert direction_results[0]["mode"] == "MODE2_ATOMIC_COMMIT"
    assert direction_results[1]["mode"] == "MODE3_SOFT_BRIDGE_WAIT"
    assert all(r["covariance_norm"] < 0.5 for r in direction_results)

    weak = np.array([0, 0, 0, 1, 0, 0.0])
    before = np.diag([60, 60, 60, 20, 40, 40])
    after = np.diag([60, 60, 60, 30, 5, 5])
    covariance_results = [evaluate(weak, before, after, np.linalg.inv(after), t)
                          for t in (0.0, 5.0)]
    assert covariance_results[0]["mode"] == "MODE2_ATOMIC_COMMIT"
    assert covariance_results[1]["mode"] == "MODE3_SOFT_BRIDGE_WAIT"
    assert all(abs(r["info_after"] - 30.0) < 1e-8 for r in covariance_results)
    print(json.dumps({"scope": "Normal gauge re-expression, no native runs or hostile inputs",
                      "source_root": str(ROOT), "weak_direction_renormalization": direction_results,
                      "covariance_origin": covariance_results}, indent=2))
    print("Both A7 gauge-invariance failures reproduced without algorithm edits.")


if __name__ == "__main__":
    main()
