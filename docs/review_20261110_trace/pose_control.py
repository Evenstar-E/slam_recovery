#!/usr/bin/env python3
"""The control the traces cannot provide: does run-to-run divergence exist with tracing OFF?

Tracing off emits no CSV, so the pre-declared trace judgement has no OFF pair to compare. The OFF
runs still write their odometry bag, and that is the same physical quantity the trace's STATE rows
sample. This compares output bags pairwise, so the control is measured instead of assumed.

    python -I docs/review_20261110_trace/pose_control.py res_on1.bag res_on2.bag res_off1.bag res_off2.bag
"""

from __future__ import annotations

import json
import sys

import numpy as np


def load(path: str):
    import rosbag
    out = []
    with rosbag.Bag(path) as bag:
        for _, msg, _ in bag.read_messages(topics=["/aft_mapped_to_init"]):
            q = msg.pose.pose.position
            out.append((msg.header.stamp.to_nsec(), np.array([q.x, q.y, q.z], dtype=np.float64)))
    return out


def compare(a, b):
    da = dict(a)
    db = dict(b)
    common = sorted(set(da) & set(db))
    d = np.array([np.linalg.norm(da[s] - db[s]) for s in common])
    first = next((i for i, x in enumerate(d) if x > 1e-3), None)
    return {
        "common": len(common),
        "first_gt_1mm_index": first,
        "first_gt_1mm_stamp_ns": common[first] if first is not None else None,
        "delta_at_first_m": float(d[first]) if first is not None else None,
        "median_m": float(np.median(d)) if len(d) else None,
        "max_m": float(d.max()) if len(d) else None,
        "max_index": int(d.argmax()) if len(d) else None,
        "frames_over_1mm": int((d > 1e-3).sum()),
    }


def main(argv):
    if len(argv) != 5:
        print(__doc__)
        return 2
    bags = {name: load(path) for name, path in
            (("on1", argv[1]), ("on2", argv[2]), ("off1", argv[3]), ("off2", argv[4]))}
    out = {name: {"frames": len(v)} for name, v in bags.items()}
    out["pairs"] = {"on1-on2": compare(bags["on1"], bags["on2"]),
                    "off1-off2": compare(bags["off1"], bags["off2"])}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
