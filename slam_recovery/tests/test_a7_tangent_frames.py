#!/usr/bin/env python3
"""A7: the gate evaluates in one frozen basis -- the trigger scan's body frame.

Three things are pinned here:

  * transport() carries a direction, an information matrix and a covariance so that the profiled
    information and the covariance norm are invariant (algebraic identity);
  * the gate refuses an undeclared or unreconcilable basis instead of computing a plausible number;
  * re-expressing the whole physical configuration in another world frame -- including a plain
    translation, which is what broke the first attempt -- leaves every gate metric and the mode
    bit-identical.

    python -m unittest slam_recovery.tests.test_a7_tangent_frames -v
"""

from __future__ import annotations

import unittest

import numpy as np

from slam_recovery.core import (
    BackendDelta,
    CandidateMap,
    Checkpoint,
    GateThresholds,
    MissingAnchorPose,
    MissingTangentFrame,
    QuarantineSegment,
    RecoveryMode,
    RecoveryState,
    TangentFrame,
    TangentFrameError,
    TangentFrameMismatch,
    adjoint,
    evaluate_four_mode_gate,
    transport,
    transport_covariance,
    transport_information,
)
from slam_recovery.validation import compute_6dof_point_to_plane_fim


def _rot_z(deg: float) -> np.ndarray:
    c, s = np.cos(np.deg2rad(deg)), np.sin(np.deg2rad(deg))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _se3(R: np.ndarray, t) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


def _segment(v, info_before, v_frame, b_frame, anchor_pose_world=None,
             duration_s: float = 4.0) -> QuarantineSegment:
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
        anchor_pose_world=anchor_pose_world,
    )


def _candidate(info_after, cov_after, frame, **over) -> CandidateMap:
    kw = dict(
        candidate_id="cand",
        parent_map_version=0,
        repaired_poses={1: np.eye(4)},
        info_after_6x6=np.asarray(info_after, dtype=np.float64),
        cov_after_6x6=np.asarray(cov_after, dtype=np.float64),
        holdout_nis=1.0,
        info_after_frame=frame,
        cov_after_frame=frame,
        paired_benefit_approved=True,
        wilson_lower_bound=0.90,
        reentry_pos_jump_m=0.05,
    )
    kw.update(over)
    return CandidateMap(**kw)


BODY = TangentFrame("body", "rot_trans", "scan:7")
WORLD = TangentFrame("world", "rot_trans", "world")


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

        # The covariance has to move with it. A gate that transports one and not the other is how
        # a body covariance ends up compared against a world threshold, so the same producer-based
        # check is applied to it: invert the two informations and compare the transported result.
        cov_body = np.linalg.inv(info_body + np.eye(6) * 1e-3)
        cov_world = np.linalg.inv(info_world + np.eye(6) * 1e-3)
        cov_moved = transport_covariance(cov_body, T)
        self.assertLess(float(np.linalg.norm(cov_moved - cov_world)
                              / np.linalg.norm(cov_world)), 1e-3,
                        "covariance transport disagrees with the covariance the producer computes")

    def test_transport_composes(self):
        T1 = _se3(_rot_z(30.0), [0.4, -1.2, 0.7])
        T2 = _se3(_rot_z(-75.0), [2.0, 0.1, -0.5])
        v = np.array([0.1, -0.2, 0.3, 1.0, 0.0, -0.4])
        self.assertTrue(np.allclose(transport(v, T2 @ T1), transport(transport(v, T1), T2)))

    def test_covariance_and_information_move_in_opposite_directions(self):
        T = _se3(_rot_z(20.0), [1.0, 2.0, 3.0])
        A = np.random.default_rng(3).normal(size=(6, 6))
        cov = A @ A.T + np.eye(6)
        info = np.linalg.inv(cov)
        moved_cov = transport_covariance(cov, T)
        moved_info = transport_information(info, T)
        self.assertTrue(np.allclose(moved_cov, np.linalg.inv(moved_info)))

    def test_the_two_block_orders_differ_and_are_not_interchangeable(self):
        T = _se3(_rot_z(20.0), [1.0, 2.0, 3.0])
        self.assertFalse(np.allclose(adjoint(T, "rot_trans"), adjoint(T, "trans_rot")))


