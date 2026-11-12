"""The measurement-repair handshake: no replay before the host has the repaired clouds.

The clouds travel on a ROS topic and `reprocess` travels on the command file. These tests pin the
two properties that make the INJECTION test meaningful:

  * `wait_for_repair_count` reads `repair_received` out of the existing status ack and only
    returns True when the host has taken at least the published count;
  * an accepted candidate whose repairs were published but not acknowledged does **not** send
    `reprocess` (and does not send `restore` either) -- the previous run's failure mode was a
    replay of the original scans.
"""

import json
import os
import tempfile
import threading
import time
import unittest

import numpy as np

from slam_recovery.ros.recovery_node import CheckpointClient, Episode, NativeClosedLoop
from slam_recovery.tests.test_cloud_repair import _Cloud, ROWS
from slam_recovery.tests.test_recovery_node import _FakeLoopNode, _Report


class _CountingHost(threading.Thread):
    """Answers status with an increasing repair_received, one step per status command."""

    def __init__(self, directory, counts):
        super().__init__(daemon=True)
        self.dir = directory
        self.counts = list(counts)
        self.seen = []
        self._stop_evt = threading.Event()

    def run(self):
        while not self._stop_evt.is_set():
            path = os.path.join(self.dir, "cmd")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    cmd = fh.readline().strip()
                os.rename(path, os.path.join(self.dir, "cmd.done"))
                self.seen.append(cmd)
                if cmd == "status":
                    n = self.counts.pop(0) if self.counts else 0
                    ack = f"OK status valid=1 repair_received={n} repair_applied=0\n"
                else:
                    ack = f"OK {cmd} done\n"
                with open(os.path.join(self.dir, "ack"), "w", encoding="utf-8") as fh:
                    fh.write(ack)
            time.sleep(0.005)

    def stop(self):
        self._stop_evt.set()
        self.join(timeout=2)


class _FakeCP:
    def __init__(self, wait_result):
        self.wait_result = wait_result
        self.reprocess_calls = 0
        self.restore_calls = 0
        self.set_state_calls = 0
        self.expected = None
        self._last_snapshot_wall = 0.0

    def wait_for_repair_count(self, n, timeout_s=5.0):
        self.expected = n
        return self.wait_result

    def reprocess(self):
        self.reprocess_calls += 1
        return {"command": "reprocess"}

    def restore(self):
        self.restore_calls += 1
        return {"command": "restore"}

    def set_state(self, pose):
        self.set_state_calls += 1
        return {"command": "set_state"}


class RepairReceiptTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.hosts = []

    def tearDown(self):
        for h in self.hosts:
            h.stop()
        self._tmp.cleanup()

    def _host(self, counts):
        h = _CountingHost(self.dir, counts)
        h.start()
        self.hosts.append(h)
        return h

    def test_waits_until_the_receipt_reaches_the_published_count(self):
        host = self._host([1, 3])
        client = CheckpointClient(self.dir, ack_timeout_s=2.0)
        self.assertTrue(client.wait_for_repair_count(3, timeout_s=2.0))
        self.assertGreaterEqual(len(host.seen), 1)

    def test_returns_false_when_the_receipt_never_reaches_the_count(self):
        self._host([0, 0, 0, 0])
        client = CheckpointClient(self.dir, ack_timeout_s=2.0)
        t0 = time.time()
        self.assertFalse(client.wait_for_repair_count(2, timeout_s=0.6))
        self.assertLess(time.time() - t0, 3.0)


class RepairGateTest(unittest.TestCase):
    def _loop(self, wait_result):
        from slam_recovery.tests.test_cloud_repair import _plane

        node = _FakeLoopNode(trigger_at=10 ** 9)
        node.evaluate_and_commit_candidate = lambda *a, **k: _Report(
            accepted=True, committed_pose_keys=[0, 1], deferred_pose_keys=[])
        plane = _plane()
        node.support_reference = lambda: plane
        corrupted = _plane(z=0.5)[::4]
        node.scan_buffer_body = {0: corrupted, 1: corrupted}
        loop = NativeClosedLoop(node, run_id="run")
        loop.repair_publish_enabled = True
        loop.published = []
        loop.publish_repair = loop.published.append
        loop.cp = _FakeCP(wait_result)
        cloud = _Cloud()
        cloud.set_points([(float(x), float(y), float(z), 0.0, 0.0, 0)
                          for x, y, z in corrupted])
        for k in (0, 1):
            loop._scan_index[k] = (1000 + k, cloud)
        ep = Episode(0, 1_000, np.eye(4), 2_000)
        ep.frames = [(k, 1_000, np.eye(4)) for k in (0, 1)]
        loop._open = ep
        loop.episodes = [ep]
        return loop, ep

    def test_an_unacknowledged_repair_stops_the_replay(self):
        loop, ep = self._loop(wait_result=False)
        loop.decide(1_500, "test")
        self.assertEqual(loop.cp.expected, 2)
        self.assertEqual(len(loop.published), 2)
        self.assertEqual(loop.cp.reprocess_calls, 0)
        self.assertEqual(loop.cp.restore_calls, 0)
        self.assertEqual(loop.cp.set_state_calls, 0)
        self.assertEqual(ep.meta.get("native_checkpoint_skipped"), "repair_sync_timeout")
        self.assertFalse(ep.meta["repair_publish"]["synced"])

    def test_an_acknowledged_repair_replays_and_writes_the_pose(self):
        loop, ep = self._loop(wait_result=True)
        loop.decide(1_500, "test")
        self.assertEqual(len(loop.published), 2)
        self.assertEqual(loop.cp.reprocess_calls, 1)
        self.assertEqual(loop.cp.set_state_calls, 1)
        self.assertTrue(ep.meta["repair_publish"]["synced"])

    def test_the_bias_is_estimated_at_the_incumbent_pose_with_a_pinned_sign(self):
        # A synthetic plane map; the frame's cloud is that plane displaced +0.5 in body z. With the
        # incumbent at identity the 1-D search must return +0.5 and the published cloud must carry
        # -0.5. An inverted sign would double the corruption instead of removing it.
        from slam_recovery.tests.test_cloud_repair import _plane

        loop, ep = self._loop(wait_result=True)
        plane = _plane()
        loop.node.support_reference = lambda: plane
        corrupted = _plane(z=0.5)[::4]
        cloud = _Cloud()
        cloud.set_points([(float(x), float(y), float(z), 0.0, 0.0, 0)
                          for x, y, z in corrupted])
        loop.node.scan_buffer_body = {0: corrupted, 1: corrupted}
        loop._scan_index = {0: (1000, cloud), 1: (1001, cloud)}
        loop._last_incumbent = {0: np.eye(4), 1: np.eye(4)}
        ep.frames = [(k, 1_000, np.eye(4)) for k in (0, 1)]
        rep = loop._publish_repaired_scans(ep)
        self.assertAlmostEqual(rep["bias_z_m"], 0.5, delta=0.06)
        self.assertAlmostEqual(rep["repair_shift_z_m"], -0.5, delta=0.06)
        self.assertEqual(rep["published"], 2)
        raw = np.frombuffer(loop.published[0].data, dtype=np.uint8).reshape(-1, 24)
        z = raw[:, 8:12].view(np.float32).reshape(-1)
        self.assertAlmostEqual(float(z[0]), 0.0, delta=0.06)


if __name__ == "__main__":
    unittest.main()
