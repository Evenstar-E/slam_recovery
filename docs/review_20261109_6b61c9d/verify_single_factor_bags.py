#!/usr/bin/env python3
"""Verify the four 2x2 bags against the original-index construction.

Checks required before any native run is interpreted (review dc714e9):

  1. Outside the window, every arm's LiDAR message is byte-identical to the filtered recording.
  2. Inside the window, each arm's rows equal the injected scan's rows at the sidecar indices.
  3. O+F-B is byte-identical to the filtered recording inside the window (the combined cell *is*
     the actual in-window condition, not a lookalike).
  4. O subset O+F, O-B subset O, O+F-B subset O+F hold row-for-row, and message metadata
     (width/height/row_step/is_dense/point_step) matches the reconstructed row count.

A check passes only when its failure counter is zero AND the population it ranges over is
non-empty: an empty window or an empty outside set is a failure, not a vacuous pass. Failures carry
a typed `kind`, never a message prefix. Every exit path writes the receipt.

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

KINDS = ("stamp_mismatch", "missing_message", "outside_mismatch", "combined_mismatch",
         "index_mismatch", "row_count", "metadata_mismatch", "empty_outside", "empty_window",
         "fatal")
WHY = {
    "stamp_mismatch": "stamp mismatch between bags",
    "missing_message": "a bag ended before the reference stream",
    "outside_mismatch": "outside window differs from the filtered scan",
    "combined_mismatch": "the combined cell differs from the actual filtered scan inside the window",
    "index_mismatch": "arm rows differ from the original indices",
    "row_count": "arm row count differs from the original indices",
    "metadata_mismatch": "message metadata disagrees with the reconstructed row set",
    "empty_outside": "no outside-window frame: equality would be vacuously true",
    "empty_window": "no in-window frame: equivalence would be vacuously true",
    "fatal": "verifier aborted; the exception is in the error field",
}


def _ns(msg) -> int:
    st = msg.header.stamp
    if hasattr(st, "secs"):
        return int(st.secs) * 10**9 + int(st.nsecs)
    return int(st.sec) * 10**9 + int(st.nanosec)


def _rows(msg) -> np.ndarray:
    return np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(-1, int(msg.point_step))


def _meta(msg):
    return (int(msg.width), int(msg.height), int(msg.row_step),
            int(msg.point_step), bool(msg.is_dense))


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
    failures: list[dict] = []
    counts = {k: 0 for k in KINDS}

    def fail(kind: str, **kw):
        if kind not in counts:
            raise KeyError(f"unregistered failure kind {kind!r}")
        counts[kind] += 1
        failures.append({"kind": kind, "why": WHY[kind], **kw})

    try:
        while True:
            try:
                _t, fil_msg, _bt = next(it_fil)
            except StopIteration:
                break
            ns = _ns(fil_msg)
            fil_rows = _rows(fil_msg)
            try:
                _ti, inj_msg, _bi = next(it_inj)   # advance on EVERY frame, window or not
            except StopIteration:
                fail("missing_message", ns=ns, source="injected")
                break
            if _ns(inj_msg) != ns:
                fail("stamp_mismatch", ns=ns, source="injected", got=_ns(inj_msg))
            got, metas = {}, {}
            missing = False
            for a in BAGS:
                try:
                    _ta, m, _b = next(it[a])
                except StopIteration:
                    fail("missing_message", ns=ns, source=a)
                    missing = True
                    break
                if _ns(m) != ns:
                    fail("stamp_mismatch", ns=ns, arm=a, got=_ns(m))
                got[a], metas[a] = _rows(m), _meta(m)
            if missing:
                break
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
                        fail("row_count", ns=ns, arm=a, got=int(got[a].shape[0]),
                             want=int(idx.size))
                    elif not np.array_equal(got[a], inj_rows[idx]):
                        fail("index_mismatch", ns=ns, arm=a)
                    width, height, row_step, step, _dense = metas[a]
                    if (width, height, row_step, step) != (idx.size, 1, idx.size * step, step):
                        fail("metadata_mismatch", ns=ns, arm=a, got=metas[a],
                             want=(int(idx.size), 1, int(idx.size) * step, step))
                if not np.array_equal(got["O_plus_F_minus_B"], fil_rows):
                    fail("combined_mismatch", ns=ns)
                per_frame.append({"ns": ns, "in_window": True,
                                  "rows": {a: int(got[a].shape[0]) for a in BAGS}})
            else:
                n_out += 1
                for a in BAGS:
                    if metas[a] != _meta(fil_msg):
                        fail("metadata_mismatch", ns=ns, arm=a, got=metas[a],
                             want=_meta(fil_msg))
                    if not np.array_equal(got[a], fil_rows):
                        fail("outside_mismatch", ns=ns, arm=a)
                per_frame.append({"ns": ns, "in_window": False,
                                  "rows": {a: int(got[a].shape[0]) for a in BAGS}})
    except Exception as exc:                     # noqa: BLE001 - receipt must survive any failure
        fail("fatal", error=repr(exc))
    finally:
        inj_bag.close()
        fil_bag.close()
        for b in bags.values():
            b.close()

    if n_out == 0:
        fail("empty_outside", note="no frame outside the window; the check would be vacuous")
    if n_in == 0:
        fail("empty_window", note="no frame inside the window; the check would be vacuous")
    checks = {
        "outside_all_equal_filtered": counts["outside_mismatch"] == 0
                                      and counts["metadata_mismatch"] == 0 and n_out > 0,
        "combined_equals_actual_in_window": counts["combined_mismatch"] == 0 and n_in > 0,
        "arms_match_original_indices": counts["index_mismatch"] == 0 and n_in > 0,
        "row_counts_match": counts["row_count"] == 0 and counts["metadata_mismatch"] == 0
                            and n_in > 0,
        "frames_complete": counts["stamp_mismatch"] == 0 and counts["missing_message"] == 0,
    }
    res = {"inputs": {"injected_sha256": _sha256(INJ), "filtered_sha256": _sha256(FIL),
                      "sidecar_sha256": _sha256(SIDECAR)},
           "bags": {a: {"path": p, "sha256": _sha256(p)} for a, p in BAGS.items()},
           "frames": {"total": len(per_frame), "in_window": n_in, "outside": n_out},
           "checks": checks,
           "failure_counts": counts,
           "failures": failures,
           "preregistration": {
               "declared_before_results": True,
               "declared_on": "2026-11-09",
               "repetitions_per_cell": 2,
               "failure_threshold_ate_m": 1.0,
               "cells": list(BAGS),
               "interaction_rule": "O+F-B fails in both repeats while O+F and O-B fail in neither",
               "outside_policy": "actual filtered rows in every cell",
           }}
    with open(RECEIPT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(checks, indent=1))
    print("failure counts:", {k: v for k, v in counts.items() if v})
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
