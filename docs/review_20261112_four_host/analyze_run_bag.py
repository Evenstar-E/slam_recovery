#!/usr/bin/env python3
"""Describe one host's recorded run at two declared event stamps.

Reads an output bag and reports, per odometry topic: the pose nearest each declared stamp, the
displacement between them, the largest single-step displacement, path length, and the tail after
E2. Also reports whether the host's own sleep flag was raised around each event.

Only what is in the bag: no ground truth, no quality claim.

    python analyze_run_bag.py <bag> <out.json> <e1_ns> <e2_ns> [topic ...]
"""
import json
import sys

import numpy as np


def main():
    bag_path, out_path = sys.argv[1], sys.argv[2]
    e1, e2 = int(sys.argv[3]), int(sys.argv[4])
    topics = sys.argv[5:] or ["/Odometry"]
    import rosbag

    bag = rosbag.Bag(bag_path)
    out = {"bag": bag_path, "start": bag.get_start_time(), "end": bag.get_end_time(),
           "duration_s": bag.get_end_time() - bag.get_start_time(),
           "events_ns": {"E1": e1, "E2": e2}, "topics": {}}

    for topic in topics:
        ts, pos = [], []
        counts = 0
        zero_stamp = 0
        for _t, msg, _ in bag.read_messages(topics=[topic]):
            counts += 1
            if hasattr(msg, "pose"):
                p = msg.pose.pose.position
            elif getattr(msg, "poses", None):
                p = msg.poses[-1].pose.position       # nav_msgs/Path: the newest pose
            else:
                continue
            stamp = msg.header.stamp.secs * 10 ** 9 + msg.header.stamp.nsecs
            if stamp <= 0:
                # A zero stamp cannot be placed on the bag timeline; keeping it would sort it to
                # the front and manufacture a ~1.7e9 s gap.
                zero_stamp += 1
                continue
            ts.append(stamp)
            pos.append([p.x, p.y, p.z])
        if not ts:
            out["topics"][topic] = {"messages": 0, "zero_stamp_messages": zero_stamp}
            continue
        ts = np.asarray(ts, dtype=np.int64)
        pos = np.asarray(pos, dtype=np.float64)
        order = np.argsort(ts)
        ts, pos = ts[order], pos[order]

        def nearest(stamp):
            i = int(np.argmin(np.abs(ts - stamp)))
            return i, int(ts[i]), pos[i].tolist(), float((ts[i] - stamp) / 1e9)

        i1, t1, p1, d1 = nearest(e1)
        i2, t2, p2, d2 = nearest(e2)
        step = np.linalg.norm(np.diff(pos, axis=0), axis=1) if len(pos) > 1 else np.zeros(0)
        step_dt = np.diff(ts) / 1e9 if len(ts) > 1 else np.zeros(0)
        # A step is only a discontinuity if it is large AND the interval is short; a gap in the
        # stream is reported separately rather than called a jump.
        jump_idx = int(np.argmax(step)) if len(step) else None
        tail = ts[ts >= e2]
        out["topics"][topic] = {
            "messages": counts,
            "zero_stamp_messages": zero_stamp,
            "stamp_looks_wall_clock": bool(ts[0] == ts[-1] and counts > 1),
            "first_stamp_ns": int(ts[0]), "last_stamp_ns": int(ts[-1]),
            "at_E1": {"stamp_ns": t1, "dt_to_declared_s": round(d1, 3), "pos": p1},
            "at_E2": {"stamp_ns": t2, "dt_to_declared_s": round(d2, 3), "pos": p2},
            "disp_E1_to_E2_m": float(np.linalg.norm(np.asarray(p2) - np.asarray(p1))),
            "path_length_m": float(step.sum()),
            "max_step": (None if jump_idx is None else {
                "m": float(step[jump_idx]), "dt_s": float(step_dt[jump_idx]),
                "at_ns": int(ts[jump_idx])}),
            "max_step_short_interval_m": (None if not len(step) else
                                          float(step[step_dt <= 1.0].max() if np.any(step_dt <= 1.0) else 0.0)),
            "max_gap_s": float(step_dt.max()) if len(step_dt) else 0.0,
            # Every stream gap long enough that "no message" is itself a fact: the positions on
            # both sides say whether the host stopped, jumped, or re-initialised.
            "gaps_gt_1s": [
                {"from_ns": int(ts[i]), "to_ns": int(ts[i + 1]), "dt_s": float(step_dt[i]),
                 "step_m": float(step[i]), "pos_before": pos[i].tolist(),
                 "pos_after": pos[i + 1].tolist()}
                for i in np.where(step_dt > 1.0)[0]
            ],
            "tail_after_E2_s": (float((ts[-1] - e2) / 1e9) if ts[-1] >= e2 else 0.0),
            "messages_after_E2": int(len(tail)),
        }

    # The host's own sleep flag, if it published one. std_msgs/Bool carries no header, so the
    # only clock available is the recorder's receive time -- wall clock, not bag time. The
    # spacing between two flags is still comparable to the spacing between the declared events.
    for topic in ("Issleeping", "/Issleeping", "Isbuilding", "/Isbuilding"):
        recv, flag_val = [], []
        for _t, msg, t in bag.read_messages(topics=[topic]):
            recv.append(int(t.to_nsec()) if hasattr(t, "to_nsec") else int(float(t) * 1e9))
            flag_val.append(bool(getattr(msg, "data", False)))
        if recv:
            out.setdefault("flags", {})[topic] = {
                "messages": len(recv),
                "true_messages": int(sum(flag_val)),
                "clock": "bag receive time (wall clock); the message has no header",
                "received_wall_ns": recv,
                "true_wall_ns": [r for r, v in zip(recv, flag_val) if v],
            }
    bag.close()
    json.dump(out, open(out_path, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
