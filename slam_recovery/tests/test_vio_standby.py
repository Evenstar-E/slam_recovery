from concurrent.futures import ThreadPoolExecutor
from threading import Event
import unittest
from unittest.mock import Mock

from slam_recovery.vio.run_euroc import Lane

from slam_recovery.vio.standby import StandbyQueue, StandbyRebuild, StandbyTimeout


class StandbyQueueTest(unittest.TestCase):
    def test_primary_can_proceed_until_the_checkpoint_barrier(self):
        started = Event()
        release = Event()
        received = []

        def process(stamp):
            started.set()
            release.wait(timeout=2)
            received.append(stamp)

        with ThreadPoolExecutor(max_workers=1) as pool:
            queue = StandbyQueue(pool, capacity=2, wait_s=0.2)
            try:
                self.assertFalse(queue.offer(process, 123))
                self.assertTrue(started.wait(timeout=1))
                self.assertFalse(queue.offer(process, 456))
                self.assertEqual(received, [])
            finally:
                release.set()
            queue.at_boundary()
        self.assertEqual(received, [123, 456])

    def test_timed_out_boundary_drops_only_unstarted_work_before_close(self):
        started = Event()
        release = Event()
        received = []

        def process(stamp):
            started.set()
            release.wait(timeout=2)
            received.append(stamp)

        with ThreadPoolExecutor(max_workers=1) as pool:
            queue = StandbyQueue(pool, capacity=2, wait_s=0.01)
            try:
                queue.offer(process, 123)
                self.assertTrue(started.wait(timeout=1))
                queue.offer(process, 456)
                with self.assertRaises(StandbyTimeout):
                    queue.at_boundary()
                closed = queue.retire(lambda: received.append("closed"))
            finally:
                release.set()
            closed.result(timeout=2)
        self.assertEqual(received, [123, "closed"])

    def test_rebuild_preserves_view_order_and_drains_the_moving_tail(self):
        received = []

        class Replica:
            def consume(self, pair, view, **options):
                received.append((pair, view, options.get("features")))

        with ThreadPoolExecutor(max_workers=1) as pool:
            rebuild = StandbyRebuild(pool, lambda: (10, 11, 12, 13, 14), replay_features=True)
            queue = StandbyQueue(pool)
            rebuild.record("raw")
            rebuild.record("skip")
            rebuild.start(Replica)
            rebuild.pending.result(timeout=2)
            rebuild.record("fit")
            rebuild.record("raw")
            self.assertIsNone(rebuild.at_tip(queue))
            rebuild.pending.result(timeout=2)
            rebuild.record("raw")
            lane, complete, queued_tail = rebuild.at_tip(queue)
            self.assertTrue(complete)
            self.assertEqual(queued_tail, 1)
            queue.offer(lane.consume, 15, "raw")
            queue.at_boundary()
        self.assertEqual(received, [(10, "raw", 1), (11, "skip", None),
                                    (12, "fit", None), (13, "raw", 2),
                                    (14, "raw", 3), (15, "raw", None)])


class RecoveryBoundaryTest(unittest.TestCase):
    def test_refreshed_state_replaces_only_the_terminal_observation(self):
        before = {"timestamp": 99, "map_id": 0, "maps": 1}
        reached = {"timestamp": 100, "map_id": 0, "maps": 1, "keyframes": 11}
        fresh = dict(reached, keyframes=12)
        worker = Mock()
        worker.synchronize.side_effect = [dict(fresh, map_id=1), fresh]
        lane = Lane(worker, delay=0)
        lane.snapshot = reached
        lane.recent.extend((before, reached))
        self.assertIsNone(lane.synchronize())
        self.assertEqual(list(lane.recent), [before, reached])
        self.assertEqual(lane.synchronize(), fresh)
        self.assertEqual(list(lane.recent), [before, fresh])
        worker.synchronize.assert_called_with(reached["timestamp"])

    def test_rebuild_runs_local_mapping_asynchronously_only_for_replay(self):
        lane = Mock()
        with ThreadPoolExecutor(max_workers=1) as pool:
            rebuild = StandbyRebuild(pool, lambda: (123,), async_mapping=True)
            rebuild.record("raw")
            rebuild.start(lambda: lane)
            result, _, _, _ = rebuild.pending.result(timeout=2)
        self.assertIs(result, lane)
        lane.consume.assert_called_once_with(123, "raw", async_mapping=True)
