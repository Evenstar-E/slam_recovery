#!/usr/bin/env python3
"""Metrics for the FAST-LIO2 independent run, computed exactly like the shared run so the two
can be compared item by item.

Usage: analyze_bag.py <frontend.bag> <events.json|empty> <out.json> [E1_ns E2_ns]
"""
import json
import sys

import rosbag
import numpy as np


def dyn(x):
    return np.asarray(x, dtype=np.float64)


def main():
    bag_path, out_path = sys.argv[1], sys.argv[2]
    e1, e2 = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (None, None)
    odom = []          # (stamp_ns, pos)
    flags = {"/Issleeping": [], "/Isbuilding": []}
    topics = {}
    with rosbag.Bag(bag_path) as bag:
        start, end = bag.get_start_time(), bag.get_end_time()
        for topic, msg, _t in bag.read_messages():
            bag_t_ns = int(_t.to_nsec() if hasattr(_t, "to_nsec") else round(float(_t) * 1e9))
            topics[topic] = topics.get(topic, 0) + 1
            if topic == "/Odometry":
                odom.append((int(msg.header.stamp.to_nsec()), dyn([msg.pose.pose.position.x,
                                                                   msg.pose.pose.position.y,
                                                                   msg.pose.pose.position.z])))
            elif topic in flags and hasattr(msg, "data"):
                if bool(msg.data):
                    # std_msgs/Bool carries no header: the bag time is the only stamp.
                    flags[topic].append(bag_t_ns)
    odom.sort(key=lambda x: x[0])
    st = np.array([s for s, _ in odom], dtype=np.int64)
    pos = np.array([p for _, p in odom])
    out = {"bag": bag_path, "start": start, "end": end, "duration_s": end - start,
           "topics": topics, "events_ns": {"E1": e1, "E2": e2}}
    d = {}
    if len(st):
        step = np.linalg.norm(np.diff(pos, axis=0), axis=1)
        dt = np.diff(st) / 1e9
        gaps = [{"from_ns": int(st[i]), "to_ns": int(st[i + 1]), "dt_s": float(dt[i]),
                 "step_m": float(step[i]),
                 "pos_before": pos[i].tolist(), "pos_after": pos[i + 1].tolist()}
                for i in range(len(dt)) if dt[i] > 1.0]
        d = {"messages": int(len(st)), "first_stamp_ns": int(st[0]), "last_stamp_ns": int(st[-1]),
             "path_length_m": float(step[dt < 1.0].sum()) if np.any(dt < 1.0) else 0.0,
             "max_step": {"m": float(step.max()) if len(step) else 0.0,
                          "at_ns": int(st[int(step.argmax()) + 1]) if len(step) else None},
             "max_gap_s": float(dt.max()) if len(dt) else 0.0,
             "gaps_gt_1s": gaps}
        for name, ev in (("E1", e1), ("E2", e2)):
            if ev is None:
                continue
            i = int(np.searchsorted(st, ev))
            i = min(i, len(st) - 1)
            d[f"at_{name}"] = {"stamp_ns": int(st[i]), "dt_to_declared_s": (int(st[i]) - ev) / 1e9,
                               "pos": pos[i].tolist()}
            after = st > ev
            d[f"tail_after_{name}_s"] = float((st[-1] - ev) / 1e9)
            d[f"messages_after_{name}"] = int(after.sum())
    out["/Odometry"] = d
    out["/Issleeping"] = {"true_count": len(flags["/Issleeping"]),
                          "true_stamps_ns": flags["/Issleeping"]}
    out["/Isbuilding"] = {"true_count": len(flags["/Isbuilding"]),
                          "true_stamps_ns": flags["/Isbuilding"]}
    json.dump(out, open(out_path, "w"), indent=1)
    print(json.dumps({"/Odometry": {k: d.get(k) for k in ("messages", "max_gap_s", "max_step",
                                                          "tail_after_E2_s", "messages_after_E2")},
                      "/Issleeping": out["/Issleeping"]["true_count"],
                      "/Isbuilding": out["/Isbuilding"]["true_count"]}, indent=1))


if __name__ == "__main__":
    main()
