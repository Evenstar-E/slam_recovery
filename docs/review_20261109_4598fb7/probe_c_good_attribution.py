"""Attribute C_good's holdout NIS: raw injected scans vs filtered vs clean scans.

Run with the ROS python from the repository root:
  /home/R26534/mm/ros/bin/python -u docs/review_20261109_4598fb7/probe_c_good_attribution.py

Fixed key set: every quarantine keyframe. Fixed query set per key: the scan's own points (the NIS
estimator internally subsamples to 600 reference / 300 holdout). Reference: the injected run's
pre-onset map capped at 1500 points, i.e. the gate's own `train_world`. Pose: the clean run's pose
mapped into the injected frame by the pre-onset SE(3) (the C_good construction). Only the scan
stream changes between variants:

  raw       clean pose + raw injected scan           (what C_good actually scores)
  filtered  clean pose + scan with 4.0-4.6 m returns removed
  clean     clean pose + clean scan                  (ORACLE, diagnostic only)

The filtered variant removes the sensor-range shell of the 4.30 m occluder. It is not a claim that
this is the right point filter; it is the contrast the review asked for.
"""
from __future__ import annotations

import json
import os

import numpy as np

from slam_recovery.experiments.run_four_arm_same_input import (
    pair_keyframes, detect_onset, world_points,
    DEFAULT_INJ_SCANS, DEFAULT_INJ_POSES, DEFAULT_CLN_SCANS, DEFAULT_CLN_POSES,
)
from slam_recovery.validation import compute_disjoint_holdout_point_to_plane_nis as nis
from slam_recovery.experiments.evaluation import umeyama_se3_align, associate_trajectories


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
    T_inv = np.eye(4)
    T_inv[:3, :3] = R.T
    T_inv[:3, 3] = -R.T @ t
    fit_res = np.linalg.norm(a @ R.T + t - b, axis=1)

    vals = {"raw": [], "filtered": [], "clean": [], "raw_host_pose": []}
    for k in quar:
        j = int(np.argmin(np.abs(cln_ts - k["ts"])))
        good_pose = T_inv @ cln[j]["pose"]
        raw = k["pts"]
        rr = np.linalg.norm(raw, axis=1)
        filtered = raw[(rr < 4.0) | (rr > 4.6)]
        for tag, pose, pts in (
            ("raw", good_pose, raw),
            ("filtered", good_pose, filtered),
            ("clean", good_pose, cln[j]["pts"]),
            ("raw_host_pose", k["pose"], raw),
        ):
            pw = pts @ pose[:3, :3].T + pose[:3, 3]
            vals[tag].append(float(nis(ref, pw, np.eye(4), sigma_meas_m=0.12)))

    def summary(v):
        a = np.asarray([x for x in v if np.isfinite(x)])
        return {
            "n": int(len(a)),
            "mean": round(float(a.mean()), 3),
            "median": round(float(np.median(a)), 3),
            "p90": round(float(np.percentile(a, 90)), 3),
            "equivalent_residual_m": round(float(np.sqrt(np.mean(a) * 0.12 ** 2)), 3),
        }

    out = {
        "provenance": "ARCHIVED_REAL_HOST_POSES + INJECTION_SCANS; clean scans are ORACLE_CLEAN_SCANS",
        "onset_rel_sec": round(float(ev["start_rel_sec"]), 3),
        "pre_keyframes": len(pre),
        "quarantine_keyframes": len(quar),
        "reference_points": int(len(ref)),
        "alignment_fit_pairs": int(len(a)),
        "alignment_fit_residual_m": {"mean": round(float(fit_res.mean()), 6),
                                     "p95": round(float(np.percentile(fit_res, 95)), 6)},
        "variants": {k: summary(v) for k, v in vals.items()},
        "reading": ("Compare medians: the clean-scan control is the floor imposed by the reference "
                    "budget and the cross-run alignment. If raw is close to clean, the occluder is "
                    "not what drives the NIS; if filtered moves toward clean, it is."),
        "filter": "drop returns with sensor range in [4.0, 4.6] m (the 4.30 m sheet shell)",
    }
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "c_good_attribution.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False, allow_nan=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
