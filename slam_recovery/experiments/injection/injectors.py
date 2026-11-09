"""Deterministic physical fault and degeneracy injectors (Section 8.5 & 4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import numpy as np


@dataclass(frozen=True)
class LiDARInjectionParams:
    """Parameters for LiDAR attenuation, correlated dropout, and range noise (Section 8.5)."""

    alpha_extinct: float = 0.03       # Extinction coefficient \alpha
    sigma_range_m: float = 0.03       # Range noise \sigma_r (0.01 mild, 0.03 med, 0.08 severe)
    target_drop_ratio: float = 0.30   # 0.10 mild, 0.30 med, 0.60 severe
    seed: int = 42


def inject_lidar_attenuation_and_dropout(
    points_xyzi: np.ndarray,
    params: LiDARInjectionParams,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply physical extinction I'_i = I_i exp(-2 \alpha r_i), correlated low-intensity dropout,
    and Gaussian range jitter along each beam direction.
     Purely deterministic given `params.seed` and `points_xyzi`.

    Args:
        points_xyzi: (N, 4) array of [x, y, z, intensity]
    Returns:
        (degraded_points_xyzi, kept_mask)
    """
    pts = np.asarray(points_xyzi, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] < 4:
        raise ValueError("points_xyzi must have shape (N, >=4)")

    rng = np.random.default_rng(params.seed)
    xyz = pts[:, :3]
    intensity = pts[:, 3]
    ranges = np.linalg.norm(xyz, axis=1)
    safe_ranges = np.maximum(ranges, 1e-6)
    unit_dirs = xyz / safe_ranges[:, None]

    attenuated_I = intensity * np.exp(-2.0 * params.alpha_extinct * ranges)

    # Correlated dropout: lower attenuated intensity -> higher drop probability
    if len(attenuated_I) > 0 and params.target_drop_ratio > 0.0:
        i_min, i_max = np.min(attenuated_I), np.max(attenuated_I)
        norm_I = (attenuated_I - i_min) / max(i_max - i_min, 1e-6)
        keep_prob = np.clip(
            1.0 - params.target_drop_ratio * (1.5 - norm_I),
            0.05,
            1.0,
        )
        # Rescale to hit target drop ratio on average
        keep_prob *= (1.0 - params.target_drop_ratio) / max(np.mean(keep_prob), 1e-6)
        keep_prob = np.clip(keep_prob, 0.0, 1.0)
        kept_mask = rng.uniform(0.0, 1.0, size=len(pts)) < keep_prob
    else:
        kept_mask = np.ones(len(pts), dtype=bool)

    range_noise = rng.normal(0.0, params.sigma_range_m, size=len(pts))
    new_ranges = np.maximum(0.05, ranges + range_noise)
    new_xyz = unit_dirs * new_ranges[:, None]

    out = pts.copy()
    out[:, :3] = new_xyz
    out[:, 3] = attenuated_I
    return out[kept_mask], kept_mask


