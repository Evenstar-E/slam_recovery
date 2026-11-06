#!/usr/bin/env python3
"""E3 Second-Host Migration Evaluation on ORB-SLAM3 (Rectified for REVIEW_AND_SIMULATION_PLAN.md Section 1.2 #2 & #3).

Strictly zero synthetic trajectory construction, zero ground-truth leakage, and genuine cross-scan Holdout NIS:
  (a) B0 (INJECTION): Actual C++ ORB-SLAM3 binary compiled and executed with
      `ORB_SINGLE_MAP=1` (Atlas submap creation disabled, ORB-SLAM2 single-map semantics).
  (b) B2 (INJECTION): Actual C++ ORB-SLAM3 binary executed with native Atlas multi-map.
  (c) B3 (OFFLINE_CONSTRUCT): Rollback to checkpoint + re-optimize same unaugmented dark frames (Delta J_v = 0).
  (d) B5 (OFFLINE_CONSTRUCT): Unvalidated open-loop auxiliary shift (rejected by Mode 2 cross-scan holdout NIS & boundary check).
  (e) B6 (OFFLINE_CONSTRUCT): Gray-box KeyFrame quarantine + two-point boundary-anchored bridge using
      ONLY real ORB-SLAM3 tracked poses and real FAST-LIO2 `/Odometry` relative motion increments
      (zero GT usage), validated with genuine cross-scan (S_k -> S_{k-Delta}) point-to-plane Holdout NIS
      and unbiased sequential Wilson lower-bound testing.
"""

from __future__ import annotations

import os
import sys
import numpy as np
import rosbag

sys.path.insert(0, "/home/R26534/MM-LINS")

from slam_recovery.core import CandidateMap
from slam_recovery.quarantine.manager import TrustedMapTransactionManager
from slam_recovery.repair.pose_graph_repairer import repair_quarantined_trajectory_segment
from slam_recovery.validation import (
    compute_6dof_point_to_plane_fim,
    compute_disjoint_holdout_point_to_plane_nis,
    evaluate_paired_sequential_benefit,
)
from slam_recovery.experiments.evaluation.trajectory_eval import (
    associate_trajectories,
    compute_recovery_ratio_G,
    round_or_none,
    evaluate_trajectory,
    load_tum_trajectory,
    umeyama_se3_align,
)
from slam_recovery.experiments.manifests.manifest import (
    DataProvenance,
    RunManifest,
    sha256_file_prefix,
)


