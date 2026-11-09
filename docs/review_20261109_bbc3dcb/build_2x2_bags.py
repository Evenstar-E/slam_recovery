#!/usr/bin/env python3
"""UNUSED PARALLEL IMPLEMENTATION -- do not score these bags against the host runs.

This builder writes `/tmp/fastlivo/room02_inj43_O|OF|OB|OFB.bag` and keeps every raw row outside
the window. The eight native runs consumed the different, equivalence-verified set
`/tmp/fastlivo/room02_2x2_*.bag` produced by `build_single_factor_bags.py`, whose outside-window
policy is the actual filtered rows. The two sets are not interchangeable; this file is kept as an
independent implementation record only.

Build the four single-factor in-window bags and the index-level audit, in one pass.

The previous hybrid builder matched rows by hash-set, which silently restores every duplicate row
and cannot preserve multiplicity. Everything here is by ORIGINAL ROW INDEX.

Inside the injection window, with `bg[i]` = "row i is byte-identical to the clean frame at the same
header ns" and `fk[i]` = the shipped filter's keep decision on that frame:

  O       keep = bg                  exact clean background retained
  O+F     keep = bg | (fk & ~bg)     O plus the injected rows the filter kept  (+1 265)
  O-B     keep = bg & fk             O minus the background rows the filter dropped (-23 607)
  O+F-B   keep = fk                  exactly the actual filter, for reference

Outside the window every bag keeps every row: the factor under test is the in-window policy, so
the healthy side is held identical across the four arms rather than varied.

    python3 -B docs/review_20261109_bbc3dcb/build_2x2_bags.py
"""

from __future__ import annotations

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
from slam_recovery.repair.point_mixture_repairer import (  # noqa: E402
    MixtureFilterConfig, filter_self_consistent_near_field_contaminants)

INJ = "/tmp/fastlivo/room02_inj43.bag"
CLN = "/tmp/fastlivo/room02_clean_60s.bag"
OUT = {"O": "/tmp/fastlivo/room02_inj43_O.bag",
       "O+F": "/tmp/fastlivo/room02_inj43_OF.bag",
       "O-B": "/tmp/fastlivo/room02_inj43_OB.bag",
       "O+F-B": "/tmp/fastlivo/room02_inj43_OFB.bag"}