def inject_plastic_bag_near_field_occlusion(
    points_xyzi: np.ndarray,
    occluded_azimuth_fraction: float = 0.75,
    bag_distance_m: float = 0.35,
    bag_Thickness_jitter_m: float = 0.008,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Simulate the MM-LINS floating plastic bag occlusion (Section 3.3 & 4.7):
    Replaces a large azimuth sector of true background returns with a dense,
    spatially self-consistent near-field planar/curved sheet around `bag_distance_m`.
    This creates high apparent geometric Fisher information (tight plane) while
    inducing severe innovation inconsistency against true robot motion.

    Returns:
        (corrupted_points_xyzi, is_bag_point_mask)
    """
    pts = np.asarray(points_xyzi, dtype=np.float64).copy()
    if pts.ndim != 2 or pts.shape[1] < 4:
        raise ValueError("points_xyzi must have shape (N, >=4)")

    rng = np.random.default_rng(seed)
    azimuth = np.arctan2(pts[:, 1], pts[:, 0])  # [-pi, pi]
    threshold_angle = -np.pi + 2.0 * np.pi * np.clip(occluded_azimuth_fraction, 0.0, 1.0)
    is_bag = azimuth <= threshold_angle

    num_bag = int(np.sum(is_bag))
    if num_bag > 0:
        # Project occluded rays onto a near-field tilted plane n^T p = bag_distance_m
        plane_normal = np.array([1.0, 0.15, 0.05], dtype=np.float64)
        plane_normal /= np.linalg.norm(plane_normal)

        bag_xyz = pts[is_bag, :3]
        norms = np.maximum(np.linalg.norm(bag_xyz, axis=1), 1e-6)
        dirs = bag_xyz / norms[:, None]
        denom = np.maximum(np.abs(dirs @ plane_normal), 0.25)
        d_sheet = (bag_distance_m / denom) + rng.normal(0.0, bag_Thickness_jitter_m, size=num_bag)
        pts[is_bag, :3] = dirs * d_sheet[:, None]
        pts[is_bag, 3] = 200.0 + rng.normal(0.0, 5.0, size=num_bag)

    return pts, is_bag


def inject_visual_exposure_drop(
    image_u8: np.ndarray,
    gain_g: float = 0.2,
    shot_noise_scale: float = 2.0,
    read_noise_std: float = 3.0,
    seed: int = 42,
) -> np.ndarray:
    """
    Simulate low-light visual degradation (Section 8.5):
    I'_{lin} = g * I_{lin} + n_{shot} + n_{read}.
    """
    img = np.asarray(image_u8, dtype=np.float64)
    rng = np.random.default_rng(seed)
    attenuated = gain_g * img
    shot = rng.normal(0.0, np.sqrt(np.maximum(attenuated, 0.0)) * shot_noise_scale)
    read = rng.normal(0.0, read_noise_std, size=img.shape)
    degraded = np.clip(np.round(attenuated + shot + read), 0, 255).astype(np.uint8)
    return degraded


def inject_visual_motion_blur(
    image_u8: np.ndarray,
    kernel_len: int = 15,
    angle_deg: float = 0.0,
    seed: int = 42,
) -> np.ndarray:
    """
    Simulate directional motion blur (Section 8.5): convolve with a normalised line kernel.

    Complements `inject_visual_exposure_drop`: the exposure drop removes photometric
    information, the blur removes geometric information, and a tightly-coupled LIVO is affected
    differently by the two.
    """
    img = np.asarray(image_u8)
    if kernel_len < 3:
        return img.copy()
    length = int(kernel_len) | 1  # keep the kernel centred
    kernel = np.zeros((length, length), dtype=np.float32)
    kernel[length // 2, :] = 1.0
    theta = np.deg2rad(float(angle_deg))
    c, s = np.cos(theta), np.sin(theta)
    # rotate the line kernel about the centre
    rot = np.array([[c, -s, 0.0], [s, c, 0.0]], dtype=np.float32)
    centre = (length - 1) / 2.0
    rot[0, 2] = centre - (c * centre - s * centre)
    rot[1, 2] = centre - (s * centre + c * centre)
    import cv2

    kernel = cv2.warpAffine(kernel, rot, (length, length))
    total = float(kernel.sum())
    if total <= 0:
        return img.copy()
    kernel /= total
    return cv2.filter2D(img, -1, kernel)


def inject_timestamp_offset(
    timestamps_ns: np.ndarray,
    offset_ms: float = 50.0,
    window_start_ns: int = 0,
    window_end_ns: int = int(1e18),
) -> np.ndarray:
    """
    Deterministically shift sensor timestamps within [window_start_ns, window_end_ns] by offset_ms.
    """
    ts = np.asarray(timestamps_ns, dtype=np.int64).copy()
    mask = (ts >= window_start_ns) & (ts <= window_end_ns)
    delta_ns = int(round(offset_ms * 1e6))
    ts[mask] += delta_ns
    return ts
