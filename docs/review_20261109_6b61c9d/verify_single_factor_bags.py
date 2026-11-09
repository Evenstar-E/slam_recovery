#!/usr/bin/env python3
"""Verify the four 2x2 bags against the original-index construction.

Checks required before any native run is interpreted (review dc714e9):

  1. Outside the window, every arm's LiDAR message is byte-identical to the filtered recording.
  2. Inside the window, each arm's rows equal the injected scan's rows at the sidecar indices.
  3. O+F-B is byte-identical to the filtered recording inside the window (the combined cell *is*
     the actual in-window condition, not a lookalike).
  4. O subset O+F, O-B subset O, O+F-B subset O+F hold row-for-row.

    /home/R26534/mm/ros/bin/python -B docs/review_20261109_6b61c9d/verify_single_factor_bags.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np

try:
    import rosbag
except ImportError:
    rosbag = None

_HERE = os.path.dirname(os.path.abspath(__file__))
SCAN_TOPIC = "/velodyne_points"
INJ = "/tmp/fastlivo/room02_inj43.bag"
FIL = "/tmp/fastlivo/room02_inj43_filtered.bag"
SIDECAR = "/tmp/fastlivo/room02_original_index_sidecar.npz"
BAGS = {a: f"/tmp/fastlivo/room02_2x2_{a}.bag"
        for a in ("O", "O_plus_F", "O_minus_B", "O_plus_F_minus_B")}
RECEIPT = os.path.join(_HERE, "single_factor_bags_verified.json")


def _ns(msg) -> int:
    st = msg.header.stamp
    if hasattr(st, "secs"):
        return int(st.secs) * 10**9 + int(st.nsecs)
    return int(st.sec) * 10**9 + int(st.nanosec)


def _rows(msg) -> np.ndarray:
    return np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(-1, int(msg.point_step))


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as src:
        for chunk in iter(lambda: src.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if rosbag is None:
        raise SystemExit("run under the ROS python (/home/R26534/mm/ros/bin/python)")
    side = np.load(SIDECAR)
    bags = {a: rosbag.Bag(p, "r") for a, p in BAGS.items()}
    inj_bag = rosbag.Bag(INJ, "r")
    fil_bag = rosbag.Bag(FIL, "r")
    it = {a: b.read_messages(topics=[SCAN_TOPIC]) for a, b in bags.items()}
    it_inj = inj_bag.read_messages(topics=[SCAN_TOPIC])
    it_fil = fil_bag.read_messages(topics=[SCAN_TOPIC])

    per_frame, n_in, n_out = [], 0, 0
    failures = []
    try:
        for _fi in range(10**9):
            try:
                _t, fil_msg, _bt = next(it_fil)
            except StopIteration:
                break
            ns = _ns(fil_msg)
            fil_rows = _rows(fil_msg)
            _ti, inj_msg, _bi = next(it_inj)      # advance on EVERY frame, not only window frames
            if _ns(inj_msg) != ns:
                failures.append({"ns": ns, "why": "injected stamp mismatch"})
            got = {}
            for a in BAGS:
                _ta, m, _b = next(it[a])
                if _ns(m) != ns:
                    failures.append({"ns": ns, "arm": a, "why": "stamp mismatch"})
                got[a] = _rows(m)
            if f"k{ns}" in side.files:
                n_in += 1
                inj_rows = _rows(inj_msg)
                kept = np.asarray(side[f"k{ns}"], dtype=np.int64)
                bg = np.asarray(side[f"b{ns}"], dtype=np.int64)
                arms = {"O": bg,
                        "O_plus_F": np.union1d(bg, kept),
                        "O_minus_B": np.intersect1d(bg, kept, assume_unique=True),
                        "O_plus_F_minus_B": kept}
                for a, idx in arms.items():
                    if got[a].shape[0] != idx.size:
                        failures.append({"ns": ns, "arm": a, "why": "row count",
                                         "got": int(got[a].shape[0]), "want": int(idx.size)})
                    elif not np.array_equal(got[a], inj_rows[idx]):
                        failures.append({"ns": ns, "arm": a, "why": "rows differ from indices"})
                if not np.array_equal(got["O_plus_F_minus_B"], fil_rows):
                    failures.append({"ns": ns, "arm": "O_plus_F_minus_B",
                                     "why": "combined cell differs from actual filtered scan"})
                per_frame.append({"ns": ns, "in_window": True,
                                  "rows": {a: int(got[a].shape[0]) for a in BAGS}})
            else:
                n_out += 1
                for a in BAGS:
                    if not np.array_equal(got[a], fil_rows):
                        failures.append({"ns": ns, "arm": a,
                                         "why": "outside window differs from filtered scan"})
                per_frame.append({"ns": ns, "in_window": False,
                                  "rows": {a: int(got[a].shape[0]) for a in BAGS}})
    finally:
        inj_bag.close()
        fil_bag.close()
        for b in bags.values():
            b.close()

    res = {"inputs": {"injected_sha256": _sha256(INJ), "filtered_sha256": _sha256(FIL),
                      "sidecar_sha256": _sha256(SIDECAR)},
           "bags": {a: {"path": p, "sha256": _sha256(p)} for a, p in BAGS.items()},
           "frames": {"total": len(per_frame), "in_window": n_in, "outside": n_out},
           "checks": {"outside_all_equal_filtered": not any(
                          f["why"].startswith("outside") for f in failures),
                      "combined_equals_actual_in_window": not any(
                          "combined cell" in f["why"] for f in failures),
                      "arms_match_original_indices": not any(
                          f["why"] == "rows differ from indices" for f in failures),
                      "row_counts_match": not any(
                          f["why"] == "row count" for f in failures)},
           "failures": failures}
    with open(RECEIPT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res["checks"], indent=1))
    print("failures:", len(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
