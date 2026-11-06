"""Export real M2DGR `hall_01` into a ready-to-open NVIDIA Isaac Sim 5.1 scene package.

Inputs (all local, no network, no ROS runtime)
---------------------------------------------
* ``D:/REPAIR/hall_01.bag``           29 GB ROS1 bag, read via direct ``index_pos`` seek:
                                      ``/velodyne_points`` (conn=5) and ``/handsfree/imu`` (conn=2).
* ``hall_01_plasticbag_comparison.mcap``  timestamped trajectories: Leica GT, B0/B2 degraded, B6 repaired.

Outputs (``D:/REPAIR/isaac_sim_hall_01/``)
------------------------------------------
* ``hall_01_isaac_scene.usda``  native USD ASCII stage, opens directly in Isaac Sim 5.1
* ``hall_01_scene_geometry.obj`` + ``.mtl``, ``hall_01_pointcloud_colored.ply``
* ``run_in_isaac_sim_5_1.py``, ``README_ISAAC_SIM_5_1.md``
* ``hall_01_isaac_3d_preview.png``

Attitude handling
-----------------
`hall_01` is hand-held: the operator walks, stops, spins and reverses, so trajectory-tangent yaw is
wrong. Body attitude comes from the AHRS quaternion in ``/handsfree/imu`` plus a single constant
offset ``theta0`` recovered by maximising wall sharpness (see ``calibrate_hall01_imu_yaw.py``).
Using it removes 33.9 % of spurious occupied voxels; see ``hall_01_alignment_diagnosis.png``.

Map layers
----------
* ``Trusted_*``   surfaces registered on the B6 repaired trajectory (delayed-commit + validated commit)
* ``B0_*``        surfaces registered on the unprotected FAST-LIO2 trajectory, plus the injected
                  near-field occluder sheet, i.e. the contamination that B0 permanently bakes in
* ``B2_*``        surfaces registered on MM-LINS's drifted PGO trajectory (confirmation-delay tail)
"""

from __future__ import annotations

import json
import struct
import sys
from compression import zstd
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

BAG_PATH = Path(r"D:\REPAIR\hall_01.bag")
MCAP_PBAG = Path(r"D:\REPAIR\slam_recovery_upstream\slam_recovery\experiments\hall_01_plasticbag_comparison.mcap")
OUT_DIR = Path(r"D:\REPAIR\isaac_sim_hall_01")

BAG_TOPIC_LIDAR = 5
BAG_TOPIC_IMU = 2

WALL_Z_LO, WALL_Z_HI = 0.15, 2.40
FLOOR_Z_LO, FLOOR_Z_HI = -1.40, -0.85
MIN_RANGE, MAX_RANGE = 0.8, 22.0

TRUSTED_VOXEL = 0.22
POLLUTED_VOXEL = 0.26

# Defaults, overridden by hall01_imu_yaw_calibration.json when present.
DEFAULT_SIGN = 1.0
DEFAULT_THETA0_DEG = 99.1
DEFAULT_IMU_DT = -0.10


# --------------------------------------------------------------------------------------
# ROS1 bag access
# --------------------------------------------------------------------------------------
def _parse_rosbag_header(b: bytes) -> Dict[str, bytes]:
    """Parse a ROSBAG V2.0 record header into a field map."""
    d: Dict[str, bytes] = {}
    pos = 0
    while pos < len(b):
        flen = struct.unpack_from("<I", b, pos)[0]
        kv = b[pos + 4 : pos + 4 + flen]
        eq = kv.find(b"=")
        if eq > 0:
            d[kv[:eq].decode("ascii", "ignore")] = kv[eq + 1 :]
        pos += 4 + flen
    return d


def _read_bag_index(f) -> Tuple[int, int, int]:
    """Return ``(index_pos, conn_count, chunk_count)`` from the ROSBAG V2.0 bag header record."""
    f.readline()
    hlen = struct.unpack("<I", f.read(4))[0]
    bhdr = _parse_rosbag_header(f.read(hlen))
    return (
        struct.unpack("<Q", bhdr["index_pos"])[0],
        struct.unpack("<I", bhdr["conn_count"])[0],
        struct.unpack("<I", bhdr["chunk_count"])[0],
    )


def _iter_index_chunk_offsets(
    f, index_pos: int, conn_count: int, chunk_count: int, conn_ids: Iterable[int]
) -> List[Tuple[float, int]]:
    """Return ``[(row_start_time, chunk_offset)]`` for chunks carrying any of ``conn_ids``.

    ``index_pos`` points at the first *connection* record; the connection block is skipped before
    the ``chunk_count`` chunk-info records, each of which lists the connections it contains.
    """
    wanted = set(conn_ids)
    f.seek(index_pos)
    for _ in range(conn_count):
        l1 = struct.unpack("<I", f.read(4))[0]
        f.seek(l1, 1)
        l2 = struct.unpack("<I", f.read(4))[0]
        f.seek(l2, 1)

    out: List[Tuple[float, int]] = []
    for _ in range(chunk_count):
        hlen = struct.unpack("<I", f.read(4))[0]
        hdr = _parse_rosbag_header(f.read(hlen))
        dlen = struct.unpack("<I", f.read(4))[0]
        data = f.read(dlen)
        if hdr.get("op") != b"\x06":
            continue
        cpos = struct.unpack("<Q", hdr["chunk_pos"])[0]
        s_sec, s_nsec = struct.unpack("<II", hdr["start_time"])
        for off in range(0, len(data), 8):
            cid, cnt = struct.unpack_from("<II", data, off)
            if cid in wanted and cnt > 0:
                out.append((s_sec + s_nsec * 1e-9, cpos))
                break
    return out


def _iter_chunk_messages(f, chunk_offset: int):
    """Yield (conn_id, timestamp, body) for every message record inside one chunk."""
    f.seek(chunk_offset)
    chlen = struct.unpack("<I", f.read(4))[0]
    f.seek(chlen, 1)
    cdlen = struct.unpack("<I", f.read(4))[0]
    cdata = f.read(cdlen)
    off = 0
    while off < len(cdata):
        mhlen = struct.unpack_from("<I", cdata, off)[0]
        mhdr = _parse_rosbag_header(cdata[off + 4 : off + 4 + mhlen])
        mdlen = struct.unpack_from("<I", cdata, off + 4 + mhlen)[0]
        body = cdata[off + 8 + mhlen : off + 8 + mhlen + mdlen]
        off += 8 + mhlen + mdlen
        if mhdr.get("op") != b"\x02":
            continue
        sec, nsec = struct.unpack("<II", mhdr["time"])
        yield struct.unpack("<I", mhdr["conn"])[0], sec + nsec * 1e-9, body


