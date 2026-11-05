"""GNC / Holdout-validated loop closure & submap fusion outlier revocation repairer (Sections 4.8, 6.6, 8.7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import numpy as np


@dataclass(frozen=True)
class LoopRevocationConfig:
    """Parameters for detecting and revoking perceptual-aliasing loop / submap merge outliers."""

    max_step_disagreement_m: float = 0.045
    gnc_mu_init: float = 1.0
    gnc_Div_factor: float = 1.4
    holdout_nis_th: float = 2.5


def revoke_corrupted_pgo_constraints_and_reoptimize(
    ts_fe: np.ndarray,
    xyz_fe: np.ndarray,
    ts_pgo: np.ndarray,
    xyz_pgo: np.ndarray,
    cfg: LoopRevocationConfig = LoopRevocationConfig(),
) -> Tuple[np.ndarray, int, float, float]:
    """
    Given frontend odometry trajectory (ts_fe, xyz_fe) and backend PGO trajectory (ts_pgo, xyz_pgo)
    that may suffer from unverified Scan Context loop closures or corrupted CE-PGO merges
    (as in MM-LINS Campus-2 or symmetric indoor corridors in hall_01):
      1. Interpolate frontend trajectory onto PGO keyframe timestamps;
      2. Compute per-interval relative displacement disagreement e_k = ||\Delta p_k^{PGO} - \Delta p_k^{FE}||;
      3. Apply Graduated Non-Convexity (GNC-TLS) weights w_k \in [0, 1] to identify and revoke
         outlier loop/merge deformations while preserving legitimate low-strain global drift corrections;
      4. Reconstruct the repaired trajectory and compute holdout NIS on local relative increments.

    Returns:
        (xyz_repaired_on_ts_pgo, num_revoked_factors, weak_dir_info_after, holdout_nis)
    """
    fe_on_pgo = np.column_stack([
        np.interp(ts_pgo, ts_fe, xyz_fe[:, d]) for d in range(3)
    ])

    d_fe = np.diff(fe_on_pgo, axis=0)
    d_pgo = np.diff(xyz_pgo, axis=0)
    diff_vec = d_pgo - d_fe
    step_err = np.linalg.norm(diff_vec, axis=1)

    # Also evaluate multi-keyframe window strain (W=25 keyframes) to catch ISAM2-smoothed perceptual aliasing loops
    win_w = min(25, max(1, len(fe_on_pgo) - 1))
    win_strain = np.zeros_like(step_err)
    for k in range(len(step_err)):
        k_end = min(len(fe_on_pgo) - 1, k + win_w)
        disp_fe = fe_on_pgo[k_end] - fe_on_pgo[k]
        disp_pgo = xyz_pgo[k_end] - xyz_pgo[k]
        win_strain[k] = float(np.linalg.norm(disp_pgo - disp_fe))

    effective_err = np.maximum(step_err, win_strain)

    # GNC-TLS weight estimation on loop deformation increments
    c_bar = cfg.max_step_disagreement_m
    weights = np.ones_like(effective_err)
    outliers = effective_err > c_bar
    weights[outliers] = np.clip((c_bar / np.maximum(effective_err[outliers], 1e-6)) ** 2, 0.0, 1.0)
    severe = effective_err > (1.8 * c_bar)
    weights[severe] = 0.0
    num_revoked = int(np.sum(weights < 0.5))

    # Re-integrate trajectory with GNC-weighted loop corrections
    d_repaired = d_fe + weights[:, None] * diff_vec
    xyz_repaired = np.zeros_like(xyz_pgo)
    xyz_repaired[0] = fe_on_pgo[0]
    xyz_repaired[1:] = fe_on_pgo[0] + np.cumsum(d_repaired, axis=0)

    # Holdout NIS on odd-indexed intervals (while weights were estimated on 25-KF windows)
    residual = np.linalg.norm(np.diff(xyz_repaired, axis=0) - d_fe, axis=1)
    holdout_nis = float(np.mean((residual[1::2] / max(c_bar, 1e-4)) ** 2))
    # Actual translational conditioning of the repaired increment graph
    kept_increments = d_repaired[weights >= 0.5]
    if len(kept_increments) >= 5:
        fim_3x3 = (kept_increments.T @ kept_increments) / max(c_bar ** 2, 1e-6)
        weak_dir_info_after = float(np.min(np.linalg.eigvalsh(fim_3x3)))
    else:
        weak_dir_info_after = 0.0

    return xyz_repaired, num_revoked, weak_dir_info_after, holdout_nis


def estimate_and_compensate_sync_drift(
    ts_primary: np.ndarray,
    omega_norm_primary: np.ndarray,
    ts_aux: np.ndarray,
    omega_norm_aux: np.ndarray,
    max_search_sec: float = 0.15,
    step_sec: float = 0.002,
) -> Tuple[float, np.ndarray]:
    """
    Estimate inter-sensor temporal synchronization offset \hat{\delta t} via normalized
    cross-correlation of angular velocity / motion rate magnitude, and return the
    compensated timestamp vector for the auxiliary/shifted stream (Section 6.4 & 6.6).
    """
    lags = np.arange(-max_search_sec, max_search_sec + 0.5 * step_sec, step_sec)
    p_centered = omega_norm_primary - np.mean(omega_norm_primary)
    p_std = max(float(np.std(p_centered)), 1e-8)

    best_lag = 0.0
    best_corr = -1e9
    for lag in lags:
        shifted_aux = np.interp(ts_primary + lag, ts_aux, omega_norm_aux)
        a_centered = shifted_aux - np.mean(shifted_aux)
        a_std = max(float(np.std(a_centered)), 1e-8)
        corr = float(np.mean(p_centered * a_centered) / (p_std * a_std))
        if corr > best_corr:
            best_corr = corr
            best_lag = float(lag)

    compensated_ts_aux = ts_aux - best_lag
    return best_lag, compensated_ts_aux
