"""Attribute C_good's holdout NIS with the gate's own holdout set, and an oracle sheet removal.

Run with the ROS python from the repository root:
  /home/R26534/mm/ros/bin/python -u docs/review_20261109_4598fb7/probe_c_good_attribution.py

Controls, all on the SAME fixed keyframe/query set (the gate's committable set, every 5th key, mean):

  raw        C_good: clean pose + raw injected scan
  oracle     clean pose + the injected azimuth sector removed (the injector's own mask geometry)
  clean      clean pose + clean scan (ORACLE_CLEAN_SCANS; diagnostic only)

A spherical-shell filter is NOT the injector's geometry: the sheet is a tilted plane
n^T p = 4.30 with n=(1,0.15,0.05), so its range varies with the ray direction. The oracle removal
drops exactly the azimuth sector the injector replaced (88% of the circle by default).

The reference budget is swept with a local parameterised copy of the estimator; the shared
`compute_disjoint_holdout_point_to_plane_nis` defaults are not touched.
"""
from __future__ import annotations

import json
import os

import numpy as np

from slam_recovery.core import GateThresholds
from slam_recovery.experiments.run_four_arm_same_input import (
    pair_keyframes, detect_onset, world_points,
    DEFAULT_INJ_SCANS, DEFAULT_INJ_POSES, DEFAULT_CLN_SCANS, DEFAULT_CLN_POSES,
)
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.validation import compute_disjoint_holdout_point_to_plane_nis as nis
from slam_recovery.experiments.evaluation import umeyama_se3_align, associate_trajectories

OCCLUSION_FRACTION = 0.88


