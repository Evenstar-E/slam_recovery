import unittest

import numpy as np

from slam_recovery.core import GateThresholds, TangentFrame
from slam_recovery.experiments.evaluation.surface_fixture import run_fixture
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.validation.surface_admission import SurfaceView, centers, surface_admission


class TestSurfaceAdmission(unittest.TestCase):
    def test_no_future_or_duplicate_station_votes(self):
        xyz = centers([(0, 0, 0)])
        first = SurfaceView("1", "a", 11, xyz)
        duplicate_frame = SurfaceView("1", "b", 12, xyz)
        duplicate_station = SurfaceView("2", "a", 13, xyz)
        future = SurfaceView("3", "b", 15, xyz)
        report = surface_admission(
            set(), {(0, 0, 0)}, (first, duplicate_frame, duplicate_station, future),
            candidate_end_ns=10, decision_ns=14,
        )
        self.assertEqual(report.status, "MISSING")

    def test_four_arms_share_surface_denominator_and_include_free_space(self):
        result = run_fixture()
        self.assertEqual(result["admission"]["beneficial"]["status"], "PASSED")
        self.assertEqual(result["admission"]["harmful"]["status"], "FAILED")
        region = result["evaluation"]["regions"]["common"]
        self.assertEqual({v["surveyed_surface_voxels"] for v in region["arms"].values()}, {200})
        self.assertEqual(region["coverage_gain_gated_vs_isolation_pp"], 15)
        self.assertEqual(region["arms"]["forced"]["off_surface_voxels"], 40)
        self.assertEqual(region["arms"]["gated"]["off_surface_voxels"], 0)
        self.assertTrue(region["isolation_pollution_margin_met"])

    def test_real_transaction_entry_uses_exact_pending_map_delta(self):
        grid = [(x, y, 0) for x in range(-12, 15) for y in range(-12, 12)]
        before = {key for key in grid if key[0] < 9}
        node = OnlineRecoveryTransactionNode(
            confirmation_margin_sec=0, gate_thresholds=GateThresholds(require_surface_evidence=True)
        )
        node.scan_buffer_body[0] = centers(sorted(before))
        node.tx_mgr.trusted_poses[0] = np.eye(4)
        node._sync_spatial_map_with_trusted_poses()
        self.assertEqual(node.committed_voxel_set, before)
        basis = TangentFrame("body", "rot_trans", "fixture")
        node.tx_mgr.trigger_quarantine(
            int(10e9), int(20e9), np.array([0, 0, 0, 1, 0, 0]), np.eye(6) * 2, 1.2,
            weak_direction_frame=basis, info_before_frame=basis, anchor_pose_world=np.eye(4),
        )
        poses, incumbent = {}, {}
        for key in range(1, 5):
            node.scan_buffer_body[key] = centers(grid)
            node._kf_timestamps[key] = int(10e9) + key
            poses[key] = np.eye(4)
            incumbent[key] = np.eye(4)
            incumbent[key][2, 3] = 0.3

        args = dict(aux_or_loop_info_6x6=np.eye(6) * 100, incumbent_poses=incumbent,
                    reentry_anchor_pose=np.eye(4), surface_decision_ns=int(20e9))
        report = node.evaluate_and_commit_candidate("missing", poses, **args)
        self.assertFalse(report.accepted)
        self.assertEqual(report.evidence_status, "MISSING")
        self.assertIn("held-out surface", report.reason)
        self.assertEqual(node.committed_voxel_set, before)

        # Two views agree with one another but contain no evidence for the new strip.
        invalid_views = tuple(SurfaceView(str(k), str(k), int(15e9) + k,
                                          centers(sorted(before))) for k in range(2))
        report = node.evaluate_and_commit_candidate("defer", poses, surface_views=invalid_views, **args)
        self.assertFalse(report.accepted)
        self.assertEqual(report.evidence_status, "FAILED")
        self.assertGreater(node.last_surface_evidence.unverified_added_voxels, 0)
        self.assertEqual(node.committed_voxel_set, before)

        views = tuple(SurfaceView(str(k), str(k), int(15e9) + k,
                                  centers(grid) + (k + 1) / 1000) for k in range(2))
        report = node.evaluate_and_commit_candidate("admit", poses, surface_views=views, **args)
        self.assertTrue(report.accepted, report.reason)
        self.assertEqual(report.committed_pose_keys, [1, 2, 3, 4])
        self.assertEqual(node.committed_voxel_set, set(grid))
        self.assertEqual(len(node.committed_voxel_set - before), node.last_surface_evidence.added_voxels)


if __name__ == "__main__":
    unittest.main()
