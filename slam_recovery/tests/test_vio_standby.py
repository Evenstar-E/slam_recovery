from concurrent.futures import ThreadPoolExecutor
from threading import Event
import unittest

from slam_recovery.vio.standby import StandbyQueue, StandbyTimeout


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
