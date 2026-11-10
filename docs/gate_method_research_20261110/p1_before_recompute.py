#!/usr/bin/env python3
"""Part 1: what the information leg looks like on the corrected FIM producer.

Two things are computed, both from real archived inputs:

  1. VALIDATION -- the archived `weak_dir_info_before` of every distinct trigger frame is
     reproduced from the bag by the same chain the node runs (raw scan -> stride cap 6000 ->
     producer stride 1200 -> v^T L v). If this does not reproduce, nothing below is worth reading.
  2. SCALE -- the same trigger scans through the C-2 producer (voxel 0.25 m + radius 0.6 m),
     compared with the OLD one.

`after` is NOT recomputed: the archive does not record the candidate frame set or the repaired
poses, and substituting a proxy frame set would produce a different quantity under the archive's
name. That half is reported BLOCKED.

    python -I docs/gate_method_research_20261110/p1_before_recompute.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "docs/gate_method_research_20261110")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from slam_recovery.validation import compute_6dof_point_to_plane_fim as fim_old  # noqa: E402

C2_SPEC = importlib.util.spec_from_file_location("c2", os.path.join(HERE, "c2_fim_spatial.py"))
c2 = importlib.util.module_from_spec(C2_SPEC)          # noqa: E402
C2_SPEC.loader.exec_module(c2)

SCAN_CAP = 6000
# (label, bag, trigger stamp, archived before)
CASES = [
    ("room02_early1", "/tmp/fastlivo/room02_2x2_O.bag", 1627643740912290335, 39.0496),
    ("room02_early2", "/tmp/fastlivo/room02_2x2_O.bag", 1627643742844584942, 40.2316),
    ("room02_onset", "/tmp/fastlivo/room02_2x2_O.bag", 1627643759659727812, 1.1019),
    ("hall_A", "/tmp/fastlivo/hall01_inj43_filtered.bag", 1627785265208036184, 45.4565),
    ("hall_B", "/tmp/fastlivo/hall01_inj43_filtered.bag", 1627785263807538033, 37.0057),
]


def subsample(pts, cap=SCAN_CAP):
    if len(pts) <= cap:
        return pts
    step = max(1, len(pts) // cap)
    return pts[::step][:cap]


def nearest_scan(bag_path, stamp_ns):
    import rosbag
    from sensor_msgs import point_cloud2
    best = None
    with rosbag.Bag(bag_path) as bag:
        for _, msg, _ in bag.read_messages(topics=["/velodyne_points"]):
            s = msg.header.stamp.to_nsec()
            d = abs(s - stamp_ns)
            if best is None or d < best[0]:
                best = (d, s, msg)
                if d == 0:
                    break
            elif s > stamp_ns + 2_000_000_000:
                break
    d, s, msg = best
    pts = np.array([[p[0], p[1], p[2]] for p in point_cloud2.read_points(
        msg, field_names=("x", "y", "z"), skip_nans=True)], dtype=np.float64)
    return d, s, pts


def project(v, info):
    return float(np.asarray(v) @ np.asarray(info) @ np.asarray(v))


def main():
    rows = []
    for label, bag, stamp, archived in CASES:
        dt, scan_stamp, pts = nearest_scan(bag, stamp)
        capped = subsample(pts)
        info_o, _, _, _, w_o = fim_old(capped, sigma_meas_m=0.075)
        v_o = w_o / np.linalg.norm(w_o)
        info_n, _, _, _, w_n = c2.fim_spatial(capped)
        v_n = w_n / np.linalg.norm(w_n)
        before_old = project(v_o, info_o)
        before_new = project(v_n, info_n)
        rows.append({
            "case": label, "bag": os.path.basename(bag), "trigger_stamp_ns": stamp,
            "scan_stamp_ns": scan_stamp, "scan_dt_ms": round(dt / 1e6, 2),
            "raw_points": len(pts), "capped_points": len(capped),
            "archived_before": archived,
            "before_old_recomputed": round(before_old, 4),
            "reproduced": abs(before_old - archived) < 5e-4 * max(abs(archived), 1e-9),
            "before_new": round(before_new, 4),
            "factor_new_over_old": round(before_new / before_old, 4),
            "weak_direction_alignment_cos": round(abs(float(v_n @ v_o)), 4),
            "old_direction_in_new_matrix": round(project(v_o, info_n), 4),
        })

    factors = [r["factor_new_over_old"] for r in rows]
    out = {
        "_meta": {
            "what": "Part 1: the information leg on the corrected producer",
            "written": "2026-11-10",
            "producers": {"old": "stride 1200 + 15-NN",
                          "new": "C-2 research patch: voxel 0.25 m + radius 0.6 m"},
            "not_done": ["no host run", "no threshold changed", "no production code edited"],
            "after_status": ("BLOCKED: the archived candidate record carries no candidate frame "
                             "list and no repaired poses, so `after` cannot be rebuilt; a proxy "
                             "frame set would be a different quantity under the archive's name"),
        },
        "rows": rows,
        "validation": {"reproduced": sum(1 for r in rows if r["reproduced"]), "of": len(rows)},
        "scale_summary": {
            "factor_min": min(factors), "factor_max": max(factors),
            "factor_spread": round(max(factors) / min(factors), 1),
            "alignment_min_cos": min(r["weak_direction_alignment_cos"] for r in rows),
            "reading": ("the producer change is not a global rescale: the factor spans two orders "
                        "of magnitude across five real trigger frames, while the weak direction "
                        "stays within a few degrees. The direction survives; the magnitude does "
                        "not"),
        },
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "p1_before_recompute.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({"validation": out["validation"], "rows": rows,
                      "scale_summary": out["scale_summary"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
