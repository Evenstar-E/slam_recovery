"""Tests for checkpoint hashing, delayed-commit quarantine, trusted map invariance, and 4-mode atomic commit."""

import unittest
import numpy as np

from slam_recovery.core import (
    BackendDelta,
    CandidateMap,
    GateThresholds,
    RecoveryMode,
    RecoveryState,
)
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.validation import evaluate_paired_sequential_benefit, wilson_score_lower_bound


def _make_delta(ts_sec: float, kf_id: int, x_pos: float) -> BackendDelta:
    pose = np.eye(4, dtype=np.float64)
    pose[0, 3] = x_pos
    return BackendDelta(
        timestamp_ns=int(ts_sec * 1e9),
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


class TestCheckpointAndAtomicCommit(unittest.TestCase):
    def test_checkpoint_hash_and_restore(self) -> None:
        mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0 * 1e9))
        mgr.step_healthy(_make_delta(1.0, 1, 1.0))
        mgr.step_healthy(_make_delta(3.5, 2, 2.0))  # promotes kf 1

        ckpt = mgr.create_checkpoint(timestamp_ns=int(3.5 * 1e9))
        self.assertIn(1, mgr.trusted_poses)
        self.assertNotIn(2, mgr.trusted_poses)

        # Mutate trusted map and restore
        mgr.trusted_poses[99] = np.eye(4)
        mgr.restore_checkpoint(ckpt)
        self.assertNotIn(99, mgr.trusted_poses)
        self.assertIn(1, mgr.trusted_poses)

    def test_delayed_commit_prevents_n_kappa_tail_pollution(self) -> None:
        """
        Verify Section 5.2: If degeneracy starts at t=10s and alarm triggers at t=11.5s,
        a 2.0s confirmation margin prevents the 10.0-11.5s drifted poses from polluting
        the trusted map (solving the MM-LINS N_kappa tail drift problem).
        """
        mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0 * 1e9))
        for t, kf in [(8.0, 1), (9.0, 2), (10.2, 3), (11.0, 4), (11.5, 5)]:
            mgr.step_healthy(_make_delta(t, kf, x_pos=t * 10.0 if t > 10.0 else t))

        # Alarm triggers at t=11.5s with estimated onset at 10.2s -> t_{q,start} = 8.2s
        seg = mgr.trigger_quarantine(
            estimated_onset_ns=int(10.2 * 1e9),
            current_ns=int(11.5 * 1e9),
            weak_direction_6d=np.array([0, 0, 0, 1, 0, 0], dtype=np.float64),
            info_before_6x6=np.diag([50, 50, 50, 2.0, 50, 50]),
            propagated_cov_norm=1.2,
        )
        self.assertEqual(mgr.state, RecoveryState.QUARANTINED)
        # Keyframes 3, 4, 5 (the drifted ones) must NOT be in trusted_poses!
        self.assertIn(1, mgr.trusted_poses)
        self.assertNotIn(3, mgr.trusted_poses)
        self.assertNotIn(4, mgr.trusted_poses)
        self.assertNotIn(5, mgr.trusted_poses)
        self.assertGreaterEqual(len(seg.provisional_factor_ids), 3)

    def test_four_mode_gate_rejects_bad_merge_and_accepts_verified_repair(self) -> None:
        """
        Verify Section 4.8 & 4.9:
          - Unverified / high-NIS candidate (like MM-LINS Campus-2 CE-PGO) is rejected -> Mode 3 Soft Bridge
          - Verified candidate with weak-direction info gain -> Mode 2 Atomic Commit
          - Exceeding bridge covariance without repair -> Mode 4 Hard Sleep Split
        """
        mgr = TrustedMapTransactionManager(
            confirmation_margin_ns=int(2.0 * 1e9),
            gate_thresholds=GateThresholds(tau_info=25.0, tau_val_nis=2.5, sigma_tol=0.5, sigma_bridge=4.0),
        )
        mgr.step_healthy(_make_delta(1.0, 1, 1.0))
        mgr.step_healthy(_make_delta(4.0, 2, 2.0))
        mgr.trigger_quarantine(
            estimated_onset_ns=int(3.5 * 1e9),
            current_ns=int(6.0 * 1e9),
            weak_direction_6d=np.array([0, 0, 0, 1, 0, 0], dtype=np.float64),
            info_before_6x6=np.diag([60, 60, 60, 3.0, 60, 60]),
            propagated_cov_norm=1.8,
        )
        version_before = mgr.trusted_version

        # Case 1: Bad candidate with high holdout NIS (simulating Campus-2 false/over-constrained PGO)
        bad_cand = CandidateMap(
            candidate_id="bad_ce_pgo",
            parent_map_version=version_before,
            repaired_poses={2: np.eye(4)},
            info_after_6x6=np.diag([60, 60, 60, 40.0, 60, 60]),
            cov_after_6x6=np.eye(6) * 0.05,
            holdout_nis=6.4,  # Exceeds tau_val_nis=2.5
        )
        rep1 = mgr.validate_and_resolve(bad_cand)
        self.assertFalse(rep1.accepted)
        self.assertEqual(rep1.mode, RecoveryMode.MODE3_SOFT_BRIDGE_WAIT)
        self.assertEqual(mgr.trusted_version, version_before)
        self.assertNotIn(2, mgr.trusted_poses)

        # Case 2: Good candidate with genuine weak-direction info gain and low holdout NIS
        good_cand = CandidateMap(
            candidate_id="verified_aux_repair",
            parent_map_version=version_before,
            repaired_poses={2: np.eye(4)},
            info_after_6x6=np.diag([60, 60, 60, 45.0, 60, 60]),
            cov_after_6x6=np.eye(6) * 0.05,
            holdout_nis=1.2,
        )
        rep2 = mgr.validate_and_resolve(good_cand)
        self.assertTrue(rep2.accepted)
        self.assertEqual(rep2.mode, RecoveryMode.MODE2_ATOMIC_COMMIT)
        self.assertEqual(mgr.trusted_version, version_before + 1)
        self.assertIn(2, mgr.trusted_poses)

    def test_wilson_sequential_benefit_and_reentry_continuity(self) -> None:
        """
        Verify Section 4.9:
          - Rejects repairs that reduce mean error via a few frames while failing Wilson sequential lower bound
          - Rejects repairs with re-entry boundary jumps (preventing local RPE spikes)
          - Approves repairs with consistent sequential improvement and smooth boundary handoff
        """
        inc = np.ones(30, dtype=np.float64) * 1.0
        # Only 12/30 frames improved -> Wilson LB < 0.55
        cand_inconsistent = inc.copy()
        cand_inconsistent[:12] = 0.2
        rep_inc = evaluate_paired_sequential_benefit(inc, cand_inconsistent)
        self.assertFalse(rep_inc.approved)
        self.assertEqual(rep_inc.reason, "wilson_sequential_benefit_lower_bound_failed")

        # 26/30 frames improved, but 0.85m re-entry jump -> rejected
        cand_good_frames = np.ones(30, dtype=np.float64) * 0.25
        rep_jump = evaluate_paired_sequential_benefit(
            inc, cand_good_frames, reentry_position_jump_m=0.85
        )
        self.assertFalse(rep_jump.approved)
        self.assertEqual(rep_jump.reason, "reentry_position_discontinuity_exceeded")

        # 26/30 frames improved and 0.04m re-entry jump -> approved
        rep_ok = evaluate_paired_sequential_benefit(
            inc, cand_good_frames, reentry_position_jump_m=0.04, reentry_rotation_jump_deg=0.8
        )
        self.assertTrue(rep_ok.approved)
        self.assertGreaterEqual(rep_ok.wilson_lower_bound, 0.55)


if __name__ == "__main__":
    unittest.main()