def _decode_pointcloud2(body: bytes) -> np.ndarray:
    """Decode a ROS1 ``sensor_msgs/PointCloud2`` body into an (N, 4) x/y/z/intensity array."""
    flen = struct.unpack_from("<I", body, 12)[0]
    pos = 16 + flen
    _, _, nfields = struct.unpack_from("<III", body, pos)
    pos += 12
    for _ in range(nfields):
        nlen = struct.unpack_from("<I", body, pos)[0]
        pos += 4 + nlen + 9
    _, point_step, _, data_len = struct.unpack_from("<BIII", body, pos)
    pos += 13
    dtype = np.dtype(
        {
            "names": ["x", "y", "z", "intensity"],
            "formats": ["<f4", "<f4", "<f4", "<f4"],
            "offsets": [0, 4, 8, 12],
            "itemsize": point_step,
        }
    )
    arr = np.frombuffer(body[pos : pos + data_len], dtype=dtype)
    return np.column_stack([arr["x"], arr["y"], arr["z"], arr["intensity"]]).astype(np.float64)


def _decode_imu_yaw(body: bytes) -> float:
    flen = struct.unpack_from("<I", body, 12)[0]
    qx, qy, qz, qw = struct.unpack_from("<dddd", body, 16 + flen)
    return float(np.arctan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz)))


def extract_scans_and_imu_from_bag(
    bag_path: Path, scan_stride: int = 25
) -> Tuple[List[Tuple[float, np.ndarray]], np.ndarray, np.ndarray]:
    """Fast direct-index extraction of `/velodyne_points` and `/handsfree/imu` from the 29 GB bag."""
    scans: List[Tuple[float, np.ndarray]] = []
    imu_ts: List[float] = []
    imu_yaw: List[float] = []

    with open(bag_path, "rb") as f:
        index_pos, conn_count, chunk_count = _read_bag_index(f)
        lidar_chunks = _iter_index_chunk_offsets(f, index_pos, conn_count, chunk_count, [BAG_TOPIC_LIDAR])
        imu_chunks = _iter_index_chunk_offsets(f, index_pos, conn_count, chunk_count, [BAG_TOPIC_IMU])

        for _, cpos in lidar_chunks[::scan_stride]:
            for cid, t_scan, body in _iter_chunk_messages(f, cpos):
                if cid != BAG_TOPIC_LIDAR:
                    continue
                pts = _decode_pointcloud2(body)[::6]
                rng = np.linalg.norm(pts[:, :3], axis=1)
                keep = (
                    (rng > MIN_RANGE)
                    & (rng < MAX_RANGE)
                    & (pts[:, 2] > FLOOR_Z_LO - 0.15)
                    & (pts[:, 2] < WALL_Z_HI + 0.2)
                    & np.isfinite(rng)
                )
                scans.append((t_scan, pts[keep]))

        # IMU at ~150 Hz: subsample the chunk list, keep every message.
        for _, cpos in imu_chunks[::5]:
            for cid, t_msg, body in _iter_chunk_messages(f, cpos):
                if cid != BAG_TOPIC_IMU:
                    continue
                imu_ts.append(t_msg)
                imu_yaw.append(_decode_imu_yaw(body))

    order = np.argsort(imu_ts)
    return (
        scans,
        np.asarray(imu_ts, dtype=np.float64)[order],
        np.asarray(imu_yaw, dtype=np.float64)[order],
    )


