#!/usr/bin/env python3
"""A7 negative control: the same physical configuration, written in two world frames.

The gate forms D = v^T Lambda v. In the producer this project shipped, the weak direction and the
`before` information came from a scan's own points (body frame) while the repaired candidate's
information was assembled from world-frame points. That is a mixed-basis product: its value moves
when the world frame is re-expressed, and nothing reports it.

This script builds that scenario twice -- once with the world named W1 and once with the world
named W2 = G o W1 -- and prints what the gate decides in each. Run it against a tree:

  pre-fix : the two expressions decide differently          -> the defect, demonstrated
  fixed   : the mixed declaration is refused; declared and transported, the two expressions agree

    python -I docs/review_20261110_a7/negctl_a7.py [REPO_ROOT]
"""

from __future__ import annotations

import inspect
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                       os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

import slam_recovery.core as core  # noqa: E402

HAS_FRAMES = "weak_direction_frame" in inspect.signature(core.QuarantineSegment).parameters

V_BODY = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
INFO_BEFORE_BODY = np.diag([60.0, 60.0, 60.0, 20.0, 40.0, 40.0])
INFO_AFTER_W1 = np.diag([60.0, 60.0, 60.0, 30.0, 5.0, 5.0])


def rot_z(deg):
    c, s = np.cos(np.deg2rad(deg)), np.sin(np.deg2rad(deg))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def se3(R, t):
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


G = se3(rot_z(45.0), [3.0, -2.0, 1.5])          # re-expression of the world: p_W2 = G p_W1


def segment(v, info_before, v_frame=None, b_frame=None):
    ckpt = core.Checkpoint(checkpoint_id="ckpt", timestamp_ns=0, map_version=0, keyframe_poses={},
                           factor_ids=[], imu_bias_acc=np.zeros(3), imu_bias_gyr=np.zeros(3))
    kw = dict(segment_id="seg", checkpoint=ckpt, t_start_ns=10_000_000_000,
              t_end_ns=14_000_000_000, weak_direction_6d=np.asarray(v, float),
              info_before_6x6=np.asarray(info_before, float), propagated_cov_norm=0.6)
    if HAS_FRAMES:
        kw.update(weak_direction_frame=v_frame, info_before_frame=b_frame)
    return core.QuarantineSegment(**kw)


def candidate(info_after, frame=None):
    kw = dict(candidate_id="cand", parent_map_version=0, repaired_poses={1: np.eye(4)},
              info_after_6x6=np.asarray(info_after, float), cov_after_6x6=np.eye(6) * 0.10,
              holdout_nis=1.0, paired_benefit_approved=True, wilson_lower_bound=0.90,
              reentry_pos_jump_m=0.05)
    if HAS_FRAMES:
        kw.update(info_after_frame=frame)
    return core.CandidateMap(**kw)


def judge(seg, cand):
    try:
        r = core.evaluate_four_mode_gate(seg, cand)
    except Exception as exc:  # the refusal path is a result, not a crash
        return {"refused": type(exc).__name__, "why": str(exc)}
    return {"mode": r.mode.value, "accepted": r.accepted,
            "info_before": round(r.weak_dir_info_before, 6),
            "info_after": round(r.weak_dir_info_after, 6),
            "info_gain": round(r.weak_dir_info_gain, 6)}


def main():
    out = {"repo": ROOT, "has_frame_declarations": HAS_FRAMES}
    if HAS_FRAMES:
        body = core.TangentFrame("body", "rot_trans", "scan:7")
        world = core.TangentFrame("world", "rot_trans", "world")

        # (a) the shipped producer's actual convention: body weak direction, world candidate info
        out["mixed_declaration"] = judge(segment(V_BODY, INFO_BEFORE_BODY, body, body),
                                         candidate(INFO_AFTER_W1, world))

        # (b) the same physics, transported into one declared basis, in two world names
        world2 = core.TangentFrame("world", "rot_trans", "world:2")
        v_w1 = core.transport(V_BODY, np.eye(4))
        b_w1 = core.transport_information(INFO_BEFORE_BODY, np.eye(4))
        out["w1"] = judge(segment(v_w1, b_w1, world, world), candidate(INFO_AFTER_W1, world))
        out["w2"] = judge(segment(core.transport(v_w1, G),
                                  core.transport_information(b_w1, G), world2, world2),
                          candidate(core.transport_information(INFO_AFTER_W1, G), world2))
        out["same_decision"] = (out["w1"].get("mode") == out["w2"].get("mode")
                                and out["w1"].get("accepted") == out["w2"].get("accepted"))
    else:
        # pre-fix: no declarations, so this is exactly what the gate computes
        out["w1"] = judge(segment(V_BODY, INFO_BEFORE_BODY), candidate(INFO_AFTER_W1))
        # transport_information does not exist pre-fix; re-express by hand
        Ad = np.zeros((6, 6))
        R, t = G[:3, :3], G[:3, 3]
        Ad[:3, :3] = R
        Ad[3:, :3] = np.array([[0, -t[2], t[1]], [t[2], 0, -t[0]], [-t[1], t[0], 0]]) @ R
        Ad[3:, 3:] = R
        out["w2"] = judge(segment(V_BODY, INFO_BEFORE_BODY),
                          candidate(np.linalg.inv(Ad).T @ INFO_AFTER_W1 @ np.linalg.inv(Ad)))
        out["same_decision"] = (out["w1"]["mode"] == out["w2"]["mode"]
                                and out["w1"]["accepted"] == out["w2"]["accepted"])
    print(json.dumps(out, indent=1))
    return 0 if out["same_decision"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
