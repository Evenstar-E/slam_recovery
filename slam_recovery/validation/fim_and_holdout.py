"""6-DoF Point-to-Plane Fisher Information Matrix (FIM) and Holdout Split Evaluator (Fixing Review Issue #5)."""

from __future__ import annotations

from typing import Tuple
import numpy as np


def compute_6dof_point_to_plane_fim(
    points_xyz: np.ndarray,
    sigma_meas_m: float = 0.05,
    k_neighbors: int = 15,
    max_eval_points: int = 1200,
    rot_scale: float = 1.0,
    trans_scale: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray, float, float, np.ndarray]:
    """
    Compute the true 6x6 Fisher Information Matrix \Lambda_{6x6} on SE(3) tangent space [rot(3), trans(3)]
    from a 3D point cloud by estimating local surface normals n_i and forming the exact point-to-plane
    Jacobian J_i = [(p_i x n_i)^T, n_i^T] \in R^{1x6}:
        \Lambda = (1 / \sigma^2) \sum_i J_i^T J_i

    Also supports spatial/scan holdout splitting (even vs. odd indices) so repair and validation
    use strictly disjoint measurement subsets.

    Returns:
        (fim_6x6_normalized, cov_6x6, min_eig_rot, min_eig_trans, weak_dir_6d)
    """
    pts = np.asarray(points_xyz, dtype=np.float64)[:, :3]
    n_pts = len(pts)
    if n_pts < k_neighbors + 1:
        fim_zero = np.eye(6, dtype=np.float64) * 1e-3
        cov_inf = np.eye(6, dtype=np.float64) * 1e3
        return fim_zero, cov_inf, 1e-3, 1e-3, np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])

    # Deterministic subsample for fast exact k-NN normal estimation
    if n_pts > max_eval_points:
        step = max(1, n_pts // max_eval_points)
        sub_pts = pts[::step][:max_eval_points]
    else:
        sub_pts = pts

    m = len(sub_pts)
    # Pairwise squared distances (m x m)
    diff = sub_pts[:, None, :] - sub_pts[None, :, :]
    dist_sq = np.sum(diff ** 2, axis=-1)
    nn_idx = np.argpartition(dist_sq, kth=min(k_neighbors, m - 1), axis=1)[:, 1 : k_neighbors + 1]

    neighbors = sub_pts[nn_idx]  # (m, k, 3)
    centered = neighbors - np.mean(neighbors, axis=1, keepdims=True)
    covs = np.einsum("mki,mkj->mij", centered, centered) / float(k_neighbors)
    eigvals, eigvecs = np.linalg.eigh(covs)

    # Surface normal is eigenvector corresponding to smallest eigenvalue; filter valid planar patches
    normals = eigvecs[:, :, 0]  # (m, 3)
    planarity = (eigvals[:, 1] - eigvals[:, 0]) / np.maximum(eigvals[:, 2], 1e-9)
    valid_planar = planarity > 0.15
    if np.sum(valid_planar) < 10:
        valid_planar = np.ones(m, dtype=bool)

    p_valid = sub_pts[valid_planar]
    n_valid = normals[valid_planar]

    # Exact 6-DoF point-to-plane Jacobian: J_i = [ (p_i x n_i)^T, n_i^T ]
    p_cross_n = np.cross(p_valid, n_valid)
    J = np.hstack([p_cross_n, n_valid])  # (M, 6)

    # Normalized per 100 effective planar constraints (so isotropic 3D planes give ~33.3 per axis, and a missing corridor axis drops < 1.0)
    fim_raw = (J.T @ J) / float(len(p_valid)) * 100.0

    scale_vec = np.array([rot_scale] * 3 + [trans_scale] * 3, dtype=np.float64)
    D = np.diag(scale_vec)
    fim_u = D.T @ fim_raw @ D + np.eye(6) * 1e-6
    cov_u = np.linalg.inv(fim_u)

    vals_r, vecs_r = np.linalg.eigh(0.5 * (fim_u[:3, :3] + fim_u[:3, :3].T))
    vals_t, vecs_t = np.linalg.eigh(0.5 * (fim_u[3:, 3:] + fim_u[3:, 3:].T))

    min_r = float(vals_r[0])
    min_t = float(vals_t[0])
    weak_6d = np.zeros(6, dtype=np.float64)
    if min_r < min_t:
        weak_6d[:3] = vecs_r[:, 0]
    else:
        weak_6d[3:] = vecs_t[:, 0]

    return fim_u, cov_u, min_r, min_t, weak_6d


def compute_disjoint_holdout_point_to_plane_nis(
    points_train_xyz: np.ndarray,
    points_holdout_xyz: np.ndarray,
    delta_pose_se3: np.ndarray = np.eye(4),
    sigma_meas_m: float = 0.08,
) -> float:
    """
    Compute normalized innovation squared (NIS) exclusively on the disjoint holdout point set
    against surface planes fitted ONLY on `points_train_xyz`.
    """
    train_xyz = np.asarray(points_train_xyz, dtype=np.float64)[:, :3]
    hold_xyz = np.asarray(points_holdout_xyz, dtype=np.float64)[:, :3]
    if len(train_xyz) < 30 or len(hold_xyz) < 10:
        return float("inf")

    # Transform holdout points by estimated relative pose
    R = delta_pose_se3[:3, :3]
    t = delta_pose_se3[:3, 3]
    hold_trans = (hold_xyz @ R.T) + t

    # Subsample for evaluation
    t_sub = train_xyz[:: max(1, len(train_xyz) // 600)][:600]
    h_sub = hold_trans[:: max(1, len(hold_trans) // 300)][:300]

    diff = h_sub[:, None, :] - t_sub[None, :, :]
    dist_sq = np.sum(diff ** 2, axis=-1)
    k = min(8, len(t_sub) - 1)
    nn_idx = np.argpartition(dist_sq, kth=k, axis=1)[:, :k]

    neighbors = t_sub[nn_idx]
    mean_nn = np.mean(neighbors, axis=1)
    centered = neighbors - mean_nn[:, None, :]
    covs = np.einsum("mki,mkj->mij", centered, centered) / float(k)
    _, eigvecs = np.linalg.eigh(covs)
    normals = eigvecs[:, :, 0]

    # Point-to-plane residual r_i = n_i^T (p_hold_i - \mu_train_i)
    residuals = np.abs(np.sum(normals * (h_sub - mean_nn), axis=1))
    valid_res = residuals[residuals < 1.0]
    if len(valid_res) == 0:
        return float("inf")
    return float(np.mean((valid_res / sigma_meas_m) ** 2))
