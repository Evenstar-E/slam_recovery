#!/usr/bin/env python3
"""Build the four single-factor 2x2 bags from original row indices.

Base is the injected recording. Inside the injection window only the LiDAR rows change; outside the
window every arm keeps the actual filtered rows, so the arms differ in exactly one factor each:

    O      = background rows only            (exact clean background retained)
    O+F    = O + the 1,265 kept injected rows
    O-B    = O - the 23,607 background rows the filter dropped (= kept background)
    O+F-B  = the actual filtered rows        (both changes)

IMU and camera are copied unchanged from the filtered recording, which is byte-identical to the
injected recording on those topics.

    /home/R26534/mm/ros/bin/python -B docs/review_20261109_6b61c9d/build_single_factor_bags.py
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys

import numpy as np

try:
    import rosbag                                        # noqa: E402
except ImportError:                                      # system python has no rosbag
    rosbag = None

_HERE = os.path.dirname(os.path.abspath(__file__))
SCAN_TOPIC = "/velodyne_points"
INJ = "/tmp/fastlivo/room02_inj43.bag"
FIL = "/tmp/fastlivo/room02_inj43_filtered.bag"
SIDECAR = "/tmp/fastlivo/room02_original_index_sidecar.npz"
OUT_DIR = "/tmp/fastlivo"
RESULTS = os.path.join(_HERE, "single_factor_bags.json")

ARMS = ("O", "O_plus_F", "O_minus_B", "O_plus_F_minus_B")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as src:
        for chunk in iter(lambda: src.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ns(msg) -> int:
    st = msg.header.stamp
    if hasattr(st, "secs"):          # ROS1 genpy Time
        return int(st.secs) * 10**9 + int(st.nsecs)
    return int(st.sec) * 10**9 + int(st.nanosec)


def _rows(msg):
    step = int(msg.point_step)
    return np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(-1, step)


def _with_rows(msg, row_idx: np.ndarray):
    rows = _rows(msg)[row_idx]
    out = copy.deepcopy(msg)     # never mutate the shared source message: the next arm needs it
    out.data = np.ascontiguousarray(rows, dtype=np.uint8).tobytes()
    out.width = int(row_idx.size)
    out.height = 1
    out.row_step = int(row_idx.size) * int(msg.point_step)
    out.is_dense = msg.is_dense
    return out


def _arm_indices(kept: np.ndarray, bg: np.ndarray):
    bg_kept = np.intersect1d(bg, kept, assume_unique=True)
    kept_only = np.setdiff1d(kept, bg, assume_unique=True)
    return {
        "O": bg,
        "O_plus_F": np.union1d(bg, kept),
        "O_minus_B": bg_kept,
        "O_plus_F_minus_B": kept,
    }, {"bg": int(bg.size), "kept": int(kept.size), "kept_injected": int(kept_only.size)}


def _expected_totals() -> dict:
    """Totals implied by the original-index audit, for a post-build identity check."""
    audit = os.path.join(_HERE, "room02_original_index_audit.json")
    if not os.path.exists(audit):
        return {}
    with open(audit, encoding="utf-8") as fh:
        w = json.load(fh)["in_window"]
    return {"O": w["background_present"],
            "O_plus_F": w["background_present"] + w["kept_injected"],
            "O_minus_B": w["kept_background"],
            "O_plus_F_minus_B": w["kept_background"] + w["kept_injected"]}


def main():
    if rosbag is None:
        raise SystemExit("run under the ROS python (/home/R26534/mm/ros/bin/python)")
    side = np.load(SIDECAR)
    writers = {a: rosbag.Bag(os.path.join(OUT_DIR, f"room02_2x2_{a}.bag"), "w") for a in ARMS}
    counts = {a: {"cloud": 0, "in_window": 0, "rows_by_frame": []} for a in ARMS}
    try:
        inj_bag = rosbag.Bag(INJ, "r")
        inj_clouds = inj_bag.read_messages(topics=[SCAN_TOPIC])
        fil_bag = rosbag.Bag(FIL, "r")
        for topic, msg, t in fil_bag.read_messages():
            if topic != SCAN_TOPIC:
                for a in ARMS:
                    writers[a].write(topic, msg, t)
                continue
            _it, inj_msg, _t = next(inj_clouds)
            if _ns(inj_msg) != _ns(msg):
                raise SystemExit(f"cloud stamps diverge: {_ns(inj_msg)} {_ns(msg)}")
            key = str(_ns(msg))
            if f"k{key}" not in side.files:
                # outside the window: every arm keeps the actual filtered rows
                for a in ARMS:
                    writers[a].write(topic, msg, t)
                    counts[a]["cloud"] += 1
                continue
            idx, _chk = _arm_indices(np.asarray(side[f"k{key}"]), np.asarray(side[f"b{key}"]))
            for a in ARMS:
                writers[a].write(topic, _with_rows(inj_msg, idx[a]), t)
                counts[a]["cloud"] += 1
                counts[a]["in_window"] += 1
                counts[a]["rows_by_frame"].append(int(idx[a].size))
        inj_bag.close()
        fil_bag.close()
    finally:
        for b in writers.values():
            b.close()

    res = {"inputs": {"injected": INJ, "injected_sha256": _sha256(INJ),
                      "filtered": FIL, "filtered_sha256": _sha256(FIL),
                      "index_sidecar": SIDECAR, "index_sidecar_sha256": _sha256(SIDECAR)},
           "outside_window_policy": "actual filtered rows in every arm",
           "expected_in_window_rows": _expected_totals(),
           "arms": {}}
    for a in ARMS:
        p = os.path.join(OUT_DIR, f"room02_2x2_{a}.bag")
        rows = counts[a]["rows_by_frame"]
        res["arms"][a] = {"path": p, "sha256": _sha256(p), "bytes": os.path.getsize(p),
                          "cloud_messages": counts[a]["cloud"],
                          "in_window_frames": counts[a]["in_window"],
                          "in_window_rows_total": int(sum(rows)),
                          "in_window_rows_min": int(min(rows)) if rows else None,
                          "in_window_rows_max": int(max(rows)) if rows else None}
    mismatch = {a: (sum(counts[a]["rows_by_frame"]), res["expected_in_window_rows"].get(a))
                for a in ARMS
                if res["expected_in_window_rows"] and
                sum(counts[a]["rows_by_frame"]) != res["expected_in_window_rows"][a]}
    if mismatch:
        raise SystemExit(f"arm totals disagree with the index audit: {mismatch}")
    with open(RESULTS, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res["arms"], indent=1))


if __name__ == "__main__":
    main()
