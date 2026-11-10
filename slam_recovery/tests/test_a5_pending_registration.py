"""A5: the pending population belongs to the system, not to whatever a candidate declares.

Review counter-example: with confirmation_margin_ns=0, healthy keys 1/2/3 and a quarantine segment
whose raw_frame_refs is empty, a candidate that commits key 1 and declares no deferrals used to
leave pending empty -- the manager returned to HEALTHY with keys 2 and 3 never committed, never
declared and silently dropped.

Both tests assert on validate_and_resolve's observable output (report.remaining_pending_pose_keys
and the manager state), not on internal fields.
"""

import unittest

import numpy as np

from slam_recovery.core import BackendDelta, CandidateMap, RecoveryState
from slam_recovery.quarantine import TrustedMapTransactionManager


def _delta(kf_id: int, ts_ns: int) -> BackendDelta:
    pose = np.eye(4)
    pose[0, 3] = 0.1 * kf_id
    return BackendDelta(
        timestamp_ns=ts_ns,
        frame_id="map",
        pose_se3=pose,
        velocity=np.zeros(3),
        bias_acc=np.zeros(3),
        bias_gyr=np.zeros(3),
        cov_6x6=np.eye(6) * 0.01,
        info_6x6=np.eye(6) * 100.0,
        nis_value=1.0,
        nis_dof=6,
        factor_ids=[kf_id * 10],
        keyframe_id=kf_id,
    )


def _candidate(version: int, poses) -> CandidateMap:
    return CandidateMap(
        candidate_id="a5_candidate",
        parent_map_version=version,
        repaired_poses=dict(poses),
        info_after_6x6=np.diag([60, 60, 60, 45.0, 60, 60]),
        cov_after_6x6=np.eye(6) * 0.05,
        holdout_nis=1.2,
        paired_benefit_approved=True,
        wilson_lower_bound=0.90,
        reentry_pos_jump_m=0.05,
    )


class A5PendingRegistrationTest(unittest.TestCase):
    def _triggered(self):
        """margin=0, healthy 1..3, quarantine opens at key 2 so keys 2 and 3 are rolled back."""
        mgr = TrustedMapTransactionManager(confirmation_margin_ns=0)
        for k in (1, 2, 3):
            mgr.step_healthy(_delta(k, k * 100_000_000))
        seg = mgr.trigger_quarantine(
            estimated_onset_ns=2 * 100_000_000,
            current_ns=3 * 100_000_000,
            weak_direction_6d=np.array([0, 0, 0, 1, 0, 0], dtype=np.float64),
            info_before_6x6=np.eye(6) * 10.0,
            propagated_cov_norm=1.0,
        )
        return mgr, seg

    def test_committing_one_frame_does_not_finish_the_quarantine(self):
        mgr, seg = self._triggered()
        # the segment registers the frames the system rolled back
        self.assertEqual(sorted(int(r) for r in seg.raw_frame_refs), [2, 3])

        rep = mgr.validate_and_resolve(_candidate(mgr.trusted_version, {1: np.eye(4)}))
        self.assertEqual(rep.remaining_pending_pose_keys, [2, 3])
        self.assertNotEqual(mgr.state, RecoveryState.HEALTHY)

        rep2 = mgr.validate_and_resolve(
            _candidate(mgr.trusted_version, {2: np.eye(4), 3: np.eye(4)}))
        self.assertEqual(rep2.remaining_pending_pose_keys, [])
        self.assertEqual(mgr.state, RecoveryState.HEALTHY)

    def test_a_frame_arriving_during_the_quarantine_is_registered(self):
        mgr, _seg = self._triggered()
        mgr.register_quarantined_frame(4, 4 * 100_000_000)
        self.assertIn("4", mgr.active_quarantine.raw_frame_refs)

        rep = mgr.validate_and_resolve(
            _candidate(mgr.trusted_version, {2: np.eye(4), 3: np.eye(4)}))
        self.assertEqual(rep.remaining_pending_pose_keys, [4])
        self.assertNotEqual(mgr.state, RecoveryState.HEALTHY)


if __name__ == "__main__":
    unittest.main()
