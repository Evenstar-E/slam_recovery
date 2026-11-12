"""Small source-bound async checkpoint controls; no ROS/native host execution."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
TARGET = "8ca5b41f9e1aabfd75d21a9e9adfdbfd78883356"
for path in ["slam_recovery/ros/recovery_node.py", "slam_recovery/tests/test_checkpoint_client.py",
             "slam_recovery/sim/transaction_manager_node.py"]:
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{TARGET}:{path}"])
    assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == expected
sys.path.insert(0, str(ROOT))
from slam_recovery.ros.recovery_node import CheckpointClient
from slam_recovery.tests.test_checkpoint_client import CheckpointClientTest

suite = unittest.TestSuite(CheckpointClientTest(name) for name in [
    "test_a_snapshot_never_blocks_the_caller", "test_a_disabled_client_sends_nothing"])
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()

with tempfile.TemporaryDirectory(prefix="async-review-") as directory:
    client = CheckpointClient(directory, snapshot_period_s=0., ack_timeout_s=0.)
    probe = client.tick(time.time(), True)
    assert probe["command"] == "status"
    assert client.poll() is None and len(client._pending) == 1
    Path(directory, "ack").write_text("OK status done\n", encoding="utf-8")
    assert client.poll()["ok"] and client.host_ready
    snapshot = client.tick(time.time(), True)
    Path(directory, "ack").write_text("OK hold done\n", encoding="utf-8")
    assert client.poll() is None and len(client._pending) == 1
    Path(directory, "ack").write_text("OK snapshot done\n", encoding="utf-8")
    assert client.poll()["ok"] and client.snapshots == 1

with tempfile.TemporaryDirectory(prefix="probe-hold-review-") as directory:
    client = CheckpointClient(directory, snapshot_period_s=0., ack_timeout_s=0.)
    client.tick(time.time(), True)  # host status probe has not yet been consumed
    client.hold()                  # normal callback: new segment opens
    physical_command = Path(directory, "cmd").read_text(encoding="utf-8").splitlines()[0]
    Path(directory, "ack").write_text("OK hold done\n", encoding="utf-8")
    polled = client.poll()
    pending = [e["command"] for e in client._pending]
    assert physical_command == "hold" and polled is None and pending == ["status", "hold"]
    probe_overwrite = {"physical_command": physical_command, "ack": "OK hold done",
                       "poll_returned": polled, "pending_commands": pending}

with tempfile.TemporaryDirectory(prefix="late-snapshot-review-") as directory:
    client = CheckpointClient(directory, snapshot_period_s=0., ack_timeout_s=0.)
    client.host_ready = True
    first = client.tick(time.time(), True)
    first["wall"] = time.time() - 1.
    client.expire_pending(.5)
    second = client.tick(time.time(), True)
    # A late ack from the first snapshot arrives after the second is written, before it runs.
    Path(directory, "ack").write_text("OK snapshot first-command-done\n", encoding="utf-8")
    attributed = client.poll()
    assert attributed is second and attributed["ok"]
    late_same_command = {"first_ok": first["ok"], "second_ok": second["ok"],
                         "second_ack": second["ack"], "timeout_count": client.snapshot_ack_timeouts}

print(json.dumps({
    "target": TARGET,
    "scope": "Selected local tests and deterministic file-channel fixtures; no ROS/native/bag/tuning",
    "selected_tests": {"status": "PASS_LOCAL", "count": result.testsRun},
    "async_probe_snapshot_poll": "PASS_LOCAL_NONBLOCKING_POLL_RETAINS_PENDING_AND_CHECKS_COMMAND_NAME",
    "probe_overwritten_by_hold": {"status": "FAIL_REPRODUCED_LOCAL", **probe_overwrite},
    "late_same_command_ack": {"status": "FAIL_REPRODUCED_LOCAL", **late_same_command,
        "limit": "Synthetic delayed receipt, not evidence that the reported 14 snapshots were misattributed"},
    "reported_partial_accept": "DEVELOPER_REPORTED_MODE2_23_COMMITTED_169_DEFERRED_NOT_REPAIR_QUALITY",
    "native_full_two_event": "NOT_COMPLETED",
    "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED",
}, ensure_ascii=False, indent=2))