def nis_param(train_xyz, hold_xyz, sigma, ref_cap=600, hold_cap=300):
    """Copy of the estimator with explicit budgets (diagnostic only)."""
    t = np.asarray(train_xyz, dtype=np.float64)[:, :3]
    h = np.asarray(hold_xyz, dtype=np.float64)[:, :3]
    if len(t) < 30 or len(h) < 10:
        return float("inf")
    ts = t[:: max(1, len(t) // ref_cap)][:ref_cap]
    hs = h[:: max(1, len(h) // hold_cap)][:hold_cap]
    d2 = np.sum((hs[:, None, :] - ts[None, :, :]) ** 2, axis=-1)
    k = min(8, len(ts) - 1)
    idx = np.argpartition(d2, kth=k, axis=1)[:, :k]
    nb = ts[idx]
    mn = nb.mean(axis=1)
    c = nb - mn[:, None, :]
    covs = np.einsum("mki,mkj->mij", c, c) / float(k)
    _, ev = np.linalg.eigh(covs)
    res = np.abs(np.sum(ev[:, :, 0] * (hs - mn), axis=1))
    v = res[res < 2.0]
    if len(v) == 0 or len(v) / max(len(res), 1) < 0.70:
        return float(np.mean((res / sigma) ** 2))
    return float(np.mean((v / sigma) ** 2))


def main() -> None:
    inj, _ = pair_keyframes(DEFAULT_INJ_SCANS, DEFAULT_INJ_POSES, False)
    cln, _ = pair_keyframes(DEFAULT_CLN_SCANS, DEFAULT_CLN_POSES, False)
    _, _, ev = detect_onset(DEFAULT_CLN_SCANS, DEFAULT_INJ_SCANS)
    onset_abs = ev["start_abs_sec"]
    pre = [k for k in inj if k["ts"] < onset_abs]
    quar = [k for k in inj if k["ts"] >= onset_abs]

    ref = np.vstack([world_points(k) for k in pre])
    if len(ref) > 1500:
        ref = ref[:: max(1, len(ref) // 1500)][:1500]

    cln_ts = np.asarray([k["ts"] for k in cln])
    cln_xyz = np.asarray([k["pose"][:3, 3] for k in cln])
    pre_ts = np.asarray([k["ts"] for k in pre])
    pre_xyz = np.asarray([k["pose"][:3, 3] for k in pre])
    _, a, b = associate_trajectories(pre_ts, pre_xyz, cln_ts, cln_xyz, 0.05)
    R, t, _ = umeyama_se3_align(a, b)
    T_inv = np.eye(4); T_inv[:3, :3] = R.T; T_inv[:3, 3] = -R.T @ t

    good = {}
    for i, k in enumerate(quar):
        j = int(np.argmin(np.abs(cln_ts - k["ts"])))
        good[i] = T_inv @ cln[j]["pose"]

    incumbent = {i: k["pose"].copy() for i, k in enumerate(quar)}
    node = OnlineRecoveryTransactionNode(confirmation_margin_sec=2.0, voxel_size_m=0.10, holdout_stride=5)
    node.committed_map_points = [ref]
    node.scan_buffer_body = {i: k["pts"] for i, k in enumerate(quar)}
    node._kf_timestamps = {i: int(k["ts"] * 1e9) for i, k in enumerate(quar)}
    node.tx_mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0e9))
    node.tx_mgr.trigger_quarantine(
        int(ev["start_rel_sec"] * 1e9), int((ev["start_rel_sec"] + 2.0) * 1e9),
        np.array([0, 0, 0, 1, 0, 0], dtype=np.float64), np.eye(6) * 2.0, 1.2,
    )
    report = node.evaluate_and_commit_candidate(
        "attribution", good, incumbent_poses=incumbent,
        reentry_anchor_pose=pre[-1]["pose"].copy())
    support = node._last_holdout_support
    # The gate rejects this candidate (Mode 3), so committed_pose_keys is empty; the fixed set is
    # the committable set, reconstructed with the node's own support test.
    support_ref = node.support_reference()
    committable = [i for i in range(len(quar))
                   if i in incumbent and node._frame_has_reference_support(i, support_ref, good)]
    holdout = committable[::5]
    print("committable", len(committable), "holdout", len(holdout), "gate NIS", report.holdout_nis)

    az_threshold = -np.pi + 2.0 * np.pi * OCCLUSION_FRACTION

    def oracle_removed(pts):
        az = np.arctan2(pts[:, 1], pts[:, 0])
        return pts[az > az_threshold]

    def variant_points(i, tag):
        k = quar[i]
        if tag == "raw":
            return k["pts"]
        if tag == "oracle":
            return oracle_removed(k["pts"])
        j = int(np.argmin(np.abs(cln_ts - k["ts"])))
        return cln[j]["pts"]

    def score(tag, ref_pts, ref_cap=600, hold_cap=300):
        vals = []
        for i in holdout:
            pw = variant_points(i, tag) @ good[i][:3, :3].T + good[i][:3, 3]
            vals.append(nis_param(ref_pts, pw, 0.12, ref_cap, hold_cap))
        v = np.asarray([x for x in vals if np.isfinite(x)])
        return {
            "n": int(len(v)),
            "mean": round(float(v.mean()), 3) if len(v) else None,
            "median": round(float(np.median(v)), 3) if len(v) else None,
        }

    out = {
        "provenance": "ARCHIVED_REAL_HOST_POSES + INJECTION_SCANS; clean scans are ORACLE_CLEAN_SCANS",
        "statistic": "gate holdout set: every 5th committable keyframe, mean of the estimator NIS",
        "committable_keys": len(committable),
        "holdout_keys": len(holdout),
        "gate_holdout_nis": round(float(report.holdout_nis), 4),
        "reference_points": int(len(ref)),
        "oracle_removal": (f"azimuth <= {az_threshold:.4f} rad removed (injector's replaced sector, "
                           f"{OCCLUSION_FRACTION:.0%} of the circle)"),
        "variants": {tag: score(tag, ref) for tag in ("raw", "oracle", "clean")},
        "budget_sweep": {
            str(cap): {tag: score(tag, ref, ref_cap=cap, hold_cap=min(300, cap // 2))
                       for tag in ("raw", "clean")}
            for cap in (600, 1200, 2400)
        },
        "support": {
            "committable": support.get("candidate_frames_committable"),
            "deferred": support.get("candidate_frames_deferred"),
            "holdout_frames_total": support.get("holdout_frames_total"),
        },
    }
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "c_good_attribution.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False, allow_nan=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
