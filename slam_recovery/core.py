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


TANGENT_ORDERS = ("rot_trans", "trans_rot")
TANGENT_FRAMES = ("world", "body")


class TangentFrameError(ValueError):
    """A tangent quantity whose frame/parameterization is missing or not the one required."""


class MissingTangentFrame(TangentFrameError):
    """The producer did not say which frame and block order a 6D quantity is expressed in."""


class TangentFrameMismatch(TangentFrameError):
    """Two 6D quantities that are multiplied together live in different frames."""


class MissingAnchorPose(TangentFrameError):
    """A world-declared quantity needs the anchor body frame's pose to be evaluated in it."""


@dataclass(frozen=True)
class TangentFrame:
    """Where a 6D tangent quantity lives, and how its six blocks are ordered.

    `frame`  "world" or "body"; `anchor` names *which* instance (a body frame is per scan, so
             "body" alone does not identify a basis).
    `order`  "rot_trans" ([rot(3), trans(3)], the convention of `compute_6dof_point_to_plane_fim`)
             or "trans_rot".

    A 6D information matrix and a weak direction may only be multiplied if their specs compare
    equal. Nothing defaults: a quantity that does not say where it lives cannot be used.
    """

    frame: str
    order: str = "rot_trans"
    anchor: str = ""

    def __post_init__(self) -> None:
        if self.frame not in TANGENT_FRAMES:
            raise TangentFrameError(f"frame must be one of {TANGENT_FRAMES}, got {self.frame!r}")
        if self.order not in TANGENT_ORDERS:
            raise TangentFrameError(f"order must be one of {TANGENT_ORDERS}, got {self.order!r}")
        if not str(self.anchor).strip():
            raise MissingTangentFrame(
                "TangentFrame.anchor is required: 'world' or the scan/keyframe a body frame "
                "belongs to -- 'body' on its own does not identify a basis"
            )

    def __str__(self) -> str:
        return f"{self.frame}[{self.anchor}]/{self.order}"


def _skew(t: np.ndarray) -> np.ndarray:
    return np.array([[0.0, -t[2], t[1]],
                     [t[2], 0.0, -t[0]],
                     [-t[1], t[0], 0.0]], dtype=np.float64)


def adjoint(T: np.ndarray, order: str = "rot_trans") -> np.ndarray:
    """Ad_T for twists, block order given by `order`; T maps a point from A to B.

    rot_trans:  [[R, 0], [[t]x R, R]]      trans_rot: P (.) P^T, P = block swap.
    """
    T = np.asarray(T, dtype=np.float64)
    if T.shape != (4, 4):
        raise ValueError(f"adjoint expects a 4x4 SE(3) matrix, got {T.shape}")
    R = T[:3, :3]
    Ad = np.zeros((6, 6), dtype=np.float64)
    Ad[:3, :3] = R
    if order == "rot_trans":
        Ad[3:, :3] = _skew(T[:3, 3]) @ R
        Ad[3:, 3:] = R
    elif order == "trans_rot":
        Ad[:3, :3] = R
        Ad[:3, 3:] = _skew(T[:3, 3]) @ R
        Ad[3:, 3:] = R
    else:
        raise TangentFrameError(f"order must be one of {TANGENT_ORDERS}, got {order!r}")
    return Ad


def transport(v: np.ndarray, T: np.ndarray, order: str = "rot_trans") -> np.ndarray:
    """Move a 6D direction from frame A to frame B: v_B = Ad_{T_BA} v_A."""
    return adjoint(T, order=order) @ np.asarray(v, dtype=np.float64).reshape(6)


def transport_information(info: np.ndarray, T: np.ndarray, order: str = "rot_trans") -> np.ndarray:
    """Move a 6x6 information matrix from A to B: L_B = Ad^-T L_A Ad^-1.

    Chosen so the profiled scalar is invariant:  v_B^T L_B v_B == v_A^T L_A v_A.
    """
    Ad = adjoint(T, order=order)
    Ad_inv = np.linalg.inv(Ad)
    return Ad_inv.T @ np.asarray(info, dtype=np.float64).reshape(6, 6) @ Ad_inv


