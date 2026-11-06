"""Regression tests for the near-field mixture filter's plane-selection rule.

The selector used to pick the RANSAC hypothesis with the most plane inliers. On real indoor
scans that is the floor, so the filter stripped the floor and left the occluder behind
(measured: 54-57% removed with ~17 000 plastic-bag returns surviving). These tests pin the
correct behaviour: select the hypothesis that best explains a near-field *sheet*, strip that
sheet, and leave clean scans untouched.
"""

import unittest

import numpy as np

from slam_recovery.experiments.injection.injectors import inject_plastic_bag_near_field_occlusion
from slam_recovery.repair.point_mixture_repairer import (
    MixtureFilterConfig,
    filter_self_consistent_near_field_contaminants,
)


def _synthetic_room(n_floor: int = 20000, n_wall: int = 6000, roughness: float = 0.03, seed: int = 0) -> np.ndarray:
    """A floor plus one wall, with real-scan-like surface roughness (not mathematical planes)."""
    rng = np.random.default_rng(seed)
    floor = np.column_stack(
        [
            rng.uniform(-10.0, 10.0, n_floor),
            rng.uniform(-10.0, 10.0, n_floor),
            -1.0 + rng.normal(0.0, roughness, n_floor),
            np.full(n_floor, 80.0),
        ]
    )
    wall = np.column_stack(
        [
            np.full(n_wall, 8.0) + rng.normal(0.0, roughness, n_wall),
            rng.uniform(-10.0, 10.0, n_wall),
            rng.uniform(-1.0, 3.0, n_wall),
            np.full(n_wall, 80.0),
        ]
    )
    return np.vstack([floor, wall])


class TestMixtureFilterSelection(unittest.TestCase):
    def test_clean_scan_is_not_stripped(self) -> None:
        clean = _synthetic_room()
        keep, ratio, _, _ = filter_self_consistent_near_field_contaminants(clean, MixtureFilterConfig())
        self.assertEqual(int((~keep).sum()), 0, msg=f"clean scan stripped (contam_ratio={ratio:.4f})")
        self.assertLess(ratio, MixtureFilterConfig().min_occluder_fraction)

    def test_injected_sheet_is_removed_and_background_survives(self) -> None:
        clean = _synthetic_room()
        injected, bag_mask = inject_plastic_bag_near_field_occlusion(
            clean, occluded_azimuth_fraction=0.88, seed=7
        )
        keep, ratio, _, _ = filter_self_consistent_near_field_contaminants(injected, MixtureFilterConfig())
        strip_fraction = float(np.mean(~keep))
        bag_surviving = int((keep & bag_mask).sum())
        background_total = int((~bag_mask).sum())
        background_lost = int((~keep & ~bag_mask).sum())

        self.assertGreaterEqual(strip_fraction, 0.85, msg="occluder sheet was not stripped")
        self.assertLessEqual(
            bag_surviving, int(0.01 * int(bag_mask.sum())), msg="plastic-bag returns survived the filter"
        )
        self.assertLessEqual(
            background_lost, int(0.01 * background_total), msg="filter removed genuine background"
        )
        # The strip must be dominated by the sheet, not by a coincidentally planar surface.
        self.assertGreater(float(ratio), MixtureFilterConfig().min_occluder_fraction)


if __name__ == "__main__":
    unittest.main()
