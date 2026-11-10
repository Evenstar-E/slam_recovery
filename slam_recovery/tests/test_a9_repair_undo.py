"""A9: a Mode 2 repair must be visible to the undo log.

Counter-example: a repair commits frames, a second onset opens earlier than that repair, and the
rollback cannot undo it because the repair was never written into promoted_history. The assertion
is on observable output (trusted_poses, trusted_version), not on the undo log itself.
"""

import unittest

import numpy as np

from slam_recovery.core import BackendDelta, CandidateMap, RecoveryState
from slam_recovery.quarantine import TrustedMapTransactionManager


def _delta(kf_id: int, ts_ns: int, x: float) -> BackendDelta:
    pose = np.eye(4)
    pose[0, 3] = x
    return BackendDelta(
        timestamp_ns=ts_ns, frame_id="map", pose_se3=pose,
        velocity=np.zeros(3), bias_acc=np.zeros(3), bias_gyr=np.zeros(3),
        cov_6x6=np.eye(6) * 0.01, info_6x6=np.eye(6) * 100.0,
        nis_value=1.0, nis_dof=6, factor_ids=[kf_id * 10], keyframe_id=kf_id)


def _candidate(version, poses):
    return CandidateMap(
        candidate_id="a9_repair", parent_map_version=version, repaired_poses=dict(poses),
        info_after_6x6=np.diag([60, 60, 60, 45.0, 60, 60]), cov_after_6x6=np.eye(6) * 0.05,
        holdout_nis=1.2, paired_benefit_approved=True, wilson_lower_bound=0.90,
        reentry_pos_jump_m=0.05)


class A9RepairUndoTest(unittest.TestCase):
    def test_second_onset_undoes_the_repair(self):
        mgr = TrustedMapTransactionManager(confirmation_margin_ns=0)
        for k in (1, 2, 3):
            mgr.step_healthy(_delta(k, k * 100_000_000, 0.1 * k))
        mgr.trigger_quarantine(
            estimated_onset_ns=2 * 100_000_000, current_ns=3 * 100_000_000,
            weak_direction_6d=np.array([0, 0, 0, 1, 0, 0], dtype=np.float64),
            info_before_6x6=np.eye(6) * 10.0, propagated_cov_norm=1.0)
        # the quarantine rolled 2 and 3 back, so 2 does not exist before the repair
        existed_before = 2 in mgr.trusted_poses

        repaired = np.eye(4)
        repaired[0, 3] = 9.0
        repaired3 = np.eye(4)
        repaired3[0, 3] = 9.3
        rep = mgr.validate_and_resolve(
            _candidate(mgr.trusted_version, {2: repaired, 3: repaired3}))
        self.assertTrue(rep.accepted)
        self.assertAlmostEqual(float(mgr.trusted_poses[2][0, 3]), 9.0)

        # a second onset whose window covers the repair
        mgr.step_healthy(_delta(4, 4 * 100_000_000, 0.4))
        mgr.trigger_quarantine(
            estimated_onset_ns=1 * 100_000_000, current_ns=5 * 100_000_000,
            weak_direction_6d=np.array([0, 0, 0, 1, 0, 0], dtype=np.float64),
            info_before_6x6=np.eye(6) * 10.0, propagated_cov_norm=1.0)

        # undo restores the pre-repair state: a key that did not exist is removed again
        self.assertFalse(existed_before)
        self.assertNotIn(2, mgr.trusted_poses)
        self.assertNotIn(3, mgr.trusted_poses)


if __name__ == "__main__":
    unittest.main()
