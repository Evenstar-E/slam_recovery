"""Read-only counterexamples for motion-prior runs archived at main 1058932."""
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REF = "105893283b566d1043f75d1b2977479b80836f98"
BASE = "docs/four_host/fastlio_recovery_20261113/"
NATURAL = BASE + "two_event_v9f_prior_natural_authorized/"
INJECTED = BASE + "two_event_v9g_prior_injected_authorized/"
SEQ2 = BASE + "two_event_v9h_seq2_turn_authorized/"


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", REF + ":" + path])


def json_blob(path):
    return json.loads(blob(path))


def jsonl_blob(path):
    return [json.loads(line) for line in blob(path).decode().splitlines() if line]


def ack_stamp(action):
    return int(re.search(r"stamp_ns=(\d+)", action["ack"]).group(1))


def main():
    natural = json_blob(NATURAL + "run_summary.json")
    injected = json_blob(INJECTED + "run_summary.json")
    seq2 = json_blob(SEQ2 + "run_summary.json")
    natural_icp = jsonl_blob(NATURAL + "icp_detail.jsonl")
    injected_icp = jsonl_blob(INJECTED + "icp_detail.jsonl")

    for summary in (natural, injected, seq2):
        assert summary["gate"]["accepted"] == 0
        assert summary["message_disposition"]["repair"]["clouds_published"] == 0
        assert summary["native_checkpoint"]["reprocesses"] == 0
        assert summary["detection_enabled"] is False

    # The frozen method says non-converged frames are omitted. The archived candidates
    # include ITERATION_LIMIT frames, so these runs did not evaluate that declared contract.
    assert natural_icp[0]["status_counts"]["ITERATION_LIMIT"] == 20
    assert natural_icp[0]["frames_candidate"] == 21
    assert natural_icp[1]["status_counts"]["ITERATION_LIMIT"] == 19
    assert "CONVERGED" not in natural_icp[1]["status_counts"]
    assert natural_icp[1]["frames_candidate"] == 19
    assert injected_icp[0]["status_counts"] == {"ITERATION_LIMIT": 40}
    assert injected_icp[0]["frames_candidate"] == 40
    assert injected_icp[1]["status_counts"] == {"TOO_FEW_CORRESPONDENCES": 41}
    assert injected_icp[1]["frames_candidate"] == 0
    source = blob("slam_recovery/repair/pose_reregistration.py").decode()
    assert 'if res.status in ("CONVERGED", "ITERATION_LIMIT"):' in source

    actions = injected["native_checkpoint_actions"]
    snapshots = [(i, row) for i, row in enumerate(actions) if row["command"] == "snapshot"]
    restores = [(i, row) for i, row in enumerate(actions) if row["command"] == "restore"]
    assert len(snapshots) == 2 and len(restores) == 2
    first_snapshot_i, first_snapshot = snapshots[0]
    second_snapshot_i, second_snapshot = snapshots[1]
    first_restore_i, first_restore = restores[0]
    assert first_snapshot_i < second_snapshot_i < first_restore_i
    first_snapshot_stamp = ack_stamp(first_snapshot)
    first_restore_stamp = ack_stamp(first_restore)
    second_snapshot_stamp = ack_stamp(second_snapshot)
    assert first_snapshot_stamp == 1711548075973547264
    assert second_snapshot_stamp == 1711548108373620736
    assert first_restore_stamp == second_snapshot_stamp
    ep1 = injected["quarantine"]["episode_detail"][0]
    boundary = int(ep1["checkpoint_check"]["boundary_stamp_ns"])
    restore_late_s = (first_restore_stamp - boundary) / 1e9
    assert abs(restore_late_s - 32.500372397) < 1e-9
    assert ep1["checkpoint_check"]["rollback_support"] == "UNSUPPORTED_AT_OR_BEFORE_QSTART"

    relay = jsonl_blob(INJECTED + "relay_frames.jsonl")
    frames = [row for row in relay if row.get("event") == "frame"]
    shifted = [row for row in frames if row.get("shifted") is True]
    assert len(frames) == 2350 and len(shifted) == 60
    summary_row = next(row for row in relay if row.get("event") == "summary")
    assert summary_row["received"] == 2350 and summary_row["shifted"] == 60

    assert len(seq2["scripted_triggers"]["declared_ns"]) == 2
    assert len(seq2["scripted_triggers"]["fired"]) == 1
    assert seq2["run_mode"] == "CONTROLLED_TRIGGERS_NOT_FIRED"
    assert seq2["terminal_reason"] == "HOST_HIBERNATION_TIMEOUT"

    result = {
        "reviewed_ref": REF,
        "scope": "read-only Git source and archived runs; no ROS, rebuild, or new experiment",
        "accepted_native_repair": {
            "accepted_candidates": 0,
            "repair_clouds_published": 0,
            "reprocesses": 0,
        },
        "frozen_method_mismatch": {
            "contract": "non-converged frames must not enter the candidate",
            "source_accepts_statuses": ["CONVERGED", "ITERATION_LIMIT"],
            "natural_E1": {"candidate": 21, "iteration_limit": 20, "converged": 1},
            "natural_E2": {"candidate": 19, "iteration_limit": 19, "converged": 0},
            "injected_E1": {"candidate": 40, "iteration_limit": 40, "converged": 0},
            "impact": "option 1 runs do not confirm the frozen method as written",
        },
        "checkpoint_overwrite_counterexample": {
            "first_snapshot_action_index": first_snapshot_i,
            "second_snapshot_action_index": second_snapshot_i,
            "first_restore_action_index": first_restore_i,
            "first_snapshot_stamp_ns": first_snapshot_stamp,
            "second_snapshot_stamp_ns": second_snapshot_stamp,
            "first_restore_stamp_ns": first_restore_stamp,
            "E1_restore_late_after_boundary_s": restore_late_s,
            "impact": "E2 snapshot replaced the mutable checkpoint before E1 restore; valid=1 restored a future state, not the E1 checkpoint",
        },
        "injection_count_correction": {
            "frame_records": len(frames),
            "shifted_frames": len(shifted),
            "development_text_claim": "received=2352 / shifted=61",
            "actual_frame_and_summary_records": "received=2350 / shifted=60; 2352/61 counts window+summary lines rather than frames",
        },
        "sequence2": {
            "declared_events": 2,
            "fired_events": 1,
            "E2": "NOT_REACHED",
            "terminal_reason": seq2["terminal_reason"],
        },
        "verdict": "NO_ACCEPTED_REPAIR; OPTION1_CONFIRMATION_INVALID_FOR_FROZEN_CONTRACT; CHECKPOINT_STATE_SAFETY_COUNTEREXAMPLE",
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("review_checks.json")
    assert not output.exists(), "refuse to overwrite %s" % output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
