import json
import tempfile
from pathlib import Path
import unittest

import numpy as np

from slam_recovery.ros.imu_recovery_observation import ImuRecoveryObservations, score_imu_observation
from slam_recovery.validation.spatial_index import RadiusIndex


class TestImuRecoveryObservation(unittest.TestCase):
    def test_reader_leaves_future_scan_for_its_own_frame(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "imu.jsonl"
            p.write_text(json.dumps({"scan_ns": 10000}) + "\n")
            reader = ImuRecoveryObservations(p)
            self.assertIsNone(reader.at_scan(8000))
            self.assertEqual(reader.at_scan(10001)["scan_ns"], 10000)
            self.assertIsNone(reader.at_scan(10001))

    def test_same_scan_support_can_return_without_accepting_uncertain_prediction(self):
        x, y = np.meshgrid(np.arange(-2., 2.1, .25), np.arange(-2., 2.1, .25))
        plane = np.column_stack((x.ravel(), y.ravel(), np.zeros(x.size)))
        index = RadiusIndex(plane, 1.)
        clean = plane[20:-20:2]
        row = {"checkpoint_ns": 100, "position_sigma_m": .1,
               "points": np.hstack((clean+[0,0,2], clean+[0,0,.2], clean))}
        result = score_imu_observation(row, index, .12, 10, 200, .5)
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertIsNone(result["fused_raw"]["nis"])
        self.assertGreater(result["imu_raw"]["nis"], 0.)
        self.assertAlmostEqual(result["imu_deskewed"]["nis"], 0.)
        row["position_sigma_m"] = 2.
        self.assertEqual(score_imu_observation(row, index,.12,10,200,.5)["status"],
                         "PREDICTION_UNCERTAINTY")
        self.assertEqual(score_imu_observation(row, index,.12,10,90,.5)["status"],
                         "INVALID_CHECKPOINT")


if __name__ == "__main__":
    unittest.main()
