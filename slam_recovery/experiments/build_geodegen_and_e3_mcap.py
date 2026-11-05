"""Build hall_01_geodegen_comparison.mcap including LIO-SAM (1008m divergence -> 0.28m B6), MM-LINS (Issleeping=1, 7.37m -> 0.28m B6), and ORB-SLAM3 E3 trajectories."""

from __future__ import annotations

import os
import sys
import numpy as np
import rosbag
import rospy
from geometry_msgs.msg import Point, PoseStamped
from mcap_ros1.writer import Writer as Ros1McapWriter
from nav_msgs.msg import Path
from std_msgs.msg import ColorRGBA, Header
from visualization_msgs.msg import Marker, MarkerArray

sys.path.insert(0, "/home/R26534/MM-LINS")
from slam_recovery.experiments.evaluation import (
    associate_trajectories,
    load_tum_trajectory,
    umeyama_se3_align,
)

OUT_MCAP = "/home/R26534/MM-LINS/slam_recovery/experiments/hall_01_geodegen_comparison.mcap"


def read_odom(bag_path: str, topic: str):
    ts, xyz = [], []
    with rosbag.Bag(bag_path, "r") as b:
        for _, m, _ in b.read_messages(topics=[topic]):
            ts.append(m.header.stamp.to_sec())
            p = m.pose.pose.position
            xyz.append([p.x, p.y, p.z])
    return np.asarray(ts, dtype=np.float64), np.asarray(xyz, dtype=np.float64)


def align_to_gt_pre_quarantine(
    ts_est: np.ndarray,
    xyz_est: np.ndarray,
    ts_gt: np.ndarray,
    xyz_gt: np.ndarray,
    t0: float,
    clip_radius: float = 80.0,
) -> np.ndarray:
    ts_m, est_m, gt_m = associate_trajectories(ts_est, xyz_est, ts_gt, xyz_gt, max_diff_sec=0.1)
    pre = (ts_m - t0) < 118.0
    R, t, s = umeyama_se3_align(est_m[pre], gt_m[pre], with_scale=False)
    aligned = (s * (xyz_est @ R.T)) + t
    # Optional soft clip at 80m so 1000m+ LIO-SAM explosion doesn't shrink the Foxglove 3D viewport to a dot
    norms = np.linalg.norm(aligned, axis=1)
    far = norms > clip_radius
    if np.any(far):
        aligned[far] = aligned[far] * (clip_radius / norms[far, None])
    return aligned


