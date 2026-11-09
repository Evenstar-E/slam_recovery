"""Mode 2 commits exactly the frames that were independently scored (P1/P2 regression).

The 20261109_bbc3dcb review produced an entry-level counterexample: a 20-frame candidate whose
last 12 frames were displaced by 100 m left those frames out of *scoring* (the reference cloud no
longer supported them) while they stayed in *commit*. The gate accepted and the trusted map
absorbed all 20. These tests pin the inverted expectation: the scored set and the committed set
are the same set, and anything that could not be scored stays quarantined.
"""

import unittest

import numpy as np

from slam_recovery.core import CandidateMap, RecoveryMode
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode


def _plane_cloud(n: int = 600, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.column_stack(
        [rng.uniform(-2, 2, n), rng.uniform(-2, 2, n), np.zeros(n)]
    )


def _node_with_quarantine(cloud: np.ndarray) -> OnlineRecoveryTransactionNode:
    node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0)
    node.committed_map_points = [cloud]
    node.tx_mgr.trigger_quarantine(
        int(10e9), int(20e9), np.array([0, 0, 0, 1, 0, 0]), np.eye(6) * 2, 1.2
    )
    return node


class TestCommitEvidenceCoverage(unittest.TestCase):
    def test_unsupported_tail_is_deferred_not_committed(self) -> None:
        """The review's counterexample: 8 good frames, 12 frames at z=100 m."""
        cloud = _plane_cloud()
        node = _node_with_quarantine(cloud)
        poses, incumbent = {}, {}
        for k in range(20):
            node.scan_buffer_body[k] = cloud.copy()
            pose = np.eye(4)
            pose[2, 3] = 0.0 if k < 8 else 100.0
            poses[k] = pose
            old = np.eye(4)
            old[2, 3] = 0.3
            incumbent[k] = old

        report = node.evaluate_and_commit_candidate(
            "unsupported_tail",
            poses,
            aux_or_loop_info_6x6=np.eye(6) * 100,
            incumbent_poses=incumbent,
            reentry_anchor_pose=np.eye(4),
        )

        committed = node.tx_mgr.trusted_poses
        self.assertEqual(len(committed), 8)
        self.assertFalse(any(p[2, 3] == 100.0 for p in committed.values()))
        # The 12 displaced frames are deferred, not rejected: they stay outside the trusted map.
        self.assertEqual(report.committed_pose_keys, list(range(8)))
        self.assertEqual(report.deferred_pose_keys, list(range(8, 20)))
        self.assertTrue(report.partial_commit)
        self.assertEqual(
            node._last_holdout_support["candidate_frames_deferred"], 12
        )

    def test_missing_scan_is_missing_evidence_not_keyerror(self) -> None:
        """A hole in the scan buffer must produce a wait, not a crash."""
        cloud = _plane_cloud()
        node = _node_with_quarantine(cloud)
        # No scan_buffer_body entry for keyframe 0.
        report = node.evaluate_and_commit_candidate("missing_scan", {0: np.eye(4)})

        self.assertIn(
            report.mode,
            (RecoveryMode.MODE3_SOFT_BRIDGE_WAIT, RecoveryMode.MODE4_HARD_SLEEP_SPLIT),
        )
        self.assertEqual(report.deferred_pose_keys, [0])
        self.assertEqual(node._last_holdout_support["frames_missing_scan"], [0])
        self.assertEqual(node.tx_mgr.trusted_poses, {})
        # A candidate whose first frame has no support must not be logged as an empty candidate.
        self.assertEqual(node.last_paired_evidence["reason"], "no_committable_frames")
        self.assertEqual(node._last_holdout_support["deferred_runs"], [[0, 0]])
        self.assertEqual(node._last_holdout_support["first_deferred_reason"], "missing_scan")

    def test_a_hole_does_not_discard_the_frames_after_it(self) -> None:
        """One unsupported frame is a gap in the commit, not a reason to drop the rest."""
        cloud = _plane_cloud()
        node = _node_with_quarantine(cloud)
        poses, incumbent = {}, {}
        for k in range(6):
            node.scan_buffer_body[k] = cloud.copy()
            poses[k] = np.eye(4)
            incumbent[k] = np.eye(4)
        # Frame 0 sits 100 m above the reference surface: not supportable. Frames 1..5 are fine.
        poses[0] = np.eye(4)
        poses[0][2, 3] = 100.0

        report = node.evaluate_and_commit_candidate(
            "bad_head",
            poses,
            aux_or_loop_info_6x6=np.eye(6) * 100,
            incumbent_poses=incumbent,
            reentry_anchor_pose=np.eye(4),
        )

        support = node._last_holdout_support
        self.assertEqual(support["candidate_frames_total"], 6)
        self.assertEqual(support["candidate_frames_committable"], 5)
        # Frame 0 is deferred; frames 1..5 are committed and judged on their own evidence.
        self.assertEqual(support["candidate_frames_committed"], 5)
        self.assertEqual(support["deferred_runs"], [[0, 0]])
        self.assertEqual(support["first_deferred_reason"], "no_reference_support")
        self.assertEqual(node.last_paired_evidence["num_paired_frames"], 5)
        # Identical candidate and incumbent poses carry no improvement, so the gate still waits.
        self.assertNotEqual(report.mode, RecoveryMode.MODE2_ATOMIC_COMMIT)

    def test_frame_in_reference_is_not_scored_against_itself(self) -> None:
        """Provenance must come from the map, not from a comment."""
        cloud = _plane_cloud()
        node = _node_with_quarantine(cloud)
        # Keyframe 0 already contributed to the trusted reference.
        node._kf_map_points[0] = cloud.copy()
        node.committed_map_points = [cloud.copy()]
        poses, incumbent = {}, {}
        for k in range(4):
            node.scan_buffer_body[k] = cloud.copy()
            poses[k] = np.eye(4)
            incumbent[k] = np.eye(4)

        node.evaluate_and_commit_candidate(
            "self_scored",
            poses,
            aux_or_loop_info_6x6=np.eye(6) * 100,
            incumbent_poses=incumbent,
            reentry_anchor_pose=np.eye(4),
        )

        # Frame 0 is part of the reference, so it cannot be verified and cannot be committed.
        self.assertNotIn(0, node.tx_mgr.trusted_poses)
        self.assertEqual(node._last_holdout_support["frames_in_reference"], [0])

    def test_infinite_holdout_is_missing_evidence_not_invalid_state(self) -> None:
        """No scorable holdout frame must read as MISSING, not as a non-finite pose."""
        mgr = TrustedMapTransactionManager(confirmation_margin_ns=0)
        mgr.trigger_quarantine(
            estimated_onset_ns=int(1e9),
            current_ns=int(2e9),
            weak_direction_6d=np.array([0, 0, 0, 1, 0, 0]),
            info_before_6x6=np.eye(6) * 2,
            propagated_cov_norm=1.2,
        )
        cand = CandidateMap(
            candidate_id="no_holdout",
            parent_map_version=mgr.trusted_version,
            repaired_poses={0: np.eye(4)},
            info_after_6x6=np.eye(6) * 100,
            cov_after_6x6=np.eye(6) * 0.01,
            holdout_nis=float("inf"),
            paired_benefit_approved=True,
            wilson_lower_bound=0.9,
            reentry_pos_jump_m=0.0,
        )
        report = mgr.validate_and_resolve(cand)
        self.assertIn(
            report.mode,
            (RecoveryMode.MODE3_SOFT_BRIDGE_WAIT, RecoveryMode.MODE4_HARD_SLEEP_SPLIT),
        )
        self.assertIn("holdout evidence MISSING", report.reason)
        self.assertNotIn("non-finite", report.reason)

    def test_nan_holdout_is_still_rejected_as_invalid(self) -> None:
        mgr = TrustedMapTransactionManager(confirmation_margin_ns=0)
        mgr.trigger_quarantine(
            estimated_onset_ns=int(1e9),
            current_ns=int(2e9),
            weak_direction_6d=np.array([0, 0, 0, 1, 0, 0]),
            info_before_6x6=np.eye(6) * 2,
            propagated_cov_norm=1.2,
        )
        cand = CandidateMap(
            candidate_id="nan_holdout",
            parent_map_version=mgr.trusted_version,
            repaired_poses={0: np.eye(4)},
            info_after_6x6=np.eye(6) * 100,
            cov_after_6x6=np.eye(6) * 0.01,
            holdout_nis=float("nan"),
        )
        report = mgr.validate_and_resolve(cand)
        self.assertIn("non-finite", report.reason)

    def test_support_reference_is_sampled_by_space_not_by_point_count(self) -> None:
        """The coverage test must not flip just because the map got denser.

        The four-arm replay found the same pose and scan scoring 0.82 support against a 4 000-point
        reference and 0.29 against 1 500 points. A point cap is a budget, not a coverage
        definition, so the support reference keeps one point per occupied voxel.
        """
        def grid(step: float) -> np.ndarray:
            xs = np.arange(0.0, 1.0, step)
            gx, gy = np.meshgrid(xs, xs, indexing="ij")
            return np.column_stack([gx.ravel(), gy.ravel(), np.zeros(gx.size)])

        coarse = OnlineRecoveryTransactionNode(confirmation_margin_sec=0)
        coarse.committed_map_points = [grid(0.10)]
        fine = OnlineRecoveryTransactionNode(confirmation_margin_sec=0)
        fine.committed_map_points = [grid(0.025)]

        n_coarse = len(coarse.support_reference())
        n_fine = len(fine.support_reference())
        self.assertLess(abs(n_coarse - n_fine), 0.5 * max(n_coarse, 1))
        self.assertLess(n_fine, 60)

        scan = grid(0.05)
        pose = {0: np.eye(4)}
        for node in (coarse, fine):
            node.scan_buffer_body[0] = scan
            self.assertTrue(node._frame_has_reference_support(0, node.support_reference(), pose))

    def test_sigma_is_a_parameter_not_a_constant(self) -> None:
        """NIS scales as 1/sigma^2, so a host must be able to pass its calibrated value."""
        cloud = _plane_cloud()
        reports = {}
        for sigma in (0.12, 0.24):
            node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0, sigma_meas_m=sigma)
            node.committed_map_points = [cloud]
            node.tx_mgr.trigger_quarantine(
                int(10e9), int(20e9), np.array([0, 0, 0, 1, 0, 0]), np.eye(6) * 2, 1.2
            )
            posed = cloud.copy()
            posed[:, 2] += 0.05  # keep the scan inside the support radius, give it a residual
            poses, incumbent = {}, {}
            for k in range(8):
                node.scan_buffer_body[k] = posed
                poses[k] = np.eye(4)
                incumbent[k] = np.eye(4)
            reports[sigma] = node.evaluate_and_commit_candidate(
                "sigma_probe",
                poses,
                aux_or_loop_info_6x6=np.eye(6) * 100,
                incumbent_poses=incumbent,
                reentry_anchor_pose=np.eye(4),
            )
        ratio = reports[0.12].holdout_nis / reports[0.24].holdout_nis
        self.assertAlmostEqual(ratio, 4.0, places=6)

    def test_manager_refuses_a_candidate_with_unverified_frames(self) -> None:
        """Defence in depth: the manager enforces the invariant even for direct callers."""
        mgr = TrustedMapTransactionManager(confirmation_margin_ns=0)
        mgr.trigger_quarantine(
            estimated_onset_ns=int(1e9),
            current_ns=int(2e9),
            weak_direction_6d=np.array([0, 0, 0, 1, 0, 0]),
            info_before_6x6=np.eye(6) * 2,
            propagated_cov_norm=1.2,
        )
        cand = CandidateMap(
            candidate_id="unverified",
            parent_map_version=mgr.trusted_version,
            repaired_poses={0: np.eye(4), 1: np.eye(4)},
            info_after_6x6=np.eye(6) * 100,
            cov_after_6x6=np.eye(6) * 0.01,
            holdout_nis=0.0,
            paired_benefit_approved=True,
            wilson_lower_bound=0.9,
            reentry_pos_jump_m=0.0,
            verified_pose_keys=frozenset({0}),
        )
        with self.assertRaises(RuntimeError):
            mgr.validate_and_resolve(cand)


if __name__ == "__main__":
    unittest.main()
