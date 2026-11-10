"""Mode 2's information leg is relative, with an absolute floor.

The old criterion was an absolute bound (25). On one bag the trigger frame's own information
ranged 1.10 to 40.23, so the bound sat inside the range and decided the outcome by which frame
happened to trigger: a candidate that lost 14% of the information passed, one that gained 3-4x
was refused. These fixtures use the measured values, not values chosen to sit above the bound.
"""

import unittest

import numpy as np

from slam_recovery.core import (
    CandidateMap,
    Checkpoint,
    GateThresholds,
    QuarantineSegment,
    RecoveryMode,
    TangentFrame,
    evaluate_four_mode_gate,
)

WORLD = TangentFrame("world", "rot_trans", "world")
V = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])          # so v^T diag(...) v is the [3,3] entry


def _judge(before_info: float, after_info: float):
    ckpt = Checkpoint("ckpt", 0, 0, {}, [], np.zeros(3), np.zeros(3))
    diag_b = np.diag([60.0, 60.0, 60.0, before_info, 60.0, 60.0])
    diag_a = np.diag([60.0, 60.0, 60.0, after_info, 60.0, 60.0])
    seg = QuarantineSegment(
        "seg", ckpt, 0, 4_000_000_000, V, diag_b, 0.1,
        weak_direction_frame=WORLD, info_before_frame=WORLD, anchor_pose_world=np.eye(4))
    cand = CandidateMap(
        "cand", 0, {1: np.eye(4)}, diag_a, np.eye(6) * 0.02, 0.1,
        info_after_frame=WORLD, cov_after_frame=WORLD,
        paired_benefit_approved=True, wilson_lower_bound=0.9,
        reentry_pos_jump_m=0.02, reentry_elapsed_s=0.0)
    return evaluate_four_mode_gate(seg, cand, GateThresholds())


class InformationLegTest(unittest.TestCase):
    def test_a_measured_onset_candidate_passes(self):
        """before 1.1019 -> after 4.628 is the real onset pair (ratio 4.2)."""
        rep = _judge(1.1019, 4.628)
        self.assertEqual(rep.mode, RecoveryMode.MODE2_ATOMIC_COMMIT, rep.reason)

    def test_the_early_trigger_pair_is_refused(self):
        """before 40.23 -> after 34.47 lost 14%; the old absolute bound admitted it."""
        rep = _judge(40.23, 34.47)
        self.assertNotEqual(rep.mode, RecoveryMode.MODE2_ATOMIC_COMMIT)

    def test_a_high_ratio_of_tiny_numbers_is_refused(self):
        """A 5x gain from 0.01 to 0.05 is not enough information, only a large ratio."""
        rep = _judge(0.01, 0.05)
        self.assertNotEqual(rep.mode, RecoveryMode.MODE2_ATOMIC_COMMIT)


if __name__ == "__main__":
    unittest.main()
