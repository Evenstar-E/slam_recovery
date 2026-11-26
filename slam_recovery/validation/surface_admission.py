"""Opt-in map admission using later observations registered outside the repair branch."""

from dataclasses import dataclass
from itertools import product
from typing import Optional, Sequence, Tuple

import numpy as np

from .spatial_index import RadiusIndex


VOXEL_M = 0.10
TOLERANCE_M = 0.15
MIN_GAIN_PP = 5
_NEIGHBOR_STEPS = [(x, y, z) for x, y, z in product((-1, 0, 1), repeat=3)
                   if x * x + y * y + z * z <= 2]


@dataclass(frozen=True)
class SurfaceView:
    """Unmodified validation scan, in the gauge of the trusted pre-fault checkpoint."""

    frame_id: str
    station_id: str
    stamp_ns: int
    xyz_world: np.ndarray


@dataclass(frozen=True)
class SurfaceEvidence:
    status: str
    reason: str
    view_ids: Tuple[str, ...] = ()
    reference_voxels: int = 0
    added_voxels: int = 0
    unverified_added_voxels: int = 0
    covered_before: int = 0
    covered_after: int = 0

    @property
    def coverage_gain(self) -> Optional[float]:
        if self.reference_voxels == 0:
            return None
        return (self.covered_after - self.covered_before) / self.reference_voxels


def voxel_keys(points: np.ndarray, voxel_m: float = VOXEL_M) -> np.ndarray:
    xyz = np.asarray(points, dtype=np.float64)
    if xyz.ndim != 2 or xyz.shape[1] != 3 or not np.isfinite(xyz).all():
        raise ValueError("expected finite XYZ array of shape (N, 3)")
    return np.unique(np.floor(xyz / voxel_m).astype(np.int64), axis=0)


def centers(keys, voxel_m: float = VOXEL_M) -> np.ndarray:
    return (np.asarray(keys, dtype=np.float64).reshape(-1, 3) + 0.5) * voxel_m


def nearby(reference: np.ndarray, queries: np.ndarray, radius: float) -> np.ndarray:
    if not len(reference) or not len(queries):
        return np.zeros(len(queries), dtype=bool)
    return RadiusIndex(reference, radius).within_radius_mask(queries, radius)


def surface_admission(
    trusted_keys,
    patch_keys,
    views: Sequence[SurfaceView],
    *,
    candidate_end_ns: Optional[int],
    decision_ns: Optional[int],
) -> SurfaceEvidence:
    """Admit an additive patch only when every added voxel has two-view support.

    Only independently registered scans between the candidate window and the decision may
    be supplied. The caller owns registration and must keep these scans out of construction.
    This gate neither receives survey data nor classifies unknown geometry as free space.
    """
    if candidate_end_ns is None or decision_ns is None:
        return SurfaceEvidence("MISSING", "unbound_candidate_or_decision_time")

    first = second = None
    for view in sorted(views, key=lambda view: (view.stamp_ns, view.frame_id)):
        if not candidate_end_ns < view.stamp_ns <= decision_ns:
            continue
        if not view.frame_id or not view.station_id or not len(view.xyz_world):
            continue
        if first is None:
            first = view
        elif (view.stamp_ns > first.stamp_ns and view.frame_id != first.frame_id
              and view.station_id != first.station_id):
            second = view
            break
    if second is None:
        return SurfaceEvidence("MISSING", "fewer_than_two_causal_heldout_views")

    view_ids = (first.frame_id, second.frame_id)
    add = centers(sorted({key for key in patch_keys if key not in trusted_keys}))
    first_keys, second_keys = (voxel_keys(view.xyz_world) for view in (first, second))
    a, b = centers(first_keys), centers(second_keys)
    radius = TOLERANCE_M
    # A symmetric intersection in metric space avoids using one station's visibility as truth.
    shared_keys = np.concatenate((first_keys[nearby(b, a, radius)],
                                  second_keys[nearby(a, b, radius)]))
    reference_keys = np.unique(shared_keys, axis=0)
    reference = centers(reference_keys)
    if not len(reference):
        return SurfaceEvidence("MISSING", "no_two_view_reference", view_ids)

    supported = nearby(a, add, radius) & nearby(b, add, radius)
    # On the frozen 0.10 m grid, 0.15 m includes axial and face-diagonal neighbors.
    # Query occupied keys directly to avoid indexing the entire trusted map on every event.
    before = np.fromiter(
        (any((x + dx, y + dy, z + dz) in trusted_keys for dx, dy, dz in _NEIGHBOR_STEPS)
         for x, y, z in reference_keys.tolist()), dtype=bool, count=len(reference),
    )
    after = before | nearby(add, reference, radius)
    unsupported = len(add) - int(supported.sum())
    new_covered = int(after.sum()) - int(before.sum())
    if unsupported:
        status, reason = "FAILED", "added_voxels_without_two_view_support"
    elif 100 * new_covered < MIN_GAIN_PP * len(reference):
        status, reason = "FAILED", "insufficient_heldout_coverage_gain"
    else:
        status, reason = "PASSED", "heldout_coverage_gain_and_two_view_support"
    return SurfaceEvidence(status, reason, view_ids, len(reference), len(add), unsupported,
                           int(before.sum()), int(after.sum()))
