#!/usr/bin/env python3
"""Where do two identical-input repeats first disagree?

The eight native reruns used the same bags, config and binary, yet some cells split between a
~0.1 m and a >10 m trajectory. This compares each cell's two pose streams directly (the world
frames coincide because the input and initialisation are the same) and reports the first stamp at
which position or orientation diverge beyond fixed thresholds, both absolutely and relative to the
injection onset.

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
THRESHOLDS_M = (1e-3, 1e-2, 1e-1, 1.0)
ROT_THRESHOLD_RAD = 1e-3
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


def _angle(q1, q2):
    d = abs(float(np.dot(q1, q2)))
    return 2.0 * np.arccos(min(1.0, d))


def main():
    res = {"onset_s": ONSET_S, "thresholds_m": list(THRESHOLDS_M),
           "rotation_threshold_rad": ROT_THRESHOLD_RAD, "cells": {}}
    for arm in ARMS:
        a_ts, a_xyz, a_q = V.load_poses(_run(arm, 1))
        b_ts, b_xyz, b_q = V.load_poses(_run(arm, 2))
        ia, ib = _match(a_ts, b_ts)
        if len(ia) < 2:
            res["cells"][arm] = {"status": "NO_MATCH"}
            continue
        dp = np.linalg.norm(a_xyz[ia] - b_xyz[ib], axis=1)
        da = np.asarray([_angle(a_q[i], b_q[j]) for i, j in zip(ia, ib)])
        rec = {"status": "OK", "matched_poses": int(len(ia)),
               "first_stamp_s": float(a_ts[ia[0]]),
               "first_position_delta_m": float(dp[0]),
               "first_rotation_delta_rad": float(da[0]),
               "final_position_delta_m": float(dp[-1]),
               "max_position_delta_m": float(dp.max())}
        for th in THRESHOLDS_M:
            hit = np.flatnonzero(dp > th)
            rec[f"first_over_{th:g}m_s"] = (float(a_ts[ia[hit[0]]]) if len(hit) else None)
            rec[f"first_over_{th:g}m_rel_onset_s"] = (
                float(a_ts[ia[hit[0]]] - ONSET_S) if len(hit) else None)
        hit = np.flatnonzero(da > ROT_THRESHOLD_RAD)
        rec["first_rotation_over_threshold_s"] = (float(a_ts[ia[hit[0]]]) if len(hit) else None)
        rec["first_rotation_over_threshold_rel_onset_s"] = (
            float(a_ts[ia[hit[0]]] - ONSET_S) if len(hit) else None)
        res["cells"][arm] = rec
    with open(RECEIPT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    for arm, r in res["cells"].items():
        print(arm, "first>1cm", r.get("first_over_0.01m_rel_onset_s"),
              "first>1m", r.get("first_over_1m_rel_onset_s"),
              "max_dp", round(r.get("max_position_delta_m", float("nan")), 4))


if __name__ == "__main__":
    main()
