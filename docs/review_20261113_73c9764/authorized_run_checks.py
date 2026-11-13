"""Authorized FAST-LIO run audit fixed to f1bd803; standard library, Git objects only."""
import collections
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = "f1bd803dbcbb60419d50dd70491768c54c4f22dc"
BASE = "docs/four_host/fastlio_recovery_20261113/"
RUN = BASE + "two_event_authorized_20261113/"


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", MAIN + ":" + path])


def stamp(ack):
    m = re.search(r"stamp_ns=(\d+)", ack or "")
    return int(m.group(1)) if m else None


def main():
    summary = json.loads(blob(RUN + "run_summary.json"))
    actions = [a for a in summary["native_checkpoint_actions"]
               if a.get("command") in ("hold", "snapshot")]
    assert len(actions) == 4
    pairs = []
    for hold, snap in zip(actions[::2], actions[1::2]):
        assert hold["command"] == "hold" and snap["command"] == "snapshot"
        target = int(hold["payload"])
        assert int(snap["payload"]) == target
        hs, ss = stamp(hold["ack"]), stamp(snap["ack"])
        assert hs is not None and ss is not None
        pairs.append({
            "target_ns": target,
            "hold_stamp_ns": hs,
            "hold_delta_ms": (hs - target) / 1e6,
            "snapshot_stamp_ns": ss,
            "snapshot_delta_ms": (ss - target) / 1e6,
            "snapshot_written_at_hold_applied_ack_wall": snap["wall"] == hold["ack_wall"],
            "snapshot_wall": snap["wall"],
            "hold_applied_ack_wall": hold["ack_wall"],
            "map_points": int(re.search(r"map_points=(\d+)", snap["ack"]).group(1)),
        })
    assert all(p["hold_delta_ms"] < 0 for p in pairs)
    assert all(p["snapshot_delta_ms"] > 0 for p in pairs)
    assert all(p["snapshot_written_at_hold_applied_ack_wall"] for p in pairs)

    received = blob(RUN + "ctl/ack_received").decode().strip()
    assert received.startswith("RECEIVED ") and "wall=" not in received
    driver = blob("slam_recovery/ros/recovery_node.py").decode()
    assert 'if p.startswith("wall="):' in driver
    assert 'self._pipeline_armed_pair(event)' in driver

    rows = [json.loads(x) for x in blob(RUN + "ctl/input_fates.jsonl").decode().splitlines() if x]
    fates = collections.Counter(r["fate"] for r in rows)
    assert fates == {"ingested": 1137, "quarantined": 1113}
    first_host_ns = rows[0]["stamp_ns"]
    last_diagnostic_ns = summary["frame_diagnostics"][-1]["ts_ns"]
    last_diagnostic_s = (last_diagnostic_ns - first_host_ns) / 1e9
    host_log = blob(RUN + "host.log").decode()
    assert host_log.count("Over-degeneracy") == 8
    assert host_log.count("IMU Initial Done") == 163
    assert summary["scripted_triggers"]["fired"] == []
    assert summary["quarantine"]["episodes"] == 0
    md = summary["message_disposition"]
    assert md["fully_accounted"] and md["fully_decided"]
    assert md["keyframes"]["never_quarantined"] == 949
    assert not blob(RUN + "candidates.jsonl")

    result = {
        "main": MAIN,
        "scope": "authorized archived run and fixed driver receipt parser; no ROS/host/build",
        "build": {"exit": blob(BASE + "build_v4_exit.txt").decode().strip(),
                  "pre_sha": blob(BASE + "pre_build_sha.txt").decode().strip(),
                  "post_sha": blob(BASE + "post_build_sha.txt").decode().strip(),
                  "binary_entity_independently_rebuilt_here": False},
        "checkpoint_pairs": pairs,
        "checkpoint_boundary": "FAIL_BOTH_SNAPSHOTS_LATE; v4 deferred PASS claim not accepted",
        "received_receipt_from_real_host": received,
        "received_parser_requires_wall_for_pipeline": True,
        "host_fates": dict(fates),
        "last_frame_diagnostic_relative_first_host_s": last_diagnostic_s,
        "host_log_counts": {"Over-degeneracy": 8, "IMU Initial Done": 163},
        "scripted_fired": summary["scripted_triggers"]["fired"],
        "episodes": summary["quarantine"]["episodes"],
        "driver_fully_accounted_but_driver_scope_only": {
            "fully_accounted": md["fully_accounted"],
            "driver_never_quarantined": md["keyframes"]["never_quarantined"],
            "host_quarantined": fates["quarantined"],
        },
        "runtime_driver_pid_scope": summary["runtime"],
        "native_hibernation_root_cause": "UNKNOWN; direct observation precedes armed hold and is not attributed to a unique algorithm/load cause",
        "reprocess_E1_E2": "NOT_EXECUTED",
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("authorized_run_checks.json")
    assert not output.exists(), f"refuse to overwrite {output}"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
