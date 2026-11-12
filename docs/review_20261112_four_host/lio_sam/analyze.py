import sys, json, math
import rosbag
bag_path = sys.argv[1]
out = {"bag": bag_path, "topics": {}, "odometry": {}}
times, pos = [], []
with rosbag.Bag(bag_path) as bag:
    for topic, msg, t in bag.read_messages():
        out["topics"][topic] = out["topics"].get(topic, 0) + 1
        if topic == "/lio_sam/mapping/odometry":
            p = msg.pose.pose.position
            times.append(msg.header.stamp.to_sec())
            pos.append((p.x, p.y, p.z))
if times:
    steps = [math.dist(pos[i], pos[i+1]) for i in range(len(pos)-1)]
    gaps = [times[i+1]-times[i] for i in range(len(times)-1)]
    out["odometry"] = {
        "n": len(times), "t0": times[0], "t1": times[-1],
        "path_len_m": round(sum(steps), 3),
        "max_step_m": round(max(steps), 3) if steps else None,
        "max_step_at_s": round(times[steps.index(max(steps))]-times[0], 2) if steps else None,
        "max_gap_s": round(max(gaps), 3) if gaps else None,
        "max_gap_at_s": round(times[gaps.index(max(gaps))]-times[0], 2) if gaps else None,
        "start": [round(v,3) for v in pos[0]], "end": [round(v,3) for v in pos[-1]],
    }
print(json.dumps(out, indent=1))
