"""The voxel-sampled support reference must pick the same points after the speed-up.

The row-wise unique over the whole map was a multi-second refresh on large maps; packing the
voxel indices into one int64 keeps the same first-occurrence selection. This test compares the
two selections exactly on data with duplicates and negative coordinates.
"""

import unittest

import numpy as np

from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode


class _FakeNode:
    def __init__(self, pts):
        self.pts = pts

    def get_trusted_map_points(self, max_pts=2000):
        return self.pts


class SupportReferenceDedupTest(unittest.TestCase):
    def test_packed_key_selection_matches_rowwise_unique(self):
        rng = np.random.default_rng(5)
        pts = rng.uniform(-20, 20, (5000, 3))
        # exact duplicates and points sharing a voxel must still pick the first occurrence
        pts = np.vstack([pts, pts[:200], pts[:200] + 1e-6])
        node = _FakeNode(pts)
        got = OnlineRecoveryTransactionNode.support_reference(node, voxel_m=0.3)

        q = np.floor(pts / 0.3).astype(np.int64)
        _, first = np.unique(q, axis=0, return_index=True)
        expected = pts[np.sort(first)]
        self.assertEqual(got.shape, expected.shape)
        self.assertTrue(np.array_equal(got, expected))

    def test_empty_map_returns_empty(self):
        node = _FakeNode(np.zeros((0, 3)))
        got = OnlineRecoveryTransactionNode.support_reference(node, voxel_m=0.3)
        self.assertEqual(got.shape[0], 0)


if __name__ == "__main__":
    unittest.main()
