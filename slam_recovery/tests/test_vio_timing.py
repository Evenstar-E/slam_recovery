from pathlib import Path
import unittest

import numpy as np

from slam_recovery.vio.stream import InputFault, Pair
from slam_recovery.vio.timing_recovery import (ImagePacket, ImuTimeline,
                                              pair_stereo, qualify_offset)


class TimingRecoveryTest(unittest.TestCase):
    def test_delayed_stereo_mate_keeps_physical_identity(self):
        left, right = Path("left"), Path("right")
        feed = [
            (100, ImagePacket(0, 100, left)),
            (150, ImagePacket(0, 150, left)),
            (150, ImagePacket(1, 100, right)),
            (200, ImagePacket(1, 150, right)),
        ]
        self.assertEqual(list(pair_stereo(feed, 80)), [(100, left, right), (150, left, right)])
        with self.assertRaises(InputFault):
            list(pair_stereo(feed[:2] + feed[3:], 80))

    def test_camera_clock_correction_reassigns_raw_imu_without_duplicates(self):
        period = 5_000_000
        jump = 50_000_000
        rows = [(i*period, 0, 0, 9.81, 0, 0, 2*np.sin(i*period/1e9*14))
                for i in range(650)]
        timeline = ImuTimeline(rows)
        frames = [i*jump for i in range(12, 56)]
        observations = [(a+jump, b+jump, timeline.camera_rotation(a, b, np.eye(3)))
                        for a, b in zip(frames, frames[1:])]
        decision = qualify_offset(observations, timeline, np.eye(3))
        self.assertTrue(decision["accepted"], decision)
        self.assertEqual(decision["estimated_correction_ms"], -50.0)
        observed = [Pair(stamp+jump, Path("left"), Path("right"), ()) for stamp in frames[:2]]
        corrected = list(timeline.reassign(observed, frames[0]-jump, -jump))
        self.assertEqual([frame.timestamp for frame in corrected], frames[:2])
        self.assertEqual([len(frame.imu) for frame in corrected], [10, 10])
        self.assertEqual(corrected[0].imu[-1][0]+period, corrected[1].imu[0][0])
        with self.assertRaises(InputFault):
            list(timeline.reassign(observed, frames[0], -jump))
