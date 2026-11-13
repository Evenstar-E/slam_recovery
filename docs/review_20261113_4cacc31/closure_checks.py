"""Closure checks for main 4cacc31; fixed blobs, no ROS/host/build.

The F2 reader is self-tested in an isolated temporary directory. Driver functions/classes are
AST-isolated to exercise the exact current implementation without importing ROS. Exit 0 means
checks ran; CLOSED and CONFIRMED are findings about the fixed version, not project-wide scores.
"""
import ast
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import site
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

USER_SITE = Path(site.getusersitepackages())
if USER_SITE.is_dir():
    sys.path.insert(0, str(USER_SITE))

ROOT = Path(__file__).resolve().parents[2]
MAIN = "4cacc31d8d904102eeceabb812c3e5d81959a01a"
V4 = "docs/four_host/fastlio_recovery_20261113/native_recovery_v4.diff"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def blob(path):
    return git("show", MAIN + ":" + path)


def extract(path, names, namespace):
    tree = ast.parse(blob(path).decode())
    nodes = [n for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, "exec"), namespace)
    return namespace


def episode(idx, decided, skipped=False):
    return SimpleNamespace(candidate_id=idx, frames=[(0, 1000, None)], decided=decided,
                           meta={"decision_skipped": "SEGMENT_CLOSED_BEFORE_DECISION"} if skipped else {})


def loop(episodes, records):
    pairer = SimpleNamespace(poses_received=1, scans_received=1, paired=1,
                             poses_unpaired=0, scans_unpaired=0, stamp_log_cap=1000)
    return SimpleNamespace(next_kf_id=1, episodes=episodes, records=records, pairer=pairer)


def main():
    result = {"main": MAIN, "scope": "fixed source and local controls; no host/build/algorithm edit"}
    with tempfile.TemporaryDirectory(prefix="review-4cacc-f2-") as td:
        td = Path(td)
        (td / "f2_fastlio_read.py").write_bytes(blob("docs/ali_h_v1_research/f2_fastlio_read.py"))
        (td / "t2_run.py").write_bytes(blob("docs/ali_h_v1_research/t2_run.py"))
        spec = importlib.util.spec_from_file_location("f2_review_4cacc", td / "f2_fastlio_read.py")
        f2 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(f2)
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            rc = f2.selftest()
        selftest = json.loads(capture.getvalue())
        assert rc == 0 and selftest["pass"] and len(selftest["cases"]) == 11
        for key, expected in (("missing_run_id", "INCOMPLETE_MISSING_RUN_ID"),
                              ("missing_post", "INCOMPLETE_MISSING_PAIR"),
                              ("support_fraction_only", "UNKNOWN_CONTEXT")):
            case = selftest["cases"][key]
            actual = case.get("pairing", case.get("class"))
            assert case["pass"] and actual == expected
        result["f2_previous_three_counterexamples"] = {
            "status": "CLOSED_AT_SOURCE_AND_SYNTHETIC_CONTROL",
            "selftest_cases": len(selftest["cases"]),
            "missing_run_id": selftest["cases"]["missing_run_id"],
            "missing_post": selftest["cases"]["missing_post"],
            "support_fraction_only": selftest["cases"]["support_fraction_only"],
        }

    driver_path = "slam_recovery/ros/recovery_node.py"
    ns = {"Dict": Dict, "Any": Any, "NativeClosedLoop": object}
    extract(driver_path, ["message_disposition"], ns)
    disposition = ns["message_disposition"]
    skipped = disposition(loop([episode(0, True, True)], []))
    assert skipped["keyframes"]["skipped"] == 1
    assert skipped["fully_accounted"] and not skipped["fully_decided"]
    accepted = {"candidate_id": 0, "accepted": True,
                "committed_pose_keys": [0], "deferred_pose_keys": []}
    overlap = disposition(loop([episode(0, True), episode(1, False)], [accepted]))
    assert not overlap["fully_accounted"]
    assert any(x["kind"] == "key_with_more_than_one_outcome" for x in overlap["unresolved"])
    result["f3_driver_disposition_counterexamples"] = {
        "status": "CLOSED_FOR_DRIVER_SIDE_CONTROLS",
        "skipped": skipped,
        "overlap": overlap,
        "cross_layer_host_fate_join": "NOT_IMPLEMENTED_IN_DRIVER; next run still needs host/driver reconciliation",
    }

    # Reproduce the two-command arming order with the exact current CheckpointClient.
    ns = {"Optional": Optional, "Dict": Dict, "Any": Any, "Tuple": Tuple, "List": List,
          "os": os, "json": json, "time": time, "threading": threading}
    extract(driver_path, ["HostCapabilities", "CheckpointClient"], ns)
    with tempfile.TemporaryDirectory(prefix="review-4cacc-ack-") as td:
        client = ns["CheckpointClient"](td, ack_timeout_s=0.1)
        hold = client.hold(123)
        snapshot = client.snapshot_now(123)
        cmd = Path(td) / "cmd"
        ack = Path(td) / "ack"
        assert cmd.read_text().splitlines()[0] == "hold"
        assert len(client._outbox) == 1
        ack.write_text("OK hold deferred stamp=123\n")
        assert client.poll() is None
        assert hold["armed"] and "ok" not in hold
        assert len(client._outbox) == 1
        assert cmd.read_text().splitlines()[0] == "hold"
        snapshot_sent_after_deferred = cmd.read_text().splitlines()[0] == "snapshot"
        ack.write_text("OK hold applied valid=1 stamp_ns=100 frame=9 map_writes=held\n")
        done = client.poll()
        assert done is hold and hold["ok"]
        assert cmd.read_text().splitlines()[0] == "snapshot"
        assert not snapshot_sent_after_deferred
        result["same_boundary_hold_snapshot_sequence"] = {
            "status": "CONFIRMED_SNAPSHOT_NOT_SENT_UNTIL_HOLD_APPLIED",
            "after_deferred": {"hold_armed": True, "hold_completed": False,
                               "outbox": 1, "host_command_file": "hold"},
            "after_applied": {"hold_completed": True, "host_command_file": "snapshot"},
            "impact": "same-target snapshot is not pre-armed with hold; v4 can snapshot a later completed frame",
        }

    driver = blob(driver_path).decode()
    v4 = blob(V4).decode()
    assert "nr_apply_deferred(lidar_end_time);" in v4
    assert "g_nr_cp.stamp = g_nr_lidar_end;" in v4
    assert "g_nr_repaired_in_update" in v4 and "repaired_in_update=" in v4
    assert 'ep.meta["repair_entered_estimator"] = bool(fed > 0)' in driver
    assert "repaired_in_update" not in driver
    result["repair_update_receipt_integration"] = {
        "status": "NOT_CLOSED_DRIVER_STILL_USES_QUEUE_COUNT",
        "host_v4_exposes_repaired_in_update": True,
        "driver_consumes_repaired_in_update": False,
        "driver_sets_repair_entered_estimator_from": "repaired_fed",
    }
    result["v4_execution"] = "NOT_BUILT_NOT_RUN; offline source contracts are not native behavior evidence"
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("closure_checks.json")
    assert not output.exists(), f"refuse to overwrite {output}"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