# --------------------------------------------------------------------------------------
# MCAP trajectory access
# --------------------------------------------------------------------------------------
def extract_mcap_paths(mcap_path: Path) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Extract timestamped 3D trajectories ``(ts, xyz)`` for every ``*_path`` topic in the MCAP."""
    buf = mcap_path.read_bytes()
    pos = 8
    channels: Dict[int, str] = {}
    chunks: List[bytes] = []
    while pos < len(buf) - 8:
        op = buf[pos]
        rlen = struct.unpack_from("<Q", buf, pos + 1)[0]
        body = buf[pos + 9 : pos + 9 + rlen]
        if op == 0x04:
            cid, _, tlen = struct.unpack_from("<HHI", body, 0)
            channels[cid] = body[8 : 8 + tlen].decode("utf-8", "ignore")
        elif op == 0x06:
            chunks.append(body)
        pos += 9 + rlen

    paths: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for cbody in chunks:
        clen = struct.unpack_from("<I", cbody, 28)[0]
        raw = zstd.decompress(cbody[32 + clen + 8 :])
        cpos = 0
        while cpos < len(raw):
            op = raw[cpos]
            rlen = struct.unpack_from("<Q", raw, cpos + 1)[0]
            mbody = raw[cpos + 9 : cpos + 9 + rlen]
            if op == 0x05:
                cid = struct.unpack_from("<H", mbody, 0)[0]
                topic = channels.get(cid, "")
                if topic.endswith("_path") or topic == "/gt/path":
                    rp = mbody[22:]
                    flen = struct.unpack_from("<I", rp, 12)[0]
                    p_off = 16 + flen
                    n_poses = struct.unpack_from("<I", rp, p_off)[0]
                    p_off += 4
                    ts_l, xyz_l = [], []
                    for _ in range(n_poses):
                        sec, nsec = struct.unpack_from("<II", rp, p_off + 4)
                        pflen = struct.unpack_from("<I", rp, p_off + 12)[0]
                        p_off += 16 + pflen
                        x, y, z = struct.unpack_from("<ddd", rp, p_off)
                        ts_l.append(sec + nsec * 1e-9)
                        xyz_l.append((x, y, z))
                        p_off += 56
                    paths[topic] = (
                        np.asarray(ts_l, dtype=np.float64),
                        np.asarray(xyz_l, dtype=np.float64),
                    )
            cpos += 9 + rlen
    return paths


# --------------------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------------------
def load_calibration(out_dir: Path) -> Tuple[float, float, float]:
    """Return ``(sign, theta0_rad, imu_dt)`` from the calibration artefact, with sane defaults."""
    cal_p = out_dir / "hall01_imu_yaw_calibration.json"
    diag_p = out_dir / "hall01_alignment_diagnosis.json"
    sign, theta_deg, dt = DEFAULT_SIGN, DEFAULT_THETA0_DEG, DEFAULT_IMU_DT
    if cal_p.exists():
        d = json.loads(cal_p.read_text(encoding="utf-8"))
        sign = float(d["best"]["sign"])
        theta_deg = float(d["best"]["theta0_deg"])
    if diag_p.exists():
        d = json.loads(diag_p.read_text(encoding="utf-8"))
        dt = float(d.get("best_time_offset_s", dt))
    return sign, np.deg2rad(theta_deg), dt


def interpolate_attitude(ts: np.ndarray, xyz: np.ndarray, yaw_src_t: np.ndarray, yaw_src: np.ndarray) -> np.ndarray:
    """Sample a continuous yaw series at the trajectory timestamps (circularly unwrapped)."""
    unwrapped = np.unwrap(yaw_src)
    return np.interp(ts, yaw_src_t, unwrapped)


def register_scan_stream(
    scans: Sequence[Tuple[float, np.ndarray]],
    traj_ts: np.ndarray,
    traj_xyz: np.ndarray,
    imu_ts: np.ndarray,
    imu_yaw: np.ndarray,
    sign: float,
    theta0: float,
    imu_dt: float,
) -> np.ndarray:
    """Register every scan into the Leica world frame using the trajectory positions and IMU attitude."""
    body_yaw = sign * interpolate_attitude(traj_ts + imu_dt, traj_xyz, imu_ts, imu_yaw) + theta0
    out: List[np.ndarray] = []
    for t_scan, pts in scans:
        if len(pts) == 0:
            continue
        i = int(np.argmin(np.abs(traj_ts - t_scan)))
        c, s = np.cos(body_yaw[i]), np.sin(body_yaw[i])
        R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        out.append(pts[:, :3] @ R.T + traj_xyz[i])
    return np.vstack(out) if out else np.zeros((0, 3))


def inject_near_field_sheet(
    scans: Sequence[Tuple[float, np.ndarray]],
    traj_ts: np.ndarray,
    traj_xyz: np.ndarray,
    body_yaw: np.ndarray,
    t_rel_window: Tuple[float, float],
    t0: float,
    azimuth_fraction: float = 0.88,
    bag_distance_m: float = 4.30,
    seed: int = 42,
) -> np.ndarray:
    """Synthesise the injected plastic-bag sheet in the world frame for the unprotected B0 layer.

    Mirrors ``inject_plastic_bag_near_field_occlusion``: a planar sheet at ``bag_distance_m`` covering
    ``azimuth_fraction`` of the field of view, i.e. the self-consistent near-field returns that a
    covariance-only detector cannot see and that B0 writes straight into its map.
    """
    rng = np.random.default_rng(seed)
    pts: List[np.ndarray] = []
    lo, hi = t_rel_window
    for t_scan, _ in scans:
        rel = t_scan - t0
        if not (lo <= rel <= hi):
            continue
        i = int(np.argmin(np.abs(traj_ts - t_scan)))
        n = 900
        az = rng.uniform(-np.pi, -np.pi + 2.0 * np.pi * azimuth_fraction, n)
        el = rng.uniform(-0.26, 0.26, n)
        d = bag_distance_m + rng.normal(0.0, 0.035, n)
        local = np.column_stack(
            [d * np.cos(el) * np.cos(az), d * np.cos(el) * np.sin(az), d * np.sin(el)]
        )
        c, s = np.cos(body_yaw[i]), np.sin(body_yaw[i])
        R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        pts.append(local @ R.T + traj_xyz[i] + np.array([0.0, 0.0, 1.05]))
    return np.vstack(pts) if pts else np.zeros((0, 3))


def min_distance_to_cells(query: np.ndarray, reference: np.ndarray, block: int = 1024) -> np.ndarray:
    """Nearest-neighbour distance from each query cell to a reference cell set (pure NumPy, chunked).

    Used to keep only the ghost voxels that actually moved away from the trusted map, so the
    contamination overlay does not double-draw the walls that were reconstructed correctly.
    """
    if len(query) == 0 or len(reference) == 0:
        return np.full(len(query), np.inf)
    ref = reference.astype(np.float32)
    out = np.empty(len(query), dtype=np.float64)
    for start in range(0, len(query), block):
        chunk = query[start : start + block].astype(np.float32)
        d2 = (
            (chunk[:, None, 0] - ref[None, :, 0]) ** 2
            + (chunk[:, None, 1] - ref[None, :, 1]) ** 2
            + (chunk[:, None, 2] - ref[None, :, 2]) ** 2
        )
        out[start : start + block] = np.sqrt(d2.min(axis=1))
    return out


def slice_scans(
    scans: Sequence[Tuple[float, np.ndarray]], t0: float, lo: float, hi: float
) -> List[Tuple[float, np.ndarray]]:
    """Keep only the scans whose sequence-relative timestamp lies in ``[lo, hi]``."""
    return [(t, p) for t, p in scans if lo <= (t - t0) <= hi]


def quantize_cells(points: np.ndarray, voxel: float, min_hits: int) -> np.ndarray:
    """Return occupied voxel centres having at least ``min_hits`` returns."""
    if len(points) == 0:
        return np.zeros((0, 3))
    coords = np.floor(points / voxel).astype(np.int64)
    uniq, counts = np.unique(coords, axis=0, return_counts=True)
    return (uniq[counts >= min_hits].astype(np.float64) + 0.5) * voxel


def build_exposed_voxel_surface_mesh(
    cells: np.ndarray, voxel: float
) -> Tuple[np.ndarray, np.ndarray]:
    """Build a surface-only triangle mesh: emit a quad only where a voxel face borders free space.

    This is the difference between a cloud of loose cubes and a closed architectural surface; it cuts
    the triangle count by roughly 4x and makes the hall read as walls in Isaac Sim.
    """
    if len(cells) == 0:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)

    keys = np.floor(cells / voxel).astype(np.int64)
    occupied = {tuple(k) for k in keys}

    h = 0.5 * voxel
    # (neighbour offset, 4 corner offsets in CCW order seen from outside); 2 triangles per quad.
    face_table = [
        # (neighbour offset, 4 corner offsets)
        ((-1, 0, 0), [(-h, -h, -h), (-h, h, -h), (-h, h, h), (-h, -h, h)]),
        ((1, 0, 0), [(h, -h, -h), (h, -h, h), (h, h, h), (h, h, -h)]),
        ((0, -1, 0), [(-h, -h, -h), (-h, -h, h), (h, -h, h), (h, -h, -h)]),
        ((0, 1, 0), [(-h, h, -h), (h, h, -h), (h, h, h), (-h, h, h)]),
        ((0, 0, -1), [(-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h)]),
        ((0, 0, 1), [(-h, -h, h), (-h, h, h), (h, h, h), (h, -h, h)]),
    ]

    verts: List[Tuple[float, float, float]] = []
    tris: List[Tuple[int, int, int]] = []
    index_of: Dict[Tuple[float, float, float], int] = {}

    def vertex_index(p: Tuple[float, float, float]) -> int:
        idx = index_of.get(p)
        if idx is None:
            idx = len(verts)
            index_of[p] = idx
            verts.append(p)
        return idx

    for cx, cy, cz in keys:
        base = (cx * voxel, cy * voxel, cz * voxel)
        for (dx, dy, dz), corners in face_table:
            if (cx + dx, cy + dy, cz + dz) in occupied:
                continue
            quad = []
            for ox, oy, oz in corners:
                p = (
                    round(base[0] + ox, 4),
                    round(base[1] + oy, 4),
                    round(base[2] + oz, 4),
                )
                quad.append(vertex_index(p))
            tris.append((quad[0], quad[1], quad[2]))
            tris.append((quad[0], quad[2], quad[3]))

    return (
        np.asarray(verts, dtype=np.float64).reshape(-1, 3),
        np.asarray(tris, dtype=np.int64).reshape(-1, 3),
    )


# --------------------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------------------
def _fmt_vec3(arr: np.ndarray) -> str:
    if len(arr) == 0:
        return "[]"
    return "[" + ", ".join(f"({v[0]:.3f}, {v[1]:.3f}, {v[2]:.3f})" for v in arr) + "]"


def _fmt_int(arr: np.ndarray) -> str:
    if len(arr) == 0:
        return "[]"
    return "[" + ", ".join(str(int(x)) for x in arr.reshape(-1)) + "]"


_MATERIALS = {
    "Mat_Floor": ((0.82, 0.84, 0.86), 0.70, 1.0),
    "Mat_Trusted_Wall": ((0.32, 0.68, 0.86), 0.42, 1.0),
    "Mat_B0_Polluted": ((0.92, 0.28, 0.22), 0.40, 0.55),
    "Mat_B2_Drift": ((0.93, 0.68, 0.16), 0.45, 0.60),
    "Mat_GT": ((0.12, 0.13, 0.15), 0.35, 1.0),
    "Mat_Commit": ((0.10, 0.62, 0.78), 0.30, 1.0),
    "Mat_Checkpoint": ((0.14, 0.71, 0.42), 0.30, 1.0),
}


def _material_block(name: str) -> str:
    color, rough, opacity = _MATERIALS[name]
    opacity_attrs = ""
    if opacity < 1.0:
        opacity_attrs = f"""
                float inputs:opacity = {opacity:.3f}
                float inputs:opacityThreshold = 0.01
                bool inputs:enableOpacity = 1"""
    return f"""
        def Material "{name}"
        {{
            token outputs:surface.connect = </World/Looks/{name}/Shader.outputs:surface>
            def Shader "Shader"
            {{
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = ({color[0]:.3f}, {color[1]:.3f}, {color[2]:.3f})
                float inputs:metallic = 0.0
                float inputs:roughness = {rough:.3f}{opacity_attrs}
                token outputs:surface
            }}
        }}"""


def _mesh_block(
    name: str, material: str, verts: np.ndarray, tris: np.ndarray, collider: bool = False
) -> str:
    if len(tris) == 0:
        return f"""
        def Xform "{name}"
        {{
        }}"""
    api = (
        '\n        (\n            prepend apiSchemas = ["PhysicsCollisionAPI", "PhysicsMeshCollisionAPI"]\n            bool physics:collisionEnabled = 1\n        )'
        if collider
        else ""
    )
    counts = "[" + ", ".join("3" for _ in range(len(tris))) + "]"
    return f"""
        def Mesh "{name}"{api}
        {{
            int[] faceVertexCounts = {counts}
            int[] faceVertexIndices = {_fmt_int(tris)}
            rel material:binding = </World/Looks/{material}>
            point3f[] points = {_fmt_vec3(verts)}
            uniform token subdivisionScheme = "none"
        }}"""


def _curve_block(name: str, material: str, xyz: np.ndarray, width: float) -> str:
    if len(xyz) < 2:
        return f"""
        def Xform "{name}"
        {{
        }}"""
    sub = xyz[::2]
    return f"""
        def BasisCurves "{name}"
        {{
            int[] curveVertexCounts = [{len(sub)}]
            rel material:binding = </World/Looks/{material}>
            point3f[] points = {_fmt_vec3(sub)}
            uniform token type = "linear"
            float[] widths = [{width:.3f}] (
                interpolation = "constant"
            )
        }}"""


def _robot_block(name: str, material: str, ts: np.ndarray, xyz: np.ndarray, yaw: np.ndarray, z: float) -> str:
    trans, orient = [], []
    for frame in range(0, 351, 2):
        i = int(np.argmin(np.abs(ts - (ts[0] + frame))))
        p, y = xyz[i], yaw[i]
        trans.append(f"                {frame}: ({p[0]:.3f}, {p[1]:.3f}, {p[2] + z:.3f})")
        orient.append(f"                {frame}: ({np.cos(0.5 * y):.5f}, 0, 0, {np.sin(0.5 * y):.5f})")
    return f"""
        def Xform "{name}"
        {{
            quatf xformOp:orient.timeSamples = {{
{chr(10).join(orient)}
            }}
            double3 xformOp:translate.timeSamples = {{
{chr(10).join(trans)}
            }}
            uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:orient"]

            def Cube "Chassis"
            {{
                rel material:binding = </World/Looks/{material}>
                double size = 1.0
                double3 xformOp:scale = (0.70, 0.48, 0.26)
                uniform token[] xformOpOrder = ["xformOp:scale"]
            }}
            def Cylinder "VLP32C"
            {{
                rel material:binding = </World/Looks/{material}>
                double height = 0.20
                double radius = 0.13
                double3 xformOp:translate = (0.14, 0.0, 0.23)
                uniform token[] xformOpOrder = ["xformOp:translate"]
            }}
        }}"""


def write_usda(
    path: Path,
    layers: Dict[str, Tuple[np.ndarray, np.ndarray]],
    paths_dict: Dict[str, Tuple[np.ndarray, np.ndarray]],
    yaw_by_path: Dict[str, np.ndarray],
    provenance: Dict[str, object],
) -> None:
    ts_gt, xyz_gt = paths_dict["/gt/path"]
    ts_b0, xyz_b0 = paths_dict["/degraded/fast_lio2_b0_path"]
    ts_b2, xyz_b2 = paths_dict["/degraded/mmlins_b2_pgo_path"]
    ts_b6, xyz_b6 = paths_dict["/repaired/fast_lio2_b6_path"]
    t0 = float(ts_gt[0])
    p_ckpt = xyz_gt[int(np.argmin(np.abs(ts_gt - (t0 + 118.0))))]
    p_commit = xyz_gt[int(np.argmin(np.abs(ts_gt - (t0 + 140.4))))]

    looks = "".join(_material_block(m) for m in _MATERIALS)

    def mesh(key: str, name: str, mat: str, collider: bool = False) -> str:
        verts, tris = layers[key]
        return _mesh_block(name, mat, verts, tris, collider=collider)

    body = f"""#usda 1.0
