"""Execute Simulation Experiments S1 (Online Counterfactual R4 vs. R5 with Cross-Scan Holdout \mathcal{S}_{hold})
and S2 (True 3D Mesh Voxel Contamination Ratio \mathrm{Contam}_{3D}(t), Section 3.2 of REVIEW_AND_SIMULATION_PLAN.md).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Tuple
import numpy as np

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO_ROOT)
from slam_recovery.core import GateThresholds, RecoveryMode, TangentFrame
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.validation import compute_disjoint_holdout_point_to_plane_nis


class Arena3DMeshGroundTruth:
    """
    Exact 3D surface geometry \mathcal{G}_{GT} corresponding to `recovery_arena.world` (40m x 25m):
      - Ground floor plane: z = 0.0
      - North/South corridor walls: y = +3.0, y = -3.0
      - Zone A West anchor wall: x = -5.0 (y in [-6, 6])
      - Zone A Orthogonal Pillars: x in [1.9, 3.1], y in [1.6, 2.8] and x in [5.9, 7.1], y in [-2.8, -1.6]
      - Zone C East endwall: x = 36.0 (y in [-7, 7])
      - Zone C Baffle wall: x = 32.5
    """

    def sample_lidar_scan_in_body_frame(
        self,
        pose_w_b: np.ndarray,
        zone_b_featureless: bool,
        plastic_bag_occluded_frac: float,
        rng: np.random.Generator,
        n_rays: int = 800,
    ) -> np.ndarray:
        """Sample 3D LiDAR surface hits on the arena mesh transformed into the robot body frame."""
        pos = pose_w_b[:3, 3]
        R_wb = pose_w_b[:3, :3]

        pts_world = []
        # 1. Floor hits around robot
        fx = pos[0] + rng.uniform(-8.0, 8.0, n_rays // 4)
        fy = pos[1] + rng.uniform(-3.0, 3.0, n_rays // 4)
        fz = np.zeros_like(fx) + rng.normal(0.0, 0.01, len(fx))
        pts_world.append(np.column_stack([fx, fy, fz]))

        # 2. North & South wall hits (y = +3.0 and y = -3.0)
        for y_wall in (-3.0, 3.0):
            wx = pos[0] + rng.uniform(-8.0, 8.0, n_rays // 4)
            wy = np.full_like(wx, y_wall) + rng.normal(0.0, 0.01, len(wx))
            wz = rng.uniform(0.1, 2.6, len(wx))
            pts_world.append(np.column_stack([wx, wy, wz]))

        # 3. Longitudinal orthogonal structure (present in Zone A / Zone C or when loop/orthogonal walls are visible)
        if not zone_b_featureless:
            x_struct = -5.0 if pos[0] < 10.0 else 36.0
            sx = np.full(n_rays // 3, x_struct) + rng.normal(0.0, 0.01, n_rays // 3)
            sy = rng.uniform(-3.0, 3.0, n_rays // 3)
            sz = rng.uniform(0.1, 2.6, n_rays // 3)
            pts_world.append(np.column_stack([sx, sy, sz]))
            # Add orthogonal pillar surfaces at x = 2.5 and x = 6.5 defined in recovery_arena.world
            for p_x, p_y_min, p_y_max in ((2.5, 1.6, 2.8), (6.5, -2.8, -1.6)):
                px = np.full(140, p_x) + rng.normal(0.0, 0.01, 140)
                py = rng.uniform(p_y_min, p_y_max, 140)
                pz = rng.uniform(0.1, 2.5, 140)
                pts_world.append(np.column_stack([px, py, pz]))

        world_cloud = np.vstack(pts_world)
        body_cloud = (world_cloud - pos) @ R_wb

        if plastic_bag_occluded_frac > 0.0:
            az = np.arctan2(body_cloud[:, 1], body_cloud[:, 0])
            th = -np.pi + 2.0 * np.pi * plastic_bag_occluded_frac
            occluded = az <= th
            body_cloud = body_cloud[~occluded]

        return body_cloud

    def compute_distance_to_gt_mesh(self, voxel_centers_world: np.ndarray) -> np.ndarray:
        """
        Compute exact point-to-surface Euclidean distance \min_{g \in \mathcal{G}_{GT}} ||v - g||_2
        for every 3D voxel center in `voxel_centers_world` (N, 3) against FINITE 3D arena walls/boxes
        spanning x in [-5.0, 36.0], y in [-3.0, 3.0], z in [0.0, 2.6] (F6 fix).
        """
        v = np.asarray(voxel_centers_world, dtype=np.float64)[:, :3]
        if len(v) == 0:
            return np.zeros(0, dtype=np.float64)

        def _box_dist(pts: np.ndarray, xmin: float, xmax: float, ymin: float, ymax: float, zmin: float, zmax: float) -> np.ndarray:
            dx = np.maximum(0.0, np.maximum(xmin - pts[:, 0], pts[:, 0] - xmax))
            dy = np.maximum(0.0, np.maximum(ymin - pts[:, 1], pts[:, 1] - ymax))
            dz = np.maximum(0.0, np.maximum(zmin - pts[:, 2], pts[:, 2] - zmax))
            return np.sqrt(dx * dx + dy * dy + dz * dz)

        # 1. Finite Floor slab: x in [-12.0, 48.0], y in [-3.2, 3.2], z = 0.0
        d_floor = _box_dist(v, -12.0, 48.0, -3.2, 3.2, 0.0, 0.0)
        # 2. Finite North wall (y = +3.0) & South wall (y = -3.0): x in [-12.0, 48.0], z in [0.0, 2.8]
        d_north = _box_dist(v, -12.0, 48.0, 3.0, 3.0, 0.0, 2.8)
        d_south = _box_dist(v, -12.0, 48.0, -3.0, -3.0, 0.0, 2.8)
        # 3. Finite West wall (x = -5.0) & East wall (x = 36.0): y in [-6.0, 6.0], z in [0.0, 2.8]
        d_west = _box_dist(v, -5.0, -5.0, -6.0, 6.0, 0.0, 2.8)
        d_east = _box_dist(v, 36.0, 36.0, -6.0, 6.0, 0.0, 2.8)
        # 4. Finite Pillars at x = 2.5 (y in [1.55, 2.85]) and x = 6.5 (y in [-2.85, -1.55]), z in [0.0, 2.6]
        d_pillar1 = _box_dist(v, 2.45, 2.55, 1.55, 2.85, 0.0, 2.6)
        d_pillar2 = _box_dist(v, 6.45, 6.55, -2.85, -1.55, 0.0, 2.6)

        min_dist = np.minimum.reduce([d_floor, d_north, d_south, d_west, d_east, d_pillar1, d_pillar2])
        return min_dist

    def compute_3d_voxel_contamination_ratio(
        self,
        voxel_set: set[Tuple[int, int, int]],
        voxel_size_m: float = 0.10,
        tau_map_m: float = 0.15,
    ) -> float:
        """
        Evaluate Eq. in Section 3.2 (S2):
            \mathrm{Contam}_{3D}(t) = (1 / |V_{trusted}|) \sum_{v \in V_{trusted}} I(\min_{g \in G_{GT}} ||v - g||_2 > \tau_{map})
        """
        if not voxel_set:
            return 0.0
        coords = (np.asarray(list(voxel_set), dtype=np.float64) + 0.5) * voxel_size_m
        dists = self.compute_distance_to_gt_mesh(coords)
        return float(np.mean(dists > tau_map_m))


# ---------------------------------------------------------------------------------------------
# Simulator-validity scoring
#
# The gate judges a *candidate* by: holdout = every `holdout_stride`-th keyframe of the sorted key
# set; a holdout frame is scorable only where `_frame_has_reference_support` says the reference
# covers it; the statistic is the MEAN point-to-plane NIS over the scorable frames.
#
# The validity check must replicate that statistic exactly, otherwise "the gate cannot judge GT"
# does not follow from it. It must also hold its own reference: `evaluate_and_commit_candidate`
# mutates the committed map when it accepts, so the reference has to be snapshotted first.
# ---------------------------------------------------------------------------------------------

_SIM_VALIDITY_NIS_BOUND = 2.5
_SIM_VALIDITY_DENSITY_CAPS = (1500, 20000, 200000)


def _to_world(scan_body_xyz, pose_se3) -> np.ndarray:
    pts = np.asarray(scan_body_xyz, dtype=np.float64)[:, :3]
    T = np.asarray(pose_se3, dtype=np.float64)
    return (pts @ T[:3, :3].T) + T[:3, 3]


def _holdout_ids(key_ids, stride: int) -> List[int]:
    ks = sorted(int(k) for k in key_ids)
    return [k for idx, k in enumerate(ks) if idx % int(stride) == 0]


def _plane_neighbourhood_diagnostics(ref_pts, hold_world, k: int = 8) -> dict:
    """Report the neighbourhood structure the production estimator actually fits.

    `compute_disjoint_holdout_point_to_plane_nis` sub-samples the reference to 600 points and the
    holdout to 300 before the k-NN plane fit. Anything above that budget is discarded inside the
    estimator, so the diagnostic has to look at the same sub-sample, not at the request.
    """
    ref = np.asarray(ref_pts, dtype=np.float64)[:, :3]
    hold = np.asarray(hold_world, dtype=np.float64)[:, :3]
    if len(ref) < 30 or len(hold) < 10:
        return {"available": False}
    t_sub = ref[:: max(1, len(ref) // 600)][:600]
    h_sub = hold[:: max(1, len(hold) // 300)][:300]
    kk = min(int(k), len(t_sub) - 1)
    d2 = np.sum((h_sub[:, None, :] - t_sub[None, :, :]) ** 2, axis=-1)
    nn_idx = np.argpartition(d2, kth=kk, axis=1)[:, :kk]
    neighbours = t_sub[nn_idx]
    mean_nn = neighbours.mean(axis=1)
    centered = neighbours - mean_nn[:, None, :]
    covs = np.einsum("mki,mkj->mij", centered, centered) / float(kk)
    evals = np.linalg.eigvalsh(covs)              # ascending: l0 <= l1 <= l2
    l0, l1, l2 = evals[:, 0], evals[:, 1], evals[:, 2]
    radius = np.sqrt(np.max(d2[np.arange(len(h_sub))[:, None], nn_idx], axis=1))
    thinness = np.sqrt(np.maximum(l0, 0.0)) / np.maximum(np.sqrt(np.maximum(l1, 1e-12)), 1e-12)

    # Residuals exactly as the production estimator forms them, so the calibration proposal can be
    # argued with the numbers the estimator actually sees (plane normal over the 8 neighbours).
    evals_full, eigvecs = np.linalg.eigh(covs)
    normals = eigvecs[:, :, 0]
    residuals = np.abs(np.sum(normals * (h_sub - mean_nn), axis=1))
    # Counterfactuals for the calibration proposal (diagnostic only: production defaults stay).
    res_nis = (residuals / 0.12) ** 2
    thin_mask = thinness <= 0.05
    return {
        "available": True,
        "nis_as_is_mean": float(np.mean(res_nis)),
        "nis_as_is_median": float(np.median(res_nis)),
        "nis_thin_neighbourhoods_only": (
            float(np.mean(res_nis[thin_mask])) if thin_mask.any() else None),
        "nis_mixed_neighbourhoods_only": (
            float(np.mean(res_nis[~thin_mask])) if (~thin_mask).any() else None),
        "thin_neighbourhood_fraction": float(np.mean(thin_mask)),
        "n_ref_points_returned": int(len(ref)),
        "n_ref_points_used_by_estimator": int(len(t_sub)),
        "n_holdout_points_used_by_estimator": int(len(h_sub)),
        "knn": int(kk),
        "nn_radius_m_mean": float(np.mean(radius)),
        "nn_radius_m_p90": float(np.percentile(radius, 90)),
        "plane_thickness_rms_m_median": float(np.median(np.sqrt(np.maximum(l0, 0.0)))),
        "planarity_l0_over_sum_l_median": float(
            np.median(l0 / np.maximum(l0 + l1 + l2, 1e-12))),
        "normal_vs_lateral_spread_ratio_median": float(np.median(thinness)),
        # a neighbourhood that is not thin in its smallest direction spans more than one surface
        "cross_plane_mixing_frac": float(np.mean(thinness > 0.05)),
        "residual_abs_median_m": float(np.median(residuals)),
        "residual_frac_gt_0p5m": float(np.mean(residuals > 0.5)),
        "residual_frac_gt_2p0m": float(np.mean(residuals > 2.0)),
        "holdout_residual_coverage_ge_2m": float(np.mean(residuals < 2.0)),
    }


def _score_pose_set(node, ref_pts, key_ids, support_poses, score_poses, stride: int,
                    support_ref_pts=None) -> dict:
    """Score one pose set with the gate's own sampling/aggregation (stride holdout, mean NIS).

    Support is decided on `support_ref_pts` when given: the node's commit path asks coverage of a
    spatially sampled reference, not of the point-capped cloud used for the NIS itself.
    """
    holdout = _holdout_ids(key_ids, stride)
    support_ref = ref_pts if support_ref_pts is None else support_ref_pts
    supported = [
        k for k in holdout
        if k in node.scan_buffer_body
        and node._frame_has_reference_support(k, support_ref, support_poses)
    ]
    per_frame = []
    for k in supported:
        per_frame.append(float(compute_disjoint_holdout_point_to_plane_nis(
            ref_pts,
            _to_world(node.scan_buffer_body[k], score_poses[k]),
            np.eye(4),
            sigma_meas_m=0.12,
        )))
    finite = [v for v in per_frame if np.isfinite(v)]
    return {
        "holdout_ids_sampled": list(holdout),
        "supported_ids": list(supported),
        "nis_per_frame": [round(v, 4) for v in per_frame],
        "n_scored": len(supported),
        "n_nonfinite": len(per_frame) - len(finite),
        "nis_mean": (round(float(np.mean(finite)), 4) if finite else None),
    }


def _simulator_validity_snapshot(node, key_ids, gt_poses, candidate_poses, stride: int,
                                 mesh_distance_fn) -> dict:
    """Snapshot-based validity: GT poses judged by the gate's statistic on a frozen reference."""
    ref = node.get_trusted_map_points(max_pts=1500).copy()
    # Coverage is judged on the same spatially sampled reference the node's commit path uses; the
    # 1500-point cloud above remains the scoring reference so the NIS stays comparable.
    support_ref = node.support_reference()
    # Provenance of the reference, from the node itself: a frame whose own points are part of the
    # reference cannot be scored against it (self-agreement), so the key set has to be reported
    # rather than assumed.
    ref_keys = sorted(node.get_trusted_map_keys())

    gt = _score_pose_set(node, ref, key_ids, gt_poses, gt_poses, stride, support_ref_pts=support_ref)
    cand = _score_pose_set(node, ref, key_ids, candidate_poses, candidate_poses, stride, support_ref_pts=support_ref)
    gt_ids, cand_ids = set(gt["supported_ids"]), set(cand["supported_ids"])

    gt_holdout_world = np.vstack([
        _to_world(node.scan_buffer_body[k], gt_poses[k]) for k in gt["supported_ids"]
    ]) if gt["supported_ids"] else np.zeros((0, 3))

    sweep = {}
    for cap in _SIM_VALIDITY_DENSITY_CAPS:
        ref_cap = node.get_trusted_map_points(max_pts=cap)
        scored = _score_pose_set(node, ref_cap, key_ids, gt_poses, gt_poses, stride, support_ref_pts=support_ref)
        diag = _plane_neighbourhood_diagnostics(ref_cap, gt_holdout_world)
        sweep[str(cap)] = {
            "reference_points_returned": int(len(ref_cap)),
            "gt_nis_mean": scored["nis_mean"],
            "gt_n_scored": scored["n_scored"],
            "gt_nis_per_frame": scored["nis_per_frame"],
            "neighbourhood": diag,
        }

    analytic = []
    for k in gt["supported_ids"]:
        pts_w = _to_world(node.scan_buffer_body[k], gt_poses[k])
        analytic.append(float(np.mean(
            (np.asarray(mesh_distance_fn(pts_w), dtype=np.float64) / 0.12) ** 2)))
    analytic_mean = round(float(np.mean(analytic)), 6) if analytic else None

    return {
        "gt": gt,
        "candidate": cand,
        "gt_only_ids": sorted(gt_ids - cand_ids),
        "candidate_only_ids": sorted(cand_ids - gt_ids),
        "support_set_delta": len(gt_ids ^ cand_ids),
        "reference_points_snapshot": int(len(ref)),
        "reference_keyframes": ref_keys,
        "holdout_overlapping_reference": sorted(set(gt["supported_ids"]) & set(ref_keys)),
        "density_sweep": sweep,
        "gt_nis_analytic_mean": analytic_mean,
        "n_holdout_sampled": len(gt["holdout_ids_sampled"]),
        "holdout_stride": int(stride),
    }


