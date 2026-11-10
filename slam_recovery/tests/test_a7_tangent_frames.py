#!/usr/bin/env python3
"""A7: the gate must never multiply a 6D direction by a 6x6 information matrix from another basis.

The scalar D = v^T Lambda v is the information along a physical direction only when v and Lambda
are expressed in the same frame with the same block order. These tests fix three properties:

  * transport() carries both quantities so that D is unchanged (algebraic identity);
  * the gate refuses an undeclared or inconsistent pair instead of computing a plausible number;
  * re-expressing the whole physical configuration in a different world frame leaves the decision
    bit-identical, provided everything is transported and declared.

    python -m unittest slam_recovery.tests.test_a7_tangent_frames -v
"""

from __future__ import annotations

import unittest

import numpy as np

from slam_recovery.core import (
    CandidateMap,
    Checkpoint,
    GateThresholds,
    MissingTangentFrame,
    QuarantineSegment,
    RecoveryMode,
    TangentFrame,
    TangentFrameMismatch,
    adjoint,
    evaluate_four_mode_gate,
    transport,
    transport_information,
)


def _rot_z(deg: float) -> np.ndarray:
    c, s = np.cos(np.deg2rad(deg)), np.sin(np.deg2rad(deg))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _se3(R: np.ndarray, t) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


def _segment(v, info_before, v_frame, b_frame, duration_s: float = 4.0) -> QuarantineSegment:
    ckpt = Checkpoint(checkpoint_id="ckpt", timestamp_ns=0, map_version=0,
                      keyframe_poses={}, factor_ids=[], imu_bias_acc=np.zeros(3),
                      imu_bias_gyr=np.zeros(3))
    return QuarantineSegment(
        segment_id="seg",
        checkpoint=ckpt,
        t_start_ns=10_000_000_000,
        t_end_ns=int((10.0 + duration_s) * 1e9),
        weak_direction_6d=np.asarray(v, dtype=np.float64),
        info_before_6x6=np.asarray(info_before, dtype=np.float64),
        propagated_cov_norm=0.6,
        weak_direction_frame=v_frame,
        info_before_frame=b_frame,
    )


def _candidate(info_after, frame, **over) -> CandidateMap:
    kw = dict(
        candidate_id="cand",
        parent_map_version=0,
        repaired_poses={1: np.eye(4)},
        info_after_6x6=np.asarray(info_after, dtype=np.float64),
        cov_after_6x6=np.eye(6) * 0.10,
        holdout_nis=1.0,
        info_after_frame=frame,
        paired_benefit_approved=True,
        wilson_lower_bound=0.90,
        reentry_pos_jump_m=0.05,
    )
    kw.update(over)
    return CandidateMap(**kw)


