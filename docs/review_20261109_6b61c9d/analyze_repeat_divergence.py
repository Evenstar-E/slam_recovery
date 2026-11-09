#!/usr/bin/env python3
"""Where do two identical-input repeats first disagree, after removing the gauge?

Two independent runs can start in different world frames (different initial gravity/bias and
different first-output times). Comparing raw poses therefore conflates the gauge with real
trajectory divergence. This script fits ONE SE(3) from run 2 into run 1 on the common healthy
pre-onset segment, reports the gauge residual, and then looks for the first *aligned* position or
orientation divergence and the first difference in adjacent relative motion.

The rule (stated for prospective use; this pass is POST_HOC_DESCRIPTIVE):
  * aligned divergence: first matched pose with |dp| > 1 cm or dangle > 1e-3 rad;
  * relative-motion divergence: first interval whose aligned step lengths differ by > 1 cm.

    python3 -B docs/review_20261109_6b61c9d/analyze_repeat_divergence.py
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

ONSET_S = 1627643759.554082870
THRESHOLDS_M = (0.05, 0.1, 0.5, 1.0)
ROT_THRESHOLD_RAD = 1e-3
STEP_THRESHOLD_M = 0.05
ARMS = ("O", "O_plus_F", "O_minus_B", "O_plus_F_minus_B")
RECEIPT = os.path.join(_HERE, "repeat_divergence.json")


def _run(arm, rep):
    return f"/tmp/fastlivo/res_2x2_{arm}_r{rep}.bag"


def _match(ts_a, ts_b, tol=0.01):
    idx = np.clip(np.searchsorted(ts_b, ts_a), 1, len(ts_b) - 1)
    left, right = idx - 1, idx
    pick = np.where(np.abs(ts_b[left] - ts_a) <= np.abs(ts_b[right] - ts_a), left, right)
    ok = np.abs(ts_b[pick] - ts_a) <= tol
    return np.flatnonzero(ok), pick[ok]


def _rot_angle(ra, rb):
    c = (np.trace(ra.T @ rb) - 1.0) / 2.0
    return float(np.arccos(np.clip(c, -1.0, 1.0)))


def main():
    res = {"onset_s": ONSET_S, "thresholds_m": list(THRESHOLDS_M),
           "rotation_threshold_rad": ROT_THRESHOLD_RAD,
           "step_threshold_m": STEP_THRESHOLD_M,
           "rule": "single SE(3) gauge fitted on common pre-onset poses; "
                   "then first aligned divergence; thresholds start above the fit residual",
           "threshold_note": "the gauge fit residual is ~1.3-1.5 cm, so 1 cm thresholds would fire "
                             "at the first sample by construction; 5 cm and above are reported",
           "status": "POST_HOC_DESCRIPTIVE", "cells": {}}
    for arm in ARMS:
        a_ts, a_xyz, a_q = V.load_poses(_run(arm, 1))
        b_ts, b_xyz, b_q = V.load_poses(_run(arm, 2))
        ia, ib = _match(a_ts, b_ts)
        if len(ia) < 10:
            res["cells"][arm] = {"status": "TOO_FEW_MATCHES"}
            continue
        ts = a_ts[ia]
        pa, pb = a_xyz[ia], b_xyz[ib]
        pre = ts < ONSET_S
        if pre.sum() < 5:
            res["cells"][arm] = {"status": "TOO_FEW_PREFIX"}
            continue
        # One gauge, fitted on the common healthy prefix: run2 -> run1.
        R_g, t_g = V.umeyama(pb[pre], pa[pre])
        gauge_err = np.linalg.norm(pb[pre] @ R_g.T + t_g - pa[pre], axis=1)
        pb_al = pb @ R_g.T + t_g
        dp = np.linalg.norm(pa - pb_al, axis=1)
        ra = np.asarray([V.quat_to_rot(q) for q in a_q[ia]])
        rb = np.asarray([R_g @ V.quat_to_rot(q) for q in b_q[ib]])
        da = np.asarray([_rot_angle(ra[i], rb[i]) for i in range(len(ts))])
        # Adjacent relative motion, after the same gauge.
        sa = np.linalg.norm(np.diff(pa, axis=0), axis=1)
        sb = np.linalg.norm(np.diff(pb_al, axis=0), axis=1)
        sd = np.abs(sa - sb)
        rec = {
            "status": "OK", "matched_poses": int(len(ts)),
            "gauge_prefix_matched": int(pre.sum()),
            "gauge_prefix_residual_rmse_m": float(np.sqrt(np.mean(gauge_err ** 2))),
            "first_output_run1_s": float(a_ts[0]), "first_output_run2_s": float(b_ts[0]),
            "first_output_spread_s": float(b_ts[0] - a_ts[0]),
            "raw_first_position_delta_m": float(np.linalg.norm(a_xyz[ia[0]] - b_xyz[ib[0]])),
            "aligned_first_position_delta_m": float(dp[0]),
            "aligned_first_rotation_delta_rad": float(da[0]),
            "aligned_max_position_delta_m": float(dp.max()),
            "max_step_delta_m": float(sd.max()),
        }
        for th in THRESHOLDS_M:
            hit = np.flatnonzero(dp > th)
            rec[f"first_aligned_over_{th:g}m_s"] = (float(ts[hit[0]]) if len(hit) else None)
            rec[f"first_aligned_over_{th:g}m_rel_onset_s"] = (
                float(ts[hit[0]] - ONSET_S) if len(hit) else None)
        hit = np.flatnonzero(da > ROT_THRESHOLD_RAD)
        rec["first_aligned_rotation_over_threshold_s"] = (float(ts[hit[0]]) if len(hit) else None)
        rec["first_aligned_rotation_over_threshold_rel_onset_s"] = (
            float(ts[hit[0]] - ONSET_S) if len(hit) else None)
        hit = np.flatnonzero(sd > STEP_THRESHOLD_M)
        rec["first_step_delta_over_threshold_s"] = (float(ts[hit[0] + 1]) if len(hit) else None)
        rec["first_step_delta_over_threshold_rel_onset_s"] = (
            float(ts[hit[0] + 1] - ONSET_S) if len(hit) else None)
        res["cells"][arm] = rec
    with open(RECEIPT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    for arm, r in res["cells"].items():
        if r.get("status") != "OK":
            print(arm, r)
            continue
        print(arm, "gauge_rmse", round(r["gauge_prefix_residual_rmse_m"], 4),
              "first>5cm", r["first_aligned_over_0.05m_rel_onset_s"],
              "first>10cm", r["first_aligned_over_0.1m_rel_onset_s"],
              "first>1m", r["first_aligned_over_1m_rel_onset_s"],
              "first_step_diff", r["first_step_delta_over_threshold_rel_onset_s"])


if __name__ == "__main__":
    main()
