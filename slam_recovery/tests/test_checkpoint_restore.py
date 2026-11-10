"""Tests for checkpoint restore integrity and rollback non-creation of information (Section 4.2)."""

import unittest
import numpy as np

from slam_recovery.core import (
    BackendDelta,
    CandidateMap,
    GateThresholds,
    RecoveryMode,
TangentFrame,
)
from slam_recovery.quarantine import TrustedMapTransactionManager


class TestCheckpointRestoreAndRollbackTheory(unittest.TestCase):
    def test_corrupted_checkpoint_hash_rejected(self) -> None:
        mgr = TrustedMapTransactionManager()
        ckpt = mgr.create_checkpoint(timestamp_ns=1_000_000_000)
        ckpt.map_version = 999  # Tamper without updating hash
        with self.assertRaises(RuntimeError):
            mgr.restore_checkpoint(ckpt)

    def test_rollback_plus_same_data_reoptimization_cannot_pass_mode2_gate(self) -> None:
        """
        Verify Section 4.2 (B3 baseline theorem):
        Re-optimizing the exact same degraded data D = {z_i, H_i, R_i} after rollback
        leaves v^T \Delta \Lambda_D v \approx 0, so the four-mode gate must refuse
        Mode 2 atomic commit even if residuals look small.
        """
        mgr = TrustedMapTransactionManager(
            gate_thresholds=GateThresholds(tau_info=25.0, tau_val_nis=2.5, sigma_tol=0.5, sigma_bridge=4.0)
        )
        # Weak direction along x-translation (index 3) has eigenvalue 1.5 (< tau_info=25.0)
        info_degraded = np.diag([80.0, 80.0, 80.0, 1.5, 80.0, 80.0])
        mgr.trigger_quarantine(
            estimated_onset_ns=int(5.0 * 1e9),
            current_ns=int(8.0 * 1e9),
            weak_direction_6d=np.array([0, 0, 0, 1, 0, 0], dtype=np.float64),
            info_before_6x6=info_degraded,
            propagated_cov_norm=1.1,
            weak_direction_frame=TangentFrame("body", "rot_trans", "fixture"),
            info_before_frame=TangentFrame("body", "rot_trans", "fixture"),
        )

        # B3 candidate: rollback + re-run on same degraded data -> info_after == info_before
        b3_candidate = CandidateMap(
            candidate_id="b3_rollback_same_data",
            parent_map_version=mgr.trusted_version,
            repaired_poses={10: np.eye(4)},
            info_after_6x6=info_degraded.copy(),
            cov_after_6x6=np.eye(6) * 0.1,
            holdout_nis=0.9,
            info_after_frame=TangentFrame("body", "rot_trans", "fixture"),
            cov_after_frame=TangentFrame("body", "rot_trans", "fixture"),
        )
        report = mgr.validate_and_resolve(b3_candidate)
        self.assertFalse(report.accepted)
        self.assertAlmostEqual(report.weak_dir_info_gain, 0.0, places=9)
        self.assertEqual(report.mode, RecoveryMode.MODE3_SOFT_BRIDGE_WAIT)


if __name__ == "__main__":
    unittest.main()
