"""Read target Git archive bytes; do not execute archived scripts or write extracted files."""
import hashlib
import json
from pathlib import PurePosixPath
import subprocess

REPO = "D:/REPAIR/slam_recovery_upstream"
TARGET = "3dec39a7f8f8b6d21281d56645a7fc10237460aa"
BASE = "docs/review_20261112_accepted_chain/"

def blob(path):
    return subprocess.check_output(["git", "-C", REPO, "show", f"{TARGET}:{path}"])

def fields(event):
    return dict(token.split("=", 1) for token in event.get("ack", "").split() if "=" in token)

output = {"target": TARGET, "scope": "Target Git archive readback/hash/limited log extraction; no host, bag, tests, archived script execution", "runs": []}
for run in ["fl_native_20261112T020634Z_4148249", "fl_native_20261112T022158Z_4156288"]:
    prefix = BASE + "run_" + run + "/"
    checks = []
    for line in blob(prefix + "SHA256SUMS").decode().splitlines():
        expected, path = line.split(maxsplit=1)
        path = str(PurePosixPath(path.lstrip("*")))
        assert not path.startswith("/") and ".." not in PurePosixPath(path).parts
        actual = hashlib.sha256(blob(prefix + path)).hexdigest()
        checks.append({"path": path, "ok": actual == expected})
    receipt = json.loads(blob(prefix + "receipt.json"))
    summary = json.loads(blob(prefix + "run_summary.json"))
    events = json.loads(blob(prefix + "native_checkpoint_events.json"))
    lifecycle = json.loads(blob(prefix + "lifecycle_events.json"))
    candidates = [json.loads(line) for line in blob(prefix + "candidates.jsonl").decode().splitlines() if line]
    host_lines = blob(prefix + "host.log").decode(errors="replace").splitlines()
    native = summary.get("native_checkpoint", {})
    state_events = []
    for event in events:
        if event.get("command") not in ["hold", "restore", "reprocess", "set_state", "resume"]:
            continue
        state_events.append({**{key: event.get(key) for key in ["command", "ok", "wall", "received_wall", "ack_wall", "trigger"]},
                             "ack_fields": {key: fields(event).get(key) for key in ["stamp_ns", "hold", "repair_received", "repair_applied", "set_state", "live_voxels", "live_points"]}})
    row = {"run_id": run,
           "integrity": {"matched": sum(check["ok"] for check in checks), "total": len(checks), "bad": [check["path"] for check in checks if not check["ok"]]},
           "driver_source_sha256": receipt["inputs"].get("recovery_node_source"),
           "headline": receipt.get("recovery_summary_headline"),
           "launch": {key: receipt["launch"].get(key) for key in ["candidate_source", "detection", "scripted_triggers_ns", "confirmation_margin_sec"]},
           "triggers": summary.get("scripted_triggers", {}).get("fired"),
           "candidates": [{**{key: candidate.get(key) for key in ["accepted", "mode", "t_trigger_ns", "t_decision_ns"]},
                           "committed_count": len(candidate.get("committed_pose_keys") or []),
                           "deferred_count": len(candidate.get("deferred_pose_keys") or [])} for candidate in candidates],
           "lifecycle": [{"event": event.get("event"), "segment_id": event.get("segment_id"), "unresolved_count": len(event.get("frames_unresolved", []))} for event in lifecycle],
           "native_counts": {key: native.get(key) for key in ["reprocesses", "resumes", "holds", "restores", "failures", "snapshot_ack_timeouts", "snapshots"]},
           "state_events": state_events,
           "host_log_selected": [{"line": index, "text": line} for index, line in enumerate(host_lines, 1) if "[NATIVE_CHECKPOINT] reprocess #" in line or "double free" in line or "[NATIVE_CHECKPOINT] reprocess points" in line],
           "quarantine_open_at_exit": summary.get("quarantine_open_at_exit"),
           "second_event_processed": len(candidates) >= 2,
           "limits": "Internal archive consistency, not independent build/bag verification; ack_wall is driver observation, not exact host apply time"}
    output["runs"].append(row)
print(json.dumps(output, ensure_ascii=False, indent=2))
