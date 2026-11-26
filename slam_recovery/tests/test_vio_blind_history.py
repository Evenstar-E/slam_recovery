from types import SimpleNamespace
import unittest

import numpy as np

from slam_recovery.vio.blind_history import recover_history


class HistoryTest(unittest.TestCase):
    def test_stationary_history_uses_blind_frame_identities_and_gates_endpoint(self):
        calibration = SimpleNamespace(body_from_camera=np.eye(3), camera_to_body=np.zeros(3))
        pose = [0, 0, 0, 0, 0, 0, 1]
        anchor = dict(timestamp=0, pose_cw=pose, inertial=[0] * 9, map_id=0)

        def frame(stamp):
            return SimpleNamespace(timestamp=stamp, imu=((stamp, 0, 0, 9.81, 0, 0, 0),))

        end = dict(timestamp=150_000_000, pose_cw=pose)
        pending = [(frame(t), "raw", True) for t in (50_000_000, 100_000_000)]
        pending.append((frame(end["timestamp"]), "raw", False))
        restored, audit = recover_history(anchor, frame(0), pending, end, calibration)
        self.assertTrue(audit["accepted"])
        self.assertEqual([r["timestamp"] for r in restored], [50_000_000, 100_000_000])
        np.testing.assert_allclose([r["pose_cw"] for r in restored], [pose, pose])
        end["pose_cw"] = [1, 0, 0, 0, 0, 0, 1]
        restored, audit = recover_history(anchor, frame(0), pending, end, calibration)
        self.assertFalse(audit["accepted"])
        self.assertEqual(restored, [])
