#!/usr/bin/env python3
"""Export ORB-SLAM3's visual map to a Foxglove .mcap, replayed over the sequence duration.

Everything is emitted progressively along real time so the file can actually be played back:
the trajectories grow, the sparse map fills in as keyframes are created, and the dense map
fills in as the camera observes new space.

Topics
  /orbslam3/sparse_map_points   ORB-SLAM3 triangulated MapPoints (true visual landmarks),
                                each stamped with the keyframe that first created it
  /orbslam3/dense_map_points    Depth back-projection through ORB-SLAM3's estimated poses
  /orbslam3/trajectory          ORB-SLAM3 camera trajectory
  /gt/path                      Vicon Mocap ground truth

All four are rigidly aligned into the ground-truth frame with one SE(3) fitted on the trajectory.

Producing the sparse cloud needs a patched ORB-SLAM3: this build's `System::SaveMap()` is commented
out and the ROS wrapper publishes no map points, so `SaveMapPointsTUM()` was added to
`System.h`/`System.cc` (union of every atlas submap, each point stamped with its reference keyframe)
and `Examples/RGB-D/rgbd_tum.cc` writes it when `ORB_MAP_POINTS_OUT` is set. Runs without that
variable are unchanged. The dense cloud needs no patch, only the depth frames and this trajectory.
"""

from __future__ import annotations

import argparse
import os

import cv2
import numpy as np

from mcap_ros1.writer import Writer as Ros1McapWriter
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header

import sys

sys.path.insert(0, "/home/R26534/MM-LINS")
from slam_recovery.experiments.evaluation import (  # noqa: E402
    associate_trajectories,
    load_tum_trajectory_se3,
    quat_xyzw_to_rot,
    umeyama_se3_align,
)


def load_map_points(path: str):
    """Returns (times, xyz). Points without a timestamp get t = -1 and are shown from the start."""
    rows = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 4:
                rows.append([float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])])
            elif len(parts) == 3:
                rows.append([-1.0, float(parts[0]), float(parts[1]), float(parts[2])])
    if not rows:
        return np.zeros(0), np.zeros((0, 3))
    arr = np.asarray(rows, dtype=np.float64)
    return arr[:, 0], arr[:, 1:4]


