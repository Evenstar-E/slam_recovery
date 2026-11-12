#!/usr/bin/env python3
"""C-2 research patch: a spatial evaluation sample for the point-to-plane FIM.

NOT applied to production. This module re-implements `compute_6dof_point_to_plane_fim` with two
changes and nothing else, so the patch can be reviewed as a diff and the numeric consequences
measured before anyone integrates it.

  change 1  evaluation sample : voxel centroids at a fixed 0.25 m, instead of `pts[::step]` whose
                                step is a function of the input point count
  change 2  neighbourhood     : every point within 0.6 m, instead of the 15 nearest by count

Parameters are fixed here and not searched: 0.25 m is the four-arm experiment's VOXEL_CELL and is
the same order as the reference resolution used elsewhere; 0.6 m is 2.4x the voxel, i.e. the
nearest layer of surface that a plane fit can use without reaching across separate surfaces.

Everything else (mean over points, 1/sigma^2, the 2.0 m truncation is not in this function, the
eigen analysis, the weak-direction selection, the 1e-6 regularisation) is copied unchanged.

    python -I docs/gate_method_research_20261110/c2_fim_spatial.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "docs/gate_method_research_20261110")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

VOXEL_M = 0.25
RADIUS_M = 0.6
MIN_NEIGHBOURS = 6
MAX_EVAL_POINTS = 1200
MAX_K = 15
SIGMA_FIM = 0.075


def voxel_centroids(points: np.ndarray, voxel_m: float = VOXEL_M) -> np.ndarray:
    """Centroid per occupied voxel. Duplication- and order-invariant by construction."""
    pts = np.asarray(points, dtype=np.float64)[:, :3]
    if not len(pts):
        return pts
    keys = np.floor(pts / float(voxel_m)).astype(np.int64)
    order = np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))
    keys, pts = keys[order], pts[order]
    new = np.ones(len(pts), dtype=bool)
    new[1:] = np.any(keys[1:] != keys[:-1], axis=1)
    starts = np.flatnonzero(new)
    ends = np.append(starts[1:], len(pts))
    return np.array([pts[s:e].mean(axis=0) for s, e in zip(starts, ends)])


def fim_spatial(points_xyz, sigma_meas_m=SIGMA_FIM, voxel_m=VOXEL_M, radius_m=RADIUS_M,
                max_eval_points=MAX_EVAL_POINTS, neighbour_mode="radius"):
    """neighbour_mode="radius" drops points with fewer than MIN_NEIGHBOURS inside the radius, which
    makes the mean's denominator density-dependent; "knn" keeps a fixed count per point instead."""
    """Same contract as compute_6dof_point_to_plane_fim, spatial sample and radius neighbours."""
    pts = np.asarray(points_xyz, dtype=np.float64)[:, :3]
    vox = voxel_centroids(pts, voxel_m)
    if len(vox) > max_eval_points:
        # deterministic by geometry, not by input order: keep the lexicographically first voxels
        idx = np.lexsort((vox[:, 2], vox[:, 1], vox[:, 0]))[:max_eval_points]
        vox = vox[idx]
    m = len(vox)
    fallback = (np.eye(6) * 1e-3, np.eye(6) * 1e3, 1e-3, 1e-3,
                np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0]))
    if m < MIN_NEIGHBOURS + 1:
        return fallback

    diff = vox[:, None, :] - vox[None, :, :]
    dist_sq = np.sum(diff ** 2, axis=-1)
    if neighbour_mode == "radius":
        within = dist_sq <= radius_m ** 2
        n_neigh = within.sum(axis=1) - 1          # exclude self
        usable = n_neigh >= MIN_NEIGHBOURS
        if usable.sum() < 10:
            return fallback
        vox = vox[usable]
        within = within[np.ix_(usable, usable)]
    else:
        kth = min(MAX_K, len(vox) - 1)
        idx = np.argpartition(dist_sq, kth=kth, axis=1)[:, 1:kth + 1]
        within = np.zeros_like(dist_sq, dtype=bool)
        np.put_along_axis(within, idx, True, axis=1)
    m = len(vox)

    normals = np.zeros((m, 3))
    for i in range(m):
        neigh = vox[within[i]]
        centered = neigh - neigh.mean(axis=0)
        cov = centered.T @ centered / max(len(neigh), 1)
        _, vecs = np.linalg.eigh(cov)
        normals[i] = vecs[:, 0]

    p_cross_n = np.cross(vox, normals)
    J = np.hstack([p_cross_n, normals])
    fim = (1.0 / max(float(sigma_meas_m) ** 2, 1e-6)) * (J.T @ J) / float(m)
    fim = fim + np.eye(6) * 1e-6
    cov = np.linalg.inv(fim)
    vals_r, vecs_r = np.linalg.eigh(0.5 * (fim[:3, :3] + fim[:3, :3].T))
    vals_t, vecs_t = np.linalg.eigh(0.5 * (fim[3:, 3:] + fim[3:, 3:].T))
    vals_6, vecs_6 = np.linalg.eigh(0.5 * (fim + fim.T))
    weak = np.zeros(6)
    if vals_6[0] < 0.25 * min(vals_r[0], vals_t[0]):
        v6 = vecs_6[:, 0]
        weak = v6 / max(float(np.linalg.norm(v6)), 1e-12)
        if np.linalg.norm(weak[:3]) >= np.linalg.norm(weak[3:]):
            vals_r[0] = vals_6[0]
        else:
            vals_t[0] = vals_6[0]
    elif vals_r[0] < vals_t[0]:
        weak[:3] = vecs_r[:, 0]
    else:
        weak[3:] = vecs_t[:, 0]
    return fim, cov, float(vals_r[0]), float(vals_t[0]), weak


