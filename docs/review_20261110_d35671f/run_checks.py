"""Small async-action controls, including simulated acceptance with the actual file client."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
TARGET = "d35671f97a54f611fef70318b7f0534d2011d470"
for path in ["slam_recovery/ros/recovery_node.py", "slam_recovery/tests/test_checkpoint_client.py"]:
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{TARGET}:{path}"])
    assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == expected
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import RecoveryState
from slam_recovery.ros.recovery_node import CheckpointClient, Episode, NativeClosedLoop
from slam_recovery.tests.test_checkpoint_client import CheckpointClientTest

suite = unittest.TestSuite(CheckpointClientTest(name) for name in [
    "test_received_is_recorded_before_applied", "test_a_silent_host_leaves_the_command_pending",
    "test_a_snapshot_never_blocks_the_caller"])
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()

with tempfile.TemporaryDirectory(prefix="received-review-") as directory:
    client = CheckpointClient(directory)
    event = client.restore()
    Path(directory, "ack_received").write_text(
        f"RECEIVED restore wall={event['wall'] + .01}\n", encoding="utf-8")
    assert client.poll() is None and client.pending() and "ok" not in event
    Path(directory, "ack").write_text("OK restore done\n", encoding="utf-8")
    assert client.poll() is event and event["ok"] and not client.pending()

with tempfile.TemporaryDirectory(prefix="accepted-async-review-") as directory:
    client = CheckpointClient(directory)
    manager = SimpleNamespace(trusted_poses={}, trusted_version=0, active_quarantine=None,
                              confirmation_margin_ns=2_000_000_000,
                              state=RecoveryState.HEALTHY, lifecycle_events=[])
    repaired = {1: np.eye(4), 2: np.eye(4)}
    repaired[1][0, 3], repaired[2][0, 3] = 1., 2.
    report = SimpleNamespace(accepted=True, mode="MODE2", reason="simulated partial acceptance",
                             committed_pose_keys=[1], deferred_pose_keys=[2],
                             partial_commit=True, evidence_status="PASSED")
    def evaluate(candidate_id, poses, **kwargs):
        manager.trusted_poses = {1: poses[1].copy()}
        manager.trusted_version += 1
        manager.active_quarantine = object()
        manager.state = RecoveryState.WAITING_FOR_EVIDENCE
        return report
    node = SimpleNamespace(tx_mgr=manager, sigma_meas_m=.12, _kf_timestamps={},
                           last_paired_evidence={}, evaluate_and_commit_candidate=evaluate)
    loop = NativeClosedLoop(node, "review-only", candidate_source="icp_reregistration",
                            checkpoint_client=client)
    old1, old2 = np.eye(4), np.eye(4)
    old1[0, 3], old2[0, 3] = 10., 20.
    loop._open = Episode(0, 10_000_000_000, old1, 12_000_000_000)
    loop._open.frames = [(1, 10_000_000_000, old1), (2, 11_000_000_000, old2)]
    loop._icp_candidate = lambda episode: (repaired, {"status": "synthetic correction"})
    row = loop.decide(12_000_000_000, "review-only")
    lines = Path(directory, "cmd").read_text(encoding="utf-8").splitlines()
    pending = [e["command"] for e in client._pending]
    assert row["accepted"] and pending == ["reprocess", "set_state"]
    assert lines[0] == "set_state" and float(lines[1].split()[0]) == 20.
    assert "ok" not in client._pending[0]
    Path(directory, "ack").write_text("FAIL reprocess replay_failed\n", encoding="utf-8")
    failed = client.poll()
    assert failed["ok"] is False and lines[0] == "set_state"
    accepted_control = {
        "pending_at_decision_return": pending, "physical_command": lines[0],
        "native_pose_x": float(lines[1].split()[0]), "trusted_repaired_pose_x": 1.,
        "deferred_key": 2, "reprocess_applied_before_set_state": False,
        "later_reprocess_ack": failed["ack"], "set_state_already_sent": True,
    }
print(json.dumps({
    "target": TARGET,
    "scope": "Three selected local tests, received/applied file fixture and simulated accepted report with actual driver/client; no ROS/native/bag/tuning",
    "selected_tests": {"status": "PASS_LOCAL", "count": result.testsRun},
    "received_is_not_applied": "PASS_LOCAL_PENDING_UNTIL_APPLIED_ACK",
    "accepted_async_order": {"status": "FAIL_REPRODUCED_LOCAL", **accepted_control,
        "limit": "Normal source ordering under a simulated gate report, not a deployed accepted native run"},
    "host_thread_source": "BLOCKED_NOT_PUBLISHED_OLD_PATCH_UNCHANGED",
    "reported_controlled_completion": "TWO_REFUSAL_RESTORE_RESUME_EPISODES_REPORTED_NOT_RAW_VERIFIED",
    "actual_repair_and_full_two_event": "NOT_COMPLETED",
    "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED",
}, ensure_ascii=False, indent=2))
