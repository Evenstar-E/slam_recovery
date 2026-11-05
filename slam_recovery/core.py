"""Core data structures, state machine, and unified four-mode information gate (Sections 4.8, 5.3, 7.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import numpy as np


class RecoveryState(str, Enum):
    HEALTHY = "HEALTHY"
    SUSPECT = "SUSPECT"
    QUARANTINED = "QUARANTINED"
    DIAGNOSING = "DIAGNOSING"
    REPAIRING = "REPAIRING"
    WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"
    VALIDATING = "VALIDATING"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class RecoveryMode(str, Enum):
    """Unified four-mode decision space (Section 4.8)."""

    MODE1_ONLINE_REWEIGHT = "MODE1_ONLINE_REWEIGHT"
    MODE2_ATOMIC_COMMIT = "MODE2_ATOMIC_COMMIT"
    MODE3_SOFT_BRIDGE_WAIT = "MODE3_SOFT_BRIDGE_WAIT"
    MODE4_HARD_SLEEP_SPLIT = "MODE4_HARD_SLEEP_SPLIT"


class DegeneracyType(str, Enum):
    """Interpretable mechanism signature categories (Section 6.4)."""

    GEO_DEGEN = "GEO_DEGEN"          # Geometric weak observability (corridor, severe dropout)
    MEAS_CONTAM = "MEAS_CONTAM"      # Self-consistent near-field occlusion (plastic bag, smoke, crowd)
    SYNC_DRIFT = "SYNC_DRIFT"        # Temporal offset or extrinsic drift
    LOOP_OUTLIER = "LOOP_OUTLIER"    # Perceptual aliasing / false loop or submap merge
    AUX_DEGEN = "AUX_DEGEN"          # Auxiliary modality degradation (dark, blur)
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class StandardFrame:
    sensor_id: str
    t_start_ns: int
    t_end_ns: int
    frame_id: str
    data_ref: str
    calib_version: str = "v1"
    available_mask: int = 1
    checksum: str = ""

    def __post_init__(self) -> None:
        if self.t_end_ns < self.t_start_ns:
            raise ValueError(f"t_end_ns ({self.t_end_ns}) < t_start_ns ({self.t_start_ns})")

    @property
    def t_mid_sec(self) -> float:
        return 0.5 * (self.t_start_ns + self.t_end_ns) * 1e-9


@dataclass
class BackendDelta:
    timestamp_ns: int
    frame_id: str
    pose_se3: np.ndarray              # 4x4 homogeneous matrix
    velocity: np.ndarray              # (3,)
    bias_acc: np.ndarray              # (3,)
    bias_gyr: np.ndarray              # (3,)
    cov_6x6: np.ndarray               # 6x6 [rot(3), trans(3)] tangent covariance
    info_6x6: np.ndarray              # 6x6 normalized information matrix
    nis_value: float                  # Normalized innovation squared
    nis_dof: int                      # Effective degrees of freedom
    factor_ids: List[int] = field(default_factory=list)
    keyframe_id: Optional[int] = None
    provisional: bool = True
    converged: bool = True


@dataclass
class HealthWindow:
    t_start_ns: int
    t_end_ns: int
    min_eig_rot: float
    min_eig_trans: float
    max_eig_rot_cov: float
    max_eig_trans_cov: float
    weak_dir_6d: np.ndarray           # Unit 6D vector v in tangent space [rot, trans]
    nis_mean: float
    nis_q90: float
    nis_cusum: float
    loso_primary_conflict: float      # Leave-one-sensor-out conflict on primary sensor
    loso_aux_conflict: float          # Leave-one-sensor-out conflict on auxiliary sensor
    Cross_corr_lag_sec: float         # Estimated gyro/motion phase lag \hat{\delta t}
    loop_residual_spike: float        # Residual jump after loop/submap factor
    point_drop_ratio: float = 0.0
    near_field_plane_ratio: float = 0.0
    hard_failure: bool = False
    available_mask: int = 0b111       # bit0: LiDAR, bit1: IMU, bit2: Camera


@dataclass
class HealthDecision:
    state: RecoveryState
    abnormal_score: float
    estimated_onset_ns: int
    quarantine_start_ns: int
    confidence: float
    evidence: Dict[str, float] = field(default_factory=dict)


@dataclass
class Checkpoint:
    checkpoint_id: str
    timestamp_ns: int
    map_version: int
    keyframe_poses: Dict[int, np.ndarray]
    factor_ids: List[int]
    imu_bias_acc: np.ndarray
    imu_bias_gyr: np.ndarray
    state_hash: str = ""

    def compute_hash(self) -> str:
        h = hashlib.sha256()
        h.update(f"{self.checkpoint_id}:{self.timestamp_ns}:{self.map_version}".encode())
        for k in sorted(self.keyframe_poses.keys()):
            arr = np.ascontiguousarray(self.keyframe_poses[k], dtype=np.float64)
            h.update(f"kf:{int(k)}:shape:{arr.shape}:".encode())
            h.update(arr.tobytes())
        h.update(np.asarray(sorted(self.factor_ids), dtype=np.int64).tobytes())
        h.update(np.ascontiguousarray(self.imu_bias_acc, dtype=np.float64).tobytes())
        h.update(np.ascontiguousarray(self.imu_bias_gyr, dtype=np.float64).tobytes())
        return h.hexdigest()


@dataclass
class QuarantineSegment:
    segment_id: str
    checkpoint: Checkpoint
    t_start_ns: int
    t_end_ns: int
    weak_direction_6d: np.ndarray
    info_before_6x6: np.ndarray
    propagated_cov_norm: float
    raw_frame_refs: List[str] = field(default_factory=list)
    provisional_factor_ids: List[int] = field(default_factory=list)


@dataclass
class Diagnosis:
    active_types: List[DegeneracyType]
    scores: Dict[DegeneracyType, float]
    severity: float
    weak_direction_6d: np.ndarray
    router_version: str = "signature_matrix_v1"


@dataclass
class RepairPlan:
    repairer_name: str
    target_types: List[DegeneracyType]
    allow_point_reweight: bool
    allow_factor_revoke: bool
    allow_aux_modality: bool
    require_independent_validation: bool = True


@dataclass
class CandidateMap:
    candidate_id: str
    parent_map_version: int
    repaired_poses: Dict[int, np.ndarray]
    info_after_6x6: np.ndarray
    cov_after_6x6: np.ndarray
    holdout_nis: float
    used_evidence_refs: List[str] = field(default_factory=list)
    repairer_name: str = ""
    repaired_factor_ids: Optional[List[int]] = None
    repaired_bias_acc: Optional[np.ndarray] = None
    repaired_bias_gyr: Optional[np.ndarray] = None


@dataclass
class ValidationReport:
    accepted: bool
    mode: RecoveryMode
    weak_dir_info_before: float
    weak_dir_info_after: float
    weak_dir_info_gain: float
    holdout_nis: float
    posterior_cov_norm: float
    propagated_cov_norm: float
    reason: str


@dataclass(frozen=True)
class GateThresholds:
    """Thresholds for the unified four-mode gate D(t) in Section 4.8."""

    min_duration_sec: float = 1.0     # \Delta t_{min} for Mode 1 vs quarantine
    tau_info: float = 25.0            # Minimum information along weak direction v^T \Lambda_{after} v
    tau_val_nis: float = 2.5          # Maximum normalized holdout innovation squared D_{holdout}
    sigma_tol: float = 0.50           # Posterior covariance norm tolerance ||P_{after}||
    sigma_bridge: float = 4.00        # Bridge uncertainty upper bound \Sigma_{bridge}


def evaluate_four_mode_gate(
    segment: QuarantineSegment,
    candidate: Optional[CandidateMap],
    thresholds: GateThresholds = GateThresholds(),
) -> ValidationReport:
    """
    Evaluate the unified four-mode gate D(t) (Section 4.8):
      - Mode 1 (Online Reweight): brief anomaly (\Delta t < \Delta t_min) and ||P_prop|| << \Sigma_bridge
      - Mode 2 (Atomic Commit): J_v^{after} >= \tau_info and D_holdout <= \tau_val and ||P_after|| <= \Sigma_tol
      - Mode 3 (Soft Bridge / Wait): unverified/insufficient info, but ||P_prop|| < \Sigma_bridge
      - Mode 4 (Hard Sleep / Split): unverified/insufficient info and ||P_prop|| >= \Sigma_bridge
    """
    v = np.asarray(segment.weak_direction_6d, dtype=np.float64).reshape(6)
    v_norm = np.linalg.norm(v)
    if v_norm > 1e-12:
        v = v / v_norm
    else:
        v = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float64)

    info_before = float(v.T @ segment.info_before_6x6 @ v)
    duration_sec = max(0.0, (segment.t_end_ns - segment.t_start_ns) * 1e-9)
    p_prop = float(segment.propagated_cov_norm)

    if duration_sec < thresholds.min_duration_sec and p_prop < 0.25 * thresholds.sigma_bridge:
        return ValidationReport(
            accepted=False,
            mode=RecoveryMode.MODE1_ONLINE_REWEIGHT,
            weak_dir_info_before=info_before,
            weak_dir_info_after=info_before,
            weak_dir_info_gain=0.0,
            holdout_nis=0.0 if candidate is None else float(candidate.holdout_nis),
            posterior_cov_norm=p_prop,
            propagated_cov_norm=p_prop,
            reason="Brief anomaly within online directional reweighting margin",
        )

    if candidate is not None:
        # Reject any candidate containing non-finite (NaN / Inf) poses, covariances, or information matrices (R3 fix)
        poses_finite = bool(
            candidate.repaired_poses
            and all(np.isfinite(p).all() for p in candidate.repaired_poses.values())
        )
        mats_finite = bool(
            np.isfinite(candidate.info_after_6x6).all()
            and np.isfinite(candidate.cov_after_6x6).all()
            and np.isfinite(candidate.holdout_nis)
        )
        if not (poses_finite and mats_finite):
            return ValidationReport(
                accepted=False,
                mode=RecoveryMode.MODE3_SOFT_BRIDGE_WAIT if p_prop < thresholds.sigma_bridge else RecoveryMode.MODE4_HARD_SLEEP_SPLIT,
                weak_dir_info_before=info_before,
                weak_dir_info_after=0.0,
                weak_dir_info_gain=-info_before,
                holdout_nis=float("inf"),
                posterior_cov_norm=float("inf"),
                propagated_cov_norm=p_prop,
                reason="Rejected candidate due to non-finite (NaN/Inf) state or covariance values",
            )

        info_after = float(v.T @ candidate.info_after_6x6 @ v)
        info_gain = info_after - info_before
        p_after = float(np.linalg.norm(candidate.cov_after_6x6, ord=2))
        d_hold = float(candidate.holdout_nis)

        if (
            info_after >= thresholds.tau_info
            and info_gain > 0.0
            and d_hold <= thresholds.tau_val_nis
            and p_after <= thresholds.sigma_tol
        ):
            return ValidationReport(
                accepted=True,
                mode=RecoveryMode.MODE2_ATOMIC_COMMIT,
                weak_dir_info_before=info_before,
                weak_dir_info_after=info_after,
                weak_dir_info_gain=info_gain,
                holdout_nis=d_hold,
                posterior_cov_norm=p_after,
                propagated_cov_norm=p_prop,
                reason="Passed weak-direction information gain and holdout consistency checks",
            )
    else:
        info_after = info_before
        info_gain = 0.0
        p_after = p_prop
        d_hold = float("inf")

    if p_prop < thresholds.sigma_bridge:
        return ValidationReport(
            accepted=False,
            mode=RecoveryMode.MODE3_SOFT_BRIDGE_WAIT,
            weak_dir_info_before=info_before,
            weak_dir_info_after=info_after,
            weak_dir_info_gain=info_gain,
            holdout_nis=d_hold,
            posterior_cov_norm=p_after,
            propagated_cov_norm=p_prop,
            reason="Insufficient verified info; maintaining soft bridge while waiting for new evidence",
        )

    return ValidationReport(
        accepted=False,
        mode=RecoveryMode.MODE4_HARD_SLEEP_SPLIT,
        weak_dir_info_before=info_before,
        weak_dir_info_after=info_after,
        weak_dir_info_gain=info_gain,
        holdout_nis=d_hold,
        posterior_cov_norm=p_after,
        propagated_cov_norm=p_prop,
        reason="Propagated uncertainty exceeded bridge bound without verifiable repair; splitting to sleeping submap",
    )
