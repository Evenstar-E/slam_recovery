"""Integration controls for main 73c9764; no ROS/host/build.

Uses the exact current CheckpointClient and NativeClosedLoop receipt method, AST-isolated from
ROS. Exit 0 means the deterministic controls ran, not that the recovery chain passed.
"""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
MAIN = "73c97643b08a3e4efc91f6a14b1093fdf79779ce"
DRIVER = "slam_recovery/ros/recovery_node.py"


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", MAIN + ":" + path])


def namespace():
    return {"Optional": Optional, "Dict": Dict, "Any": Any, "Tuple": Tuple, "List": List,
            "os": os, "json": json, "time": time, "threading": threading}


def main():
    tree = ast.parse(blob(DRIVER).decode())
    client_nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)
                    and n.name in ("HostCapabilities", "CheckpointClient")]
    ns = namespace()
    exec(compile(ast.Module(body=client_nodes, type_ignores=[]), DRIVER, "exec"), ns)
    Client = ns["CheckpointClient"]

    with tempfile.TemporaryDirectory(prefix="review-73c-pair-") as td:
        client = Client(td, ack_timeout_s=0.05)
        hold = client.hold(123)
        snap = client.snapshot_now(123)
        cmd = Path(td) / "cmd"
        received = Path(td) / "ack_received"
        ack = Path(td) / "ack"
        received.write_text(f"RECEIVED hold wall={time.time():.6f}\n")
        assert client.poll() is None
        assert cmd.read_text().splitlines()[0] == "snapshot"
        assert len(client._pending) == 2 and not client._outbox
        # The real host executes a FIFO `due` batch in one call and writes one shared ack file.
        # If the client does not read between the two writes, only this final snapshot ack remains.
        ack.write_text("OK snapshot applied valid=1 stamp_ns=100 frame=9 map_points=42\n")
        got = client.poll()
        assert got is None
        assert len(client._pending) == 2
        assert "ok" not in hold and "ok" not in snap
        pair = {
            "status": "CONFIRMED_OLDEST_COMMAND_BLOCKED_BY_LAST_WRITE_ACK",
            "host_command_file_after_receive": "snapshot",
            "pending_after_coalesced_applied_writes": len(client._pending),
            "remaining_ack": ack.read_text().strip(),
            "hold_completed": hold.get("ok"),
            "snapshot_completed": snap.get("ok"),
            "poll_returned": got,
        }

    # The new fallback calls cp.status(), but the real CheckpointClient.status() is the local
    # summary method. It does not write a status command. Execute the actual receipt method.
    loop_class = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                      and n.name == "NativeClosedLoop")
    receipt_fn = next(n for n in loop_class.body if isinstance(n, ast.FunctionDef)
                      and n.name == "_read_status_update_receipt")
    ns2 = namespace()
    exec(compile(ast.Module(body=[receipt_fn], type_ignores=[]), DRIVER, "exec"), ns2)
    with tempfile.TemporaryDirectory(prefix="review-73c-status-") as td:
        client = Client(td, ack_timeout_s=0.01)
        stub = SimpleNamespace(cp=client, cp_actions=[])
        value = ns2["_read_status_update_receipt"](stub)
        assert value is None
        assert not (Path(td) / "cmd").exists()
        summary = client.status()
        assert summary["enabled"] is True and "events" in summary
        status = {
            "status": "CONFIRMED_FALLBACK_CALLS_SUMMARY_NOT_HOST_COMMAND",
            "receipt": value,
            "status_command_file_created": (Path(td) / "cmd").exists(),
            "real_status_method_keys": sorted(summary)[:8],
            "impact": "v4 repaired_in_update cannot be obtained through this fallback",
        }

    v4 = blob("docs/four_host/fastlio_recovery_20261113/native_recovery_v4.diff").decode()
    reprocess = v4[v4.index('else if (cmd == "reprocess")'):v4.index('else if (cmd == "capabilities")')]
    assert "repaired_fed=" in reprocess and "repaired_in_update=" not in reprocess
    result = {
        "main": MAIN,
        "scope": "exact current driver classes/method under deterministic file controls; no ROS/host/build",
        "paired_ack": pair,
        "update_receipt_fallback": status,
        "reprocess_ack_contains_update_receipt": False,
        "minimum_fix": "unique per-command applied receipts or atomic pair; issue a real status command and wait for the relevant replay/update boundary",
        "authorized_native_build_run_evidence": "NOT_DELIVERED_IN_THIS_REVIEWED_MAIN",
    }
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("integration_checks.json")
    assert not output.exists(), f"refuse to overwrite {output}"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
