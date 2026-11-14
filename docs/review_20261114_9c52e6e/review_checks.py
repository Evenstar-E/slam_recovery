"""Read-only checks for per-frame and injected-bias runs through main 9c52e6e."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REF = "9c52e6e30962e1d8fa652e2d665cf205c45f9b5a"
BASE = "docs/four_host/fastlio_recovery_20261113/"
RUNS = {
    "per_frame": BASE + "two_event_v9c_perframe_authorized/",
    "injected_moving": BASE + "two_event_v9d_injected_authorized/",
    "injected_turn": BASE + "two_event_v9e_turn_authorized/",
}


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", REF + ":" + path])


def json_blob(path):
    return json.loads(blob(path))


def jsonl_blob(path):
    return [json.loads(line) for line in blob(path).decode().splitlines() if line]


def main():
    summaries = {name: json_blob(path + "run_summary.json") for name, path in RUNS.items()}
    icp = {name: jsonl_blob(path + "icp_detail.jsonl") for name, path in RUNS.items()}
    for name, summary in summaries.items():
        assert summary["gate"]["accepted"] == 0
        assert summary["gate"]["rejected"] == 2
        assert summary["message_disposition"]["repair"]["clouds_published"] == 0
        assert summary["native_checkpoint"]["reprocesses"] == 0
        assert summary["detection_enabled"] is False
        assert summary["quarantine_open_at_exit"] is False

    natural = summaries["per_frame"]
    ep2 = natural["quarantine"]["episode_detail"][1]
    evidence = ep2["paired_evidence"]
    improvement = ((evidence["incumbent_mean_residual"] - evidence["candidate_mean_residual"])
                   / evidence["incumbent_mean_residual"])
    assert evidence["num_improved_frames"] == 5
    assert evidence["num_paired_frames"] == 11
    assert evidence["candidate_mean_residual"] < evidence["incumbent_mean_residual"]
    assert improvement > 0.05
    assert evidence["approved"] is False
    assert evidence["reason"] == "wilson_sequential_benefit_lower_bound_failed"
    assert ep2["checkpoint_check"]["status"] == "LATE_AFTER_BOUNDARY"

    injection = {}
    for name in ("injected_moving", "injected_turn"):
        rows = jsonl_blob(RUNS[name] + "relay_frames.jsonl")
        frames = [row for row in rows if row.get("event") == "frame"]
        shifted = [row for row in frames if row.get("shifted") is True]
        assert len(shifted) == 60
        assert {row["dz"] for row in shifted} == {0.5}
        injection[name] = {
            "frame_records": len(frames),
            "shifted_frames": len(shifted),
            "shift_body_z_m": 0.5,
            "unresolved_segments": summaries[name]["lifecycle"]["unresolved_segments"],
            "terminal_reason": summaries[name]["terminal_reason"],
        }

    moving = summaries["injected_moving"]["quarantine"]["episode_detail"][0]["paired_evidence"]
    turn = summaries["injected_turn"]["quarantine"]["episode_detail"][0]["paired_evidence"]
    assert moving["num_improved_frames"] == 7 and moving["num_paired_frames"] == 40
    assert turn["num_improved_frames"] == 0 and turn["num_paired_frames"] == 40
    assert turn["candidate_mean_residual"] > turn["incumbent_mean_residual"]
    assert icp["injected_moving"][0]["init_poses"] == "host_poses"
    assert icp["injected_turn"][0]["init_poses"] == "incumbent"
    assert icp["injected_turn"][0]["status"] == "ITERATION_LIMIT"
    assert all(row["checkpoint_check"]["status"] == "AT_OR_BEFORE_BOUNDARY"
               for row in summaries["injected_turn"]["quarantine"]["episode_detail"])

    result = {
        "reviewed_ref": REF,
        "scope": "read-only archived evidence; no ROS, rebuild, new run, or algorithm execution",
        "all_three_runs": {
            "accepted_candidates": 0,
            "repair_clouds_published": 0,
            "reprocesses": 0,
            "automatic_detection": "NOT_EXECUTED",
        },
        "natural_E2_per_frame_counterexample": {
            "improved_frames": "5/11",
            "incumbent_mean_residual": evidence["incumbent_mean_residual"],
            "candidate_mean_residual": evidence["candidate_mean_residual"],
            "relative_mean_improvement": improvement,
            "wilson_lower_bound": evidence["wilson_lower_bound"],
            "approved": evidence["approved"],
            "reason": evidence["reason"],
            "interpretation": "mean improvement exists but frame-consistent evidence is insufficient; this does not prove the event has no improvable error",
            "checkpoint": ep2["checkpoint_check"],
        },
        "injection": injection,
        "candidate_initialization_comparison": {
            "moving_host_init": {
                "improved": "7/40",
                "icp_status": icp["injected_moving"][0]["status"],
                "candidate_mean_residual": moving["candidate_mean_residual"],
                "incumbent_mean_residual": moving["incumbent_mean_residual"],
            },
            "turn_incumbent_init": {
                "improved": "0/40",
                "icp_status": icp["injected_turn"][0]["status"],
                "candidate_mean_residual": turn["candidate_mean_residual"],
                "incumbent_mean_residual": turn["incumbent_mean_residual"],
            },
            "limit": "different windows and initializations; not a same-population parameter comparison",
        },
        "verdict": "REAL_NEGATIVE_EVIDENCE; ACCEPTED_NATIVE_REPAIR_NOT_REACHED; NO_IMPROVABLE_ERROR_CLAIM_NOT_ESTABLISHED",
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("review_checks.json")
    assert not output.exists(), "refuse to overwrite %s" % output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
