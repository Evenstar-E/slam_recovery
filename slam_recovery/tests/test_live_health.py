from dataclasses import replace
import unittest

import numpy as np

from slam_recovery.core import HealthWindow, RecoveryState
from slam_recovery.health import JointHealthDetector
from slam_recovery.ros.live_health import SUPPORT_RADIUS_M, score_local_planes
from slam_recovery.validation.spatial_index import RadiusIndex


class TestLiveHealth(unittest.TestCase):
    def setUp(self):
        x, y = np.meshgrid(np.arange(-2., 2.1, .25), np.arange(-2., 2.1, .25))
        plane = np.column_stack((x.ravel(), y.ravel(), np.zeros(x.size)))
        self.index = RadiusIndex(plane, SUPPORT_RADIUS_M)
        self.points = plane[20:-20:2]

    def test_supported_shift_changes_residual_with_same_scale(self):
        clean, n, supported = score_local_planes(self.index, self.points, .12, 10)
        shifted, _, shifted_supported = score_local_planes(
            self.index, self.points + [0, 0, .5], .12, 10
        )
        self.assertEqual(n, supported)
        self.assertEqual(n, shifted_supported)
        self.assertAlmostEqual(clean, 0.)
        self.assertAlmostEqual(shifted, (.5 / .12)**2)

    def test_extrapolating_planes_outside_support_does_not_create_a_score(self):
        cloud = np.vstack((self.points, self.points + [10, 0, 0]))
        value, n, supported = score_local_planes(self.index, cloud, .12, 10)
        self.assertIsNone(value)
        self.assertEqual(n, len(cloud))
        self.assertEqual(supported, len(self.points))


class TestInnovationChannel(unittest.TestCase):
    def test_geometry_evidence_is_retained_but_cannot_trigger_this_channel(self):
        window = HealthWindow(1, 2, 100.0, 5.0, 0.0, 0.0, np.zeros(6),
                              .1, .135, 0.0, 0.0, 0.0, 0.0, 0.0)
        joint = JointHealthDetector()
        self.assertEqual(joint.step(window).state, RecoveryState.SUSPECT)
        self.assertEqual(joint.step(window).state, RecoveryState.QUARANTINED)

        innovation = JointHealthDetector(joint.cfg)
        good = innovation.step(window, geometry_can_trigger=False)
        self.assertEqual(good.state, RecoveryState.HEALTHY)
        self.assertEqual(good.evidence["geometry_weak"], 1.0)
        self.assertEqual(good.evidence["innovation_alarm"], 0.0)
        bad = replace(window, nis_mean=12.0, nis_q90=16.2)
        self.assertEqual(innovation.step(bad, geometry_can_trigger=False).state,
                         RecoveryState.SUSPECT)
        self.assertEqual(innovation.step(bad, geometry_can_trigger=False).state,
                         RecoveryState.QUARANTINED)
        self.assertEqual(innovation.step(replace(window, hard_failure=True),
                                         geometry_can_trigger=False).state,
                         RecoveryState.QUARANTINED)


if __name__ == "__main__":
    unittest.main()
