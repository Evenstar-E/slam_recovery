#!/usr/bin/env python3
"""Row accounting by original index, not by hash set.

The 0c2e4206 review rejected two things in the first audit:

  * `set(row hash)` collapses duplicate rows, so multiplicities are lost; and
  * `false_negative_rate` divided by the background population (1,186,220) instead of the
    injected population (kept_injected + dropped_injected = 9,073,943).

This script rebuilds the accounting with **original row indices**. It first proves that the
filtered scan's rows are an in-order subsequence of the injected scan's rows at the same header
nanosecond; that holds for every window frame checked here, so each kept row has a unique original
index. Classification is then index-based:

  background present  : injected rows whose bytes are accounted for by the clean frame, matched as
                        a multiset (each clean row can justify one injected row)
  kept                : the filtered scan's rows, mapped back to original indices
  kept background     : kept AND background present
  kept injected       : kept AND not background present        (false negative: fake left in)
  dropped background  : background present AND not kept        (false positive: real removed)
  dropped injected    : injected rows neither background nor kept

Outputs the counts, both normalizations and, for the window frames, an index sidecar that the
single-factor 2x2 consumes. Large artefacts live in /tmp; only counts and hashes are committed.

    python3 -B docs/review_20261109_6b61c9d/room02_original_index_audit.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _REPO, os.path.join(_REPO, "docs", "review_20261109_bbc3dcb")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import verify_four_arm_independent as V          # noqa: E402

INJ = "/tmp/fastlivo/room02_inj43.bag"
CLN = "/tmp/fastlivo/room02_clean_60s.bag"
FIL = "/tmp/fastlivo/room02_inj43_filtered.bag"
ONSET_NS = 1627643759554082870
END_NS = 1627643779393426895
RESULTS = os.path.join(_HERE, "room02_original_index_audit.json")
SIDECAR = "/tmp/fastlivo/room02_original_index_sidecar.npz"


def _scans(path):
    """Yield (header_ns, list[bytes] rows) in bag order."""
    with V.Reader(path) as r:
        for conn, _t, raw in r.messages(
                connections=[c for c in r.connections if c.topic == V.SCAN_TOPIC]):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            ns = int(m.header.stamp.sec) * 10**9 + int(m.header.stamp.nanosec)
            step = int(m.point_step)
            data = np.asarray(m.data, dtype=np.uint8).reshape(-1, step)
            yield ns, [bytes(x) for x in data]


def _ordered_subsequence(needles, hay):
    """Map each needle to a strictly increasing index in hay, multiplicity aware.

    Returns (indices, n_unmatched). A local duplicate is consumed once, so two identical kept rows
    map to two distinct original rows.
    """
    pos = {}
    for i, h in enumerate(hay):
        pos.setdefault(h, []).append(i)
    cursor = 0
    out = []
    unmatched = 0
    for h in needles:
        cand = pos.get(h)
        hit = -1
        if cand:
            lo, hi = 0, len(cand)
            while lo < hi:                       # first candidate >= cursor
                mid = (lo + hi) // 2
                if cand[mid] < cursor:
                    lo = mid + 1
                else:
                    hi = mid
            if lo < len(cand):
                hit = cand[lo]
        if hit < 0:
            unmatched += 1
            out.append(-1)
        else:
            cursor = hit + 1
            out.append(hit)
    return out, unmatched


def _background_mask(inj_rows, clean_rows):
    """Multiset match: an injected row is background iff an unused clean row has equal bytes."""
    budget = Counter(clean_rows)
    mask = bytearray(len(inj_rows))
    for i, h in enumerate(inj_rows):
        if budget.get(h, 0) > 0:
            budget[h] -= 1
            mask[i] = 1
    return mask


def main():
    # Stream the three bags in lockstep; holding 599 frames of 50k Python bytes objects at once
    # costs gigabytes, and the three recordings share the same scan stamps and order.
    it_inj, it_cln, it_fil = _scans(INJ), _scans(CLN), _scans(FIL)
    frames, side = [], {}
    total_unmatched = 0
    for (ns_i, inj_rows), (ns_c, clean_rows), (ns_f, kept_rows) in zip(it_inj, it_cln, it_fil):
        if not (ns_i == ns_c == ns_f):
            raise SystemExit(f"scan stamps diverge: {ns_i} {ns_c} {ns_f}")
        ns = ns_i
        bg = _background_mask(inj_rows, clean_rows)
        kept_idx, unmatched = _ordered_subsequence(kept_rows, inj_rows)
        total_unmatched += unmatched
        if unmatched:
            # Do not silently drop rows: record the frame and exclude its per-row classification.
            frames.append({"ns": ns, "in_window": ONSET_NS <= ns <= END_NS,
                           "status": "UNMATCHED", "unmatched": unmatched,
                           "n_raw": len(inj_rows), "n_kept": len(kept_rows)})
            continue
        kept = set(kept_idx)
        kept_bg = sum(1 for i in kept_idx if bg[i])
        n_bg = sum(bg)
        kept_inj = len(kept_idx) - kept_bg
        dropped_bg = n_bg - kept_bg
        dropped_inj = (len(inj_rows) - n_bg) - kept_inj
        inw = ONSET_NS <= ns <= END_NS
        rec = {"ns": ns, "in_window": bool(inw), "status": "OK",
               "n_raw": len(inj_rows), "n_kept": len(kept_rows),
               "background_present": int(n_bg), "kept_background": int(kept_bg),
               "kept_injected": int(kept_inj), "dropped_background": int(dropped_bg),
               "dropped_injected": int(dropped_inj)}
        frames.append(rec)
        if inw:
            # Flat arrays, one key per frame: storing a dict per frame makes np.savez write a
            # pickled object array, which np.load then refuses without allow_pickle.
            side[f"k{ns}"] = np.asarray(kept_idx, dtype=np.int32)
            side[f"b{ns}"] = np.flatnonzero(np.frombuffer(bytes(bg), dtype=np.uint8))

    def _agg(sel):
        n_bg = sum(f["background_present"] for f in sel)
        kept_bg = sum(f["kept_background"] for f in sel)
        kept_inj = sum(f["kept_injected"] for f in sel)
        drop_bg = sum(f["dropped_background"] for f in sel)
        drop_inj = sum(f["dropped_injected"] for f in sel)
        injected = kept_inj + drop_inj
        return {"frames": len(sel), "background_present": int(n_bg),
                "kept_background": int(kept_bg), "kept_injected": int(kept_inj),
                "dropped_background": int(drop_bg), "dropped_injected": int(drop_inj),
                "injected_present": int(injected),
                "false_negative_rate": float(kept_inj / injected) if injected else None,
                "false_positive_rate": float(drop_bg / n_bg) if n_bg else None,
                "kept_injected_over_background_present": float(kept_inj / n_bg) if n_bg else None,
                "rows_raw": int(sum(f["n_raw"] for f in sel)),
                "rows_kept": int(sum(f["n_kept"] for f in sel))}

    ok = [f for f in frames if f["status"] == "OK"]
    res = {
        "inputs": {"injected": INJ, "injected_sha256": V._sha_file(INJ),
                   "clean": CLN, "clean_sha256": V._sha_file(CLN),
                   "filtered": FIL, "filtered_sha256": V._sha_file(FIL)},
        "window": {"onset_ns": ONSET_NS, "end_ns": END_NS,
                   "source": "per-frame buffer equality against the clean recording"},
        "method": {"row_identity": "original row index recovered as an in-order subsequence of "
                                   "the injected scan; multiplicity preserved",
                   "background_match": "multiset match of row bytes against the clean scan",
                   "hash_set_matching": False},
        "frames_total": len(frames), "frames_ok": len(ok), "frames_unmatched": len(frames) - len(ok),
        "total_unmatched_rows": int(total_unmatched),
        "in_window": _agg([f for f in ok if f["in_window"]]),
        "healthy": _agg([f for f in ok if not f["in_window"]]),
        "per_frame": frames,
        "reading": "false_negative_rate is kept_injected/(kept_injected+dropped_injected), the "
                   "conditional rate over injected rows. kept_injected_over_background_present is "
                   "the old field's quantity, renamed to say what its denominator is.",
    }
    np.savez_compressed(SIDECAR, **side)
    res["index_sidecar"] = {"path": SIDECAR, "sha256": V._sha_file(SIDECAR),
                            "frames": len(side) // 2,   # two arrays per frame
                            "arrays": "keys k<ns> = kept original indices, b<ns> = background original indices"}
    with open(RESULTS, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps({k: res[k] for k in ("in_window", "healthy", "frames_unmatched")},
                     indent=1))
    print("sidecar", res["index_sidecar"]["sha256"][:16], len(side) // 2, "frames")


if __name__ == "__main__":
    main()