(
    defaultPrim = "World"
    endTimeCode = 350
    metersPerUnit = 1
    startTimeCode = 0
    timeCodesPerSecond = 20
    upAxis = "Z"
    customLayerData = {{
        string slamRecovery:sourceBag = "{provenance['source_bag']}"
        string slamRecovery:sourceMcap = "{provenance['source_mcap']}"
        string slamRecovery:attitudeSource = "{provenance['attitude_source']}"
        double slamRecovery:theta0Deg = {provenance['theta0_deg']}
        double slamRecovery:imuTimeOffsetSec = {provenance['imu_dt']}
        string slamRecovery:trustedVoxelSize = "{TRUSTED_VOXEL}"
        string slamRecovery:numScans = "{provenance['num_scans']}"
    }}
)

def Xform "World"
{{
    def PhysicsScene "PhysicsScene"
    {{
        vector3f physics:gravityDirection = (0, 0, -1)
        float physics:gravityMagnitude = 9.81
    }}

    def Scope "Looks"
    {{{looks}
    }}

    def Xform "Lights"
    {{
        def DomeLight "Sky"
        {{
            float inputs:intensity = 850
        }}
        def DistantLight "Sun"
        {{
            float inputs:angle = 1.2
            float inputs:intensity = 1700
            float3 xformOp:rotateXYZ = (-42, 28, 0)
            uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]
        }}
    }}

    def Xform "Hall01_Trusted_Environment"
    {{
        def Scope "Colliders"
        {{
{mesh("trusted_floor", "Floor", "Mat_Floor", collider=True)}
{mesh("trusted_wall", "Walls_And_Pillars", "Mat_Trusted_Wall", collider=True)}
        }}
    }}

    def Xform "Contamination_Overlay"
    {{
        def Scope "B0_Unprotected"
        {{
{mesh("b0_floor_ghost", "Floor_Ghost", "Mat_B0_Polluted")}
{mesh("b0_wall_ghost", "Wall_Ghost_And_Occluder", "Mat_B0_Polluted")}
        }}
        def Scope "B2_MMLINS_Tail"
        {{
{mesh("b2_wall_ghost", "Wall_Ghost_TailDrift", "Mat_B2_Drift")}
        }}
    }}

    def Xform "Trajectories"
    {{
{_curve_block("Path_Leica_GT", "Mat_GT", xyz_gt, 0.10)}
{_curve_block("Path_FASTLIO2_B0", "Mat_B0_Polluted", xyz_b0, 0.14)}
{_curve_block("Path_MMLINS_B2", "Mat_B2_Drift", xyz_b2, 0.12)}
{_curve_block("Path_Ours_B6", "Mat_Checkpoint", xyz_b6, 0.18)}
    }}

    def Xform "Gate_Beacons"
    {{
        def Sphere "Checkpoint_tq_start_118s"
        {{
            rel material:binding = </World/Looks/Mat_Checkpoint>
            double radius = 0.55
            double3 xformOp:translate = ({p_ckpt[0]:.3f}, {p_ckpt[1]:.3f}, {p_ckpt[2] + 0.85:.3f})
            uniform token[] xformOpOrder = ["xformOp:translate"]
        }}
        def Sphere "Mode2_Commit_t140s"
        {{
            rel material:binding = </World/Looks/Mat_Commit>
            double radius = 0.55
            double3 xformOp:translate = ({p_commit[0]:.3f}, {p_commit[1]:.3f}, {p_commit[2] + 0.85:.3f})
            uniform token[] xformOpOrder = ["xformOp:translate"]
        }}
    }}

    def Xform "Animated_Robots"
    {{
{_robot_block("Robot_Leica_GT", "Mat_GT", ts_gt, xyz_gt, yaw_by_path["/gt/path"], 0.20)}
{_robot_block("Robot_B0_Degraded", "Mat_B0_Polluted", ts_b0, xyz_b0, yaw_by_path["/degraded/fast_lio2_b0_path"], 0.22)}
{_robot_block("Robot_B2_MMLINS", "Mat_B2_Drift", ts_b2, xyz_b2, yaw_by_path["/degraded/mmlins_b2_pgo_path"], 0.24)}
{_robot_block("Robot_B6_Ours", "Mat_Checkpoint", ts_b6, xyz_b6, yaw_by_path["/repaired/fast_lio2_b6_path"], 0.26)}
    }}
}}
"""
    path.write_text(body, encoding="utf-8")


def write_obj(path: Path, mtl_path: Path, groups: Sequence[Tuple[str, str, np.ndarray, np.ndarray]]) -> None:
    lines = ["# M2DGR hall_01 reconstruction for NVIDIA Isaac Sim 5.1", f"mtllib {mtl_path.name}", ""]
    offset = 1
    for name, mat, verts, tris in groups:
        if len(verts) == 0:
            continue
        lines.append(f"g {name}")
        lines.append(f"usemtl {mat}")
        lines.extend(f"v {v[0]:.3f} {v[1]:.3f} {v[2]:.3f}" for v in verts)
        lines.extend(f"f {t[0] + offset} {t[1] + offset} {t[2] + offset}" for t in tris)
        offset += len(verts)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_mtl(path: Path) -> None:
    chunks = []
    for name, (color, rough, opacity) in _MATERIALS.items():
        chunk = [f"newmtl {name}", f"Kd {color[0]:.3f} {color[1]:.3f} {color[2]:.3f}", f"Ns {max(1.0, (1.0 - rough) * 100):.1f}"]
        if opacity < 1.0:
            chunk.append(f"d {opacity:.3f}")
        chunks.append("\n".join(chunk))
    path.write_text("\n\n".join(chunks) + "\n", encoding="utf-8")


def write_ply(path: Path, points: np.ndarray, rgb: np.ndarray) -> None:
    header = [
        "ply",
        "format ascii 1.0",
        f"element vertex {len(points)}",
        "property float x",
        "property float y",
        "property float z",
        "property uchar red",
        "property uchar green",
        "property uchar blue",
        "end_header",
    ]
    body = [
        f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f} {int(c[0])} {int(c[1])} {int(c[2])}"
        for p, c in zip(points, rgb)
    ]
    path.write_text("\n".join(header + body), encoding="utf-8")


# --------------------------------------------------------------------------------------
# Preview
# --------------------------------------------------------------------------------------
def render_preview(
    path: Path,
    layers: Dict[str, Tuple[np.ndarray, np.ndarray]],
    trusted_wall_cells: np.ndarray,
    b0_cells: np.ndarray,
    paths_dict: Dict[str, Tuple[np.ndarray, np.ndarray]],
    stats: Dict[str, object],
) -> None:
    """Render the *exported surface mesh* itself, not the raw point cloud."""
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    ts_gt, xyz_gt = paths_dict["/gt/path"]
    _, xyz_b0 = paths_dict["/degraded/fast_lio2_b0_path"]
    _, xyz_b2 = paths_dict["/degraded/mmlins_b2_pgo_path"]
    _, xyz_b6 = paths_dict["/repaired/fast_lio2_b6_path"]
    t0 = float(ts_gt[0])
    i_ckpt = int(np.argmin(np.abs(ts_gt - (t0 + 118.0))))
    i_commit = int(np.argmin(np.abs(ts_gt - (t0 + 140.4))))

    def poly(verts: np.ndarray, tris: np.ndarray, stride: int, color: str, alpha: float, shade: float = 0.0):
        if len(tris) == 0:
            return None
        sel = tris[::stride]
        faces = verts[sel]
        # cheap directional shading so the surface reads as solid geometry
        n = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
        n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        lam = np.clip(n @ np.array([0.35, -0.45, 0.82]), 0.0, 1.0)
        base = np.array(matplotlib.colors.to_rgb(color))
        rgb = base[None, :] * (1.0 - shade + shade * lam[:, None])
        pc = Poly3DCollection(faces, facecolors=np.clip(rgb, 0, 1), edgecolors="none")
        pc.set_alpha(alpha)
        return pc

    plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 10})
    fig = plt.figure(figsize=(15.0, 6.6), facecolor="#F4F5F7")
    fig.suptitle(
        "hall_01 → Isaac Sim 5.1: exported collider mesh & contamination overlay",
        fontsize=14.5, fontweight="bold", color="#171717", y=0.975,
    )

    t0_rel = ts_gt[0]

    # (a) trusted collider mesh, coloured by wall height
    ax1 = fig.add_subplot(1, 2, 1, facecolor="#FFFFFF")
    sc = ax1.scatter(
        trusted_wall_cells[:, 0],
        trusted_wall_cells[:, 1],
        c=trusted_wall_cells[:, 2],
        cmap="viridis",
        s=2.4,
        linewidths=0,
        vmin=0.0,
        vmax=2.4,
        alpha=0.9,
        label="Trusted walls (B6)",
    )
    cb = fig.colorbar(sc, ax=ax1, fraction=0.045, pad=0.02)
    cb.set_label("wall voxel height (m)", fontsize=8.5)
    ax1.plot(xyz_gt[:, 0], xyz_gt[:, 1], "--", color="#171717", lw=1.5, label="Leica GT")
    ax1.plot(xyz_b6[:, 0], xyz_b6[:, 1], "-", color="#1E824C", lw=2.2, label="B6 Ours (0.31 m)")
    ax1.scatter([xyz_gt[i_ckpt, 0]], [xyz_gt[i_ckpt, 1]], s=130, c="#B4D9BE",
                edgecolors="#171717", lw=1.5, zorder=9, label="Checkpoint t=118.0 s")
    ax1.scatter([xyz_gt[i_commit, 0]], [xyz_gt[i_commit, 1]], s=130, c="#67C5E4",
                edgecolors="#171717", lw=1.5, zorder=9, label="Commit t=140.4 s")
    ax1.set_aspect("equal", adjustable="datalim")
    ax1.grid(True, ls="--", alpha=0.45)
    ax1.set_xlabel("World X (m)", fontweight="bold")
    ax1.set_ylabel("World Y (m)", fontweight="bold")
    ax1.set_title(
        f"(a) Trusted collider mesh — {stats['trusted_wall_cells']} wall voxels",
        fontsize=10.5, fontweight="bold",
    )
    ax1.legend(loc="upper left", fontsize=7.4, framealpha=0.95)

    # (b) contamination overlay vs. trusted map
    ax2 = fig.add_subplot(1, 2, 2, facecolor="#FFFFFF")
    ax2.scatter(trusted_wall_cells[:, 0], trusted_wall_cells[:, 1], s=1.8, c="#9FB3BF",
                linewidths=0, alpha=0.45, label="Trusted walls (B6)")
    if len(b0_cells):
        ax2.scatter(b0_cells[:, 0], b0_cells[:, 1], s=7.0, c="#E04F3E",
                    edgecolors="#8C2B1E", lw=0.3, alpha=0.85,
                    label=f"B0 ghost surfaces ({stats['b0_ghost_cells']})")
    b2_cells_plot = layers["b2_wall_ghost"]
    ax2.plot(xyz_gt[:, 0], xyz_gt[:, 1], "--", color="#171717", lw=1.6, label="Leica GT trajectory")
    ax2.plot(xyz_b0[:, 0], xyz_b0[:, 1], "-", color="#D64535", lw=1.5, label="B0 degraded (7.28 m)")
    ax2.plot(xyz_b2[:, 0], xyz_b2[:, 1], "-.", color="#B86B19", lw=1.2, label="B2 MM-LINS (5.96 m)")
    ax2.plot(xyz_b6[:, 0], xyz_b6[:, 1], "-", color="#1E824C", lw=2.0, label="B6 ours repaired (0.31 m)")
    ax2.set_aspect("equal", adjustable="datalim")
    ax2.grid(True, ls="--", alpha=0.45)
    ax2.set_xlabel("World X (m)", fontweight="bold")
    ax2.set_ylabel("World Y (m)", fontweight="bold")
    ax2.set_title(
        f"(b) Contamination overlay [117–146 s] — {stats['b0_ghost_cells']} B0 / {stats['b2_ghost_cells']} B2 ghost voxels",
        fontsize=10.5, fontweight="bold",
    )
    leg2 = ax2.legend(loc="upper left", fontsize=7.2, framealpha=0.95)
    leg2.get_frame().set_edgecolor("#171717")

    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.925])
    fig.savefig(path, dpi=200)
    plt.close(fig)


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sign, theta0, imu_dt = load_calibration(OUT_DIR)
    print(f"[calib] sign={sign:+.0f} theta0={np.rad2deg(theta0):.2f} deg imu_dt={imu_dt:+.2f} s")

    print("[mcap] loading trajectories ...")
    paths_dict = extract_mcap_paths(MCAP_PBAG)
    ts_gt, xyz_gt = paths_dict["/gt/path"]
    t0 = float(ts_gt[0])

    print("[bag] loading scans + IMU attitude ...")
    scans, imu_ts, imu_yaw = extract_scans_and_imu_from_bag(BAG_PATH, scan_stride=30)
    print(f"[bag] {len(scans)} VLP-32C keyframes, {len(imu_ts)} IMU attitude samples")

    print("[geom] registering scans on each trajectory ...")
    pts_trusted = register_scan_stream(scans, *paths_dict["/repaired/fast_lio2_b6_path"], imu_ts, imu_yaw, sign, theta0, imu_dt)

    # Contamination layers are restricted to the interval that is actually quarantined and committed
    # ([117, 146] s covers t_q_start = 118.0 s .. the 140.4 s Mode-2 commit). Outside it every host
    # agrees with the trusted map, so drawing ghosts there would only add visual noise.
    scans_window = slice_scans(scans, t0, 117.0, 146.0)
    pts_b0_win = register_scan_stream(scans_window, *paths_dict["/degraded/fast_lio2_b0_path"], imu_ts, imu_yaw, sign, theta0, imu_dt)
    pts_b2_win = register_scan_stream(scans_window, *paths_dict["/degraded/mmlins_b2_pgo_path"], imu_ts, imu_yaw, sign, theta0, imu_dt)
    print(f"[geom] contamination window scans: {len(scans_window)}")

    body_yaw_b0 = sign * interpolate_attitude(paths_dict["/degraded/fast_lio2_b0_path"][0] + imu_dt,
                                              paths_dict["/degraded/fast_lio2_b0_path"][1], imu_ts, imu_yaw) + theta0
    bag_sheet = inject_near_field_sheet(
        scans,
        paths_dict["/degraded/fast_lio2_b0_path"][0],
        paths_dict["/degraded/fast_lio2_b0_path"][1],
        body_yaw_b0,
        (120.0, 140.0),
        t0,
    )
    print(f"[geom] injected occluder sheet points: {len(bag_sheet)}")

    def split(points: np.ndarray):
        floor = points[(points[:, 2] > FLOOR_Z_LO) & (points[:, 2] < FLOOR_Z_HI)]
        wall = points[(points[:, 2] > WALL_Z_LO) & (points[:, 2] < WALL_Z_HI)]
        return floor, wall

    t_floor, t_wall = split(pts_trusted)
    b0_floor, b0_wall = split(pts_b0_win)
    _, b2_wall = split(pts_b2_win)

    trusted_floor_cells = quantize_cells(t_floor, TRUSTED_VOXEL, min_hits=3)
    trusted_wall_cells = quantize_cells(t_wall, TRUSTED_VOXEL, min_hits=3)

    # Ghost layer: only the surfaces that moved > 1 voxel away from the trusted map.
    all_wall_ghost = np.vstack([b0_wall, bag_sheet[bag_sheet[:, 2] > -1.0]]) if len(bag_sheet) else b0_wall
    b0_cells = quantize_cells(all_wall_ghost, POLLUTED_VOXEL, min_hits=3)
    if len(b0_cells) and len(trusted_wall_cells):
        b0_cells = b0_cells[min_distance_to_cells(b0_cells, trusted_wall_cells) > 1.6 * POLLUTED_VOXEL]
    b2_cells = quantize_cells(b2_wall, POLLUTED_VOXEL, min_hits=3)
    if len(b2_cells) and len(trusted_wall_cells):
        b2_cells = b2_cells[min_distance_to_cells(b2_cells, trusted_wall_cells) > 1.6 * POLLUTED_VOXEL]

    b0_floor_cells = quantize_cells(b0_floor, POLLUTED_VOXEL, min_hits=4)

    print(f"[mesh] trusted: {len(trusted_wall_cells)} wall cells, {len(trusted_floor_cells)} floor cells")
    print(f"[mesh] ghosts : B0 {len(b0_cells)} wall + {len(b0_floor_cells)} floor, B2 {len(b2_cells)} wall")

    layers = {
        "trusted_floor": build_exposed_voxel_surface_mesh(trusted_floor_cells, TRUSTED_VOXEL),
        "trusted_wall": build_exposed_voxel_surface_mesh(trusted_wall_cells, TRUSTED_VOXEL),
        "b0_floor_ghost": build_exposed_voxel_surface_mesh(b0_floor_cells, POLLUTED_VOXEL),
        "b0_wall_ghost": build_exposed_voxel_surface_mesh(b0_cells, POLLUTED_VOXEL),
        "b2_wall_ghost": build_exposed_voxel_surface_mesh(b2_cells, POLLUTED_VOXEL),
    }
    tris_total = sum(len(t) for _, t in layers.values())
    print(f"[mesh] total triangles: {tris_total}")

    # Per-path attitude for animated robots: derive from trajectory tangent (orientation only,
    # cosmetic) — the *geometry* uses the calibrated IMU attitude.
    yaw_by_path = {
        topic: np.unwrap(np.interp(ts, imu_ts, np.unwrap(imu_yaw))) * sign + theta0
        for topic, (ts, _) in paths_dict.items()
    }

    provenance = {
        "source_bag": BAG_PATH.name,
        "source_mcap": MCAP_PBAG.name,
        "attitude_source": "IMU AHRS yaw (/handsfree/imu) + calibrated constant offset",
        "theta0_deg": round(float(np.rad2deg(theta0)), 3),
        "imu_dt": round(float(imu_dt), 3),
        "num_scans": len(scans),
    }

    print("[write] USD / OBJ / PLY ...")
    write_usda(OUT_DIR / "hall_01_isaac_scene.usda", layers, paths_dict, yaw_by_path, provenance)
    write_mtl(OUT_DIR / "hall_01_materials.mtl")
    write_obj(
        OUT_DIR / "hall_01_scene_geometry.obj",
        OUT_DIR / "hall_01_materials.mtl",
        [
            ("Trusted_Floor", "Mat_Floor", *layers["trusted_floor"]),
            ("Trusted_Walls_Pillars", "Mat_Trusted_Wall", *layers["trusted_wall"]),
            ("B0_Floor_Ghost", "Mat_B0_Polluted", *layers["b0_floor_ghost"]),
            ("B0_Wall_Ghost", "Mat_B0_Polluted", *layers["b0_wall_ghost"]),
            ("B2_Wall_Ghost", "Mat_B2_Drift", *layers["b2_wall_ghost"]),
        ],
    )

    pts = np.vstack([trusted_floor_cells, trusted_wall_cells, b0_cells, b2_cells])
    rgb = np.vstack(
        [
            np.tile([209, 213, 219], (len(trusted_floor_cells), 1)),
            np.tile([82, 173, 216], (len(trusted_wall_cells), 1)),
            np.tile([235, 77, 60], (len(b0_cells), 1)),
            np.tile([237, 173, 41], (len(b2_cells), 1)),
        ]
    )
    write_ply(OUT_DIR / "hall_01_pointcloud_colored.ply", pts, rgb)

    stats = {
        "trusted_wall_cells": len(trusted_wall_cells),
        "trusted_floor_cells": len(trusted_floor_cells),
        "b0_ghost_cells": len(b0_cells),
        "b2_ghost_cells": len(b2_cells),
        "triangles_total": int(tris_total),
        **provenance,
    }
    (OUT_DIR / "hall_01_export_manifest.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print("[preview] rendering ...")
    render_preview(
        OUT_DIR / "hall_01_isaac_3d_preview.png",
        layers,
        trusted_wall_cells,
        b0_cells,
        paths_dict,
        stats,
    )

    (OUT_DIR / "run_in_isaac_sim_5_1.py").write_text(
        '''"""Standalone loader for NVIDIA Isaac Sim 5.1.

    ./python.sh run_in_isaac_sim_5_1.py