def make_path_msg(ts_arr: np.ndarray, xyz_arr: np.ndarray, up_to_t: float, frame_id: str = "map") -> Path:
    path = Path()
    path.header = Header(stamp=rospy.Time.from_sec(up_to_t), frame_id=frame_id)
    idxs = np.flatnonzero(ts_arr <= up_to_t)
    if len(idxs) > 700:
        idxs = idxs[:: max(1, len(idxs) // 700)]
    for i in idxs:
        ps = PoseStamped()
        ps.header = Header(stamp=rospy.Time.from_sec(float(ts_arr[i])), frame_id=frame_id)
        ps.pose.position.x = float(xyz_arr[i, 0])
        ps.pose.position.y = float(xyz_arr[i, 1])
        ps.pose.position.z = float(xyz_arr[i, 2])
        ps.pose.orientation.w = 1.0
        path.poses.append(ps)
    return path


def make_markers(stamp_t: float, gt_ts: np.ndarray, gt_xyz: np.ndarray, t0: float) -> MarkerArray:
    ma = MarkerArray()
    hdr = Header(stamp=rospy.Time.from_sec(stamp_t), frame_id="map")

    ckpt_idx = int(np.argmin(np.abs(gt_ts - (t0 + 118.0))))
    ckpt_pos = gt_xyz[ckpt_idx]

    m_ckpt = Marker()
    m_ckpt.header = hdr
    m_ckpt.ns = "geodegen_events"
    m_ckpt.id = 1
    m_ckpt.type = Marker.SPHERE
    m_ckpt.action = Marker.ADD
    m_ckpt.pose.position.x = float(ckpt_pos[0])
    m_ckpt.pose.position.y = float(ckpt_pos[1])
    m_ckpt.pose.position.z = float(ckpt_pos[2])
    m_ckpt.pose.orientation.w = 1.0
    m_ckpt.scale.x = m_ckpt.scale.y = m_ckpt.scale.z = 1.2
    m_ckpt.color = ColorRGBA(0.0, 1.0, 0.3, 0.9)
    ma.markers.append(m_ckpt)

    m_zone = Marker()
    m_zone.header = hdr
    m_zone.ns = "geodegen_events"
    m_zone.id = 2
    m_zone.type = Marker.LINE_STRIP
    m_zone.action = Marker.ADD
    m_zone.pose.orientation.w = 1.0
    m_zone.scale.x = 0.45
    m_zone.color = ColorRGBA(1.0, 0.4, 0.0, 0.85)
    zone_mask = ((gt_ts - t0) >= 120.0) & ((gt_ts - t0) <= 140.0)
    for pt in gt_xyz[zone_mask]:
        m_zone.points.append(Point(float(pt[0]), float(pt[1]), float(pt[2])))
    ma.markers.append(m_zone)

    m_board = Marker()
    m_board.header = hdr
    m_board.ns = "geodegen_events"
    m_board.id = 3
    m_board.type = Marker.TEXT_VIEW_FACING
    m_board.action = Marker.ADD
    m_board.pose.position.x = float(gt_xyz[0, 0])
    m_board.pose.position.y = float(gt_xyz[0, 1])
    m_board.pose.position.z = float(gt_xyz[0, 2] + 4.5)
    m_board.pose.orientation.w = 1.0
    m_board.scale.z = 0.72
    m_board.color = ColorRGBA(0.4, 0.95, 1.0, 1.0)
    m_board.text = (
        "hall_01 Directional GEO_DEGEN & E3 ORB-SLAM3 [120-140s]\n"
        "LIO-SAM B0: 1008.65m (clipped@80m) -> +Ours B6: 0.2788m (G=100%)\n"
        "MM-LINS B2 (Issleeping=1): 7.3747m -> +Ours B6: 0.2836m (G=100%)\n"
        "ORB-SLAM3 Severe Low-Light: Atlas B2=2.1822m (Win 6.89m) -> +Ours B6=0.9066m (Win 0.74m)"
    )
    ma.markers.append(m_board)
    return ma


def main() -> None:
    ts_gt, xyz_gt = load_tum_trajectory("/home/R26534/M2DGR/GT/hall_01.txt")
    t0 = float(ts_gt[0])
    origin_offset = xyz_gt[0].copy()
    xyz_gt_c = xyz_gt - origin_offset

    ts_lio_deg, xyz_lio_deg = read_odom("/tmp/liosam_geodegen_deg.bag", "/lio_sam/mapping/odometry")
    ts_fl_deg, xyz_fl_deg = read_odom("/tmp/mmlins_geodegen_deg.bag", "/Odometry")
    ts_mm_deg, xyz_mm_deg = read_odom("/tmp/mmlins_geodegen_deg.bag", "/aft_pgo_odom")

    ts_lio_rep, xyz_lio_rep = read_odom("/tmp/liosam_geodegen_rep.bag", "/lio_sam/mapping/odometry")
    ts_fl_rep, xyz_fl_rep = read_odom("/tmp/mmlins_geodegen_rep.bag", "/Odometry")

    # Also load E3 ORB-SLAM3 severe low-light trajectories (B2 Atlas vs B6 Ours)
    e3_dir = "/home/R26534/MM-LINS/slam_recovery/experiments/e3_orbslam3/trajectories"
    ts_orb_b2, xyz_orb_b2 = load_tum_trajectory(os.path.join(e3_dir, "sev_g005_CameraTrajectory_b2_atlas.txt"))
    ts_orb_b6, xyz_orb_b6 = load_tum_trajectory(os.path.join(e3_dir, "severe_gain_0.05_CameraTrajectory_b6_ours.txt"))

    al_lio_deg = align_to_gt_pre_quarantine(ts_lio_deg, xyz_lio_deg, ts_gt, xyz_gt_c, t0)
    al_fl_deg = align_to_gt_pre_quarantine(ts_fl_deg, xyz_fl_deg, ts_gt, xyz_gt_c, t0)
    al_mm_deg = align_to_gt_pre_quarantine(ts_mm_deg, xyz_mm_deg, ts_gt, xyz_gt_c, t0)
    al_lio_b6 = align_to_gt_pre_quarantine(ts_lio_rep, xyz_lio_rep, ts_gt, xyz_gt_c, t0)
    al_fl_b6 = align_to_gt_pre_quarantine(ts_fl_rep, xyz_fl_rep, ts_gt, xyz_gt_c, t0)
    al_orb_b2 = align_to_gt_pre_quarantine(ts_orb_b2, xyz_orb_b2, ts_gt, xyz_gt_c, t0)
    al_orb_b6 = align_to_gt_pre_quarantine(ts_orb_b6, xyz_orb_b6, ts_gt, xyz_gt_c, t0)

    with open(OUT_MCAP, "wb") as f:
        writer = Ros1McapWriter(output=f)
        for t_cur in np.arange(t0 + 1.0, float(ts_gt[-1]), 1.0):
            t_ns = int(t_cur * 1e9)
            writer.write_message("/gt/path", make_path_msg(ts_gt, xyz_gt_c, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/geodegen/lio_sam_b0_1008m_path", make_path_msg(ts_lio_deg, al_lio_deg, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/geodegen/fast_lio2_b0_path", make_path_msg(ts_fl_deg, al_fl_deg, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/geodegen/mmlins_b2_sleep1_path", make_path_msg(ts_mm_deg, al_mm_deg, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/repaired/lio_sam_b6_path", make_path_msg(ts_lio_rep, al_lio_b6, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/repaired/fast_lio2_b6_path", make_path_msg(ts_fl_rep, al_fl_b6, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/e3_orbslam3/b2_native_atlas_path", make_path_msg(ts_orb_b2, al_orb_b2, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/e3_orbslam3/b6_ours_repaired_path", make_path_msg(ts_orb_b6, al_orb_b6, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/quarantine/markers", make_markers(t_cur, ts_gt, xyz_gt_c, t0), log_time=t_ns, publish_time=t_ns)
        writer.finish()

    print(f"Generated {OUT_MCAP} ({os.path.getsize(OUT_MCAP) / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    main()
