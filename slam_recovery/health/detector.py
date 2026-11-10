"""Joint health detector (NIS-CUSUM + decoupled information spectrum + 3-state HMM) and interpretable signature router."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np

from ..core import (
    BackendDelta,
    DegeneracyType,
    Diagnosis,
    HealthDecision,
    HealthWindow,
    RecoveryState,
)


@dataclass(frozen=True)
class DetectorConfig:
    """Parameters for joint anomaly detection and signature routing (Sections 4.4, 4.5, 6.4)."""

    # Normalized information spectrum threshold (relative or scaled eigenvalue)
    lambda_rot_min_th: float = 15.0
    lambda_trans_min_th: float = 20.0
    # MM-LINS baseline covariance thresholds (from Section IV-C of MM-LINS paper)
    mmlins_cov_rot_th: float = 0.0006
    mmlins_cov_trans_th: float = 0.0050
    # NIS chi-square & CUSUM parameters
    nis_allowance_k: float = 1.35
    nis_cusum_h: float = 4.0
    nis_spike_th: float = 2.8
    # Cross-sensor leave-one-out conflict & time offset thresholds
    loso_conflict_th: float = 3.0
    sync_lag_sec_th: float = 0.015     # 15 ms
    loop_spike_th: float = 4.0
    # Minimum dwell count for HMM state transition
    min_dwell_windows: int = 2
    confirmation_margin_ns: int = int(2.0 * 1e9)


def analyze_decoupled_information(
    info_6x6: np.ndarray,
    cov_6x6: np.ndarray,
    rot_scale: float = 1.0,
    trans_scale: float = 1.0,
) -> Tuple[float, float, float, float, np.ndarray]:
    """
    Decouple rotation (indices 0:3) and translation (indices 3:6) as in MM-LINS Eq.(2)
    and Section 4.5 normalized observability analysis.
    Returns (min_eig_rot_info, min_eig_trans_info, max_eig_rot_cov, max_eig_trans_cov, weak_dir_6d).
    """
    scale_vec = np.array([rot_scale] * 3 + [trans_scale] * 3, dtype=np.float64)
    D = np.diag(scale_vec)
    info_u = D.T @ info_6x6 @ D

    vals_r, vecs_r = np.linalg.eigh(0.5 * (info_u[:3, :3] + info_u[:3, :3].T))
    vals_t, vecs_t = np.linalg.eigh(0.5 * (info_u[3:, 3:] + info_u[3:, 3:].T))
    vals_6d, vecs_6d = np.linalg.eigh(0.5 * (info_u + info_u.T))

    cov_r = 0.5 * (cov_6x6[:3, :3] + cov_6x6[:3, :3].T)
    cov_t = 0.5 * (cov_6x6[3:, 3:] + cov_6x6[3:, 3:].T)
    cvals_r = np.linalg.eigvalsh(cov_r)
    cvals_t = np.linalg.eigvalsh(cov_t)

    min_r = float(vals_r[0])
    min_t = float(vals_t[0])
    min_6d = float(vals_6d[0])
    weak_6d = np.zeros(6, dtype=np.float64)
    # Catch coupled rotation-translation weak directions (R4 fix)
    if min_6d < min(min_r, min_t):
        weak_6d = vecs_6d[:, 0].copy()
        if np.linalg.norm(weak_6d[:3]) >= np.linalg.norm(weak_6d[3:]):
            min_r = min_6d
        else:
            min_t = min_6d
    elif min_r < min_t:
        weak_6d[:3] = vecs_r[:, 0]
    else:
        weak_6d[3:] = vecs_t[:, 0]

    return min_r, min_t, float(cvals_r[-1]), float(cvals_t[-1]), weak_6d


class MMLINSCovarianceDetector:
    """
    Exact reproduction of the MM-LINS Over-Degeneracy Detection module (Section III-B1, Eq. 1-3)
    for direct E1 baseline comparison.
    """

    def __init__(
        self,
        xi_r_major: float = 0.0006,
        xi_t_major: float = 0.0050,
        xi_r_minor: float = 0.0003,
        xi_t_minor: float = 0.0025,
        n_kappa: int = 5,
    ) -> None:
        self.xi_r_major = xi_r_major
        self.xi_t_major = xi_t_major
        self.xi_r_minor = xi_r_minor
        self.xi_t_minor = xi_t_minor
        self.n_kappa = n_kappa
        self.gamma_lambda = 0

    def step(self, cov_6x6: np.ndarray) -> bool:
        _, _, lam_r_max, lam_t_max, _ = analyze_decoupled_information(
            np.eye(6), cov_6x6
        )
        in_minor = (self.xi_r_minor < lam_r_max < self.xi_r_major) or (
            self.xi_t_minor < lam_t_max < self.xi_t_major
        )
        if in_minor:
            self.gamma_lambda += 1
        else:
            self.gamma_lambda = 0

        if (
            (lam_r_max > self.xi_r_major and lam_t_max > self.xi_t_major)
            or self.gamma_lambda > self.n_kappa
        ):
            return True
        return False


class JointHealthDetector:
    """
    Joint NIS-CUSUM + Decoupled Information Spectrum + LOSO consistency detector
    with 3-state dwell-constrained HMM and onset backtracking.
    """

    def __init__(self, config: DetectorConfig = DetectorConfig()) -> None:
        self.cfg = config
        self.cusum_g: float = 0.0
        self.state: RecoveryState = RecoveryState.HEALTHY
        self.suspect_dwell: int = 0
        self.suspect_onset_ns: Optional[int] = None

    def update_cusum(self, normalized_nis: float) -> float:
        if normalized_nis < self.cfg.nis_allowance_k:
            self.cusum_g = max(0.0, 0.4 * self.cusum_g + (normalized_nis - self.cfg.nis_allowance_k))
        else:
            self.cusum_g = max(0.0, self.cusum_g + (normalized_nis - self.cfg.nis_allowance_k))
        return self.cusum_g

    def reset(self) -> None:
        """Forget the alarm history when a segment closes without evidence.

        The CUSUM and dwell counters describe the segment that just ended. Carrying them into
        the next one would make a second event's detection depend on how the first one ended.
        """
        self.cusum_g = 0.0
        self.state = RecoveryState.HEALTHY
        self.suspect_dwell = 0
        self.suspect_onset_ns = None

    def step(self, window: HealthWindow) -> HealthDecision:
        g_t = self.update_cusum(window.nis_mean)

        geo_weak = (
            window.min_eig_rot < self.cfg.lambda_rot_min_th
            or window.min_eig_trans < self.cfg.lambda_trans_min_th
        )
        nis_alarm = (g_t > self.cfg.nis_cusum_h) or (window.nis_q90 > self.cfg.nis_spike_th)
        loso_alarm = window.loso_primary_conflict > self.cfg.loso_conflict_th
        sync_alarm = abs(window.Cross_corr_lag_sec) > self.cfg.sync_lag_sec_th
        loop_alarm = window.loop_residual_spike > self.cfg.loop_spike_th

        any_soft_alarm = geo_weak or nis_alarm or loso_alarm or sync_alarm or loop_alarm
        score = float(
            max(
                g_t / max(self.cfg.nis_cusum_h, 1e-6),
                self.cfg.lambda_trans_min_th / max(window.min_eig_trans, 1e-3) if geo_weak else 0.0,
                window.loso_primary_conflict / max(self.cfg.loso_conflict_th, 1e-6),
                window.loop_residual_spike / max(self.cfg.loop_spike_th, 1e-6),
            )
        )

        if window.hard_failure:
            onset = self.suspect_onset_ns if self.suspect_onset_ns is not None else window.t_start_ns
            self.state = RecoveryState.QUARANTINED
            return HealthDecision(
                state=self.state,
                abnormal_score=max(score, 10.0),
                estimated_onset_ns=onset,
                quarantine_start_ns=onset - self.cfg.confirmation_margin_ns,
                confidence=1.0,
                evidence={"cusum": g_t, "hard_failure": 1.0},
            )

        if any_soft_alarm:
            if self.suspect_dwell == 0:
                self.suspect_onset_ns = window.t_start_ns
            self.suspect_dwell += 1
            if self.suspect_dwell >= self.cfg.min_dwell_windows:
                self.state = RecoveryState.QUARANTINED
            else:
                self.state = RecoveryState.SUSPECT
        else:
            self.suspect_dwell = 0
            self.suspect_onset_ns = None
            self.cusum_g = max(0.0, 0.5 * self.cusum_g)
            self.state = RecoveryState.HEALTHY

        onset = self.suspect_onset_ns if self.suspect_onset_ns is not None else window.t_start_ns
        return HealthDecision(
            state=self.state,
            abnormal_score=score,
            estimated_onset_ns=onset,
            quarantine_start_ns=onset - self.cfg.confirmation_margin_ns,
            confidence=min(1.0, score / 2.0),
            evidence={
                "cusum": g_t,
                "min_eig_rot": window.min_eig_rot,
                "min_eig_trans": window.min_eig_trans,
                "loso_primary": window.loso_primary_conflict,
            },
        )
