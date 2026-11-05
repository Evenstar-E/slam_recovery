"""Deterministic Mechanism Signature Matrix router (Section 6.4 & 6.6)."""

from __future__ import annotations

from typing import Dict, List
import numpy as np

from ..core import DegeneracyType, Diagnosis, HealthWindow, RepairPlan
from ..health.detector import DetectorConfig


class SignatureMatrixRouter:
    """
    Zero-training interpretable mechanism signature router (Section 6.4):
      1. GEO_DEGEN:    \lambda_min(\Lambda_u) collapsed, NIS normal
      2. MEAS_CONTAM:  \lambda_min normal/inflated, NIS spiked + primary LOSO conflict
                       (captures MM-LINS floating plastic bag / near-field smoke)
      3. SYNC_DRIFT:   cross-correlation phase lag |\hat{\delta t}| > \tau_t
      4. LOOP_OUTLIER: local odometry consistent, loop factor residual spike
      5. AUX_DEGEN:    primary healthy, auxiliary LOSO conflict high
    """

    def __init__(self, config: DetectorConfig = DetectorConfig()) -> None:
        self.cfg = config

    def diagnose(self, window: HealthWindow) -> Diagnosis:
        scores: Dict[DegeneracyType, float] = {t: 0.0 for t in DegeneracyType}
        active: List[DegeneracyType] = []

        # 1. Geometric weak observability
        rot_ratio = self.cfg.lambda_rot_min_th / max(window.min_eig_rot, 1e-3)
        trans_ratio = self.cfg.lambda_trans_min_th / max(window.min_eig_trans, 1e-3)
        geo_score = max(rot_ratio, trans_ratio)
        if geo_score > 1.0:
            scores[DegeneracyType.GEO_DEGEN] = float(geo_score)
            active.append(DegeneracyType.GEO_DEGEN)

        # 2. Self-consistent near-field contamination / occlusion (e.g., plastic bag)
        nis_ratio = max(
            window.nis_cusum / max(self.cfg.nis_cusum_h, 1e-6),
            window.nis_q90 / max(self.cfg.nis_spike_th, 1e-6),
        )
        loso_ratio = window.loso_primary_conflict / max(self.cfg.loso_conflict_th, 1e-6)
        if nis_ratio > 1.0 and (loso_ratio > 1.0 or window.near_field_plane_ratio > 0.35):
            scores[DegeneracyType.MEAS_CONTAM] = float(0.5 * (nis_ratio + max(loso_ratio, 1.0)))
            active.append(DegeneracyType.MEAS_CONTAM)

        # 3. Temporal synchronization drift
        sync_ratio = abs(window.Cross_corr_lag_sec) / max(self.cfg.sync_lag_sec_th, 1e-6)
        if sync_ratio > 1.0:
            scores[DegeneracyType.SYNC_DRIFT] = float(sync_ratio)
            active.append(DegeneracyType.SYNC_DRIFT)

        # 4. Loop closure or submap fusion outlier
        loop_ratio = window.loop_residual_spike / max(self.cfg.loop_spike_th, 1e-6)
        if loop_ratio > 1.0:
            scores[DegeneracyType.LOOP_OUTLIER] = float(loop_ratio)
            active.append(DegeneracyType.LOOP_OUTLIER)

        # 5. Auxiliary modality degradation
        aux_ratio = window.loso_aux_conflict / max(self.cfg.loso_conflict_th, 1e-6)
        if aux_ratio > 1.0 and loso_ratio <= 1.0:
            scores[DegeneracyType.AUX_DEGEN] = float(aux_ratio)
            active.append(DegeneracyType.AUX_DEGEN)

        if not active:
            active.append(DegeneracyType.UNKNOWN)
            scores[DegeneracyType.UNKNOWN] = 1.0

        severity = float(max(scores.values()))
        return Diagnosis(
            active_types=active,
            scores=scores,
            severity=severity,
            weak_direction_6d=window.weak_dir_6d.copy(),
        )

    def route(self, diagnosis: Diagnosis) -> RepairPlan:
        types = set(diagnosis.active_types)
        if DegeneracyType.LOOP_OUTLIER in types:
            return RepairPlan(
                repairer_name="gnc_loop_revocation_reoptimizer",
                target_types=list(types),
                allow_point_reweight=False,
                allow_factor_revoke=True,
                allow_aux_modality=False,
            )
        if DegeneracyType.MEAS_CONTAM in types:
            return RepairPlan(
                repairer_name="point_mixture_filter_and_realign",
                target_types=list(types),
                allow_point_reweight=True,
                allow_factor_revoke=False,
                allow_aux_modality=DegeneracyType.AUX_DEGEN not in types,
            )
        if DegeneracyType.GEO_DEGEN in types:
            return RepairPlan(
                repairer_name="aux_modality_or_delayed_loop_injection",
                target_types=list(types),
                allow_point_reweight=False,
                allow_factor_revoke=False,
                allow_aux_modality=DegeneracyType.AUX_DEGEN not in types,
            )
        if DegeneracyType.SYNC_DRIFT in types:
            return RepairPlan(
                repairer_name="temporal_offset_joint_reoptimizer",
                target_types=list(types),
                allow_point_reweight=False,
                allow_factor_revoke=False,
                allow_aux_modality=True,
            )
        return RepairPlan(
            repairer_name="conservative_hold_no_high_risk_repair",
            target_types=list(types),
            allow_point_reweight=False,
            allow_factor_revoke=False,
            allow_aux_modality=False,
        )
