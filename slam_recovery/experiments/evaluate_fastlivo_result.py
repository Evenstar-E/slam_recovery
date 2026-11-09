#!/usr/bin/env python
"""Evaluate a FAST-LIVO2 result bag against M2DGR ground truth.

Reads `/aft_mapped_to_init` from the recorded bag, associates it with the TUM ground-truth
file, fits a rigid SE(3) alignment on the leading prefix only (never on the evaluation window),
then reports ATE / RPE over the full overlap and over a caller-specified window.

Usage (ROS1 python):
  /home/R26534/mm/ros/bin/python -m slam_recovery.experiments.evaluate_fastlivo_result \
      --bag /tmp/fastlivo/res_room02_clean.bag --gt /home/R26534/M2DGR/GT/room_02.txt \
      --window 30,55 --out slam_recovery/experiments/manifests/p11_fastlivo2_room_02_clean.json
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import rosbag

from .evaluation import (
    associate_trajectories,
    evaluate_trajectory,
    load_tum_trajectory,
    umeyama_se3_align,
)


def read_odom(bag_path: str, topic: str = "/aft_mapped_to_init"):
    ts, xyz = [], []
    with rosbag.Bag(bag_path, "r") as b:
        for _, m, _ in b.read_messages(topics=[topic]):
            ts.append(m.header.stamp.to_sec())
            p = m.pose.pose.position
            xyz.append([p.x, p.y, p.z])
    ts_a = np.asarray(ts, dtype=np.float64)
    xyz_a = np.asarray(xyz, dtype=np.float64)
    order = np.argsort(ts_a)
    return ts_a[order], xyz_a[order]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--topic", default="/aft_mapped_to_init")
    ap.add_argument("--prefix-frac", type=float, default=0.20, help="fraction of the overlap used to fit SE(3)")
    ap.add_argument("--window", default=None, help="start,end seconds relative to the first matched pose")
    ap.add_argument("--out", required=True)
    ap.add_argument("--provenance", default="REAL_HOST")
    ap.add_argument("--gt-outlier-m", type=float, default=0.5,
                    help="drop a GT sample that disagrees with both neighbours by more than this")
    args = ap.parse_args()

    ts_est, xyz_est = read_odom(args.bag, args.topic)
    ts_gt, xyz_gt = load_tum_trajectory(args.gt)
    # M2DGR Mocap files carry isolated corrupted samples: on room_02 one sample at t=26.35 s
    # jumps 7.11 m away and returns 20 ms later, which alone turns a 0.17 m ATE into 0.25 m and
    # a 7.0 m ATE_max. A rigid body cannot move 7 m in one 20 ms sample, so drop samples that
    # disagree with both neighbours by more than `gt_outlier_m`.
    keep = np.ones(len(ts_gt), dtype=bool)
    if len(ts_gt) > 2:
        prev = np.linalg.norm(xyz_gt[1:-1] - xyz_gt[:-2], axis=1)
        nxt = np.linalg.norm(xyz_gt[2:] - xyz_gt[1:-1], axis=1)
        keep[1:-1] = ~((prev > args.gt_outlier_m) & (nxt > args.gt_outlier_m))
    n_gt_rejected = int((~keep).sum())
    ts_gt, xyz_gt = ts_gt[keep], xyz_gt[keep]
    ts_m, est_m, gt_m = associate_trajectories(ts_est, xyz_est, ts_gt, xyz_gt, 0.05)
    if len(ts_m) < 10:
        raise RuntimeError(f"only {len(ts_m)} associated poses")

    n_prefix = max(10, int(args.prefix_frac * len(ts_m)))
    R, t, _ = umeyama_se3_align(est_m[:n_prefix], gt_m[:n_prefix])
    aligned = (est_m @ R.T) + t

    full = evaluate_trajectory(ts_m, aligned, ts_m, gt_m, max_diff_sec=0.05)

    out = {
        "run_id": os.path.basename(args.out).replace(".json", ""),
        "host_system": "FAST-LIVO2",
        "provenance": args.provenance,
        "input_bag": args.bag,
        "gt_source": args.gt,
        "evaluation_protocol": {
            "association_max_dt_sec": 0.05,
            "alignment": f"rigid SE(3) fitted on the leading {args.prefix_frac:.0%} of matched poses, never on the evaluation window",
            "prefix_poses": n_prefix,
        },
        "matched_poses": int(len(ts_m)),
        "gt_outlier_samples_rejected": n_gt_rejected,
        "path_length_m": round(full.path_length_m, 4),
        "ate_rmse_m": round(full.ate_rmse_m, 4),
        "ate_mean_m": round(full.ate_mean_m, 4),
        "ate_max_m": round(full.ate_max_m, 4),
        "rpe_trans_rmse_m": round(full.rpe_trans_rmse_m, 4),
    }

    if args.window:
        lo, hi = (float(v) for v in args.window.split(","))
        t_rel = ts_m - ts_m[0]
        sel = (t_rel >= lo) & (t_rel <= hi)
        if int(sel.sum()) >= 5:
            err = np.linalg.norm(aligned[sel] - gt_m[sel], axis=1)
            out["window"] = {
                "start_sec": lo,
                "end_sec": hi,
                "num_poses": int(sel.sum()),
                "window_rmse_m": round(float(np.sqrt(np.mean(err ** 2))), 4),
                "window_max_m": round(float(err.max()), 4),
            }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
