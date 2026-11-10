"""Diagnostic controls for C_good's holdout NIS: fixed frames, explicit budgets, scoped oracle.

Run with the ROS python from the repository root:
  /home/R26534/mm/ros/bin/python -u docs/review_20261109_4598fb7/probe_c_good_attribution.py

What this is and is not
  - The frame set is fixed (the gate's committable set; every 5th key; mean).
  - The QUERY POPULATION is not identical across variants: a raw injected scan, the same scan with
    the injector's sector removed, and the clean run's scan are different point sets. Differences
    between variants therefore mix the observation change with a query-sampling change; they are
    reported as a sensitivity, not as a controlled causal attribution.
  - The oracle removal uses the injector's own azimuth geometry and is applied ONLY inside the
    absolute injection window; healthy post-injection frames are left untouched.
  - Requested and actual reference budgets are both reported. The reference is frozen at the
    four-arm construction (4000-point pre-onset map), so caps up to 4000 are real.
  - The gate's own path is run separately to recover its key set and its 1500-point scoring value;
    this probe is a new construction and does not claim to explain the archived 18.07 by identity.
"""
from __future__ import annotations

import json
import os

import numpy as np

from slam_recovery.experiments.run_four_arm_same_input import (
    pair_keyframes, detect_onset, world_points,
    DEFAULT_INJ_SCANS, DEFAULT_INJ_POSES, DEFAULT_CLN_SCANS, DEFAULT_CLN_POSES,
)
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.experiments.evaluation import umeyama_se3_align, associate_trajectories
from slam_recovery.core import TangentFrame

OCCLUSION_FRACTION = 0.88


def nis_param(train_xyz, hold_xyz, sigma, ref_cap=600, hold_cap=300):
    """Copy of the estimator with explicit budgets (diagnostic only; defaults untouched)."""
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
    onset_ns, end_ns = ev["start_abs_ns"], ev["end_abs_ns"]
    pre = [k for k in inj if k["ts_ns"] < onset_ns]
    quar = [k for k in inj if k["ts_ns"] >= onset_ns]

    # Frozen reference at the four-arm construction: 4000 points, not the 1500 scoring cap.
    ref_full = np.vstack([world_points(k) for k in pre])
    if len(ref_full) > 4000:
        ref_full = ref_full[:: max(1, len(ref_full) // 4000)][:4000]
    ref_1500 = ref_full[:: max(1, len(ref_full) // 1500)][:1500]

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

    # Gate path on the four-arm construction (full pre map for support; 1500 for its own scoring).
    node = OnlineRecoveryTransactionNode(confirmation_margin_sec=2.0, voxel_size_m=0.10, holdout_stride=5)
    node.committed_map_points = [ref_full]
    node.scan_buffer_body = {i: k["pts"] for i, k in enumerate(quar)}
    node._kf_timestamps = {i: int(k["ts"] * 1e9) for i, k in enumerate(quar)}
    node.tx_mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0e9))
    node.tx_mgr.trigger_quarantine(
        int(ev["start_rel_sec"] * 1e9), int((ev["start_rel_sec"] + 2.0) * 1e9),
        np.array([0, 0, 0, 1, 0, 0], dtype=np.float64), np.eye(6) * 2.0, 1.2,
        weak_direction_frame=TangentFrame("world", "rot_trans", "world"),
        info_before_frame=TangentFrame("world", "rot_trans", "world"),
        anchor_pose_world=np.eye(4),
    )
    report = node.evaluate_and_commit_candidate(
        "attribution", good, incumbent_poses=incumbent,
        reentry_anchor_pose=pre[-1]["pose"].copy())
    support_ref = node.support_reference()
    committable = [i for i in range(len(quar))
                   if i in incumbent and node._frame_has_reference_support(i, support_ref, good)]
    holdout = committable[::5]

    az_threshold = -np.pi + 2.0 * np.pi * OCCLUSION_FRACTION

    def variant_points(i, tag):
        k = quar[i]
        if tag == "raw":
            return k["pts"]
        if tag == "oracle":
            if onset_ns <= k["ts_ns"] <= end_ns:
                az = np.arctan2(k["pts"][:, 1], k["pts"][:, 0])
                return k["pts"][az > az_threshold]
            return k["pts"]           # healthy frame: untouched
        j = int(np.argmin(np.abs(cln_ts - k["ts"])))
        return cln[j]["pts"]

    def score(tag, ref_pts, cap):
        vals, missing = [], []
        for i in holdout:
            pw = variant_points(i, tag) @ good[i][:3, :3].T + good[i][:3, 3]
            v = nis_param(ref_pts, pw, 0.12, ref_cap=cap, hold_cap=min(300, cap // 2))
            if np.isfinite(v):
                vals.append(v)
            else:
                missing.append(int(i))
        v = np.asarray(vals)
        return {
            "n": int(len(v)),
            "missing_ids": missing,
            "mean": round(float(v.mean()), 3) if len(v) else None,
            "median": round(float(np.median(v)), 3) if len(v) else None,
            "requested_cap": cap,
            "actual_ref_points": int(min(cap, len(ref_pts))),
        }

    out = {
        "provenance": "ARCHIVED_REAL_HOST_POSES + INJECTION_SCANS; clean scans are ORACLE_CLEAN_SCANS",
        "statistic": "fixed frame set: gate committable keys, every 5th, mean estimator NIS",
        "query_population_note": ("raw scan vs sector-removed scan vs clean scan are different point "
                                  "sets; differences mix observation and query sampling and are not a "
                                  "controlled causal attribution"),
        "injection_window_ns": {"start": onset_ns, "end": end_ns},
        "oracle_removal": (f"azimuth <= {az_threshold:.4f} rad removed only inside the injection "
                           f"window ({OCCLUSION_FRACTION:.0%} of the circle)"),
        "gate_path": {
            "committable_keys": len(committable),
            "holdout_keys": len(holdout),
            "gate_holdout_nis_1500_ref": round(float(report.holdout_nis), 4),
            "gate_support": node._last_holdout_support,
            "reference_points_frozen": int(len(ref_full)),
            "reference_1500_points": int(len(ref_1500)),
        },
        "sensitivity_by_variant": {
            tag: score(tag, ref_full, 600) for tag in ("raw", "oracle", "clean")
        },
        "budget_sweep": {
            str(cap): {tag: score(tag, ref_full, cap) for tag in ("raw", "oracle", "clean")}
            for cap in (600, 1200, 2400, 4000)
        },
    }
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "c_good_attribution.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False, allow_nan=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
