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

    # Fit the dominant near-field plane with deterministic RANSAC.
    #
    # Hypotheses are scored by how many returns they explain as a *near-field sheet* -- the same
    # criterion the strip below uses -- rather than by raw plane-inlier count. Scoring by inliers
    # loses on real indoor scans: a floor plane at z ~ 0 collects more inliers than the occluder
    # sheet, so the filter ends up stripping the floor and leaving the bag (measured: 54-57 %
    # removed and ~17 000 bag returns surviving on M2DGR room_02 / hall_01, instead of the ~89 %
    # the repair is supposed to remove). Scoring by sheet coverage selects the occluder and leaves
    # clean scans untouched (sheet fraction 0.18 on a clean scan vs 0.89 on an injected one).
    near_xyz = xyz[near_indices]
    unit_dirs_all = xyz / np.maximum(ranges[:, None], 1e-6)
    rng = np.random.default_rng(0)
    best_inliers = np.zeros(len(near_indices), dtype=bool)
    best_sheet = np.zeros(n_total, dtype=bool)
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
        # Sheet coverage: for each ray, where the plane would place a return, allowing for the
        # grazing-ray cap the occluder model produces (denominator clipped at 0.25).
        denom_all = np.maximum(np.abs(unit_dirs_all @ normal), 0.25)
        sheet_m = np.abs(ranges - ortho_dist_origin / denom_all) <= 4.0 * cfg.plane_inlier_dist_m
        if int(sheet_m.sum()) > int(best_sheet.sum()):
            best_inliers = np.abs((near_xyz - p0) @ normal) <= cfg.plane_inlier_dist_m
            best_sheet = sheet_m
            best_ortho_d = ortho_dist_origin
            best_normal = normal.copy()

    # The contaminant set is the sheet the selected hypothesis predicts, not the hypothesis's raw
    # plane inliers: with sheet-based selection the inlier set can still be a floor plane, and
    # adding it back re-introduces the floor-stripping the selection was changed to avoid
    # (measured on a synthetic room: sheet 0.10 but plane inliers 0.67).
    is_contaminant = np.zeros(n_total, dtype=bool)
    if best_ortho_d > 0.0 and int(best_sheet.sum()) > int(0.15 * n_total):
        unit_dirs = xyz / np.maximum(ranges[:, None], 1e-6)
        denom = np.maximum(np.abs(unit_dirs @ best_normal), 0.25)
        expected_sheet_r = best_ortho_d / denom
        is_contaminant = np.abs(ranges - expected_sheet_r) <= 4.0 * cfg.plane_inlier_dist_m
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
