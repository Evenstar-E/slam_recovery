"""The support test's fast path must answer exactly the question the slow path answered.

The decision used to spend ~4 s of a 4.4 s window building distance matrices for one boolean per
query point: "is any reference point within r". A cell grid of cell size r answers that exactly --
a point within r of a query necessarily lies in one of the 27 surrounding cells -- but "exact" is
a claim, so it is checked against brute force on random layouts, including sparse and empty
neighbourhoods.
"""

import unittest

import numpy as np

from slam_recovery.sim.transaction_manager_node import _RadiusIndex


class TestRadiusIndex(unittest.TestCase):
    def test_matches_brute_force_on_random_layouts(self):
        rng = np.random.default_rng(0)
        for _ in range(20):
            ref = rng.normal(size=(int(rng.integers(1, 3000)), 3)) * 10 ** rng.uniform(-1, 1)
            q = rng.normal(size=(int(rng.integers(1, 200)), 3)) * 6
            radius = 1.0
            got = _RadiusIndex(ref, radius).within_radius_mask(q, radius)
            d2 = np.sum((q[:, None, :] - ref[None, :, :]) ** 2, axis=-1)
            want = d2.min(axis=1) <= radius * radius
            self.assertTrue(np.array_equal(got, want))

    def test_no_neighbour_is_a_false_not_an_error(self):
        ref = np.array([[0.0, 0.0, 0.0]])
        q = np.array([[100.0, 100.0, 100.0], [0.1, 0.0, 0.0]])
        inside = _RadiusIndex(ref, 1.0).within_radius_mask(q, 1.0)
        self.assertEqual(list(inside), [False, True])

    def test_a_point_exactly_at_the_radius_counts(self):
        ref = np.array([[1.0, 0.0, 0.0]])
        q = np.array([[0.0, 0.0, 0.0]])
        self.assertTrue(bool(_RadiusIndex(ref, 1.0).within_radius_mask(q, 1.0)[0]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
