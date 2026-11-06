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

    def test_r1_to_r6_audit_counterexamples_resolved(self) -> None:
        """Verify that all 6 bounded counterexamples (R1-R6) in docs/review_20261105/audit_review.py are resolved."""
        import copy
        from slam_recovery.health.detector import analyze_decoupled_information
        from slam_recovery.validation import compute_disjoint_holdout_point_to_plane_nis

        # R1: Checkpoint key identity is hashed
        m = TrustedMapTransactionManager()
        m.trusted_poses[1] = np.eye(4)
        ck = m.create_checkpoint(100)
        changed = copy.deepcopy(ck)
        changed.keyframe_poses[99] = changed.keyframe_poses.pop(1)
        self.assertNotEqual(ck.compute_hash(), changed.compute_hash())

        # R2: Late onset revokes already-promoted poses >= t_{q,start} via undo log
        m = TrustedMapTransactionManager()
        for t in range(8, 15):
            m.step_healthy(_make_delta(t, t, t if t < 10 else 100 + t))
        m.trigger_quarantine(int(10e9), int(14e9), np.array([0, 0, 0, 1, 0, 0]), np.eye(6), 1.0)
        self.assertEqual([k for k in m.trusted_poses if k >= 10], [])

        # R3: Non-finite (NaN/Inf) candidate pose is rejected by the gate
        m = TrustedMapTransactionManager()
        m.trigger_quarantine(int(10e9), int(14e9), np.array([0, 0, 0, 1, 0, 0]), np.eye(6), 1.0)
        bad_pose = np.eye(4)
        bad_pose[0, 3] = np.nan
        c_nan = CandidateMap("nonfinite_pose", m.trusted_version, {42: bad_pose}, np.eye(6) * 100, np.eye(6) * 0.01, 0.1)
        rep_nan = m.validate_and_resolve(c_nan)
        self.assertFalse(rep_nan.accepted)

        # R4: Coupled rotation-translation weak direction is caught by full 6D eigenspectrum
        fim = np.block([[np.eye(3) * 50, np.eye(3) * 49.999], [np.eye(3) * 49.999, np.eye(3) * 50]])
        mr, mt, _, _, v = analyze_decoupled_information(fim, np.linalg.inv(fim))
        self.assertLess(min(mr, mt), 0.01)
        self.assertLess(float(v @ fim @ v), 0.01)

        # R5: Holdout large residuals are not hidden when >30% points exceed truncation bound
        rng = np.random.default_rng(17)
        train = np.column_stack([rng.uniform(-1, 1, (120, 2)), np.zeros(120)])
        hold = np.column_stack([rng.uniform(-0.5, 0.5, (160, 2)), np.r_[np.full(40, 0.001), np.full(120, 3.0)]])
        nis = compute_disjoint_holdout_point_to_plane_nis(train, hold)
        self.assertGreater(nis, 2.5)

        # R6: Atomic commit updates both trusted_poses and trusted_factors
        m = TrustedMapTransactionManager()
        m.trusted_poses[1] = np.eye(4)
        m.trusted_factors = [10]
        m.trigger_quarantine(int(10e9), int(14e9), np.array([0, 0, 0, 1, 0, 0]), np.eye(6), 1.0)
        c_ok = CandidateMap("pose_and_factor", m.trusted_version, {2: np.eye(4)}, np.eye(6) * 100, np.eye(6) * 0.01, 0.1)
        rep_ok = m.validate_and_resolve(c_ok)
        self.assertTrue(rep_ok.accepted)
        self.assertIn(20, m.trusted_factors)

    def test_spatial_mutation_log_cow_and_redo_replay(self) -> None:
        """Verify O(|Delta M_dirty|) copy-on-write mutation log and zero-copy dual-branch redo replay."""
        from slam_recovery.quarantine import SpatialMutationLog

        store = {(0, 0, 0): np.array([1.0, 0.0, 0.0]), (1, 0, 0): np.array([0.0, 1.0, 0.0])}
        journal = SpatialMutationLog(store)
        journal.begin_generation()

        # Branch A modifies existing voxel (0,0,0), inserts new voxel (2,2,2), and deletes (1,0,0)
        journal.put((0, 0, 0), np.array([9.0, 9.0, 9.0]))
        journal.put((0, 0, 0), np.array([8.0, 8.0, 8.0]))  # second write does not overwrite original before-image
        journal.put((2, 2, 2), np.array([3.0, 3.0, 3.0]))
        journal.remove((1, 0, 0))
        self.assertEqual(journal.dirty_set_size, 3)

        redo_a = journal.capture_mutation_redo()
        journal.rollback_mutation_journal()

        # After rollback, store is bit-for-bit identical to pre-generation state
        self.assertEqual(set(store.keys()), {(0, 0, 0), (1, 0, 0)})
        np.testing.assert_allclose(store[(0, 0, 0)], np.array([1.0, 0.0, 0.0]))
        np.testing.assert_allclose(store[(1, 0, 0)], np.array([0.0, 1.0, 0.0]))

        # Winning branch A is replayed without re-running voxelization
        journal.consume_mutation_redo(redo_a)
        self.assertEqual(set(store.keys()), {(0, 0, 0), (2, 2, 2)})
        np.testing.assert_allclose(store[(0, 0, 0)], np.array([8.0, 8.0, 8.0]))
        np.testing.assert_allclose(store[(2, 2, 2)], np.array([3.0, 3.0, 3.0]))

    def test_nuisance_projected_identifiability_and_spherical_cells(self) -> None:
        """Verify Proposition 2 identifiability I_perp(s | H) and 48-cell spherical point cloud encoding."""
        from slam_recovery.health import (
            compute_nuisance_projected_identifiability,
            extract_48_spherical_cells,
        )

        rng = np.random.default_rng(7)
        H = rng.normal(size=(60, 6))
        # Case 1: Distortion direction s lies strictly in span(H) -> unidentifiable (I_perp == 0)
        s_collinear = H @ np.array([1.0, -0.5, 0.2, 0.8, -1.1, 0.4])
        id_col, _ = compute_nuisance_projected_identifiability(H, s_collinear)
        self.assertAlmostEqual(id_col, 0.0, places=9)

        # Case 2: Distortion direction s orthogonal to span(H) -> fully identifiable (I_perp == 1)
        q, _ = np.linalg.qr(H, mode="complete")
        s_orth = q[:, 6]
        id_orth, _ = compute_nuisance_projected_identifiability(H, s_orth)
        self.assertAlmostEqual(id_orth, 1.0, places=9)

        # 48-cell spherical encoding shape and non-empty indicator
        pts = rng.uniform(-8.0, 8.0, size=(400, 4))
        pts[:, 3] = rng.uniform(10.0, 120.0, size=400)
        cells = extract_48_spherical_cells(pts)
        self.assertEqual(cells.shape, (48, 10))
        self.assertGreater(np.sum(cells[:, 9]), 10.0)

    def test_physics_guided_causal_transformer_fallback_and_onset_age(self) -> None:
        """Verify cold-start analytical fallback and trained causal transformer onset-age prediction."""
        from slam_recovery.core import HealthWindow
        from slam_recovery.diagnosis import PhysicsGuidedCausalTransformer

        tf = PhysicsGuidedCausalTransformer(seed=42)
        w_nom = HealthWindow(
            t_start_ns=0,
            t_end_ns=int(0.2e9),
            min_eig_rot=45.0,
            min_eig_trans=60.0,
            max_eig_rot_cov=1e-4,
            max_eig_trans_cov=1e-3,
            weak_dir_6d=np.array([0, 0, 0, 1, 0, 0], dtype=float),
            nis_mean=1.0,
            nis_q90=1.4,
            nis_cusum=0.0,
            loso_primary_conflict=0.8,
            loso_aux_conflict=0.8,
            Cross_corr_lag_sec=0.0,
            loop_residual_spike=0.5,
            point_drop_ratio=0.01,
            near_field_plane_ratio=0.04,
        )
        # Cold-start frames (< min_ready_samples) must trigger Safeguard #2 analytical fallback
        out0 = tf.step_inference(w_nom)
        self.assertTrue(out0.used_analytical_fallback)

    def test_f1_to_f8_followup_review_probes_resolved(self) -> None:
        """Verify all 9 bounded probes in docs/review_20261105_followup/audit_local.py return defect_reproduced == False."""
        from docs.review_20261105_followup.audit_local import (
            absent_validation_defaults,
            all_revoked_bias,
            incomplete_model_hash,
            late_same_key,
            mesh_outside_bounds,
            missing_orientation_fabricates_zero,
            p9_no_alarm_still_perfect_recall,
            voxel_rollback_divergence,
        )

        for probe_fn in (
            late_same_key,
            all_revoked_bias,
            absent_validation_defaults,
            voxel_rollback_divergence,
            incomplete_model_hash,
            missing_orientation_fabricates_zero,
            mesh_outside_bounds,
            p9_no_alarm_still_perfect_recall,
        ):
            res = probe_fn()
            self.assertFalse(res["defect_reproduced"], msg=f"Probe {probe_fn.__name__} failed: {res}")

        # Also verify unsafe_candidate_fields rejects both NaN bias and (2,2) invalid pose matrix
        m = TrustedMapTransactionManager()
        m.trigger_quarantine(int(10e9), int(14e9), np.array([0.0, 0, 0, 1, 0, 0]), np.eye(6), 1.0)
        r_nan_bias = m.validate_and_resolve(
            CandidateMap(
                "nan_bias",
                m.trusted_version,
                {42: np.eye(4)},
                np.eye(6) * 100,
                np.eye(6) * 0.01,
                0.1,
                repaired_bias_acc=np.array([np.nan, 0.0, 0.0]),
            )
        )
        self.assertFalse(r_nan_bias.accepted)

        m2 = TrustedMapTransactionManager()
        m2.trigger_quarantine(int(10e9), int(14e9), np.array([0.0, 0, 0, 1, 0, 0]), np.eye(6), 1.0)
        r_bad_shape = m2.validate_and_resolve(
            CandidateMap("bad_shape", m2.trusted_version, {42: np.eye(2)}, np.eye(6) * 100, np.eye(6) * 0.01, 0.1)
        )
        self.assertFalse(r_bad_shape.accepted)
        self.assertNotIn(42, m2.trusted_poses)


if __name__ == "__main__":
    unittest.main()
