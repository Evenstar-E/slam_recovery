"""Tests for deterministic fault injection and MM-LINS plastic-bag vs covariance blindness."""

import unittest
import numpy as np

from slam_recovery.core import DegeneracyType, HealthWindow
from slam_recovery.diagnosis import SignatureMatrixRouter
from slam_recovery.experiments.injection import (
    LiDARInjectionParams,
    inject_lidar_attenuation_and_dropout,
    inject_plastic_bag_near_field_occlusion,
    inject_visual_exposure_drop,
)
from slam_recovery.health import MMLINSCovarianceDetector


class TestInjectionDeterminism(unittest.TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(123)
        xyz = rng.uniform(-15.0, 15.0, size=(2000, 3))
        intensity = rng.uniform(20.0, 200.0, size=(2000, 1))
        self.cloud = np.hstack([xyz, intensity])

    def test_lidar_attenuation_bit_exact_determinism(self) -> None:
        params = LiDARInjectionParams(alpha_extinct=0.03, sigma_range_m=0.03, target_drop_ratio=0.30, seed=99)
        c1, m1 = inject_lidar_attenuation_and_dropout(self.cloud, params)
        c2, m2 = inject_lidar_attenuation_and_dropout(self.cloud, params)
        np.testing.assert_array_equal(m1, m2)
        np.testing.assert_allclose(c1, c2, rtol=0.0, atol=0.0)
        # Drop rate should be close to 30%
        drop_rate = 1.0 - (len(c1) / len(self.cloud))
        self.assertTrue(0.20 <= drop_rate <= 0.40)

    def test_visual_exposure_determinism(self) -> None:
        img = np.full((64, 64, 3), 180, dtype=np.uint8)
        d1 = inject_visual_exposure_drop(img, gain_g=0.2, seed=7)
        d2 = inject_visual_exposure_drop(img, gain_g=0.2, seed=7)
        np.testing.assert_array_equal(d1, d2)
        self.assertLess(np.mean(d1), 50.0)

    def test_plastic_bag_blinds_covariance_only_but_caught_by_signature_matrix(self) -> None:
        corrupted, is_bag = inject_plastic_bag_near_field_occlusion(
            self.cloud, occluded_azimuth_fraction=0.75, bag_distance_m=0.35, seed=42
        )
        self.assertGreater(np.mean(is_bag), 0.60)

        # Because the plastic bag creates dense near-field points, posterior covariance stays small:
        fake_tight_cov = np.diag([1e-4, 1e-4, 1e-4, 1e-3, 1e-3, 1e-3])
        mmlins_det = MMLINSCovarianceDetector()
        self.assertFalse(
            mmlins_det.step(fake_tight_cov),
            "MM-LINS covariance-only detector is blinded by self-consistent near-field occlusion",
        )

        # Meanwhile, our SignatureMatrixRouter sees spiked NIS + LOSO conflict and diagnoses MEAS_CONTAM:
        win = HealthWindow(
            t_start_ns=0,
            t_end_ns=int(1e9),
            min_eig_rot=50.0,
            min_eig_trans=80.0,
            max_eig_rot_cov=1e-4,
            max_eig_trans_cov=1e-3,
            weak_dir_6d=np.array([0, 0, 0, 1, 0, 0], dtype=np.float64),
            nis_mean=3.5,
            nis_q90=5.2,
            nis_cusum=6.8,
            loso_primary_conflict=5.5,
            loso_aux_conflict=0.4,
            Cross_corr_lag_sec=0.001,
            loop_residual_spike=0.2,
            near_field_plane_ratio=float(np.mean(is_bag)),
        )
        router = SignatureMatrixRouter()
        diag = router.diagnose(win)
        self.assertIn(DegeneracyType.MEAS_CONTAM, diag.active_types)
        plan = router.route(diag)
        self.assertEqual(plan.repairer_name, "point_mixture_filter_and_realign")


if __name__ == "__main__":
    unittest.main()
