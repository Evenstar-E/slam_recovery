"""A5/A9 on the normal path: every frame has a home, and a repair can be undone.

The review's 2026-11-10 handoff names three holes that the earlier counterexamples did not cover
because they only exercised the abnormal entry points:

  1. the frame that *sets off* the alarm is never registered in the pending population -- it is
     neither promoted (it was never fed to step_healthy) nor deferred (it arrives before the
     segment exists);
  2. a repair that is later revoked leaves its frames in no population at all: they are removed
     from the trusted map but neither re-queued nor listed, so "where did frame k go" has no answer;
  3. a segment that is still waiting keeps the timestamp of its trigger, so frames that arrive
     while waiting are recorded with a time that never advances.

Each test fails on the pre-fix code for the reason it states.
"""

import unittest

import numpy as np

from slam_recovery.core import (
    BackendDelta,
    CandidateMap,
    RecoveryState,
    TangentFrame,
)
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode

WORLD = TangentFrame("world", "rot_trans", "world")


def _delta(kf_id: int, ts_ns: int, x: float) -> BackendDelta:
    pose = np.eye(4)
    pose[0, 3] = x
    return BackendDelta(
        timestamp_ns=ts_ns, frame_id="map", pose_se3=pose,
        velocity=np.zeros(3), bias_acc=np.zeros(3), bias_gyr=np.zeros(3),
        cov_6x6=np.eye(6) * 0.01, info_6x6=np.eye(6) * 100.0,
        nis_value=1.0, nis_dof=6, factor_ids=[kf_id * 10], keyframe_id=kf_id)


def _candidate(version: int, poses: dict) -> CandidateMap:
    return CandidateMap(
        candidate_id="repair", parent_map_version=version, repaired_poses=dict(poses),
        info_after_6x6=np.diag([60.0, 60.0, 60.0, 45.0, 60.0, 60.0]),
        cov_after_6x6=np.eye(6) * 0.05, holdout_nis=1.2,
        paired_benefit_approved=True, wilson_lower_bound=0.90, reentry_pos_jump_m=0.05,
        info_after_frame=WORLD, cov_after_frame=WORLD)


def _trigger(mgr, onset_ns: int, current_ns: int):
    return mgr.trigger_quarantine(
        estimated_onset_ns=onset_ns, current_ns=current_ns,
        weak_direction_6d=np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0]),
        info_before_6x6=np.eye(6) * 10.0, propagated_cov_norm=1.0,
        weak_direction_frame=WORLD, info_before_frame=WORLD,
        anchor_pose_world=np.eye(4))


class AlarmFrameRegistrationTest(unittest.TestCase):
    def test_the_frame_that_trips_the_alarm_has_a_home(self):
        """The alarm frame is neither promoted nor queued before the trigger, so it disappears."""
        rng = np.random.default_rng(0)
        node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0.0)
        scan = rng.normal(size=(400, 3)) * 2.0
        alarm_kf = None
        for kf in range(1, 6):
            node.step_frame(kf, kf * 100_000_000, np.eye(4), scan, 8.0)
            if node.tx_mgr.state == RecoveryState.QUARANTINED:
                alarm_kf = kf
                break
        self.assertIsNotNone(alarm_kf, "the detector never tripped on this fixture")
        refs = node.tx_mgr.active_quarantine.raw_frame_refs
        self.assertIn(str(alarm_kf), refs,
                      f"alarm frame {alarm_kf} is in no population; refs={refs}")


class RepairRevocationPopulationTest(unittest.TestCase):
    def test_revoked_repair_frames_return_to_the_pending_population(self):
        """A repair commits 2 and 3; a later onset covering them removes their poses.

        Their home after the undo must be the new quarantine, otherwise the frames exist neither
        in the trusted map nor in any pending list and can never be resolved.
        """
        mgr = TrustedMapTransactionManager(confirmation_margin_ns=0)
        for k in (1, 2, 3):
            mgr.step_healthy(_delta(k, k * 100_000_000, 0.1 * k))
        _trigger(mgr, 2 * 100_000_000, 3 * 100_000_000)

        p2, p3 = np.eye(4), np.eye(4)
        p2[0, 3], p3[0, 3] = 9.0, 9.3
        rep = mgr.validate_and_resolve(_candidate(mgr.trusted_version, {2: p2, 3: p3}))
        self.assertTrue(rep.accepted)
        self.assertIn(2, mgr.trusted_poses)

        mgr.step_healthy(_delta(4, 400_000_000, 0.4))
        _trigger(mgr, 1 * 100_000_000, 500_000_000)   # onset reaches back over the repair

        self.assertNotIn(2, mgr.trusted_poses)
        refs = mgr.active_quarantine.raw_frame_refs if mgr.active_quarantine else []
        self.assertIn("2", refs, f"revoked repair frame 2 is in no population; refs={refs}")
        self.assertIn("3", refs, f"revoked repair frame 3 is in no population; refs={refs}")


class WaitingSegmentTimeTest(unittest.TestCase):
    def test_a_frame_arriving_while_waiting_advances_the_segment_time(self):
        """t_end must follow the real arrival, not stay at the trigger instant."""
        mgr = TrustedMapTransactionManager(confirmation_margin_ns=0)
        for k in (1, 2, 3):
            mgr.step_healthy(_delta(k, k * 100_000_000, 0.1 * k))
        seg = _trigger(mgr, 2 * 100_000_000, 3 * 100_000_000)
        self.assertEqual(seg.t_end_ns, 300_000_000)
        mgr.register_quarantined_frame(4, 400_000_000)
        self.assertEqual(mgr.active_quarantine.t_end_ns, 400_000_000,
                         "a frame that arrives while waiting is recorded with a stale segment time")


if __name__ == "__main__":
    unittest.main()


class ReentryEvidenceLegTest(unittest.TestCase):
    """The gate's re-entry leg and the boundary check must use one definition.

    A 1.2506 m displacement 2.329 s after the anchor is 0.54 m/s of motion. Before the fix the
    boundary check learned that and the evidence leg did not, so the same run failed twice on the
    same number under two names.
    """

    def _report(self, elapsed):
        from slam_recovery.core import evaluate_four_mode_gate

        mgr = TrustedMapTransactionManager(confirmation_margin_ns=0)
        for k in (1, 2, 3):
            mgr.step_healthy(_delta(k, k * 100_000_000, 0.1 * k))
        seg = _trigger(mgr, 2 * 100_000_000, 3 * 100_000_000)
        cand = _candidate(seg.checkpoint.map_version, {2: np.eye(4)})
        cand.reentry_pos_jump_m = 1.2506
        cand.reentry_elapsed_s = elapsed
        return evaluate_four_mode_gate(seg, cand)

    def test_motion_over_the_margin_is_not_a_discontinuity(self):
        rep = self._report(2.329)
        self.assertNotEqual(rep.evidence_status, "FAILED")

    def test_the_same_jump_with_no_elapsed_time_is_refused(self):
        self.assertEqual(self._report(0.0).evidence_status, "FAILED")

    def test_an_undated_jump_keeps_the_strict_reading(self):
        self.assertEqual(self._report(None).evidence_status, "FAILED")
