"""The checkpoint channel is a file protocol, so it can be tested without ROS or a host.

What matters here is the part that would silently corrupt a run: a command must be executed at
most once, and a host that never answers must be visible as a failure rather than as a success.

Written as ``unittest.TestCase`` because that is this repository's acceptance runner
(``python -m unittest discover``); pytest-style module functions are invisible to it.
"""

import os
import tempfile
import threading
import time
import unittest

from slam_recovery.ros.recovery_node import CheckpointClient


class _FakeHost(threading.Thread):
    """Stands in for the host's poll loop: consume cmd, rename it away, write an ack."""

    def __init__(self, directory, ack="OK {cmd} done", delay=0.0):
        super().__init__(daemon=True)
        self.dir = directory
        self.ack = ack
        self.delay = delay
        self.seen = []
        self._stop_evt = threading.Event()

    def run(self):
        while not self._stop_evt.is_set():
            path = os.path.join(self.dir, "cmd")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    cmd = fh.read().strip()
                os.rename(path, os.path.join(self.dir, "cmd.done"))
                self.seen.append(cmd)
                time.sleep(self.delay)
                with open(os.path.join(self.dir, "ack"), "w", encoding="utf-8") as fh:
                    fh.write(self.ack.format(cmd=cmd) + "\n")
            time.sleep(0.005)

    def stop(self):
        self._stop_evt.set()
        self.join(timeout=2)


class CheckpointClientTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.hosts = []

    def tearDown(self):
        for host in self.hosts:
            host.stop()
        self._tmp.cleanup()

    def _host(self, **kwargs):
        host = _FakeHost(self.dir, **kwargs)
        host.start()
        self.hosts.append(host)
        return host

    def test_one_command_runs_exactly_once(self):
        host = self._host()
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        event = client._send("snapshot")
        self.assertTrue(event["ok"])
        self.assertEqual(host.seen, ["snapshot"])
        # A second send must produce a second execution, not a replay of the first ack.
        client._send("restore")
        self.assertEqual(host.seen, ["snapshot", "restore"])

    def test_a_silent_host_is_a_failure_not_a_success(self):
        client = CheckpointClient(self.dir, ack_timeout_s=0.2)
        event = client._send("snapshot")
        self.assertFalse(event["ok"])
        self.assertEqual(event["error"], "ack_timeout")
        # Exactly one accounting: the timeout must not also be counted by the success branch.
        self.assertEqual(client.failures, 1)
        self.assertEqual(client.snapshots, 0)

    def test_rolling_snapshot_respects_the_period_and_the_quiescent_flag(self):
        host = self._host()
        client = CheckpointClient(self.dir, snapshot_period_s=10.0, ack_timeout_s=5.0)
        self.assertIsNone(client.tick(100.0, quiescent=False))   # a segment is open
        self.assertIsNotNone(client.tick(100.0, quiescent=True))  # first snapshot
        self.assertIsNone(client.tick(101.0, quiescent=True))     # inside the period
        self.assertIsNotNone(client.tick(110.5, quiescent=True))  # period elapsed
        self.assertEqual(host.seen, ["snapshot", "snapshot"])

    def test_a_disabled_client_sends_nothing(self):
        client = CheckpointClient("")
        self.assertFalse(client.enabled)
        self.assertIsNone(client.tick(1e9, quiescent=True))
        self.assertEqual(client.events, [])


if __name__ == "__main__":
    unittest.main()
