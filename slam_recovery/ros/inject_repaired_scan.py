#!/usr/bin/env python3
"""Publish one controlled "repaired" scan so the injection path can be checked deterministically.

This is a CONTROLLED_INTERFACE_TEST, not a repair: it takes exactly one scan off the live topic,
applies a known rigid translation to it, and republishes it on the repair channel with the same
header. What that proves is only that the host replaces the measurement it would have used, and
that the replacement changes the estimate; it says nothing about repair quality.

    python3 -B -m slam_recovery.ros.inject_repaired_scan \
        --after-sec 15 --shift-z 0.5 --stamp-file /tmp/inj_stamp.txt
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np


def shift_cloud(msg, dz: float):
    """Add dz to every point's z, keeping every other field byte-identical."""
    from sensor_msgs.msg import PointCloud2

    step = int(msg.point_step)
    raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(-1, step).copy()
    # x, y, z, intensity are the first four float32 fields in this recording (offsets 0/4/8/12).
    z = raw[:, 8:12].view(np.float32).reshape(-1)
    z += np.float32(dz)
    out = PointCloud2()
    out.header = msg.header
    out.height = 1
    out.width = int(raw.shape[0])
    out.fields = msg.fields
    out.is_bigendian = False
    out.point_step = step
    out.row_step = step * out.width
    out.data = raw.tobytes()
    out.is_dense = True
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in-topic", default="/velodyne_points")
    ap.add_argument("--out-topic", default="/native_recovery/repaired_scan")
    ap.add_argument("--after-sec", type=float, default=15.0)
    ap.add_argument("--window-sec", type=float, default=0.0,
                    help="republish every scan in [after, after+window); 0 = exactly one scan")
    ap.add_argument("--shift-z", type=float, default=0.5)
    ap.add_argument("--stamp-file", default="/tmp/inj_stamp.txt")
    args, _unknown = ap.parse_known_args(argv)

    import rospy
    from sensor_msgs.msg import PointCloud2

    rospy.init_node("inject_repaired_scan", anonymous=True)
    pub = rospy.Publisher(args.out_topic, PointCloud2, queue_size=5)
    state = {"t0": time.time(), "stamps": [], "done": False}

    def on_scan(msg):
        if state["done"]:
            return
        elapsed = time.time() - state["t0"]
        if elapsed < args.after_sec:
            return
        if args.window_sec > 0 and elapsed > args.after_sec + args.window_sec:
            state["done"] = True
            rospy.loginfo("[inject] window closed after %d repaired scans", len(state["stamps"]))
            return
        out = shift_cloud(msg, args.shift_z)
        stamp_ns = int(msg.header.stamp.secs) * 10 ** 9 + int(msg.header.stamp.nsecs)
        # The header must survive unchanged: the host matches on it.
        pub.publish(out)
        state["stamps"].append(stamp_ns)
        with open(args.stamp_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(str(s) for s in state["stamps"]) + "\n")
        rospy.loginfo("[inject] published repaired scan stamp=%d dz=%.3f", stamp_ns, args.shift_z)
        if args.window_sec <= 0:
            state["done"] = True

    rospy.Subscriber(args.in_topic, PointCloud2, on_scan, queue_size=5)
    rospy.spin()
    return 0


if __name__ == "__main__":
    sys.exit(main())
