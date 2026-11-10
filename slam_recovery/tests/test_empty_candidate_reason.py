"""An absent candidate and a malformed one must not share one refusal.

The hall icp run produced no poses at all (REFERENCE_TOO_SMALL: the trusted map had no points
yet). The gate reported "non-finite state/bias or invalid SE(3) pose shape", which points at the
pose chain; the real cause was upstream and lived in a side file. The numbers had the same
problem: `weak_dir_info_after` was recorded as 0.0, which reads as "measured, very low" rather
than "not measured".

These two fixtures pin the distinction: empty -> "no candidate was produced" with a null
information value; NaN pose -> the malformed-candidate refusal, also with a null value (the
information is not finite, so it was never measured either).
"""

import unittest

import numpy as np

from slam_recovery.core import (
    CandidateMap,
    Checkpoint,
    QuarantineSegment,
    RecoveryMode,
    TangentFrame,
    evaluate_four_mode_gate,
)

WORLD = TangentFrame("world", "rot_trans", "world")
V = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])


def _segment() -> QuarantineSegment:
    checkpoint = Checkpoint("probe", 0, 0, {}, [], np.zeros(3), np.zeros(3))
    return QuarantineSegment(
        "segment", checkpoint, 0, 4_000_000_000, V,
        np.diag([60.0, 60.0, 60.0, 20.0, 40.0, 40.0]), 0.1,
        weak_direction_frame=WORLD, info_before_frame=WORLD, anchor_pose_world=np.eye(4))


def _candidate(poses) -> CandidateMap:
    return CandidateMap(
        "cand", 0, poses,
        np.diag([60.0, 60.0, 60.0, 30.0, 40.0, 40.0]), np.eye(6) * 0.01, 1.0,
        info_after_frame=WORLD, cov_after_frame=WORLD,
        paired_benefit_approved=True, wilson_lower_bound=0.9, reentry_pos_jump_m=0.05)


class TestEmptyCandidateIsNotMalformed(unittest.TestCase):
    def test_an_empty_candidate_says_so_and_measures_nothing(self):
        report = evaluate_four_mode_gate(_segment(), _candidate({}))
        self.assertFalse(report.accepted)
        self.assertIs(report.mode, RecoveryMode.MODE3_SOFT_BRIDGE_WAIT)
        self.assertIn("No candidate was produced", report.reason)
        self.assertNotIn("pose shape", report.reason)
        self.assertIsNone(report.weak_dir_info_after)
        self.assertIsNone(report.weak_dir_info_gain)

    def test_a_nan_pose_is_still_malformed(self):
        bad = np.full((4, 4), np.nan)
        report = evaluate_four_mode_gate(_segment(), _candidate({1: bad}))
        self.assertFalse(report.accepted)
        self.assertIn("non-finite", report.reason)
        self.assertIsNone(report.weak_dir_info_after)

    def test_a_normal_candidate_still_reports_its_measured_information(self):
        report = evaluate_four_mode_gate(_segment(), _candidate({1: np.eye(4)}))
        self.assertIsNotNone(report.weak_dir_info_after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
