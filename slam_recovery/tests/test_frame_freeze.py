"""The candidate population stops growing when the decision deadline is crossed.

Without this, a decision delayed by a pending command or the 2 Hz service tick scores whatever
frames arrived in the meantime. That is invisible in one run and fatal to an A/B: the repair and
control arms then have different candidate sets and different replay spans.
"""

import unittest

import numpy as np

from slam_recovery.ros.recovery_node import Episode, NativeClosedLoop
from slam_recovery.tests.test_recovery_node import _scan


def _make(trigger_at=3):
    from slam_recovery.tests.test_recovery_node import _FakeLoopNode

    node = _FakeLoopNode(trigger_at=trigger_at)
    return NativeClosedLoop(node, run_id="run", confirmation_margin_ns=2_000_000_000)


def _drive(loop, n=40, t0=1_000_000_000, step=100_000_000):
    for i in range(n):
        loop.on_pair(t0 + i * step, np.eye(4), _scan(200))
        loop.service()


class FrameFreezeTest(unittest.TestCase):
    def test_frames_after_the_deadline_do_not_join_the_candidate(self):
        loop = _make()
        _drive(loop)
        ep = loop.episodes[0]
        self.assertTrue(ep.frozen)
        self.assertIsNotNone(ep.frozen_at_ns)
        # the frozen set is exactly the frames up to and including the crossing frame
        self.assertEqual([kf for kf, _, _ in ep.frames], [kf for kf, _, _ in ep.frozen_frames])
        self.assertEqual(len(ep.frozen_frames), len(ep.frames))
        self.assertGreater(ep.frames_after_freeze, 0)
        # the frozen timestamp is the crossing frame's stamp, not a wall-clock delay
        self.assertGreaterEqual(ep.frozen_at_ns, ep.deadline_ns)
        # the recorded decision used the frozen count
        self.assertEqual(loop.records[0]["t_decision_ns"] >= ep.frozen_at_ns, True)

    def test_the_same_input_gives_the_same_frozen_set(self):
        a, b = _make(), _make()
        _drive(a)
        _drive(b)
        ids_a = [kf for kf, _, _ in a.episodes[0].frozen_frames]
        ids_b = [kf for kf, _, _ in b.episodes[0].frozen_frames]
        self.assertEqual(ids_a, ids_b)
        self.assertEqual(a.episodes[0].frozen_at_ns, b.episodes[0].frozen_at_ns)

    def test_a_late_service_tick_does_not_change_the_population(self):
        # Crossing frames arrive, then several more before service() runs the decision. The
        # candidate must be the crossing set, not the larger set present at decision time.
        loop = _make()
        t0 = 1_000_000_000
        for i in range(30):
            loop.on_pair(t0 + i * 100_000_000, np.eye(4), _scan(200))
        ep = loop._open
        self.assertTrue(ep.frozen)
        frozen_n = len(ep.frames)
        # keep feeding without service: the candidate must not grow
        for i in range(30, 45):
            loop.on_pair(t0 + i * 100_000_000, np.eye(4), _scan(200))
        self.assertEqual(len(ep.frames), frozen_n)
        self.assertGreater(ep.frames_after_freeze, 0)
        loop.service()
        self.assertEqual(len(loop.records), 1)
        self.assertEqual(ep.meta.get("candidate_frames"), frozen_n)

    def test_an_empty_episode_does_not_crash(self):
        loop = _make()
        ep = Episode(0, 1_000, np.eye(4), 2_000)
        loop._open = ep
        loop.episodes = [ep]
        row = loop.decide(1_500, "empty")
        self.assertIsNotNone(row)
        self.assertTrue(ep.frozen)
        self.assertEqual(len(ep.frozen_frames), 0)


if __name__ == "__main__":
    unittest.main()
