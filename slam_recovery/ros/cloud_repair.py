"""Pure helpers for the declared-corruption test.

No ROS import at module level: the relay and the recovery node both use these, and their tests
run without a master.

The corruption model is a declared body-frame z bias. `shift_z_cloud` applies it (or its inverse)
to the x/y/z bytes only, preserving header, fields and every other byte, which is what the host's
`p_pre->process` expects (x, y, z, intensity, time, ring).
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np


def window_active(stamp_ns: int, start_ns: Optional[int], end_ns: Optional[int]) -> bool:
    """Half-open [start, end); a missing bound is open on that side."""
    if start_ns is not None and stamp_ns < start_ns:
        return False
    if end_ns is not None and stamp_ns >= end_ns:
        return False
    return True


def z_field_offset(msg) -> int:
    by_name = {f.name: f for f in msg.fields}
    if "z" not in by_name:
        raise ValueError("point cloud lacks a z field")
    if by_name["z"].datatype != 7:          # sensor_msgs/PointField.FLOAT32
        raise ValueError(f"z is datatype {by_name['z'].datatype}, expected FLOAT32 (7)")
    return int(by_name["z"].offset)


def shift_z_cloud(msg, dz: float):
    """Copy `msg` with dz added to every point's z; all other bytes are untouched.

    The copy is made with the message's own class, so this works both on a live
    sensor_msgs/PointCloud2 and on the plain stand-in the tests use (no ROS import here).
    """
    step = int(msg.point_step)
    off = z_field_offset(msg)
    raw = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(-1, step).copy()
    z = raw[:, off:off + 4].view(np.float32).reshape(-1)
    z += np.float32(dz)
    out = type(msg)()
    out.header = msg.header
    out.height = msg.height
    out.width = msg.width
    out.fields = msg.fields
    out.is_bigendian = msg.is_bigendian
    out.point_step = msg.point_step
    out.row_step = msg.row_step
    out.data = raw.tobytes()
    out.is_dense = msg.is_dense
    return out


def corrupt_if_in_window(msg, stamp_ns: int, start_ns: Optional[int], end_ns: Optional[int],
                         dz: float):
    """Return (message, shifted). Outside the window the original object is forwarded unchanged."""
    if window_active(stamp_ns, start_ns, end_ns):
        return shift_z_cloud(msg, dz), True
    return msg, False


def body_z_bias(frames, delta: np.ndarray) -> Tuple[float, int]:
    """Body-frame z component of a world-frame correction, one value per frame.

    The registration returns a world-frame translation `dt`. For a frame whose body-to-world
    rotation is R, the same correction expressed in the body frame is R^T dt; its z component is
    the part of the correction along the declared corruption direction, and it is also the value
    to add to the body cloud's z to undo the bias. The median over frames is used because the
    constant bias is the same in every frame while pose error is not.
    """
    vals = []
    for _kf, _ts, pose in frames:
        R = np.asarray(pose, dtype=np.float64)[:3, :3]
        vals.append(float((R.T @ np.asarray(delta, dtype=np.float64)[:3, 3])[2]))
    if not vals:
        return 0.0, 0
    return float(np.median(vals)), len(vals)
