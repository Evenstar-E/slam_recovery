"""Focused controls for main a355343; fixed Git objects, no host or production edits.

Exit 0 means the controls ran. CONFIRMED findings reproduce defects in that fixed version;
they are not project PASS results. The F2 reader and its T2 dependency are materialized in a
new temporary directory and imported explicitly under Python -I. The driver accounting function
is AST-isolated so this check does not import or run the ROS driver.
"""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import site
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Any, Dict

# Python -I omits the existing per-user packages. Add that known local NumPy location
# explicitly; do not install anything or execute modules from the input/export directory.
USER_SITE = Path(site.getusersitepackages())
if USER_SITE.is_dir():
    sys.path.insert(0, str(USER_SITE))

ROOT = Path(__file__).resolve().parents[2]
OLD = "6b3c7f2610e4dd601a7a2cbca9efa45b527943c0"
MAIN = "a355343711cf8e8daf71eadbd68677ab4bf7bddb"
F1_BRANCH_AT_FETCH = "a4c652fcda5131988dbbcd9feb82743b4e69fe80"
HASHES = {}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def blob(path):
    raw = git("show", MAIN + ":" + path)
    HASHES[path] = hashlib.sha256(raw).hexdigest()
    return raw


def make_loop(episodes, records, ingested):
    pairer = SimpleNamespace(
        poses_received=ingested,
        scans_received=ingested,
        paired=ingested,
        poses_unpaired=0,
        scans_unpaired=0,
        stamp_log_cap=100000,
    )
    return SimpleNamespace(next_kf_id=ingested, episodes=episodes,
                           records=records, pairer=pairer)


def episode(decided, meta):
    return SimpleNamespace(frames=[(0, 1000, None)], decided=decided, meta=meta)


