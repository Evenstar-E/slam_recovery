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
AUDIT = os.path.join(_HERE, "room02_original_index_audit.json")

KINDS = ("stamp_mismatch", "missing_message", "extra_messages", "outside_mismatch",
         "combined_mismatch", "index_mismatch", "row_count", "metadata_mismatch",
         "empty_outside", "empty_window", "sidecar_order", "sidecar_dtype", "sidecar_bounds",
         "sidecar_missing_frame", "sidecar_hash_mismatch", "window_mismatch", "fatal")
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
    "sidecar_order": "a sidecar index array is not strictly increasing",
    "sidecar_dtype": "a sidecar array is not an integer array",
    "sidecar_bounds": "a sidecar index is negative or beyond the injected row count",
    "sidecar_missing_frame": "a sidecar frame has no scan in the filtered stream",
    "sidecar_hash_mismatch": "the loaded sidecar hash differs from the audit's recorded hash",
    "window_mismatch": "the audit's declared window and the sidecar frame set disagree",
    "extra_messages": "a stream has scan messages after the filtered stream ended",
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


def _array_problem(arr, n_rows: int):
    """Return the sidecar failure kind for one index array, or None.

    Pure, so the negative/out-of-bounds/unsorted/dtype cases can be tested without bags.
    """
    if not np.issubdtype(arr.dtype, np.integer):
        return "sidecar_dtype"
    if arr.size and (int(arr.min()) < 0 or int(arr.max()) >= n_rows):
        return "sidecar_bounds"
    if arr.size and not np.all(np.diff(arr.astype(np.int64)) > 0):
        return "sidecar_order"
    return None


def _extra_messages(iterator) -> bool:
    """True iff the stream has a message after the reference stream ended."""
    try:
        next(iterator)
        return True
    except StopIteration:
        return False


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as src:
        for chunk in iter(lambda: src.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if rosbag is None:
        raise SystemExit("run under the ROS python (/home/R26534/mm/ros/bin/python)")
    per_frame, n_in, n_out = [], 0, 0
    failures: list[dict] = []
    counts = {k: 0 for k in KINDS}

    def fail(kind: str, **kw):
        if kind not in counts:
            raise KeyError(f"unregistered failure kind {kind!r}")
        counts[kind] += 1
        failures.append({"kind": kind, "why": WHY[kind], **kw})

    side, bags, inj_bag, fil_bag = None, {}, None, None
    row_counts: dict[int, int] = {}
    try:
        audit = json.load(open(AUDIT, encoding="utf-8"))
        window = audit["window"]
        onset_ns, end_ns = int(window["onset_ns"]), int(window["end_ns"])
        if not window.get("source"):
            fail("window_mismatch", note="the audit declares no independent window source")
        side = np.load(SIDECAR)
        declared = (audit.get("index_sidecar") or {}).get("sha256")
        if declared != _sha256(SIDECAR):
            fail("sidecar_hash_mismatch", declared=declared, actual=_sha256(SIDECAR))

        bags = {a: rosbag.Bag(p, "r") for a, p in BAGS.items()}
        inj_bag = rosbag.Bag(INJ, "r")
        fil_bag = rosbag.Bag(FIL, "r")
        it = {a: b.read_messages(topics=[SCAN_TOPIC]) for a, b in bags.items()}
        it_inj = inj_bag.read_messages(topics=[SCAN_TOPIC])
        it_fil = fil_bag.read_messages(topics=[SCAN_TOPIC])

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
            inj_rows = _rows(inj_msg)
            row_counts[ns] = int(inj_rows.shape[0])
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
            # The window comes from the audit's independent declaration, never from the sidecar's
            # own key set; a disagreement is a failure in both directions.
            in_win = bool(onset_ns <= ns <= end_ns)
            has_key = f"k{ns}" in side.files
            if in_win != has_key:
                fail("window_mismatch", ns=ns, declared=in_win, sidecar=has_key)
            if in_win:
                if not has_key:
                    continue
                n_in += 1
                kept = np.asarray(side[f"k{ns}"])
                bg = np.asarray(side[f"b{ns}"])
                bad = False
                for name, arr in (("k", kept), ("b", bg)):
                    problem = _array_problem(arr, inj_rows.shape[0])
                    if problem is not None:
                        fail(problem, ns=ns, array=name)
                        bad = True
                kept = kept.astype(np.int64)
                bg = bg.astype(np.int64)
                arms = {"O": bg,
                        "O_plus_F": np.union1d(bg, kept),
                        "O_minus_B": np.intersect1d(bg, kept, assume_unique=True),
                        "O_plus_F_minus_B": kept}
                if not bad:
                    inj_meta = _meta(inj_msg)
                    step = inj_meta[3]
                    for a, idx in arms.items():
                        if got[a].shape[0] != idx.size:
                            fail("row_count", ns=ns, arm=a, got=int(got[a].shape[0]),
                                 want=int(idx.size))
                        elif not np.array_equal(got[a], inj_rows[idx]):
                            fail("index_mismatch", ns=ns, arm=a)
                        want_meta = (int(idx.size), 1, int(idx.size) * step, step, inj_meta[4])
                        if metas[a] != want_meta:
                            fail("metadata_mismatch", ns=ns, arm=a, got=metas[a],
                                 want=want_meta)
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

        # The filtered stream defines the end of the comparison. Every other stream must end with
        # it: an arm (or the injected bag) with a trailing scan would otherwise go unseen.
        if not counts["missing_message"] and not counts["fatal"]:
            for a, iterator in it.items():
                if _extra_messages(iterator):
                    fail("extra_messages", arm=a)
            if _extra_messages(it_inj):
                fail("extra_messages", source="injected")
        for key in side.files:
            if key.startswith(("k", "b")) and int(key[1:]) not in row_counts:
                fail("sidecar_missing_frame", ns=int(key[1:]), array=key[0])
    except Exception as exc:                     # noqa: BLE001 - receipt must survive any failure
        fail("fatal", error=repr(exc))
    finally:
        if inj_bag is not None:
            inj_bag.close()
        if fil_bag is not None:
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
        "frames_complete": (counts["stamp_mismatch"] == 0 and counts["missing_message"] == 0
                            and counts["extra_messages"] == 0),
        "sidecar_valid": (counts["sidecar_order"] == 0 and counts["sidecar_dtype"] == 0
                          and counts["sidecar_bounds"] == 0
                          and counts["sidecar_missing_frame"] == 0
                          and counts["sidecar_hash_mismatch"] == 0),
        "window_matches_sidecar": counts["window_mismatch"] == 0,
        "sidecar_order_ok": counts["sidecar_order"] == 0,
        "no_fatal": counts["fatal"] == 0,
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
    # Gate on the counters, not on a hand-maintained list of checks: a new failure kind that is
    # recorded but not yet wired into `checks` must still make the run fail.
    return 0 if not any(counts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
