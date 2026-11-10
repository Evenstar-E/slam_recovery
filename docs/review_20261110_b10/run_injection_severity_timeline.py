#!/usr/bin/env python3
"""Injection severity over time, for hall_01, from the two bags themselves.

S3 asked whether the last ~6 s of the injection window is "self-consistent" or "missed": the NIS
exceedances stop at about onset+12 s but the window runs to onset+19.8 s. Answering that needs a
per-frame statement of how much contamination was actually present, and that is measurable
without any new host run -- the injected bag and the clean bag it was built from share their frame
stamps and their row layout.

Per frame: rows that differ from the clean frame (injected), how far they reach in the sensor frame,
and the frame stamp. A window whose contamination stops early will show the injected count going to
zero; a window that stays contaminated while the NIS goes quiet is a missed detection.

    python3 -B docs/review_20261110_b10/run_injection_severity_timeline.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _REPO, os.path.join(_REPO, "docs", "review_20261109_bbc3dcb")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_2x2_bags as B                       # noqa: E402
import verify_four_arm_independent as V          # noqa: E402

INJ = "/tmp/fastlivo/hall01_inj43.bag"
CLN = "/tmp/fastlivo/hall01_100_160.bag"
OUT = os.path.join(_HERE, "hall01_injection_severity.json")


def main() -> int:
    if not (os.path.exists(INJ) and os.path.exists(CLN)):
        print(json.dumps({"status": "BLOCKED", "reason": "one of the bags is missing",
                          "inj": os.path.exists(INJ), "cln": os.path.exists(CLN)}))
        return 2
    inj, cln = B._read(INJ), B._read(CLN)
    shared = sorted(set(inj) & set(cln))
    if not shared:
        print(json.dumps({"status": "BLOCKED", "reason": "no shared frame stamps"}))
        return 2
    print(f"[] shared frames {len(shared)} (inj {len(inj)}, clean {len(cln)})")

    per_frame = []
    for ns in shared:
        a_raw, step, dt = inj[ns]
        c_raw = cln[ns][0]
        if len(a_raw) != len(c_raw):
            per_frame.append({"ns": int(ns), "status": "ROW_COUNT_MISMATCH"})
            continue
        rows = np.frombuffer(a_raw, dtype=np.uint8).reshape(-1, step)
        crows = np.frombuffer(c_raw, dtype=np.uint8).reshape(-1, step)
        diff = (rows != crows).any(axis=1)
        a = np.frombuffer(a_raw, dtype=dt)
        pts = np.column_stack([a["x"], a["y"], a["z"]]).astype(np.float64)
        r = np.linalg.norm(pts[diff], axis=1) if diff.any() else np.zeros(0)
        per_frame.append({
            "ns": int(ns), "rows": int(len(rows)), "injected_rows": int(diff.sum()),
            "injected_fraction": float(diff.mean()),
            "injected_radius_min_m": float(r.min()) if len(r) else None,
            "injected_radius_median_m": float(np.median(r)) if len(r) else None,
            "injected_radius_max_m": float(r.max()) if len(r) else None,
        })

    differing = [f for f in per_frame if f.get("injected_rows")]
    if not differing:
        print(json.dumps({"status": "BLOCKED", "reason": "the two bags are byte-identical"}))
        return 2
    onset_ns = differing[0]["ns"]
    end_ns = differing[-1]["ns"]
    t0 = per_frame[0]["ns"]
    for f in per_frame:
        f["rel_onset_s"] = round((f["ns"] - onset_ns) * 1e-9, 3)
        f["rel_first_frame_s"] = round((f["ns"] - t0) * 1e-9, 3)

    # 1 s buckets relative to the onset
    buckets = {}
    for f in differing:
        b = int(np.floor(f["rel_onset_s"]))
        buckets.setdefault(b, []).append(f["injected_rows"])
    timeline = [{"second_from_onset": k, "frames": len(v),
                 "injected_rows_mean": float(np.mean(v)),
                 "injected_rows_min": int(min(v)), "injected_rows_max": int(max(v))}
                for k, v in sorted(buckets.items())]

    inside = [f for f in per_frame if onset_ns <= f["ns"] <= end_ns]
    trailing_zero = [f for f in inside if not f["injected_rows"]]
    payload = {
        "protocol": "per-frame contamination measured directly from the two bags",
        "inputs": {"injected": {"path": INJ, "sha256": V._sha_file(INJ)},
                   "clean": {"path": CLN, "sha256": V._sha_file(CLN)}},
        "window": {"onset_ns": onset_ns, "end_ns": end_ns,
                   "duration_s": round((end_ns - onset_ns) * 1e-9, 3),
                   "differing_frames": len(differing),
                   "frames_in_window": len(inside)},
        "trailing_frames_with_no_injection": {
            "n": len(trailing_zero),
            "rel_onset_s": [f["rel_onset_s"] for f in trailing_zero]},
        "timeline_per_second": timeline,
        "per_frame": per_frame,
        "notes": [
            "injected_rows counts rows that differ from the clean frame at the same stamp; a row "
            "that was injected and then filtered out of this bag would not appear here",
            "this says how much of the last seconds was contaminated, not whether the run should "
            "have flagged it",
        ],
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    print(f"[] window {payload['window']['duration_s']} s, {len(differing)} differing frames, "
          f"{len(trailing_zero)} window frames with no injection")
    for row in timeline:
        print(f"  +{row['second_from_onset']:3d}s frames={row['frames']:3d} "
              f"injected mean={row['injected_rows_mean']:8.1f} "
              f"min={row['injected_rows_min']:5d} max={row['injected_rows_max']:5d}")
    print(f"saved {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