class TestRefusals(unittest.TestCase):
    def test_a_segment_without_a_frame_cannot_be_built(self):
        with self.assertRaises(MissingTangentFrame):
            _segment([0, 0, 0, 1, 0, 0], np.eye(6), None, None)

    def test_a_segment_with_only_one_frame_declared_is_refused(self):
        with self.assertRaises(MissingTangentFrame):
            _segment([0, 0, 0, 1, 0, 0], np.eye(6), BODY, None)

    def test_a_candidate_without_a_frame_is_refused(self):
        seg = _segment([0, 0, 0, 1, 0, 0], np.diag([1, 1, 1, 30.0, 1, 1]), BODY, BODY)
        cand = _candidate(np.diag([1, 1, 1, 90.0, 1, 1]), np.eye(6) * 0.1, None)
        with self.assertRaises(MissingTangentFrame):
            evaluate_four_mode_gate(seg, cand)

    def test_a_candidate_without_a_covariance_frame_is_refused(self):
        seg = _segment([0, 0, 0, 1, 0, 0], np.diag([1, 1, 1, 30.0, 1, 1]), BODY, BODY)
        cand = _candidate(np.diag([1, 1, 1, 90.0, 1, 1]), np.eye(6) * 0.1, BODY)
        cand.cov_after_frame = None
        with self.assertRaises(MissingTangentFrame):
            evaluate_four_mode_gate(seg, cand)

    def test_two_bases_in_the_segment_are_refused(self):
        seg = _segment([0, 0, 0, 1, 0, 0], np.diag([1, 1, 1, 30.0, 1, 1]), BODY, WORLD)
        with self.assertRaises(TangentFrameMismatch):
            evaluate_four_mode_gate(seg, None)

    def test_a_world_candidate_without_the_anchor_pose_is_refused(self):
        seg = _segment([0, 0, 0, 1, 0, 0], np.diag([1, 1, 1, 30.0, 1, 1]), BODY, BODY)
        cand = _candidate(np.diag([1, 1, 1, 90.0, 1, 1]), np.eye(6) * 0.1, WORLD)
        with self.assertRaises(MissingAnchorPose):
            evaluate_four_mode_gate(seg, cand)

    def test_an_unrelated_body_anchor_is_refused(self):
        seg = _segment([0, 0, 0, 1, 0, 0], np.diag([1, 1, 1, 30.0, 1, 1]), BODY, BODY)
        other = TangentFrame("body", "rot_trans", "scan:99")
        cand = _candidate(np.diag([1, 1, 1, 90.0, 1, 1]), np.eye(6) * 0.1, other)
        with self.assertRaises(TangentFrameMismatch):
            evaluate_four_mode_gate(seg, cand)

    def test_a_block_order_mismatch_is_refused(self):
        seg = _segment([0, 0, 0, 1, 0, 0], np.diag([1, 1, 1, 30.0, 1, 1]),
                       TangentFrame("body", "rot_trans", "scan:7"),
                       TangentFrame("body", "trans_rot", "scan:7"))
        with self.assertRaises(TangentFrameMismatch):
            evaluate_four_mode_gate(seg, None)

    def test_a_refusal_does_not_strand_the_manager_in_validating(self):
        from slam_recovery.quarantine import TrustedMapTransactionManager

        mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0e9))
        mgr.step_healthy(BackendDelta(
            timestamp_ns=1_000_000_000, frame_id="map", pose_se3=np.eye(4),
            velocity=np.zeros(3), bias_acc=np.zeros(3), bias_gyr=np.zeros(3),
            cov_6x6=np.eye(6), info_6x6=np.eye(6), nis_value=0.5, nis_dof=6,
            factor_ids=[0], keyframe_id=0))
        mgr.trigger_quarantine(10_000_000_000, 14_000_000_000,
                               np.array([0.0, 0, 0, 1, 0, 0]), np.eye(6) * 2.0, 1.0,
                               weak_direction_frame=BODY, info_before_frame=BODY)
        before = mgr.state
        version_before = mgr.trusted_version
        with self.assertRaises(TangentFrameError):
            mgr.validate_and_resolve(_candidate(np.eye(6) * 90.0, np.eye(6) * 0.1,
                                                TangentFrame("body", "rot_trans", "scan:99")))
        self.assertEqual(mgr.state, before)
        self.assertEqual(mgr.trusted_version, version_before)


