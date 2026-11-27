from collections import deque
import threading
import time
from types import SimpleNamespace
import unittest

from slam_recovery.vio.hosts.bridge import NativeLane
from slam_recovery.vio.hosts.controller import Recovery


class Lane:
    timing = None

    def __init__(self, release=None):
        self.release = release
        self.entered = threading.Event()
        self.recent = deque(maxlen=16)
        self.gauge = None

    def step(self, pair, images, imu):
        self.entered.set()
        if self.release and not self.release.wait(2):
            raise RuntimeError("test did not release the standby")
        row = {"timestamp": pair.timestamp, "pose_cw": [0, 0, 0, 0, 0, 0, 1],
               "inertial": [0]*9}
        self.recent.append(row)
        return row


class HostScheduleTest(unittest.TestCase):
    def test_public_delivery_does_not_wait_for_standby(self):
        release = threading.Event()
        delivered = threading.Event()
        publisher = SimpleNamespace(send=lambda row: delivered.set() or 1)
        observed = []
        events = SimpleNamespace(emit=lambda kind, **kwargs: observed.append(kind))
        standby = Lane(release)
        controller = Recovery(Lane(), standby, None, events, publisher)
        runner = threading.Thread(
            target=controller.forward, args=(SimpleNamespace(timestamp=1), None, (), "native"))
        runner.start()
        try:
            self.assertTrue(standby.entered.wait(1))
            self.assertTrue(delivered.wait(1))
            qualified, _, reason = controller.qualify_spare(1)
            self.assertFalse(qualified)
            self.assertEqual(reason, "standby_boundary_late")
            self.assertIs(controller.spare, standby)
            self.assertTrue(controller.spare_lagged)
            release.set()
            controller.mirror.at_boundary(1)
            for stamp in range(2, 13):
                controller.forward(SimpleNamespace(timestamp=stamp), None, (), "native")
                controller.mirror.at_boundary(1)
            controller.observe_spare(13)
            self.assertFalse(controller.spare_lagged)
            self.assertIn("standby_requalified", observed)
            self.assertEqual([row["timestamp"] for row in standby.recent], list(range(1, 13)))
        finally:
            release.set()
            runner.join()
            controller.close()


    def test_boundary_wait_replays_held_frames_once_after_requalification(self):
        publisher = SimpleNamespace(send=lambda row: 1)
        observed = []
        events = SimpleNamespace(emit=lambda kind, **fields: observed.append((kind, fields)))
        controller = Recovery(Lane(), Lane(), None, events, publisher, serial=True)
        controller.isolated = controller.awaiting_boundary = True
        controller.pending = [(SimpleNamespace(timestamp=stamp), None, (), True)
                              for stamp in (100, 200)]
        received = []
        controller.candidate = lambda pair, *args: received.append(pair.timestamp)
        checks = iter([(False, None, "standby_boundary_late"), (True, [0]*5, "")])
        controller.qualify_spare = lambda stamp, wait: next(checks)

        controller.try_fault_boundary(200, first=True)
        self.assertTrue(controller.awaiting_boundary)
        self.assertEqual(received, [])
        controller.step(SimpleNamespace(timestamp=300), None, (), True)
        self.assertFalse(controller.awaiting_boundary)
        self.assertEqual(received, [100, 200, 300])
        self.assertEqual(sum(kind == "standby_boundary_wait" for kind, _ in observed), 1)
        self.assertTrue(observed[-1][1]["qualified"])


class CallbackIdentityTest(unittest.TestCase):
    def test_keep_physical_callback_identity_and_count_a_missed_frame(self):
        lane = NativeLane.__new__(NativeLane)
        lane.awaiting = deque([10, 20, 30])
        lane.resolved = lane.callback_gaps = lane.late_callbacks = 0
        lane.recent = deque(maxlen=16)
        now = time.monotonic_ns()
        packets = iter([f"batch 30 {now} {now} 2".encode(), b"20 1", b"30 1"])
        lane.readline = lambda _: next(packets)
        lane.decode = lambda row, expected: {"timestamp": expected}
        self.assertEqual([r["timestamp"] for r in lane.read_callbacks(30, now)], [20, 30])
        self.assertEqual(lane.callback_gaps, 1)

    def test_unrequested_callback_cannot_be_published(self):
        lane = NativeLane.__new__(NativeLane)
        lane.awaiting = deque([10])
        lane.resolved = 0
        now = time.monotonic_ns()
        packets = iter([f"batch 10 {now} {now} 1".encode(), b"11 1"])
        lane.readline = lambda _: next(packets)
        with self.assertRaisesRegex(RuntimeError, "unrequested native callback"):
            lane.read_callbacks(10, now)


if __name__ == "__main__":
    unittest.main()
