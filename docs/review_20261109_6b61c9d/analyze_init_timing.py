#!/usr/bin/env python3
"""Does the first-pose delay track the host's good/bad mode?

The 16 existing result bags already contain what the initialisation hypothesis needs: the first
`/aft_mapped_to_init` stamp relative to the first LiDAR scan of the same input. No host or binary
change is required. If the delay separates GOOD from BAD runs, initialisation timing is a direct
correlate; if it does not, the hypothesis is weakened.

Mode labels come from the archived results (bistability run: recorded mode; 2x2 run: the same
unsupported thresholds 0.10 / 0.50).

    python3 -B docs/review_20261109_6b61c9d/analyze_init_timing.py
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

BIST = os.path.join(_REPO, "docs", "review_20261109_bbc3dcb", "room02_bistability_results.json")
TWO = os.path.join(_REPO, "docs", "review_20261109_bbc3dcb", "room02_2x2_results.json")
RECEIPT = os.path.join(_HERE, "init_timing.json")
INPUT = {"O": "/tmp/fastlivo/room02_2x2_O.bag",
         "O+F": "/tmp/fastlivo/room02_2x2_O_plus_F.bag",
         "O-B": "/tmp/fastlivo/room02_2x2_O_minus_B.bag",
         "O+F-B": "/tmp/fastlivo/room02_2x2_O_plus_F_minus_B.bag"}
GOOD_MAX, BAD_MIN = 0.10, 0.50


def _first_scan_s(path):
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == V.SCAN_TOPIC]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            st = m.header.stamp
            return float(st.sec) + float(st.nanosec) * 1e-9
    return None


def _mode(u):
    if u is None:
        return None
    return "GOOD" if u < GOOD_MAX else ("BAD" if u > BAD_MIN else "UNCLEAR")


def main():
    bist = json.load(open(BIST, encoding="utf-8"))
    two = json.load(open(TWO, encoding="utf-8"))
    first_scan = {a: _first_scan_s(p) for a, p in INPUT.items()}
    rows = []
    for key, v in bist["new_runs"].items():
        if v.get("mode") not in ("GOOD", "BAD", "UNCLEAR"):
            continue
        arm = key.split("#")[0]
        path = f"/tmp/fastlivo/res_bist_{arm.replace('+','_plus_').replace('-','_minus_')}" \
               f"_r{key.split('#')[1]}.bag"
        rows.append((key, path, arm, v["mode"], v.get("unsupported_fraction")))
    for key, v in two["cells"].items():
        if v.get("status") != "OK":
            continue
        arm, rep = key.split("#")
        path = f"/tmp/fastlivo/res_2x2_{arm.replace('+','_plus_').replace('-','_minus_')}" \
               f"_r{rep}.bag"
        rows.append((key, path, arm, _mode(v.get("unsupported_fraction")),
                     v.get("unsupported_fraction")))

    out = {"good_max": GOOD_MAX, "bad_min": BAD_MIN, "runs": [], "by_mode": {}}
    for key, path, arm, mode, uns in rows:
        if not os.path.exists(path):
            out["runs"].append({"run": key, "status": "MISSING"})
            continue
        ts, xyz, _q = V.load_poses(path)
        delay = float(ts.min() - first_scan[arm])
        rec = {"run": key, "arm": arm, "mode": mode, "unsupported_fraction": uns,
               "first_pose_stamp_s": float(ts.min()),
               "first_scan_stamp_s": float(first_scan[arm]),
               "first_pose_delay_s": delay,
               "first_pose_xyz": [float(x) for x in xyz[0]]}
        out["runs"].append(rec)
        out["by_mode"].setdefault(mode, []).append(delay)
    for mode, vals in out["by_mode"].items():
        out["by_mode"][mode] = {"n": len(vals), "mean_delay_s": float(np.mean(vals)),
                                "min_delay_s": float(np.min(vals)),
                                "max_delay_s": float(np.max(vals))}
    with open(RECEIPT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    for mode, v in out["by_mode"].items():
        print(mode, v)
    print("per-run delays:")
    for r in out["runs"]:
        if "first_pose_delay_s" not in r:
            continue
        print(f"  {r['run']:12s} {str(r['mode']):8s} {r['first_pose_delay_s']:.3f}")


if __name__ == "__main__":
    main()
