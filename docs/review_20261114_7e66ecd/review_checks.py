"""Read-only inventory of the three FAST-LIO runs archived by main 7e66ecd."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REF = "7e66ecdb2b575fa0b7b8f2db2c0d1587fd26f654"
BASE = "docs/four_host/fastlio_recovery_20261113/"
RUN2 = BASE + "two_event_v9_icp_authorized/"
RUN3 = BASE + "two_event_v9b_rearm_authorized/"


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", REF + ":" + path])


def json_blob(path):
    return json.loads(blob(path))


def jsonl_blob(path):
    return [json.loads(line) for line in blob(path).decode().splitlines() if line]


def main():
    summary = json_blob(RUN3 + "run_summary.json")
    candidates = jsonl_blob(RUN3 + "candidates.jsonl")
    icp_rows = jsonl_blob(RUN3 + "icp_detail.jsonl")
    ep2 = summary["quarantine"]["episode_detail"][1]
    candidate = candidates[1]
    icp = icp_rows[1]
    wait = next(row for row in summary["lifecycle"]["events"]
                if row["event"] == "wait_limit_closed")
    check = ep2["checkpoint_check"]
    late_ns = int(check["actual_stamp_ns"]) - int(check["boundary_stamp_ns"])

    assert summary["run_id"] == "two_event_v9b_rearm_authorized"
    assert len(summary["scripted_triggers"]["fired"]) == 2
    assert summary["quarantine"]["decisions"] == 2
    assert summary["final_state"] == "HEALTHY"
    assert summary["quarantine_open_at_exit"] is False
    assert "valid=1" in ep2["native_checkpoint"]["ack"]
    assert check["status"] == "LATE_AFTER_BOUNDARY"
    assert check["rollback_support"] == "UNSUPPORTED_AT_OR_BEFORE_QSTART"
    assert late_ns == 200143352
    assert candidate["accepted"] is False
    assert candidate["mode"] == "MODE3_SOFT_BRIDGE_WAIT"
    assert ep2["paired_evidence"]["num_paired_frames"] == 11
    assert ep2["paired_evidence"]["num_improved_frames"] == 1
    assert (ep2["paired_evidence"]["candidate_mean_residual"]
            > ep2["paired_evidence"]["incumbent_mean_residual"])
    assert icp["status"] == "ITERATION_LIMIT"
    assert icp["icp_converged"] is False
    assert icp["icp_iterations"] == 20
    assert len(wait["frames_unresolved"]) == 92
    assert summary["lifecycle"]["unresolved_segments"] == 1
    assert summary["terminal_reason"] == "INPUT_STALE"
    assert summary["native_checkpoint"]["reprocesses"] == 0
    assert summary["message_disposition"]["repair"]["clouds_published"] == 0

    run2 = json_blob(RUN2 + "run_summary.json")
    run2_ep1 = run2["quarantine"]["episode_detail"][0]
    run3_ep1 = summary["quarantine"]["episode_detail"][0]
    run2_pre = blob(RUN2 + "pre_run.txt").decode()
    run3_pre = blob(RUN3 + "pre_run.txt").decode()
    run2_binary = next(x for x in run2_pre.splitlines() if x.startswith("binary=")).split()[0]
    run3_binary = next(x for x in run3_pre.splitlines() if x.startswith("binary=")).split()[0]
    run2_bag = next(x for x in run2_pre.splitlines() if x.startswith("bag=")).split()[0]
    run3_bag = next(x for x in run3_pre.splitlines() if x.startswith("bag=")).split()[0]
    assert run2_binary == run3_binary
    assert run2_bag == run3_bag
    assert run2_ep1["paired_evidence"]["num_improved_frames"] == 9
    assert run2_ep1["paired_evidence"]["num_paired_frames"] == 13
    assert run3_ep1["paired_evidence"]["num_improved_frames"] == 3
    assert run3_ep1["paired_evidence"]["num_paired_frames"] == 12

    result = {
        "reviewed_ref": REF,
        "scope": "read-only Git originals; no ROS, host execution, rebuild, or algorithm changes",
        "run3_lifecycle": {
            "fired": len(summary["scripted_triggers"]["fired"]),
            "decisions": summary["quarantine"]["decisions"],
            "final_state": summary["final_state"],
            "quarantine_open_at_exit": summary["quarantine_open_at_exit"],
            "terminal_reason": summary["terminal_reason"],
            "automatic_detection": "NOT_EXECUTED",
        },
        "e2": {
            "restore_ack": ep2["native_checkpoint"]["ack"],
            "checkpoint_status": check["status"],
            "checkpoint_late_ns": late_ns,
            "rollback_support": check["rollback_support"],
            "accepted": candidate["accepted"],
            "mode": candidate["mode"],
            "paired_frames": ep2["paired_evidence"]["num_paired_frames"],
            "improved_frames": ep2["paired_evidence"]["num_improved_frames"],
            "incumbent_mean_residual": ep2["paired_evidence"]["incumbent_mean_residual"],
            "candidate_mean_residual": ep2["paired_evidence"]["candidate_mean_residual"],
            "icp_status": icp["status"],
            "icp_iterations": icp["icp_iterations"],
            "correction_rotation_deg": icp["correction_rotation_deg"],
            "correction_translation_m": icp["correction_translation_m"],
            "unresolved_raw_frame_refs": len(wait["frames_unresolved"]),
            "unresolved_segments": summary["lifecycle"]["unresolved_segments"],
            "repair_clouds_published": summary["message_disposition"]["repair"]["clouds_published"],
            "reprocesses": summary["native_checkpoint"]["reprocesses"],
        },
        "candidate_repeatability_same_binary_bag_E1": {
            "run2_improved": "9/13",
            "run3_improved": "3/12",
            "binary_identity": run2_binary,
            "bag_identity": run2_bag,
        },
        "reporting_caveat": {
            "message_disposition_fully_decided": summary["message_disposition"]["fully_decided"],
            "lifecycle_unresolved_segments": summary["lifecycle"]["unresolved_segments"],
            "interpretation": "driver classification says fully_decided while the lifecycle explicitly closes 92 frames unresolved; neither means those frames were repaired or replayed",
        },
        "verdict": "PARTIAL_FUNCTIONAL_PROGRESS; CONTROL_LIFECYCLE_CLOSED_WITHOUT_ACCEPTED_MEASUREMENT_REPAIR",
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("review_checks.json")
    assert not output.exists(), "refuse to overwrite %s" % output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
