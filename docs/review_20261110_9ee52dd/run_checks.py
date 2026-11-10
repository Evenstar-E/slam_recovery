"""Source-bound local controls for replacement episodes and runner records; no ROS/native run."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TARGET = "9ee52dde35af9a2ba020c54b74b09a3ba7756c95"
for path in ["slam_recovery/ros/recovery_node.py", "slam_recovery/ros/run_native_loop.sh",
             "slam_recovery/sim/transaction_manager_node.py", "slam_recovery/quarantine/manager.py"]:
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{TARGET}:{path}"])
    assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == expected
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import RecoveryState
from slam_recovery.ros.recovery_node import NativeClosedLoop
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.tests import test_lifecycle_rearm as tests

suite = unittest.TestSuite()
for cls in [tests.TestWaitLimit, tests.TestNodeRearm, tests.TestWaitClosesOnTheUndetectedPath]:
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()

class HostRecorder:
    enabled = True
    def __init__(self):
        self.commands = []
        self.held = False
    def hold(self):
        self.commands.append("hold")
        self.held = True
        return {"command": "hold", "ok": True}
    def resume(self):
        self.commands.append("resume")
        self.held = False
        return {"command": "resume", "ok": True}
    def collect(self, timeout_s=None):
        return None

# Reuse the old stale-decision fixture, now through actual loop episode/lifecycle wiring.
cloud = np.random.default_rng(0).normal(size=(400, 3)) * .16
node = OnlineRecoveryTransactionNode(wait_limit_sec=1.)
tests._open_waiting_segment(node.tx_mgr)
for key in [1, 2]:
    node.step_frame(key, key * 100_000_000, np.eye(4), cloud, 10.)
old_segment = node.tx_mgr.active_quarantine
host = HostRecorder()
loop = NativeClosedLoop(node, "review-only", checkpoint_client=host)
# Supply deterministic measured NIS and independent support to isolate lifecycle ordering.
loop.nis.measure = lambda *args, **kwargs: (10., "computed", "node_map")
loop.nis.support_reference = lambda *args, **kwargs: cloud
loop.on_pair(2_000_000_000, np.eye(4), cloud)
assert node.tx_mgr.active_quarantine is not old_segment
assert len(loop.episodes) == 1
assert node.tx_mgr.state == RecoveryState.QUARANTINED
assert node.detector.state == RecoveryState.HEALTHY
loop.service()
assert host.commands == ["hold", "resume"] and not host.held

source = (ROOT / "slam_recovery/ros/run_native_loop.sh").read_text(encoding="utf-8")
blocks = []
for part in source.split("<<'PY'\n")[1:]:
    blocks.append(part.split("\nPY", 1)[0])
receipt = next(b for b in blocks if "def sha(p):" in b)
wiring = next(b for b in blocks if "recorded_pgid = None" in b)
receipt_ast = ast.parse(receipt)
exit_expr = receipt_ast.body[-1]
assert isinstance(exit_expr, ast.Expr) and ast.unparse(exit_expr.value) == "sys.exit(0)"
# Read only the changed PGID section; execute with a fixture file and a dead-host result.
start = wiring.index('recovery_pgid = s.get("runtime", {}).get("pgid")')
end = wiring.index("\nchecks = {}", start)
selection = wiring[start:end]
with tempfile.TemporaryDirectory(prefix="review-pgid-") as directory:
    Path(directory, "runtime_pgid.txt").write_text("12345\n", encoding="utf-8")
    scope = {"os": os, "rd": directory, "s": {"runtime": {"pgid": 12345}},
             "host_pid": "dead-host-fixture", "pgid_of": lambda pid: None}
    exec(selection, scope)
    assert scope["host_pgid"] == 12345

print(json.dumps({
    "target": TARGET,
    "scope": "Four selected lifecycle tests, actual loop control with supplied NIS/support and simulated host, runner expression controls; no ROS/native/bag/tuning",
    "selected_tests": {"count": result.testsRun, "status": "PASS_LOCAL"},
    "replacement_episode": {"status": "PASS_LOCAL", "episodes": len(loop.episodes)},
    "same_frame_reopen": {"status": "FAIL_REPRODUCED_LOCAL", "manager_state": node.tx_mgr.state.value,
        "detector_state": node.detector.state.value, "detector_dwell": node.detector.suspect_dwell},
    "new_quarantine_release": {"status": "FAIL_REPRODUCED_LOCAL", "commands": host.commands,
        "simulated_host_held": host.held, "new_segment_active": node.tx_mgr.active_quarantine is not None,
        "limit": "Source ordering with simulated host, not measured native map pollution"},
    "runner_controls": {"receipt_write_exit": "PASS_LOCAL_ZERO_EXIT_PRESERVES_JSON_STATUS",
        "saved_pgid_dead_host": "PASS_LOCAL", "runner_overall_fail_check": "STATIC_PRESENT"},
    "developer_new_episode_test": "NOT_RUN_DEPENDS_ON_PYTEST_MODULE_IMPORT_AND_AFTER_FIRST_MAIN_GUARD",
    "third_run": "DEVELOPER_REPORTED_TWO_PREINJECTION_SEGMENTS_THIRD_WITHOUT_EPISODE_E2_NOT_TRIGGERED",
    "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED",
}, ensure_ascii=False, indent=2))
