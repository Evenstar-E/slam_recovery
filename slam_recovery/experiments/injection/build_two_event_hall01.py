#!/usr/bin/env python3
"""Add a second degradation window to the hall01 filtered input, keeping the first one.

The recovery mainline has to show one native instance handling two events on one input timeline.
The existing `hall01_inj43_filtered.bag` already carries E1 (plastic-bag near-field occlusion over
`[1627785275.607, 1627785295.546]`), so this writes a *new* file that keeps E1 untouched, keeps
every real message between the two events, and injects E2 over a later window with the same
supported injector. The source bag is opened read-only and never rewritten.

    /home/R26534/mm/ros/bin/python -B \
        slam_recovery/experiments/injection/build_two_event_hall01.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import rosbag
from sensor_msgs.msg import PointCloud2

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, _REPO)

from slam_recovery.experiments.injection import (  # noqa: E402
    inject_plastic_bag_near_field_occlusion,
)

SRC = "/tmp/fastlivo/hall01_inj43_filtered.bag"
OUT = "/tmp/fastlivo/hall01_two_event_v1.bag"
REPORT = os.path.join(_HERE, "hall01_two_event_v1.json")
SCAN_TOPIC = "/velodyne_points"

# E2, relative to the first lidar header stamp of the source bag. E1 already occupies
# [+14.606, +34.545] s, so [+42, +52] s leaves [+34.545, +42] s of untouched real message between
# the two events -- the re-entry interval the run has to consume.
E2_START_REL_S = 42.0
E2_END_REL_S = 52.0

# Same supported degradation type as E1 (near-field self-consistent occlusion), at a different
# severity and seed so E2 is a second event rather than a repeat of the first.
E2_PARAMS = dict(occluded_azimuth_fraction=0.70, bag_distance_m=3.50,
                 bag_Thickness_jitter_m=0.01, seed=4242)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not os.path.exists(SRC):
        print(f"FAIL: missing {SRC}")
        return 2
    if os.path.exists(OUT):
        print(f"FAIL: refusing to overwrite existing {OUT}")
        return 2

    t0 = None
    n_e2 = 0
    n_scan = 0
    first_e2_ns = last_e2_ns = None
    with rosbag.Bag(SRC, "r") as b_in, rosbag.Bag(OUT, "w") as b_out:
        for topic, msg, t in b_in.read_messages():
            if topic != SCAN_TOPIC:
                b_out.write(topic, msg, t)
                continue
            n_scan += 1
            # rosbag hands back genpy Time, whose fields are secs/nsecs (ros 2 names them
            # sec/nanosec); both carry to_nsec().
            stamp_ns = int(msg.header.stamp.to_nsec())
            if t0 is None:
                t0 = stamp_ns
            rel_s = (stamp_ns - t0) / 1e9
            if not (E2_START_REL_S <= rel_s <= E2_END_REL_S):
                # Every byte of E1 and of the messages between the events is copied unchanged.
                b_out.write(topic, msg, t)
                continue

            n_e2 += 1
            if first_e2_ns is None:
                first_e2_ns = stamp_ns
            last_e2_ns = stamp_ns

            # msg.data is already bytes in this rosbag build; np.asarray(bytes) would try to parse
            # it as a number, so go straight through frombuffer.
            raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(-1, msg.point_step).copy()
            xyzi = raw[:, 0:16].view(np.float32).reshape(-1, 4).copy()
            bag_xyzi, _is_bag = inject_plastic_bag_near_field_occlusion(xyzi, **E2_PARAMS)
            raw[:, 0:16] = bag_xyzi.astype(np.float32).view(np.uint8).reshape(-1, 16)

            out = PointCloud2()
            out.header = msg.header
            out.height = 1
            out.width = int(raw.shape[0])
            out.fields = msg.fields
            out.is_bigendian = False
            out.point_step = msg.point_step
            out.row_step = msg.point_step * out.width
            out.data = raw.tobytes()
            out.is_dense = True
            b_out.write(topic, out, t)

    rep = {
        "source": {"path": SRC, "sha256": _sha256(SRC)},
        "output": {"path": OUT, "sha256": _sha256(OUT)},
        "e1": {"window_abs_ns": [1627785275607408524, 1627785295546408653],
               "note": "already present in the source; copied unchanged"},
        "e2": {"window_rel_s": [E2_START_REL_S, E2_END_REL_S],
               "window_abs_ns": [first_e2_ns, last_e2_ns],
               "frames": n_e2,
               "injector": "inject_plastic_bag_near_field_occlusion",
               "params": E2_PARAMS},
        "between_events_rel_s": [(1627785295546408653 - t0) / 1e9, E2_START_REL_S],
        "scans_total": n_scan,
        "note": "source untouched; output is a new file; E1 messages and the re-entry interval are "
                "copied verbatim from the source",
    }
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, default=int)
    print(f"scans {n_scan}, E2 frames {n_e2} over rel [{E2_START_REL_S}, {E2_END_REL_S}] s")
    print(f"wrote {OUT}\nsha256 {rep['output']['sha256']}")
    print(f"report {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
