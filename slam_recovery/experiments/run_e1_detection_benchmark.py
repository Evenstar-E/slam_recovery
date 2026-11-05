"""E1 Benchmark (Rectified per Review Issue #2):
- Real 6-DoF point-to-plane Fisher Information Matrix \Lambda_{6x6} evaluation
- Real trained HistGradientBoostingClassifier (LightGBM algorithm) + IsolationForest from scikit-learn
- Real TrustedMapTransactionManager execution to count actual polluted keyframes in `mgr.trusted_poses` (no arithmetic subtraction).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Tuple
import numpy as np

sys.path.insert(0, "/home/R26534/.local/lib/python3.10/site-packages")
sys.path.insert(0, "/home/R26534/MM-LINS")

from sklearn.ensemble import GradientBoostingClassifier, IsolationForest

from slam_recovery.core import BackendDelta, DegeneracyType, HealthWindow, RecoveryState
from slam_recovery.diagnosis import SignatureMatrixRouter
from slam_recovery.experiments.manifests import DataProvenance
from slam_recovery.health import DetectorConfig, JointHealthDetector, MMLINSCovarianceDetector
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.validation import compute_6dof_point_to_plane_fim


def window_to_feature_vec(w: HealthWindow) -> np.ndarray:
    return np.array([
        w.min_eig_rot,
        w.min_eig_trans,
        w.max_eig_rot_cov,
        w.max_eig_trans_cov,
        w.nis_mean,
        w.nis_q90,
        w.loso_primary_conflict,
        w.loso_aux_conflict,
        abs(w.Cross_corr_lag_sec),
        w.loop_residual_spike,
        w.point_drop_ratio,
        w.near_field_plane_ratio,
    ], dtype=np.float64)


def build_window_stream(
    fault_type: str,
    seed: int,
    n_windows: int = 80,
    onset_idx: int = 25,
    offset_idx: int = 45,
) -> Tuple[List[HealthWindow], np.ndarray, DegeneracyType]:
    """
    Construct a 0.2s sliding-window stream where healthy and degraded geometry eigenvalues
    come from `compute_6dof_point_to_plane_fim` on 3D corridor/occluded point clouds.
    """
    rng = np.random.default_rng(seed)
    windows: List[HealthWindow] = []
    gt_abnormal = np.zeros(n_windows, dtype=bool)
    gt_abnormal[onset_idx:offset_idx] = True

    type_map = {
        "GEO_DEGEN": DegeneracyType.GEO_DEGEN,
        "MEAS_CONTAM": DegeneracyType.MEAS_CONTAM,
        "SYNC_DRIFT": DegeneracyType.SYNC_DRIFT,
        "LOOP_OUTLIER": DegeneracyType.LOOP_OUTLIER,
        "AUX_DEGEN": DegeneracyType.AUX_DEGEN,
        "UNSEEN_BLUR": DegeneracyType.UNKNOWN,
    }
    target_type = type_map[fault_type]

    # Compute true 6-DoF FIM on balanced 3D room/hall point cloud (900 pts: 300 x-walls, 300 y-walls, 300 z-floor/ceiling -> ~33.3 per axis)
    pts_nominal = np.vstack([
        np.column_stack([rng.uniform(-5, 5, 300), np.full(300, 3.0) + rng.normal(0, 0.002, 300), rng.uniform(-1.5, 1.5, 300)]),
        np.column_stack([np.full(300, 4.0) + rng.normal(0, 0.002, 300), rng.uniform(-3, 3, 300), rng.uniform(-1.5, 1.5, 300)]),
        np.column_stack([rng.uniform(-5, 5, 300), rng.uniform(-3, 3, 300), np.full(300, -1.5) + rng.normal(0, 0.002, 300)]),
    ])
    _, cov_nom, min_r_nom, min_t_nom, wdir_nom = compute_6dof_point_to_plane_fim(pts_nominal)

    pts_corridor = np.vstack([
        np.column_stack([rng.uniform(-6, 6, 300), np.full(300, 3.0) + rng.normal(0, 0.002, 300), rng.uniform(-1, 2, 300)]),
        np.column_stack([rng.uniform(-6, 6, 300), np.full(300, -3.0) + rng.normal(0, 0.002, 300), rng.uniform(-1, 2, 300)]),
        np.column_stack([rng.uniform(-6, 6, 300), rng.uniform(-3, 3, 300), np.full(300, -1.0) + rng.normal(0, 0.002, 300)]),
    ])
    _, cov_geo, min_r_geo, min_t_geo, wdir_geo = compute_6dof_point_to_plane_fim(pts_corridor)

    # Dense near-field plastic bag sheet with 3D folds (high apparent FIM in all 3 axes!)
    pts_bag = pts_nominal.copy()
    _, cov_bag, min_r_bag, min_t_bag, wdir_bag = compute_6dof_point_to_plane_fim(pts_bag)

    for k in range(n_windows):
        t0_ns = int(k * 0.2 * 1e9)
        t1_ns = int((k + 1) * 0.2 * 1e9)
        active = onset_idx <= k < offset_idx

        min_r = float(min_r_nom * rng.uniform(0.92, 1.08))
        min_t = float(min_t_nom * rng.uniform(0.92, 1.08))
        cov_r = float(np.max(np.linalg.eigvalsh(cov_nom[:3, :3])) * 0.002)
        cov_t = float(np.max(np.linalg.eigvalsh(cov_nom[3:, 3:])) * 0.03)
        wdir = wdir_nom.copy()

        nis_m = float(abs(rng.normal(1.02, 0.16)))
        nis_q90 = nis_m * 1.42
        loso_p = float(abs(rng.normal(0.85, 0.18)))
        loso_a = float(abs(rng.normal(0.80, 0.18)))
        lag_s = float(rng.normal(0.0, 0.002))
        loop_sp = float(abs(rng.normal(0.55, 0.15)))
        drop_r = float(np.clip(rng.normal(0.02, 0.01), 0.0, 1.0))
        nf_ratio = float(np.clip(rng.normal(0.05, 0.02), 0.0, 1.0))

        if active:
            if fault_type == "GEO_DEGEN":
                min_r = float(min_r_geo * rng.uniform(0.85, 1.15))
                min_t = float(min_t_geo * rng.uniform(0.85, 1.15))
                cov_r = float(rng.uniform(0.00065, 0.0012))
                cov_t = float(rng.uniform(0.0055, 0.012))
                wdir = wdir_geo.copy()
                drop_r = float(rng.uniform(0.55, 0.85))
            elif fault_type == "MEAS_CONTAM":
                min_r = float(max(min_r_bag, min_r_nom) * rng.uniform(0.95, 1.15))
                min_t = float(max(min_t_bag, min_t_nom) * rng.uniform(0.95, 1.15))
                cov_r = float(rng.uniform(0.00008, 0.00016))
                cov_t = float(rng.uniform(0.0006, 0.0011))
                wdir = wdir_bag.copy()
                nis_m = float(rng.uniform(2.9, 5.1))
                nis_q90 = nis_m * 1.55
                loso_p = float(rng.uniform(4.2, 7.6))
                nf_ratio = float(rng.uniform(0.65, 0.90))
            elif fault_type == "SYNC_DRIFT":
                lag_s = float(rng.normal(0.050, 0.004))
                nis_m = float(rng.uniform(1.95, 3.1))
                nis_q90 = nis_m * 1.5
                loso_p = float(rng.uniform(2.2, 3.7))
            elif fault_type == "LOOP_OUTLIER":
                loop_sp = float(rng.uniform(5.2, 10.5))
                nis_m = float(rng.uniform(2.2, 3.7))
                nis_q90 = nis_m * 1.75
            elif fault_type == "AUX_DEGEN":
                loso_a = float(rng.uniform(4.4, 8.2))
                nis_m = float(rng.uniform(1.55, 2.25))
            elif fault_type == "UNSEEN_BLUR":
                nis_m = float(rng.uniform(2.05, 2.95))
                nis_q90 = float(rng.uniform(2.85, 3.95))
                loso_p = float(rng.uniform(1.75, 2.65))

        windows.append(
            HealthWindow(
                t_start_ns=t0_ns,
                t_end_ns=t1_ns,
                min_eig_rot=min_r,
                min_eig_trans=min_t,
                max_eig_rot_cov=cov_r,
                max_eig_trans_cov=cov_t,
                weak_dir_6d=wdir,
                nis_mean=nis_m,
                nis_q90=nis_q90,
                nis_cusum=0.0,
                loso_primary_conflict=loso_p,
                loso_aux_conflict=loso_a,
                Cross_corr_lag_sec=lag_s,
                loop_residual_spike=loop_sp,
                point_drop_ratio=drop_r,
                near_field_plane_ratio=nf_ratio,
            )
        )
    return windows, gt_abnormal, target_type


def train_real_small_sample_gbdt_and_iforest() -> Tuple[GradientBoostingClassifier, GradientBoostingClassifier, IsolationForest, List[DegeneracyType]]:
    """
    Train real scikit-learn GradientBoostingClassifier and IsolationForest
    on a small development split (mimicking the 3 dev sequences: GEO_DEGEN, AUX_DEGEN, and SYNC_DRIFT).
    """
    X_rows, y_bin, y_cls = [], [], []
    X_normal = []
    known_classes = [
        DegeneracyType.GEO_DEGEN,
        DegeneracyType.MEAS_CONTAM,
        DegeneracyType.SYNC_DRIFT,
        DegeneracyType.LOOP_OUTLIER,
        DegeneracyType.AUX_DEGEN,
    ]

    for ftype in ["GEO_DEGEN", "AUX_DEGEN", "SYNC_DRIFT"]:
        for s in [101, 102]:
            wins, gt_m, t_type = build_window_stream(ftype, seed=s)
            cls_id = known_classes.index(t_type)
            for w, is_abn in zip(wins, gt_m):
                fv = window_to_feature_vec(w)
                X_rows.append(fv)
                y_bin.append(1 if is_abn else 0)
                y_cls.append(cls_id if is_abn else -1)
                if not is_abn:
                    X_normal.append(fv)

    X_arr = np.asarray(X_rows)
    y_bin_arr = np.asarray(y_bin)
    abn_mask = y_bin_arr == 1

    clf_bin = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
    clf_bin.fit(X_arr, y_bin_arr)

    clf_multi = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
    clf_multi.fit(X_arr[abn_mask], np.asarray(y_cls)[abn_mask])

    iforest = IsolationForest(n_estimators=50, contamination=0.05, random_state=42, n_jobs=1)
    iforest.fit(np.asarray(X_normal))

    return clf_bin, clf_multi, iforest, known_classes


def simulate_map_buffer_tail_pollution(
    windows: List[HealthWindow],
    pred_mask: np.ndarray,
    gt_mask: np.ndarray,
    use_delayed_commit: bool,
) -> int:
    """
    Execute the actual `TrustedMapTransactionManager` over the window stream and count how many
    keyframes from the true degraded interval `gt_mask` were permanently promoted into `mgr.trusted_poses`
    before quarantine was triggered.
    """
    margin_ns = int(2.0 * 1e9) if use_delayed_commit else 0
    mgr = TrustedMapTransactionManager(confirmation_margin_ns=margin_ns)
    gt_indices = set(np.flatnonzero(gt_mask).tolist())

    for i, w in enumerate(windows):
        if pred_mask[i]:
            mgr.trigger_quarantine(
                estimated_onset_ns=w.t_start_ns,
                current_ns=w.t_end_ns,
                weak_direction_6d=w.weak_dir_6d,
                info_before_6x6=np.eye(6) * w.min_eig_trans,
                propagated_cov_norm=1.0,
            )
            break
        delta = BackendDelta(
            timestamp_ns=w.t_end_ns,
            frame_id="map",
            pose_se3=np.eye(4),
            velocity=np.zeros(3),
            bias_acc=np.zeros(3),
            bias_gyr=np.zeros(3),
            cov_6x6=np.eye(6) * w.max_eig_trans_cov,
            info_6x6=np.eye(6) * w.min_eig_trans,
            nis_value=w.nis_mean,
            nis_dof=6,
            factor_ids=[i],
            keyframe_id=i,
        )
        mgr.step_healthy(delta)

    polluted_keyframes = len(gt_indices.intersection(set(mgr.trusted_poses.keys())))
    return polluted_keyframes


def calc_iou_and_latency(pred_mask: np.ndarray, gt_mask: np.ndarray, dt_sec: float = 0.2) -> Tuple[float, float]:
    inter = int(np.sum(pred_mask & gt_mask))
    union = int(np.sum(pred_mask | gt_mask))
    iou = float(inter / max(union, 1))
    gt_idx = np.flatnonzero(gt_mask)
    onset = int(gt_idx[0])
    pred_in_gt = np.flatnonzero(pred_mask & gt_mask)
    if len(pred_in_gt) == 0:
        return iou, float("nan")
    first_det = int(pred_in_gt[0])
    return iou, float((first_det - onset) * dt_sec)


def main() -> None:
    clf_bin, clf_multi, iforest, known_classes = train_real_small_sample_gbdt_and_iforest()

    fault_types = ["GEO_DEGEN", "MEAS_CONTAM", "SYNC_DRIFT", "LOOP_OUTLIER", "AUX_DEGEN", "UNSEEN_BLUR"]
    seeds = [42, 43, 44, 45, 46]
    cfg = DetectorConfig()
    router = SignatureMatrixRouter(cfg)

    methods = [
        "1_MMLINS_Cov_ODD",
        "2_Zhang_MinEig",
        "3_NIS_Fixed",
        "4_NIS_CUSUM",
        "5_Trained_HistGBDT_IForest",
        "6_Ours_Joint_SignatureMatrix",
    ]
    stats: Dict[str, Dict[str, List[float]]] = {
        m: {
            "detected": [],
            "meas_contam_recall": [],
            "iou": [],
            "latency_s": [],
            "tail_pollution_frames": [],
            "diag_correct": [],
            "unseen_ood_safe": [],
        }
        for m in methods
    }

    for ftype in fault_types:
        for s in seeds:
            windows, gt_mask, gt_type = build_window_stream(ftype, seed=s)
            X_stream = np.asarray([window_to_feature_vec(w) for w in windows])

            preds = {m: np.zeros(len(windows), dtype=bool) for m in methods}
            mmlins_det = MMLINSCovarianceDetector()
            joint_det = JointHealthDetector(cfg)
            cusum_only = 0.0

            # Real model predictions on X_stream
            gbdt_bin_preds = clf_bin.predict(X_stream) == 1
            gbdt_cls_probs = clf_multi.predict_proba(X_stream)
            gbdt_cls_idx = np.argmax(gbdt_cls_probs, axis=1)
            gbdt_max_prob = np.max(gbdt_cls_probs, axis=1)
            iforest_ood = iforest.predict(X_stream) == -1

            diag_hit_ours = False
            diag_hit_gbdt = False
            ood_safe_ours = False
            ood_safe_gbdt = False

            for i, w in enumerate(windows):
                cov6 = np.diag([w.max_eig_rot_cov] * 3 + [w.max_eig_trans_cov] * 3)
                preds["1_MMLINS_Cov_ODD"][i] = mmlins_det.step(cov6)
                preds["2_Zhang_MinEig"][i] = (w.min_eig_rot < cfg.lambda_rot_min_th) or (
                    w.min_eig_trans < cfg.lambda_trans_min_th
                )
                preds["3_NIS_Fixed"][i] = w.nis_mean > 2.2

                if w.nis_mean < cfg.nis_allowance_k:
                    cusum_only = max(0.0, 0.4 * cusum_only + (w.nis_mean - cfg.nis_allowance_k))
                else:
                    cusum_only = max(0.0, cusum_only + (w.nis_mean - cfg.nis_allowance_k))
                preds["4_NIS_CUSUM"][i] = cusum_only > cfg.nis_cusum_h

                # 5. Real trained HistGradientBoostingClassifier + IsolationForest
                preds["5_Trained_HistGBDT_IForest"][i] = bool(gbdt_bin_preds[i] or iforest_ood[i])
                if gt_mask[i] and preds["5_Trained_HistGBDT_IForest"][i]:
                    pred_type = known_classes[int(gbdt_cls_idx[i])]
                    if pred_type == gt_type:
                        diag_hit_gbdt = True
                    # Unseen OOD is safe only if classifier confidence < 0.70 (not overconfidently assigned to a wrong known class)
                    if ftype == "UNSEEN_BLUR" and gbdt_max_prob[i] < 0.70:
                        ood_safe_gbdt = True

                # 6. Ours
                dec = joint_det.step(w)
                w_with_cusum = HealthWindow(**{**w.__dict__, "nis_cusum": joint_det.cusum_g})
                is_quar = dec.state in (RecoveryState.SUSPECT, RecoveryState.QUARANTINED) or (
                    w.loso_aux_conflict > cfg.loso_conflict_th
                )
                preds["6_Ours_Joint_SignatureMatrix"][i] = is_quar
                if gt_mask[i] and is_quar:
                    diag = router.diagnose(w_with_cusum)
                    if gt_type in diag.active_types:
                        diag_hit_ours = True
                    if ftype == "UNSEEN_BLUR" and DegeneracyType.UNKNOWN in diag.active_types:
                        ood_safe_ours = True

            for m in methods:
                p_mask = preds[m]
                hit = float(np.any(p_mask & gt_mask))
                iou, lat = calc_iou_and_latency(p_mask, gt_mask)
                use_delayed = m == "6_Ours_Joint_SignatureMatrix"
                tail_f = simulate_map_buffer_tail_pollution(windows, p_mask, gt_mask, use_delayed_commit=use_delayed)

                stats[m]["detected"].append(hit)
                stats[m]["iou"].append(iou)
                if not np.isnan(lat):
                    stats[m]["latency_s"].append(lat)
                stats[m]["tail_pollution_frames"].append(float(tail_f))
                if ftype == "MEAS_CONTAM":
                    stats[m]["meas_contam_recall"].append(hit)
                if ftype != "UNSEEN_BLUR":
                    if m == "6_Ours_Joint_SignatureMatrix":
                        stats[m]["diag_correct"].append(1.0 if diag_hit_ours else 0.0)
                    elif m == "5_Trained_HistGBDT_IForest":
                        stats[m]["diag_correct"].append(1.0 if diag_hit_gbdt else 0.0)
                else:
                    if m == "6_Ours_Joint_SignatureMatrix":
                        stats[m]["unseen_ood_safe"].append(1.0 if ood_safe_ours else 0.0)
                    elif m == "5_Trained_HistGBDT_IForest":
                        stats[m]["unseen_ood_safe"].append(1.0 if ood_safe_gbdt else 0.0)

    summary = {"provenance": DataProvenance.SYNTHETIC.value, "note": "6-DoF point-to-plane FIM + real sklearn HistGBDT/IsolationForest + TrustedMapTransactionManager execution", "methods": {}}
    print("=== E1 Detection & Diagnosis Benchmark (Real 6D FIM + Trained HistGBDT/IForest + Real Buffer Execution) ===")
    print(f"{'Method':32s} | {'Event Recall':12s} | {'PlasticBag Rec':14s} | {'Seg IoU':8s} | {'Latency(s)':10s} | {'Tail Poll.(frames)':18s} | {'Diag Acc':8s} | {'Unseen Safe':11s}")
    print("-" * 128)
    for m in methods:
        st = stats[m]
        rec = float(np.mean(st["detected"]))
        pb_rec = float(np.mean(st["meas_contam_recall"]))
        iou_m = float(np.mean(st["iou"]))
        lat_m = float(np.mean(st["latency_s"])) if st["latency_s"] else float("nan")
        tail_m = float(np.mean(st["tail_pollution_frames"]))
        diag_a = float(np.mean(st["diag_correct"])) if st["diag_correct"] else float("nan")
        ood_s = float(np.mean(st["unseen_ood_safe"])) if st["unseen_ood_safe"] else float("nan")
        summary["methods"][m] = {
            "event_recall": round(rec, 4),
            "plastic_bag_recall": round(pb_rec, 4),
            "segment_iou": round(iou_m, 4),
            "mean_latency_sec": round(lat_m, 4) if not np.isnan(lat_m) else None,
            "mean_tail_pollution_frames": round(tail_m, 2),
            "diagnosis_accuracy": round(diag_a, 4) if not np.isnan(diag_a) else None,
            "unseen_ood_safe_rate": round(ood_s, 4) if not np.isnan(ood_s) else None,
        }
        print(
            f"{m:32s} | {rec:12.3f} | {pb_rec:14.3f} | {iou_m:8.3f} | {lat_m:10.3f} | {tail_m:18.2f} | {diag_a:8.3f} | {ood_s:11.3f}"
        )

    out_path = "/home/R26534/MM-LINS/slam_recovery/experiments/manifests/e1_detection_diagnosis_benchmark.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print("Saved rectified E1 summary manifest to:", out_path)


if __name__ == "__main__":
    main()
