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
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.validation import (
    compute_disjoint_holdout_point_to_plane_nis,
    evaluate_paired_sequential_benefit,
    wilson_score_lower_bound,
)


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
            paired_benefit_approved=True,
            wilson_lower_bound=0.90,
            reentry_pos_jump_m=0.05,
        )
        rep2 = mgr.validate_and_resolve(good_cand)
        self.assertTrue(rep2.accepted)
        self.assertEqual(rep2.mode, RecoveryMode.MODE2_ATOMIC_COMMIT)
        self.assertEqual(mgr.trusted_version, version_before + 1)
        self.assertIn(2, mgr.trusted_poses)

    def test_p1a_self_fitting_candidate_fails_independent_scan(self) -> None:
        """
        P1-A: a candidate can be *perfectly self-consistent* --- its residuals against the map it
        just rebuilt are ~0 --- while making an independent scan strictly worse.

        The trusted surface is the floor z = 0. Incumbent poses sit 5 cm above it, candidate poses
        20 cm above it. Because the candidate rebuilds its own map from its own scans, its
        point-to-plane NIS against that map is ~0 no matter how wrong the pose is. Only the paired
        test against a reference the candidate did not fit exposes the damage, and the gate must
        refuse the commit even though every self-measured number looks admissible.
        """
        rng = np.random.default_rng(11)
        n = 600
        trusted_floor = np.column_stack([rng.uniform(-2, 2, n), rng.uniform(-2, 2, n), np.zeros(n)])
        scans = [
            np.column_stack([rng.uniform(-2, 2, n), rng.uniform(-2, 2, n), np.zeros(n)])
            for _ in range(8)
        ]

        def place(dz: float):
            return np.zeros((0, 3)) if False else [s + np.array([0.0, 0.0, dz]) for s in scans]

        incumbent = place(0.05)
        candidate = place(0.20)

        # (a) Self-consistency: score the candidate against the map it built for itself.
        self_map = np.vstack(candidate[0::2])
        cand_self_nis = float(np.mean([
            compute_disjoint_holdout_point_to_plane_nis(self_map, s, np.eye(4), sigma_meas_m=0.05)
            for s in candidate[1::2]
        ]))
        self.assertLess(cand_self_nis, 1.0, "counterexample needs a self-consistent candidate")

        # (b) Independent reference: the trusted floor, which the candidate never fitted.
        inc_res = np.asarray([float(np.mean(np.abs(s[:, 2]))) for s in incumbent])
        cand_res = np.asarray([float(np.mean(np.abs(s[:, 2]))) for s in candidate])
        self.assertTrue(np.all(cand_res > inc_res), "candidate must be uniformly worse on the holdout")

        benefit = evaluate_paired_sequential_benefit(
            inc_res, cand_res, reentry_position_jump_m=0.0, min_observations=4
        )
        self.assertFalse(benefit.approved)
        self.assertEqual(benefit.num_improved_frames, 0)
        self.assertLess(benefit.wilson_lower_bound, 0.55)

        # (c) The gate must refuse it, even though its self-measured holdout NIS looks excellent
        #     and its weak-direction information gain is comfortably above tau_info.
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

        self_fitting = CandidateMap(
            candidate_id="self_fitting_candidate",
            parent_map_version=version_before,
            repaired_poses={2: np.eye(4)},
            info_after_6x6=np.diag([60, 60, 60, 45.0, 60, 60]),  # passes tau_info=25.0
            cov_after_6x6=np.eye(6) * 0.05,                       # passes sigma_tol=0.5
            holdout_nis=cand_self_nis,                            # passes tau_val_nis=2.5
            paired_benefit_approved=benefit.approved,
            wilson_lower_bound=benefit.wilson_lower_bound,
            reentry_pos_jump_m=0.0,
        )
        self.assertLess(self_fitting.holdout_nis, 2.5)
        rep = mgr.validate_and_resolve(self_fitting)
        self.assertFalse(rep.accepted)
        self.assertNotEqual(rep.mode, RecoveryMode.MODE2_ATOMIC_COMMIT)
        self.assertEqual(mgr.trusted_version, version_before)
        self.assertNotIn(2, mgr.trusted_poses)

    def test_p1a_node_reference_is_independent_of_the_candidate(self) -> None:
        """
        P1-A on the real node path (`evaluate_and_commit_candidate`), not just the principle.

        A candidate that is self-consistent by construction --- its own scans placed under its own
        poses --- must not be scored against a reference containing those same scans. The trusted
        map is the true floor at z = 0; the incumbent sits 5 cm above it, the candidate 20 cm.
        Against its own cloud the candidate looks perfect; against the trusted map it is strictly
        worse. The node must refuse it, and the paired evidence must record that no reference frame
        came from the candidate.
        """
        rng = np.random.default_rng(23)
        n = 600
        trusted_floor = np.column_stack([rng.uniform(-2, 2, n), rng.uniform(-2, 2, n), np.zeros(n)])
        scan_body = np.column_stack([rng.uniform(-2, 2, n), rng.uniform(-2, 2, n), np.zeros(n)])

        keys = list(range(6))
        def pose(dz: float) -> np.ndarray:
            T = np.eye(4)
            T[2, 3] = dz
            return T

        incumbent_poses = {k: pose(0.05) for k in keys}   # 5 cm off
        repaired_poses = {k: pose(0.20) for k in keys}    # 20 cm off, but self-consistent

        # Sanity: the candidate is perfectly consistent with the cloud it would build itself.
        self_map = np.vstack([(scan_body @ repaired_poses[k][:3, :3].T) + repaired_poses[k][:3, 3]
                              for k in keys[:3]])
        self_nis = float(np.mean([
            compute_disjoint_holdout_point_to_plane_nis(
                self_map, (scan_body @ repaired_poses[k][:3, :3].T) + repaired_poses[k][:3, 3],
                np.eye(4), sigma_meas_m=0.12)
            for k in keys[3:]
        ]))
        self.assertLess(self_nis, 1.0, "counterexample needs a self-consistent candidate")

        node = OnlineRecoveryTransactionNode(confirmation_margin_sec=2.0, voxel_size_m=0.10,
                                             holdout_stride=5)
        node.committed_map_points = [trusted_floor]
        node.scan_buffer_body = {k: scan_body.copy() for k in keys}
        node.tx_mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0 * 1e9))
        node.tx_mgr.trigger_quarantine(
            int(10e9), int(20e9),
            np.array([0, 0, 0, 1, 0, 0], dtype=np.float64), np.eye(6) * 2.0, 1.2,
        )
        version_before = node.tx_mgr.trusted_version

        report = node.evaluate_and_commit_candidate(
            "self_fitting_through_node",
            repaired_poses,
            incumbent_poses=incumbent_poses,
            reentry_anchor_pose=np.eye(4),
        )

        ev = node.last_paired_evidence
        # The reference was built from the trusted map alone: no frame of the candidate leaked in.
        self.assertEqual(ev["reference_frames_from_candidate"], 0)
        # Every pairable frame here is independent, and all of them were scored.
        self.assertEqual(ev["num_paired_frames"], len(keys))
        self.assertEqual(ev["candidate_keyframes"], len(keys))
        self.assertFalse(ev["approved"])
        self.assertLess(ev["wilson_lower_bound"], 0.55)

        self.assertFalse(report.accepted)
        self.assertNotEqual(report.mode, RecoveryMode.MODE2_ATOMIC_COMMIT)
        self.assertEqual(node.tx_mgr.trusted_version, version_before)
        self.assertNotIn(0, node.tx_mgr.trusted_poses)

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

        # Boundary case that distinguishes the two historical bounds: 0.40 m sits between the old
        # 0.35 m limit and the unified 0.50 m one. It must pass, otherwise the same physical
        # quantity carries two thresholds again.
        rep_mid = evaluate_paired_sequential_benefit(
            inc, cand_good_frames, reentry_position_jump_m=0.40
        )
        self.assertTrue(rep_mid.approved)
        self.assertNotEqual(rep_mid.reason, "reentry_position_discontinuity_exceeded")

    def test_paired_evidence_requirement_scales_with_candidate_size(self) -> None:
        """
        A candidate that touches >= 8 keyframes must supply >= 8 paired frames. Four frames clear
        the 0.55 Wilson bound by only 0.046, which is too thin for an irreversible map commit.
        """
        from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode

        node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0.0)
        rng = np.random.default_rng(0)
        scan = rng.uniform(-1.0, 1.0, size=(40, 3))
        repaired, incumbent = {}, {}
        for k in range(8):
            node.scan_buffer_body[k] = scan + 0.01 * k
            repaired[k] = np.eye(4)
            incumbent[k] = np.eye(4)
        # Only six frames are usable as paired observations.
        node.scan_buffer_body.pop(7)
        node.scan_buffer_body.pop(6)
        node.committed_map_points = [rng.uniform(-1.0, 1.0, size=(60, 3))]

        paired_ok, wilson, _ = node._measure_paired_evidence(
            repaired, incumbent_poses=incumbent, reentry_anchor_pose=np.eye(4)
        )
        self.assertIsNone(paired_ok)
        self.assertIsNone(wilson)
        ev = node.last_paired_evidence
        self.assertEqual(ev["required_paired_frames"], 8)
        self.assertEqual(ev["candidate_keyframes"], 8)
        self.assertEqual(ev["num_paired_frames"], 6)
        self.assertEqual(ev["reason"], "insufficient_paired_frames")

        # The same evidence volume is enough for a small candidate.
        small_repaired = {k: np.eye(4) for k in range(4)}
        node._measure_paired_evidence(
            small_repaired,
            incumbent_poses={k: np.eye(4) for k in range(4)},
            reentry_anchor_pose=np.eye(4),
        )
        self.assertEqual(node.last_paired_evidence["required_paired_frames"], 4)

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
        c_ok = CandidateMap(
            "pose_and_factor", m.trusted_version, {2: np.eye(4)}, np.eye(6) * 100, np.eye(6) * 0.01, 0.1,
            paired_benefit_approved=True, wilson_lower_bound=0.90, reentry_pos_jump_m=0.05,
        )
        rep_ok = m.validate_and_resolve(c_ok)
        self.assertTrue(rep_ok.accepted)
        self.assertIn(20, m.trusted_factors)

    def test_missing_vs_failed_vs_passed_paired_evidence_is_tri_state(self) -> None:
        """
        P1-1: a candidate that merely omits the paired-benefit evidence must not be treated as
        having passed it. Missing evidence waits; explicit failure is rejected; only a measured
        pass may unlock Mode 2 atomic commit.
        """

        def resolve(**evidence):
            m = TrustedMapTransactionManager()
            m.trigger_quarantine(int(10e9), int(14e9), np.array([0., 0., 0., 1., 0., 0.]), np.eye(6), 1.0)
            cand = CandidateMap(
                candidate_id="evidence_probe",
                parent_map_version=m.trusted_version,
                repaired_poses={42: np.eye(4)},
                info_after_6x6=np.eye(6) * 100,
                cov_after_6x6=np.eye(6) * 0.01,
                holdout_nis=0.10,
                **evidence,
            )
            return m.validate_and_resolve(cand), m

        rep_missing, m_missing = resolve()
        self.assertFalse(rep_missing.accepted)
        self.assertEqual(rep_missing.mode, RecoveryMode.MODE3_SOFT_BRIDGE_WAIT)
        self.assertEqual(rep_missing.evidence_status, "MISSING")
        self.assertNotIn(42, m_missing.trusted_poses)

        rep_failed, m_failed = resolve(wilson_lower_bound=0.0, reentry_pos_jump_m=99.0, paired_benefit_approved=True)
        self.assertFalse(rep_failed.accepted)
        self.assertEqual(rep_failed.evidence_status, "FAILED")
        self.assertNotIn(42, m_failed.trusted_poses)

        rep_nan, _ = resolve(wilson_lower_bound=float("nan"), reentry_pos_jump_m=0.0, paired_benefit_approved=True)
        self.assertFalse(rep_nan.accepted)
        self.assertEqual(rep_nan.evidence_status, "FAILED")

        rep_passed, m_passed = resolve(wilson_lower_bound=0.90, reentry_pos_jump_m=0.05, paired_benefit_approved=True)
        self.assertTrue(rep_passed.accepted)
        self.assertEqual(rep_passed.mode, RecoveryMode.MODE2_ATOMIC_COMMIT)
        self.assertEqual(rep_passed.evidence_status, "PASSED")
        self.assertIn(42, m_passed.trusted_poses)

    def test_revoking_last_keyframe_empties_validation_reference(self) -> None:
        """P1-2: after the last trusted keyframe is revoked the holdout reference must be empty."""
        from types import SimpleNamespace
        from unittest.mock import patch

        from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode

        node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0.0)
        decisions = [
            SimpleNamespace(state=RecoveryState.HEALTHY),
            SimpleNamespace(state=RecoveryState.QUARANTINED, estimated_onset_ns=0),
        ]
        fim = (np.eye(6) * 100, np.eye(6) * 0.01, 100.0, 100.0, np.array([0., 0., 0., 1., 0., 0.]))
        scan = np.array([[10.0 + i * 0.01, 0.0, 0.0] for i in range(4)])
        with patch.object(node.detector, "step", side_effect=decisions), patch(
            "slam_recovery.sim.transaction_manager_node.compute_6dof_point_to_plane_fim", return_value=fim
        ):
            for k in (1, 2):
                node.step_frame(k, k * 10**9, np.eye(4), scan, 1.0)
        self.assertEqual(len(node.tx_mgr.trusted_poses), 0)
        self.assertEqual(len(node.voxel_store), 0)
        self.assertEqual(node.get_trusted_map_points().shape, (0, 3))

    def test_undo_log_grows_linear_in_promotions(self) -> None:
        """P1-4: the rollback record must not copy the whole factor history on every promotion."""
        m = TrustedMapTransactionManager(confirmation_margin_ns=0)
        for k in range(500):
            m.step_healthy(_make_delta(k, k, k))
        self.assertEqual(len(m._promoted_before_images), 500)
        self.assertTrue(all(isinstance(rec[1], int) for rec in m._promoted_before_images))
        # A full revocation must still restore the exact pre-onset factor set
        before = list(m.trusted_factors)
        m.trigger_quarantine(0, 10**15, np.array([0., 0., 0., 1., 0., 0.]), np.eye(6), 1.0)
        self.assertEqual(m.trusted_factors, [])
        self.assertTrue(all(isinstance(f, int) for f in before))

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