or open `hall_01_isaac_scene.usda` directly from the Isaac Sim GUI (File -> Open).
Then press Play (Spacebar) to replay the 350 s timeline.
"""
from pathlib import Path

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": False, "width": 1920, "height": 1080})

import omni.timeline
import omni.usd

stage_path = (Path(__file__).resolve().parent / "hall_01_isaac_scene.usda").as_posix()
print(f"[Isaac Sim 5.1] opening {stage_path}")
omni.usd.get_context().open_stage(stage_path)

timeline = omni.timeline.get_timeline_interface()
timeline.set_start_time(0.0)
timeline.set_end_time(350.0 / 20.0)
timeline.play()

while simulation_app.is_running():
    simulation_app.update()

simulation_app.close()
''',
        encoding="utf-8",
    )

    (OUT_DIR / "README_ISAAC_SIM_5_1.md").write_text(
        f"""# M2DGR `hall_01` → NVIDIA Isaac Sim 5.1 场景包

由真实 `{BAG_PATH.name}`（VLP-32C 点云 + `/handsfree/imu` 姿态）与 `{MCAP_PBAG.name}`
（Leica MS60 真值、B0/B2 退化、B6 修复轨迹）离线生成，无 ROS 运行依赖。

## 姿态标定（关键）
`hall_01` 为手持序列，操作者会原地旋转与倒退，因此**轨迹切向不能当作机体姿态**。
本场景使用 `/handsfree/imu` 的 AHRS 偏航角 + 常量偏移 `θ₀ = {np.rad2deg(theta0):.2f}°`
（sign = {sign:+.0f}），按墙面锐度搜索得到：占用 25 cm 栅格从 16524 降到 10927（-33.9 %）。
原始与标定后的对比见 `hall_01_alignment_diagnosis.png`。

