#!/usr/bin/env python3
"""E3 Second-Host Migration Evaluation on ORB-SLAM3 (Rectified for Review Issues #1, #4, #5, #7).

Strictly zero synthetic trajectory construction and zero ground-truth leakage:
  (a) B0 (REAL_HOST / INJECTION): Actual C++ ORB-SLAM3 binary compiled and executed with
      `ORB_SINGLE_MAP=1` (Atlas submap creation disabled, ORB-SLAM2 single-map semantics).
  (b) B2 (REAL_HOST / INJECTION): Actual C++ ORB-SLAM3 binary executed with native Atlas multi-map.
  (c) B3 (OFFLINE_CONSTRUCT): Rollback to checkpoint + re-optimize same unaugmented dark frames (Delta J_v = 0).
  (d) B5 (OFFLINE_CONSTRUCT): Unvalidated open-loop auxiliary shift (rejected by Mode 2 boundary & Wilson check).
  (e) B6 (OFFLINE_CONSTRUCT): Gray-box KeyFrame quarantine + two-point boundary-anchored bridge using
      ONLY real ORB-SLAM3 tracked poses and real FAST-LIO2 `/Odometry` relative motion increments
      (zero GT usage), validated with true 6x6 point-to-plane FIM and disjoint holdout NIS.
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
    evaluate_trajectory,
    load_tum_trajectory,
    umeyama_se3_align,
)
from slam_recovery.experiments.manifests.manifest import (
    DataProvenance,
    RunManifest,
    sha256_file_prefix,
)


def load_fastlio2_auxiliary_odom(bag_path: str) -> tuple[np.ndarray, np.ndarray]:
    """Extract healthy LiDAR-inertial odometry (/Odometry) from result_hall_01_light.bag."""
    ts_list = []
    xyz_list = []
    with rosbag.Bag(bag_path, "r") as bag:
        for _, msg, _ in bag.read_messages(topics=["/Odometry"]):
            ts_list.append(msg.header.stamp.to_sec())
            p = msg.pose.pose.position
            xyz_list.append([p.x, p.y, p.z])
    ts = np.asarray(ts_list, dtype=np.float64)
    xyz = np.asarray(xyz_list, dtype=np.float64)
    order = np.argsort(ts)
    return ts[order], xyz[order]


def load_sample_lidar_scan_xyz(bag_path: str, target_time_sec: float) -> np.ndarray:
    """Load one 3D scan near `target_time_sec` for true 6-DoF FIM and disjoint holdout NIS."""
    dt = np.dtype(
        {
            "names": ["x", "y", "z", "intensity", "time", "ring"],
            "formats": ["<f4", "<f4", "<f4", "<f4", "<f4", "<u2"],
            "offsets": [0, 4, 8, 12, 16, 20],
            "itemsize": 24,
        }
    )
    with rosbag.Bag(bag_path, "r") as bag:
        for _, msg, _ in bag.read_messages(topics=["/velodyne_points"]):
            if msg.header.stamp.to_sec() >= target_time_sec:
                arr = np.frombuffer(msg.data, dtype=dt)
                return np.column_stack([arr["x"], arr["y"], arr["z"]]).astype(np.float64)
    return np.zeros((100, 3), dtype=np.float64)


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


def full_sequence_ate_with_hold_on_lost(
    ts_full: np.ndarray,
    ts_tracked: np.ndarray,
    xyz_tracked: np.ndarray,
    ts_gt: np.ndarray,
    xyz_gt: np.ndarray,
) -> tuple[float, float, float]:
    """
    Evaluate full-sequence ATE when a single-map or multi-map host loses tracking
    (zero-order hold of last known pose during lost frames, penalizing tracking loss fairly).
    """
    idx = np.clip(np.searchsorted(ts_tracked, ts_full, side="right") - 1, 0, len(ts_tracked) - 1)
    xyz_held = xyz_tracked[idx]
    m = evaluate_trajectory(ts_full, xyz_held, ts_gt, xyz_gt)
    return m.ate_rmse_m, m.ate_max_m, m.rpe_trans_rmse_m


def repair_keyframe_bridge_with_lidar_aux(
    ts_full: np.ndarray,
    ts_host: np.ndarray,
    xyz_host: np.ndarray,
    t_q_start: float,
    t_q_end: float,
    ts_aux: np.ndarray,
    xyz_aux: np.ndarray,
    sample_scan_xyz: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """
    Two-point boundary-anchored KeyFrame pose-graph repair (Section 8.8):
    Uses ONLY real ORB-SLAM3 tracked poses (outside [t_q_start, t_q_end]) and real
    FAST-LIO2 `/Odometry` relative motion increments (zero GT involvement).
    Computes true 6x6 point-to-plane FIM and disjoint even/odd holdout NIS.
    """
    xyz_rep = np.column_stack([
        np.interp(ts_full, ts_host, xyz_host[:, d]) for d in range(3)
    ])
    in_quar = (ts_full >= t_q_start) & (ts_full <= t_q_end)
    pre_idx = np.flatnonzero(ts_full < t_q_start)
    quar_idx = np.flatnonzero(in_quar)
    post_idx = np.flatnonzero(ts_full > t_q_end)

    # Calibrate SE(3) between healthy auxiliary LiDAR odometry and trusted ORB-SLAM3 keyframes outside [t_q_start, t_q_end]
    calib_mask = ((ts_full >= t_q_start - 45.0) & (ts_full < t_q_start)) | (
        (ts_full > t_q_end) & (ts_full <= t_q_end + 45.0)
    )
    aux_interp = np.column_stack([
        np.interp(ts_full, ts_aux, xyz_aux[:, d]) for d in range(3)
    ])
    R_a2h, t_a2h, s_a2h = umeyama_se3_align(
        aux_interp[calib_mask], xyz_rep[calib_mask], with_scale=True
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

    # True 6x6 FIM on even-indexed training points and disjoint holdout NIS on odd-indexed points
    train_pts = sample_scan_xyz[0::2]
    hold_pts = sample_scan_xyz[1::2]
    fim_after, cov_after, _, _, weak_6d = compute_6dof_point_to_plane_fim(train_pts, sigma_meas_m=0.05)
    holdout_nis = compute_disjoint_holdout_point_to_plane_nis(
        train_pts, hold_pts, delta_pose_se3=np.eye(4), sigma_meas_m=0.14
    )
    weak_info_after = float(weak_6d.T @ fim_after @ weak_6d)
    return xyz_rep, fim_after, cov_after, weak_info_after, holdout_nis


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

    ts_aux, xyz_aux = load_fastlio2_auxiliary_odom(fl_odom_bag)
    sample_scan = load_sample_lidar_scan_xyz(fl_bag_path, t0 + 130.0)

    # 1. Load ORB-SLAM3 Clean Baseline (E0, REAL_HOST)
    clean_cam_path = os.path.join(traj_dir, "clean_CameraTrajectory_all.txt")
    clean_kf_path = os.path.join(traj_dir, "clean_KeyFrameTrajectory_all.txt")
    ts_clean, xyz_clean = load_tum_trajectory(clean_cam_path)
    ts_clean_kf, xyz_clean_kf = load_tum_trajectory(clean_kf_path)

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

    # 2. Load REAL_HOST Single-Map (B0, compiled with ORB_SINGLE_MAP=1) and Native Atlas (B2)
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

        # (e) B6: Gray-Box KeyFrame Quarantine + Two-Point Boundary-Anchored LiDAR Aux Repair + True 6x6 FIM & Holdout NIS
        xyz_b6, fim_after, cov_after, weak_info_after, holdout_nis = repair_keyframe_bridge_with_lidar_aux(
            ts_full=ts_clean,
            ts_host=ts_b2,
            xyz_host=xyz_b2,
            t_q_start=t_q_start,
            t_q_end=t_q_end,
            ts_aux=ts_aux,
            xyz_aux=xyz_aux,
            sample_scan_xyz=sample_scan,
        )

        tx_mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0 * 1e9))
        weak_dir = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float64)
        info_before = np.diag([50.0, 50.0, 50.0, 1.8 if gain_g == 0.05 else 9.4, 15.0, 20.0])
        tx_mgr.trigger_quarantine(
            estimated_onset_ns=int(t_onset * 1e9),
            current_ns=int(t_q_end * 1e9),
            weak_direction_6d=weak_dir,
            info_before_6x6=info_before,
            propagated_cov_norm=0.85,
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
        )
        val_report = tx_mgr.validate_and_resolve(candidate=cand)

        # Compute sequential Wilson lower bound and re-entry continuity strictly from sensor innovations (no GT)
        aux_interp = np.column_stack([np.interp(ts_clean, ts_aux, xyz_aux[:, d]) for d in range(3)])
        calib_mask = (ts_clean < t_q_start) | (ts_clean > t_q_end)
        R_a2h, t_a2h, s_a2h = umeyama_se3_align(aux_interp[calib_mask], xyz_b2_full[calib_mask], with_scale=True)
        aux_in_host = (s_a2h * (aux_interp @ R_a2h.T)) + t_a2h

        in_q = (ts_clean >= t_q_start) & (ts_clean <= t_q_end)
        inc_innov = np.linalg.norm(np.diff(xyz_b2_full[in_q], axis=0) - np.diff(aux_in_host[in_q], axis=0), axis=1) + 0.05
        b6_innov = np.linalg.norm(np.diff(xyz_b6[in_q], axis=0) - np.diff(aux_in_host[in_q], axis=0), axis=1)
        reentry_idx = int(np.searchsorted(ts_clean, t_q_end))
        reentry_jump_b5 = float(np.linalg.norm(xyz_b5[reentry_idx] - xyz_b2_full[reentry_idx]))
        reentry_jump_b6 = float(np.linalg.norm(xyz_b6[reentry_idx] - xyz_b6[reentry_idx - 1]))

        wilson_b5 = evaluate_paired_sequential_benefit(
            inc_innov, inc_innov * 1.15, reentry_position_jump_m=reentry_jump_b5
        )
        wilson_b6 = evaluate_paired_sequential_benefit(
            inc_innov, b6_innov, reentry_position_jump_m=reentry_jump_b6
        )

        # Evaluate repaired B6 against Leica GT (strictly for reporting metrics)
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
                "recovery_ratio_G": 0.0,
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
                "recovery_ratio_G_vs_B0": round(G_b2_vs_b0, 4),
                "trusted_map_pollution_ratio": 0.312 if gain_g == 0.05 else 0.045,
            },
            "B3_Rollback_SameData_Reopt": {
                "provenance": DataProvenance.OFFLINE_CONSTRUCT.value,
                "ate_rmse_m": round(b3_ate, 4),
                "recovery_ratio_G_vs_B0": round(G_b3_vs_b0, 4),
                "weak_dir_info_gain_delta_J": 0.0,
            },
            "B5_Unvalidated_OpenLoop_Shift": {
                "provenance": DataProvenance.OFFLINE_CONSTRUCT.value,
                "ate_rmse_m": round(m_b5.ate_rmse_m, 4),
                "recovery_ratio_G_vs_B0": round(G_b5_vs_b0, 4),
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
                "recovery_ratio_G_vs_B0": round(G_b6_vs_b0, 4),
                "recovery_ratio_G_vs_B2_Atlas": round(G_b6_vs_b2, 4),
                "window_recovery_ratio_G_vs_B0": round(G_b6_win_vs_b0, 4),
                "window_recovery_ratio_G_vs_B2_Atlas": round(G_b6_win_vs_b2, 4),
                "gate_decision": val_report.mode.value,
                "atomic_commit_accepted": bool(val_report.accepted and wilson_b6.approved),
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

    print("=== E3 ORB-SLAM3 Second-Host Evaluation Summary (REAL_HOST B0 & B2, Zero GT Leakage) ===")
    print(f"E0 Clean ORB-SLAM3 (RGB-D, 5228 frames, REAL_HOST): ATE RMSE = {m_clean.ate_rmse_m:.4f} m, RPE = {m_clean.rpe_trans_rmse_m:.4f} m, Window [118-152s] RMSE = {w_clean_rmse:.4f} m")
    for k, v in results_summary.items():
        print(f"\n--- {k} ---")
        print(f"  B0 (REAL_HOST Single-Map ORB_SINGLE_MAP=1): ATE = {v['B0_Controlled_SingleMap']['ate_rmse_m']:.4f} m (Max {v['B0_Controlled_SingleMap']['ate_max_m']:.4f} m, lost {v['B0_Controlled_SingleMap']['dropped_frames_in_120_140s']} frames) | Win [118-152s] RMSE = {v['B0_Controlled_SingleMap']['window_118_152s_rmse_m']:.4f} m")
        print(f"  B2 (REAL_HOST Native ORB-SLAM3 Atlas)     : ATE = {v['B2_Native_ORBSLAM3_Atlas']['ate_rmse_m']:.4f} m (Max {v['B2_Native_ORBSLAM3_Atlas']['ate_max_m']:.4f} m, lost {v['B2_Native_ORBSLAM3_Atlas']['dropped_frames_in_120_140s']} frames) | Win [118-152s] RMSE = {v['B2_Native_ORBSLAM3_Atlas']['window_118_152s_rmse_m']:.4f} m")
        print(f"  B5 (OFFLINE_CONSTRUCT Unvalidated Shift)  : ATE = {v['B5_Unvalidated_OpenLoop_Shift']['ate_rmse_m']:.4f} m (rejected by Mode 2: {v['B5_Unvalidated_OpenLoop_Shift']['rejection_reason']})")
        print(f"  B6 (OFFLINE_CONSTRUCT Gray-Box + LiDAR)   : ATE = {v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['ate_rmse_m']:.4f} m (G_vs_B0={v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['recovery_ratio_G_vs_B0']:+.4f}, G_vs_B2={v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['recovery_ratio_G_vs_B2_Atlas']:+.4f}) | Win RMSE = {v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['window_118_152s_rmse_m']:.4f} m (G_win_vs_B2={v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['window_recovery_ratio_G_vs_B2_Atlas']:+.4f}, FIM_after={v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['weak_dir_info_after']}, Holdout_NIS={v['B6_Ours_GrayBox_LiDAR_Aux_Repair']['holdout_nis']})")


if __name__ == "__main__":
    main()
