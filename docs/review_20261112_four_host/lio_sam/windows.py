import sys, json, math
import rosbag
bag = rosbag.Bag(sys.argv[1])
times, pos = [], []
for topic, msg, t in bag.read_messages(topics=["/lio_sam/mapping/odometry"]):
    p = msg.pose.pose.position
    times.append(msg.header.stamp.to_sec()); pos.append((p.x, p.y, p.z))
t0 = times[0]
wins = {"pre": (0, 50), "E1": (50, 70), "middle": (70, 190), "E2": (190, 210), "tail": (210, 260)}
out = {"t0": t0, "n": len(times), "windows": {}}
for name, (a, b) in wins.items():
    steps = []; gaps = []; nodes = 0
    for i in range(len(times) - 1):
        rel = times[i] - t0
        if a <= rel < b:
            g = times[i+1] - times[i]
            s = math.dist(pos[i], pos[i+1])
            gaps.append(g); steps.append(s); nodes += 1
    out["windows"][name] = {
        "n_pairs": nodes,
        "median_dt_s": round(sorted(gaps)[len(gaps)//2], 3) if gaps else None,
        "max_dt_s": round(max(gaps), 3) if gaps else None,
        "median_step_m": round(sorted(steps)[len(steps)//2], 3) if steps else None,
        "max_step_m": round(max(steps), 3) if steps else None,
        "n_step_gt_1m": sum(1 for s in steps if s > 1.0),
        "n_gap_gt_0p5s": sum(1 for g in gaps if g > 0.5),
    }
# first anomaly relative time
first_big = next((times[i] - t0 for i in range(len(times)-1) if math.dist(pos[i], pos[i+1]) > 1.0), None)
first_gap = next((times[i] - t0 for i in range(len(times)-1) if times[i+1]-times[i] > 0.5), None)
out["first_step_gt_1m_at_s"] = round(first_big, 2) if first_big is not None else None
out["first_gap_gt_0p5s_at_s"] = round(first_gap, 2) if first_gap is not None else None
print(json.dumps(out, indent=1))
