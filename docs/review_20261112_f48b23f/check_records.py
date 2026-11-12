"""Read target Git records only; do not execute archived runners or load ROS bags."""
import hashlib
import json
import math
from pathlib import PurePosixPath
import subprocess

REPO = "D:/REPAIR/slam_recovery_upstream"
TARGET = "f48b23f66707e9491350c1c62972fbf542f94fa3"
PREFIX = "docs/review_20261112_four_host/"

def blob(path):
    return subprocess.check_output(["git", "-C", REPO, "show", TARGET + ":" + PREFIX + path])

checks = []
for line in blob("SHA256SUMS").decode().splitlines():
    expected, path = line.split(maxsplit=1)
    path = str(PurePosixPath(path.lstrip("*")))
    assert not path.startswith("/") and ".." not in PurePosixPath(path).parts
    checks.append({"path": path, "ok": hashlib.sha256(blob(path)).hexdigest() == expected})
results = []
for name in ["mmlins_campus12_20261112", "fastlio2_shared_campus12_20261112"]:
    analysis = json.loads(blob(name + "/analysis.json"))
    declaration = json.loads(blob(name + "/events.json"))
    row = {"run": name, "events": [], "topics": {}, "flags": analysis.get("flags", {})}
    for event in declaration["events"]:
        offset = event["stamp_ns"] - declaration["bag_first_imu_ns"]
        assert offset == round(event["offset_s"] * 1e9)
        row["events"].append({"name": event["name"], "stamp_ns": event["stamp_ns"], "offset_ns": offset})
    for topic in ["/Odometry", "/aft_pgo_odom"]:
        if topic not in analysis["topics"]:
            continue
        data = analysis["topics"][topic]
        topic_result = {key: data.get(key) for key in ["messages", "zero_stamp_messages", "path_length_m", "last_stamp_ns", "tail_after_E2_s", "messages_after_E2"]}
        assert math.isclose(topic_result["tail_after_E2_s"], (data["last_stamp_ns"] - declaration["events"][1]["stamp_ns"]) / 1e9, abs_tol=1e-8)
        topic_result["event_near_gaps"] = []
        for event in declaration["events"]:
            gap = min(data["gaps_gt_1s"], key=lambda item: abs(item["from_ns"] - event["stamp_ns"]))
            delta = (gap["to_ns"] - gap["from_ns"]) / 1e9
            step = math.dist(gap["pos_before"], gap["pos_after"])
            assert math.isclose(delta, gap["dt_s"], abs_tol=1e-9)
            assert math.isclose(step, gap["step_m"], abs_tol=1e-8)
            topic_result["event_near_gaps"].append({"event": event["name"], "gap_s": delta, "step_m": step})
        row["topics"][topic] = topic_result
    results.append(row)
log = blob("fastlio2_shared_campus12_20261112/fastlio_node.log").decode(errors="replace").splitlines()
selected = [{"line": index, "text": line} for index, line in enumerate(log, 1) if "Over-degeneracy has happened" in line or "construct a new map" in line]
print(json.dumps({"target": TARGET, "scope": "Archive hashes and arithmetic of recorded summaries; raw output bags not read", "integrity": {"matched": sum(check["ok"] for check in checks), "total": len(checks), "bad": [check["path"] for check in checks if not check["ok"]]}, "runs": results, "frontend_log_events": selected}, ensure_ascii=False, indent=2))
