"""Our quarantine must not fight the host's own hibernation and rebuild.

FAST-LIO sets isPublish=false on its own covariance check, calls re_slam() (which clears the
map) and re-initialises. Holding map writes across that blocks the rebuild: in the authorised
run the map went from 221815 points at E1 to 1347 at E2 while held, and /Odometry never came
back. These tests pin the coexistence rules:

  * a host sleep/build signal releases our hold;
  * no hold is sent while the host is hibernating or rebuilding;
  * a quarantine opened before the host reset is taken over, not rolled back.
"""

import unittest

import numpy as np

from slam_recovery.ros.recovery_node import Episode, NativeClosedLoop
from slam_recovery.tests.test_recovery_node import _FakeLoopNode
from slam_recovery.tests.test_repair_sync import _FakeCP


class HostCoexistenceTest(unittest.TestCase):
    def _loop(self):
        node = _FakeLoopNode(trigger_at=10 ** 9)
        loop = NativeClosedLoop(node, run_id="run")
        loop.cp = _FakeCP(True)
        return loop

    def test_a_sleep_signal_releases_the_hold(self):
        loop = self._loop()
        loop.on_host_signal("sleep", 1_000)
        self.assertEqual(loop.host_native_state, "HIBERNATING")
        self.assertEqual(loop.cp.resumes, 1)
        self.assertEqual(loop.host_native_events[-1]["event"], "host_sleep")

    def test_a_build_signal_also_releases_the_hold(self):
        loop = self._loop()
        loop.on_host_signal("build", 2_000)
        self.assertEqual(loop.host_native_state, "REBUILDING")
        self.assertEqual(loop.cp.resumes, 1)

    def test_no_hold_is_sent_while_the_host_hibernates(self):
        loop = self._loop()
        loop.on_host_signal("sleep", 1_000)
        loop._open_episode(1_100, np.eye(4), None)
        self.assertEqual(loop.cp.holds, 0)
        self.assertEqual(loop._open.meta["hold_skipped_host_state"], "HIBERNATING")

    def test_a_hold_is_sent_when_the_host_is_publishing(self):
        loop = self._loop()
        loop.on_host_signal("publish", 1_000)
        loop._open_episode(1_100, np.eye(4), None)
        self.assertEqual(loop.cp.holds, 1)

    def test_a_segment_the_host_reset_is_taken_over_not_decided(self):
        loop = self._loop()
        loop.on_host_signal("sleep", 1_000)
        loop._open_episode(1_100, np.eye(4), None)
        ep = loop._open
        ep.meta["host_reset_during_quarantine"] = {"signal": "sleep", "ts_ns": 1_000}
        self.assertIsNone(loop.decide(1_500, "test"))
        self.assertEqual(ep.meta["decision_skipped"], "HOST_NATIVE_RECOVERY_TAKEOVER")
        self.assertEqual(loop.cp.restore_calls, 0)
        self.assertEqual(loop.cp.reprocess_calls, 0)

    def test_publishing_after_a_sleep_is_recorded_as_a_transition(self):
        loop = self._loop()
        loop.on_host_signal("sleep", 1_000)
        loop.on_host_signal("publish", 3_000)
        self.assertEqual(loop.host_native_state, "PUBLISHING")
        self.assertEqual([e["event"] for e in loop.host_native_events],
                         ["host_sleep", "host_publish"])


if __name__ == "__main__":
    unittest.main()
