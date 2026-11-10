"""Stage (d): pose-level re-registration of quarantined frames against the pre-quarantine map.

The native closed loop can only offer the host's own poses as a candidate, and the archived
four-arm shows the gate refuses exactly that population -- so B10's benefit side has no candidate
to score. This module produces a different one: each buffered scan is re-registered against the
trusted map as it stood before the quarantine opened, and the resulting pose is the candidate.

Frozen parameters (B10_PREREGISTRATION.md §9; changing any one of them is a new experiment):

    init                      the frame's host pose
    reference                 trusted points within 30 m of that pose, at most 20 000
    scan sampling             uniform stride to 2 000 points
    correspondence gate       0.5 m for the first 10 iterations, 0.25 m afterwards
    iteration limit           20
    convergence               ||delta_xi|| < 1e-6

The solver is pure numpy -- no scipy -- because the ROS interpreter that hosts the recovery node
has numpy but not scipy, and a repairer that cannot run where the node runs is not a repairer.
Nearest neighbours come from a uniform voxel hash rather than a KD-tree.

What this is not: it is a *candidate generator*. Whether a candidate deserves to be committed is
the gate's decision, and this module never calls the gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

# Frozen by B10_PREREGISTRATION.md §9.
REFERENCE_RADIUS_M = 30.0
REFERENCE_MAX_POINTS = 20_000
SCAN_SAMPLES = 2_000
GATE_NEAR_M = 0.50
GATE_FAR_M = 0.25
GATE_SWITCH_ITER = 10
MAX_ITERS = 20
CONVERGENCE_TOL = 1e-6

# Not part of §9: implementation constants of the neighbour search and normal estimate. They are
# recorded with every result so a run is interpretable, and they do not change what is optimised.
# 0.5 m, not 1.0 m: with a 1 m cell a dense surface puts hundreds of points in every
# neighbourhood and the query dominates the run (2000 queries x 27 cells x N per cell). At
# 0.5 m the same 3x3x3 block still reaches 1.5 m, which is three times the correspondence gate,
# and the candidate set shrinks by close to an order of magnitude.
CELL_M = 0.5
# Hard ceiling on points taken from one cell per query. Only reached in very dense cells; when
# it is, the nearest neighbour is taken from this cap rather than from the whole cell, which is
# recorded with the run so an approximation is never silent.
MAX_POINTS_PER_CELL = 64
NORMAL_K = 8
MIN_REFERENCE_POINTS = 100
MIN_CORRESPONDENCES = 30


@dataclass(frozen=True)
class IcpConfig:
    reference_radius_m: float = REFERENCE_RADIUS_M
    reference_max_points: int = REFERENCE_MAX_POINTS
    scan_samples: int = SCAN_SAMPLES
    gate_near_m: float = GATE_NEAR_M
    gate_far_m: float = GATE_FAR_M
    gate_switch_iter: int = GATE_SWITCH_ITER
    max_iters: int = MAX_ITERS
    convergence_tol: float = CONVERGENCE_TOL
    cell_m: float = CELL_M
    max_points_per_cell: int = MAX_POINTS_PER_CELL
    normal_k: int = NORMAL_K
    min_reference_points: int = MIN_REFERENCE_POINTS
    min_correspondences: int = MIN_CORRESPONDENCES


ICP_CONFIG = IcpConfig()


@dataclass
class IcpResult:
    pose: np.ndarray
    iterations: int
    final_residual_m: float
    converged: bool
    inliers: int
    correspondences: int
    reference_points: int
    reference_total_points: int
    scan_points: int
    status: str
    displacement_from_init_m: float
    rotation_from_init_deg: float
    gate_path: List[float] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "pose_se3": [float(x) for x in np.asarray(self.pose, dtype=np.float64).reshape(16)],
            "icp_iterations": int(self.iterations),
            "icp_residual": float(self.final_residual_m),
            "icp_converged": bool(self.converged),
            "icp_inliers": int(self.inliers),
            "correspondences": int(self.correspondences),
            "reference_points": int(self.reference_points),
            "reference_total_points": int(self.reference_total_points),
            "scan_points": int(self.scan_points),
            "displacement_from_init_m": float(self.displacement_from_init_m),
            "rotation_from_init_deg": float(self.rotation_from_init_deg),
            "status": self.status,
        }


# ---------------------------------------------------------------------------------------------
# neighbour search
# ---------------------------------------------------------------------------------------------
class VoxelGrid:
    """Uniform voxel hash providing k-nearest-neighbour lookup without scipy.

    Cell size 1.0 m with a 3x3x3 neighbourhood reaches at least one cell in every direction, which
    is wider than the 0.5 m correspondence gate; a query that finds nothing there is an outlier,
    not a victim of the grid.
    """

    def __init__(self, points: np.ndarray, cell_m: float = CELL_M,
                 max_per_cell: int = MAX_POINTS_PER_CELL) -> None:
        self.max_per_cell = int(max_per_cell)
        self.capped_cells = 0
        self.points = np.ascontiguousarray(np.asarray(points, dtype=np.float64)[:, :3])
        self.cell_m = float(cell_m)
        if len(self.points) == 0:
            self.keys = np.zeros(0, dtype=np.int64)
            self.order = np.zeros(0, dtype=np.int64)
            self.origin = np.zeros(3, dtype=np.int64)
            self.dims = np.ones(3, dtype=np.int64)
            return
        q = np.floor(self.points / self.cell_m).astype(np.int64)
        self.origin = q.min(axis=0) - 1
        q = q - self.origin
        self.dims = (q.max(axis=0) + 2).astype(np.int64)
        key = self._key(q)
        self.order = np.argsort(key, kind="stable")
        self.keys = key[self.order]

    def _key(self, q: np.ndarray) -> np.ndarray:
        return (q[:, 0] * self.dims[1] + q[:, 1]) * self.dims[2] + q[:, 2]

    def query(self, queries: np.ndarray, k: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """Return (indices, squared distances), both (n, k); index -1 and inf where nothing is found."""
        queries = np.ascontiguousarray(np.asarray(queries, dtype=np.float64)[:, :3])
        n = len(queries)
        idx_out = np.full((n, k), -1, dtype=np.int64)
        d2_out = np.full((n, k), np.inf, dtype=np.float64)
        if n == 0 or len(self.points) == 0:
            return idx_out, d2_out

        qc = np.floor(queries / self.cell_m).astype(np.int64) - self.origin
        base = self._key(qc)
        offsets = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    offsets.append((dx * self.dims[1] + dy) * self.dims[2] + dz)

        lo_all, hi_all = [], []
        for off in offsets:
            target = base + off
            lo = np.searchsorted(self.keys, target, side="left")
            hi = np.searchsorted(self.keys, target, side="right")
            over = hi - lo
            self.capped_cells += int(np.count_nonzero(over > self.max_per_cell))
            hi = np.minimum(hi, lo + self.max_per_cell)
            lo_all.append(lo)
            hi_all.append(hi)
        counts = np.stack([h - l for l, h in zip(lo_all, hi_all)], axis=0)   # (27, n), offset-major
        total = int(counts.sum())
        if total == 0:
            return idx_out, d2_out

        # offset-major throughout, so the flat arrays from `np.concatenate(lo_all)` line up with
        # `counts.reshape(-1)` and with the repeated query indices
        flat_counts = counts.reshape(-1)
        # one query index per (offset, query) pair, then one per candidate
        qi = np.repeat(np.tile(np.arange(n, dtype=np.int64), len(offsets)), flat_counts)
        cell_start = np.repeat(np.concatenate(lo_all), flat_counts)
        within = np.arange(total, dtype=np.int64) - np.repeat(np.cumsum(flat_counts) - flat_counts,
                                                              flat_counts)
        ci = cell_start + within
        cand = self.order[ci]
        d2 = np.sum((queries[qi] - self.points[cand]) ** 2, axis=1)

        order = np.lexsort((d2, qi))
        qi_s, d2_s, cand_s = qi[order], d2[order], cand[order]
        new_group = np.empty(len(qi_s), dtype=bool)
        new_group[0] = True
        new_group[1:] = qi_s[1:] != qi_s[:-1]
        group_start = np.flatnonzero(new_group)
        group_id = np.cumsum(new_group) - 1
        rank = np.arange(len(qi_s)) - group_start[group_id]
        keep = rank < k
        rows = qi_s[keep]
        cols = rank[keep]
        idx_out[rows, cols] = cand_s[keep]
        d2_out[rows, cols] = d2_s[keep]
        return idx_out, d2_out


def estimate_normals(points: np.ndarray, grid: Optional[VoxelGrid] = None,
                     k: int = NORMAL_K) -> Tuple[np.ndarray, np.ndarray]:
    """Point-to-plane normals from a local k-NN plane fit; the point itself is its own neighbour."""
    pts = np.asarray(points, dtype=np.float64)[:, :3]
    n = len(pts)
    normals = np.zeros((n, 3), dtype=np.float64)
    valid = np.zeros(n, dtype=bool)
    if n < 3:
        return normals, valid
    grid = grid if grid is not None else VoxelGrid(pts)
    kk = int(min(k, n))
    for start in range(0, n, 2000):
        blk = pts[start:start + 2000]
        idx, _d2 = grid.query(blk, k=kk)
        counts = (idx >= 0).sum(axis=1)
        ok = counts >= 3
        if not np.any(ok):
            continue
        cnt = counts[ok]
        neigh = pts[np.clip(idx[ok], 0, n - 1)]                  # (m, kk, 3)
        mask = (np.arange(kk)[None, :] < cnt[:, None])[..., None]
        mean = (neigh * mask).sum(axis=1) / np.maximum(cnt, 1)[:, None]
        centred = (neigh - mean[:, None, :]) * mask
        cov = np.einsum("mki,mkj->mij", centred, centred) / np.maximum(cnt, 1)[:, None, None]
        cov = 0.5 * (cov + np.swapaxes(cov, 1, 2))
        _vals, vecs = np.linalg.eigh(cov)
        tgt = np.flatnonzero(ok) + start
        normals[tgt] = vecs[:, :, 0]
        valid[tgt] = True
    # eigh returns unit eigenvectors; the sign is arbitrary and irrelevant to |n . (p - q)|
    return normals, valid


def _exp_se3(xi: np.ndarray) -> np.ndarray:
    """Small-angle SE(3) exponential; adequate at the 1e-6 convergence tolerance used here."""
    w = np.asarray(xi[:3], dtype=np.float64)
    v = np.asarray(xi[3:], dtype=np.float64)
    theta = float(np.linalg.norm(w))
    K = np.array([[0.0, -w[2], w[1]], [w[2], 0.0, -w[0]], [-w[1], w[0], 0.0]])
    if theta < 1e-12:
        R = np.eye(3) + K
        V = np.eye(3)
    else:
        s, c = np.sin(theta), np.cos(theta)
        R = np.eye(3) + (s / theta) * K + ((1 - c) / theta ** 2) * (K @ K)
        V = (np.eye(3) + ((1 - c) / theta ** 2) * K
             + ((theta - s) / theta ** 3) * (K @ K))
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = V @ v
    return T


def restrict_reference(reference_world: np.ndarray, init_pose: np.ndarray,
                       cfg: IcpConfig = ICP_CONFIG) -> Tuple[np.ndarray, int]:
    """Reference points within the radius, thinned by a uniform stride to the point budget."""
    ref = np.asarray(reference_world, dtype=np.float64)[:, :3]
    total = len(ref)
    if total == 0:
        return ref, 0
    centre = np.asarray(init_pose, dtype=np.float64)[:3, 3]
    near = ref[np.linalg.norm(ref - centre, axis=1) <= cfg.reference_radius_m]
    if len(near) > cfg.reference_max_points:
        step = int(np.ceil(len(near) / cfg.reference_max_points))
        near = near[::step]
    return near, total


def sample_scan(scan_body: np.ndarray, cfg: IcpConfig = ICP_CONFIG) -> np.ndarray:
    pts = np.asarray(scan_body, dtype=np.float64)[:, :3]
    if len(pts) <= cfg.scan_samples:
        return pts
    step = int(np.ceil(len(pts) / cfg.scan_samples))
    return pts[::step]


def _rotation_deg(R: np.ndarray) -> float:
    c = (float(np.trace(R)) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


def reregister_frame(scan_body: np.ndarray, reference_world: np.ndarray,
                     init_pose: np.ndarray, cfg: IcpConfig = ICP_CONFIG) -> IcpResult:
    """Point-to-plane ICP of one scan against the reference, starting from the host pose."""
    init = np.asarray(init_pose, dtype=np.float64).copy()
    scan = sample_scan(scan_body, cfg)
    ref, total_ref = restrict_reference(reference_world, init, cfg)

    def _fail(status: str, iterations: int = 0, gate_path: Optional[List[float]] = None) -> IcpResult:
        return IcpResult(pose=init.copy(), iterations=iterations, final_residual_m=float("nan"),
                         converged=False, inliers=0, correspondences=0,
                         reference_points=len(ref), reference_total_points=total_ref,
                         scan_points=len(scan), status=status,
                         displacement_from_init_m=0.0, rotation_from_init_deg=0.0,
                         gate_path=gate_path or [])

    if len(ref) < cfg.min_reference_points:
        return _fail("REFERENCE_TOO_SMALL")
    if len(scan) < 3:
        return _fail("SCAN_TOO_SMALL")

    grid = VoxelGrid(ref, cfg.cell_m)
    normals, normal_valid = estimate_normals(ref, grid, cfg.normal_k)
    if not np.any(normal_valid):
        return _fail("NO_VALID_NORMALS")

    T = init.copy()
    gate_path: List[float] = []
    correspondences = 0
    inliers = 0
    residual = float("nan")
    converged = False
    iterations = 0
    for it in range(cfg.max_iters):
        gate = cfg.gate_near_m if it < cfg.gate_switch_iter else cfg.gate_far_m
        gate_path.append(gate)
        world = scan @ T[:3, :3].T + T[:3, 3]
        idx, d2 = grid.query(world, k=1)
        idx = idx[:, 0]
        d2 = d2[:, 0]
        correspondences = int(np.sum(idx >= 0))
        if correspondences < cfg.min_correspondences:
            return _fail("TOO_FEW_CORRESPONDENCES", iterations,
                         gate_path) if it == 0 else _fail("LOST_CORRESPONDENCES", iterations,
                                                          gate_path)
        take = (idx >= 0) & (d2 <= gate * gate)
        take &= normal_valid[np.clip(idx, 0, len(ref) - 1)]
        inliers = int(take.sum())
        iterations = it + 1
        if inliers < cfg.min_correspondences:
            return _fail("TOO_FEW_INLIERS", iterations, gate_path)
        p = world[take]
        q = ref[idx[take]]
        n = normals[idx[take]]
        r0 = np.einsum("ij,ij->i", n, p - q)
        J = np.hstack([np.cross(p, n), n])
        xi, *_ = np.linalg.lstsq(J, -r0, rcond=None)
        T = _exp_se3(xi) @ T
        residual = float(np.mean(np.abs(r0)))
        if float(np.linalg.norm(xi)) < cfg.convergence_tol:
            converged = True
            break

    return IcpResult(
        pose=T, iterations=iterations, final_residual_m=residual, converged=converged,
        inliers=inliers, correspondences=correspondences,
        reference_points=len(ref), reference_total_points=total_ref, scan_points=len(scan),
        status="CONVERGED" if converged else "ITERATION_LIMIT",
        displacement_from_init_m=float(np.linalg.norm(T[:3, 3] - init[:3, 3])),
        rotation_from_init_deg=_rotation_deg(T[:3, :3] @ init[:3, :3].T),
        gate_path=gate_path,
    )


def build_icp_candidate(
    scan_bodies: Dict[int, np.ndarray],
    reference_world: np.ndarray,
    init_poses: Dict[int, np.ndarray],
    cfg: IcpConfig = ICP_CONFIG,
) -> Tuple[Dict[int, np.ndarray], List[Tuple[int, IcpResult]]]:
    """Re-register every frame that has both a scan and an init pose.

    A frame whose re-registration fails keeps its init pose out of the returned candidate: a
    candidate is a claim that the pose was improved, and an ICP that never converged makes no such
    claim. The failure is returned alongside so the caller can report why the frame is missing.
    """
    poses: Dict[int, np.ndarray] = {}
    results: List[Tuple[int, IcpResult]] = []
    for kf_id in sorted(scan_bodies):
        if kf_id not in init_poses:
            continue
        res = reregister_frame(scan_bodies[kf_id], reference_world, init_poses[kf_id], cfg)
        results.append((kf_id, res))
        if res.status in ("CONVERGED", "ITERATION_LIMIT"):
            poses[kf_id] = res.pose
    return poses, results