def main():
    changed = git("diff", "--name-only", OLD, MAIN).decode().splitlines()
    assert changed == [
        "docs/COLLABORATION_STATUS.md",
        "docs/FASTLIO_ALI_AUTODETECTION_E2_TASK_20261113.md",
        "docs/ali_h_v1_research/F2_FASTLIO_CHANNEL_ELIGIBILITY.md",
        "docs/ali_h_v1_research/f2_fastlio_read.py",
        "docs/ali_h_v1_research/f2_selftest.json",
        "slam_recovery/ros/recovery_node.py",
        "slam_recovery/tests/test_host_capabilities.py",
    ]
    f1_now = git("rev-parse", "origin/exp/growth-run").decode().strip()

    # Execute the actual F2 selftest from the fixed commit in an isolated temporary directory.
    with tempfile.TemporaryDirectory(prefix="review-a355-f2-") as td:
        td = Path(td)
        (td / "f2_fastlio_read.py").write_bytes(
            blob("docs/ali_h_v1_research/f2_fastlio_read.py"))
        (td / "t2_run.py").write_bytes(blob("docs/ali_h_v1_research/t2_run.py"))
        spec = importlib.util.spec_from_file_location(
            "f2_review_a355", td / "f2_fastlio_read.py")
        f2 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(f2)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            selftest_rc = f2.selftest()
        selftest = json.loads(captured.getvalue())
        assert selftest_rc == 0 and selftest["pass"] is True

        pose = {"x": 0, "y": 0, "z": 0, "qx": 0, "qy": 0, "qz": 0, "qw": 1}

        def row(uid, run_id="A", **extra):
            value = {"update_id": uid, "lidar_beg_ns": uid * 1000,
                     "has_out": 1, "eff": 100, "pre": dict(pose), "post": dict(pose)}
            if run_id is not None:
                value["run_id"] = run_id
            value.update(extra)
            return value

        def summary(rows):
            q = f2.qualify(rows)
            return q, f2.summarize(q, f2.blocks(q["rows"]))

        # A missing required run_id is omitted from run_ids, so identity and pairing can pass.
        q_missing, s_missing = summary([row(1), row(2, run_id=None)])
        missing_run_repro = (
            s_missing["mixed_run_ids"] is False
            and s_missing["qualification"]["SAME_UPDATE_ID_PAIRING"] == "PASS"
            and s_missing["I_rows"] == 2
            and q_missing["counts"].get("OK") == 2
        )
        assert missing_run_repro

        # The qualification expression only needs one OK row; a NO_PAIR row can coexist with PASS.
        broken = row(2)
        broken.pop("post")
        q_pair, s_pair = summary([row(1), broken])
        no_pair_repro = (
            q_pair["counts"].get("NO_PAIR") == 1
            and s_pair["qualification"]["SAME_UPDATE_ID_PAIRING"] == "PASS"
        )
        assert no_pair_repro

        # The protocol requires 200 samples, but a fraction without n is accepted as SUPPORTED.
        q_support, _ = summary([row(1, support={"pass_fraction": 1.0})])
        support_repro = q_support["rows"][0]["support"] == "SUPPORTED"
        assert support_repro

    # Isolate only the new accounting function; no ROS import or archived driver execution.
    driver_path = "slam_recovery/ros/recovery_node.py"
    driver = blob(driver_path).decode()
    tree = ast.parse(driver)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "message_disposition")
    namespace = {"Dict": Dict, "Any": Any, "NativeClosedLoop": object}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), driver_path, "exec"), namespace)
    disposition = namespace["message_disposition"]

    skipped = disposition(make_loop([
        episode(True, {"decision_skipped": "SEGMENT_CLOSED_BEFORE_DECISION"})], [], 1))
    skipped_k = skipped["keyframes"]
    skipped_accounted = (skipped_k["never_quarantined"] + skipped_k["committed_distinct"]
                         + skipped_k["deferred_distinct"]
                         + skipped_k["pending_at_exit_memberships"])
    skipped_repro = skipped_accounted == 0 and skipped["unresolved"] == []
    assert skipped_repro

    overlap = disposition(make_loop([
        episode(True, {}), episode(False, {})],
        [{"committed_pose_keys": [0], "deferred_pose_keys": []}], 1))
    overlap_k = overlap["keyframes"]
    overlap_accounted = (overlap_k["never_quarantined"] + overlap_k["committed_distinct"]
                         + overlap_k["deferred_distinct"]
                         + overlap_k["pending_at_exit_memberships"])
    overlap_repro = overlap_accounted == 2 and overlap["unresolved"] == []
    assert overlap_repro

    result = {
        "reviewed_main": MAIN,
        "comparison": OLD,
        "command": "C:/Python315/python.exe -I -B docs/review_20261113_a355343/run_checks.py <new-json>",
        "scope": "fixed source, actual F2 selftest and ordinary counterexamples; no ROS/host/algorithm run",
        "changed_paths": changed,
        "task_acceptance": "CONFIRMED_FROM_MAIN_COLLABORATION_STATUS_178",
        "f2_selftest": {"exit": selftest_rc, "pass": selftest["pass"],
                        "cases": len(selftest["cases"])},
        "f1_growth_branch_at_fetch": F1_BRANCH_AT_FETCH,
        "f1_growth_branch_observed_now": f1_now,
        "f1_native_source_available_in_fetched_growth_branch": f1_now != F1_BRANCH_AT_FETCH,
        "findings": {
            "F2_MISSING_RUN_ID_ACCEPTED": {
                "status": "CONFIRMED" if missing_run_repro else "NOT_REPRODUCED",
                "actual": {"mixed_run_ids": s_missing["mixed_run_ids"],
                           "pairing": s_missing["qualification"]["SAME_UPDATE_ID_PAIRING"],
                           "I_rows": s_missing["I_rows"],
                           "row_status": q_missing["counts"]},
                "expected": "missing required run_id must invalidate identity and exclude pairing PASS",
            },
            "F2_NO_PAIR_COEXISTS_WITH_PAIRING_PASS": {
                "status": "CONFIRMED" if no_pair_repro else "NOT_REPRODUCED",
                "actual": {"pairing": s_pair["qualification"]["SAME_UPDATE_ID_PAIRING"],
                           "row_status": q_pair["counts"]},
                "expected": "complete-pair qualification cannot PASS with a required post missing",
            },
            "F2_SUPPORT_WITHOUT_SAMPLE_COUNT_SUPPORTED": {
                "status": "CONFIRMED" if support_repro else "NOT_REPRODUCED",
                "actual": q_support["rows"][0]["support"],
                "input_support": {"pass_fraction": 1.0},
                "expected": "UNKNOWN_CONTEXT without the declared 200-sample support",
            },
            "F3_SKIPPED_EPISODE_NOT_UNRESOLVED": {
                "status": "CONFIRMED" if skipped_repro else "NOT_REPRODUCED",
                "ingested": skipped_k["ingested"],
                "sum_of_four_declared_categories": skipped_accounted,
                "unresolved": skipped["unresolved"],
                "segments_decision_skipped": skipped_k["segments_decision_skipped"],
            },
            "F3_OVERLAP_DOUBLE_COUNT_NOT_UNRESOLVED": {
                "status": "CONFIRMED" if overlap_repro else "NOT_REPRODUCED",
                "ingested": overlap_k["ingested"],
                "sum_of_four_declared_categories": overlap_accounted,
                "unresolved": overlap["unresolved"],
            },
        },
        "hashes": HASHES,
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("local_checks.json")
    assert not output.exists(), f"refuse to overwrite {output}"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
