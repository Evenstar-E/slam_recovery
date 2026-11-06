"""Tests for trusted map invariance under soft bridge (Mode 3) and hard sleep split (Mode 4)."""

import unittest
import numpy as np

from slam_recovery.core import GateThresholds, RecoveryMode, RecoveryState
from slam_recovery.experiments.evaluation import compute_recovery_ratio_G
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.tests.test_atomic_commit import _make_delta


class TestTrustedMapInvariance(unittest.TestCase):
    def test_trusted_map_invariant_during_mode3_and_archived_on_mode4(self) -> None:
        mgr = TrustedMapTransactionManager(
            confirmation_margin_ns=int(1.0 * 1e9),
            gate_thresholds=GateThresholds(tau_info=25.0, tau_val_nis=2.5, sigma_tol=0.5, sigma_bridge=3.0),
        )
        mgr.step_healthy(_make_delta(1.0, 1, 1.0))
        mgr.step_healthy(_make_delta(2.5, 2, 2.0))  # promotes kf 1

        mgr.trigger_quarantine(
            estimated_onset_ns=int(2.2 * 1e9),
            current_ns=int(4.0 * 1e9),
            weak_direction_6d=np.array([0, 0, 0, 1, 0, 0], dtype=np.float64),
            info_before_6x6=np.diag([50, 50, 50, 1.0, 50, 50]),
            propagated_cov_norm=1.5,  # < sigma_bridge (3.0)
        )
        snapshot = {k: v.copy() for k, v in mgr.trusted_poses.items()}

        # No candidate available yet -> Mode 3 Soft Bridge Wait
        rep_wait = mgr.validate_and_resolve(candidate=None, updated_propagated_cov_norm=2.1)
        self.assertEqual(rep_wait.mode, RecoveryMode.MODE3_SOFT_BRIDGE_WAIT)
        self.assertEqual(mgr.state, RecoveryState.WAITING_FOR_EVIDENCE)
        self.assertEqual(set(mgr.trusted_poses.keys()), set(snapshot.keys()))

        # Uncertainty grows past sigma_bridge=3.0 without new evidence -> Mode 4 Hard Sleep Split
        rep_split = mgr.validate_and_resolve(candidate=None, updated_propagated_cov_norm=4.5)
        self.assertEqual(rep_split.mode, RecoveryMode.MODE4_HARD_SLEEP_SPLIT)
        self.assertEqual(mgr.state, RecoveryState.ABORTED)
        self.assertEqual(len(mgr.sleeping_submaps), 1)

    def test_recovery_ratio_G_captures_campus2_degradation(self) -> None:
        # MM-LINS Campus-2: w/o PGO = 0.603m, with CE-PGO = 1.295m, clean reference ~ 0.09m
        G_bad_pgo = compute_recovery_ratio_G(
            error_degraded=0.603,
            error_repaired=1.295,
            error_clean=0.090,
        )
        self.assertLess(G_bad_pgo, -1.0)

    def test_recovery_ratio_G_is_undefined_rather_than_zero(self) -> None:
        """
        A zero or inverted denominator means there is no recovery to normalise. Returning 0.0
        there (the previous behaviour) is indistinguishable from a measured "no improvement";
        ORB-SLAM3 under a LiDAR-only injection is exactly that case.
        """
        from slam_recovery.experiments.evaluation import round_or_none

        # E_degraded == E_clean -> denominator zero
        self.assertIsNone(compute_recovery_ratio_G(0.9513, 0.5599, 0.9513))
        # E_clean worse than E_degraded -> negative denominator, sign-flipped ratio
        self.assertIsNone(compute_recovery_ratio_G(0.7614, 0.5599, 0.9513))
        # A genuine negative ratio must still be reported
        self.assertAlmostEqual(compute_recovery_ratio_G(1.7124, 2.1120, 0.5076), -0.3317, places=4)
        # Manifest emission must survive the undefined case instead of raising
        self.assertIsNone(round_or_none(None))
        self.assertEqual(round_or_none(0.123456), 0.1235)


if __name__ == "__main__":
    unittest.main()