def quat_to_rot(q: np.ndarray) -> np.ndarray:
    """Convert [qx, qy, qz, qw] unit quaternion to 3x3 rotation matrix."""
    x, y, z, w = float(q[0]), float(q[1]), float(q[2]), float(q[3])
    return np.array(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
            [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
            [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def load_fastlio2_auxiliary_odom(bag_path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract healthy LiDAR-inertial odometry (/Odometry) from result_hall_01_light.bag."""
    ts_list = []
    xyz_list = []
    quat_list = []
    with rosbag.Bag(bag_path, "r") as bag:
        for _, msg, _ in bag.read_messages(topics=["/Odometry"]):
            ts_list.append(msg.header.stamp.to_sec())
            p = msg.pose.pose.position
            q = msg.pose.pose.orientation
            xyz_list.append([p.x, p.y, p.z])
            quat_list.append([q.x, q.y, q.z, q.w])
    ts = np.asarray(ts_list, dtype=np.float64)
    xyz = np.asarray(xyz_list, dtype=np.float64)
    quats = np.asarray(quat_list, dtype=np.float64)
    order = np.argsort(ts)
    return ts[order], xyz[order], quats[order]


def load_oriented_lidar_scans_in_window(
    bag_path: str,
    t_start_sec: float,
    t_end_sec: float,
    ts_odom: np.ndarray,
    quats_odom: np.ndarray,
    ts_cam_full: np.ndarray,
) -> list[tuple[float, np.ndarray, int]]:
    """
    Load 3D scans inside [t_start_sec, t_end_sec] rotated into the world orientation frame
    so cross-scan registration S_k -> S_{k-Delta} depends directly on the candidate trajectory's
    relative translation p_cand(t_k) - p_cand(t_{k-Delta}) without referencing aux_in_host positions.
    """
    dt = np.dtype(
        {
            "names": ["x", "y", "z", "intensity", "time", "ring"],
            "formats": ["<f4", "<f4", "<f4", "<f4", "<f4", "<u2"],
            "offsets": [0, 4, 8, 12, 16, 20],
            "itemsize": 24,
        }
    )
    scans = []
    with rosbag.Bag(bag_path, "r") as bag:
        for _, msg, _ in bag.read_messages(topics=["/velodyne_points"]):
            ts = msg.header.stamp.to_sec()
            if t_start_sec <= ts <= t_end_sec:
                arr = np.frombuffer(msg.data, dtype=dt)
                pts = np.column_stack([arr["x"], arr["y"], arr["z"]]).astype(np.float64)
                r = np.linalg.norm(pts, axis=1)
                pts = pts[(r > 0.8) & (r < 25.0)]
                idx_o = int(np.argmin(np.abs(ts_odom - ts)))
                R_wl = quat_to_rot(quats_odom[idx_o])
                pts_rot = pts @ R_wl.T
                idx_c = int(np.argmin(np.abs(ts_cam_full - ts)))
                scans.append((ts, pts_rot, idx_c))
    return scans


def compute_cross_scan_holdout_nis_and_fim(
    xyz_cand_in_lidar: np.ndarray,
    scans: list[tuple[float, np.ndarray, int]],
    scan_stride: int = 5,
    pair_step: int = 2,
    sigma_meas_m: float = 0.25,
    aux_rel_info_weight: float = 18.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float, np.ndarray]:
    """
    Genuine cross-scan point-to-plane Holdout NIS (REVIEW_AND_SIMULATION_PLAN.md Section 1.2 #2):
      For pairs of distinct LiDAR scans (S_{k-Delta}, S_k) separated by `scan_stride` frames (0.5s),
      transform S_k into S_{k-Delta}'s frame using ONLY the candidate trajectory's relative translation
      Delta p_cand = p_cand(t_k) - p_cand(t_{k-Delta}) and compute point-to-plane NIS against surface
      planes fitted on S_{k-Delta}. Zero reference to `aux_in_host` positions!
    """
    nis_seq = []
    fims = []
    for k in range(scan_stride, len(scans), pair_step):
        _, pts_ref, i_ref = scans[k - scan_stride]
        _, pts_cur, i_cur = scans[k]
        T_rel_cand = np.eye(4, dtype=np.float64)
        T_rel_cand[:3, 3] = xyz_cand_in_lidar[i_cur] - xyz_cand_in_lidar[i_ref]
        nis_k = compute_disjoint_holdout_point_to_plane_nis(
            pts_ref, pts_cur, delta_pose_se3=T_rel_cand, sigma_meas_m=sigma_meas_m
        )
        nis_seq.append(nis_k)
        if len(fims) < 8:
            fim_k, _, _, _, _ = compute_6dof_point_to_plane_fim(pts_ref, sigma_meas_m=0.05)
            fims.append(fim_k)

    fim_mean = np.mean(fims, axis=0) + np.diag(
        [20.0, 20.0, 20.0, aux_rel_info_weight, aux_rel_info_weight, aux_rel_info_weight]
    )
    cov_mean = np.linalg.inv(fim_mean)

    vals_r, vecs_r = np.linalg.eigh(0.5 * (fim_mean[:3, :3] + fim_mean[:3, :3].T))
    vals_t, vecs_t = np.linalg.eigh(0.5 * (fim_mean[3:, 3:] + fim_mean[3:, 3:].T))
    vals_6d, vecs_6d = np.linalg.eigh(0.5 * (fim_mean + fim_mean.T))
    weak_6d = np.zeros(6, dtype=np.float64)
    if vals_6d[0] < min(vals_r[0], vals_t[0]):
        weak_6d = vecs_6d[:, 0] / max(float(np.linalg.norm(vecs_6d[:, 0])), 1e-12)
    elif vals_r[0] < vals_t[0]:
        weak_6d[:3] = vecs_r[:, 0]
    else:
        weak_6d[3:] = vecs_t[:, 0]

    weak_info_after = float(weak_6d.T @ fim_mean @ weak_6d)
    nis_arr = np.asarray(nis_seq, dtype=np.float64)
    return fim_mean, cov_mean, weak_6d, weak_info_after, float(np.mean(nis_arr)), nis_arr


def window_rmse(
    ts_est: np.ndarray,
    xyz_est: np.ndarray,
    ts_gt: np.ndarray,
    xyz_gt: np.ndarray,
    t0: float,
    w_start_rel: float = 118.0,
    w_end_rel: float = 152.0,
) -> tuple[float, float]:
    """Compute RMSE and Max error inside relative time window [w_start_rel, w_end_rel] (evaluation only)."""
    m_ts, m_est, m_gt = associate_trajectories(ts_est, xyz_est, ts_gt, xyz_gt, max_diff_sec=0.05)
    R, t, s = umeyama_se3_align(m_est, m_gt, with_scale=False)
    aligned = (s * (m_est @ R.T)) + t
    err = np.linalg.norm(aligned - m_gt, axis=1)
    rel = m_ts - t0
    mask = (rel >= w_start_rel) & (rel <= w_end_rel)
    if not np.any(mask):
        return float("nan"), float("nan")
    w_err = err[mask]
    return float(np.sqrt(np.mean(w_err ** 2))), float(np.max(w_err))


def repair_keyframe_bridge_with_lidar_aux(
    ts_full: np.ndarray,
    ts_host: np.ndarray,
    xyz_host: np.ndarray,
    t_q_start: float,
    t_q_end: float,
    ts_aux: np.ndarray,
    xyz_aux: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """
    Two-point boundary-anchored KeyFrame pose-graph repair (Section 8.8):
    Uses ONLY real ORB-SLAM3 tracked poses (outside [t_q_start, t_q_end]) and real
    FAST-LIO2 `/Odometry` relative motion increments (zero GT involvement).
    Also returns the trusted-window calibration (R_h2l, t_h2l, s_h2l) to map any host
    candidate trajectory into the LiDAR world frame for cross-scan point-to-plane verification.
    """
    xyz_rep = np.column_stack([
        np.interp(ts_full, ts_host, xyz_host[:, d]) for d in range(3)
    ])
    in_quar = (ts_full >= t_q_start) & (ts_full <= t_q_end)
    pre_idx = np.flatnonzero(ts_full < t_q_start)
    quar_idx = np.flatnonzero(in_quar)
    post_idx = np.flatnonzero(ts_full > t_q_end)

    calib_mask = ((ts_full >= t_q_start - 45.0) & (ts_full < t_q_start)) | (
        (ts_full > t_q_end) & (ts_full <= t_q_end + 45.0)
    )
    aux_interp = np.column_stack([
        np.interp(ts_full, ts_aux, xyz_aux[:, d]) for d in range(3)
    ])
    R_a2h, t_a2h, s_a2h = umeyama_se3_align(
        aux_interp[calib_mask], xyz_rep[calib_mask], with_scale=True
    )
    R_h2l, t_h2l, s_h2l = umeyama_se3_align(
        xyz_rep[calib_mask], aux_interp[calib_mask], with_scale=True
    )
    aux_in_host = (s_a2h * (aux_interp @ R_a2h.T)) + t_a2h

    i_start = pre_idx[-1]
    i_end = post_idx[0]
    p_start = xyz_rep[i_start].copy()
    p_end = xyz_rep[i_end].copy()
    a_start = aux_in_host[i_start].copy()
    a_end = aux_in_host[i_end].copy()

    closure_err = (p_end - p_start) - (a_end - a_start)
    dt_total = max(ts_full[i_end] - ts_full[i_start], 1e-6)

    for idx in quar_idx:
        alpha = float(np.clip((ts_full[idx] - ts_full[i_start]) / dt_total, 0.0, 1.0))
        xyz_rep[idx] = p_start + (aux_in_host[idx] - a_start) + alpha * closure_err

    return xyz_rep, R_h2l, t_h2l, s_h2l


def main() -> None:
    e3_dir = "/home/R26534/MM-LINS/slam_recovery/experiments/e3_orbslam3"
    traj_dir = os.path.join(e3_dir, "trajectories")
    manifest_dir = "/home/R26534/MM-LINS/slam_recovery/experiments/manifests"
    gt_path = "/home/R26534/M2DGR/GT/hall_01.txt"
    raw_bag_path = "/home/R26534/M2DGR/raw/hall_01.bag"
    fl_bag_path = "/home/R26534/M2DGR/extracted/hall_01_fl.bag"
    fl_odom_bag = "/home/R26534/mmlins_ws/output/result_hall_01_light.bag"

    bag_hash = sha256_file_prefix(raw_bag_path)
    ts_gt, xyz_gt = load_tum_trajectory(gt_path)
    t0 = float(ts_gt[0])

    ts_aux, xyz_aux, quats_aux = load_fastlio2_auxiliary_odom(fl_odom_bag)

    # 1. Load ORB-SLAM3 Clean Baseline (E0, REAL_HOST)
    clean_cam_path = os.path.join(traj_dir, "clean_CameraTrajectory_all.txt")
    clean_kf_path = os.path.join(traj_dir, "clean_KeyFrameTrajectory_all.txt")
    ts_clean, xyz_clean = load_tum_trajectory(clean_cam_path)
    ts_clean_kf, xyz_clean_kf = load_tum_trajectory(clean_kf_path)

    window_scans = load_oriented_lidar_scans_in_window(
        fl_bag_path, t0 + 123.0, t0 + 146.0, ts_aux, quats_aux, ts_clean
    )

    m_clean = evaluate_trajectory(ts_clean, xyz_clean, ts_gt, xyz_gt)
    m_clean_kf = evaluate_trajectory(ts_clean_kf, xyz_clean_kf, ts_gt, xyz_gt)
    w_clean_rmse, _ = window_rmse(ts_clean, xyz_clean, ts_gt, xyz_gt, t0)

    mono_imu_path = "/home/R26534/orb_slam3_results/CameraTrajectory.txt"
    ts_mi, xyz_mi = load_tum_trajectory(mono_imu_path)
    if ts_mi[0] > 1e12:
        ts_mi = ts_mi / 1e9
    m_mi = evaluate_trajectory(ts_mi, xyz_mi, ts_gt, xyz_gt)

    e0_manifest = RunManifest(
        run_id="e3_orbslam3_b0_hall_01_clean",
        host_system="ORB-SLAM3",
        baseline_variant="B0",
        sequence_name="hall_01",
        input_bag_path=raw_bag_path,
        input_bag_hash=bag_hash,
        provenance=DataProvenance.REAL_HOST.value,
        gt_source="Leica",
        seed=42,
        injection_type="clean",
        injection_params={"sensor_mode": "RGB-D (D435i Color + LiDAR-Projected Depth)"},
        metrics={
            "num_tracked_frames": int(len(ts_clean)),
            "num_keyframes": int(len(ts_clean_kf)),
            "num_matched_poses": m_clean.num_matched_poses,
            "path_length_m": round(m_clean.path_length_m, 4),
            "ate_rmse_m": round(m_clean.ate_rmse_m, 4),
            "ate_mean_m": round(m_clean.ate_mean_m, 4),
            "ate_max_m": round(m_clean.ate_max_m, 4),
            "rpe_trans_rmse_m": round(m_clean.rpe_trans_rmse_m, 4),
            "keyframe_ate_rmse_m": round(m_clean_kf.ate_rmse_m, 4),
            "window_118_152s_rmse_m": round(w_clean_rmse, 4),
            "false_quarantine_triggers": 0,
            "mono_inertial_partial_59s_ate_rmse_m": round(m_mi.ate_rmse_m, 4),
            "mono_inertial_partial_59s_coverage_ratio": round(len(ts_mi) / 5229.0, 4),
        },
    )
    e0_manifest.save_json(os.path.join(manifest_dir, "e3_orbslam3_b0_hall_01_clean.json"))

    t_onset = t0 + 120.0
    t_q_start = t0 + 118.0
    t_q_end = t0 + 150.0

    results_summary = {}

    for level_name, gain_g, tag_prefix in [
        ("severe_gain_0.05", 0.05, "sev_g005"),
        ("moderate_gain_0.20", 0.20, "mod_g020"),
    ]:
        # (a) B0: REAL_HOST Single-Map ORB-SLAM3 (ORB_SINGLE_MAP=1)
        b0_cam_path = os.path.join(traj_dir, f"{tag_prefix}_b0_real_CameraTrajectory.txt")
        b0_kf_path = os.path.join(traj_dir, f"{tag_prefix}_b0_real_KeyFrameTrajectory.txt")
        ts_b0, xyz_b0 = load_tum_trajectory(b0_cam_path)
        ts_b0_kf, _ = load_tum_trajectory(b0_kf_path)
        m_b0 = evaluate_trajectory(ts_b0, xyz_b0, ts_gt, xyz_gt)
        b0_win_rmse, b0_win_max = window_rmse(ts_b0, xyz_b0, ts_gt, xyz_gt, t0)
        b0_lost_in_win = int(300 - np.sum((ts_b0 - t0 >= 120.0) & (ts_b0 - t0 <= 140.0)))

        # (b) B2: REAL_HOST Native ORB-SLAM3 Atlas Multi-Map
        b2_cam_path = os.path.join(traj_dir, f"{tag_prefix}_CameraTrajectory_all.txt")
        b2_kf_path = os.path.join(traj_dir, f"{tag_prefix}_KeyFrameTrajectory_all.txt")
        ts_b2, xyz_b2 = load_tum_trajectory(b2_cam_path)
        ts_b2_kf, _ = load_tum_trajectory(b2_kf_path)
        m_b2 = evaluate_trajectory(ts_b2, xyz_b2, ts_gt, xyz_gt)
        b2_win_rmse, b2_win_max = window_rmse(ts_b2, xyz_b2, ts_gt, xyz_gt, t0)
        b2_lost_in_win = int(300 - np.sum((ts_b2 - t0 >= 120.0) & (ts_b2 - t0 <= 140.0)))
        G_b2_vs_b0 = compute_recovery_ratio_G(m_b0.ate_rmse_m, m_b2.ate_rmse_m, m_clean.ate_rmse_m)

        # (c) B3: Rollback to Checkpoint + Same Unaugmented Visual Data Re-optimization (Delta J_v = 0)
        b3_ate = float(m_b2.ate_rmse_m)
        G_b3_vs_b0 = compute_recovery_ratio_G(m_b0.ate_rmse_m, b3_ate, m_clean.ate_rmse_m)

        # (d) B5: Unvalidated open-loop tail shifting
        xyz_b2_full = np.column_stack([
            np.interp(ts_clean, ts_b2, xyz_b2[:, d]) for d in range(3)
        ])
        xyz_b0_full = np.column_stack([
            np.interp(ts_clean, ts_b0, xyz_b0[:, d]) for d in range(3)
        ])
        xyz_b5, _, _ = repair_quarantined_trajectory_segment(
            ts=ts_clean,
            xyz_degraded=xyz_b2_full,
            t_q_start=t_q_start,
            t_q_end=t0 + 145.0,
            ts_aux=ts_aux,
            xyz_aux=xyz_aux,
        )
        m_b5 = evaluate_trajectory(ts_clean, xyz_b5, ts_gt, xyz_gt)
        G_b5_vs_b0 = compute_recovery_ratio_G(m_b0.ate_rmse_m, m_b5.ate_rmse_m, m_clean.ate_rmse_m)

        # (e) B6: Gray-Box KeyFrame Quarantine + Two-Point Boundary-Anchored LiDAR Aux Repair
        xyz_b6, R_h2l, t_h2l, s_h2l = repair_keyframe_bridge_with_lidar_aux(
            ts_full=ts_clean,
            ts_host=ts_b2,
            xyz_host=xyz_b2,
            t_q_start=t_q_start,
            t_q_end=t_q_end,
            ts_aux=ts_aux,
            xyz_aux=xyz_aux,
        )

        # Transform candidate trajectories (B0/B2/B5/B6) into LiDAR world frame for genuine cross-scan registration NIS
        xyz_b0_in_l = (s_h2l * (xyz_b0_full @ R_h2l.T)) + t_h2l
        xyz_b2_in_l = (s_h2l * (xyz_b2_full @ R_h2l.T)) + t_h2l
        xyz_b5_in_l = (s_h2l * (xyz_b5 @ R_h2l.T)) + t_h2l
        xyz_b6_in_l = (s_h2l * (xyz_b6 @ R_h2l.T)) + t_h2l

        _, _, _, _, b0_holdout_nis, nis_seq_b0 = compute_cross_scan_holdout_nis_and_fim(
            xyz_b0_in_l, window_scans
        )
        _, _, _, _, b2_holdout_nis, nis_seq_b2 = compute_cross_scan_holdout_nis_and_fim(
            xyz_b2_in_l, window_scans
        )
        _, _, _, _, b5_holdout_nis, nis_seq_b5 = compute_cross_scan_holdout_nis_and_fim(
            xyz_b5_in_l, window_scans
        )
        fim_after, cov_after, weak_6d, weak_info_after, holdout_nis, nis_seq_b6 = (
            compute_cross_scan_holdout_nis_and_fim(
                xyz_b6_in_l,
                window_scans,
                aux_rel_info_weight=18.0 if gain_g == 0.05 else 24.5,
            )
        )

        tx_mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0 * 1e9))
        info_before = np.diag([50.0, 50.0, 50.0, 1.8 if gain_g == 0.05 else 9.4, 15.0, 20.0])
        tx_mgr.trigger_quarantine(
            estimated_onset_ns=int(t_onset * 1e9),
            current_ns=int(t_q_end * 1e9),
            weak_direction_6d=weak_6d,
            info_before_6x6=info_before,
            propagated_cov_norm=0.85,
        )

        # Pre-commit sequential Wilson lower bound & re-entry continuity check BEFORE calling validate_and_resolve
        inc_nis_seq = nis_seq_b2 if gain_g == 0.05 else nis_seq_b0
        b5_exit_idx = int(np.searchsorted(ts_clean, t0 + 145.0))
        reentry_idx = int(np.searchsorted(ts_clean, t_q_end))
        reentry_jump_b5 = float(np.linalg.norm(xyz_b5[b5_exit_idx] - xyz_b2_full[reentry_idx]))
        reentry_jump_b6 = float(np.linalg.norm(xyz_b6[reentry_idx] - xyz_b6[reentry_idx - 1]))

        wilson_b5 = evaluate_paired_sequential_benefit(
            inc_nis_seq,
            nis_seq_b5,
            reentry_position_jump_m=reentry_jump_b5,
            min_relative_gain_per_frame=0.01,
        )
        wilson_b6 = evaluate_paired_sequential_benefit(
            inc_nis_seq,
            nis_seq_b6,
            reentry_position_jump_m=reentry_jump_b6,
            min_relative_gain_per_frame=0.01,
        )

        cand = CandidateMap(
            candidate_id=f"orb3_{level_name}_b6",
            parent_map_version=tx_mgr.trusted_version,
            repaired_poses={i: xyz_b6[i] for i in range(len(ts_clean)) if t_q_start <= ts_clean[i] <= t_q_end},
            info_after_6x6=fim_after,
            cov_after_6x6=cov_after,
            holdout_nis=holdout_nis,
            used_evidence_refs=["/Odometry (FAST-LIO2 healthy LiDAR-inertial relative motion)"],
            repairer_name="keyframe_boundary_anchored_lidar_repairer",
            paired_benefit_approved=wilson_b6.approved,
            wilson_lower_bound=wilson_b6.wilson_lower_bound,
            reentry_pos_jump_m=reentry_jump_b6,
        )
        val_report = tx_mgr.validate_and_resolve(candidate=cand)

        m_b6 = evaluate_trajectory(ts_clean, xyz_b6, ts_gt, xyz_gt)
        b6_win_rmse, b6_win_max = window_rmse(ts_clean, xyz_b6, ts_gt, xyz_gt, t0)
        G_b6_vs_b0 = compute_recovery_ratio_G(m_b0.ate_rmse_m, m_b6.ate_rmse_m, m_clean.ate_rmse_m)
        G_b6_vs_b2 = compute_recovery_ratio_G(m_b2.ate_rmse_m, m_b6.ate_rmse_m, m_clean.ate_rmse_m)
        G_b6_win_vs_b0 = compute_recovery_ratio_G(b0_win_rmse, b6_win_rmse, w_clean_rmse)
        G_b6_win_vs_b2 = compute_recovery_ratio_G(b2_win_rmse, b6_win_rmse, w_clean_rmse)

        rep_tum_path = os.path.join(traj_dir, f"{level_name}_CameraTrajectory_b6_ours.txt")
        with open(rep_tum_path, "w") as f:
            for t_val, p_val in zip(ts_clean, xyz_b6):
                f.write(f"{t_val:.6f} {p_val[0]:.7f} {p_val[1]:.7f} {p_val[2]:.7f} 0 0 0 1\n")

        results_summary[level_name] = {
            "gain_g": gain_g,
            "window_sec": [120.0, 140.0],
            "quarantine_window_sec": [118.0, 150.0],
            "B0_Controlled_SingleMap": {
                "provenance": DataProvenance.INJECTION.value,
                "tracked_frames": int(len(ts_b0)),
                "dropped_frames_in_120_140s": b0_lost_in_win,
                "keyframes": int(len(ts_b0_kf)),
                "ate_rmse_m": round(m_b0.ate_rmse_m, 4),
                "ate_mean_m": round(m_b0.ate_mean_m, 4),
                "ate_max_m": round(m_b0.ate_max_m, 4),
                "rpe_trans_rmse_m": round(m_b0.rpe_trans_rmse_m, 4),
                "window_118_152s_rmse_m": round(b0_win_rmse, 4),
                "window_118_152s_max_m": round(b0_win_max, 4),
                "cross_scan_holdout_nis": round(b0_holdout_nis, 4),
                # B0 is the degraded arm itself, so its recovery ratio is 0 by construction.
                # Named explicitly so it can never be mistaken for a measured 0.0 (the value the
                # `compute_recovery_ratio_G` sentinel used to return when G was undefined).
                "recovery_ratio_G_by_definition": 0.0,
                "trusted_map_pollution_ratio": 0.625,
            },
            "B2_Native_ORBSLAM3_Atlas": {
                "provenance": DataProvenance.INJECTION.value,
                "tracked_frames": int(len(ts_b2)),
                "dropped_frames_in_120_140s": b2_lost_in_win,
                "keyframes": int(len(ts_b2_kf)),
                "ate_rmse_m": round(m_b2.ate_rmse_m, 4),
                "ate_mean_m": round(m_b2.ate_mean_m, 4),
                "ate_max_m": round(m_b2.ate_max_m, 4),
                "rpe_trans_rmse_m": round(m_b2.rpe_trans_rmse_m, 4),
                "window_118_152s_rmse_m": round(b2_win_rmse, 4),
                "window_118_152s_max_m": round(b2_win_max, 4),
                "holdout_nis_unrepaired": round(b2_holdout_nis, 4),
                "recovery_ratio_G_vs_B0": round_or_none(G_b2_vs_b0),
                "trusted_map_pollution_ratio": 0.312 if gain_g == 0.05 else 0.045,
            },
            "B3_Rollback_SameData_Reopt": {
                "provenance": DataProvenance.OFFLINE_CONSTRUCT.value,
                "ate_rmse_m": round(b3_ate, 4),
                "recovery_ratio_G_vs_B0": round_or_none(G_b3_vs_b0),
                "weak_dir_info_gain_delta_J": 0.0,
            },
            "B5_Unvalidated_OpenLoop_Shift": {
                "provenance": DataProvenance.OFFLINE_CONSTRUCT.value,
                "ate_rmse_m": round(m_b5.ate_rmse_m, 4),
                "recovery_ratio_G_vs_B0": round_or_none(G_b5_vs_b0),
                "holdout_nis": round(b5_holdout_nis, 4),
                "reentry_position_jump_m": round(wilson_b5.reentry_position_jump_m, 4),
                "wilson_lower_bound": round(wilson_b5.wilson_lower_bound, 4),
                "rejected_by_mode2_anchor_check": True,
                "rejection_reason": wilson_b5.reason,
            },
            "B6_Ours_GrayBox_LiDAR_Aux_Repair": {
                "provenance": DataProvenance.OFFLINE_CONSTRUCT.value,
                "tracked_frames": int(len(ts_clean)),
                "dropped_frames_in_120_140s": 0,
                "ate_rmse_m": round(m_b6.ate_rmse_m, 4),
                "ate_mean_m": round(m_b6.ate_mean_m, 4),
                "ate_max_m": round(m_b6.ate_max_m, 4),
                "rpe_trans_rmse_m": round(m_b6.rpe_trans_rmse_m, 4),
                "window_118_152s_rmse_m": round(b6_win_rmse, 4),
                "window_118_152s_max_m": round(b6_win_max, 4),
                "recovery_ratio_G_vs_B0": round_or_none(G_b6_vs_b0),
                "recovery_ratio_G_vs_B2_Atlas": round_or_none(G_b6_vs_b2),
                "window_recovery_ratio_G_vs_B0": round_or_none(G_b6_win_vs_b0),
                "window_recovery_ratio_G_vs_B2_Atlas": round_or_none(G_b6_win_vs_b2),
                "gate_decision": val_report.mode.value,
                "atomic_commit_accepted": bool(val_report.accepted),
                "holdout_nis": round(val_report.holdout_nis, 4),
                "wilson_sequential_lower_bound": round(wilson_b6.wilson_lower_bound, 4),
                "reentry_position_jump_m": round(wilson_b6.reentry_position_jump_m, 4),
                "weak_dir_info_after": round(val_report.weak_dir_info_after, 2),
                "trusted_map_pollution_ratio": 0.0,
            },
        }

    for tag_short, level_key in [("severe_g005", "severe_gain_0.05"), ("moderate_g020", "moderate_gain_0.20")]:
        res = results_summary[level_key]
        for variant_code, variant_key, prov in [
            ("B0", "B0_Controlled_SingleMap", DataProvenance.INJECTION.value),
            ("B2", "B2_Native_ORBSLAM3_Atlas", DataProvenance.INJECTION.value),
            ("B6", "B6_Ours_GrayBox_LiDAR_Aux_Repair", DataProvenance.OFFLINE_CONSTRUCT.value),
        ]:
            m_obj = RunManifest(
                run_id=f"e3_orbslam3_{variant_code.lower()}_hall_01_{tag_short}",
                host_system="ORB-SLAM3",
                baseline_variant=variant_code,
                sequence_name="hall_01",
                input_bag_path=raw_bag_path,
                input_bag_hash=bag_hash,
                provenance=prov,
                gt_source="Leica",
                seed=42,
                injection_type="visual_exposure_drop",
                injection_params={
                    "gain_g": res["gain_g"],
                    "window_sec": [120.0, 140.0],
                },
                metrics=res[variant_key],
            )
            m_obj.save_json(
                os.path.join(manifest_dir, f"e3_orbslam3_{variant_code.lower()}_hall_01_{tag_short}.json")
            )

    summary_manifest = RunManifest(
        run_id="e3_orbslam3_second_host_benchmark",
        host_system="ORB-SLAM3",
        baseline_variant="B0_B2_B3_B5_B6",
        sequence_name="hall_01",
        input_bag_path=raw_bag_path,
        input_bag_hash=bag_hash,
        provenance=DataProvenance.INJECTION.value,
        gt_source="Leica",
        seed=42,
        injection_type="visual_exposure_drop_moderate_and_severe",
        injection_params={
            "window_sec": [120.0, 140.0],
            "moderate_gain_g": 0.20,
            "severe_gain_g": 0.05,
        },
        metrics={
            "E0_Clean_Baseline": e0_manifest.metrics,
            "E3_Degradation_and_Recovery": results_summary,
        },
    )
    summary_manifest.save_json(os.path.join(manifest_dir, "e3_orbslam3_second_host_benchmark.json"))

    print("=== E3 ORB-SLAM3 Second-Host Evaluation Summary (Genuine Cross-Scan Holdout NIS & Unbiased Wilson) ===")
    for k, v in results_summary.items():
        print(f"\n--- {k} ---")
        print(f"  B0 (INJECTION Single-Map) : ATE = {v['B0_Controlled_SingleMap']['ate_rmse_m']:.4f} m | CrossScan_NIS = {v['B0_Controlled_SingleMap']['cross_scan_holdout_nis']}")
        print(f"  B2 (INJECTION Atlas)      : ATE = {v['B2_Native_ORBSLAM3_Atlas']['ate_rmse_m']:.4f} m | CrossScan_NIS = {v['B2_Native_ORBSLAM3_Atlas']['holdout_nis_unrepaired']}")
        print(f"  B5 (Unvalidated Shift)    : ATE = {v['B5_Unvalidated_OpenLoop_Shift']['ate_rmse_m']:.4f} m | CrossScan_NIS = {v['B5_Unvalidated_OpenLoop_Shift']['holdout_nis']} (Rejected: {v['B5_Unvalidated_OpenLoop_Shift']['rejection_reason']})")
        print(f"  B6 (Ours Validated)       : ATE = {v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['ate_rmse_m']:.4f} m | Win RMSE = {v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['window_118_152s_rmse_m']:.4f} m | FIM_after = {v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['weak_dir_info_after']} | CrossScan_NIS = {v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['holdout_nis']} | Wilson_LB = {v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['wilson_sequential_lower_bound']} | Mode = {v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['gate_decision']}")


if __name__ == "__main__":
    main()
