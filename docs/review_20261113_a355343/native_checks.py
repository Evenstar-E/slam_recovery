"""Native FAST-LIO evidence controls fixed to main 119f5d7 and growth ce3aaac.

Standard-library only. Reads Git objects, never executes archived host/scripts and never runs ROS.
Exit 0 means the independent calculations completed, not that recovery passed.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = "119f5d7b4561039f3de91e6e709d76dcae021615"
GROWTH = "ce3aaacdf9e31a13e00ba293829ee0eeae50c21d"
PREVIOUS = "a355343711cf8e8daf71eadbd68677ab4bf7bddb"
BASE = "docs/four_host/fastlio_recovery_20261113/"
HASHES = {}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def blob(ref, path):
    raw = git("show", ref + ":" + path)
    HASHES[ref + ":" + path] = hashlib.sha256(raw).hexdigest()
    return raw


def jsonl(ref, path):
    return [json.loads(line) for line in blob(ref, path).decode().splitlines() if line.strip()]


def main():
    v2_path = BASE + "laserMapping.v2.cpp"
    v3_path = BASE + "native_recovery_v3_deferred.diff"
    driver_path = "slam_recovery/ros/recovery_node.py"
    f2_path = "docs/ali_h_v1_research/f2_fastlio_read.py"
    v2 = blob(MAIN, v2_path).decode()
    v3 = blob(GROWTH, v3_path).decode()
    driver = blob(MAIN, driver_path).decode()
    controlled = blob(GROWTH, BASE + "tools/run_controlled.sh").decode()
    assert blob(PREVIOUS, driver_path) == blob(MAIN, driver_path)
    assert blob(PREVIOUS, f2_path) == blob(MAIN, f2_path)

    commands = blob(MAIN, BASE + "ctrl2/commands.log").decode()
    replay_ack = re.search(r"OK reprocess replay_suffix=(\d+) replay_within_end=(\d+) "
                           r"repaired_fed=(\d+) source=buffer", commands)
    assert replay_ack
    replay_suffix, replay_within, repaired_fed = map(int, replay_ack.groups())
    map_points = [int(x) for x in re.findall(r"OK snapshot valid=1 stamp_ns=\d+ frame=\d+ "
                                             r"map_points=(\d+)", commands)]
    assert map_points == [27513, 71690]

    ctrl_rows = jsonl(MAIN, BASE + "ctrl2/ctl/input_fates.jsonl")
    ctrl_counts = collections.Counter(r["fate"] for r in ctrl_rows)
    pre_max = max(r["stamp_ns"] for r in ctrl_rows if r["fate"] != "replayed")
    replayed = [r for r in ctrl_rows if r["fate"] == "replayed"]
    declared_replay = [r for r in replayed if r["stamp_ns"] <= pre_max]
    future_mislabeled = [r for r in replayed if r["stamp_ns"] > pre_max]
    assert len(ctrl_rows) == 1255
    assert ctrl_counts == {"ingested": 261, "quarantined": 12, "replayed": 982}
    assert len(declared_replay) == replay_within == 83
    assert len(future_mislabeled) == 899
    assert v2.count("g_nr_replay.store(true)") == 1
    assert "g_nr_replay.store(false)" not in v2
    assert "g_nr_replay.store(false)" not in v3

    # repaired_fed is incremented while selecting and enqueueing clouds, before the ACK; the
    # function contains no native update call. The later map growth proves replay, not which cloud
    # entered a successful update or whether the repair helped.
    reprocess_body = v2[v2.index('else if (cmd == "reprocess")'):v2.index('else if (cmd == "capabilities")')]
    queue_pos = reprocess_body.index("lidar_buffer.push_front")
    fed_pos = reprocess_body.index("++g_nr_repaired_fed")
    ack_pos = reprocess_body.index("nr_write_ack", queue_pos)
    assert fed_pos < queue_pos < ack_pos
    assert "update_iterated_dyn_share_modified" not in reprocess_body
    assert "map_incremental" not in reprocess_body

    # The controlled script resumes before replay. The automatic accepted path commits inside
    # decide(), while lifecycle resume is serviced before decide() and native reprocess does not
    # clear hold. This is a source-confirmed uncovered sequence, not a claimed observed E1 failure.
    assert controlled.index("== resume") < controlled.index("== reprocess")
    assert "g_nr_hold.store(false)" not in reprocess_body
    service_body = driver[driver.index("    def service("):driver.index("    def _apply_lifecycle(")]
    lifecycle_body = driver[driver.index("    def _apply_lifecycle("):driver.index("    def finish(")]
    assert service_body.index("self._apply_lifecycle()") < service_body.index("return self.decide")
    assert "self.cp.resume()" in lifecycle_body

    # v3 emits final-looking OK at arm time and applies only after g_nr_lidar_end already reached
    # the target. Its call site is before sync_packages, so the reaching frame has already run.
    assert 's2 << "OK " << cmd << " deferred stamp="' in v3
    assert "g_nr_deferred.front().stamp_ns <= now_ns" in v3
    apply_call = v3.index("nr_apply_deferred();", v3.index("@@ -780"))
    sync_call = v3.index("if (sync_packages(Measures))", apply_call)
    frame_end = v3.index("g_nr_lidar_end = lidar_end_time;", sync_call)
    assert apply_call < sync_call < frame_end

    run5_rows = jsonl(GROWTH, BASE + "two_event5_hold_ignored_stamp/ctl/input_fates.jsonl")
    run5_counts = collections.Counter(r["fate"] for r in run5_rows)
    run5 = json.loads(blob(GROWTH, BASE + "two_event5_hold_ignored_stamp/run_summary.json"))
    assert len(run5_rows) == 2248 and run5_counts == {"quarantined": 2248}
    md = run5["message_disposition"]
    assert md["keyframes"]["never_quarantined"] == 1004
    assert md["unresolved"] == []
    assert run5["quarantine"]["episodes"] == 0
    assert run5["scripted_triggers"]["fired"] == []
    assert run5["run_mode"] == "CONTROLLED_TRIGGERS_NOT_FIRED"
    host_by_stamp = {r["stamp_ns"]: r["fate"] for r in run5_rows}
    exact_matches = [r for r in run5["frame_diagnostics"] if r["ts_ns"] in host_by_stamp]
    assert exact_matches
    assert all(host_by_stamp[r["ts_ns"]] == "quarantined" for r in exact_matches)

    result = {
        "main": MAIN,
        "growth": GROWTH,
        "command": "C:/Python315/python.exe -I -B docs/review_20261113_a355343/native_checks.py <new-json>",
        "scope": "fixed native source/diffs and archived receipts; no archived code execution, ROS, build or algorithm edit",
        "controlled_interface": {
            "status": "PARTIAL_CONTROLLED_INTERFACE_ONLY",
            "map_points_snapshots": map_points,
            "replay_suffix": replay_suffix,
            "replay_within_end": replay_within,
            "repaired_fed_declared": repaired_fed,
            "full_checkpoint": False,
            "automatic_detection": "NOT_EXECUTED",
            "net_benefit": "NOT_EVALUABLE",
        },
        "replay_fate": {
            "status": "CONFIRMED_POST_REPLAY_LIVE_INPUT_MISLABELED",
            "rows": len(ctrl_rows),
            "counts": dict(ctrl_counts),
            "pre_replay_max_stamp_ns": pre_max,
            "declared_replay_rows_at_or_before_pre_max": len(declared_replay),
            "later_live_rows_marked_replayed": len(future_mislabeled),
            "replay_reset_present_v2_or_v3": False,
        },
        "repair_fed_semantics": {
            "status": "CONFIRMED_QUEUE_SUBSTITUTION_NOT_NATIVE_UPDATE_PROOF",
            "order": ["nr_take_repair/++g_nr_repaired_fed", "lidar_buffer.push_front", "ACK"],
            "native_update_or_map_call_in_reprocess_command": False,
            "driver_field_overclaim": "repair_entered_estimator=bool(repaired_fed>0)",
        },
        "automatic_hold_sequence": {
            "status": "SOURCE_CONFIRMED_UNCOVERED_SEQUENCE_NOT_OBSERVED_E1_FAILURE",
            "controlled_resume_before_reprocess": True,
            "native_reprocess_clears_hold": False,
            "driver_lifecycle_resume_after_commit_waits_for_later_service": True,
            "minimum_acceptance": "accepted E1 replay must release map writes for replay while controlling live input; show actual map/update evidence",
        },
        "v3_deferred": {
            "status": "NOT_READY_BOUNDARY_AND_APPLIED_ACK_SEMANTICS",
            "arm_emits_OK_deferred": True,
            "apply_uses_previous_completed_frame_end": True,
            "apply_call_before_next_sync": True,
            "boundary_risk": "snapshot/hold occurs after the first frame reaching the target, not before it",
            "built_or_run": False,
        },
        "run5_actual_failure": {
            "run_mode": run5["run_mode"],
            "host_fates": dict(run5_counts),
            "driver_keyframes": md["keyframes"],
            "driver_unresolved": md["unresolved"],
            "exact_timestamp_matches": len(exact_matches),
            "host_fate_on_exact_matches": sorted({host_by_stamp[r["ts_ns"]] for r in exact_matches}),
            "episodes": run5["quarantine"]["episodes"],
            "fired": run5["scripted_triggers"]["fired"],
            "wall_sec": run5["runtime"]["wall_sec"],
            "peak_rss_kb_driver_pid_scope": run5["runtime"]["peak_rss_kb"],
            "final_state_not_health_evidence": run5["final_state"],
        },
        "previous_f2_f3_findings_still_apply": True,
        "hashes": HASHES,
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("native_checks.json")
    assert not output.exists(), f"refuse to overwrite {output}"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
