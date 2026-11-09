#!/usr/bin/env python3
"""Independent evaluation of the eight 2x2 host reruns.

Reads the eight result bags directly and applies the pre-registered rule from
`single_factor_preregistration.json`: a cell fails when its full-alignment ATE exceeds 1.0 m,
a cell is stable when both repeats land on the same side, and interaction requires O+F-B to fail
in both repeats while O+F and O-B fail in neither.

This is a cross-check of the host owner's numbers, not the deliverable: it reports every cell's
status and error, including failures, and writes its receipt next to the design.

    python3 -B docs/review_20261109_6b61c9d/evaluate_2x2_runs.py
"""

from __future__ import annotations

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
SIDECAR = "/tmp/fastlivo/room02_original_index_sidecar.npz"
DESIGN = os.path.join(_HERE, "single_factor_preregistration.json")
RECEIPT = os.path.join(_HERE, "evaluate_2x2_runs.json")
ARMS = ("O", "O_plus_F", "O_minus_B", "O_plus_F_minus_B")
REPS = (1, 2)
POSE_TOL_S = 0.075


def _bag(arm: str, rep: int) -> str:
    return f"/tmp/fastlivo/res_2x2_{arm}_r{rep}.bag"


def main():
    design = json.load(open(DESIGN, encoding="utf-8"))
    threshold = float(design["failure_threshold_ate_m"])
    ts_gt, xyz_gt, _ = load_tum_trajectory_se3(GT)
    side = np.load(SIDECAR)
    window_ns = np.asarray(sorted(int(k[1:]) for k in side.files if k.startswith("k")),
                           dtype=np.int64)

    cells = {a: [] for a in ARMS}
    for arm in ARMS:
        for rep in REPS:
            path = _bag(arm, rep)
            rec = {"arm": arm, "repeat": rep, "bag": path, "exists": os.path.exists(path)}
            if not rec["exists"]:
                rec.update({"status": "MISSING", "fail": None})
                cells[arm].append(rec)
                continue
            ts, xyz, _quat = V.load_poses(path)
            rec["poses"] = int(len(ts))
            rec["span_s"] = [float(ts.min()), float(ts.max())] if len(ts) else None
            # Service population: window scan stamps with a pose inside the 75 ms pairing rule.
            if len(ts):
                idx = np.clip(np.searchsorted(ts, window_ns * 1e-9), 1, len(ts) - 1)
                left, right = idx - 1, idx
                pick = np.where(np.abs(ts[left] - window_ns * 1e-9)
                                <= np.abs(ts[right] - window_ns * 1e-9), left, right)
                dt = np.abs(ts[pick] - window_ns * 1e-9)
                rec["window_frames_with_pose_75ms"] = int((dt <= POSE_TOL_S).sum())
                rec["window_frames"] = int(window_ns.size)
            mt, me, mg = associate_trajectories(ts, xyz, ts_gt, xyz_gt, 0.05)
            if len(mt) >= 10:
                Ru, tu = V.umeyama(me, mg)
                err = np.linalg.norm(me @ Ru.T + tu - mg, axis=1)
                rec["matched"] = int(len(mt))
                rec["ate_rmse_m"] = float(np.sqrt(np.mean(err ** 2)))
                rec["ate_max_m"] = float(err.max())
                rec["fail"] = bool(rec["ate_rmse_m"] > threshold)
            else:
                rec["status"] = "TOO_FEW_GT_MATCHES"
                rec["fail"] = None
            cells[arm].append(rec)

    verdict = {}
    for arm in ARMS:
        fails = [r["fail"] for r in cells[arm]]
        stable = all(f is not None for f in fails) and len(set(fails)) == 1
        verdict[arm] = {"fails": fails, "stable": bool(stable),
                        "cell_fails": bool(stable and fails[0] is True)}
    interaction = (verdict["O_plus_F_minus_B"]["cell_fails"]
                   and not verdict["O_plus_F"]["cell_fails"]
                   and not verdict["O_minus_B"]["cell_fails"]
                   and verdict["O_plus_F"]["stable"] and verdict["O_minus_B"]["stable"])
    if interaction:
        reading = "INTERACTION_SUPPORTED"
    elif any(v["cell_fails"] for v in verdict.values()):
        reading = "NOT_A_CLEAN_INTERACTION"
    else:
        reading = "NO_CELL_FAILED"
    res = {"design": design, "gt": GT, "threshold_ate_m": threshold,
           "cells": cells, "cell_verdicts": verdict,
           "reading": reading,
           "note": ("full-alignment ATE, one SE(3) fit over the whole trajectory; diagnostic, "
                    "not the frozen healthy-prefix protocol")}
    with open(RECEIPT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    for arm in ARMS:
        vals = [(r.get("ate_rmse_m"), r.get("matched"), r.get("fail")) for r in cells[arm]]
        print(arm, vals, "cell_fails=", verdict[arm]["cell_fails"])
    print(reading)


if __name__ == "__main__":
    main()
