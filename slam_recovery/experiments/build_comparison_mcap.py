"""Build a unified Foxglove .mcap comparison file for hall_01 plastic-bag occlusion & recovery."""

from __future__ import annotations

import os
import sys
import numpy as np
import rosbag
import rospy
from geometry_msgs.msg import Point, PoseStamped
from mcap_ros1.writer import Writer as Ros1McapWriter
from nav_msgs.msg import Path
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import ColorRGBA, Header
from visualization_msgs.msg import Marker, MarkerArray

sys.path.insert(0, "/home/R26534/MM-LINS")
from slam_recovery.experiments.evaluation import (
    associate_trajectories,
    load_tum_trajectory,
    umeyama_se3_align,
)
from slam_recovery.repair import repair_quarantined_trajectory_segment

OUT_MCAP = "/home/R26534/MM-LINS/slam_recovery/experiments/hall_01_plasticbag_comparison.mcap"


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
) -> np.ndarray:
    ts_m, est_m, gt_m = associate_trajectories(ts_est, xyz_est, ts_gt, xyz_gt, max_diff_sec=0.1)
    pre = (ts_m - t0) < 118.0
    R, t, s = umeyama_se3_align(est_m[pre], gt_m[pre], with_scale=False)
    return (s * (xyz_est @ R.T)) + t


