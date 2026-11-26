import json
from pathlib import Path
import tempfile
import unittest

from slam_recovery.ros.refusal_comparison import summarize_refusal_comparison


class TestRefusalComparison(unittest.TestCase):
    def test_native_loss_does_not_count_unmeasured_groups_as_improvement(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "refusal_comparison.jsonl"
            rows = [
                ("native", 11, "lidar_tracking"), ("native", 12, "native_reset_due"),
                ("refusal", 11, "lidar_tracking"), ("refusal", 12, "imu_only"),
                ("refusal", 13, "lidar_tracking"),
            ]
            path.write_text("".join(json.dumps(
                dict(branch=arm, checkpoint_ns=10, target_ns=14,
                     scan_ns=scan, end_ns=scan+1, result=state))+"\n"
                for arm, scan, state in rows))
            result = summarize_refusal_comparison(path, 10, 14, 3)
            self.assertEqual(result["status"], "NATIVE_STOPPED_EARLY")
            self.assertEqual(result["native_reset_scan_ns"], 12)
            self.assertEqual(result["matched_outcomes"],
                             {"both_lidar_tracking": 1, "protected_imu_only": 1,
                              "native_unmeasured": 1})


if __name__ == "__main__":
    unittest.main()