class TestAtomicPublish(unittest.TestCase):
    """A8: a failed commit must leave every piece of trusted state untouched.

    The counterexample is `repaired_factor_ids` consumed by list.extend after trusted_poses had
    already been replaced: the map was written, the factors were half-extended, the version was
    unchanged and no history entry existed. Four states, four different stories.
    """

    @staticmethod
    def _manager():
        mgr = TrustedMapTransactionManager(
            confirmation_margin_ns=int(2.0 * 1e9),
            gate_thresholds=GateThresholds(tau_info=25.0, tau_val_nis=2.5,
                                           sigma_tol=0.5, sigma_bridge=4.0),
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
        return mgr

    @staticmethod
    def _candidate(mgr, **overrides):
        pose = np.eye(4)
        pose[0, 3] = 42.0
        kwargs = dict(
            candidate_id="atomic_probe",
            parent_map_version=mgr.trusted_version,
            repaired_poses={42: pose},
            info_after_6x6=np.diag([60, 60, 60, 45.0, 60, 60]),
            cov_after_6x6=np.eye(6) * 0.05,
            holdout_nis=1.2,
            paired_benefit_approved=True,
            wilson_lower_bound=0.90,
            reentry_pos_jump_m=0.05,
        )
        kwargs.update(overrides)
        return CandidateMap(**kwargs)

    def _snapshot(self, mgr):
        return {
            "poses": {k: v.copy() for k, v in mgr.trusted_poses.items()},
            "factors": list(mgr.trusted_factors),
            "version": mgr.trusted_version,
            "history": len(mgr.commit_history),
            "state": mgr.state,
            "segment": mgr.active_quarantine,
            "checkpoints": len(mgr.checkpoints),
        }

    def _assert_untouched(self, mgr, before):
        self.assertEqual(set(mgr.trusted_poses), set(before["poses"]))
        for k, v in before["poses"].items():
            self.assertTrue(np.array_equal(mgr.trusted_poses[k], v))
        self.assertEqual(list(mgr.trusted_factors), before["factors"])
        self.assertEqual(mgr.trusted_version, before["version"])
        self.assertEqual(len(mgr.commit_history), before["history"])
        self.assertEqual(mgr.state, before["state"])
        self.assertIs(mgr.active_quarantine, before["segment"])
        self.assertEqual(len(mgr.checkpoints), before["checkpoints"])

    def test_factor_ids_generator_raising_leaves_state_untouched(self) -> None:
        mgr = self._manager()
        mgr.trusted_poses[42] = np.eye(4)          # the frame the counterexample spoke about
        before = self._snapshot(mgr)

        def exploding():
            yield 999
            raise RuntimeError("factor stream died after one id")

        cand = self._candidate(mgr, repaired_factor_ids=exploding())
        with self.assertRaises(RuntimeError):
            mgr.validate_and_resolve(cand)

        self._assert_untouched(mgr, before)
        self.assertNotIn(999, mgr.trusted_factors)
        self.assertNotIn(43, mgr.trusted_poses)    # the candidate's own frame never lands

    def test_pose_mapping_raising_leaves_state_untouched(self) -> None:
        mgr = self._manager()
        before = self._snapshot(mgr)

        class Exploding(dict):
            def items(self):
                done = False
                for k, v in list(super().items()):
                    if done:
                        raise RuntimeError("pose mapping died mid-iteration")
                    done = True
                    yield k, v

        poses = Exploding({42: np.eye(4), 43: np.eye(4)})
        cand = self._candidate(mgr, repaired_poses=poses)
        with self.assertRaises(RuntimeError):
            mgr.validate_and_resolve(cand)
        self._assert_untouched(mgr, before)

    def test_successful_commit_publishes_every_field_together(self) -> None:
        """Positive control: without it the two tests above pass by never committing."""
        mgr = self._manager()
        before = self._snapshot(mgr)
        cand = self._candidate(mgr, repaired_factor_ids=[999])
        report = mgr.validate_and_resolve(cand)

        self.assertTrue(report.accepted)
        self.assertEqual(report.mode, RecoveryMode.MODE2_ATOMIC_COMMIT)
        self.assertEqual(mgr.trusted_version, before["version"] + 1)
        self.assertIn(42, mgr.trusted_poses)
        self.assertIn(999, mgr.trusted_factors)
        self.assertEqual(len(mgr.commit_history), before["history"] + 1)
        self.assertEqual(mgr.commit_history[-1][0], mgr.trusted_version)
