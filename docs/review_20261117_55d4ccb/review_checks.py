"""Read-only checks for the two-hour review ending at main 55d4ccb."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REF = "55d4ccb477893bf93f52b2df780304e4d480a6e3"
SMOKE = "docs/four_host/fastlio_recovery_20261113/host_smoke7_v9_authorized/"
CLOSURE = "docs/ali_h_v1_research/ALI_H_FINAL_CLOSURE_20261117.md"


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", REF + ":" + path])


def main():
    rows = [json.loads(x) for x in blob(SMOKE + "smoke7.jsonl").decode().splitlines() if x]
    assert [r["step"] for r in rows] == [
        "status", "capabilities", "hold", "snapshot", "restore", "reprocess", "resume"]
    assert "valid=1" in rows[2]["ack"]
    assert "valid=1" in rows[3]["ack"]
    assert "valid=1" in rows[4]["ack"]
    assert "replay_suffix=0" in rows[5]["ack"]
    assert "repaired_fed=0" in rows[5]["ack"]
    assert "valid=1" in rows[6]["ack"]
    caps = json.loads(blob(SMOKE + "ctl/capabilities.json"))
    assert "imu_preintegration_cache" in caps["checkpoint_excludes"]
    assert "deskew_cache" in caps["checkpoint_excludes"]

    closure = blob(CLOSURE).decode()
    assert "C2（独立正常前缀）`BLOCKED`" in closure
    assert "C3（声明式注入标签）`BLOCKED`" in closure
    assert "C4（检测指标：召回/延迟/误报/错误 NORMAL）`NOT_EVALUABLE`" in closure
    assert "106 块 / 53.0 s 全部 UNKNOWN" in closure
    assert "没有" and "新增运行、注入、数据或外部参考" in closure

    abstract = blob("paper_main.tex").decode()
    assert "No native accepted repair commit was obtained." in abstract
    assert "offline-constructed candidate" in abstract
    assert "0.5+2.0" in abstract

    result = {
        "reviewed_ref": REF,
        "window_utc8": "2026-11-17 08:37–11:10",
        "host_smoke": {
            "steps": [r["step"] for r in rows],
            "hold_snapshot_restore_resume_valid": True,
            "reprocess_ack": rows[5]["ack"],
            "accepted_meaning": "command/ACK path only; zero replay content and no repair cloud",
            "checkpoint_excludes": caps["checkpoint_excludes"],
        },
        "ali_h": {
            "C2": "BLOCKED",
            "C3": "BLOCKED",
            "C4": "NOT_EVALUABLE",
            "new_run_injection_data_or_external_reference": False,
            "all_UNKNOWN_means_zero_risk": False,
        },
        "paper": {
            "abstract_explicitly_no_native_accepted_commit": True,
            "reentry_elapsed_envelope_present": True,
            "scope": "limited factual and claim corrections, not new scientific evidence or full paper validation",
        },
        "verdict": "PARTIAL_MAINLINE_PROGRESS; INTERFACE_AND_FAILURE_SEMANTICS_ADVANCED_WITHOUT_ACCEPTED_REPAIR",
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("review_checks.json")
    assert not output.exists(), "refuse to overwrite %s" % output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
