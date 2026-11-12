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


class ReferenceGrid:
    """Uniform-cell nearest-neighbour lookup over a reference point cloud.

    scipy is not available in the interpreter the ROS node runs under, and the reference is a few
    thousand points, so a dict of cells is enough: a query looks in its own cell and the 26
    neighbours (1.5 m reach at 0.5 m cells) and takes the closest point. Points with no reference
    inside the reach are reported as +inf and excluded from the cost.
    """

    def __init__(self, points, cell_m: float = 0.5):
        self.cell = float(cell_m)
        pts = np.asarray(points, dtype=np.float64)[:, :3]
        self.cells = {}
        if len(pts) == 0:
            return
        keys = np.floor(pts / self.cell).astype(np.int64)
        for k, p in zip(map(tuple, keys), pts):
            self.cells.setdefault(k, []).append(p)
        self.cells = {k: np.asarray(v) for k, v in self.cells.items()}

    def nearest_distances(self, queries, reach: int = 1):
        out = np.full(len(queries), np.inf)
        if not self.cells:
            return out
        for i, q in enumerate(np.asarray(queries, dtype=np.float64)):
            base = np.floor(q / self.cell).astype(np.int64)
            best = np.inf
            for dx in range(-reach, reach + 1):
                for dy in range(-reach, reach + 1):
                    for dz in range(-reach, reach + 1):
                        arr = self.cells.get((int(base[0] + dx), int(base[1] + dy),
                                              int(base[2] + dz)))
                        if arr is None:
                            continue
                        d = float(np.min(np.linalg.norm(arr - q, axis=1)))
                        if d < best:
                            best = d
            out[i] = best
        return out


def estimate_body_z_bias(scan_body, pose, grid: ReferenceGrid, z_min: float = -0.6,
                         z_max: float = 1.4, step: float = 0.05, n_samples: int = 80,
                         min_valid: int = 20):
    """One-dimensional search for the body-z shift that best fits the reference map.

    The scan is placed with the *incumbent* pose (independent of the host pose that absorbed the
    bias) and shifted by `-b` along body z; the cost is the median nearest-reference distance.
    Returns (bias, curve, n_valid). `bias` is the injected corruption, i.e. the value to subtract
    from the cloud; a +0.5 body-z corruption gives +0.5 here.

    The reference has no normals in this repository's live path, so the cost is point-to-nearest
    rather than point-to-plane. That is the same direction of information (the scan is displaced
    along z relative to the map) and does not assume a local plane fit the driver cannot build
    without scipy.
    """
    pts = np.asarray(scan_body, dtype=np.float64)[:, :3]
    if len(pts) == 0:
        return 0.0, [], 0
    if len(pts) > n_samples:
        idx = np.linspace(0, len(pts) - 1, n_samples).astype(int)
        pts = pts[idx]
    R = np.asarray(pose, dtype=np.float64)[:3, :3]
    t = np.asarray(pose, dtype=np.float64)[:3, 3]
    best_b, best_cost, n_best = 0.0, float("inf"), 0
    curve = []
    for b in np.arange(z_min, z_max + 1e-9, step):
        shifted = pts.copy()
        shifted[:, 2] -= b
        q = shifted @ R.T + t
        d = grid.nearest_distances(q)
        valid = np.isfinite(d)
        n_valid = int(valid.sum())
        cost = float(np.median(d[valid])) if n_valid else float("inf")
        curve.append((float(b), cost, n_valid))
        if n_valid >= min_valid and cost < best_cost:
            best_b, best_cost, n_best = float(b), cost, n_valid
    return best_b, curve, n_best


def body_z_bias(frames, delta: np.ndarray) -> Tuple[float, int]:
    """Body-frame z component of a world-frame correction, one value per frame.

    The registration returns a world-frame translation `dt`. For a frame whose body-to-world
    rotation is R, the same correction expressed in the body frame is R^T dt. That is the
    *correction*, i.e. minus the corruption; this function returns the corruption estimate (the
    value that was injected), so the caller undoes it with `shift_z_cloud(msg, -bias)`. The sign
    is fixed here rather than at the call site: an inverted sign would double the bias instead of
    removing it. The median over frames is used because the constant bias is the same in every
    frame while pose error is not.
    """
    vals = []
    for _kf, _ts, pose in frames:
        R = np.asarray(pose, dtype=np.float64)[:3, :3]
        vals.append(-float((R.T @ np.asarray(delta, dtype=np.float64)[:3, 3])[2]))
    if not vals:
        return 0.0, 0
    return float(np.median(vals)), len(vals)
