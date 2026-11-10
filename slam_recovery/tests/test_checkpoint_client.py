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
                    # The host reads the command from the first line; the second, when present, is
                    # the payload. Reading the whole file would hide that distinction.
                    cmd = fh.readline().strip()
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



class CheckpointWiringTest(unittest.TestCase):
    """The loop must hold the host's map when a segment opens and release it on re-arm."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.host = _FakeHost(self.dir)
        self.host.start()

    def tearDown(self):
        self.host.stop()
        self._tmp.cleanup()

    def _wait_seen(self, n, timeout_s=2.0):
        deadline = time.time() + timeout_s
        while time.time() < deadline and len(self.host.seen) < n:
            time.sleep(0.005)
        return list(self.host.seen)

    def _loop(self, client):
        import numpy as np

        from slam_recovery.ros.recovery_node import NativeClosedLoop
        from slam_recovery.tests.test_recovery_node import _FakeLoopNode

        node = _FakeLoopNode(trigger_at=10 ** 9)      # no automatic trigger
        loop = NativeClosedLoop(node, run_id="run", checkpoint_client=client)
        loop._open_episode(1_000_000_000, np.eye(4))
        return loop, node

    def test_opening_a_segment_holds_the_host_map(self):
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        self._loop(client)
        # The host consumes the command on its own thread; the assertion waits for it rather than
        # racing it.
        self.assertEqual(self._wait_seen(1), ["hold"])

    def test_a_re_arm_writes_resume(self):
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        loop, node = self._loop(client)
        client.collect(timeout_s=5.0)                 # account for the hold before the next command
        node.tx_mgr.lifecycle_events.append({"event": "rearm"})
        loop._apply_lifecycle()
        self.assertEqual(self._wait_seen(2), ["hold", "resume"])
        self.assertEqual(client.resumes, 1)

    def test_lifecycle_events_are_only_acted_on_once(self):
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        loop, node = self._loop(client)
        client.collect(timeout_s=5.0)
        node.tx_mgr.lifecycle_events.append({"event": "rearm"})
        loop._apply_lifecycle()
        loop._apply_lifecycle()
        self.assertEqual(self._wait_seen(2), ["hold", "resume"])
        time.sleep(0.05)
        self.assertEqual(self.host.seen, ["hold", "resume"])


if __name__ == "__main__":
    unittest.main()


class WritebackTest(unittest.TestCase):
    """An accepted repair must reach the host as a state, not only as a decision."""

    def test_identity_rotation_is_the_identity_quaternion(self):
        import numpy as np

        from slam_recovery.ros.recovery_node import _rotation_to_quaternion

        q = _rotation_to_quaternion(np.eye(3))
        self.assertEqual([round(v, 9) for v in q], [0.0, 0.0, 0.0, 1.0])

    def test_ninety_degrees_about_z(self):
        import math

        import numpy as np

        from slam_recovery.ros.recovery_node import _rotation_to_quaternion

        c, s = math.cos(math.pi / 2), math.sin(math.pi / 2)
        R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        q = _rotation_to_quaternion(R)
        # x, y, z, w with a positive w; the axis is +z
        self.assertAlmostEqual(q[3], math.cos(math.pi / 4), places=9)
        self.assertAlmostEqual(q[2], math.sin(math.pi / 4), places=9)

    def test_set_state_sends_the_pose_in_seven_numbers(self):
        import tempfile

        import numpy as np

        with tempfile.TemporaryDirectory() as d:
            host = _FakeHost(d)
            host.start()
            try:
                client = CheckpointClient(d, ack_timeout_s=5.0)
                T = np.eye(4)
                T[:3, 3] = [1.0, -2.0, 3.0]
                event = client.set_state(T)
                self.assertTrue(event["ok"])
                self.assertEqual(host.seen, ["set_state"])
                with open(os.path.join(d, "cmd.done"), encoding="utf-8") as fh:
                    lines = [ln.strip() for ln in fh if ln.strip()]
                self.assertEqual(len(lines), 2)
                values = [float(v) for v in lines[1].split()]
                self.assertEqual([round(v, 6) for v in values[:3]], [1.0, -2.0, 3.0])
            finally:
                host.stop()
