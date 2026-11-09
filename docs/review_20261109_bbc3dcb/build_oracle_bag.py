#!/usr/bin/env python3
"""Build the exact-oracle-removal replay bag for room_02 (or an oracle/filter hybrid).

Inside the injection window the injector rewrote only some rows of each scan; every other row is
byte-identical to the clean frame at the same header nanosecond.  Keeping the identical rows and
dropping the rewritten ones is therefore an exact oracle removal -- no geometric model.

With --hybrid-with, the window keeps the ORACLE removal while the frames outside it adopt the given
bag's own decision.  That isolates the filter's healthy-region removals from its in-window ones.

Fail-closed: the build refuses to run unless the bags have the same point layout and row count in
every shared frame, and unless no frame outside the window differs.  It never falls back to the raw
scan.

    python3 -B docs/review_20261109_bbc3dcb/build_oracle_bag.py \
        --injected /tmp/fastlivo/room02_inj43.bag \
        --clean /tmp/fastlivo/room02_clean_60s.bag \
        --out /tmp/fastlivo/room02_inj43_oracle.bag
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import verify_four_arm_independent as V          # noqa: E402

REPORT = os.path.join(_HERE, "room02_oracle_bag_report.json")


def _row_hash(row):
    return hashlib.blake2b(bytes(row), digest_size=8).digest()


def _read(path):
    out = {}
    with V.Reader(path) as r:
        for conn, _t, raw in r.messages(
                connections=[c for c in r.connections if c.topic == V.SCAN_TOPIC]):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            ns = int(m.header.stamp.sec) * 10**9 + int(m.header.stamp.nanosec)
            out[ns] = (np.asarray(m.data, dtype=np.uint8).tobytes(), int(m.point_step),
                       V._cloud_dtype(m))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--injected", required=True)
    ap.add_argument("--clean", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hybrid-with", default=None)
    ap.add_argument("--mode", default="oracle",
                    choices=["oracle", "hybrid", "x_add_fn", "y_drop_fp"],
                    help="oracle: exact removal only; hybrid: oracle window + filter outside; "
                         "x_add_fn: oracle + the injected rows the filter missed (residual "
                         "contamination only); y_drop_fp: oracle + the background rows the filter "
                         "wrongly dropped (false removal only)")
    a = ap.parse_args()

    inj, cln = _read(a.injected), _read(a.clean)
    shared = sorted(set(inj) & set(cln))
    if len(shared) != len(inj):
        raise SystemExit(json.dumps({"status": "BLOCKED", "reason": "PARTIAL_COVERAGE",
                                     "injected": len(inj), "shared": len(shared)}))
    bad_layout, bad_rows = [], []
    for ns in shared:
        (ri, si, dti), (rc, sc, dtc) = inj[ns], cln[ns]
        if si != sc or dti != dtc:
            bad_layout.append(ns)
        elif len(ri) // si != len(rc) // sc:
            bad_rows.append(ns)
    if bad_layout or bad_rows:
        raise SystemExit(json.dumps({"status": "BLOCKED", "reason": "LAYOUT_OR_ORDER_MISMATCH",
                                     "layout_mismatch": len(bad_layout),
                                     "row_count_mismatch": len(bad_rows)}))
    differing = [ns for ns in shared if inj[ns][0] != cln[ns][0]]
    onset_ns, end_ns = min(differing), max(differing)
    outside_diff = [ns for ns in shared if (ns < onset_ns or ns > end_ns)
                    and inj[ns][0] != cln[ns][0]]
    if outside_diff:
        raise SystemExit(json.dumps({"status": "BLOCKED", "reason": "DIFFERS_OUTSIDE_WINDOW",
                                     "count": len(outside_diff)}))

    hyb = _read(a.hybrid_with) if a.hybrid_with else None
    if hyb is not None and set(hyb) != set(inj):
        raise SystemExit(json.dumps({"status": "BLOCKED", "reason": "HYBRID_BAG_MISMATCH"}))

    from rosbags.rosbag1 import Writer
    kept_total = dropped_total = 0
    per_frame = []
    w = Writer(a.out)
    w.open()
    try:
        with V.Reader(a.injected) as r:
            conns = {c.topic: w.add_connection(c.topic, c.msgtype, typestore=V.TYPESTORE)
                     for c in r.connections}
            for conn, t, raw in r.messages():
                if conn.topic != V.SCAN_TOPIC:
                    w.write(conns[conn.topic], t, raw)
                    continue
                m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
                buf = np.asarray(m.data, dtype=np.uint8)
                step = int(m.point_step)
                ns = int(m.header.stamp.sec) * 10**9 + int(m.header.stamp.nanosec)
                rows = buf.reshape(-1, step)
                clean_rows = np.frombuffer(cln[ns][0], dtype=np.uint8).reshape(-1, step)
                keep = ~(rows != clean_rows).any(axis=1)
                if hyb is not None:
                    filter_kept = {_row_hash(x) for x in
                                   np.frombuffer(hyb[ns][0], np.uint8).reshape(-1, step)}
                    in_win = onset_ns <= ns <= end_ns
                    if a.mode == "hybrid" and not in_win:
                        keep = np.asarray([_row_hash(x) in filter_kept for x in rows])
                    elif a.mode == "x_add_fn" and in_win:
                        is_injected = (rows != clean_rows).any(axis=1)
                        in_filter = np.asarray([_row_hash(x) in filter_kept for x in rows])
                        keep = keep | (is_injected & in_filter)
                    elif a.mode == "y_drop_fp" and in_win:
                        in_filter = np.asarray([_row_hash(x) in filter_kept for x in rows])
                        keep = keep & in_filter
                kept = rows[keep].tobytes()
                m.data = np.frombuffer(kept, dtype=np.uint8)
                m.width = int(keep.sum())
                m.height = 1
                m.row_step = step * m.width
                w.write(conns[conn.topic], t, V.TYPESTORE.serialize_ros1(m, conn.msgtype))
                kept_total += int(keep.sum())
                dropped_total += int(len(rows) - keep.sum())
                per_frame.append({"ns": ns, "n": int(len(rows)), "kept": int(keep.sum()),
                                  "in_window": bool(onset_ns <= ns <= end_ns)})
    finally:
        w.close()

    inw = [f for f in per_frame if f["in_window"]]
    outw = [f for f in per_frame if not f["in_window"]]
    rep = {"status": "OK", "input": a.injected, "input_sha256": V._sha_file(a.injected),
           "clean": a.clean, "clean_sha256": V._sha_file(a.clean),
           "hybrid_with": a.hybrid_with, "mode": a.mode,
           "output": a.out, "output_sha256": V._sha_file(a.out),
           "window": {"onset_ns": onset_ns, "end_ns": end_ns,
                      "differing_frames": len(differing)},
           "points_in": int(kept_total + dropped_total), "points_kept": int(kept_total),
           "removed": int(dropped_total),
           "frames": len(per_frame),
           "in_window": {"frames": len(inw),
                         "kept_fraction": sum(f["kept"] for f in inw)
                         / max(sum(f["n"] for f in inw), 1)},
           "outside_window": {"frames": len(outw),
                              "kept_fraction": sum(f["kept"] for f in outw)
                              / max(sum(f["n"] for f in outw), 1)},
           "per_frame": per_frame}
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    print(json.dumps({k: rep[k] for k in ("status", "points_in", "points_kept", "removed",
                                          "in_window", "outside_window")}, indent=1))


if __name__ == "__main__":
    main()
