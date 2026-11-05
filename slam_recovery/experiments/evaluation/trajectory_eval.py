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