## 文件
| 文件 | 说明 |
|---|---|
| `hall_01_isaac_scene.usda` | Isaac Sim 5.1 原生 USD 场景（推荐，直接 `File → Open`） |
| `hall_01_scene_geometry.obj` + `.mtl` | 通用三角网格，可导入 Blender / MeshLab |
| `hall_01_pointcloud_colored.ply` | 分色点云（灰地板 / 蓝可信墙 / 红 B0 污染 / 黄 B2 拖尾） |
| `run_in_isaac_sim_5_1.py` | 一键加载并播放时间线 |
| `hall_01_export_manifest.json` | 体素数、三角形数、标定参数等出处记录 |

## USD 结构
- `/World/Hall01_Trusted_Environment/Colliders` — **带 `PhysicsCollisionAPI` 的地板与墙/柱**，可直接跑 Nav2/机器人
- `/World/Contamination_Overlay/B0_Unprotected` — 按 B0 漂移位姿注册的墙面 + 注入的近场遮挡面（半透明红）
- `/World/Contamination_Overlay/B2_MMLINS_Tail` — MM-LINS 确认延迟尾漂移（半透明黄）
- `/World/Trajectories` — Leica GT / B0 / B2 / B6 四条三维曲线
- `/World/Gate_Beacons` — `t=118.0 s` 检查点（绿）与 `t=140.4 s` Mode-2 原子提交（青）
- `/World/Animated_Robots` — 四台带 0–350 帧关键帧的机器人，按 Play 同步行驶

## 打开方式
- **GUI**：拷到装有 Isaac Sim 5.1 的机器 → `File → Open` → 选 `hall_01_isaac_scene.usda` → 按空格播放
- **命令行**：`/path/to/isaac-sim-5.1/python.sh run_in_isaac_sim_5_1.py`

## 出处声明
墙/地面几何来自真实 `hall_01` 扫描；B0/B2 图层用**同一批真实扫描**按各自退化位姿注册，
并按 `INJECTION` 协议补入 88 % 视场、4.30 m 的近场遮挡面，用于可视化地图污染，
不是新的实验结论。
""",
        encoding="utf-8",
    )

    print(f"\n[done] {OUT_DIR}")
    for f in sorted(OUT_DIR.iterdir()):
        if f.is_file():
            print(f"  {f.name:42s} {f.stat().st_size / 1024:10.1f} KB")


if __name__ == "__main__":
    main()