class TestTransportAlgebra(unittest.TestCase):
    def test_the_profiled_scalar_is_invariant(self):
        rng = np.random.default_rng(7)
        for _ in range(20):
            R, _q = np.linalg.qr(rng.normal(size=(3, 3)))
            if np.linalg.det(R) < 0:
                R = -R
            T = _se3(R, rng.normal(scale=2.0, size=3))
            v = rng.normal(size=6)
            A = rng.normal(size=(6, 6))
            info = A @ A.T + np.eye(6) * 0.5
            v2 = transport(v, T)
            info2 = transport_information(info, T)
            self.assertAlmostEqual(float(v @ info @ v), float(v2 @ info2 @ v2), places=9)

    def test_transport_matches_the_fim_the_producer_computes(self):
        """Invariance alone is an algebraic identity; this pins the adjoint to the real FIM.

        A wrong adjoint still satisfies v'^T L' v' == v^T L (it holds for any invertible map), so
        the invariance test cannot catch a convention error. Recomputing the same point-to-plane
        information from the transformed points can: if the adjoint moves into the wrong basis,
        the two numbers differ. Measured agreement on this fixture is 6e-9 relative.
        """
        from slam_recovery.validation.fim_and_holdout import compute_6dof_point_to_plane_fim

        rng = np.random.default_rng(0)
        pts = rng.normal(size=(400, 3))
        T = _se3(_rot_z(40.0), [2.0, -1.0, 0.5])
        pts_world = pts @ T[:3, :3].T + T[:3, 3]
        info_body = compute_6dof_point_to_plane_fim(pts, sigma_meas_m=0.05)[0]
        info_world = compute_6dof_point_to_plane_fim(pts_world, sigma_meas_m=0.05)[0]
        moved = transport_information(info_body, T)
        self.assertLess(float(np.linalg.norm(moved - info_world)
                              / np.linalg.norm(info_world)), 1e-6)

    def test_transport_composes(self):
        T1 = _se3(_rot_z(30.0), [0.4, -1.2, 0.7])
        T2 = _se3(_rot_z(-75.0), [2.0, 0.1, -0.5])
        v = np.array([0.1, -0.2, 0.3, 1.0, 0.0, -0.4])
        self.assertTrue(np.allclose(transport(v, T2 @ T1), transport(transport(v, T1), T2)))

    def test_the_two_block_orders_differ_and_are_not_interchangeable(self):
        T = _se3(_rot_z(20.0), [1.0, 2.0, 3.0])
        self.assertFalse(np.allclose(adjoint(T, "rot_trans"), adjoint(T, "trans_rot")))


class TestRefusals(unittest.TestCase):
    def test_a_segment_without_a_frame_cannot_be_built(self):
        with self.assertRaises(MissingTangentFrame):
            _segment([0, 0, 0, 1, 0, 0], np.eye(6), None, None)

    def test_a_segment_with_only_one_frame_declared_is_refused(self):
        with self.assertRaises(MissingTangentFrame):
            _segment([0, 0, 0, 1, 0, 0], np.eye(6), TangentFrame("body", anchor="scan:1"), None)

    def test_a_candidate_without_a_frame_is_refused(self):
        seg = _segment([0, 0, 0, 1, 0, 0], np.diag([1, 1, 1, 30.0, 1, 1]),
                       TangentFrame("body", anchor="scan:1"), TangentFrame("body", anchor="scan:1"))
        cand = _candidate(np.diag([1, 1, 1, 90.0, 1, 1]), None)
        with self.assertRaises(MissingTangentFrame):
            evaluate_four_mode_gate(seg, cand)

    def test_two_bases_are_refused_not_averaged(self):
        seg = _segment([0, 0, 0, 1, 0, 0], np.diag([1, 1, 1, 30.0, 1, 1]),
                       TangentFrame("body", anchor="scan:1"), TangentFrame("world", anchor="world"))
        with self.assertRaises(TangentFrameMismatch):
            evaluate_four_mode_gate(seg, None)

    def test_the_candidate_must_share_the_segment_basis(self):
        seg = _segment([0, 0, 0, 1, 0, 0], np.diag([1, 1, 1, 30.0, 1, 1]),
                       TangentFrame("body", anchor="scan:1"), TangentFrame("body", anchor="scan:1"))
        cand = _candidate(np.diag([1, 1, 1, 90.0, 1, 1]), TangentFrame("world", anchor="world"))
        with self.assertRaises(TangentFrameMismatch):
            evaluate_four_mode_gate(seg, cand)

    def test_a_block_order_mismatch_is_refused(self):
        seg = _segment([0, 0, 0, 1, 0, 0], np.diag([1, 1, 1, 30.0, 1, 1]),
                       TangentFrame("body", "rot_trans", "scan:1"),
                       TangentFrame("body", "trans_rot", "scan:1"))
        with self.assertRaises(TangentFrameMismatch):
            evaluate_four_mode_gate(seg, None)

    def test_a_refusal_does_not_strand_the_manager_in_validating(self):
        from slam_recovery.core import BackendDelta, RecoveryState
        from slam_recovery.quarantine import TrustedMapTransactionManager

        mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0e9))
        mgr.step_healthy(BackendDelta(
            timestamp_ns=1_000_000_000, frame_id="map", pose_se3=np.eye(4),
            velocity=np.zeros(3), bias_acc=np.zeros(3), bias_gyr=np.zeros(3),
            cov_6x6=np.eye(6), info_6x6=np.eye(6), nis_value=0.5, nis_dof=6,
            factor_ids=[0], keyframe_id=0))
        mgr.trigger_quarantine(10_000_000_000, 14_000_000_000,
                               np.array([0.0, 0, 0, 1, 0, 0]), np.eye(6) * 2.0, 1.0,
                               weak_direction_frame=TangentFrame("body", "rot_trans", "scan:1"),
                               info_before_frame=TangentFrame("body", "rot_trans", "scan:1"))
        before = mgr.state
        version_before = mgr.trusted_version
        with self.assertRaises(TangentFrameMismatch):
            mgr.validate_and_resolve(_candidate(np.eye(6) * 90.0,
                                                TangentFrame("world", "rot_trans", "world")))
        self.assertEqual(mgr.state, before)
        self.assertEqual(mgr.trusted_version, version_before)


