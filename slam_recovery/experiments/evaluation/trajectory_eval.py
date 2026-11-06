"""Trajectory and recovery evaluation metrics (ATE, RPE, Recovery Ratio G, and End-to-End drift)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np


@dataclass(frozen=True)
class TrajectoryMetrics:
    num_matched_poses: int
    ate_rmse_m: float
    ate_mean_m: float
    ate_max_m: float
    rpe_trans_rmse_m: float
    end_to_end_error_m: float
    path_length_m: float


def load_tum_trajectory(file_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load a TUM format trajectory file: `timestamp tx ty tz qx qy qz qw`.
    Returns:
        timestamps_sec: (N,) float64
        positions_xyz:  (N, 3) float64
    """
    ts_list = []
    xyz_list = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split()
            if len(parts) < 4:
                continue
            ts_list.append(float(parts[0]))
            xyz_list.append([float(parts[1]), float(parts[2]), float(parts[3])])
    if not ts_list:
        raise ValueError(f"No valid TUM trajectory rows found in {file_path}")
    ts = np.asarray(ts_list, dtype=np.float64)
    if len(ts) > 0 and ts[0] > 1e14:
        ts = ts * 1e-9
    xyz = np.asarray(xyz_list, dtype=np.float64)
    order = np.argsort(ts)
    return ts[order], xyz[order]


