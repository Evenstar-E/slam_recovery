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
        self.payloads = []
        self._stop_evt = threading.Event()

    def run(self):
        while not self._stop_evt.is_set():
            path = os.path.join(self.dir, "cmd")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    # The host reads the command from the first line; the second, when present, is
                    # the payload. Reading the whole file would hide that distinction.
                    cmd = fh.readline().strip()
                    payload = fh.readline().strip()
                os.rename(path, os.path.join(self.dir, "cmd.done"))
                self.seen.append(cmd)
                self.payloads.append(payload)
                with open(os.path.join(self.dir, "ack_received"), "w", encoding="utf-8") as fh:
                    fh.write(f"RECEIVED {cmd} wall={time.time():.6f}\n")
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
        # Issuing does not wait: the ack is collected by poll().
        self.assertNotIn("ok", event)
        deadline = time.time() + 3.0
        while time.time() < deadline and not event.get("ok"):
            client.poll()
            time.sleep(0.005)
        self.assertTrue(event["ok"])
        self.assertEqual(host.seen, ["snapshot"])
        # A second send must produce a second execution, not a replay of the first ack.
        client._send("restore")
        deadline = time.time() + 3.0
        while time.time() < deadline and not client.restores:
            client.poll()
            time.sleep(0.005)
        self.assertEqual(host.seen, ["snapshot", "restore"])

    def test_received_is_recorded_before_applied(self):
        host = self._host(delay=0.15)
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        event = client._send("restore")
        deadline = time.time() + 3.0
        while time.time() < deadline and not event.get("ack"):
            client.poll()
            time.sleep(0.005)
        self.assertIsNotNone(event.get("received_wall"))
        self.assertTrue(event["ok"])
        self.assertGreaterEqual(event["received_s"], 0.0)
        self.assertGreater(event["ack_wall"] - event["received_wall"], 0.05)

    def test_a_silent_host_leaves_the_command_pending(self):
        client = CheckpointClient(self.dir, ack_timeout_s=0.2)
        event = client._send("restore")
        self.assertIsNone(client.poll())
        self.assertTrue(client.pending())
        self.assertNotIn("ok", event)
        self.assertEqual(client.restores, 0)

    def test_rolling_snapshot_respects_the_period_and_the_quiescent_flag(self):
        host = self._host()
        client = CheckpointClient(self.dir, snapshot_period_s=10.0, ack_timeout_s=5.0)
        self.assertIsNone(client.tick(100.0, quiescent=False))   # a segment is open
        # Nothing is asked of the host until it has answered once: the first tick is a probe.
        client.tick(100.0, quiescent=True)
        deadline = time.time() + 2.0
        while time.time() < deadline and not client.host_ready:
            client.poll()
            time.sleep(0.005)
        self.assertTrue(client.host_ready)
        self.assertIsNone(client.tick(101.0, quiescent=True))     # inside the period
        client.tick(110.5, quiescent=True)                        # period elapsed
        deadline = time.time() + 2.0
        while time.time() < deadline and client.snapshots == 0:
            client.poll()
            time.sleep(0.005)
        self.assertEqual(host.seen, ["status", "snapshot"])

    def test_a_snapshot_never_blocks_the_caller(self):
        # No host at all: tick must return immediately, and the timeout is recorded by the
        # expiring path rather than by making the main loop wait for it.
        client = CheckpointClient(self.dir, snapshot_period_s=0.0, ack_timeout_s=5.0)
        client.host_ready = True
        t0 = time.time()
        event = client.tick(time.time(), quiescent=True)
        self.assertLess(time.time() - t0, 0.2)
        self.assertEqual(event["command"], "snapshot")
        time.sleep(0.05)
        client.expire_pending(0.01)
        self.assertEqual(client.snapshot_ack_timeouts, 1)

    def test_reprocess_carries_the_terminal_stamp(self):
        host = self._host()
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        event = client.reprocess(123456789)
        deadline = time.time() + 3.0
        while time.time() < deadline and not event.get("ok"):
            client.poll()
            time.sleep(0.005)
        self.assertTrue(event["ok"])
        with open(os.path.join(self.dir, "cmd.done"), encoding="utf-8") as fh:
            lines = [ln.rstrip("\n") for ln in fh]
        self.assertEqual(lines[0], "reprocess")
        self.assertEqual(lines[1], "123456789")
        # an empty payload keeps the historical replay-everything behaviour
        event2 = client.reprocess()
        deadline = time.time() + 3.0
        while time.time() < deadline and not event2.get("ok"):
            client.poll()
            time.sleep(0.005)
        with open(os.path.join(self.dir, "cmd.done"), encoding="utf-8") as fh:
            lines = [ln.rstrip("\n") for ln in fh]
        self.assertEqual(lines[0], "reprocess")
        self.assertEqual(lines[1], "")

    def test_a_disabled_client_sends_nothing(self):
        client = CheckpointClient("")
        self.assertFalse(client.enabled)
        self.assertIsNone(client.tick(1e9, quiescent=True))
        self.assertEqual(client.events, [])



    def test_a_second_state_command_waits_for_the_first_ack(self):
        # decide() used to issue reprocess and set_state inside the same millisecond. The host
        # polls `cmd` on its own thread every 5 ms, so set_state replaced reprocess unread and
        # the host never replayed the repaired frames. Measured in the accepted run: zero
        # `[NATIVE_CHECKPOINT] reprocess` lines and a final ack of set_state.
        host = self._host(delay=0.15)
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        first = client._send("reprocess", "1")
        second = client._send("set_state", "1 2 3 0 0 0 1")
        time.sleep(0.05)
        self.assertEqual(host.seen, ["reprocess"],
                         "the second command reached the host before the first was answered")

        deadline = time.time() + 5.0
        while time.time() < deadline and not (first.get("ok") and second.get("ok")):
            client.poll()
            time.sleep(0.005)
        self.assertTrue(first["ok"], first)
        self.assertTrue(second["ok"], second)
        self.assertEqual(host.seen, ["reprocess", "set_state"])
        self.assertEqual(client.reprocesses, 1)

    def test_a_queued_command_is_not_timed_out_before_it_is_sent(self):
        # Queued commands have no wall time yet; expire_pending must leave them alone.
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        self._host(delay=0.05)
        client._send("restore", "1")
        queued = client._send("resume")
        self.assertIsNone(queued.get("wall"))
        client.expire_pending(0.5)
        self.assertTrue(client.pending())

    def test_hold_preempts_a_snapshot_but_never_a_state_command(self):
        host = self._host(delay=0.2)
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        client._send("snapshot")
        time.sleep(0.02)                       # host has consumed the snapshot
        client.hold()
        deadline = time.time() + 3.0
        while time.time() < deadline and len(host.seen) < 2:
            client.poll()
            time.sleep(0.005)
        self.assertEqual(host.seen, ["snapshot", "hold"])
        # Now a restore is in flight; resume must queue, not overwrite it.
        client._send("restore", "2")
        client.resume()
        time.sleep(0.05)
        self.assertNotIn("resume", host.seen,
                         "resume overwrote a restore that had not been answered")
        deadline = time.time() + 5.0
        while time.time() < deadline and "resume" not in host.seen:
            client.poll()
            time.sleep(0.005)
        self.assertEqual(host.seen[-1], "resume")


    def test_stamped_commands_carry_their_application_stamp(self):
        # hold/snapshot with a stamp are queued now and executed by the host just before the first
        # group whose lio_time reaches it. The stamp travels as the payload line.
        host = self._host(delay=0.05)
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        client.hold(1627785276215170145)
        client.snapshot_now(1627785276215170145)
        deadline = time.time() + 5.0
        while time.time() < deadline and len(host.seen) < 2:
            client.poll()
            time.sleep(0.005)
        self.assertEqual(host.seen, ["hold", "snapshot"])
        self.assertEqual(host.payloads, ["1627785276215170145", "1627785276215170145"])


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

    def _account_open(self, client):
        """Account for the command an episode open queues.

        Opening queues `hold` only. The checkpoint is armed ahead of time at the declared trigger
        stamp (main()), because a command sent when the trigger fires is applied a backlog later.
        """
        client.collect(timeout_s=5.0)

    def test_opening_a_segment_holds_the_map(self):
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        self._loop(client)
        # The host consumes the command on its own thread; the assertion waits for it rather than
        # racing it. Opening no longer takes a snapshot: the checkpoint is armed at a declared
        # stamp before the trigger, so its application does not depend on backlog.
        self.assertEqual(self._wait_seen(1), ["hold"])

    def test_a_re_arm_writes_resume(self):
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        loop, node = self._loop(client)
        self._account_open(client)                    # account for the open hold
        node.tx_mgr.lifecycle_events.append({"event": "rearm"})
        loop._apply_lifecycle()
        self.assertEqual(self._wait_seen(2), ["hold", "resume"])
        # resume is now async too: the count follows when poll() sees the applied ack.
        deadline = time.time() + 3.0
        while time.time() < deadline and client.resumes == 0:
            client.poll()
            time.sleep(0.005)
        self.assertEqual(client.resumes, 1)

    def test_an_accepted_commit_writes_resume(self):
        # The accepted path ends the quarantine with `commit_closed`, not `rearm`; the host
        # releases its map hold on the same command either way.
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        loop, node = self._loop(client)
        self._account_open(client)
        node.tx_mgr.lifecycle_events.append(
            {"event": "commit_closed", "segment_id": "s", "n_committed": 1})
        loop._apply_lifecycle()
        self.assertEqual(self._wait_seen(2), ["hold", "resume"])
        deadline = time.time() + 3.0
        while time.time() < deadline and client.resumes == 0:
            client.poll()
            time.sleep(0.005)
        self.assertEqual(client.resumes, 1)

    def test_lifecycle_events_are_only_acted_on_once(self):
        client = CheckpointClient(self.dir, ack_timeout_s=5.0)
        loop, node = self._loop(client)
        self._account_open(client)
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
                deadline = time.time() + 3.0
                while time.time() < deadline and not event.get("ok"):
                    client.poll()
                    time.sleep(0.005)
                self.assertTrue(event["ok"])
                self.assertEqual(host.seen, ["set_state"])
                with open(os.path.join(d, "cmd.done"), encoding="utf-8") as fh:
                    lines = [ln.strip() for ln in fh if ln.strip()]
                self.assertEqual(len(lines), 2)
                values = [float(v) for v in lines[1].split()]
                self.assertEqual([round(v, 6) for v in values[:3]], [1.0, -2.0, 3.0])
            finally:
                host.stop()
