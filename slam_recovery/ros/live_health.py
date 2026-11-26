"""Causal observation scores for the online native replay controller."""

from typing import Optional, Tuple

import numpy as np

from slam_recovery.validation.spatial_index import RadiusIndex


# Same physical support radius and frame coverage as the transaction support check.
SUPPORT_RADIUS_M = 1.0
SUPPORT_FRACTION = 0.60
_NEIGHBOR_CELLS = np.array(
    [(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)]
)


def score_local_planes(
    index: RadiusIndex, world: np.ndarray, sigma: float, min_holdout: int
) -> Tuple[Optional[float], int, int]:
    """Score held-out points only against planes supported by nearby reference samples."""
    queries = world[::max(1, len(world) // 300)][:300]
    k = 8
    radius = index.cell
    cells = np.floor(queries / radius).astype(np.int64)[:, None, :] - index.origin
    cells = cells + _NEIGHBOR_CELLS
    valid = np.all((cells >= 0) & (cells < index.dims), axis=-1)
    keys = (cells[:, :, 0] * index.dims[1] + cells[:, :, 1]) * index.dims[2] + cells[:, :, 2]
    lo = np.searchsorted(index.sorted_lin, keys, side="left")
    hi = np.searchsorted(index.sorted_lin, keys, side="right")
    neighbors = []
    selected = []
    for i, query in enumerate(queries):
        ranges = [(a, b) for a, b in zip(lo[i, valid[i]], hi[i, valid[i]]) if a < b]
        if not ranges:
            continue
        ids = np.concatenate([index.sorted_idx[a:b] for a, b in ranges])
        if len(ids) < k:
            continue
        points = index.points[ids]
        diff = points - query
        dist_sq = np.einsum("ij,ij->i", diff, diff)
        nearest = np.argpartition(dist_sq, k - 1)[:k]
        if np.max(dist_sq[nearest]) > radius**2:
            continue
        neighbors.append(points[nearest])
        selected.append(query)

    n = len(selected)
    if n < min_holdout or n < SUPPORT_FRACTION * len(queries):
        return None, len(queries), n
    points = np.asarray(neighbors)
    center = np.mean(points, axis=1)
    diff = points - center[:, None, :]
    cov = np.einsum("mki,mkj->mij", diff, diff) / k
    _, eigenvectors = np.linalg.eigh(cov)
    residual = np.einsum("ij,ij->i", eigenvectors[:, :, 0], np.asarray(selected) - center)
    return float(np.mean((residual / sigma)**2)), len(queries), n