def associate_trajectories(
    ts_est: np.ndarray,
    xyz_est: np.ndarray,
    ts_gt: np.ndarray,
    xyz_gt: np.ndarray,
    max_diff_sec: float = 0.05,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Associate estimated timestamps to nearest ground-truth timestamps within `max_diff_sec`."""
    idx = np.searchsorted(ts_gt, ts_est)
    idx_left = np.clip(idx - 1, 0, len(ts_gt) - 1)
    idx_right = np.clip(idx, 0, len(ts_gt) - 1)

    diff_left = np.abs(ts_est - ts_gt[idx_left])
    diff_right = np.abs(ts_est - ts_gt[idx_right])
    best_idx = np.where(diff_left <= diff_right, idx_left, idx_right)
    best_diff = np.minimum(diff_left, diff_right)

    valid = best_diff <= max_diff_sec
    return ts_est[valid], xyz_est[valid], xyz_gt[best_idx[valid]]


def umeyama_se3_align(
    src_xyz: np.ndarray,
    dst_xyz: np.ndarray,
    with_scale: bool = False,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Rigid (SE(3)) or similarity (Sim(3)) alignment from src_xyz (N,3) to dst_xyz (N,3).
    Returns (R, t, scale) such that aligned = scale * (src_xyz @ R.T) + t.
    """
    src = np.asarray(src_xyz, dtype=np.float64)
    dst = np.asarray(dst_xyz, dtype=np.float64)
    mu_src = np.mean(src, axis=0)
    mu_dst = np.mean(dst, axis=0)
    src_c = src - mu_src
    dst_c = dst - mu_dst

    cov = (dst_c.T @ src_c) / float(len(src))
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1.0
    R = U @ S @ Vt

    if with_scale:
        var_src = np.mean(np.sum(src_c ** 2, axis=1))
        scale = float(np.sum(D * np.diag(S)) / max(var_src, 1e-12))
    else:
        scale = 1.0

    t = mu_dst - scale * (R @ mu_src)
    return R, t, scale


def evaluate_trajectory(
    ts_est: np.ndarray,
    xyz_est: np.ndarray,
    ts_gt: Optional[np.ndarray] = None,
    xyz_gt: Optional[np.ndarray] = None,
    max_diff_sec: float = 0.05,
    rpe_delta_steps: int = 10,
) -> TrajectoryMetrics:
    """Compute ATE RMSE, RPE, path length, and end-to-end error."""
    diffs = np.diff(xyz_est, axis=0)
    path_len = float(np.sum(np.linalg.norm(diffs, axis=1))) if len(xyz_est) > 1 else 0.0
    e2e_err = float(np.linalg.norm(xyz_est[-1] - xyz_est[0])) if len(xyz_est) > 1 else 0.0

    if ts_gt is None or xyz_gt is None:
        return TrajectoryMetrics(
            num_matched_poses=len(xyz_est),
            ate_rmse_m=float("nan"),
            ate_mean_m=float("nan"),
            ate_max_m=float("nan"),
            rpe_trans_rmse_m=float("nan"),
            end_to_end_error_m=e2e_err,
            path_length_m=path_len,
        )

    _, m_est, m_gt = associate_trajectories(ts_est, xyz_est, ts_gt, xyz_gt, max_diff_sec)
    if len(m_est) < 3:
        raise ValueError(f"Insufficient matched poses ({len(m_est)}) within {max_diff_sec}s")

    R, t, s = umeyama_se3_align(m_est, m_gt, with_scale=False)
    aligned = (s * (m_est @ R.T)) + t
    pos_err = np.linalg.norm(aligned - m_gt, axis=1)

    ate_rmse = float(np.sqrt(np.mean(pos_err ** 2)))
    ate_mean = float(np.mean(pos_err))
    ate_max = float(np.max(pos_err))

    if len(aligned) > rpe_delta_steps:
        d_est = aligned[rpe_delta_steps:] - aligned[:-rpe_delta_steps]
        d_gt = m_gt[rpe_delta_steps:] - m_gt[:-rpe_delta_steps]
        rpe_err = np.linalg.norm(d_est - d_gt, axis=1)
        rpe_rmse = float(np.sqrt(np.mean(rpe_err ** 2)))
    else:
        rpe_rmse = ate_rmse

    return TrajectoryMetrics(
        num_matched_poses=len(m_est),
        ate_rmse_m=ate_rmse,
        ate_mean_m=ate_mean,
        ate_max_m=ate_max,
        rpe_trans_rmse_m=rpe_rmse,
        end_to_end_error_m=e2e_err,
        path_length_m=path_len,
    )


def compute_recovery_ratio_G(
    error_degraded: float,
    error_repaired: float,
    error_clean: float,
) -> float:
    """
    Compute continuous recovery ratio G (Section 9.2):
        G = (E_degraded - E_repaired) / (E_degraded - E_clean)
    G = 1: full recovery to clean baseline
    G = 0: no improvement
    G < 0: repair degraded the map/trajectory (e.g., MM-LINS Campus-2 CE-PGO)
    """
    denom = error_degraded - error_clean
    if abs(denom) < 1e-9:
        return 0.0
    return float((error_degraded - error_repaired) / denom)


def quat_xyzw_to_rot(q: np.ndarray) -> np.ndarray:
    """Convert unit quaternion [qx, qy, qz, qw] to 3x3 rotation matrix in SO(3)."""
    q_arr = np.asarray(q, dtype=np.float64).reshape(4)
    n = float(np.linalg.norm(q_arr))
    if n < 1e-12:
        return np.eye(3, dtype=np.float64)
    qx, qy, qz, qw = q_arr / n
    return np.array(
        [
            [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
            [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
            [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
        ],
        dtype=np.float64,
    )


def _median_body_z_tilt_deg(q_xyzw: np.ndarray) -> float:
    """Median angle (deg) between the body z-axis and the world z-axis.

    A ground/handheld platform keeps body-z roughly aligned with gravity, so the *correct*
    quaternion component ordering yields a small tilt. Used only to disambiguate `xyzw` vs `wxyz`.
    """
    if len(q_xyzw) == 0:
        return float("nan")
    R = np.asarray([quat_xyzw_to_rot(q) for q in q_xyzw])
    return float(np.median(np.rad2deg(np.arccos(np.clip(np.abs(R[:, 2, 2]), 0.0, 1.0)))))


def detect_quat_order(stored: np.ndarray) -> str:
    """Infer the on-disk quaternion ordering of a 4-column block.

    Returns "xyzw" (TUM / ORB-SLAM3 convention) or "wxyz" (M2DGR Vicon Mocap convention).
    The decision uses the upright-body criterion rather than an amplitude heuristic, which
    silently misfires on sequences whose yaw swings far enough that median|qw| drops below 0.85.
    """
    if len(stored) == 0:
        return "xyzw"
    if float(np.median(np.linalg.norm(stored, axis=1))) < 1e-6:
        return "xyzw"  # all-zero block (3-DoF prism GT): ordering is irrelevant
    tilt_xyzw = _median_body_z_tilt_deg(stored)
    tilt_wxyz = _median_body_z_tilt_deg(stored[:, [1, 2, 3, 0]])
    # Require a decisive margin: camera-frame trajectories (ORB-SLAM3, body-z = optical axis)
    # score almost identically under both orderings, and must not be silently re-permuted.
    if abs(tilt_xyzw - tilt_wxyz) < 5.0:
        return "xyzw"
    return "wxyz" if tilt_wxyz < tilt_xyzw else "xyzw"


def load_tum_trajectory_se3(
    file_path: str,
    quat_order: str = "auto",
    drop_invalid_quats: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Load a TUM format trajectory file with full SE(3) poses: `timestamp tx ty tz q0 q1 q2 q3`.

    Args:
        quat_order: on-disk component ordering, one of {"xyzw", "wxyz", "auto"}.
            "xyzw" is the TUM/ORB-SLAM3 convention; "wxyz" is the M2DGR Vicon Mocap convention
            (`timestamp x y z qw qx qy qz`); "auto" infers it via the upright-body criterion.
        drop_invalid_quats: drop rows whose quaternion norm deviates from 1 by more than 0.05.
            The distributed M2DGR Mocap files contain ~2% such rows (a single component is
            corrupted by up to 10x, e.g. `... 0.9999 -0.0030 -0.0110 -4.3742`); after
            renormalization they produce near-arbitrary rotations and destroy every rotational
            metric that touches them.

    Returns (timestamps_sec, positions_xyz, quaternions_xyzw) with quaternions always in xyzw
    order, unit-normalized, and sign-continuous.
    """
    ts_list, xyz_list, quat_list = [], [], []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split()
            if len(parts) < 8:
                continue
            ts_list.append(float(parts[0]))
            xyz_list.append([float(parts[1]), float(parts[2]), float(parts[3])])
            quat_list.append([float(parts[4]), float(parts[5]), float(parts[6]), float(parts[7])])
    if not ts_list:
        raise ValueError(f"No valid 8-column TUM SE(3) rows found in {file_path}")
    ts = np.asarray(ts_list, dtype=np.float64)
    if len(ts) > 0 and ts[0] > 1e14:
        ts = ts * 1e-9
    xyz = np.asarray(xyz_list, dtype=np.float64)
    quats = np.asarray(quat_list, dtype=np.float64)
    order = np.argsort(ts)
    ts, xyz, quats = ts[order], xyz[order], quats[order]

    if quat_order == "auto":
        quat_order = detect_quat_order(quats)
    if quat_order == "wxyz":
        quats = quats[:, [1, 2, 3, 0]]
    elif quat_order != "xyzw":
        raise ValueError(f"Unsupported quat_order={quat_order!r} (expected 'xyzw', 'wxyz' or 'auto')")

    non_zero = np.linalg.norm(quats, axis=1) > 1e-6
    if drop_invalid_quats and np.any(non_zero):
        norms = np.linalg.norm(quats, axis=1)
        # Rows with an all-zero orientation (3-DoF prism GT) are kept; only corrupt 6-DoF rows drop.
        keep = (~non_zero) | (np.abs(norms - 1.0) <= 0.05)
        ts, xyz, quats = ts[keep], xyz[keep], quats[keep]

    norms = np.linalg.norm(quats, axis=1)
    safe = norms > 1e-6
    quats[safe] /= norms[safe, None]
    for i in range(1, len(quats)):
        if safe[i] and safe[i - 1] and float(quats[i] @ quats[i - 1]) < 0.0:
            quats[i] = -quats[i]
    return ts, xyz, quats


def evaluate_path_heading_proxy_deg(
    ts_est: np.ndarray,
    xyz_est: np.ndarray,
    ts_gt: np.ndarray,
    xyz_gt: np.ndarray,
    max_diff_sec: float = 0.08,
    min_chord_m: float = 0.85,
) -> dict:
    """
    Explicitly named path-tangent heading proxy (in degrees) for 3-DoF prism ground truth
    (e.g., Leica total station where 6-DoF orientation quaternions are absent).
    Does NOT trim the top 5% tail errors; returns UNAVAILABLE / None if moving segments are insufficient.
    """
    idx = np.searchsorted(ts_gt, ts_est)
    idx_l = np.clip(idx - 1, 0, len(ts_gt) - 1)
    idx_r = np.clip(idx, 0, len(ts_gt) - 1)
    dl = np.abs(ts_est - ts_gt[idx_l])
    dr = np.abs(ts_est - ts_gt[idx_r])
    best = np.where(dl <= dr, idx_l, idx_r)
    valid = np.minimum(dl, dr) <= max_diff_sec

    p_e = xyz_est[valid]
    p_g = xyz_gt[best[valid]]
    if len(p_e) < 12:
        return {
            "proxy_status": "UNAVAILABLE",
            "heading_proxy_rmse_deg": None,
            "heading_proxy_mean_deg": None,
            "heading_proxy_max_deg": None,
        }

    R_umeyama, _, _ = umeyama_se3_align(p_e, p_g, with_scale=False)
    p_e_aligned = p_e @ R_umeyama.T
    win = max(8, min(30, len(p_g) // 18))
    dp_g = p_g[win:] - p_g[:-win]
    dp_e = p_e_aligned[win:] - p_e_aligned[:-win]
    chord_len = np.linalg.norm(dp_g[:, :2], axis=1)
    steady = chord_len >= min_chord_m
    if int(np.sum(steady)) < 5:
        return {
            "proxy_status": "UNAVAILABLE",
            "heading_proxy_rmse_deg": None,
            "heading_proxy_mean_deg": None,
            "heading_proxy_max_deg": None,
        }

    yaw_g = np.arctan2(dp_g[steady, 1], dp_g[steady, 0])
    yaw_e = np.arctan2(dp_e[steady, 1], dp_e[steady, 0])
    dyaw_deg = np.rad2deg(np.abs(np.arctan2(np.sin(yaw_e - yaw_g), np.cos(yaw_e - yaw_g))))
    return {
        "proxy_status": "AVAILABLE_PATH_TANGENT_PROXY",
        "num_moving_chords": int(np.sum(steady)),
        "heading_proxy_rmse_deg": round(float(np.sqrt(np.mean(dyaw_deg ** 2))), 3),
        "heading_proxy_mean_deg": round(float(np.mean(dyaw_deg)), 3),
        "heading_proxy_max_deg": round(float(np.max(dyaw_deg)), 3),
    }


def evaluate_rotation_ate_rpe_deg(
    ts_est: np.ndarray,
    xyz_est: np.ndarray,
    quats_est: np.ndarray,
    ts_gt: np.ndarray,
    xyz_gt: np.ndarray,
    quats_gt: np.ndarray,
    max_diff_sec: float = 0.08,
    rpe_delta_steps: int = 10,
    gt_quat_order: str = "xyzw",
) -> dict:
    """
    Compute full SE(3) rotational ATE_rot (RMSE / Mean / Max in degrees) and rotational RPE_rot (RMSE in degrees).
    Strictly requires valid 6-DoF unit quaternions in both estimate and reference:
      - If either `quats_est` or `quats_gt` is missing / zero-norm (e.g., 3-DoF Leica prism GT),
        returns `orientation_status="UNAVAILABLE"` and `None` metrics (never fabricates 0.0 or substitutes path chords).
      - Calibrates rigid world/extrinsic frame alignment `(R_world, R_ext)` strictly on the initial 20% healthy
        prefix of the trajectory, never fitting over the full evaluation horizon.
      - `gt_quat_order` is "xyzw" by default; pass "wxyz" only if the caller hand-loaded a Mocap file without
        going through `load_tum_trajectory_se3` (which already normalizes the ordering).
      - Rows with non-unit norm (corrupt quaternion components) are rejected and reported in
        `num_invalid_gt_quaternions`; they are never silently renormalized into an arbitrary rotation.
    """
    unavailable = {
        "orientation_status": "UNAVAILABLE",
        "ate_rot_rmse_deg": None,
        "ate_rot_mean_deg": None,
        "ate_rot_max_deg": None,
        "rpe_rot_rmse_deg": None,
    }
    if len(ts_est) < 5 or len(ts_gt) < 5:
        return unavailable

    idx = np.searchsorted(ts_gt, ts_est)
    idx_l = np.clip(idx - 1, 0, len(ts_gt) - 1)
    idx_r = np.clip(idx, 0, len(ts_gt) - 1)
    dl = np.abs(ts_est - ts_gt[idx_l])
    dr = np.abs(ts_est - ts_gt[idx_r])
    best = np.where(dl <= dr, idx_l, idx_r)
    valid = np.minimum(dl, dr) <= max_diff_sec
    if int(np.sum(valid)) < 5:
        return unavailable

    q_e = np.asarray(quats_est[valid], dtype=np.float64)
    q_g = np.asarray(quats_gt[best[valid]], dtype=np.float64)

    est_norms = np.linalg.norm(q_e, axis=1)
    gt_norms = np.linalg.norm(q_g, axis=1)
    if float(np.median(est_norms)) < 1e-3 or float(np.median(gt_norms)) < 1e-3:
        return unavailable

    if gt_quat_order == "wxyz":
        q_g = q_g[:, [1, 2, 3, 0]]
    elif gt_quat_order != "xyzw":
        raise ValueError(f"Unsupported gt_quat_order={gt_quat_order!r}")

    # Reject corrupt reference rows instead of renormalizing them into a near-arbitrary rotation.
    gt_valid = np.abs(gt_norms - 1.0) <= 0.05
    num_invalid_gt = int(np.sum(~gt_valid))
    if int(np.sum(gt_valid)) < 5:
        return unavailable
    q_e, q_g = q_e[gt_valid], q_g[gt_valid]

    q_e = q_e / np.linalg.norm(q_e, axis=1)[:, None]
    q_g = q_g / np.linalg.norm(q_g, axis=1)[:, None]
    for arr in (q_e, q_g):
        for i in range(1, len(arr)):
            if float(arr[i] @ arr[i - 1]) < 0.0:
                arr[i] = -arr[i]

    R_e = np.asarray([quat_xyzw_to_rot(q) for q in q_e])
    R_g = np.asarray([quat_xyzw_to_rot(q) for q in q_g])

    # Calibrate fixed rigid alignment (R_world, R_ext) strictly on the initial 20% healthy prefix
    n_cal = max(5, len(R_e) // 5)
    R_e_cal = R_e[:n_cal]
    R_g_cal = R_g[:n_cal]

    R_world = np.eye(3, dtype=np.float64)
    R_ext = np.eye(3, dtype=np.float64)
    for _ in range(6):
        M_w = np.einsum("nij,nkj->ik", R_g_cal, np.einsum("nij,jk->nik", R_e_cal, R_ext))
        U_w, _, Vt_w = np.linalg.svd(M_w)
        S_w = np.eye(3)
        if np.linalg.det(U_w) * np.linalg.det(Vt_w) < 0:
            S_w[2, 2] = -1.0
        R_world = U_w @ S_w @ Vt_w

        L = np.einsum("ij,njk->nik", R_world, R_e_cal)
        M_x = np.einsum("nji,njk->ik", L, R_g_cal)
        U_x, _, Vt_x = np.linalg.svd(M_x)
        S_x = np.eye(3)
        if np.linalg.det(U_x) * np.linalg.det(Vt_x) < 0:
            S_x[2, 2] = -1.0
        R_ext = U_x @ S_x @ Vt_x

    ate_angles_deg = []
    for i in range(len(R_e)):
        R_pred = R_world @ R_e[i] @ R_ext
        R_err = R_g[i].T @ R_pred
        cos_theta = float(np.clip(0.5 * (np.trace(R_err) - 1.0), -1.0, 1.0))
        ate_angles_deg.append(np.rad2deg(np.arccos(cos_theta)))
    ate_arr = np.asarray(ate_angles_deg, dtype=np.float64)

    rpe_angles_deg = []
    for i in range(len(R_e) - rpe_delta_steps):
        dR_pred = R_ext.T @ (R_e[i].T @ R_e[i + rpe_delta_steps]) @ R_ext
        dR_gt = R_g[i].T @ R_g[i + rpe_delta_steps]
        R_rpe = dR_gt.T @ dR_pred
        cos_th = float(np.clip(0.5 * (np.trace(R_rpe) - 1.0), -1.0, 1.0))
        rpe_angles_deg.append(np.rad2deg(np.arccos(cos_th)))

    if not rpe_angles_deg:
        rpe_rmse = None
    else:
        rpe_arr = np.asarray(rpe_angles_deg, dtype=np.float64)
        rpe_rmse = round(float(np.sqrt(np.mean(rpe_arr ** 2))), 3)

    return {
        "orientation_status": "AVAILABLE_6DOF_QUATERNION",
        "calibration_prefix_frames": int(n_cal),
        "num_invalid_gt_quaternions_rejected": num_invalid_gt,
        "ate_rot_rmse_deg": round(float(np.sqrt(np.mean(ate_arr ** 2))), 3),
        "ate_rot_mean_deg": round(float(np.mean(ate_arr)), 3),
        "ate_rot_max_deg": round(float(np.max(ate_arr)), 3),
        "rpe_rot_rmse_deg": rpe_rmse,
    }
