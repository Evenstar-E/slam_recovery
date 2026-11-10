#!/usr/bin/env python3
"""Per-frame weak-direction information over two bags: is an absolute floor like 3.0 ever inside
the natural range?

`tau_abs_min` is still an absolute number, and it was derived from one bag. This sweeps *every*
frame of both bags through the same FIM the node uses, so the question "does 3.0 sit at the bottom
of the range, or inside it?" can be answered per bag instead of inferred from two decisions.

The quantity is `v^T Lambda v` on each frame's own 6000-point cloud, at the node's FIM sigma
(0.075). It is the same quantity `weak_dir_info_before` is computed from, evaluated on every frame
rather than only on the frame that happened to trigger.

    python3 -B docs/review_20261110_b10/tau_info_evidence/run_info_distribution.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_B10 = os.path.dirname(_HERE)
_REPO = os.path.dirname(os.path.dirname(_B10))
for _p in (_HERE, _B10, _REPO, os.path.join(_REPO, "docs", "review_20261109_bbc3dcb")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import verify_four_arm_independent as V          # noqa: E402
from slam_recovery.validation import compute_6dof_point_to_plane_fim  # noqa: E402

sys.path.insert(0, _HERE)
from run_tau_info_offline import load_clouds, _subsample, SCAN_CAP, FIM_SIGMA  # noqa: E402

BAGS = {
    "room02_2x2_O": "/tmp/fastlivo/room02_2x2_O.bag",
    "hall01_inj43_filtered": "/tmp/fastlivo/hall01_inj43_filtered.bag",
}
OUT = os.path.join(_HERE, "info_distribution_results.json")
TAU_ABS_MIN = 3.0        # the value frozen by the pre-registration; measured against, not changed
KAPPA = 2.0              # likewise frozen; measured against, not changed


def main() -> int:
    res = {"protocol": "per-frame v^T Lambda v on each frame's own cloud, node preprocessing",
           "fim_sigma_m": FIM_SIGMA, "scan_cap": SCAN_CAP,
           "tau_abs_min_under_test": TAU_ABS_MIN, "kappa_under_test": KAPPA, "bags": {}}
    for label, path in BAGS.items():
        if not os.path.exists(path):
            res["bags"][label] = {"status": "BAG_MISSING", "path": path}
            continue
        clouds = load_clouds(path)
        stamps = sorted(clouds)
        info, minr, mint = [], [], []
        for ns in stamps:
            pts = _subsample(clouds[ns], SCAN_CAP)
            if len(pts) < 30:
                continue
            fim, _cov, r, t, weak = compute_6dof_point_to_plane_fim(pts, sigma_meas_m=FIM_SIGMA)
            w = np.asarray(weak, dtype=np.float64)
            info.append(float(w @ fim @ w))
            minr.append(float(r))
            mint.append(float(t))
        if not info:
            res["bags"][label] = {"status": "NO_USABLE_FRAMES"}
            continue
        a = np.asarray(info)
        q = {f"p{p}": float(np.percentile(a, p)) for p in (0, 10, 50, 90, 100)}
        below = int(np.sum(a < TAU_ABS_MIN))
        res["bags"][label] = {
            "bag": {"path": path, "sha256": V._sha_file(path)},
            "frames": int(len(a)),
            "weak_dir_info": {"min": q["p0"], "p10": q["p10"], "median": q["p50"],
                              "p90": q["p90"], "max": q["p100"],
                              "span_max_over_min": (q["p100"] / q["p0"]) if q["p0"] > 0 else None},
            "min_eig_rot": {"min": float(min(minr)), "median": float(np.median(minr)),
                            "max": float(max(minr))},
            "min_eig_trans": {"min": float(min(mint)), "median": float(np.median(mint)),
                              "max": float(max(mint))},
            # A ratio leg `after >= kappa * before` is unreachable whenever `before` exceeds the
            # best information any frame in that bag attains, divided by kappa. That is a property
            # of the bag, not of the candidate, so it is measured here rather than argued.
            "ratio_feasibility": {
                "kappa": KAPPA,
                "max_info_in_bag": q["p100"],
                "max_before_that_can_still_pass": q["p100"] / KAPPA,
                "frames_above_that": int(np.sum(a > q["p100"] / KAPPA)),
                "fraction_above_that": float(np.mean(a > q["p100"] / KAPPA)),
                "reading": ("for those frames `after >= kappa*before` cannot be satisfied by any "
                            "candidate, because no candidate can exceed the bag's own maximum"),
            },
            "tau_abs_min_position": {
                "value": TAU_ABS_MIN,
                "frames_below": below,
                "fraction_below": below / len(a),
                "percentile_of_threshold": float(np.mean(a <= TAU_ABS_MIN) * 100.0),
                "reading": ("threshold sits below every frame of this bag"
                            if below == 0 else
                            f"threshold sits inside the range: {below} of {len(a)} frames are below it"),
            },
        }
        b = res["bags"][label]
        print(f"[] {label}: {len(a)} frames, info min {q['p0']:.4f} p10 {q['p10']:.4f} "
              f"median {q['p50']:.4f} p90 {q['p90']:.4f} max {q['p100']:.4f}")
        print(f"     tau_abs_min={TAU_ABS_MIN}: {below}/{len(a)} frames below "
              f"({below / len(a):.2%}) -> {b['tau_abs_min_position']['reading']}")

    if len(res["bags"]) == 2 and all("weak_dir_info" in v for v in res["bags"].values()):
        r = res["bags"]["room02_2x2_O"]["weak_dir_info"]
        h = res["bags"]["hall01_inj43_filtered"]["weak_dir_info"]
        res["cross_bag"] = {
            "median_ratio_hall_over_room": h["median"] / max(r["median"], 1e-12),
            "max_ratio_hall_over_room": h["max"] / max(r["max"], 1e-12),
            "note": "if the two bags occupy different ranges, an absolute floor cannot serve both",
        }
        print(f"\n[] median ratio hall/room {res['cross_bag']['median_ratio_hall_over_room']:.2f}x, "
              f"max ratio {res['cross_bag']['max_ratio_hall_over_room']:.2f}x")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print(f"saved {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
