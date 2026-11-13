#!/usr/bin/env python3
"""Odometry timeline for one diagnostic run: counts, gaps, first stop, sleep/build flags."""
import json, sys
import rosbag
import numpy as np

run = sys.argv[1]
odom = []
flags = {"/Issleeping": [], "/Isbuilding": []}
with rosbag.Bag(run + "/frontend.bag") as b:
    for topic, msg, t in b.read_messages():
        if topic == "/Odometry":
            p = msg.pose.pose.position
            odom.append((msg.header.stamp.to_nsec(), [p.x, p.y, p.z]))
        elif topic in flags and bool(msg.data):
            flags[topic].append(int(t.to_nsec() if hasattr(t, "to_nsec") else round(float(t) * 1e9)))
odom.sort()
st = np.array([s for s, _ in odom], dtype=np.int64)
t0 = int(st[0]); rel = (st - t0) / 1e9
dt = np.diff(rel)
gaps = [{"start_s": round(float(rel[i]), 2), "len_s": round(float(dt[i]), 2)} for i in range(len(dt)) if dt[i] > 1.0]
out = {
    "odom_messages": int(len(st)), "first_stamp_ns": int(st[0]), "last_stamp_ns": int(st[-1]),
    "span_s": round(float(rel[-1]), 2), "gaps_gt_1s": gaps,
    "first_stop_s": gaps[0]["start_s"] if gaps else None,
    "Issleeping_true": len(flags["/Issleeping"]),
    "Isbuilding_true": len(flags["/Isbuilding"]),
    "Issleeping_delta_s": [round(float((v - flags["/Issleeping"][0]) / 1e9), 2) for v in flags["/Issleeping"]],
    "Isbuilding_delta_s": [round(float((v - flags["/Isbuilding"][0]) / 1e9), 2) for v in flags["/Isbuilding"]],
}
text = open(run + "/host.log", errors="ignore").read()
out["host_over_degeneracy"] = text.count("Over-degeneracy")
out["host_imu_initial_done"] = text.count("IMU Initial Done")
json.dump(out, open(run + "/analysis.json", "w"), indent=1)
print(json.dumps(out, indent=1))
