"""Read-only checks for the preregistered static-injection run at main 7b134b3."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REF = "7b134b37a62d8d1dcbe4075caf6b2013252b60a8"
RUN = "docs/four_host/fastlio_recovery_20261113/two_event_v9j_static_injected_authorized/"


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", REF + ":" + path])


def jsonl(path):
    return [json.loads(x) for x in blob(path).decode().splitlines() if x]


def main():
    summary = json.loads(blob(RUN + "run_summary.json"))
    candidates = jsonl(RUN + "candidates.jsonl")
    details = jsonl(RUN + "candidates_detail.jsonl")
    icp = jsonl(RUN + "icp_detail.jsonl")
    relay = jsonl(RUN + "relay_frames.jsonl")
    frames = [row for row in relay if row.get("event") == "frame"]
    shifted = [row for row in frames if row.get("shifted") is True]
    assert len(frames) == 2350 and len(shifted) == 50
    assert {row["dz"] for row in shifted} == {0.5}
    assert summary["detection_enabled"] is False
    assert summary["gate"]["accepted"] == 0
    assert summary["message_disposition"]["repair"]["clouds_published"] == 0
    assert summary["native_checkpoint"]["reprocesses"] == 0
    assert summary["lifecycle"]["unresolved_segments"] == 1
    assert summary["terminal_reason"] == "INPUT_STALE"
    assert len(summary["scripted_triggers"]["fired"]) == 2

    rows = []
    for i in range(2):
        candidate = candidates[i]
        ep = summary["quarantine"]["episode_detail"][i]
        evidence = ep["paired_evidence"]
        anchor_ts = int(ep["incumbent_basis"]["anchor_timestamp_ns"])
        first_ts = int(details[i]["candidate_frame_ts_ns"][0])
        elapsed = (first_ts - anchor_ts) / 1e9
        envelope = 0.5 + 2.0 * elapsed
        jump = float(candidate["reentry_pos_jump_m"])
        rows.append({
            "candidate_id": candidate["candidate_id"],
            "icp_status": icp[i]["status"],
            "icp_inliers": icp[i]["icp_inliers"],
            "improved_frames": evidence["num_improved_frames"],
            "paired_frames": evidence["num_paired_frames"],
            "incumbent_mean_residual": evidence["incumbent_mean_residual"],
            "candidate_mean_residual": evidence["candidate_mean_residual"],
            "wilson_lower_bound": evidence["wilson_lower_bound"],
            "info_before": candidate["weak_dir_info_before"],
            "info_after": candidate["weak_dir_info_after"],
            "info_kappa_pass": candidate["weak_dir_info_after"] >= 2.0 * candidate["weak_dir_info_before"],
            "holdout_nis": candidate["holdout_nis"],
            "holdout_pass": candidate["holdout_nis"] <= 2.5,
            "reentry_elapsed_s": elapsed,
            "reentry_envelope_m": envelope,
            "reentry_jump_m": jump,
            "reentry_envelope_pass": jump <= envelope,
            "checkpoint_check": ep["checkpoint_check"],
            "accepted": candidate["accepted"],
        })
    assert rows[0]["icp_status"] == "TOO_FEW_INLIERS"
    assert rows[0]["icp_inliers"] == 0
    assert rows[0]["candidate_mean_residual"] == rows[0]["incumbent_mean_residual"]
    assert rows[0]["improved_frames"] == 0 and rows[0]["paired_frames"] == 8
    assert rows[0]["checkpoint_check"]["status"] == "AT_OR_BEFORE_BOUNDARY"
    assert rows[1]["icp_status"] == "ITERATION_LIMIT"
    assert rows[1]["candidate_mean_residual"] > rows[1]["incumbent_mean_residual"]
    assert rows[1]["improved_frames"] == 0 and rows[1]["paired_frames"] == 22
    assert rows[1]["checkpoint_check"]["status"] == "LATE_AFTER_BOUNDARY"
    assert all(row["info_kappa_pass"] for row in rows)
    assert not any(row["holdout_pass"] for row in rows)
    assert all(row["reentry_envelope_pass"] for row in rows)
    assert not any(row["accepted"] for row in rows)

    result = {
        "reviewed_ref": REF,
        "scope": "read-only archived run and source; no ROS, rebuild, new run, or algorithm execution",
        "injection": {"frame_records": len(frames), "shifted_frames": len(shifted), "body_z_m": 0.5},
        "events": rows,
        "lifecycle": {
            "final_state": summary["final_state"],
            "quarantine_open_at_exit": summary["quarantine_open_at_exit"],
            "unresolved_segments": summary["lifecycle"]["unresolved_segments"],
            "terminal_reason": summary["terminal_reason"],
            "repair_clouds_published": 0,
            "reprocesses": 0,
            "automatic_detection": "NOT_EXECUTED",
        },
        "interpretation": {
            "option3": "a preregistered stop/closure decision, not accepted recovery or proof that repair is scientifically impossible",
            "E1": "candidate generation failed and returned incumbent; zero measured benefit does not prove zero improvable error",
            "reentry": "both events pass the elapsed-time envelope; 0.5 m is not the sole or current binding constraint",
            "other_gates": "both events fail Wilson and holdout NIS; E2 checkpoint is also late",
        },
        "verdict": "REAL_NEGATIVE_RESULT_AND_PARTIAL_LIFECYCLE_EVIDENCE; NO_ACCEPTED_NATIVE_REPAIR",
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("review_checks.json")
    assert not output.exists(), "refuse to overwrite %s" % output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
