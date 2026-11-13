"""18:00 FAST-LIO deadline inventory fixed to main 5494cdb; no host execution."""
import collections
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = "5494cdbd324377de9cfcfa1392f4bd56cf3a28f8"
POST = "d9e4f34c251a526f3c0aa2cd4beb5a4dc074f6ea"
BASE = "docs/four_host/fastlio_recovery_20261113/"
RUN = BASE + "two_event_drain_authorized/"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def blob(ref, path):
    return git("show", ref + ":" + path)


def main():
    summary = json.loads(blob(MAIN, RUN + "run_summary.json"))
    pre = blob(MAIN, RUN + "pre_run.txt").decode()
    caps = json.loads(blob(MAIN, RUN + "ctl/capabilities.json"))
    candidate = json.loads(blob(MAIN, RUN + "candidates.jsonl"))
    fates_rows = [json.loads(x) for x in blob(MAIN, RUN + "ctl/input_fates.jsonl").decode().splitlines() if x]
    fates = collections.Counter(r["fate"] for r in fates_rows)
    f2 = json.loads(blob(MAIN, "docs/ali_h_v1_research/f2_selftest.json"))
    assert len(summary["scripted_triggers"]["fired"]) == 2
    assert summary["quarantine"]["episodes"] == 2
    assert summary["quarantine"]["decisions"] == 1
    assert summary["quarantine"]["second_and_later_events"] == 1
    assert candidate["accepted"] is False
    assert summary["final_state"] == "WAITING_FOR_EVIDENCE"
    assert summary["quarantine_open_at_exit"] is True
    assert summary["run_mode"] == "CONTROLLED_INTERFACE_TEST"
    commands = collections.Counter(a.get("command") for a in summary["native_checkpoint_actions"])
    assert commands.get("reprocess", 0) == 0
    restores = [a for a in summary["native_checkpoint_actions"] if a.get("command") == "restore"]
    assert len(restores) == 1 and "valid=0" in restores[0]["ack"]
    assert "checkpoint_invalidated_by_re_slam" in restores[0]["ack"]
    ep2 = summary["quarantine"]["episode_detail"][1]
    assert ep2["restore_disposition"]["scope"] == "STATE_AND_MAP_ROLLBACK_ONLY"
    assert ep2["restore_disposition"]["subsequent_input"] == "CONTINUES_FROM_RESTORED_STATE"
    assert fates == {"ingested": 1269, "quarantined": 982}
    assert f2["pass"] and len(f2["cases"]) == 11
    post_files = git("diff", "--name-only", MAIN, POST).decode().splitlines()
    assert post_files == ["docs/COLLABORATION_STATUS.md", "docs/TODO_PRIORITIES_20261113.md"]

    result = {
        "deadline_utc8": "2026-11-13T18:00:00+08:00",
        "deadline_main": MAIN,
        "post_deadline_main_checked": POST,
        "post_deadline_changes": post_files,
        "post_deadline_has_new_code_or_run": False,
        "run_identity": {
            "pre_run": pre,
            "host": "MM-LINS-derived FAST-LIO frontend, not independently verified upstream FAST-LIO2",
            "binary_sha_v7": "a40e20d516b14914728c98baf6b8807868bd6eb9b6f47523818c4caf1d7f0852",
            "bag_sha": "a924b5f9b593fad111f2ef91197735b85c8d26d340f04d5ca61535f25eaaf2de",
            "driver_identity": "0b4dc78+ (short-plus declaration, not a full immutable SHA)",
            "config_source_identity": "INCOMPLETE_IN_PRE_RUN",
        },
        "events": {
            "fired": summary["scripted_triggers"]["fired"],
            "mode": summary["run_mode"],
            "episodes": summary["quarantine"]["episodes"],
            "decisions": summary["quarantine"]["decisions"],
            "second_and_later_events": summary["quarantine"]["second_and_later_events"],
            "E1": "HOST_NATIVE_RECOVERY_TAKEOVER; segment_abandoned",
            "E2": {"candidate_id": candidate["candidate_id"], "mode": candidate["mode"],
                   "accepted": candidate["accepted"], "refusal": candidate["refusal_reason"],
                   "paired_evidence": ep2["paired_evidence"]},
            "automatic_detection": "NOT_EXECUTED; both triggers are scripted",
        },
        "native": {
            "capabilities": caps,
            "restore_ack": restores[0]["ack"],
            "restore_disposition_in_driver": ep2["restore_disposition"],
            "reprocess_count": commands.get("reprocess", 0),
            "repair_clouds_published": summary["message_disposition"]["repair"]["clouds_published"],
            "actual_repair_native_update_map": "NOT_EXECUTED_IN_THIS_RUN",
            "controlled_ctrl2_partial_replay_is_separate_evidence": True,
        },
        "input_and_tail": {
            "driver": summary["message_disposition"],
            "host_fates": dict(fates),
            "final_state": summary["final_state"],
            "quarantine_open_at_exit": summary["quarantine_open_at_exit"],
            "tail_closed": False,
            "non_realtime": True,
        },
        "ali_h": {
            "reader_synthetic_cases": len(f2["cases"]),
            "reader_synthetic_pass": f2["pass"],
            "real_FAST_LIO_M_I_export": "NOT_DELIVERED",
            "T": "NOT_APPLICABLE_BY_F2_HOST_STRUCTURE_ASSESSMENT",
            "independent_normal_prefix": "NOT_AVAILABLE",
            "independent_fault_labels": "NOT_AVAILABLE",
            "same_population_old_vs_ALI_H": "NOT_EXECUTED",
            "recall_false_alarm_latency_error_NORMAL": "NOT_EVALUABLE",
            "UNKNOWN_intervals_from_real_FAST_LIO": "NOT_EVALUABLE",
        },
        "cost": {
            "runtime_driver_pid_scope": summary["runtime"],
            "frame_cost_breakdown": summary.get("frame_cost_breakdown"),
            "non_realtime_drain": True,
            "whole_chain_peak_and_monetary_cost": "UNAVAILABLE",
            "resource_metrics_are_diagnostic_not_gates": True,
        },
        "overall": "PARTIAL_FUNCTIONAL_PROGRESS; FULL_ALI_AUTODETECTION_AND_RECOVERY_GOAL_NOT_COMPLETE",
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("deadline_evidence.json")
    assert not output.exists(), f"refuse to overwrite {output}"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
