#!/usr/bin/env python3
"""The reviewer's two gauge counterexamples, re-run under the fixed evaluation basis.

Same physical scenarios as `docs/review_20261110_4255cbe/a7_gauge_probes.py`, same numbers:
the real default FIM producer for the rotated weak direction, and the diagonal before/after pair
for the covariance/origin case. What changed is the contract: the scene is authored in the trigger
scan's body frame, the segment carries T_world_from_anchor, and the candidate's information AND
covariance are declared in world. The old probe now stops at MissingAnchorPose, which is the point
-- it used to compute a number through a translation-bearing adjoint and re-normalise there.

    python -I docs/review_20261110_a7/a7_gauge_probes_fixed.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from slam_recovery.core import (  # noqa: E402
    CandidateMap, Checkpoint, QuarantineSegment, TangentFrame,
    evaluate_four_mode_gate, transport_covariance, transport_information,
)
from slam_recovery.validation import compute_6dof_point_to_plane_fim  # noqa: E402

BODY = TangentFrame("body", "rot_trans", "scan:7")
WORLD = TangentFrame("world", "rot_trans", "world")


def evaluate(v_body, before_body, after_body, cov_body, T_world_anchor):
    """Author the physics in the anchor body frame; submit the candidate in world."""
    checkpoint = Checkpoint("probe", 0, 0, {}, [], np.zeros(3), np.zeros(3))
    segment = QuarantineSegment(
        "segment", checkpoint, 0, 4_000_000_000,
        v_body, before_body, 0.1,
        weak_direction_frame=BODY, info_before_frame=BODY,
        anchor_pose_world=np.asarray(T_world_anchor, dtype=np.float64))
    candidate = CandidateMap(
        "candidate", 0, {1: np.eye(4)},
        transport_information(after_body, T_world_anchor),
        transport_covariance(cov_body, T_world_anchor), 1.0,
        info_after_frame=WORLD, cov_after_frame=WORLD,
        paired_benefit_approved=True, wilson_lower_bound=0.9, reentry_pos_jump_m=0.05)
    r = evaluate_four_mode_gate(segment, candidate)
    return {"world_y_m": float(T_world_anchor[1, 3]),
            "world_rotation_deg": None,
            "info_before": float(r.weak_dir_info_before),
            "info_after": float(r.weak_dir_info_after),
            "covariance_norm": float(r.posterior_cov_norm),
            "mode": r.mode.value, "accepted": r.accepted}


def rot_z(deg):
    c, s = np.cos(np.deg2rad(deg)), np.sin(np.deg2rad(deg))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def se3(R, t):
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


def main():
    cloud = np.random.default_rng(0).normal(size=(400, 3))
    before, _, _, _, weak = compute_6dof_point_to_plane_fim(0.5 * cloud, sigma_meas_m=0.075)
    after, _, _, _, _ = compute_6dof_point_to_plane_fim(0.8 * cloud, sigma_meas_m=0.075)
    covariance = np.linalg.inv(after + np.eye(6) * 0.001)

    direction = [evaluate(weak, before, after, covariance, se3(np.eye(3), [0.0, t, 0.0]))
                 for t in (0.0, 2.0)]

    weak2 = np.array([0, 0, 0, 1, 0, 0.0])
    before2 = np.diag([60, 60, 60, 20, 40, 40]).astype(np.float64)
    after2 = np.diag([60, 60, 60, 30, 5, 5]).astype(np.float64)
    cov2 = np.linalg.inv(after2)
    covariance_case = [evaluate(weak2, before2, after2, cov2, se3(np.eye(3), [0.0, t, 0.0]))
                       for t in (0.0, 5.0)]

    rotated = evaluate(weak, before, after, covariance,
                       se3(rot_z(30.0), [0.5, 2.0, -1.0]))
    rotated["world_rotation_deg"] = 30.0

    def same(rows, keys):
        def close(a, b, k):
            return a[k] == b[k] if isinstance(a[k], str) else abs(a[k] - b[k]) < 1e-9
        return all(all(close(a, b, k) for k in keys) for a, b in zip(rows, rows[1:]))

    out = {
        "scope": "gauge re-expression in the anchor body basis; no host run, no threshold change",
        "weak_direction_translation": direction,
        "info_and_mode_invariant": same(direction, ("info_before", "info_after", "mode")),
        "covariance_origin_translation": covariance_case,
        "covariance_and_mode_invariant": same(covariance_case,
                                              ("covariance_norm", "mode")),
        "rotated_anchor_with_translation": rotated,
        "rotated_matches_untranslated": (
            abs(rotated["info_before"] - direction[0]["info_before"]) < 1e-6
            and abs(rotated["info_after"] - direction[0]["info_after"]) < 1e-6
            and abs(rotated["covariance_norm"] - direction[0]["covariance_norm"]) < 1e-9
            and rotated["mode"] == direction[0]["mode"]),
    }
    print(json.dumps(out, indent=1))
    ok = (out["info_and_mode_invariant"] and out["covariance_and_mode_invariant"]
          and out["rotated_matches_untranslated"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
