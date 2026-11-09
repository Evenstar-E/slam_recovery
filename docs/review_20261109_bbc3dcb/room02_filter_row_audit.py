#!/usr/bin/env python3
"""What exactly does the shipped filter keep and drop, row by row?

E_oracle and E_actual differ only in the removal, and they land on opposite sides of the map
quality, so the removal itself has to be characterised.  Rows are compared as bytes against the
clean frame at the same header nanosecond:

  kept   and in clean   -> background kept (good)
  kept   and not clean  -> injected row retained  (FALSE NEGATIVE: fake geometry left in)
  dropped and in clean  -> background removed     (FALSE POSITIVE: real geometry thrown away)
  dropped and not clean -> injected row removed   (good)

    python3 -B docs/review_20261109_bbc3dcb/room02_filter_row_audit.py
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

INJ = "/tmp/fastlivo/room02_inj43.bag"
CLN = "/tmp/fastlivo/room02_clean_60s.bag"
FIL = "/tmp/fastlivo/room02_inj43_filtered.bag"
RESULTS = os.path.join(_HERE, "room02_filter_row_audit.json")


def _rows(path):
    out = {}
    with V.Reader(path) as r:
        for conn, _t, raw in r.messages(
                connections=[c for c in r.connections if c.topic == V.SCAN_TOPIC]):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            ns = int(m.header.stamp.sec) * 10**9 + int(m.header.stamp.nanosec)
            step = int(m.point_step)
            rows = np.asarray(m.data, dtype=np.uint8).reshape(-1, step)
            out[ns] = [hashlib.blake2b(bytes(x), digest_size=8).digest() for x in rows]
    return out


def main():
    inj, cln, fil = _rows(INJ), _rows(CLN), _rows(FIL)
    onset, end = None, None
    differing = [ns for ns in sorted(set(inj) & set(cln)) if inj[ns] != cln[ns]]
    onset, end = min(differing), max(differing)

    frames = []
    for ns in sorted(set(inj) & set(fil)):
        inw = onset <= ns <= end
        kept = set(fil[ns])
        clean = set(cln[ns]) if ns in cln else set()
        inj_rows = set(inj[ns])
        frames.append({
            "ns": ns, "in_window": bool(inw), "n_raw": len(inj_rows), "n_kept": len(fil[ns]),
            "kept_background": len(kept & clean),
            "kept_injected": len(kept - clean),
            # background PRESENT in this scan = rows that survived the injection untouched.
            # Counting clean-minus-kept instead would score rows the injector overwrote as
            # "dropped by the filter", which is how the first version of this audit invented an
            # 88 % false-positive rate inside the window.
            "background_present": len(inj_rows & clean),
            "dropped_background": len((inj_rows & clean) - kept),
            "dropped_injected": len((inj_rows - clean) - kept),
        })

    def _agg(sel):
        n = sum(f["background_present"] for f in sel)
        return {"frames": len(sel), "background_present": int(n),
                "kept_background": int(sum(f["kept_background"] for f in sel)),
                "kept_injected": int(sum(f["kept_injected"] for f in sel)),
                "dropped_background": int(sum(f["dropped_background"] for f in sel)),
                "dropped_injected": int(sum(f["dropped_injected"] for f in sel)),
                "false_negative_rate": (sum(f["kept_injected"] for f in sel) / n) if n else None,
                "false_positive_rate": (sum(f["dropped_background"] for f in sel) / n)
                if n else None,
                "rows_raw": int(sum(f["n_raw"] for f in sel)),
                "background_present": int(n)}

    res = {
        "inputs": {"injected": INJ, "injected_sha256": V._sha_file(INJ),
                   "clean": CLN, "clean_sha256": V._sha_file(CLN),
                   "filtered": FIL, "filtered_sha256": V._sha_file(FIL)},
        "window": {"onset_ns": onset, "end_ns": end},
        "in_window": _agg([f for f in frames if f["in_window"]]),
        "healthy": _agg([f for f in frames if not f["in_window"]]),
        "per_frame": frames,
        "reading": "kept_injected is the false-negative count: injected geometry that survives the "
                   "filter. Those rows are mutually consistent on the sheet, so a small number of "
                   "them can still steer registration.",
    }
    with open(RESULTS, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps({k: res[k] for k in ("in_window", "healthy")}, indent=1))


if __name__ == "__main__":
    main()
