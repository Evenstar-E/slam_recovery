"""Physics-Guided Feature Engineering (Sections 4.2, 4.4, 4.5, 5.2 of FAST_LIVO2_SHARED_CORE_EXTRACTION.md):
1. Nuisance-Projected Identifiability \mathcal{I}_\perp(s | H) = ||(I - H(H^T H)^\dagger H^T) s||_2^2 / ||s||_2^2
2. 4x12 = 48 Spherical Azimuth-Elevation Cell Encoding S_t \in R^{48 x 10}
3. Zero-Dataset-Fit Physical Unit Compression & Causal Past-Median Residual \tilde{\delta}_t
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np

from ..core import HealthWindow


def compute_nuisance_projected_identifiability(
    jacobian_6dof: np.ndarray,
    distortion_dir_s: np.ndarray,
    rcond: float = 1e-6,
) -> Tuple[float, np.ndarray]:
    """
    Compute the nuisance-projected identifiability \mathcal{I}_\perp(s | H) in [0, 1] (Section 4.5):
        s_\perp = (I - H (H^T H)^\dagger H^T) s
        \mathcal{I}_\perp(s | H) = ||s_\perp||_2^2 / max(||s||_2^2, 1e-12)

    If \mathcal{I}_\perp(s | H) -> 0, the candidate sensor distortion direction `s` (e.g., range scale,
    extrinsic offset, or planar sheet shift) is collinear with 6-DoF rigid-body pose motion `H`,
    proving that single-modality parameter fitting is unidentifiable and cross-modal bridging is required.
    """
    H = np.asarray(jacobian_6dof, dtype=np.float64)
    s = np.asarray(distortion_dir_s, dtype=np.float64).reshape(-1)
    if H.ndim != 2 or H.shape[0] != len(s) or len(s) == 0:
        raise ValueError(f"Incompatible shapes: H={H.shape}, s={s.shape}")

    s_norm_sq = float(np.dot(s, s))
    if s_norm_sq < 1e-12:
        return 0.0, np.zeros_like(s)

    # Project s onto column space of H via pseudoinverse
    HTH_pinv = np.linalg.pinv(H.T @ H, rcond=rcond)
    s_proj = H @ (HTH_pinv @ (H.T @ s))
    s_perp = s - s_proj
    identifiability = float(np.clip(np.dot(s_perp, s_perp) / s_norm_sq, 0.0, 1.0))
    return identifiability, s_perp


def extract_48_spherical_cells(
    points_xyzi: np.ndarray,
    n_azimuth: int = 12,
    n_elevation: int = 4,
    elev_min_deg: float = -25.0,
    elev_max_deg: float = 15.0,
) -> np.ndarray:
    """
    Partition a 3D point cloud into C = n_azimuth * n_elevation = 48 spherical cells (Section 4.2).
    For each cell c in 0..47, extract 10 physical statistics:
      [0]: log1p(valid_point_count) / log1p(500)
      [1]: log1p(range_q25 / 10.0)
      [2]: log1p(range_q50 / 10.0)
      [3]: log1p(range_q75 / 10.0)
      [4]: log1p(intensity_q50 / 100.0)
      [5]: log1p(radial_std / 1.0)
      [6,7,8]: unit line-of-sight vector u_c = [cos(el)cos(az), cos(el)sin(az), sin(el)]
      [9]: non_empty_mask in {0.0, 1.0}
    Returns array of shape (48, 10).
    """
    n_cells = n_azimuth * n_elevation
    out = np.zeros((n_cells, 10), dtype=np.float64)

    az_edges = np.linspace(-np.pi, np.pi, n_azimuth + 1)
    el_edges = np.deg2rad(np.linspace(elev_min_deg, elev_max_deg, n_elevation + 1))

    # Pre-fill cell center unit vectors u_c
    for ie in range(n_elevation):
        el_c = 0.5 * (el_edges[ie] + el_edges[ie + 1])
        for ia in range(n_azimuth):
            az_c = 0.5 * (az_edges[ia] + az_edges[ia + 1])
            cid = ie * n_azimuth + ia
            out[cid, 6] = np.cos(el_c) * np.cos(az_c)
            out[cid, 7] = np.cos(el_c) * np.sin(az_c)
            out[cid, 8] = np.sin(el_c)

    pts = np.asarray(points_xyzi, dtype=np.float64)
    if len(pts) == 0:
        return out

    xyz = pts[:, :3]
    inten = pts[:, 3] if pts.shape[1] >= 4 else np.full(len(pts), 50.0)
    ranges = np.linalg.norm(xyz, axis=1)
    valid = ranges > 0.05
    if not np.any(valid):
        return out

    xyz = xyz[valid]
    ranges = ranges[valid]
    inten = inten[valid]

    az = np.arctan2(xyz[:, 1], xyz[:, 0])
    el = np.arcsin(np.clip(xyz[:, 2] / ranges, -1.0, 1.0))

    ia_idx = np.clip(np.searchsorted(az_edges, az) - 1, 0, n_azimuth - 1)
    ie_idx = np.clip(np.searchsorted(el_edges, el) - 1, 0, n_elevation - 1)
    cell_ids = ie_idx * n_azimuth + ia_idx

    for cid in range(n_cells):
        m = cell_ids == cid
        cnt = int(np.sum(m))
        if cnt == 0:
            continue
        r_c = ranges[m]
        i_c = inten[m]
        q25, q50, q75 = np.percentile(r_c, [25, 50, 75])
        out[cid, 0] = np.log1p(cnt) / np.log1p(500.0)
        out[cid, 1] = np.log1p(q25 / 10.0)
        out[cid, 2] = np.log1p(q50 / 10.0)
        out[cid, 3] = np.log1p(q75 / 10.0)
        out[cid, 4] = np.log1p(max(0.0, float(np.median(i_c))) / 100.0)
        out[cid, 5] = np.log1p(float(np.std(r_c)) / 1.0)
        out[cid, 9] = 1.0

    return out


# Pre-declared task physical units u_{phys} (Zero dataset-fit normalization, Section 5.2.1)
PHYSICAL_UNITS_12D = np.array([
    20.0,     # [0] min_eig_rot
    25.0,     # [1] min_eig_trans
    0.0005,   # [2] max_eig_rot_cov
    0.0040,   # [3] max_eig_trans_cov
    1.20,     # [4] nis_mean
    1.80,     # [5] nis_q90
    1.50,     # [6] loso_primary_conflict
    1.50,     # [7] loso_aux_conflict
    0.015,    # [8] |Cross_corr_lag_sec|
    1.50,     # [9] loop_residual_spike
    0.15,     # [10] point_drop_ratio
    0.20,     # [11] near_field_plane_ratio
], dtype=np.float64)


def compress_window_by_physical_units(w: HealthWindow) -> np.ndarray:
    """Apply parameter-free physical unit compression v_t = arcsinh(z_t / u_{phys}) in R^{12}."""
    raw = np.array([
        w.min_eig_rot,
        w.min_eig_trans,
        w.max_eig_rot_cov,
        w.max_eig_trans_cov,
        w.nis_mean,
        w.nis_q90,
        w.loso_primary_conflict,
        w.loso_aux_conflict,
        abs(w.Cross_corr_lag_sec),
        w.loop_residual_spike,
        w.point_drop_ratio,
        w.near_field_plane_ratio,
    ], dtype=np.float64)
    return np.arcsinh(raw / PHYSICAL_UNITS_12D)


class CausalPhysicsTokenStream:
    """
    Maintains the causal sliding history buffer \mathcal{H}_{<t} of healthy tokens
    and produces the 48-dimensional physics-invariant token:
        x_t = [v_t (12), \tilde{\delta}_t (12), m_t (12), p_t (12)] \in R^{48}
    strictly without looking at future frames or fitting dataset-wide mean/std.
    """

    def __init__(self, history_size: int = 25, min_ready_samples: int = 5) -> None:
        self.history_size = int(history_size)
        self.min_ready_samples = int(min_ready_samples)
        self.healthy_history: List[np.ndarray] = []

    def step(self, w: HealthWindow, is_currently_trusted_healthy: bool = True) -> np.ndarray:
        v_t = compress_window_by_physical_units(w)
        m_t = np.ones_like(v_t)
        past_ready = len(self.healthy_history) >= self.min_ready_samples
        p_t = np.ones_like(v_t) if past_ready else np.zeros_like(v_t)

        if past_ready:
            hist_mat = np.asarray(self.healthy_history[-self.history_size :], dtype=np.float64)
            med_past = np.median(hist_mat, axis=0)
            delta_t = m_t * p_t * (v_t - med_past)
        else:
            delta_t = np.zeros_like(v_t)

        # Update causal history only with nominal/pre-alarm frames so ongoing degradation does not corrupt the baseline
        if is_currently_trusted_healthy and len(self.healthy_history) < self.min_ready_samples * 2:
            self.healthy_history.append(v_t.copy())
        elif is_currently_trusted_healthy and np.max(np.abs(delta_t)) < 0.85:
            self.healthy_history.append(v_t.copy())
            if len(self.healthy_history) > self.history_size:
                self.healthy_history.pop(0)

        return np.concatenate([v_t, delta_t, m_t, p_t], axis=0)