def main():
    from c1_fim_controls import load_scan, fim as fim_old, project
    pts = load_scan()
    old_info, _, old_r, old_t, old_weak = fim_old(pts)
    new_info, _, new_r, new_t, new_weak = fim_spatial(pts)

    def consistency(fn):
        # One fixed physical direction for every input size: the full cloud's own weak direction
        # under this method. Comparing each cloud along its OWN weak direction would confound a
        # change of matrix with a change of direction.
        _, _, _, _, w_full = fn(pts)
        v_fixed = np.asarray(w_full, dtype=np.float64)
        v_fixed = v_fixed / max(np.linalg.norm(v_fixed), 1e-12)
        rows = []
        for label, cloud in (("8000", pts), ("4000_half", pts[::2]),
                             ("16000_duplicated", np.vstack([pts, pts])),
                             ("32000_quadrupled", np.vstack([pts] * 4))):
            info, _, _, _, weak = fn(cloud)
            rows.append({"input": label, "points": len(cloud),
                         "projection": round(project(v_fixed, info), 4),
                         "min_eig_rot": round(float(min(np.linalg.eigvalsh(info[:3, :3]))), 4),
                         "min_eig_trans": round(float(min(np.linalg.eigvalsh(info[3:, 3:]))), 4)})
        return rows

    old_rows = consistency(fim_old)
    new_rows = consistency(fim_spatial)
    knn_rows = consistency(lambda c: fim_spatial(c, neighbour_mode="knn"))

    def spread(rows, key):
        vals = [r[key] for r in rows]
        return round((max(vals) - min(vals)) / max(abs(np.mean(vals)), 1e-12), 4)

    v_old = old_weak / np.linalg.norm(old_weak)
    v_new = new_weak / np.linalg.norm(new_weak)
    out = {
        "_meta": {"what": "C-2 research patch, not integrated",
                  "voxel_m": VOXEL_M, "radius_m": RADIUS_M, "min_neighbours": MIN_NEIGHBOURS,
                  "max_eval_points": MAX_EVAL_POINTS, "sigma_fim": SIGMA_FIM,
                  "changes": ["voxel centroid sample", "radius neighbourhood"],
                  "unchanged": ["mean over points", "1/sigma^2", "eigen analysis", "weak direction",
                                "1e-6 regularisation"]},
        "old_stride_knn": {"rows": old_rows, "projection_spread": spread(old_rows, "projection"),
                           "min_eig_trans_spread": spread(old_rows, "min_eig_trans")},
        "new_voxel_radius": {"rows": new_rows, "projection_spread": spread(new_rows, "projection"),
                             "min_eig_trans_spread": spread(new_rows, "min_eig_trans")},
        "new_voxel_knn": {"rows": knn_rows, "projection_spread": spread(knn_rows, "projection"),
                          "min_eig_trans_spread": spread(knn_rows, "min_eig_trans")},
        "same_scan_difference": {
            # each method's own weak direction in its own matrix
            "projection_old_own_v": round(project(v_old, old_info), 4),
            "projection_new_own_v": round(project(v_new, new_info), 4),
            # the old weak direction evaluated in both matrices: same physical direction, two bases
            "old_v_in_old": round(project(v_old, old_info), 4),
            "old_v_in_new": round(project(v_old, new_info), 4),
            "min_eig_rot_old_new": [round(old_r, 4), round(new_r, 4)],
            "min_eig_trans_old_new": [round(old_t, 4), round(new_t, 4)],
        },
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "c2_fim_spatial_results.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