def load_intrinsics(yaml_path: str) -> dict:
    vals: dict[str, float] = {}
    want = {
        "Camera1.fx": "fx", "Camera1.fy": "fy", "Camera1.cx": "cx",
        "Camera1.cy": "cy", "RGBD.DepthMapFactor": "factor",
    }
    with open(yaml_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            for key, short in want.items():
                if line.startswith(key + ":"):
                    vals[short] = float(line.split(":", 1)[1].strip().strip('"'))
    missing = {"fx", "fy", "cx", "cy", "factor"} - set(vals)
    if missing:
        raise ValueError(f"missing intrinsics {sorted(missing)} in {yaml_path}")
    return vals


def build_timed_dense_cloud(assoc_path, ts_est, xyz_est, quats_est, K,
                            frame_stride, pixel_stride, min_depth, max_depth, voxel):
    """Accumulate back-projected depth in time order, keeping one point per voxel."""
    fx, fy, cx, cy, factor = K["fx"], K["fy"], K["cx"], K["cy"], K["factor"]

    frames = []
    with open(assoc_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 4:
                frames.append((float(parts[0]), parts[3]))

    us = np.arange(0, 640, pixel_stride)
    vs = np.arange(0, 480, pixel_stride)
    uu, vv = np.meshgrid(us, vs)
    uu_i = uu.ravel().astype(int)
    vv_i = vv.ravel().astype(int)
    uuf = uu_i.astype(np.float64)
    vvf = vv_i.astype(np.float64)

    occupied: set = set()
    pts_out, t_out = [], []
    used = 0
    for fi in range(0, len(frames), frame_stride):
        ts, depth_path = frames[fi]
        if not os.path.exists(depth_path):
            continue
        i = int(np.argmin(np.abs(ts_est - ts)))
        if abs(ts_est[i] - ts) > 0.10:
            continue
        depth = cv2.imread(depth_path, cv2.IMREAD_UNCHANGED)
        if depth is None:
            continue
        d = depth[vv_i, uu_i].astype(np.float64) / factor
        valid = (d > min_depth) & (d < max_depth)
        if not np.any(valid):
            continue
        d = d[valid]
        p_cam = np.column_stack([
            (uuf[valid] - cx) / fx * d,
            (vvf[valid] - cy) / fy * d,
            d,
        ])
        R = quat_xyzw_to_rot(quats_est[i])
        p_world = p_cam @ R.T + xyz_est[i]

        keys = np.floor(p_world / voxel).astype(np.int64)
        keep = np.ones(len(p_world), dtype=bool)
        for j in range(len(keys)):
            k = (int(keys[j, 0]), int(keys[j, 1]), int(keys[j, 2]))
            if k in occupied:
                keep[j] = False
            else:
                occupied.add(k)
        if np.any(keep):
            pts_out.append(p_world[keep])
            t_out.append(np.full(int(keep.sum()), ts_est[i]))
        used += 1

    if not pts_out:
        return np.zeros(0), np.zeros((0, 3))
    print(f"    dense: {used} frames -> {sum(len(p) for p in pts_out)} unique-voxel points")
    return np.concatenate(t_out), np.vstack(pts_out)


def decimate(n: int, max_n: int) -> np.ndarray:
    if n <= max_n:
        return np.arange(n)
    return np.unique(np.linspace(0, n - 1, max_n).astype(int))


def make_pc2(pts: np.ndarray, stamp, frame_id: str = "map") -> PointCloud2:
    m = PointCloud2()
    m.header = Header(stamp=stamp, frame_id=frame_id)
    m.height = 1
    m.width = int(len(pts))
    m.fields = [
        PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
    ]
    m.is_bigendian = False
    m.point_step = 12
    m.row_step = 12 * m.width
    m.data = np.ascontiguousarray(pts, dtype="<f4").tobytes() if len(pts) else b""
    m.is_dense = True
    return m


def make_path_msg(ts_arr, xyz_arr, stamp) -> Path:
    p = Path()
    p.header = Header(stamp=stamp, frame_id="map")
    keep = decimate(len(ts_arr), 400)
    for i in keep:
        ps = PoseStamped()
        ps.header = Header(stamp=stamp, frame_id="map")
        ps.pose.position.x = float(xyz_arr[i, 0])
        ps.pose.position.y = float(xyz_arr[i, 1])
        ps.pose.position.z = float(xyz_arr[i, 2])
        ps.pose.orientation.w = 1.0
        p.poses.append(ps)
    return p


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--traj", required=True)
    ap.add_argument("--map-points", required=True)
    ap.add_argument("--assoc", required=True)
    ap.add_argument("--yaml", required=True)
    ap.add_argument("--gt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frame-stride", type=int, default=2)
    ap.add_argument("--pixel-stride", type=int, default=5)
    ap.add_argument("--dense-voxel-m", type=float, default=0.10)
    ap.add_argument("--dense-every-sec", type=float, default=2.0)
    ap.add_argument("--emit-hz", type=float, default=2.0)
    ap.add_argument("--min-depth", type=float, default=0.3)
    ap.add_argument("--max-depth", type=float, default=8.0)
    args = ap.parse_args()

    ts_orb, xyz_orb, q_orb = load_tum_trajectory_se3(args.traj)
    ts_gt, xyz_gt, _ = load_tum_trajectory_se3(args.gt)
    print(f"trajectory : {len(ts_orb)} poses, {ts_orb[-1]-ts_orb[0]:.1f} s")

    m_ts, m_e, m_g = associate_trajectories(ts_orb, xyz_orb, ts_gt, xyz_gt, 0.08)
    if len(m_e) < 5:
        raise SystemExit("not enough matched poses to align ORB-SLAM3 to GT")
    R, t, _ = umeyama_se3_align(m_e, m_g, with_scale=False)
    resid = float(np.sqrt(np.mean(np.sum((m_e @ R.T + t - m_g) ** 2, axis=1))))
    print(f"alignment  : {len(m_e)} matched poses, residual {resid:.4f} m")

    xyz_orb_al = xyz_orb @ R.T + t
    xyz_gt_al = xyz_gt

    sp_t, sp_xyz = load_map_points(args.map_points)
    sp_xyz_al = sp_xyz @ R.T + t if len(sp_xyz) else sp_xyz
    print(f"sparse map : {len(sp_xyz_al)} ORB map points")

    K = load_intrinsics(args.yaml)
    dn_t, dn_xyz = build_timed_dense_cloud(
        args.assoc, ts_orb, xyz_orb, q_orb, K,
        args.frame_stride, args.pixel_stride, args.min_depth, args.max_depth, args.dense_voxel_m)
    dn_xyz_al = dn_xyz @ R.T + t if len(dn_xyz) else dn_xyz

    # Reveal times: map points without a stamp fall back to the trajectory start.
    t_start = float(ts_gt[0])
    if len(sp_t):
        sp_t = np.where(sp_t < 0, t_start - 1.0, sp_t)
        order = np.argsort(sp_t)
        sp_t, sp_xyz_al = sp_t[order], sp_xyz_al[order]
    if len(dn_t):
        order = np.argsort(dn_t)
        dn_t, dn_xyz_al = dn_t[order], dn_xyz_al[order]

    t_end = float(min(ts_orb[-1], ts_gt[-1]))
    step = 1.0 / args.emit_hz
    ticks = np.arange(t_start, t_end + step, step)
    print(f"emitting   : {len(ticks)} frames over {t_end - t_start:.1f} s at {args.emit_hz:g} Hz")

    import rospy

    n_dense_msgs = 0
    with open(args.out, "wb") as fh, Ros1McapWriter(fh) as w:
        next_dense = t_start
        for now in ticks:
            stamp = rospy.Time.from_sec(float(now))
            log_ns = int(now * 1e9)

            gi = np.searchsorted(ts_gt, now)
            if gi >= 2:
                w.write_message("/gt/path", make_path_msg(ts_gt[:gi], xyz_gt_al[:gi], stamp),
                                log_time=log_ns, publish_time=log_ns)
            oi = np.searchsorted(ts_orb, now)
            if oi >= 2:
                w.write_message("/orbslam3/trajectory", make_path_msg(ts_orb[:oi], xyz_orb_al[:oi], stamp),
                                log_time=log_ns, publish_time=log_ns)
            if len(sp_t):
                si = np.searchsorted(sp_t, now, side="right")
                if si > 0:
                    w.write_message("/orbslam3/sparse_map_points", make_pc2(sp_xyz_al[:si], stamp),
                                    log_time=log_ns, publish_time=log_ns)
            if len(dn_t) and now >= next_dense:
                di = np.searchsorted(dn_t, now, side="right")
                if di > 0:
                    w.write_message("/orbslam3/dense_map_points", make_pc2(dn_xyz_al[:di], stamp),
                                    log_time=log_ns, publish_time=log_ns)
                    n_dense_msgs += 1
                next_dense = now + args.dense_every_sec

    print(f"wrote {args.out} ({os.path.getsize(args.out)/1e6:.1f} MB, {len(ticks)} ticks, {n_dense_msgs} dense msgs)")


if __name__ == "__main__":
    main()
