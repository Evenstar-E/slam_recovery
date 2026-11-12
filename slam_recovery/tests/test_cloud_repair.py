"""The declared-corruption helpers, without ROS or a master.

What matters for the INJECTION test: the window is half-open and the outside bytes are forwarded
untouched; a shift changes only z; the header (including its stamp) and every other field survive;
and the body-z projection of a registration correction has the sign that undoes the bias.
"""

import struct
import unittest

import numpy as np

from slam_recovery.ros.cloud_repair import (
    body_z_bias,
    corrupt_if_in_window,
    shift_z_cloud,
    window_active,
)


class _Field:
    def __init__(self, name, offset, datatype=7):
        self.name = name
        self.offset = offset
        self.datatype = datatype


class _Stamp:
    def __init__(self, secs=0, nsecs=0):
        self.secs = secs
        self.nsecs = nsecs


class _Header:
    def __init__(self):
        self.stamp = _Stamp(1711547999, 123456789)
        self.frame_id = "velodyne"


class _Cloud:
    """Stand-in with the velodyne layout the host parses: x,y,z,intensity,time,ring."""

    def __init__(self):
        self.header = _Header()
        self.height = 1
        self.width = 0
        self.fields = [_Field("x", 0), _Field("y", 4), _Field("z", 8),
                       _Field("intensity", 12), _Field("time", 16),
                       _Field("ring", 20, datatype=4)]
        self.point_step = 24
        self.row_step = 0
        self.is_bigendian = False
        self.is_dense = True
        self.data = b""

    def set_points(self, rows):
        self.width = len(rows)
        self.data = b"".join(struct.pack("<fffffH2x", *r) for r in rows)


ROWS = [(1.0, 2.0, 3.0, 0.5, 0.01, 7), (4.0, 5.0, 6.0, 0.6, 0.02, 8)]


class CorruptRelayTest(unittest.TestCase):
    def test_window_is_half_open(self):
        self.assertFalse(window_active(99, 100, 200))
        self.assertTrue(window_active(100, 100, 200))
        self.assertTrue(window_active(199, 100, 200))
        self.assertFalse(window_active(200, 100, 200))

    def test_open_bounds(self):
        self.assertTrue(window_active(0, None, 200))
        self.assertTrue(window_active(999, 100, None))
        self.assertTrue(window_active(50, None, None))

    def test_outside_window_the_object_is_forwarded_unchanged(self):
        msg = _Cloud()
        msg.set_points(ROWS)
        out, shifted = corrupt_if_in_window(msg, 50, 100, 200, 0.5)
        self.assertFalse(shifted)
        self.assertIs(out, msg)

    def test_inside_window_only_z_changes_and_the_header_survives(self):
        msg = _Cloud()
        msg.set_points(ROWS)
        out, shifted = corrupt_if_in_window(msg, 150, 100, 200, 0.5)
        self.assertTrue(shifted)
        self.assertEqual(out.header.stamp.secs, 1711547999)
        self.assertEqual(out.header.stamp.nsecs, 123456789)
        self.assertEqual(out.header.frame_id, "velodyne")
        self.assertEqual([f.name for f in out.fields], [f.name for f in msg.fields])
        self.assertEqual(out.point_step, msg.point_step)
        self.assertEqual(out.width, msg.width)
        before = np.frombuffer(msg.data, dtype=np.uint8).reshape(-1, 24)
        after = np.frombuffer(out.data, dtype=np.uint8).reshape(-1, 24)
        # z bytes shifted by exactly dz
        zb = before[:, 8:12].view(np.float32).reshape(-1)
        za = after[:, 8:12].view(np.float32).reshape(-1)
        np.testing.assert_allclose(za, zb + np.float32(0.5), rtol=0, atol=1e-6)
        # every other byte identical
        for lo, hi in ((0, 8), (12, 24)):
            np.testing.assert_array_equal(before[:, lo:hi], after[:, lo:hi])

    def test_repair_shift_undoes_the_injected_bias(self):
        msg = _Cloud()
        msg.set_points(ROWS)
        corrupted = shift_z_cloud(msg, 0.5)
        repaired = shift_z_cloud(corrupted, -0.5)
        orig_z = np.frombuffer(msg.data, dtype=np.uint8).reshape(-1, 24)[:, 8:12] \
            .view(np.float32).reshape(-1)
        rep_z = np.frombuffer(repaired.data, dtype=np.uint8).reshape(-1, 24)[:, 8:12] \
            .view(np.float32).reshape(-1)
        np.testing.assert_allclose(rep_z, orig_z, rtol=0, atol=1e-6)


class BodyBiasTest(unittest.TestCase):
    def test_identity_rotation_returns_the_injected_bias_with_positive_sign(self):
        # The registration correction for a +0.5 body-z corruption is -0.5; the estimate is the
        # corruption (+0.5), so `shift_z_cloud(msg, -bias)` removes it. The sign is pinned here.
        T = np.eye(4)
        frames = [(1, 0, T)]
        bias, n = body_z_bias(frames, np.array([[1, 0, 0, 0], [0, 1, 0, 0],
                                                [0, 0, 1, -0.5], [0, 0, 0, 1]]))
        self.assertEqual(n, 1)
        self.assertAlmostEqual(bias, 0.5, places=9)

    def test_rotation_is_undone_before_projecting(self):
        # A world correction that is the body-z bias rotated into world must project back to -0.5.
        c, s = np.cos(1.0), np.sin(1.0)
        R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
        T = np.eye(4)
        T[:3, :3] = R
        delta = np.eye(4)
        delta[:3, 3] = R @ np.array([0.0, 0.0, -0.5])
        bias, _ = body_z_bias([(1, 0, T)], delta)
        self.assertAlmostEqual(bias, 0.5, places=9)

    def test_median_ignores_one_outlying_frame(self):
        delta = np.eye(4)
        delta[2, 3] = -0.5
        frames = [(k, 0, np.eye(4)) for k in range(5)]
        # one frame whose pose puts the correction off the z axis is outvoted
        T = np.eye(4)
        T[:3, :3] = np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])
        frames.append((99, 0, T))
        bias, n = body_z_bias(frames, delta)
        self.assertEqual(n, 6)
        self.assertAlmostEqual(bias, 0.5, places=9)


if __name__ == "__main__":
    unittest.main()
