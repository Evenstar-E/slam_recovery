"""Runtime-independent regressions at the automatic refusal protocol boundary."""

import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np

from slam_recovery.core import RecoveryState
from slam_recovery.ros.recovery_node import CheckpointClient, Episode, NativeClosedLoop
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode


class Host:
    enabled = True

    def __init__(self):
        self.calls = []
        self.events = []
        self.consumed = 5

    def pending(self):
        return False

    def reprocess_refusal(self, boundary, healthy):
        self.calls.append(("refusal", boundary, list(healthy)))
        return {"ok": True, "ack": "OK reprocess_refusal valid=1 checkpoint_stamp_ns=70 "
                                   "target_ns=2101 target_scan_ns=2100 queued=5"}

    def request_status(self):
        self.calls.append(("status",))
        return {"ok": True, "ack": f"OK status replay_remaining=0 refusal_consumed={self.consumed} "
                                   "stamp_ns=2101 map_writes=held"}

    def resume(self):
        self.calls.append(("resume",))
        return {"ok": True, "ack": "OK resume valid=1 stamp_ns=2101 map_writes=released"}


class TestOnlineRefusal(unittest.TestCase):
    def setup_loop(self):
        node = OnlineRecoveryTransactionNode()
        host = Host()
        loop = NativeClosedLoop(node, "refusal-test", checkpoint_client=host, online_refusal_wait_s=10)
        ep = Episode(0, 100, np.eye(4), 110, quarantine_start_ns=80)
        ep.meta["online_refusal"] = {"status": "WAIT_HEALTHY_SUFFIX"}
        ep.refusal_started = time.monotonic()
        loop._open = ep
        loop._host_held = True
        node.tx_mgr.state = RecoveryState.ABORTED
        return loop, host, ep

    def test_request_status_writes_the_native_command(self):
        with tempfile.TemporaryDirectory() as root:
            client = CheckpointClient(root)
            event = client.request_status()
            self.assertEqual(event["command"], "status")
            self.assertEqual((Path(root) / "cmd").read_text(), "status\n\n")
            self.assertTrue(client.status()["enabled"])

    def test_startup_alarm_requires_a_confirmed_checkpoint_before_its_boundary(self):
        loop, host, _ = self.setup_loop()
        alarm = SimpleNamespace(estimated_onset_ns=100, quarantine_start_ns=80)
        host.events.append({"command": "snapshot", "ok": True,
                            "ack": "OK snapshot applied valid=1 stamp_ns=90"})
        self.assertFalse(loop._online_quarantine_ready(alarm))
        self.assertEqual(loop.unarmed_online_alarms[100]["observations"], 1)
        host.events.insert(0, {"command": "snapshot", "ok": True,
                               "ack": "OK snapshot applied valid=1 stamp_ns=70"})
        self.assertTrue(loop._online_quarantine_ready(alarm))

    def test_unavailable_breaks_the_observed_suffix(self):
        loop, host, ep = self.setup_loop()
        healthy = SimpleNamespace(state=RecoveryState.HEALTHY)
        loop._observe_healthy_suffix(ep, 130, healthy)
        loop._observe_healthy_suffix(ep, 150, None)
        loop._observe_healthy_suffix(ep, 200, healthy)
        loop._service_online_refusal()
        self.assertEqual(host.calls, [])
        self.assertEqual(ep.healthy_suffix, [200])

    def test_native_consumption_and_release_precede_rearm(self):
        loop, host, ep = self.setup_loop()
        ep.healthy_suffix = [2000, 2100]
        loop._service_online_refusal()
        loop._service_online_refusal()
        self.assertEqual(loop.node.tx_mgr.state, RecoveryState.ABORTED)
        loop._service_online_refusal()
        self.assertTrue(loop._host_held)
        loop._service_online_refusal()
        self.assertEqual(host.calls, [("refusal", 80, [2000, 2100]), ("status",), ("resume",)])
        self.assertEqual(loop.node.tx_mgr.state, RecoveryState.HEALTHY)
        self.assertFalse(loop._host_held)

    def test_native_comparison_stopping_does_not_block_a_complete_refusal(self):
        loop, host, ep = self.setup_loop()
        ep.healthy_suffix = [2000, 2100]
        default_reprocess = host.reprocess_refusal

        def with_comparison(boundary, healthy):
            action = default_reprocess(boundary, healthy)
            action["ack"] += " comparison=1"
            return action

        host.reprocess_refusal = with_comparison
        host.refusal_comparison = lambda *_args: {"status": "NATIVE_STOPPED_EARLY"}
        for _ in range(4):
            loop._service_online_refusal()
        self.assertIn(("resume",), host.calls)
        self.assertEqual(ep.meta["online_refusal"]["paired_native_outcomes"]["status"],
                         "NATIVE_STOPPED_EARLY")
        self.assertEqual(ep.meta["online_refusal"]["status"], "RELEASED_AND_REARMED")

    def test_drained_queue_with_missing_update_does_not_release(self):
        loop, host, ep = self.setup_loop()
        ep.healthy_suffix = [2000, 2100]
        host.consumed = 4
        for _ in range(4):
            loop._service_online_refusal()
        self.assertNotIn(("resume",), host.calls)
        self.assertEqual(ep.meta["online_refusal"]["status"], "FAILED_REPLAY_RECEIPT")
        self.assertTrue(loop._host_held)


if __name__ == "__main__":
    unittest.main()