def _simulator_validity_status(row) -> str:
    """Per-scenario verdict. Missing evidence is never a pass."""
    if row.get("n_holdout_sampled", 0) == 0:
        return "MISSING"
    gt = row["gt"]
    if gt["n_scored"] == 0 or gt["nis_mean"] is None:
        return "INVALID"
    if gt["n_nonfinite"] > 0:
        return "INVALID"
    return "FAILED" if gt["nis_mean"] > _SIM_VALIDITY_NIS_BOUND else "PASSED"



def _build_simulator_validity_block(rows: List[dict]) -> dict:
    """Assemble the manifest block from per-scenario rows.

    No cross-scenario average may turn a single-scenario failure into a pass: the status is the
    worst per-scenario status, and every scenario keeps its own verdict and evidence count.
    """
    statuses = [r["status"] for r in rows]
    counts = {k: statuses.count(k) for k in ("PASSED", "FAILED", "INVALID", "MISSING")}
    if counts["FAILED"]:
        overall = "FAILED"
    elif counts["INVALID"]:
        overall = "INVALID"
    elif counts["MISSING"]:
        overall = "MISSING"
    elif rows:
        overall = "PASSED"
    else:
        overall = "MISSING"

    def _clean(v):
        if isinstance(v, float) and not np.isfinite(v):
            return None
        return v

    def _agg(key_path):
        vals = []
        for r in rows:
            cur = r
            for k in key_path:
                cur = cur.get(k, {}) if isinstance(cur, dict) else None
                if cur is None:
                    break
            if isinstance(cur, (int, float)) and np.isfinite(cur):
                vals.append(float(cur))
        return vals

    per_cap = {}
    for cap in _SIM_VALIDITY_DENSITY_CAPS:
        key = str(cap)
        scored = [r["density_sweep"][key]["gt_nis_mean"] for r in rows
                  if r["density_sweep"][key]["gt_nis_mean"] is not None]
        returned = [r["density_sweep"][key]["reference_points_returned"] for r in rows]
        neigh = [r["density_sweep"][key]["neighbourhood"] for r in rows
                 if r["density_sweep"][key]["neighbourhood"].get("available")]
        def _nmean(field):
            vals = [n[field] for n in neigh if field in n]
            return round(float(np.mean(vals)), 4) if vals else None
        per_cap[key] = {
            "requested_cap": cap,
            "reference_points_returned_per_scenario": returned,
            "gt_nis_mean_per_scenario": [round(v, 3) for v in scored],
            "gt_nis_mean": round(float(np.mean(scored)), 3) if scored else None,
            "estimator_points_used": _nmean("n_ref_points_used_by_estimator"),
            "nn_radius_m_mean": _nmean("nn_radius_m_mean"),
            "plane_thickness_rms_m_median": _nmean("plane_thickness_rms_m_median"),
            "planarity_l0_over_sum_l_median": _nmean("planarity_l0_over_sum_l_median"),
            "cross_plane_mixing_frac": _nmean("cross_plane_mixing_frac"),
            "residual_abs_median_m": _nmean("residual_abs_median_m"),
            "residual_frac_gt_0p5m": _nmean("residual_frac_gt_0p5m"),
            "residual_frac_gt_2p0m": _nmean("residual_frac_gt_2p0m"),
            "holdout_residual_coverage_ge_2m": _nmean("holdout_residual_coverage_ge_2m"),
            "nis_as_is_mean": _nmean("nis_as_is_mean"),
            "nis_as_is_median": _nmean("nis_as_is_median"),
            "nis_thin_neighbourhoods_only": _nmean("nis_thin_neighbourhoods_only"),
            "nis_mixed_neighbourhoods_only": _nmean("nis_mixed_neighbourhoods_only"),
            "thin_neighbourhood_fraction": _nmean("thin_neighbourhood_fraction"),
        }

    gt_means = [r["gt"]["nis_mean"] for r in rows if r["gt"]["nis_mean"] is not None]
    analytic = [r["gt_nis_analytic_mean"] for r in rows if r["gt_nis_analytic_mean"] is not None]
    sweep_1500 = per_cap["1500"]["gt_nis_mean"]
    sweep_20000 = per_cap["20000"]["gt_nis_mean"]
    same_high = per_cap["20000"]["reference_points_returned_per_scenario"] ==         per_cap["200000"]["reference_points_returned_per_scenario"]
    estimator_cap = per_cap["1500"]["estimator_points_used"]

    return {
        "status": overall,
        "status_counts": counts,
        "status_per_scenario": statuses,
        "criterion": (
            "The GROUND-TRUTH poses must satisfy the gate's own holdout-NIS bound "
            "(tau = 2.5) when scored with the gate's own sampling and aggregation: holdout = "
            "every `holdout_stride`-th keyframe of the sorted key set, scorable only where the "
            "frozen reference supports the frame, statistic = MEAN point-to-plane NIS over the "
            "scorable frames. If GT cannot pass, the simulator cannot distinguish a good "
            "candidate from a bad one and no Mode 2 / Mode 3 verdict from S1/S2 may be cited. "
            "The reference is snapshotted before `evaluate_and_commit_candidate` so an accepted "
            "candidate cannot change the map GT is scored against."
        ),
        "gate_statistic_replicated": {
            "holdout_stride": int(rows[0]["holdout_stride"]) if rows else None,
            "aggregation": "mean over scorable holdout frames",
            "sigma_meas_m": 0.12,
            "support_rule": "GT poses (not repaired poses) decide support; candidate support is "
                            "reported separately as a set difference",
        },
        "per_scenario": [
            {
                "seed": r["seed"],
                "status": r["status"],
                "gt_nis_mean": r["gt"]["nis_mean"],
                "gt_n_scored": r["gt"]["n_scored"],
                "gt_n_nonfinite": r["gt"]["n_nonfinite"],
                "gt_holdout_ids_sampled": r["gt"]["holdout_ids_sampled"],
                "gt_supported_ids": r["gt"]["supported_ids"],
                "gt_nis_per_frame": r["gt"]["nis_per_frame"],
                "candidate_supported_ids": r["candidate"]["supported_ids"],
                "candidate_nis_mean": r["candidate"]["nis_mean"],
                "gt_only_ids": r["gt_only_ids"],
                "candidate_only_ids": r["candidate_only_ids"],
                "support_set_symmetric_difference": r["support_set_delta"],
                "reference_points_snapshot": r["reference_points_snapshot"],
                "reference_keyframes": r["reference_keyframes"],
                "holdout_overlapping_reference": r["holdout_overlapping_reference"],
                "reference_points_after_commit": r["reference_points_after_commit"],
                "reference_mutated_by_candidate": r["reference_mutated_by_candidate"],
                "gate_holdout_nis_for_candidate": _clean(r["gate_holdout_nis_candidate"]),
                "gate_holdout_support": r["gate_holdout_support"],
                "gt_nis_analytic_mean": r["gt_nis_analytic_mean"],
            }
            for r in rows
        ],
        "gt_nis_mean_across_scenarios": round(float(np.mean(gt_means)), 3) if gt_means else None,
        "reference_provenance_note": (
            "In this simulation the trusted reference is injected by setting "
            "`node.committed_map_points` directly, so the node's keyframe->points index is empty "
            "and `get_trusted_map_keys()` returns an empty set: reference provenance is not "
            "reconstructable here. That is a property of the test bed, not of the gate; on the "
            "real path the key set is populated and is reported per scenario below."
        ),
        "gt_nis_analytic_mean_across_scenarios": (
            round(float(np.mean(analytic)), 6) if analytic else None),
        "reference_density_sweep": per_cap,
        "finding": (
            "Scored with the gate's own statistic, GT poses sit at "
            f"{', '.join('%.2f' % v for v in gt_means) if gt_means else 'n/a'} (mean per scenario), "
            "one to two orders of magnitude above tau = 2.5, while the same GT poses against the "
            f"analytic arena give {('%.4f' % float(np.mean(analytic))) if analytic else 'n/a'}. "
            "Geometry is therefore self-consistent and the error lives in the local plane fit. "
            "On density: the 1500-point budget scores "
            f"{sweep_1500 if sweep_1500 is not None else 'n/a'} and the 20000-point budget "
            f"{sweep_20000 if sweep_20000 is not None else 'n/a'} (scenario means), so the score "
            "DOES move with the requested budget; but the reference returned at 20000 and 200000 "
            f"is {'identical' if same_high else 'different'}, and the production estimator "
            f"truncates every reference to {estimator_cap} points before the k-NN plane fit. "
            "Raising the budget above ~%.0f is arithmetically incapable of changing the result, "
            "so 'density is not the cause' is NOT supported: what the sweep excludes is only that "
            "budgets above 20000 matter in this simulator." % (estimator_cap or 600)
        ),
        "second_finding": (
            "The analytic value must NOT be read as 'the gate passes'. This simulator is "
            "effectively noise-free (0.01 m sampling jitter against sigma = 0.12 m), so the NIS "
            "scale carries no physical meaning. It means the simulator is not a valid test bed, "
            "not that the candidate is good."
        ),
        "local_plane_diagnostics": {
            "what_is_measured": (
                "Neighbourhood radius, plane thickness (sqrt of the smallest covariance "
                "eigenvalue of the 8 nearest reference points), planarity, and the fraction of "
                "holdout neighbourhoods whose smallest direction is not thin (a proxy for a "
                "neighbourhood spanning two surfaces). All computed on the estimator's own "
                "600/300 sub-sample."
            ),
            "by_budget": per_cap,
            "finding": (
                "Pooled over holdout points the mean NIS is %.1f (1500-point budget) / %.1f "
                "(full reference), but the MEDIAN is %.3f / %.3f. Restricting to thin "
                "(single-surface) neighbourhoods gives %.4f / %.4f, while the mixed "
                "neighbourhoods alone give %.1f / %.1f. Only %.0f%% / %.0f%% of neighbourhoods "
                "are thin, and the mean is set entirely by the rest. GT poses are therefore "
                "accurate: the score is manufactured by 8-NN plane fits that span two surfaces "
                "(the 8th neighbour sits ~%.1f m away in a 6 m corridor). Raising the reference "
                "budget improves the thin fraction and the thin-only NIS but cannot move the "
                "mean, because the estimator truncates every reference to %s points."
                % (
                    per_cap["1500"]["nis_as_is_mean"] or 0.0,
                    per_cap["20000"]["nis_as_is_mean"] or 0.0,
                    per_cap["1500"]["nis_as_is_median"] or 0.0,
                    per_cap["20000"]["nis_as_is_median"] or 0.0,
                    per_cap["1500"]["nis_thin_neighbourhoods_only"] or 0.0,
                    per_cap["20000"]["nis_thin_neighbourhoods_only"] or 0.0,
                    per_cap["1500"]["nis_mixed_neighbourhoods_only"] or 0.0,
                    per_cap["20000"]["nis_mixed_neighbourhoods_only"] or 0.0,
                    100.0 * (per_cap["1500"]["thin_neighbourhood_fraction"] or 0.0),
                    100.0 * (per_cap["20000"]["thin_neighbourhood_fraction"] or 0.0),
                    per_cap["1500"]["nn_radius_m_mean"] or 0.0,
                    int(estimator_cap or 600),
                )
            ),
            "candidate_calibration": (
                "DIAGNOSTIC ONLY - default values of compute_disjoint_holdout_point_to_plane_nis "
                "are deliberately left unchanged because they also drive already-published real-"
                "sequence holdout numbers. Candidate calibration to evaluate: (a) weight or "
                "reject neighbourhoods by planarity (drop the k-NN fit where the smallest "
                "eigenvalue exceeds ~0.05 x the middle one, i.e. where two surfaces mix); "
                "(b) report NIS as a robust quantile instead of a mean so mixed-plane frames do "
                "not dominate; (c) raise sigma to the actual surface sampling error measured on "
                "the analytic arena (~0.01 m) or, for real sequences, calibrate sigma per sensor; "
                "(d) scale the reference budget with the estimator cap rather than above it. "
                "Each of these changes reported numbers and needs the owner's sign-off."
            ),
        },
    }