def make_path_msg(ts_arr: np.ndarray, xyz_arr: np.ndarray, up_to_t: float, frame_id: str = "map") -> Path:
    path = Path()
    path.header = Header(stamp=rospy.Time.from_sec(up_to_t), frame_id=frame_id)
    mask = ts_arr <= up_to_t
    # Subsample to ~5Hz for smooth lightweight Path rendering in Foxglove
    idxs = np.flatnonzero(mask)
    if len(idxs) > 700:
        step = max(1, len(idxs) // 700)
        idxs = idxs[::step]
    for i in idxs:
        ps = PoseStamped()
        ps.header = Header(stamp=rospy.Time.from_sec(float(ts_arr[i])), frame_id=frame_id)
        ps.pose.position.x = float(xyz_arr[i, 0])
        ps.pose.position.y = float(xyz_arr[i, 1])
        ps.pose.position.z = float(xyz_arr[i, 2])
        ps.pose.orientation.w = 1.0
        path.poses.append(ps)
    return path


def make_markers(
    stamp_t: float,
    gt_ts: np.ndarray,
    gt_xyz: np.ndarray,
    t0: float,
) -> MarkerArray:
    ma = MarkerArray()
    hdr = Header(stamp=rospy.Time.from_sec(stamp_t), frame_id="map")

    # 1. Checkpoint sphere at t = t0 + 118s
    ckpt_idx = int(np.argmin(np.abs(gt_ts - (t0 + 118.0))))
    ckpt_pos = gt_xyz[ckpt_idx]

    m_ckpt = Marker()
    m_ckpt.header = hdr
    m_ckpt.ns = "quarantine_events"
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

    # 2. Text label for checkpoint
    m_txt = Marker()
    m_txt.header = hdr
    m_txt.ns = "quarantine_events"
    m_txt.id = 2
    m_txt.type = Marker.TEXT_VIEW_FACING
    m_txt.action = Marker.ADD
    m_txt.pose.position.x = float(ckpt_pos[0])
    m_txt.pose.position.y = float(ckpt_pos[1])
    m_txt.pose.position.z = float(ckpt_pos[2] + 1.8)
    m_txt.pose.orientation.w = 1.0
    m_txt.scale.z = 0.8
    m_txt.color = ColorRGBA(1.0, 1.0, 1.0, 1.0)
    m_txt.text = "Trusted Checkpoint (t=118s, 2s pre-onset margin)"
    ma.markers.append(m_txt)

    # 3. Highlighted line strip for [120s, 140s] plastic-bag injection zone on GT
    m_zone = Marker()
    m_zone.header = hdr
    m_zone.ns = "quarantine_events"
    m_zone.id = 3
    m_zone.type = Marker.LINE_STRIP
    m_zone.action = Marker.ADD
    m_zone.pose.orientation.w = 1.0
    m_zone.scale.x = 0.45
    m_zone.color = ColorRGBA(1.0, 0.2, 0.2, 0.85)
    zone_mask = ((gt_ts - t0) >= 120.0) & ((gt_ts - t0) <= 140.0)
    for pt in gt_xyz[zone_mask]:
        m_zone.points.append(Point(float(pt[0]), float(pt[1]), float(pt[2])))
    ma.markers.append(m_zone)

    # 4. Summary scoreboard text above origin
    m_board = Marker()
    m_board.header = hdr
    m_board.ns = "quarantine_events"
    m_board.id = 4
    m_board.type = Marker.TEXT_VIEW_FACING
    m_board.action = Marker.ADD
    m_board.pose.position.x = float(gt_xyz[0, 0])
    m_board.pose.position.y = float(gt_xyz[0, 1])
    m_board.pose.position.z = float(gt_xyz[0, 2] + 4.0)
    m_board.pose.orientation.w = 1.0
    m_board.scale.z = 0.75
    m_board.color = ColorRGBA(0.95, 0.95, 0.4, 1.0)
    m_board.text = (
        "hall_01 Plastic-Bag Occlusion [120-140s]\n"
        "FAST-LIO2 Degraded: ATE=7.28m | +slam_recovery B6: ATE=0.31m (G=99.5%)\n"
        "MM-LINS B2 (0 sleep): ATE=5.96m (Win=12.34m)\n"
        "LIO-SAM Degraded: ATE=5.96m | +slam_recovery B6: ATE=1.51m (G=78.8%)"
    )
    ma.markers.append(m_board)
    return ma


def subsample_pc2(msg: PointCloud2, stride: int = 8, frame_id: str = "map") -> PointCloud2:
    raw = np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(-1, 24)[::stride].copy()
    m = PointCloud2()
    m.header = Header(stamp=msg.header.stamp, frame_id=frame_id)
    m.height = 1
    m.width = int(raw.shape[0])
    m.fields = msg.fields
    m.is_bigendian = False
    m.point_step = 24
    m.row_step = 24 * m.width
    m.data = raw.tobytes()
    m.is_dense = True
    return m


def main() -> None:
    ts_gt, xyz_gt = load_tum_trajectory("/home/R26534/M2DGR/GT/hall_01.txt")
    t0 = float(ts_gt[0])
    # Center GT near (0,0,0) for comfortable Foxglove 3D camera orbit
    origin_offset = xyz_gt[0].copy()
    xyz_gt_centered = xyz_gt - origin_offset

    ts_lio_deg, xyz_lio_deg = read_odom("/tmp/liosam_plasticbag.bag", "/lio_sam/mapping/odometry")
    ts_fl_deg, xyz_fl_deg = read_odom("/tmp/mmlins_plasticbag.bag", "/Odometry")
    ts_mm_deg, xyz_mm_deg = read_odom("/tmp/mmlins_plasticbag.bag", "/aft_pgo_odom")
    ts_fl_rep, xyz_fl_rep = read_odom("/tmp/mmlins_repaired_bag.bag", "/Odometry")

    xyz_lio_b6, _, _ = repair_quarantined_trajectory_segment(
        ts_lio_deg,
        xyz_lio_deg,
        t_q_start=t0 + 118.0,
        t_q_end=t0 + 142.0,
        ts_aux=ts_fl_rep,
        xyz_aux=xyz_fl_rep,
    )

    # Align all trajectories to centered GT using pre-quarantine (<118s) segment
    aligned_fl_deg = align_to_gt_pre_quarantine(ts_fl_deg, xyz_fl_deg, ts_gt, xyz_gt_centered, t0)
    aligned_mm_deg = align_to_gt_pre_quarantine(ts_mm_deg, xyz_mm_deg, ts_gt, xyz_gt_centered, t0)
    aligned_lio_deg = align_to_gt_pre_quarantine(ts_lio_deg, xyz_lio_deg, ts_gt, xyz_gt_centered, t0)
    aligned_fl_b6 = align_to_gt_pre_quarantine(ts_fl_rep, xyz_fl_rep, ts_gt, xyz_gt_centered, t0)
    aligned_lio_b6 = align_to_gt_pre_quarantine(ts_lio_deg, xyz_lio_b6, ts_gt, xyz_gt_centered, t0)

    os.makedirs(os.path.dirname(OUT_MCAP), exist_ok=True)
    with open(OUT_MCAP, "wb") as f:
        writer = Ros1McapWriter(output=f)

        # Emit time-stepped trajectory paths at 1 Hz across the 351s sequence
        eval_times = np.arange(t0 + 1.0, float(ts_gt[-1]), 1.0)
        for t_cur in eval_times:
            t_ns = int(t_cur * 1e9)
            writer.write_message("/gt/path", make_path_msg(ts_gt, xyz_gt_centered, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/degraded/fast_lio2_b0_path", make_path_msg(ts_fl_deg, aligned_fl_deg, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/degraded/mmlins_b2_pgo_path", make_path_msg(ts_mm_deg, aligned_mm_deg, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/degraded/lio_sam_b0_path", make_path_msg(ts_lio_deg, aligned_lio_deg, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/repaired/fast_lio2_b6_path", make_path_msg(ts_fl_rep, aligned_fl_b6, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/repaired/lio_sam_b6_path", make_path_msg(ts_lio_deg, aligned_lio_b6, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/quarantine/markers", make_markers(t_cur, ts_gt, xyz_gt_centered, t0), log_time=t_ns, publish_time=t_ns)

        # Also embed 1Hz sensor-frame scans during [115s, 145s] to visually compare plastic-bag vs stripped scan
        last_sec_deg = -1
        with rosbag.Bag("/home/R26534/M2DGR/injected/hall_01_inj_plasticbag_120_140s.bag", "r") as b_deg:
            for _, msg, _ in b_deg.read_messages(topics=["/velodyne_points"]):
                ts = msg.header.stamp.to_sec()
                rel = ts - t0
                if 115.0 <= rel <= 145.0 and int(rel) != last_sec_deg:
                    last_sec_deg = int(rel)
                    t_ns = int(ts * 1e9)
                    writer.write_message("/scan_sensor_frame/degraded_plasticbag", subsample_pc2(msg, stride=6, frame_id="map"), log_time=t_ns, publish_time=t_ns)

        last_sec_rep = -1
        with rosbag.Bag("/home/R26534/M2DGR/injected/hall_01_repaired_plasticbag_120_140s.bag", "r") as b_rep:
            for _, msg, _ in b_rep.read_messages(topics=["/velodyne_points"]):
                ts = msg.header.stamp.to_sec()
                rel = ts - t0
                if 115.0 <= rel <= 145.0 and int(rel) != last_sec_rep:
                    last_sec_rep = int(rel)
                    t_ns = int(ts * 1e9)
                    writer.write_message("/scan_sensor_frame/repaired_stripped_bg", subsample_pc2(msg, stride=2, frame_id="map"), log_time=t_ns, publish_time=t_ns)

        writer.finish()

    print(f"Successfully generated {OUT_MCAP} ({os.path.getsize(OUT_MCAP) / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    main()