AUDIT = os.path.join(_HERE, "room02_2x2_audit.json")
IDX_NPZ = "/tmp/room02_2x2_indices.npz"
MODES = ("O", "O+F", "O-B", "O+F-B")


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
    inj, cln = _read(INJ), _read(CLN)
    shared = sorted(set(inj) & set(cln))
    if len(shared) != len(inj):
        raise SystemExit(json.dumps({"status": "BLOCKED", "reason": "PARTIAL_COVERAGE"}))
    for ns in shared:
        if inj[ns][1] != cln[ns][1] or inj[ns][2] != cln[ns][2]:
            raise SystemExit(json.dumps({"status": "BLOCKED", "reason": "LAYOUT_MISMATCH",
                                         "ns": ns}))
        if len(inj[ns][0]) != len(cln[ns][0]):
            raise SystemExit(json.dumps({"status": "BLOCKED", "reason": "ROW_COUNT_MISMATCH",
                                         "ns": ns}))
    differing = [ns for ns in shared if inj[ns][0] != cln[ns][0]]
    onset, end = min(differing), max(differing)

    # independent window check: a frame outside [onset, end] that differs would break the premise
    outside_bad = [ns for ns in shared if not (onset <= ns <= end) and inj[ns][0] != cln[ns][0]]
    if outside_bad:
        raise SystemExit(json.dumps({"status": "BLOCKED", "reason": "DIFFERS_OUTSIDE_WINDOW",
                                     "count": len(outside_bad)}))

    from rosbags.rosbag1 import Writer
    writers = {m: Writer(p) for m, p in OUT.items()}
    for w in writers.values():
        w.open()
    cfg = MixtureFilterConfig()
    per_frame, idx_store, offs = [], [], {m: [0] for m in MODES}
    kept_counts = {m: 0 for m in MODES}
    mode_idx = {m: [] for m in MODES}

    try:
        with V.Reader(INJ) as r:
            conns = {m: {c.topic: writers[m].add_connection(c.topic, c.msgtype,
                                                            typestore=V.TYPESTORE)
                         for c in r.connections} for m in MODES}
            for conn, t, raw in r.messages():
                if conn.topic != V.SCAN_TOPIC:
                    for m in MODES:
                        writers[m].write(conns[m][conn.topic], t, raw)
                    continue
                mm = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
                step = int(mm.point_step)
                ns = int(mm.header.stamp.sec) * 10**9 + int(mm.header.stamp.nanosec)
                rows = np.asarray(mm.data, dtype=np.uint8).reshape(-1, step)
                crows = np.frombuffer(cln[ns][0], np.uint8).reshape(-1, step)
                bg = ~(rows != crows).any(axis=1)

                a = np.frombuffer(rows.tobytes(), dtype=inj[ns][2])
                pts = np.column_stack([a["x"], a["y"], a["z"], a["intensity"]]).astype(np.float64)
                fk, _ratio, _eig, _rep = filter_self_consistent_near_field_contaminants(pts, cfg)

                in_win = onset <= ns <= end
                masks = {
                    "O": bg,
                    "O+F": bg | (fk & ~bg),
                    "O-B": bg & fk,
                    "O+F-B": fk,
                }
                if not in_win:
                    masks = {m: np.ones(len(rows), dtype=bool) for m in MODES}

                for m in MODES:
                    keep = masks[m]
                    kept = rows[keep].tobytes()
                    mm.data = np.frombuffer(kept, dtype=np.uint8)
                    mm.width = int(keep.sum())
                    mm.height = 1
                    mm.row_step = step * mm.width
                    writers[m].write(conns[m][conn.topic], t,
                                     V.TYPESTORE.serialize_ros1(mm, conn.msgtype))
                    kept_counts[m] += int(keep.sum())
                    mode_idx[m].append(np.flatnonzero(keep).astype(np.int32))

                per_frame.append({
                    "ns": ns, "in_window": bool(in_win), "n": int(len(rows)),
                    "background": int(bg.sum()), "injected": int((~bg).sum()),
                    "filter_kept": int(fk.sum()),
                    "filter_kept_background": int((fk & bg).sum()),
                    "filter_kept_injected": int((fk & ~bg).sum()),
                    "filter_dropped_background": int((~fk & bg).sum()),
                    "filter_dropped_injected": int((~fk & ~bg).sum())})
    finally:
        for w in writers.values():
            w.close()

    np.savez(IDX_NPZ, **{f"{m}_idx": np.concatenate(mode_idx[m]) if mode_idx[m]
                         else np.zeros(0, np.int32) for m in MODES},
             **{f"{m}_counts": np.asarray([len(x) for x in mode_idx[m]], np.int32)
                for m in MODES},
             ns=np.asarray([f["ns"] for f in per_frame], np.int64))

    inw = [f for f in per_frame if f["in_window"]]
    outw = [f for f in per_frame if not f["in_window"]]
    bg_present = sum(f["background"] for f in inw)
    inj_present = sum(f["injected"] for f in inw)
    kept_bg = sum(f["filter_kept_background"] for f in inw)
    kept_inj = sum(f["filter_kept_injected"] for f in inw)
    dropped_bg = sum(f["filter_dropped_background"] for f in inw)
    dropped_inj = sum(f["filter_dropped_injected"] for f in inw)

    audit = {
        "status": "OK",
        "inputs": {"injected": INJ, "injected_sha256": V._sha_file(INJ),
                   "clean": CLN, "clean_sha256": V._sha_file(CLN),
                   "filter_config": "MixtureFilterConfig() shipped defaults"},
        "window": {"onset_ns": onset, "end_ns": end, "differing_frames": len(differing)},
        "index_sidecar": IDX_NPZ,
        "outside_window_policy": "every bag keeps every row outside the window, so the four "
                                 "arms differ only in the in-window policy",
        "in_window": {
            "frames": len(inw), "background_present": int(bg_present),
            "injected_present": int(inj_present),
            "filter_kept_background": int(kept_bg), "filter_kept_injected": int(kept_inj),
            "filter_dropped_background": int(dropped_bg),
            "filter_dropped_injected": int(dropped_inj),
            "false_negative_rate": kept_inj / max(inj_present, 1),
            "background_normalized_residual_rate": kept_inj / max(bg_present, 1),
            "false_positive_rate": dropped_bg / max(bg_present, 1)},
        "healthy": {
            "frames": len(outw),
            "background_present": int(sum(f["background"] for f in outw)),
            "filter_dropped_background": int(sum(f["filter_dropped_background"] for f in outw)),
            "filter_kept_injected": int(sum(f["filter_kept_injected"] for f in outw)),
            "false_positive_rate": (sum(f["filter_dropped_background"] for f in outw)
                                    / max(sum(f["background"] for f in outw), 1)),
        },
        "bags": {m: {"path": OUT[m], "sha256": V._sha_file(OUT[m]),
                     "points_kept": int(kept_counts[m]),
                     "in_window_kept_fraction": (sum(len(mode_idx[m][i]) for i, f in
                                                     enumerate(per_frame) if f["in_window"])
                                                 / max(sum(f["n"] for f in inw), 1))}
                 for m in MODES},
        "per_frame": per_frame,
    }
    with open(AUDIT, "w", encoding="utf-8") as fh:
        json.dump(audit, fh, indent=1)
    print(json.dumps({k: audit[k] for k in ("in_window", "healthy")}, indent=1))
    for m in MODES:
        print(m, audit["bags"][m]["points_kept"], audit["bags"][m]["sha256"][:16])


if __name__ == "__main__":
    main()