def transport_covariance(cov: np.ndarray, T: np.ndarray, order: str = "rot_trans") -> np.ndarray:
    """Move a 6x6 covariance from A to B: P_B = Ad P_A Ad^T.

    Information and covariance must move together and in opposite directions; transporting one and
    not the other is how a gate ends up comparing a body covariance against a world threshold.
    """
    Ad = adjoint(T, order=order)
    return Ad @ np.asarray(cov, dtype=np.float64).reshape(6, 6) @ Ad.T


def require_tangent_frame(spec: Optional[TangentFrame], where: str) -> TangentFrame:
    """Refuse an undeclared quantity. There is no default frame."""
    if spec is None:
        raise MissingTangentFrame(
            f"{where} carries no TangentFrame: a 6D quantity that does not declare its frame "
            "and block order cannot be used -- fill it at the producer, do not assume one"
        )
    if not isinstance(spec, TangentFrame):
        raise TangentFrameError(f"{where} must be a TangentFrame, got {type(spec).__name__}")
    return spec


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
    # A 6D direction and a 6x6 information matrix mean nothing on their own: the scalar the gate
    # forms is only the information along a physical direction if both are expressed in the same
    # basis, with the same block order. Both must be declared by the producer.
    weak_direction_frame: Optional[TangentFrame] = None
    info_before_frame: Optional[TangentFrame] = None
    # T_world_from_anchor: maps a point from the *anchor* body frame to world. The gate evaluates
    # in that body frame and needs this to bring a world-declared candidate's information and
    # covariance back into it. Keeping the anchor (and its pose) is what makes the evaluation
    # basis fixed: an origin-free tangent space does not exist, and the covariance norm in
    # particular is not invariant to where the origin is.
    anchor_pose_world: Optional[np.ndarray] = None

    def __post_init__(self) -> None:
        require_tangent_frame(self.weak_direction_frame, "QuarantineSegment.weak_direction_frame")
        require_tangent_frame(self.info_before_frame, "QuarantineSegment.info_before_frame")


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
    # The basis `info_after_6x6` lives in. The gate profiles it along the segment's weak direction,
    # so this must be the same basis or be transportable into it.
    info_after_frame: Optional[TangentFrame] = None
    # The basis `cov_after_6x6` lives in. It is compared against a fixed norm bound, and the
    # spectral norm of a covariance depends on where the origin is, so the covariance has to
    # declare its basis exactly as the information does.
    cov_after_frame: Optional[TangentFrame] = None
    used_evidence_refs: List[str] = field(default_factory=list)
    repairer_name: str = ""
    repaired_factor_ids: Optional[List[int]] = None
    repaired_bias_acc: Optional[np.ndarray] = None
    repaired_bias_gyr: Optional[np.ndarray] = None
    # Paired-benefit evidence (Section 4.9). ``None`` means "not measured": a candidate that
    # merely omits these fields must never be treated as having passed them. Only an explicitly
    # measured pass may unlock Mode 2 atomic commit.
    paired_benefit_approved: Optional[bool] = None
    wilson_lower_bound: Optional[float] = None
    reentry_pos_jump_m: Optional[float] = None
    # How long the platform had to travel between the anchor and the boundary frame. Without it
    # the jump is compared as if the two poses were instantaneous neighbours, which refuses every
    # candidate on a moving platform once a confirmation margin exists.
    reentry_elapsed_s: Optional[float] = None
    # The set of keyframes whose poses were actually scored against an independent reference.
    # Mode 2 commits exactly ``repaired_poses``, so this set is the commit invariant: a frame that
    # produced no evidence must never be committed alongside the frames that did. ``None`` means
    # the caller did not make a verification claim (legacy callers); the transaction manager then
    # cannot enforce independence for it and records that fact rather than assuming coverage.
    verified_pose_keys: Optional[frozenset] = None
    # Candidate frames left out of the commit because they could not be independently scored.
    # They stay quarantined; they are not "rejected", they are "not yet verifiable".
    deferred_pose_keys: tuple = ()
    # A commit set may be non-contiguous. Each contiguous run after the first starts at a hole,
    # so its entry boundary must be checked independently: one global re-entry jump measured at
    # the first keyframe says nothing about a segment that begins 1.5 m away after a gap.
    boundary_continuity_ok: Optional[bool] = None
    boundary_jumps_m: Optional[List[float]] = None
    # How the boundary was judged. "BOUND_ONLY" means an elapsed-time speed envelope, not an
    # independent relative-motion measurement; a legitimate displacement and a wrong offset are
    # indistinguishable in that regime, and the gate records the weaker basis rather than
    # presenting it as continuity evidence.
    boundary_basis: str = ""


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
    # Tri-state outcome of the paired-benefit / re-entry evidence check (Section 4.9):
    #   "PASSED"  -> measured and satisfied; the only status that can unlock Mode 2
    #   "MISSING" -> the candidate supplied no measurement; Mode 2 is refused
    #   "FAILED"  -> measured and violated (or non-finite); Mode 2 is refused
    #   "NOT_APPLICABLE" -> the gate never reached the candidate branch (Mode 1/3/4)
    evidence_status: str = "NOT_APPLICABLE"
    # Audit of what Mode 2 actually wrote into the trusted map. ``partial_commit`` is True when
    # the candidate carried frames that could not be independently scored; those frames are
    # listed in ``deferred_pose_keys`` and remain outside the trusted map.
    committed_pose_keys: Optional[List[int]] = None
    deferred_pose_keys: Optional[List[int]] = None
    partial_commit: bool = False
    # See CandidateMap.boundary_basis; empty when the gate never reached a candidate.
    boundary_basis: str = ""
    newly_deferred_pose_keys: Optional[List[int]] = None
    remaining_pending_pose_keys: Optional[List[int]] = None


