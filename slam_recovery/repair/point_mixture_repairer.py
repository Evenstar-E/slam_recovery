"""Point-level mixture reliability filter and repairer for MEAS_CONTAM (Sections 4.7 & 6.6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import numpy as np

from ..validation.fim_and_holdout import compute_6dof_point_to_plane_fim


@dataclass(frozen=True)
class MixtureFilterConfig:
    """Parameters for the 3-component point mixture model p(z) = pi_t p_t + pi_s p_s + pi_n p_n (Section 4.7)."""

    near_field_max_range_m: float = 5.0
    plane_inlier_dist_m: float = 0.05
    min_occluder_fraction: float = 0.30
    min_remaining_bg_points: int = 400
    min_weak_dir_eigenvalue: float = 15.0


def filter_self_consistent_near_field_contaminants(
    points_xyzi: np.ndarray,
    cfg: MixtureFilterConfig = MixtureFilterConfig(),
) -> Tuple[np.ndarray, float, float, bool]:
    """
    Identify and strip self-consistent near-field pseudo-planar contaminants
    (such as a floating plastic bag or dense near-field smoke/crowd cluster)
    and verify whether the remaining background points satisfy the geometric
    observability condition v^T \Lambda_{filtered} v >= \tau_{obs} (Section 4.7).

    Returns:
        (filtered_mask, contam_ratio, min_bg_eigenvalue, is_geometrically_repairable)
    """
    pts = np.asarray(points_xyzi, dtype=np.float64)
    n_total = len(pts)
    if n_total == 0:
        return np.zeros(0, dtype=bool), 0.0, 0.0, False

    xyz = pts[:, :3]
    intensity = pts[:, 3]
    ranges = np.linalg.norm(xyz, axis=1)
    # Candidate rays within full oblique span of a near-field occluder sheet
    near_mask = (ranges > 0.05) & (ranges <= cfg.near_field_max_range_m * 5.0)
    near_indices = np.flatnonzero(near_mask)

    if len(near_indices) < int(cfg.min_occluder_fraction * n_total):
        _, _, min_r, min_t, _ = compute_6dof_point_to_plane_fim(xyz)
        min_eig = min(min_r, min_t)
        return np.ones(n_total, dtype=bool), 0.0, min_eig, True

    # Fit dominant near-field plane via deterministic RANSAC and verify orthogonal distance |n^T p0| <= near_field_max_range_m
    near_xyz = xyz[near_indices]
    rng = np.random.default_rng(0)
    best_inliers = np.zeros(len(near_indices), dtype=bool)
    best_ortho_d = 0.0
    best_normal = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    for _ in range(80):
        if len(near_xyz) < 3:
            break
        sample_idx = rng.choice(len(near_xyz), size=3, replace=False)
        p0, p1, p2 = near_xyz[sample_idx]
        normal = np.cross(p1 - p0, p2 - p0)
        n_norm = np.linalg.norm(normal)
        if n_norm < 1e-6:
            continue
        normal /= n_norm
        ortho_dist_origin = abs(float(p0 @ normal))
        if ortho_dist_origin > cfg.near_field_max_range_m:
            continue
        dists = np.abs((near_xyz - p0) @ normal)
        inliers = dists <= cfg.plane_inlier_dist_m
        if np.sum(inliers) > np.sum(best_inliers):
            best_inliers = inliers
            best_ortho_d = ortho_dist_origin
            best_normal = normal.copy()

    is_contaminant = np.zeros(n_total, dtype=bool)
    is_contaminant[near_indices[best_inliers]] = True
    # Strip the entire occluded azimuth sector and grazed cap associated with the near-field sheet
    if best_ortho_d > 0.0 and np.sum(best_inliers) > int(0.15 * n_total):
        unit_dirs = xyz / np.maximum(ranges[:, None], 1e-6)
        denom = np.maximum(np.abs(unit_dirs @ best_normal), 0.25)
        expected_sheet_r = best_ortho_d / denom
        sheet_match = np.abs(ranges - expected_sheet_r) <= 4.0 * cfg.plane_inlier_dist_m
        is_contaminant |= sheet_match
    contam_ratio = float(np.mean(is_contaminant))

    if contam_ratio < cfg.min_occluder_fraction:
        keep_mask = np.ones(n_total, dtype=bool)
    else:
        keep_mask = ~is_contaminant

    bg_xyz = xyz[keep_mask]
    if len(bg_xyz) < cfg.min_remaining_bg_points:
        return keep_mask, contam_ratio, 0.0, False

    # Compute true 6-DoF point-to-plane Fisher Information Matrix \Lambda_{6x6} on surviving background points
    _, _, min_r, min_t, _ = compute_6dof_point_to_plane_fim(bg_xyz)
    min_eig = min(min_r, min_t)
    repairable = min_eig >= cfg.min_weak_dir_eigenvalue
    return keep_mask, contam_ratio, min_eig, repairable
