from collections import deque
import math
from types import SimpleNamespace
import unittest

import numpy as np

from slam_recovery.vio.run_euroc import Lane
from slam_recovery.vio.stream import Pair
from slam_recovery.vio.vision import gauge_from, in_public_world, qualify_replay, replay_delta


def snapshot(pose):
    return {
        "pose_cw": pose, "inertial": [0.0] * 19 + [1.0],
        "timestamp": 123, "map_id": 0, "maps": 1, "tracking": 2,
        "imu_initialized": True, "inliers": 30, "occupied_cells": 6,
        "reprojection_px": 1.0, "keyframes": 8,
    }


class ReplayTest(unittest.TestCase):
    def test_rigid_gauge_preserves_displacement_and_rejects_drift(self):
        public = snapshot([0, 0, 0, 0, 0, 0, 1])
        q = [0, 0, math.sin(0.3), math.cos(0.3)]
        private = snapshot([9, -1, 2, *q])
        gauge = gauge_from(public, private)
        self.assertTrue(replay_delta(public, in_public_world(private, gauge))["qualified"])
        private["pose_cw"][0] += 0.08
        self.assertFalse(replay_delta(public, in_public_world(private, gauge))["qualified"])

    def test_rebinding_live_standby_composes_the_existing_gauge(self):
        public = deque(maxlen=16)
        raw = deque(maxlen=16)
        for timestamp in range(16):
            public.append(dict(snapshot([0.01 * timestamp, 0, 0, 0, 0, 0, 1]),
                               timestamp=timestamp))
            raw.append(dict(snapshot([2 + 0.01 * timestamp, 0, 0, 0, 0, 0, 1]),
                            timestamp=timestamp))
        marks = []
        emit = SimpleNamespace(emit=lambda kind, **record: marks.append((kind, record)))
        prior = np.eye(3), np.array([-1.0, 0.0, 0.0])
        active = SimpleNamespace(recent=public)
        standby = SimpleNamespace(gauge=prior, recent=deque(
            (in_public_world(row, prior) for row in raw), maxlen=16))
        self.assertTrue(qualify_replay(active, standby, emit, "incremental_checkpoint"))
        np.testing.assert_allclose(standby.gauge[1], [-2, 0, 0])
        np.testing.assert_allclose(
            in_public_world(raw[-1], standby.gauge)["pose_cw"], public[-1]["pose_cw"])
        self.assertTrue(marks[-1][1]["qualified"])

    def test_skipped_observations_preserve_every_imu_sample_once(self):
        class FakeWorker:
            def __init__(self):
                self.batches = []

            def track(self, pair, images, imu):
                self.batches.append(tuple(imu))
                return snapshot([0, 0, 0, 0, 0, 0, 1])

        worker = FakeWorker()
        lane = Lane(worker, delay=0)
        image = np.zeros((50, 50), np.uint8)
        lane.consume(Pair(10, None, None, ()), "raw", (image, image))
        skipped = (11, 0, 0, 0, 0, 0, 0)
        next_sample = (13, 0, 0, 0, 0, 0, 0)
        self.assertIsNone(lane.consume(Pair(12, None, None, (skipped,)), "skip"))
        lane.consume(Pair(14, None, None, (next_sample,)), "raw", (image, image))
        lane.consume(Pair(16, None, None, ()), "raw", (image, image))
        self.assertEqual(worker.batches, [(), (skipped, next_sample), ()])


if __name__ == "__main__":
    unittest.main()
