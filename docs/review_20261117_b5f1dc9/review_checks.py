"""Read-only checks for MM-LINS v4 and LIO-SAM status at main b5f1dc9."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REF = "b5f1dc938029a467a88c0420fda29fdd75192a06"
RUN = "docs/four_host/mmlins_recovery_20261117/two_event_mmlins_v4_20261117/"
PREREG = "docs/four_host/liosam_recovery_20261117/PREREGISTRATION_20261117.md"
PATCH = "docs/four_host/liosam_recovery_20261117/patches/mapOptmization_native_recovery.patch"


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", REF + ":" + path])


def main():
    summary = json.loads(blob(RUN + "run_summary.json"))
    candidates = [json.loads(x) for x in blob(RUN + "candidates.jsonl").decode().splitlines() if x]
    pgo = blob(RUN + "pgo.log").decode()
    bag = blob(RUN + "bag_info.txt").decode()
    pre = blob(RUN + "pre_run.txt").decode()
    assert summary["run_id"] == "mmlins_two_event_v4_20261117"
    assert len(summary["scripted_triggers"]["fired"]) == 2
    assert summary["final_state"] == "HEALTHY"
    assert summary["quarantine_open_at_exit"] is False
    assert summary["terminal_reason"] is None
    assert summary["lifecycle"]["unresolved_segments"] == 1
    assert summary["message_disposition"]["repair"]["clouds_published"] == 0
    assert summary["native_checkpoint"]["reprocesses"] == 0
    assert summary["detection_enabled"] is False
    assert "a924b5f9b593fad111f2ef91197735b85c8d26d340f04d5ca61535f25eaaf2de" in pre
    assert "2066f02533db78d61d753366bd322a8ac6e861976f5a5443ca112425afd7b2de" in pre
    assert "cc99d2ea5be3ac923c965cd9708b7e5b8587a76b1628dba0207e06693f82f886" in pre
    assert "/aft_pgo_odom   7921 msgs" in bag
    assert pgo.count("skipping sleeping map") == 819
    assert blob(RUN + "pgo_hold_at_exit.txt").decode().strip() == "absent"

    ep1, ep2 = summary["quarantine"]["episode_detail"]
    assert ep1["checkpoint_check"]["status"] == "AT_OR_BEFORE_BOUNDARY"
    assert "valid=1" in ep1["native_checkpoint"]["ack"]
    assert ep1["paired_evidence"]["num_improved_frames"] == 5
    assert ep1["paired_evidence"]["num_paired_frames"] == 13
    assert ep2["checkpoint_check"]["status"] == "LATE_AFTER_BOUNDARY"
    late_ns = int(ep2["checkpoint_check"]["actual_stamp_ns"]) - int(ep2["checkpoint_check"]["boundary_stamp_ns"])
    assert late_ns == 200143352
    assert ep2["paired_evidence"]["num_improved_frames"] == 0
    assert ep2["paired_evidence"]["num_paired_frames"] == 11
    assert all(row["accepted"] is False for row in candidates)

    prereg = blob(PREREG).decode()
    patch = blob(PATCH).decode()
    assert "（run 后填写。）" in prereg
    assert '\\"reprocess\\": \\"NO\\"' in patch
    assert '\\"measurement_relay\\": \\"NO\\"' in patch

    result = {
        "reviewed_ref": REF,
        "scope": "read-only archived MM-LINS run and LIO-SAM patch; no ROS, build, new run, or algorithm execution",
        "mmlins_v4": {
            "fired_events": 2,
            "final_state": summary["final_state"],
            "terminal_reason": summary["terminal_reason"],
            "unresolved_segments": summary["lifecycle"]["unresolved_segments"],
            "accepted_candidates": 0,
            "repair_clouds_published": 0,
            "reprocesses": 0,
            "pgo_output_messages": 7921,
            "pgo_guard_activations": 819,
            "pgo_hold_at_exit": "absent",
            "E1_checkpoint": ep1["checkpoint_check"],
            "E2_checkpoint": ep2["checkpoint_check"],
            "E2_checkpoint_late_ns": late_ns,
            "E1_improved": "5/13",
            "E2_improved": "0/11",
            "E1_holdout_nis": candidates[0]["holdout_nis"],
            "E2_holdout_nis": candidates[1]["holdout_nis"],
            "automatic_detection": "NOT_EXECUTED",
        },
        "liosam": {
            "status": "PATCH_AND_PREREGISTRATION_ONLY",
            "build": "NOT_EXECUTED_IN_ARCHIVED_COMMIT",
            "run": "NOT_EXECUTED_IN_ARCHIVED_COMMIT",
            "reprocess": "NO",
            "measurement_relay": "NO",
        },
        "verdict": "PARTIAL_NATIVE_LIFECYCLE_PROGRESS; NO_ACCEPTED_REPAIR_OR_LIO_SAM_RUN",
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("review_checks.json")
    assert not output.exists(), "refuse to overwrite %s" % output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
