"""Build room_dark_01_natural_dark_and_r4r5_comparison.mcap for Foxglove visualization."""

from __future__ import annotations

import os
import sys
import numpy as np
import rospy
from geometry_msgs.msg import PoseStamped
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

OUT_MCAP = "/home/R26534/MM-LINS/slam_recovery/experiments/room_dark_01_natural_dark_and_r4r5_comparison.mcap"


def align_full(ts_e: np.ndarray, xyz_e: np.ndarray, ts_gt: np.ndarray, xyz_gt: np.ndarray) -> np.ndarray:
    _, est_m, gt_m = associate_trajectories(ts_e, xyz_e, ts_gt, xyz_gt, 0.1)
    R, t, s = umeyama_se3_align(est_m, gt_m, with_scale=False)
    return (s * (xyz_e @ R.T)) + t


def make_path_msg(ts_arr: np.ndarray, xyz_arr: np.ndarray, up_to_t: float, frame_id: str = "map") -> Path:
    path = Path()
    path.header = Header(stamp=rospy.Time.from_sec(up_to_t), frame_id=frame_id)
    idxs = np.flatnonzero(ts_arr <= up_to_t)
    if len(idxs) > 600:
        idxs = idxs[:: max(1, len(idxs) // 600)]
    for i in idxs:
        ps = PoseStamped()
        ps.header = Header(stamp=rospy.Time.from_sec(float(ts_arr[i])), frame_id=frame_id)
        ps.pose.position.x = float(xyz_arr[i, 0])
        ps.pose.position.y = float(xyz_arr[i, 1])
        ps.pose.position.z = float(xyz_arr[i, 2])
        ps.pose.orientation.w = 1.0
        path.poses.append(ps)
    return path


def main() -> None:
    ts_gt, xyz_gt = load_tum_trajectory("/home/R26534/M2DGR/GT/room_dark_01.txt")
    t0 = float(ts_gt[0])
    xyz_gt_c = xyz_gt - xyz_gt[0]

    d_dir = "/home/R26534/MM-LINS/slam_recovery/experiments/e3_orbslam3/room_dark_01/trajectories"
    ts_b0, xyz_b0 = load_tum_trajectory(os.path.join(d_dir, "b0_singlemap_CameraTrajectory.txt"))
    ts_b2, xyz_b2 = load_tum_trajectory(os.path.join(d_dir, "raw_CameraTrajectory_b2_atlas.txt"))
    ts_b6, xyz_b6 = load_tum_trajectory(os.path.join(d_dir, "b6_ours_CameraTrajectory.txt"))

    al_b0 = align_full(ts_b0, xyz_b0, ts_gt, xyz_gt_c)
    al_b2 = align_full(ts_b2, xyz_b2, ts_gt, xyz_gt_c)
    al_b6 = align_full(ts_b6, xyz_b6, ts_gt, xyz_gt_c)

    with open(OUT_MCAP, "wb") as f:
        writer = Ros1McapWriter(output=f)
        for t_cur in np.arange(t0 + 1.0, float(ts_gt[-1]), 1.0):
            t_ns = int(t_cur * 1e9)
            writer.write_message("/gt/path", make_path_msg(ts_gt, xyz_gt_c, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/orbslam3_natural_dark/b0_singlemap_path", make_path_msg(ts_b0, al_b0, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/orbslam3_natural_dark/b2_native_atlas_5submaps_path", make_path_msg(ts_b2, al_b2, t_cur), log_time=t_ns, publish_time=t_ns)
            writer.write_message("/orbslam3_natural_dark/b6_ours_zero_drop_path", make_path_msg(ts_b6, al_b6, t_cur), log_time=t_ns, publish_time=t_ns)

            ma = MarkerArray()
            m_board = Marker()
            m_board.header = Header(stamp=rospy.Time.from_sec(t_cur), frame_id="map")
            m_board.ns = "room_dark_01_board"
            m_board.id = 1
            m_board.type = Marker.TEXT_VIEW_FACING
            m_board.action = Marker.ADD
            m_board.pose.position.z = 2.5
            m_board.pose.orientation.w = 1.0
            m_board.scale.z = 0.45
            m_board.color = ColorRGBA(0.95, 0.95, 0.35, 1.0)
            m_board.text = (
                "M2DGR room_dark_01 (106.8s Real Natural Darkness)\n"
                "ORB-SLAM3 B0 Single-Map: ATE=0.6897m | Native Atlas B2 (181 lost, 5 submaps, Map4 unmerged): ATE=0.4855m\n"
                "ORB-SLAM3 + Ours B6 (0 lost, 0 unmerged submaps): ATE=0.1800m (G=+98.1%)\n"
                "R4/R5 Dual-Degradation (Dark + Plastic-Bag [35-55s]): LIO-SAM 1.74m->0.27m, FAST-LIO2 1.14m->0.17m"
            )
            ma.markers.append(m_board)
            writer.write_message("/quarantine/markers", ma, log_time=t_ns, publish_time=t_ns)
        writer.finish()

    print(f"Generated {OUT_MCAP} ({os.path.getsize(OUT_MCAP) / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    main()