def _into_basis(value, spec: Optional[TangentFrame], target: TangentFrame,
                T_body_world: Optional[np.ndarray], what: str, kind: str):
    """Move one 6D quantity into the fixed evaluation basis, or refuse.

    `kind` is "direction", "information" or "covariance": information and covariance move in
    opposite directions and must never be transported as if they were the same object.
    `T_body_world` maps world points to the anchor body frame. It is only available when the
    segment carried `anchor_pose_world`; without it a world-declared quantity cannot be evaluated
    and is refused rather than read through a norm that silently depends on the origin.
    """
    spec = require_tangent_frame(spec, f"{what}_frame")
    if spec.order != target.order:
        raise TangentFrameMismatch(
            f"{what} is declared with block order {spec.order!r} but the evaluation basis uses "
            f"{target.order!r}")
    if spec == target:
        return np.asarray(value, dtype=np.float64)
    if spec.frame == "world" and T_body_world is not None:
        if kind == "information":
            return transport_information(value, T_body_world, order=spec.order)
        if kind == "covariance":
            return transport_covariance(value, T_body_world, order=spec.order)
        return transport(value, T_body_world, order=spec.order)
    raise TangentFrameMismatch(
        f"{what} is in {spec} but the gate evaluates in {target}: no transform is available to "
        "reconcile them. Declare the quantity in the evaluation basis, or carry "
        "QuarantineSegment.anchor_pose_world so it can be transported."
    )


