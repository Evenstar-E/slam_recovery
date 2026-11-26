"""Seal the actual subscribed ROS output and map-transition signals."""
from collections import Counter
import json
from pathlib import Path
import sys

import rosbag


folder = Path(sys.argv[1])
trace = folder / "OBSERVED.jsonl"
counts = Counter()
active_flags = Counter()
with rosbag.Bag(str(folder / "observed.bag")) as bag, trace.open("x") as out:
    for topic, msg, arrival in bag.read_messages():
        counts[topic] += 1
        row = {"topic": topic, "observer_arrival_ns": arrival.to_nsec()}
        if topic in ("/Odometry", "/aft_pgo_odom"):
            pos = msg.pose.pose.position
            q = msg.pose.pose.orientation
            row.update(sensor_stamp_ns=msg.header.stamp.to_nsec(), frame=msg.header.frame_id,
                       pose=[pos.x, pos.y, pos.z, q.x, q.y, q.z, q.w])
        elif topic == "/aft_pgo_path":
            row.update(sensor_stamp_ns=msg.header.stamp.to_nsec(), frame=msg.header.frame_id,
                       pose_stamps_ns=[pose.header.stamp.to_nsec() for pose in msg.poses])
        elif topic in ("/Issleeping", "/Isbuilding"):
            row["value"] = msg.data
            active_flags[topic] += bool(msg.data)
        out.write(json.dumps(row, allow_nan=False) + "\n")
print(json.dumps(dict(counts=counts, true_transition_signals=active_flags,
                      validated_historical_downstream_receipts=0,
                      gauge_merge_verified=False), indent=2))
