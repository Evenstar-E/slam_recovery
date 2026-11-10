"""The gate's `after` must be reconstructible from a run, not re-invented from a name.

The archived streams record whether a candidate passed and nothing about which frames formed
`info_after` or with which poses. When the FIM producer was found to be sampling-dependent, that
made the new-scale values impossible to derive from any existing run: substituting "all scans in
the quarantine window at host poses" would be a different quantity with the same name. This
sidecar is the minimum fix -- the frame ids, their timestamps and the scored poses.
"""

import unittest

import numpy as np

from slam_recovery.ros.recovery_node import candidate_detail_record


class TestCandidateDetailRecord(unittest.TestCase):
    def test_records_the_frame_set_and_poses_the_gate_scored(self):
        pose = np.eye(4)
        pose[0, 3] = 1.5
        row = candidate_detail_record(
            "cand_0001", 100, 200, keys=[3, 4],
            ts_by_key={3: 110, 4: 140},
            repaired_poses={3: pose, 4: np.eye(4)})
        self.assertEqual(row["candidate_frame_ids"], [3, 4])
        self.assertEqual(row["candidate_frame_ts_ns"], [110, 140])
        self.assertEqual(len(row["repaired_poses"]["3"]), 16)
        self.assertAlmostEqual(row["repaired_poses"]["3"][3], 1.5)

    def test_a_missing_timestamp_is_zero_not_dropped(self):
        """Zero says "this frame has no recorded time"; dropping the entry would shorten the
        list and silently change the frame set the record claims."""
        row = candidate_detail_record("c", 1, 2, [7], {}, {7: np.eye(4)})
        self.assertEqual(row["candidate_frame_ids"], [7])
        self.assertEqual(row["candidate_frame_ts_ns"], [0])

    def test_an_empty_candidate_is_recorded_as_empty(self):
        row = candidate_detail_record("c", None, 2, [], {}, {})
        self.assertEqual(row["candidate_frame_ids"], [])
        self.assertEqual(row["repaired_poses"], {})
        self.assertIsNone(row["t_trigger_ns"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