class TestGlobalReexpression(unittest.TestCase):
    """The same physical configuration, written in two world frames, must decide the same."""

    V_BODY = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    INFO_BEFORE_BODY = np.diag([60.0, 60.0, 60.0, 20.0, 40.0, 40.0])
    # Weak along world x before repair; 30 of information there, 5 along y.
    INFO_AFTER_W1 = np.diag([60.0, 60.0, 60.0, 30.0, 5.0, 5.0])
    T_W1_BODY = np.eye(4)
    # W2 is W1 re-expressed: p_W2 = G p_W1.
    G = _se3(_rot_z(45.0), [3.0, -2.0, 1.5])

    def _report_in(self, G):
        """Express the configuration in the world frame W' with p_W' = G p_W, then judge it."""
        T_W2_BODY = G @ self.T_W1_BODY
        frame2 = TangentFrame("world", "rot_trans", "world:2")
        body = TangentFrame("body", "rot_trans", "scan:7")
        v_w1 = transport(self.V_BODY, self.T_W1_BODY)
        b_w1 = transport_information(self.INFO_BEFORE_BODY, self.T_W1_BODY)
        v_w2 = transport(v_w1, G)
        b_w2 = transport_information(b_w1, G)
        a_w2 = transport_information(self.INFO_AFTER_W1, G)
        # sanity: the body-frame quantities are unchanged by the re-expression of the world
        self.assertTrue(np.allclose(transport(v_w2, np.linalg.inv(T_W2_BODY)), self.V_BODY))
        seg = _segment(v_w2, b_w2, frame2, frame2)
        return evaluate_four_mode_gate(seg, _candidate(a_w2, frame2))

    def test_the_decision_does_not_depend_on_how_the_world_is_named(self):
        r1 = self._report_in(np.eye(4))
        r2 = self._report_in(self.G)
        self.assertEqual(r1.mode, RecoveryMode.MODE2_ATOMIC_COMMIT)
        self.assertEqual(r1.accepted, r2.accepted)
        self.assertEqual(r1.mode, r2.mode)
        self.assertAlmostEqual(r1.weak_dir_info_before, r2.weak_dir_info_before, places=9)
        self.assertAlmostEqual(r1.weak_dir_info_after, r2.weak_dir_info_after, places=9)
        self.assertAlmostEqual(r1.weak_dir_info_after, 30.0, places=9)

    def test_mixing_the_bases_would_move_the_scalar(self):
        """Why the check exists: with v left in the body frame, the world re-expression of the
        candidate's information produces a different number for the same physical setup."""
        v_body = self.V_BODY.copy()
        a_w1 = self.INFO_AFTER_W1
        a_w2 = transport_information(a_w1, self.G)
        self.assertAlmostEqual(float(v_body @ a_w1 @ v_body), 30.0, places=9)
        # The old, silent computation: same v, rotated information.
        self.assertAlmostEqual(float(v_body @ a_w2 @ v_body), 17.5, places=9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
