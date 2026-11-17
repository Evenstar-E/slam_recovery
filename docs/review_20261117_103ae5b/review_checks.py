"""Read-only checks for closure and regenerated simulation at main 103ae5b."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REF = "103ae5bf6ac77d82bbe9cade640a2e8c58e32b6e"
CLOSURE = "docs/four_host/fastlio_recovery_20261113/FASTLIO2_OPTION3_CLOSURE_PACKAGE_20261117.md"
PROGRESS = "docs/FOUR_HOST_AB_PROGRESS_20261117.md"
MANIFEST = "slam_recovery/experiments/manifests/sim_s1_s2_counterfactual_and_3d_voxel_benchmark.json"


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", REF + ":" + path])


def main():
    closure = blob(CLOSURE).decode()
    progress = blob(PROGRESS).decode()
    manifest = json.loads(blob(MANIFEST))
    cases = manifest["S1_CrossScan_Holdout_Gate_Verification"]
    assert len(cases) == 5
    assert all(row["mode"] == "MODE3_SOFT_BRIDGE_WAIT" for row in cases.values())
    assert cases["R5_Delayed_Revisit_Loop"]["holdout_nis"] == 10.38
    assert cases["B5_Narrow_FoV_Filter_LIOSAM"]["holdout_nis"] == 17.856
    assert manifest["simulator_validity"]["status"] == "FAILED"
    assert manifest["simulator_validity"]["status_counts"]["FAILED"] == 5
    assert "accepted 测量修复提交：未获得" in closure
    assert "不支持对宿主+序列作一般「不可达」判断" in closure
    assert "replay_suffix=0" in closure
    assert "本表**不是新评分**" in progress
    assert "不把 `P` 当通过" in progress

    result = {
        "reviewed_ref": REF,
        "scope": "read-only archived documents and regenerated manifest; no host, simulation, build, or new run",
        "simulation": {
            "cases": {name: {"mode": row["mode"], "holdout_nis": row["holdout_nis"]}
                      for name, row in cases.items()},
            "simulator_validity": manifest["simulator_validity"]["status"],
            "all_mode3": True,
        },
        "closure": {
            "accepted_repair": False,
            "general_impossibility_claim": False,
            "reprocess_replay_suffix_zero_disclosed": True,
            "new_scientific_evidence": False,
        },
        "four_host_progress": {
            "new_score": False,
            "P_means_pass": False,
            "other_host_new_run": False,
        },
        "verdict": "CLOSURE_AND_SIMULATION_NEGATIVE_EVIDENCE_ADVANCED; ACCEPTED_NATIVE_REPAIR_NOT_REACHED",
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("review_checks.json")
    assert not output.exists(), "refuse to overwrite %s" % output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
