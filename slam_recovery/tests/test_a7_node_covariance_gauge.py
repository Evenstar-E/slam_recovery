"""A7 on the real node path: moving the world origin must not move the covariance bound.

The gate's evaluation basis is the trigger scan's body frame, and `evaluate_four_mode_gate` brings
a world-declared quantity there before reading it. That fixed the *transport*, but the node builds
the posterior covariance as `inv(mean(FIM_world) + epsilon*I)`: the regulariser is information, and
adding it in world then transporting the inverse is not the same object as adding it in the body
frame, because the adjoint of a translation is not orthogonal. Re-expressing the same physical
scan at a different world origin therefore changed `||P_after||` from .4876 to .4336 on the fixed
400-point fixture -- 11% with no physical change, and enough to cross the .5 tolerance elsewhere.

The candidate's information and covariance are now transported out of world once, together, and
inverted/regularised in the evaluation basis, so the bound the gate applies is origin-free.
The test fails on the pre-fix code at the covariance assertion.
"""

import unittest

import numpy as np

from slam_recovery.core import CandidateMap, TangentFrame  # noqa: F401  (contract reference)
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode


def _run_case(cloud: np.ndarray, world_y: float):
    node = OnlineRecoveryTransactionNode()
    T = np.eye(4)
    T[1, 3] = world_y
    node.scan_buffer_body[0] = cloud.copy()
    node.tx_mgr.trusted_poses[0] = T.copy()
    node._sync_spatial_map_with_trusted_poses()
    body = TangentFrame("body", "rot_trans", "scan:0")
    node.tx_mgr.trigger_quarantine(
        0, 4_000_000_000,
        np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0]),
        np.diag([60.0, 60.0, 60.0, 20.0, 40.0, 40.0]), 0.1,
        weak_direction_frame=body, info_before_frame=body,
        anchor_pose_world=T,
    )
    candidate, incumbent = {}, {}
    for k in (1, 2, 3, 4):
        node.scan_buffer_body[k] = cloud.copy()
        node._kf_timestamps[k] = k * 100_000_000
        node.tx_mgr.register_quarantined_frame(k, k * 100_000_000)
        candidate[k] = T.copy()
        incumbent[k] = T.copy()
        incumbent[k][0, 3] += 0.12
    return node.evaluate_and_commit_candidate(
        "gauge", candidate, incumbent_poses=incumbent, reentry_anchor_pose=T)


class TestNodeCovarianceGauge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cloud = np.random.default_rng(0).normal(size=(400, 3)) * 0.16
        cls.at_origin = _run_case(cloud, 0.0)
        cls.translated = _run_case(cloud, 20.0)

    def test_information_does_not_depend_on_the_world_origin(self):
        self.assertAlmostEqual(self.at_origin.weak_dir_info_after,
                               self.translated.weak_dir_info_after, places=6)

    def test_covariance_norm_does_not_depend_on_the_world_origin(self):
        a = self.at_origin.posterior_cov_norm
        b = self.translated.posterior_cov_norm
        self.assertLess(abs(a - b) / max(abs(a), abs(b)), 1e-3,
                        f"covariance norm moved with the world origin: {a} vs {b}")

    def test_mode_and_admission_do_not_flip(self):
        self.assertEqual(self.at_origin.mode, self.translated.mode)
        self.assertEqual(self.at_origin.accepted, self.translated.accepted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
