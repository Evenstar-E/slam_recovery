#!/usr/bin/env python3
"""Is the ordered-subsequence index mapping unique?

The audit recovers a kept row's original index by matching row bytes to the injected scan in order.
When two rows in a frame have identical bytes, several increasing assignments are possible and
greedy-earliest is one valid witness, not a proof of the injector's index. This script measures
whether that ambiguity exists in the window: if every row in every window frame is distinct, the
mapping is unique and the "original index" label is exact for this data.

    /home/R26534/mm/ros/bin/python -B docs/review_20261109_6b61c9d/check_index_uniqueness.py
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
INJ = "/tmp/fastlivo/room02_inj43.bag"
ONSET_NS = 1627643759554082870
END_NS = 1627643779393426895
RECEIPT = os.path.join(_HERE, "index_uniqueness.json")

try:
    import rosbag
except ImportError:
    rosbag = None

import numpy as np


def main():
    if rosbag is None:
        raise SystemExit("run under the ROS python (/home/R26534/mm/ros/bin/python)")
    frames, frames_with_dupes, dup_rows, max_mult, max_extra = 0, 0, 0, 0, 0
    worst = None
    with rosbag.Bag(INJ, "r") as bag:
        for _topic, msg, _t in bag.read_messages(topics=["/velodyne_points"]):
            st = msg.header.stamp
            ns = int(st.secs) * 10**9 + int(st.nsecs)
            if not (ONSET_NS <= ns <= END_NS):
                continue
            frames += 1
            step = int(msg.point_step)
            rows = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(-1, step)
            counts = Counter(hashlib.blake2b(bytes(r), digest_size=16).digest() for r in rows)
            frame_max = max(counts.values())          # 1 when every row is distinct
            max_mult = max(max_mult, frame_max)
            max_extra = max(max_extra, frame_max - 1)
            dup = sum(v - 1 for v in counts.values() if v > 1)
            if dup:
                frames_with_dupes += 1
                dup_rows += dup
                if frame_max > 1:
                    worst = ns
    res = {"input": INJ, "window": {"onset_ns": ONSET_NS, "end_ns": END_NS},
           "frames": frames,
           "frames_with_duplicate_injected_rows": frames_with_dupes,
           "duplicate_injected_rows": dup_rows,
           "max_multiplicity": max_mult,            # 1 = every row in every frame is distinct
           "max_extra_copies": max_extra,           # 0 under the same condition
           "worst_frame_ns": worst,
           "mapping": ("UNIQUE" if dup_rows == 0 else
                       "AMBIGUOUS: greedy-earliest is one valid witness, not a unique index")}
    with open(RECEIPT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