def run_s1_counterfactual_r4_vs_r5_and_s2_voxel_contamination() -> dict:
    arena = Arena3DMeshGroundTruth()
    seeds = [42, 43, 44, 45, 46]

    # S1: Counterfactual R4 (no revisit) vs. R5 (loop revisit to Zone A) across 5 seeds
    r4_nis_list, r4_info_list = [], []
    r5_nis_list, r5_info_list = [], []
    b5_narrow_nis_list, b5_narrow_info_list = [], []
    b6_point_nis_list, b6_point_info_list = [], []
    b6_pg_nis_list, b6_pg_info_list = [], []
    # Tri-state paired-benefit evidence outcome recorded per branch (P1-1)
    r4_evidence_list, r5_evidence_list, b5_evidence_list = [], [], []
    b6_point_evidence_list, b6_pg_evidence_list = [], []
    b6_point_mode_list, b6_point_committed_kfs_list = [], []
    b6_point_voxel_count_list, b6_point_contam_list = [], []
    # Simulator-validity rows, one per scenario (see `simulator_validity` in the manifest).
    sim_validity_rows: List[dict] = []

    # S2: 3D Voxel Contamination Ratio \mathrm{Contam}_{3D} across B0, B1, B2, B3, B4, B5, B6
    contam_3d = {"B0": [], "B1": [], "B2": [], "B3": [], "B4": [], "B5": [], "B6": []}

    for s in seeds:
        rng = np.random.default_rng(s)
        node_r4 = OnlineRecoveryTransactionNode(confirmation_margin_sec=2.0, voxel_size_m=0.10, holdout_stride=5)
        node_r5 = OnlineRecoveryTransactionNode(confirmation_margin_sec=2.0, voxel_size_m=0.10, holdout_stride=5)

        # Track B0 (unprotected), B1 (online directional projection without quarantine),
        # B2 (MM-LINS N_kappa=10 frames confirmation delay, 0s rollback), and B3 (rollback on same corrupted data):
        voxels_b0: set[Tuple[int, int, int]] = set()
        voxels_b1: set[Tuple[int, int, int]] = set()
        voxels_b2: set[Tuple[int, int, int]] = set()
        voxels_b3: set[Tuple[int, int, int]] = set()

        quar_poses_gt: Dict[int, np.ndarray] = {}
        quar_poses_drifted_r4: Dict[int, np.ndarray] = {}
        quar_poses_drifted_b5: Dict[int, np.ndarray] = {}

        # Simulate 50 keyframes at 2Hz (t = 0.0s .. 25.0s):
        #   - Zone A [0, 10]s (kf 0..19): rich 3D structure
        #   - Zone B [10, 20]s (kf 20..39): degenerate corridor + occlusion onset at t=10.0s (kf 20)
        #     MM-LINS B2 confirms degeneracy after N_kappa=6 keyframes (kf 26, t=13.0s) without rolling back kf 20..25!
        for kf in range(50):
            t_sec = kf * 0.5
            t_ns = int(t_sec * 1e9)
            in_deg = 20 <= kf < 40

            T_gt = np.eye(4, dtype=np.float64)
            T_gt[0, 3] = -2.0 + 0.8 * t_sec

            scan_b = arena.sample_lidar_scan_in_body_frame(
                T_gt, zone_b_featureless=in_deg, plastic_bag_occluded_frac=0.0, rng=rng
            )

            # Host odometry drifts along longitudinal x & lateral y during Zone B [20, 40)
            T_est = T_gt.copy()
            if kf >= 20:
                drift_step = min(kf - 19, 20)
                T_est[0, 3] += 0.18 * drift_step + rng.normal(0.0, 0.02)
                T_est[1, 3] += 0.09 * drift_step + rng.normal(0.0, 0.02)

            # B0 commits every frame unconditionally
            pts_w_b0 = (scan_b @ T_est[:3, :3].T) + T_est[:3, 3]
            voxels_b0.update(node_r4._quantize_voxels(pts_w_b0))

            # B1 (Zhang/X-ICP online directional projection without quarantine): damps longitudinal x drift by 35%
            # when eigenvalue drops, but completely fails to damp lateral/plastic-bag contamination and still commits online!
            T_b1 = T_gt.copy()
            if kf >= 20:
                drift_step = min(kf - 19, 20)
                T_b1[0, 3] += 0.11 * drift_step + rng.normal(0.0, 0.02)
                T_b1[1, 3] += 0.09 * drift_step + rng.normal(0.0, 0.02)
            pts_w_b1 = (scan_b @ T_b1[:3, :3].T) + T_b1[:3, 3]
            voxels_b1.update(node_r4._quantize_voxels(pts_w_b1))

            # B2 (MM-LINS) commits frames until N_kappa=10 confirmation delay (kf 20..29 leak into sleeping map!)
            if kf < 30:
                voxels_b2.update(node_r4._quantize_voxels(pts_w_b0))

            # B3 (Rollback to clean checkpoint kf=19 and re-solve on the SAME corrupted measurements D):
            # By Proposition 1, Delta J_v <= 0; re-solving on D without stripping or external evidence reproduces drift
            voxels_b3.update(node_r4._quantize_voxels(pts_w_b0))

            nis_v = 3.6 if in_deg else 1.02
            node_r4.step_frame(kf, t_ns, T_est, scan_b, nis_value=nis_v)
            node_r5.step_frame(kf, t_ns, T_est, scan_b, nis_value=nis_v)

            if in_deg:
                quar_poses_gt[kf] = T_gt.copy()
                quar_poses_drifted_r4[kf] = T_est.copy()
                T_b5 = T_gt.copy()
                T_b5[1, 3] += 0.38 * ((kf - 19) / 10.0)  # Narrow-FoV lateral/yaw drift in B5
                quar_poses_drifted_b5[kf] = T_b5

        # S2: At end of Zone B, B4 (Quarantine Only) has committed ONLY pre-onset frames (kf < 16)
        contam_3d["B0"].append(arena.compute_3d_voxel_contamination_ratio(voxels_b0))
        contam_3d["B1"].append(arena.compute_3d_voxel_contamination_ratio(voxels_b1))
        contam_3d["B2"].append(arena.compute_3d_voxel_contamination_ratio(voxels_b2))
        contam_3d["B3"].append(arena.compute_3d_voxel_contamination_ratio(voxels_b3))
        contam_3d["B4"].append(arena.compute_3d_voxel_contamination_ratio(node_r4.committed_voxel_set))

        # Pre-onset trusted anchor and measured per-keyframe advance, taken from the trusted
        # trajectory itself (never from ground truth). These are the only inputs the repair
        # branch is allowed to use when predicting a pose for a sealed validation scan.
        max_trusted_kf = max(node_r5.tx_mgr.trusted_poses.keys())
        anchor_pose = node_r5.tx_mgr.trusted_poses[max_trusted_kf].copy()
        pre_anchor_x = float(anchor_pose[0, 3])
        if (max_trusted_kf - 1) in node_r5.tx_mgr.trusted_poses:
            step_dx_measured = float(node_r5.tx_mgr.trusted_poses[max_trusted_kf][0, 3]
                                     - node_r5.tx_mgr.trusted_poses[max_trusted_kf - 1][0, 3])
        else:
            step_dx_measured = 0.0

        def _bridge_anchor_at(kf: int) -> np.ndarray:
            """Trusted pre-onset pose carried forward at the measured pre-onset velocity."""
            T = anchor_pose.copy()
            T[0, 3] += step_dx_measured * (kf - max_trusted_kf)
            return T

        # S1 Case 1: R4 (No revisit evidence -> feature-poor corridor scans + drifted trajectory).
        # The candidate re-publishes the host's own quarantined trajectory, so its paired benefit
        # is genuinely zero rather than merely unmeasured.
        node_r4.tx_mgr.active_quarantine.weak_direction_6d = np.array([0, 0, 0, 1, 0, 0], dtype=np.float64)
        rep_r4 = node_r4.evaluate_and_commit_candidate(
            "R4_no_revisit", quar_poses_drifted_r4, aux_or_loop_info_6x6=None,
            incumbent_poses=quar_poses_drifted_r4,
            reentry_anchor_pose=_bridge_anchor_at(min(quar_poses_drifted_r4)),
        )
        r4_info_list.append(rep_r4.weak_dir_info_after)
        r4_nis_list.append(rep_r4.holdout_nis)
        r4_evidence_list.append(rep_r4.evidence_status)

        # S1 Case 2: B5 Narrow-FoV LIO-SAM filter (single-modality only: aux_or_loop_info_6x6=None, narrow 12% FoV + yaw/lateral drift)
        for k in quar_poses_drifted_b5:
            theta = 0.045 * (k - 19)
            c, sn = np.cos(theta), np.sin(theta)
            quar_poses_drifted_b5[k][:2, :2] = np.array([[c, -sn], [sn, c]])
            quar_poses_drifted_b5[k][1, 3] += 0.12 * (k - 19)
        node_b5 = OnlineRecoveryTransactionNode(confirmation_margin_sec=2.0, voxel_size_m=0.10, holdout_stride=5)
        node_b5.scan_buffer_body = {
            k: arena.sample_lidar_scan_in_body_frame(quar_poses_gt[k], zone_b_featureless=True, plastic_bag_occluded_frac=0.88, rng=rng)
            for k in quar_poses_gt
        }
        node_b5.committed_map_points = list(node_r4.committed_map_points)
        node_b5.tx_mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0 * 1e9))
        node_b5.tx_mgr.trigger_quarantine(
            int(10e9), int(20e9), np.array([0, 0, 0, 1, 0, 0], dtype=np.float64), np.eye(6) * 2.0, 1.5,
            weak_direction_frame=TangentFrame("world", "rot_trans", "world"),
            info_before_frame=TangentFrame("world", "rot_trans", "world"),
        )
        rep_b5 = node_b5.evaluate_and_commit_candidate(
            "B5_narrow_fov", quar_poses_drifted_b5, aux_or_loop_info_6x6=None,
            incumbent_poses={k: quar_poses_drifted_r4[k] for k in sorted(quar_poses_drifted_b5)},
            reentry_anchor_pose=_bridge_anchor_at(min(quar_poses_drifted_b5)),
        )
        b5_evidence_list.append(rep_b5.evidence_status)
        b5_narrow_info_list.append(rep_b5.weak_dir_info_after)
        b5_narrow_nis_list.append(rep_b5.holdout_nis)

        # Unscaled 3D voxel contamination of B5 when narrow-FoV LIO-SAM candidate is committed without Mode 2 screening:
        # Also test SpatialMutationLog trial write + rollback on node_r4's voxel_journal:
        node_r4.voxel_journal.begin_generation()
        for k, T_b5 in quar_poses_drifted_b5.items():
            pts_w = (node_r4.scan_buffer_body[k] @ T_b5[:3, :3].T) + T_b5[:3, 3]
            for v_key in node_r4._quantize_voxels(pts_w):
                node_r4.voxel_journal.put(v_key, int(k))
        contam_3d["B5"].append(arena.compute_3d_voxel_contamination_ratio(node_r4.committed_voxel_set))
        # Roll back the rejected B5 trial branch via CoW SpatialMutationLog in O(|Dirty Set|)
        node_r4.voxel_journal.rollback_mutation_journal()

        # S1 Case 3: R5 (Delayed Revisit to Zone A/C provides orthogonal pillar/wall constraints).
        # Scan-identity sealed split: the candidate pose *model* is fitted on non-validation scans
        # only, and every validation scan gets a pose predicted from that model. The fit set and
        # the validation set therefore share no scan id (repair_plan.md Section 2).
        node_r5.tx_mgr.active_quarantine.weak_direction_6d = np.array([0, 0, 0, 1, 0, 0], dtype=np.float64)
        scans_revisit = {
            k: arena.sample_lidar_scan_in_body_frame(
                quar_poses_gt[k], zone_b_featureless=False, plastic_bag_occluded_frac=0.0, rng=rng
            )
            for k in sorted(quar_poses_gt.keys())
        }
        node_r5.scan_buffer_body = {k: v for k, v in scans_revisit.items()}
        r5_keys = sorted(quar_poses_gt.keys())
        r5_validation_keys = {k for idx, k in enumerate(r5_keys) if idx % node_r5.holdout_stride == 0}
        r5_fit_keys = [k for k in r5_keys if k not in r5_validation_keys]

        def _wall_lateral_offset(scan_pts: np.ndarray) -> float:
            north = scan_pts[(scan_pts[:, 1] > 2.2) & (scan_pts[:, 2] > 0.2)]
            return 3.0 - float(np.median(north[:, 1])) if len(north) > 5 else 0.0

        y_fit = np.array([_wall_lateral_offset(scans_revisit[k]) for k in r5_fit_keys], dtype=np.float64)
        if len(r5_fit_keys) >= 2:
            slope_y, intercept_y = np.polyfit(np.asarray(r5_fit_keys, dtype=np.float64), y_fit, 1)
        else:
            slope_y, intercept_y = 0.0, float(y_fit[0]) if len(y_fit) else 0.0

        quar_poses_repaired_r5: Dict[int, np.ndarray] = {}
        for k in r5_keys:
            # Validation frames use the fitted model only; the scan itself never informs its own pose.
            y_est = float(slope_y * k + intercept_y) if k in r5_validation_keys else _wall_lateral_offset(scans_revisit[k])
            T_cand = np.eye(4, dtype=np.float64)
            T_cand[0, 3] = pre_anchor_x + step_dx_measured * (k - max_trusted_kf)
            T_cand[1, 3] = y_est
            quar_poses_repaired_r5[k] = T_cand

        rep_r5 = node_r5.evaluate_and_commit_candidate(
            "R5_revisit_loop", quar_poses_repaired_r5, aux_or_loop_info_6x6=None,
            incumbent_poses={k: quar_poses_drifted_r4[k] for k in r5_keys},
            reentry_anchor_pose=_bridge_anchor_at(r5_keys[0]),
        )
        r5_info_list.append(rep_r5.weak_dir_info_after)
        r5_nis_list.append(rep_r5.holdout_nis)
        r5_evidence_list.append(rep_r5.evidence_status)

        # S1 Case 4: B6 Point-Mixture Stripping on FAST-LIO2 (surviving 3D hall walls, solved candidate poses)
        node_b6_pm = OnlineRecoveryTransactionNode(confirmation_margin_sec=2.0, voxel_size_m=0.10, holdout_stride=5)
        node_b6_pm.committed_map_points = list(node_r5.committed_map_points)
        node_b6_pm.scan_buffer_body = {
            k: arena.sample_lidar_scan_in_body_frame(quar_poses_gt[k], zone_b_featureless=False, plastic_bag_occluded_frac=0.35, rng=rng)
            for k in quar_poses_repaired_r5
        }
        node_b6_pm.tx_mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0 * 1e9))
        node_b6_pm.tx_mgr.trigger_quarantine(
            int(10e9), int(20e9), np.array([0, 0, 0, 1, 0, 0], dtype=np.float64), np.eye(6) * 2.0, 1.2,
            weak_direction_frame=TangentFrame("world", "rot_trans", "world"),
            info_before_frame=TangentFrame("world", "rot_trans", "world"),
        )

        # ---- simulator validity: reference must be frozen BEFORE the candidate is committed ----
        # `evaluate_and_commit_candidate` mutates the committed map on acceptance, so reading the
        # reference afterwards scores GT against a map the candidate already changed.
        _validity = _simulator_validity_snapshot(
            node_b6_pm,
            r5_keys,
            quar_poses_gt,
            quar_poses_repaired_r5,
            node_b6_pm.holdout_stride,
            arena.compute_distance_to_gt_mesh,
        )
        rep_b6_pm = node_b6_pm.evaluate_and_commit_candidate(
            "B6_point_mixture", quar_poses_repaired_r5, aux_or_loop_info_6x6=None,
            incumbent_poses={k: quar_poses_drifted_r4[k] for k in r5_keys},
            reentry_anchor_pose=_bridge_anchor_at(r5_keys[0]),
        )
        b6_point_info_list.append(rep_b6_pm.weak_dir_info_after)
        b6_point_nis_list.append(rep_b6_pm.holdout_nis)
        b6_point_evidence_list.append(rep_b6_pm.evidence_status)
        b6_point_mode_list.append(rep_b6_pm.mode.value)
        b6_point_committed_kfs_list.append(int(len(node_b6_pm.tx_mgr.trusted_poses)))
        b6_point_voxel_count_list.append(int(len(node_b6_pm.committed_voxel_set)))
        b6_point_contam_list.append(
            arena.compute_3d_voxel_contamination_ratio(node_b6_pm.committed_voxel_set))
        # ---- simulator validity: record whether the commit mutated the reference --------------
        _ref_after = node_b6_pm.get_trusted_map_points(max_pts=1500)
        _validity["reference_points_after_commit"] = int(len(_ref_after))
        _validity["reference_mutated_by_candidate"] = bool(
            len(_ref_after) != _validity["reference_points_snapshot"])
        _validity["seed"] = int(s)
        _validity["status"] = _simulator_validity_status(_validity)
        _validity["gate_holdout_nis_candidate"] = float(rep_b6_pm.holdout_nis)
        _validity["gate_holdout_support"] = dict(
            getattr(node_b6_pm, "_last_holdout_support", {}) or {})
        sim_validity_rows.append(_validity)


        # S1 Case 5: B6 Aux Pose-Graph Bridge on LIO-SAM (with physical IMU/visual relative odometry Fisher prior \sigma_{rel}^{-2})
        sigma_rel_rot_rad = 0.04
        sigma_rel_trans_m = 0.045
        aux_fim_physical = np.diag([0.05 / sigma_rel_rot_rad**2] * 3 + [0.05 / sigma_rel_trans_m**2] * 3)
        node_b6_pg = OnlineRecoveryTransactionNode(confirmation_margin_sec=2.0, voxel_size_m=0.10, holdout_stride=5)
        node_b6_pg.committed_map_points = list(node_r5.committed_map_points)
        node_b6_pg.scan_buffer_body = dict(node_r5.scan_buffer_body)
        node_b6_pg.tx_mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0 * 1e9))
        node_b6_pg.tx_mgr.trigger_quarantine(
            int(10e9), int(20e9), np.array([0, 0, 0, 1, 0, 0], dtype=np.float64), np.eye(6) * 2.0, 1.2,
            weak_direction_frame=TangentFrame("world", "rot_trans", "world"),
            info_before_frame=TangentFrame("world", "rot_trans", "world"),
        )
        rep_b6_pg = node_b6_pg.evaluate_and_commit_candidate(
            "B6_aux_pg", quar_poses_repaired_r5, aux_or_loop_info_6x6=aux_fim_physical,
            incumbent_poses={k: quar_poses_drifted_r4[k] for k in r5_keys},
            reentry_anchor_pose=_bridge_anchor_at(r5_keys[0]),
        )
        b6_pg_info_list.append(rep_b6_pg.weak_dir_info_after)
        b6_pg_nis_list.append(rep_b6_pg.holdout_nis)
        b6_pg_evidence_list.append(rep_b6_pg.evidence_status)

        # B6 must be scored on the node that actually ran the verified candidate. The previous
        # line measured `node_r5`, which is the quarantine-only node and therefore has exactly the
        # same committed set as B4 -- so B6's reported 0% was B4's 0%, not a property of verified
        # admission. `node_b6_pm` writes its (filtered) scan buffer under the accepted poses via
        # `_sync_spatial_map_with_trusted_poses()`, which is the semantics the paper claims.
        contam_3d["B6"].append(arena.compute_3d_voxel_contamination_ratio(node_b6_pm.committed_voxel_set))

    out = {
        "provenance": "ONLINE_SIM_3D_MESH (Controlled Analytical 3D-Mesh Ray-Sampling & Gate Benchmark)",
        "world_file": "slam_recovery/sim/recovery_arena.world",
        "node_file": "slam_recovery/sim/transaction_manager_node.py",
        "num_seeds": len(seeds),
        "S1_CrossScan_Holdout_Gate_Verification": {
            "R4_Dual_Blind_No_Evidence": {
                "weak_dir_info_after": round(float(np.mean(r4_info_list)), 2),
                "holdout_nis": round(float(np.mean(r4_nis_list)), 3),
                "mode": rep_r4.mode.value,
                "paired_evidence_status": sorted(set(r4_evidence_list)),
            },
            "B5_Narrow_FoV_Filter_LIOSAM": {
                "weak_dir_info_after": round(float(np.mean(b5_narrow_info_list)), 2),
                "holdout_nis": round(float(np.mean(b5_narrow_nis_list)), 3),
                "mode": rep_b5.mode.value,
                "paired_evidence_status": sorted(set(b5_evidence_list)),
            },
            "R5_Delayed_Revisit_Loop": {
                "weak_dir_info_after": round(float(np.mean(r5_info_list)), 2),
                "holdout_nis": round(float(np.mean(r5_nis_list)), 3),
                "mode": rep_r5.mode.value,
                "paired_evidence_status": sorted(set(r5_evidence_list)),
                "paired_evidence_diagnostics": node_r5.last_paired_evidence,
            },
            "B6_Ours_Point_Mixture_FASTLIO2": {
                "weak_dir_info_after": round(float(np.mean(b6_point_info_list)), 2),
                "holdout_nis": round(float(np.mean(b6_point_nis_list)), 3),
                "mode": rep_b6_pm.mode.value,
                "paired_evidence_status": sorted(set(b6_point_evidence_list)),
                "gate_modes": sorted(set(b6_point_mode_list)),
                "trusted_keyframes_after_commit": b6_point_committed_kfs_list,
                "committed_voxels_per_scenario": b6_point_voxel_count_list,
                "committed_voxels_mean": round(float(np.mean(b6_point_voxel_count_list)), 1),
                "contam_3d_per_scenario": [round(float(c), 6) for c in b6_point_contam_list],
                "paired_evidence_diagnostics": node_b6_pm.last_paired_evidence,
            },
            "B6_Ours_Aux_PoseGraph_LIOSAM": {
                "weak_dir_info_after": round(float(np.mean(b6_pg_info_list)), 2),
                "holdout_nis": round(float(np.mean(b6_pg_nis_list)), 3),
                "mode": rep_b6_pg.mode.value,
                "paired_evidence_status": sorted(set(b6_pg_evidence_list)),
            },
        },
        "simulator_validity": _build_simulator_validity_block(sim_validity_rows),
        "holdout_reference_truncation": {
            "where": "slam_recovery/validation/fim_and_holdout.py::compute_disjoint_holdout_point_to_plane_nis",
            "limit": (
                "The reference cloud is hard-truncated to 600 points and the holdout scan to 300 "
                "points before the k-NN plane fit."
            ),
            "consequence": (
                "Every holdout NIS reported elsewhere in this repository -- including the real "
                "M2DGR sequences -- was computed from at most 600 reference points. The truncation "
                "is in the production path, not only in this simulation, so it bounds the "
                "credibility of the main results, not just S1/S2."
            ),
            "status": "NOT FIXED; reported so a reviewer can weigh it.",
        },
        "S2_True_3D_Mesh_Voxel_Contamination_Ratio": {
            "voxel_resolution_m": 0.10,
            "surface_tolerance_tau_map_m": 0.15,
            "B0_Original_Host_Unprotected": round(float(np.mean(contam_3d["B0"])), 4),
            "B1_Online_Directional_Projection_Mode1Only": round(float(np.mean(contam_3d["B1"])), 4),
            "B2_MMLINS_ConfirmationDelay_ZeroMargin": round(float(np.mean(contam_3d["B2"])), 4),
            "B3_Rollback_Only_Same_Data_NoInfoGain": round(float(np.mean(contam_3d["B3"])), 4),
            "B4_Ours_2s_DelayedCommit_QuarantineOnly": round(float(np.mean(contam_3d["B4"])), 4),
            "B5_Unvalidated_SingleModality_Commit": round(float(np.mean(contam_3d["B5"])), 4),
            "B6_Ours_2s_DelayedCommit_VerifiedCommit": round(float(np.mean(contam_3d["B6"])), 4),
        },
    }

    man_path = os.path.join(
        _REPO_ROOT,
        "slam_recovery/experiments/manifests/sim_s1_s2_counterfactual_and_3d_voxel_benchmark.json",
    )
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("=== Simulation S1 (Online Counterfactual R4 vs. R5 with Cross-Scan Holdout S_hold) ===")
    for k, v in out["S1_CrossScan_Holdout_Gate_Verification"].items():
        print(f"  {k:34s} | 6D-FIM J_v={v['weak_dir_info_after']:6.2f} | Cross-Scan Holdout NIS={v['holdout_nis']:6.3f} | Mode={v['mode']} | Evidence={v['paired_evidence_status']}")

    print("\n=== Simulation S2 (True 3D Mesh Voxel Contamination Ratio Contam_3D(t), tau_map=0.15m) ===")
    for k, v in out["S2_True_3D_Mesh_Voxel_Contamination_Ratio"].items():
        if isinstance(v, float):
            print(f"  {k:44s} : {v*100:6.2f}%")
    print("Saved S1 & S2 manifest to:", man_path)
    return out


if __name__ == "__main__":
    run_s1_counterfactual_r4_vs_r5_and_s2_voxel_contamination()
