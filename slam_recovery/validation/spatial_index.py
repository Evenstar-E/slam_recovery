"""Exact Euclidean neighbourhood queries for point-cloud validation."""

import numpy as np


class RadiusIndex:
    """Exact "is there a reference point within r" queries without a distance matrix.

    The support test asks one question per query point: is any reference point within `radius`.
    Answering it with the full distance matrix is O(queries * points) per call, and the decision
    calls it for every candidate frame twice -- 4 s of a 4.4 s decision on a 100k-point map.
    Bucketing the reference into cells of exactly `radius` answers the same question exactly:
    a point within `radius` of a query must lie in one of the 27 cells around it, so no true
    neighbour is ever missed and no approximate structure is introduced.
    """

    def __init__(self, points: np.ndarray, cell: float) -> None:
        self.cell = float(cell)
        pts = np.asarray(points, dtype=np.float64)[:, :3]
        self.points = pts
        q = np.floor(pts / self.cell).astype(np.int64)
        self.origin = q.min(axis=0) - 1
        q = q - self.origin
        self.dims = q.max(axis=0) + 2
        lin = (q[:, 0] * self.dims[1] + q[:, 1]) * self.dims[2] + q[:, 2]
        order = np.argsort(lin, kind="stable")
        self.sorted_lin = lin[order]
        self.sorted_idx = order

    def within_radius_mask(self, queries: np.ndarray, radius: float) -> np.ndarray:
        queries = np.asarray(queries, dtype=np.float64)[:, :3]
        cell = np.floor(queries / self.cell).astype(np.int64) - self.origin
        inside = np.zeros(len(queries), dtype=bool)
        r2 = float(radius) * float(radius)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    c = cell + np.array([dx, dy, dz], dtype=np.int64)
                    valid = np.all((c >= 0) & (c < self.dims), axis=1)
                    if not valid.any():
                        continue
                    valid &= ~inside
                    lin = (c[:, 0] * self.dims[1] + c[:, 1]) * self.dims[2] + c[:, 2]
                    lo = np.searchsorted(self.sorted_lin, lin, side="left")
                    hi = np.searchsorted(self.sorted_lin, lin, side="right")
                    hit = valid & (hi > lo)
                    for i in np.flatnonzero(hit):
                        if inside[i]:
                            continue
                        cand = self.sorted_idx[lo[i]:hi[i]]
                        d2 = np.sum((self.points[cand] - queries[i]) ** 2, axis=1)
                        if d2.size and d2.min() <= r2:
                            inside[i] = True
        return inside
