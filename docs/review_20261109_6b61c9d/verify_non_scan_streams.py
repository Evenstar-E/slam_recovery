#!/usr/bin/env python3
"""Verify the non-scan streams the 2x2 bags inherit from the filtered recording.

The builder passes IMU and camera through unchanged, so the four arms agree with the filtered bag
by construction. What is not yet checked is that the filtered recording's non-scan streams are
identical to the injected recording's -- a mixed old audit would show up there, not in LiDAR.

Compares /handsfree/imu and /camera/color/image_raw message by message (stamp + payload digest).

    /home/R26534/mm/ros/bin/python -B docs/review_20261109_6b61c9d/verify_non_scan_streams.py
"""

from __future__ import annotations

import hashlib
import json
import os

import numpy as np

try:
    import rosbag
except ImportError:
    rosbag = None

_HERE = os.path.dirname(os.path.abspath(__file__))
INJ = "/tmp/fastlivo/room02_inj43.bag"
FIL = "/tmp/fastlivo/room02_inj43_filtered.bag"
IMU = "/handsfree/imu"
IMG = "/camera/color/image_raw"
RECEIPT = os.path.join(_HERE, "non_scan_streams_verified.json")


def _ns(msg) -> int:
    st = msg.header.stamp
    if hasattr(st, "secs"):
        return int(st.secs) * 10**9 + int(st.nsecs)
    return int(st.sec) * 10**9 + int(st.nanosec)


def _digest(topic, msg) -> str:
    if topic == IMU:
        vals = []
        for obj in (msg.orientation, msg.angular_velocity, msg.linear_acceleration):
            for attr in ("x", "y", "z", "w"):
                if hasattr(obj, attr):
                    vals.append(float(getattr(obj, attr)))
        payload = np.asarray(vals, dtype=np.float64).tobytes()
    else:
        payload = bytes(msg.data)
    h = hashlib.sha256()
    h.update(topic.encode())
    h.update(str(_ns(msg)).encode())
    h.update(payload)
    return h.hexdigest()


def _stream(path):
    out = {IMU: {}, IMG: {}}
    with rosbag.Bag(path, "r") as bag:
        for topic, msg, _t in bag.read_messages(topics=[IMU, IMG]):
            out[topic][_ns(msg)] = _digest(topic, msg)
    return out


def main():
    if rosbag is None:
        raise SystemExit("run under the ROS python (/home/R26534/mm/ros/bin/python)")
    a, b = _stream(INJ), _stream(FIL)
    res = {"inputs": {"injected": INJ, "filtered": FIL}, "streams": {}, "failures": []}
    for topic in (IMU, IMG):
        ka, kb = set(a[topic]), set(b[topic])
        only_a, only_b = sorted(ka - kb), sorted(kb - ka)
        differing = [ns for ns in sorted(ka & kb) if a[topic][ns] != b[topic][ns]]
        res["streams"][topic] = {"injected": len(ka), "filtered": len(kb),
                                 "only_injected": len(only_a), "only_filtered": len(only_b),
                                 "differing": len(differing),
                                 "first_differing": differing[:5]}
        if only_a or only_b or differing:
            res["failures"].append(topic)
    res["verdict"] = "IDENTICAL" if not res["failures"] else "DIFFERS"
    with open(RECEIPT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res["streams"], indent=1))
    print(res["verdict"])
    return 0 if res["verdict"] == "IDENTICAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
