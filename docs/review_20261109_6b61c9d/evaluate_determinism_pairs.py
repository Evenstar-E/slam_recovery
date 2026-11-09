#!/usr/bin/env python3
"""Recompute the T1/T2 aligned first-pose numbers from the archived output bags.

The results JSON reported `first_stamps` at the onset frame while the receipts report the actual
first output stamps; both are useful but they are different fields. This script defines and
reports them separately (`first_output` vs `first_scored`), states the gauge fit segment, the
matched-ID hash and the residual, and recomputes the aligned first-pose differences so the
1.13 cm (T1) and 1.9 mm (T2) numbers have a generator.

    python3 -B docs/review_20261109_6b61c9d/evaluate_determinism_pairs.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, os.path.join(_REPO, "docs", "review_20261109_bbc3dcb"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import verify_four_arm_independent as V                    # noqa: E402
from slam_recovery.experiments.evaluation import (          # noqa: E402
    load_tum_trajectory_se3, associate_trajectories)

GT = "/home/R26534/M2DGR/GT/room_02.txt"
ONSET_S = 1627643759.554082870
PAIRS = {"T1": ("/tmp/fastlivo/res_T1_O_r1.bag", "/tmp/fastlivo/res_T1_O_r2.bag"),
         "T2": ("/tmp/fastlivo/res_T2_O_r1.bag", "/tmp/fastlivo/res_T2_O_r2.bag")}
RECEIPTS = {"T1": ["room02_T1_receipt_r1.json", "room02_T1_receipt_r2.json"],
            "T2": ["room02_T2_receipt_r1.json", "room02_T2_receipt_r2.json"]}
RESULTS = os.path.join(_REPO, "docs", "review_20261109_bbc3dcb")
OUT = os.path.join(_HERE, "determinism_alignment.json")


def _ate(path, ts_gt, xyz_gt):
    ts, xyz, _q = V.load_poses(path)
    mt, me, mg = associate_trajectories(ts, xyz, ts_gt, xyz_gt, 0.05)
    if len(mt) < 10:
        return None, int(len(mt))
    R, t = V.umeyama(me, mg)
    err = np.linalg.norm(me @ R.T + t - mg, axis=1)
    return float(np.sqrt(np.mean(err ** 2))), int(len(mt))


def main():
    ts_gt, xyz_gt, _ = load_tum_trajectory_se3(GT)
    out = {"onset_s": ONSET_S,
           "field_definitions": {
               "first_output_s": "first stamped pose in the output bag",
               "first_scored_s": "first timestamp in the common matched stream (both runs)",
               "gauge_fit": "single SE(3) fitted on common poses with stamp < onset",
               "aligned_first_scored_m": "distance between the two poses at first_scored_s after "
                                         "applying that gauge",
               "aligned_at_onset_m": "same distance evaluated at the onset frame; this is the "
                                     "quantity the T1/T2 results JSON reports"},
           "pairs": {}}
    for tag, (pa, pb) in PAIRS.items():
        ta, xa, _qa = V.load_poses(pa)
        tb, xb, _qb = V.load_poses(pb)
        idx = np.clip(np.searchsorted(tb, ta), 1, len(tb) - 1)
        pick = np.where(np.abs(tb[idx - 1] - ta) <= np.abs(tb[idx] - ta), idx - 1, idx)
        ok = np.abs(tb[pick] - ta) <= 0.01
        ia, ib = np.flatnonzero(ok), pick[ok]
        ts = ta[ia]
        pre = ts < ONSET_S
        R_g, t_g = V.umeyama(xb[ib][pre], xa[ia][pre])
        gauge = np.linalg.norm(xb[ib][pre] @ R_g.T + t_g - xa[ia][pre], axis=1)
        dp = np.linalg.norm(xa[ia] - (xb[ib] @ R_g.T + t_g), axis=1)
        rec = {
            "run1_bag": pa, "run2_bag": pb,
            "run1_sha256": V._sha_file(pa), "run2_sha256": V._sha_file(pb),
            "first_output_run1_s": float(ta.min()), "first_output_run2_s": float(tb.min()),
            "first_scored_s": float(ts[0]),
            "common_ids": int(len(ts)),
            "common_ids_sha256": hashlib.sha256(
                ",".join(str(int(round(t * 1e9))) for t in ts).encode()).hexdigest(),
            "gauge_prefix_ids": int(pre.sum()),
            "gauge_prefix_range_s": [float(ts[pre].min()), float(ts[pre].max())],
            "gauge_residual_rmse_m": float(np.sqrt(np.mean(gauge ** 2))),
            "aligned_first_scored_m": float(dp[0]),
            "onset_index": int(np.argmin(np.abs(ts - ONSET_S))),
            "aligned_at_onset_m": float(dp[int(np.argmin(np.abs(ts - ONSET_S)))]),
            "raw_first_output_delta_m": float(np.linalg.norm(xa[0] - xb[0])),
            "ate_run1_m": _ate(pa, ts_gt, xyz_gt)[0],
            "ate_run2_m": _ate(pb, ts_gt, xyz_gt)[0],
        }
        for th in (0.05, 0.1, 1.0):
            hit = np.flatnonzero(dp > th)
            rec[f"first_aligned_over_{th:g}m_rel_onset_s"] = (
                float(ts[hit[0]] - ONSET_S) if len(hit) else None)
        for i, name in enumerate(RECEIPTS[tag]):
            path = os.path.join(RESULTS, name)
            if os.path.exists(path):
                d = json.load(open(path, encoding="utf-8"))
                rec[f"receipt_r{i + 1}_first_stamp_s"] = d["output"]["first_stamp_sec"]
                rec[f"receipt_r{i + 1}_output_sha256"] = d["output"]["sha256"]
        out["pairs"][tag] = rec
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    for tag, r in out["pairs"].items():
        print(tag, "first_output", round(r["first_output_run1_s"], 3),
              round(r["first_output_run2_s"], 3),
              "first_scored", round(r["first_scored_s"], 3),
              "aligned_first", round(r["aligned_first_scored_m"], 6),
              "gauge", round(r["gauge_residual_rmse_m"], 5))


if __name__ == "__main__":
    main()
