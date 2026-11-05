"""Tests for timestamp conventions, synchronization offset injection, and window boundaries."""

import unittest
import numpy as np

from slam_recovery.core import StandardFrame
from slam_recovery.experiments.injection import inject_timestamp_offset


class TestTimestampConventions(unittest.TestCase):
    def test_standard_frame_monotonicity(self) -> None:
        frame = StandardFrame(
            sensor_id="velodyne",
            t_start_ns=1_000_000_000,
            t_end_ns=1_100_000_000,
            frame_id="base_link",
            data_ref="bag://0",
        )
        self.assertAlmostEqual(frame.t_mid_sec, 1.05, places=6)
        with self.assertRaises(ValueError):
            StandardFrame(
                sensor_id="velodyne",
                t_start_ns=2_000_000_000,
                t_end_ns=1_000_000_000,
                frame_id="base_link",
                data_ref="bag://1",
            )

    def test_timestamp_offset_injection_window_only(self) -> None:
        ts = np.array([1_000_000_000, 2_000_000_000, 3_000_000_000, 4_000_000_000], dtype=np.int64)
        shifted = inject_timestamp_offset(
            ts,
            offset_ms=50.0,
            window_start_ns=1_500_000_000,
            window_end_ns=3_500_000_000,
        )
        self.assertEqual(shifted[0], 1_000_000_000)
        self.assertEqual(shifted[1], 2_050_000_000)
        self.assertEqual(shifted[2], 3_050_000_000)
        self.assertEqual(shifted[3], 4_000_000_000)


if __name__ == "__main__":
    unittest.main()
