#!/usr/bin/env python3
"""INJECTION relay: replay a bag's cloud topic through a declared corruption window.

The host and the recovery node both read `/velodyne_points`. During a controlled corruption test
the bag is played with that topic remapped to `/velodyne_points_raw`, this relay subscribes to the
raw topic, and it republishes on `/velodyne_points`:

  * inside [start_ns, end_ns]: every point's z is shifted by `dz` (a systematic, declared bias);
  * outside: the message is forwarded unchanged.

The shift is applied to the x/y/z bytes only, exactly like `inject_repaired_scan.shift_cloud`, so
every other field (`intensity`, `time`, `ring`), the header and the point layout survive.

Every frame is recorded with its stamp and whether it was shifted, so the archive can show which
frames the host actually saw corrupted.

    python3 -B -m slam_recovery.ros.corrupt_relay \
        --in-topic /velodyne_points_raw --out-topic /velodyne_points \
        --start-ns 1627785276215170145 --end-ns 1627785282215170145 \
        --shift-z 0.5 --record /tmp/relay_frames.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np

from slam_recovery.ros.cloud_repair import corrupt_if_in_window, window_active  # noqa: F401


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in-topic", default="/velodyne_points_raw")
    ap.add_argument("--out-topic", default="/velodyne_points")
    ap.add_argument("--start-ns", type=int, default=None,
                    help="first stamp (ns) to corrupt; default: from the beginning")
    ap.add_argument("--end-ns", type=int, default=None,
                    help="stamp (ns) at which corruption stops (half-open)")
    ap.add_argument("--shift-z", type=float, default=0.5)
    ap.add_argument("--record", default="",
                    help="JSONL of {stamp_ns, shifted, dz, points}; empty = no file")
    args, _unknown = ap.parse_known_args(argv)

    import rospy
    from sensor_msgs.msg import PointCloud2

    rospy.init_node("corrupt_relay", anonymous=True)
    pub = rospy.Publisher(args.out_topic, PointCloud2, queue_size=20)
    rec = open(args.record, "w", encoding="utf-8") if args.record else None
    state = {"received": 0, "shifted": 0}
    if rec is not None:
        rec.write(json.dumps({
            "event": "window", "in_topic": args.in_topic, "out_topic": args.out_topic,
            "start_ns": args.start_ns, "end_ns": args.end_ns, "shift_z": args.shift_z,
            "wall_start": time.time(),
        }) + "\n")

    def on_cloud(msg):
        stamp_ns = int(msg.header.stamp.secs) * 10 ** 9 + int(msg.header.stamp.nsecs)
        out, active = corrupt_if_in_window(msg, stamp_ns, args.start_ns, args.end_ns,
                                           args.shift_z)
        pub.publish(out)
        state["received"] += 1
        if active:
            state["shifted"] += 1
        if rec is not None:
            rec.write(json.dumps({"event": "frame", "stamp_ns": stamp_ns,
                                  "shifted": bool(active), "dz": args.shift_z if active else 0.0,
                                  "points": int(msg.width) * int(msg.height)}) + "\n")
            rec.flush()

    rospy.Subscriber(args.in_topic, PointCloud2, on_cloud, queue_size=20)
    rospy.loginfo("[corrupt_relay] %s -> %s window=[%s, %s) dz=%.3f",
                  args.in_topic, args.out_topic, args.start_ns, args.end_ns, args.shift_z)
    rospy.spin()
    if rec is not None:
        rec.write(json.dumps({"event": "summary", **state, "wall_end": time.time()}) + "\n")
        rec.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
