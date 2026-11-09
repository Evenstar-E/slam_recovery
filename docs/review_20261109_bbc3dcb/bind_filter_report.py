#!/usr/bin/env python3
"""Bind a filter sidecar to the exact bags it describes, or refuse it.

`build_filtered_bag` writes its per-frame record to a fixed path, so a later run can leave a
sidecar that no longer describes the bags on disk.  This rebinds an existing sidecar by evidence
rather than by assertion: every frame's `n` must equal the input bag's point count and every
frame's `kept` must equal the output bag's point count, for the same header nanosecond.  Only then
is the room-specific sidecar written, with the input/output sha256 attached.

    python3 -B docs/review_20261109_bbc3dcb/bind_filter_report.py \
        --input /tmp/fastlivo/room02_inj43.bag \
        --output /tmp/fastlivo/room02_inj43_filtered.bag \
        --report /tmp/filtered_bag_report.json \
        --out docs/review_20261109_bbc3dcb/room02_filter_report.json
"""

from __future__ import annotations

import argparse
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


def _counts(path):
    out = {}
    with V.Reader(path) as r:
        for conn, _t, raw in r.messages(
                connections=[c for c in r.connections if c.topic == V.SCAN_TOPIC]):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            ns = int(m.header.stamp.sec) * 10**9 + int(m.header.stamp.nanosec)
            out[ns] = int(np.frombuffer(np.asarray(m.data, dtype=np.uint8).tobytes(),
                                        dtype=V._cloud_dtype(m)).shape[0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    rep = json.load(open(a.report, encoding="utf-8"))
    in_counts = _counts(a.input)
    out_counts = _counts(a.output)
    ms_in = {round(ns / 1e9, 3): n for ns, n in in_counts.items()}
    ms_out = {round(ns / 1e9, 3): n for ns, n in out_counts.items()}

    mismatched, missing = [], []
    for f in rep["per_frame"]:
        t = round(float(f["t"]), 3)
        if t not in ms_in or t not in ms_out:
            missing.append(t)
            continue
        if ms_in[t] != f["n"] or ms_out[t] != f["kept"]:
            mismatched.append({"t": t, "report": [f["n"], f["kept"]],
                               "bags": [ms_in[t], ms_out[t]]})

    ok = not mismatched and not missing and len(rep["per_frame"]) == len(in_counts) == len(out_counts)
    bound = {
        "input": a.input, "input_sha256": V._sha_file(a.input),
        "output": a.output, "output_sha256": V._sha_file(a.output),
        "frames": len(rep["per_frame"]),
        "binding": {
            "method": "every frame's n must equal the input bag's point count and its kept must "
                      "equal the output bag's point count, at the same header millisecond",
            "frames_checked": len(rep["per_frame"]),
            "mismatched": mismatched[:20], "missing": missing[:20],
            "n_mismatched": len(mismatched), "n_missing": len(missing),
            "verdict": "BOUND" if ok else "STALE_AUDIT",
        },
        "filter": rep.get("filter"),
        "points_in": rep.get("points_in"),
        "points_kept": rep.get("points_kept"),
        "global_strip_fraction": rep.get("global_strip_fraction"),
        "frames_stripping_gt_10pct": rep.get("frames_stripping_gt_10pct"),
        "per_frame": rep["per_frame"],
    }
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(bound, fh, indent=1)
    print(json.dumps(bound["binding"], indent=1))
    if not ok:
        raise SystemExit("STALE_AUDIT: the sidecar does not describe these bags")


if __name__ == "__main__":
    main()
