"""Recompute archived CSV/log facts without running host or archived analysis scripts."""
import csv
import io
import json
import math
import re
import subprocess

REPO = "D:/REPAIR/slam_recovery_upstream"
TARGET = "088906ae7cda17fb50b32580323a1008c542e3b1"
PREFIX = "docs/review_20261112_four_host/"

def text(path):
    return subprocess.check_output(["git", "-C", REPO, "show", TARGET + ":" + PREFIX + path]).decode(errors="replace")

rows = list(csv.reader(io.StringIO(text("lio_sam/trajectory.csv"))))
assert rows[0] == ["stamp_s", "x", "y", "z", "qx", "qy", "qz", "qw"]
rows = [[float(value) for value in row] for row in rows[1:] if row]
stamps = [row[0] for row in rows]
positions = [row[1:4] for row in rows]
steps = [math.dist(before, after) for before, after in zip(positions, positions[1:])]
gaps = [after - before for before, after in zip(stamps, stamps[1:])]
windows = {}
for name, (start, end) in {"pre": (0, 50), "E1": (50, 70), "middle": (70, 190), "E2": (190, 210), "tail": (210, 260)}.items():
    indices = [index for index in range(len(steps)) if start <= stamps[index] - stamps[0] < end]
    windows[name] = {"n_pairs": len(indices), "max_step_m": round(max(steps[index] for index in indices), 3),
                     "n_step_gt_1m": sum(steps[index] > 1 for index in indices),
                     "max_dt_s": round(max(gaps[index] for index in indices), 3),
                     "n_gap_gt_0p5s": sum(gaps[index] > 0.5 for index in indices)}
archived = json.loads(text("lio_sam/window_stats.json"))
assert all(all(value == archived["windows"][name][key] for key, value in window.items()) for name, window in windows.items())
log = text("orb_slam3/orb.log").splitlines()
ids = [int(match.group(1)) for line in log if (match := re.match(r"mnFirstFrameId = (\d+)", line.strip()))]
print(json.dumps({"target": TARGET, "scope": "Git CSV recomputation and selected raw log facts; no host, bag, archived scripts or tests",
                  "lio_sam": {"status": "ARCHIVE_RECOMPUTED", "n": len(rows), "path_len_m": round(sum(steps), 3),
                              "t0_first_output_stamp": stamps[0], "t1": stamps[-1], "windows": windows,
                              "matches_archived_selected_window_fields": True},
                  "orb_slam3": {"status": "RAW_LOG_READBACK", "initializations": len(ids),
                                "new_map_lines": sum("New Map created" in line for line in log),
                                "not_enough_motion_lines": sum("Not enough motion" in line for line in log),
                                "bad_imu_reset_lines": sum("Reset map because local mapper set the bad imu flag" in line for line in log),
                                "final_zero_keyframes": any("Map 0 has 0 KFs" in line for line in log[-22:]),
                                "exit_139": "exit=139" in log[-22:]},
                  "limits": "Observation windows are not independently identified physical fault events; declarations state after launch, before analysis. LIO window anchor is first output, not independently bound bag start. ORB times.txt is absent, so per-window mapping is not independently recomputed."}, ensure_ascii=False, indent=2))
