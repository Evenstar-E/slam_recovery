"""Read one target Git archive; no native execution or archived script loading."""
import hashlib
import json
from pathlib import PurePosixPath
import subprocess

REPO = "D:/REPAIR/slam_recovery_upstream"
TARGET = "751a226ce2ffad3df5d01cce5d81a4ffc1b23835"
PREFIX = "docs/review_20261112_accepted_chain/run_fl_native_20261112T024337Z_4166038/"

def blob(path):
    return subprocess.check_output(["git", "-C", REPO, "show", TARGET + ":" + PREFIX + path])

def read(path):
    return json.loads(blob(path))

checks = []
for line in blob("SHA256SUMS").decode().splitlines():
    expected, path = line.split(maxsplit=1)
    path = str(PurePosixPath(path.lstrip("*")))
    assert not path.startswith("/") and ".." not in PurePosixPath(path).parts
    checks.append(hashlib.sha256(blob(path)).hexdigest() == expected)
summary = read("run_summary.json")
receipt = read("receipt.json")
life = read("lifecycle_events.json")
events = read("native_checkpoint_events.json")
candidates = [json.loads(line) for line in blob("candidates.jsonl").decode().splitlines() if line]
closed = [event for event in life if event["event"] == "wait_limit_closed"]
t1, t2 = [event["ts_ns"] for event in summary["scripted_triggers"]["fired"]]
stamps = [row["ts_ns"] for row in summary["frame_diagnostics"]]
state_events = [event for event in events if event["command"] in ["hold", "reprocess", "set_state", "restore", "resume"]]
boundaries = []
for index, event in enumerate([event for event in events if event["command"] in ["reprocess", "restore"]]):
    fields = dict(token.split("=", 1) for token in event["ack"].split() if "=" in token)
    stamp = int(fields["stamp_ns"])
    boundaries.append({"command": event["command"], "checkpoint_ns": stamp,
                       "quarantine_start_ns": closed[index]["t_start_ns"],
                       "checkpoint_minus_start_s": (stamp - closed[index]["t_start_ns"]) / 1e9,
                       "repair_applied": fields["repair_applied"]})
print(json.dumps({"target": TARGET, "sha256_matches": sum(checks), "sha256_total": len(checks),
                  "inputs": receipt["inputs"], "launch": receipt["launch"],
                  "headline": receipt["recovery_summary_headline"],
                  "triggers": summary["scripted_triggers"]["fired"],
                  "decisions": [{key: row.get(key) for key in ["accepted", "mode", "t_trigger_ns", "t_decision_ns"]} for row in candidates],
                  "state_events": state_events, "checkpoint_boundaries": boundaries,
                  "frames": {"t1_inclusive_to_t2_exclusive": sum(t1 <= stamp < t2 for stamp in stamps),
                             "strict_close1_to_t2": sum(closed[0]["closed_ns"] < stamp < t2 for stamp in stamps),
                             "t2_inclusive_to_end": sum(t2 <= stamp for stamp in stamps),
                             "strict_close2_to_end": sum(closed[1]["closed_ns"] < stamp for stamp in stamps)},
                  "quarantine_open_at_exit": summary["quarantine_open_at_exit"]}, ensure_ascii=False, indent=2))