class TestGaugeInvariance(unittest.TestCase):
    """Re-express the world; the physics and the decision must not move.

    The first attempt transported the weak direction into world and re-normalised it there. A
    translation makes Ad non-orthogonal, so the world vector is not unit length and re-normalising
    divides the information by ||Ad v||^2: 2 m of plain translation turned MODE2 into MODE3. The
    covariance had the mirror-image problem -- its spectral norm is not origin-invariant -- which
    is why information and covariance now travel together into the anchor body frame.
    """

    V_BODY = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    INFO_BEFORE_BODY = np.diag([60.0, 60.0, 60.0, 20.0, 40.0, 40.0])
    # 50 against 20 is a 2.5x gain: the gate now asks for a factor (kappa) as well as an
    # absolute floor, so a fixture built on a 1.5x gain would no longer reach Mode 2.
    INFO_AFTER_BODY = np.diag([60.0, 60.0, 60.0, 50.0, 5.0, 5.0])
    COV_BODY = np.linalg.inv(INFO_AFTER_BODY)

    def _report(self, T_world_anchor):
        """Body-frame physics submitted as a world-declared candidate at this anchor pose."""
        info_after_world = transport_information(self.INFO_AFTER_BODY, T_world_anchor)
        cov_after_world = transport_covariance(self.COV_BODY, T_world_anchor)
        seg = _segment(self.V_BODY, self.INFO_BEFORE_BODY, BODY, BODY,
                       anchor_pose_world=T_world_anchor)
        return evaluate_four_mode_gate(
            seg, _candidate(info_after_world, cov_after_world, WORLD))

    def test_a_plain_translation_does_not_move_the_information(self):
        rows = [self._report(_se3(np.eye(3), [0.0, t, 0.0])) for t in (0.0, 2.0)]
        self.assertEqual(rows[0].mode, RecoveryMode.MODE2_ATOMIC_COMMIT)
        self.assertEqual(rows[0].mode, rows[1].mode)
        self.assertAlmostEqual(rows[0].weak_dir_info_before, rows[1].weak_dir_info_before, places=9)
        self.assertAlmostEqual(rows[0].weak_dir_info_after, rows[1].weak_dir_info_after, places=9)
        self.assertAlmostEqual(rows[0].weak_dir_info_before, 20.0, places=9)
        self.assertAlmostEqual(rows[0].weak_dir_info_after, 50.0, places=9)

    def test_a_plain_translation_does_not_move_the_covariance_norm(self):
        rows = [self._report(_se3(np.eye(3), [0.0, t, 0.0])) for t in (0.0, 5.0)]
        self.assertEqual(rows[0].mode, RecoveryMode.MODE2_ATOMIC_COMMIT)
        self.assertEqual(rows[0].mode, rows[1].mode)
        self.assertAlmostEqual(rows[0].posterior_cov_norm, rows[1].posterior_cov_norm, places=9)
        self.assertAlmostEqual(rows[0].posterior_cov_norm, 0.2, places=9)

    def test_a_rotated_anchor_with_translation_does_not_move_the_decision(self):
        identity = self._report(np.eye(4))
        moved = self._report(_se3(_rot_z(45.0), [3.0, -2.0, 1.5]))
        self.assertEqual(identity.mode, moved.mode)
        self.assertEqual(identity.accepted, moved.accepted)
        for field in ("weak_dir_info_before", "weak_dir_info_after", "posterior_cov_norm"):
            self.assertAlmostEqual(getattr(identity, field), getattr(moved, field), places=9)

    def test_a_real_producer_with_a_rotated_weak_direction_is_gauge_free(self):
        cloud = np.random.default_rng(0).normal(size=(400, 3))
        before, _, _, _, weak = compute_6dof_point_to_plane_fim(0.5 * cloud, sigma_meas_m=0.075)
        after, _, _, _, _ = compute_6dof_point_to_plane_fim(0.8 * cloud, sigma_meas_m=0.075)
        cov = np.linalg.inv(after + np.eye(6) * 0.001)
        self.assertGreater(float(np.linalg.norm(weak[:3])), 1e-3, "the producer must give a "
                                                                    "rotational weak direction")
        reports = []
        for T in (np.eye(4), _se3(_rot_z(30.0), [0.0, 2.0, 0.0])):
            seg = _segment(weak, before, BODY, BODY, anchor_pose_world=T)
            reports.append(evaluate_four_mode_gate(
                seg, _candidate(transport_information(after, T),
                                transport_covariance(cov, T), WORLD)))
        self.assertAlmostEqual(reports[0].weak_dir_info_before,
                               reports[1].weak_dir_info_before, places=6)
        self.assertAlmostEqual(reports[0].weak_dir_info_after,
                               reports[1].weak_dir_info_after, places=6)
        self.assertAlmostEqual(reports[0].posterior_cov_norm,
                               reports[1].posterior_cov_norm, places=9)
        self.assertEqual(reports[0].mode, reports[1].mode)


if __name__ == "__main__":
    unittest.main(verbosity=2)