@dataclass(frozen=True)
class GateThresholds:
    """Thresholds for the unified four-mode gate D(t) in Section 4.8."""

    min_duration_sec: float = 1.0          # \Delta t_{min} for Mode 1 vs quarantine
    # Information along the weak direction. An absolute bound alone is not scale-free: on one bag
    # the trigger frame's own information ranged 1.10 to 40.23, so any constant floor inside that
    # range decides the outcome by which frame happened to trigger. The criterion is therefore
    # relative (the repair must increase the information by a factor) with an absolute floor that
    # only rejects candidates carrying less information than the trigger geometry itself.
    tau_abs_min: float = 3.0               # v^T \Lambda_{after} v >= this (measured floor, see prereg)
    tau_info_kappa: float = 2.0            # and v^T \Lambda_{after} v >= kappa * v^T \Lambda_{before} v
    tau_val_nis: float = 2.5               # Maximum normalized holdout innovation squared D_{holdout}
    sigma_tol: float = 0.50                # Posterior covariance norm tolerance ||P_{after}||
    sigma_bridge: float = 4.00             # Bridge uncertainty upper bound \Sigma_{bridge}
    min_wilson_lower_bound: float = 0.55   # Minimum Wilson score lower bound on paired holdout benefit
    max_reentry_jump_m: float = 0.50       # Maximum re-entry boundary position jump (m)


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
    # The evaluation basis is FIXED: the trigger scan's body frame. Every 6D quantity the gate
    # multiplies is brought into that one basis before anything is computed, because the quantities
    # the gate compares are not origin-free. A weak direction carried into a translated world frame
    # no longer has unit length there (Ad is not orthogonal when the translation is non-zero), so
    # re-normalising it in world silently rescales the information; and a covariance's spectral
    # norm is not invariant to the origin either. Evaluating in the anchor body frame removes both
    # by construction rather than by remembering not to normalise.
    v_frame = require_tangent_frame(segment.weak_direction_frame,
                                    "QuarantineSegment.weak_direction_frame")
    info_before_frame = require_tangent_frame(segment.info_before_frame,
                                              "QuarantineSegment.info_before_frame")
    if v_frame != info_before_frame:
        raise TangentFrameMismatch(
            f"weak_direction is in {v_frame} but info_before is in {info_before_frame}: "
            "v^T Lambda v would mix two bases. Transport one of them into the other's frame and "
            "declare the result; the gate will not pick a frame for you."
        )
    target = TangentFrame("body", v_frame.order,
                          v_frame.anchor if v_frame.frame == "body" else "anchor")
    T_body_world = None
    if v_frame.frame == "world" or (candidate is not None
                                    and candidate.info_after_frame is not None
                                    and candidate.info_after_frame.frame == "world"):
        if segment.anchor_pose_world is None:
            raise MissingAnchorPose(
                "the gate evaluates in the trigger scan's body frame, and a world-declared "
                "quantity needs QuarantineSegment.anchor_pose_world (T_world_from_anchor) to be "
                "brought there; the origin of the tangent space cannot be left unnamed"
            )
        T_body_world = np.linalg.inv(np.asarray(segment.anchor_pose_world, dtype=np.float64))

    v = _into_basis(segment.weak_direction_6d, v_frame, target, T_body_world,
                    "weak_direction", kind="direction")
    info_before_basis = _into_basis(segment.info_before_6x6, info_before_frame, target,
                                    T_body_world, "info_before", kind="information")
    v = np.asarray(v, dtype=np.float64).reshape(6)
    # Safe now: the vector is in the (rigid, orthonormal) anchor body frame, not in a frame reached
    # through a translation-bearing adjoint.
    v_norm = np.linalg.norm(v)
    if v_norm > 1e-12:
        v = v / v_norm
    else:
        v = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float64)

    info_before = float(v.T @ np.asarray(info_before_basis, dtype=np.float64) @ v)

    # The candidate's information and covariance are brought into the same basis before either is
    # used. Before this, the covariance was compared against a fixed bound in whatever basis its
    # producer happened to work in, and a plain translation moved that number.
    info_after_basis = None
    cov_after_basis = None
    if candidate is not None:
        info_after_basis = _into_basis(candidate.info_after_6x6, candidate.info_after_frame,
                                       target, T_body_world, "info_after", kind="information")
        cov_after_basis = _into_basis(candidate.cov_after_6x6, candidate.cov_after_frame,
                                      target, T_body_world, "cov_after", kind="covariance")
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

    evidence_status = "NOT_APPLICABLE"
    if candidate is not None:
        # Tri-state paired-benefit evidence (Section 4.9). A candidate that simply omits the
        # evidence is *not* treated as having passed it: "missing" can never reach Mode 2.
        def _bad_optional(value: Optional[float], bound: float, is_lower_bound: bool) -> bool:
            if value is None:
                return False
            f = float(value)
            if not np.isfinite(f):
                return True
            return f < bound if is_lower_bound else f > bound

        # The re-entry leg is a *discontinuity* bound, so a distance that elapsed time can explain
        # is not a failure. Same envelope as boundary_continuity_ok, otherwise one report would
        # carry two definitions of the same boundary.
        reentry_ok = True
        if candidate.reentry_pos_jump_m is not None:
            if candidate.reentry_elapsed_s is None:
                reentry_ok = float(candidate.reentry_pos_jump_m) <= thresholds.max_reentry_jump_m
            else:
                reentry_ok = (
                    float(candidate.reentry_pos_jump_m)
                    <= thresholds.max_reentry_jump_m + 2.0 * max(0.0, candidate.reentry_elapsed_s))
        evidence_failed = bool(
            candidate.paired_benefit_approved is False
            or _bad_optional(candidate.wilson_lower_bound, thresholds.min_wilson_lower_bound, True)
            or not reentry_ok
        )
        evidence_missing = bool(
            candidate.paired_benefit_approved is None
            or candidate.wilson_lower_bound is None
            or candidate.reentry_pos_jump_m is None
        )
        evidence_status = "FAILED" if evidence_failed else ("MISSING" if evidence_missing else "PASSED")

        # Reject any candidate containing non-finite (NaN / Inf) poses, biases, covariances, or invalid pose shapes (R3 & F4 fix)
        def _is_valid_pose_array(p: np.ndarray) -> bool:
            arr = np.asarray(p, dtype=np.float64)
            if not np.isfinite(arr).all():
                return False
            if arr.shape == (3,):
                return True
            if arr.shape == (4, 4):
                return bool(np.allclose(arr[3, :], [0.0, 0.0, 0.0, 1.0], atol=1e-4))
            return False

        poses_valid = bool(
            candidate.repaired_poses
            and all(_is_valid_pose_array(p) for p in candidate.repaired_poses.values())
        )
        bias_acc_valid = (
            True
            if candidate.repaired_bias_acc is None
            else (
                np.asarray(candidate.repaired_bias_acc).shape == (3,)
                and bool(np.isfinite(candidate.repaired_bias_acc).all())
            )
        )
        bias_gyr_valid = (
            True
            if candidate.repaired_bias_gyr is None
            else (
                np.asarray(candidate.repaired_bias_gyr).shape == (3,)
                and bool(np.isfinite(candidate.repaired_bias_gyr).all())
            )
        )
        # holdout_nis is excluded from the finite-state check on purpose. A candidate with no
        # scorable holdout frame carries +inf by construction; treating that as a non-finite
        # *state* mislabels "no evidence" as "invalid pose", which is the opposite of what the
        # operator needs to see. Positive infinity is routed to its own MISSING reason below;
        # NaN is a genuine numeric defect and stays in this rejection.
        holdout_nis_value = float(candidate.holdout_nis)
        holdout_missing = bool(np.isinf(holdout_nis_value))
        mats_finite = bool(
            np.asarray(info_after_basis).shape == (6, 6)
            and np.asarray(cov_after_basis).shape == (6, 6)
            and np.isfinite(info_after_basis).all()
            and np.isfinite(cov_after_basis).all()
            and not np.isnan(holdout_nis_value)
        )
        if not (poses_valid and bias_acc_valid and bias_gyr_valid and mats_finite):
            return ValidationReport(
                accepted=False,
                mode=RecoveryMode.MODE3_SOFT_BRIDGE_WAIT if p_prop < thresholds.sigma_bridge else RecoveryMode.MODE4_HARD_SLEEP_SPLIT,
                weak_dir_info_before=info_before,
                weak_dir_info_after=0.0,
                weak_dir_info_gain=-info_before,
                holdout_nis=float("inf"),
                posterior_cov_norm=float("inf"),
                propagated_cov_norm=p_prop,
                reason="Rejected candidate due to non-finite (NaN/Inf) state/bias or invalid SE(3) pose shape",
                evidence_status=evidence_status,
            )

        info_after = float(v.T @ np.asarray(info_after_basis, dtype=np.float64) @ v)
        info_gain = info_after - info_before
        p_after = float(np.linalg.norm(np.asarray(cov_after_basis, dtype=np.float64), ord=2))
        d_hold = float(candidate.holdout_nis)

        # No scorable holdout frame: the candidate supplied no cross-scan evidence at all. This is
        # a wait, not a rejection of the poses, and the reason string must say so.
        if holdout_missing:
            return ValidationReport(
                accepted=False,
                mode=RecoveryMode.MODE3_SOFT_BRIDGE_WAIT if p_prop < thresholds.sigma_bridge else RecoveryMode.MODE4_HARD_SLEEP_SPLIT,
                weak_dir_info_before=info_before,
                weak_dir_info_after=info_after,
                weak_dir_info_gain=info_gain,
                holdout_nis=float("inf"),
                posterior_cov_norm=p_after,
                propagated_cov_norm=p_prop,
                reason=(
                    "Refused Mode 2 atomic commit: holdout evidence MISSING "
                    "(no scorable holdout frame against the independent reference)"
                ),
                # The machine-readable status must not keep saying PASSED when the holdout half of
                # the evidence is absent. Downstream consumers aggregate this field, and a
                # paired-only pass is not a pass for admission.
                evidence_status="MISSING",
            )

        # A non-contiguous commit is allowed, but every run after a gap must reconnect to the
        # previously committed keyframe. One first-anchor jump cannot speak for those boundaries.
        if candidate.boundary_continuity_ok is False:
            return ValidationReport(
                accepted=False,
                mode=RecoveryMode.MODE3_SOFT_BRIDGE_WAIT if p_prop < thresholds.sigma_bridge else RecoveryMode.MODE4_HARD_SLEEP_SPLIT,
                weak_dir_info_before=info_before,
                weak_dir_info_after=info_after,
                weak_dir_info_gain=info_gain,
                holdout_nis=d_hold,
                posterior_cov_norm=p_after,
                propagated_cov_norm=p_prop,
                reason=(
                    "Refused Mode 2 atomic commit: a committed segment begins beyond the boundary "
                    "jump bound (per-segment continuity failed)"
                ),
                evidence_status=evidence_status,
            )

        if evidence_status != "PASSED":
            return ValidationReport(
                accepted=False,
                mode=RecoveryMode.MODE3_SOFT_BRIDGE_WAIT if p_prop < thresholds.sigma_bridge else RecoveryMode.MODE4_HARD_SLEEP_SPLIT,
                weak_dir_info_before=info_before,
                weak_dir_info_after=info_after,
                weak_dir_info_gain=info_gain,
                holdout_nis=d_hold,
                posterior_cov_norm=p_after,
                propagated_cov_norm=p_prop,
                reason=(
                    "Refused Mode 2 atomic commit: paired-benefit evidence MISSING "
                    "(candidate did not report paired_benefit_approved / wilson_lower_bound / reentry_pos_jump_m)"
                    if evidence_status == "MISSING"
                    else "Refused Mode 2 atomic commit: paired-benefit evidence FAILED "
                    "(explicit failure, non-finite value, or threshold violation)"
                ),
                evidence_status=evidence_status,
            )

        wilson_ok = True  # evidence_status == "PASSED" is the only way to reach this point

        if (
            info_after >= thresholds.tau_abs_min
            and info_after >= thresholds.tau_info_kappa * max(info_before, 1e-12)
            and info_gain > 0.0
            and d_hold <= thresholds.tau_val_nis
            and p_after <= thresholds.sigma_tol
            and wilson_ok
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
                reason="Passed weak-direction information gain, holdout consistency, and paired Wilson sequential checks",
                evidence_status="PASSED",
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
            evidence_status=evidence_status,
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
        evidence_status=evidence_status,
    )
