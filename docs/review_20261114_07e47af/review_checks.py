"""Read-only gate-leg checks for the two-hour review ending at main 07e47af."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REF = "07e47af8286a2801f967a5bdbb5e9e6764ae881a"
RUN = "docs/four_host/fastlio_recovery_20261113/two_event_v9i_seq2_hostposes_authorized/"


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", REF + ":" + path])


def main():
    summary = json.loads(blob(RUN + "run_summary.json"))
    candidates = [json.loads(x) for x in blob(RUN + "candidates.jsonl").decode().splitlines() if x]
    details = [json.loads(x) for x in blob(RUN + "candidates_detail.jsonl").decode().splitlines() if x]
    assert summary["candidate_source"] == "host_poses"
    assert summary["detection_enabled"] is False
    assert summary["gate"]["accepted"] == 0
    assert summary["message_disposition"]["repair"]["clouds_published"] == 0
    assert summary["native_checkpoint"]["reprocesses"] == 0
    assert len(summary["scripted_triggers"]["fired"]) == 2
    assert summary["lifecycle"]["unresolved_segments"] == 2
    assert candidates[0]["paired_benefit_status"] == "PASSED"
    assert candidates[1]["paired_benefit_status"] == "FAILED"
    assert all(row["accepted"] is False for row in candidates)
    assert "boundary jump" not in candidates[0]["refusal_reason"]
    assert "boundary jump" in candidates[1]["refusal_reason"]

    rows = []
    for i in range(2):
        ep = summary["quarantine"]["episode_detail"][i]
        candidate = candidates[i]
        anchor_ts = int(ep["incumbent_basis"]["anchor_timestamp_ns"])
        first_ts = int(details[i]["candidate_frame_ts_ns"][0])
        elapsed_s = (first_ts - anchor_ts) / 1e9
        envelope_m = 0.5 + 2.0 * elapsed_s
        jump = float(candidate["reentry_pos_jump_m"])
        info_before = float(candidate["weak_dir_info_before"])
        info_after = float(candidate["weak_dir_info_after"])
        info_required = 2.0 * info_before
        holdout = float(candidate["holdout_nis"])
        rows.append({
            "candidate_id": candidate["candidate_id"],
            "candidate_source": candidate["candidate_source"],
            "paired_benefit_status": candidate["paired_benefit_status"],
            "wilson_lower_bound": candidate["wilson_lower_bound"],
            "num_improved_frames": ep["paired_evidence"]["num_improved_frames"],
            "num_paired_frames": ep["paired_evidence"]["num_paired_frames"],
            "reentry_elapsed_s": elapsed_s,
            "reentry_envelope_m": envelope_m,
            "reentry_jump_m": jump,
            "reentry_envelope_pass": jump <= envelope_m,
            "info_before": info_before,
            "info_after": info_after,
            "info_kappa_required": info_required,
            "info_kappa_pass": info_after >= info_required,
            "holdout_nis": holdout,
            "holdout_max": 2.5,
            "holdout_pass": holdout <= 2.5,
            "checkpoint_status": ep["checkpoint_check"]["status"],
            "accepted": candidate["accepted"],
            "refusal_reason": candidate["refusal_reason"],
        })
    assert rows[0]["reentry_envelope_pass"] is True
    assert rows[1]["reentry_envelope_pass"] is False
    assert all(row["info_kappa_pass"] is False for row in rows)
    assert all(row["holdout_pass"] is False for row in rows)
    assert all(row["checkpoint_status"] == "LATE_AFTER_BOUNDARY" for row in rows)
    assert summary["scripted_triggers"]["armed_boundaries"][1]["lead_s"] < 0

    result = {
        "reviewed_ref": REF,
        "window_utc8": "2026-11-14 19:24–21:24",
        "scope": "read-only archived evidence and source; no ROS, rebuild, new run, or algorithm execution",
        "latest_run": summary["run_id"],
        "gate_legs": rows,
        "correction": "E1 reentry passes the elapsed-time envelope; both events also fail information-kappa and holdout-NIS, so 0.5 m reentry is not the sole binding constraint",
        "accepted_native_repair": {
            "accepted_candidates": 0,
            "repair_clouds_published": 0,
            "reprocesses": 0,
            "unresolved_segments": summary["lifecycle"]["unresolved_segments"],
        },
        "interpretation": "host_poses beating constant-velocity extrapolation is real paired-benefit progress, not accepted measurement repair or proof of map benefit",
        "verdict": "PARTIAL_MAINLINE_PROGRESS; PAIRED_BENEFIT_FIRST_PASS_WITHOUT_NATIVE_COMMIT",
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("review_checks.json")
    assert not output.exists(), "refuse to overwrite %s" % output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
