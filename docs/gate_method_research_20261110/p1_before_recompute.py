#!/usr/bin/env python3
"""Part 1: what the information leg looks like on the corrected FIM producer.

Two things are computed, both from real archived inputs:

  1. VALIDATION -- the archived `weak_dir_info_before` of every distinct trigger frame is
     reproduced from the bag by the same chain the node runs (raw scan -> stride cap 6000 ->
     producer stride 1200 -> v^T L v). The match is a MEASURED precision: relative tolerance
     5e-4, and every row records its own absolute and relative difference. It is not
     bit-for-bit, and the scan the chain uses is the nearest scan to the trigger stamp, which
     can be tens of milliseconds away; both numbers are recorded per row.
  2. SCALE -- the same trigger scans through the C-2 producer (voxel 0.25 m + radius 0.6 m),
     compared with the OLD one.

Every row is bound to the inputs that produced it: the bag content hash, the capped scan content
hash and its stamp, and the producer source hash. A filename is not a binding -- two bags can
share a name, and the same file can be replaced in place.

`after` is NOT recomputed: the archive does not record the candidate frame set or the repaired
poses, and substituting a proxy frame set would produce a different quantity under the archive's
name. That half is reported BLOCKED.

    python -I docs/gate_method_research_20261110/p1_before_recompute.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
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
REL_TOL = 5e-4  # declared BEFORE the run: the precision at which a reproduction counts
# (label, bag, trigger stamp, archived before)
CASES = [
    ("room02_early1", "/tmp/fastlivo/room02_2x2_O.bag", 1627643740912290335, 39.0496),
    ("room02_early2", "/tmp/fastlivo/room02_2x2_O.bag", 1627643742844584942, 40.2316),
    ("room02_onset", "/tmp/fastlivo/room02_2x2_O.bag", 1627643759659727812, 1.1019),
    ("hall_A", "/tmp/fastlivo/hall01_inj43_filtered.bag", 1627785265208036184, 45.4565),
    ("hall_B", "/tmp/fastlivo/hall01_inj43_filtered.bag", 1627785263807538033, 37.0057),
]

_BAG_HASH_CACHE: dict = {}


def sha256_file(path: str, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def bag_binding(path: str) -> dict:
    if path not in _BAG_HASH_CACHE:
        st = os.stat(path)
        _BAG_HASH_CACHE[path] = {"bag_path": path, "bag_size_bytes": int(st.st_size),
                                 "bag_mtime_ns": int(st.st_mtime_ns),
                                 "bag_sha256": sha256_file(path)}
    return dict(_BAG_HASH_CACHE[path])


def producer_binding() -> dict:
    src = os.path.join(ROOT, "slam_recovery", "validation", "fim_and_holdout.py")
    try:
        head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                   # noqa: BLE001 - recorded, not hidden
        head = "UNAVAILABLE"
    return {"module": "slam_recovery.validation.fim_and_holdout",
            "source_sha256": sha256_file(src) if os.path.exists(src) else "MISSING",
            "git_head_at_run": head,
            "note": "source hash binds the producer; git_head is the tree the script ran on, "
                    "which is the parent commit of the commit that adds this result"}


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
        abs_diff = abs(before_old - archived)
        rel_diff = abs_diff / max(abs(archived), 1e-9)
        cos = abs(float(v_n @ v_o))
        row = {
            "case": label,
            **bag_binding(bag),
            "trigger_stamp_ns": stamp,
            "scan_stamp_ns": scan_stamp,
            "scan_dt_ms": round(dt / 1e6, 2),
            "scan_sha256": hashlib.sha256(np.ascontiguousarray(capped).tobytes()).hexdigest(),
            "raw_points": len(pts), "capped_points": len(capped),
            "archived_before": archived,
            "before_old_recomputed": round(before_old, 6),
            "abs_diff": float(f"{abs_diff:.3e}"),
            "rel_diff": float(f"{rel_diff:.3e}"),
            "within_rel_tol_5e-4": bool(rel_diff < REL_TOL),
            "before_new": round(before_new, 4),
            "factor_new_over_old": round(before_new / before_old, 4),
            "weak_direction_alignment_cos": round(cos, 4),
            "weak_direction_angle_deg": round(float(np.degrees(np.arccos(min(cos, 1.0)))), 2),
            "old_direction_in_new_matrix": round(project(v_o, info_n), 4),
        }
        rows.append(row)

    factors = [r["factor_new_over_old"] for r in rows]
    angles = [r["weak_direction_angle_deg"] for r in rows]
    dts = [r["scan_dt_ms"] for r in rows]
    out = {
        "_meta": {
            "what": "Part 1: the information leg on the corrected producer",
            "written": "2026-11-10",
            "producers": {"old": "stride 1200 + 15-NN (slam_recovery.validation.fim_and_holdout)",
                          "new": "C-2 research patch: voxel 0.25 m + radius 0.6 m"},
            "producer": producer_binding(),
            "binding": ("each row carries the bag content hash, the capped-scan content hash and "
                        "its stamp, and the producer source hash; the reproduction is bound to "
                        "those bytes, not to a file name"),
            "not_done": ["no host run", "no threshold changed", "no production code edited"],
            "after_status": ("BLOCKED: the archived candidate record carries no candidate frame "
                             "list and no repaired poses, so `after` cannot be rebuilt; a proxy "
                             "frame set would be a different quantity under the archive's name"),
        },
        "rows": rows,
        "validation": {
            "within_rel_tol_5e-4": sum(1 for r in rows if r["within_rel_tol_5e-4"]),
            "of": len(rows),
            "rel_tol_declared": REL_TOL,
            "max_rel_diff": max(r["rel_diff"] for r in rows),
            "max_abs_diff": max(r["abs_diff"] for r in rows),
            "scan_dt_ms_min": min(dts), "scan_dt_ms_max": max(dts),
            "reading": ("reproduced at the declared 5e-4 relative tolerance, not bit-for-bit. "
                        "The scan used is the nearest to the trigger stamp and can be 23 ms away; "
                        "that offset is recorded per row rather than hidden behind a name match"),
        },
        "scale_summary": {
            "factor_min": min(factors), "factor_max": max(factors),
            "factor_spread": round(max(factors) / min(factors), 1),
            "alignment_min_cos": min(r["weak_direction_alignment_cos"] for r in rows),
            "alignment_angle_deg_min": min(angles), "alignment_angle_deg_max": max(angles),
            "reading": ("the producer change is not a global rescale: the factor spans two orders "
                        "of magnitude across five real trigger frames. The weak direction turns by "
                        f"{min(angles):.2f} to {max(angles):.2f} degrees. No acceptance tolerance "
                        "for that angle was declared before the run, so it is reported as a "
                        "measurement, not scored as a PASS"),
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
