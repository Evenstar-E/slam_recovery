"""Quarantine buffer, delayed commit, and atomic map state transactions (Sections 5.2, 5.3, 8.7)."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional, Tuple
import numpy as np

from ..core import (
    BackendDelta,
    CandidateMap,
    Checkpoint,
    GateThresholds,
    QuarantineSegment,
    RecoveryMode,
    RecoveryState,
    ValidationReport,
    evaluate_four_mode_gate,
)


class TrustedMapTransactionManager:
    """
    Maintains the strict separation between:
      - Provisional live map (updated continuously for online continuity)
      - Trusted persistent map (only receives updates aged past the confirmation margin
        or atomically committed after passing independent validation).
    """

    def __init__(
        self,
        confirmation_margin_ns: int = int(2.0 * 1e9),
        gate_thresholds: GateThresholds = GateThresholds(),
    ) -> None:
        self.confirmation_margin_ns = int(confirmation_margin_ns)
        self.gate_thresholds = gate_thresholds
        self.state: RecoveryState = RecoveryState.HEALTHY

        self.trusted_version: int = 0
        self.trusted_poses: Dict[int, np.ndarray] = {}
        self.trusted_factors: List[int] = []
        self.trusted_bias_acc = np.zeros(3, dtype=np.float64)
        self.trusted_bias_gyr = np.zeros(3, dtype=np.float64)

        self.provisional_queue: List[BackendDelta] = []
        self.checkpoints: List[Checkpoint] = []
        self.active_quarantine: Optional[QuarantineSegment] = None
        self.sleeping_submaps: List[Dict[int, np.ndarray]] = []
        self.commit_history: List[Tuple[int, str, ValidationReport]] = []

    def create_checkpoint(self, timestamp_ns: int) -> Checkpoint:
        ckpt_id = f"ckpt_v{self.trusted_version}_{timestamp_ns}"
        ckpt = Checkpoint(
            checkpoint_id=ckpt_id,
            timestamp_ns=timestamp_ns,
            map_version=self.trusted_version,
            keyframe_poses=deepcopy(self.trusted_poses),
            factor_ids=list(self.trusted_factors),
            imu_bias_acc=self.trusted_bias_acc.copy(),
            imu_bias_gyr=self.trusted_bias_gyr.copy(),
        )
        ckpt.state_hash = ckpt.compute_hash()
        self.checkpoints.append(ckpt)
        return ckpt

    def restore_checkpoint(self, ckpt: Checkpoint) -> None:
        if ckpt.compute_hash() != ckpt.state_hash:
            raise RuntimeError(f"Checkpoint hash mismatch for {ckpt.checkpoint_id}")
        self.trusted_version = ckpt.map_version
        self.trusted_poses = deepcopy(ckpt.keyframe_poses)
        self.trusted_factors = list(ckpt.factor_ids)
        self.trusted_bias_acc = ckpt.imu_bias_acc.copy()
        self.trusted_bias_gyr = ckpt.imu_bias_gyr.copy()

    def step_healthy(self, delta: BackendDelta) -> int:
        """
        Buffer provisional update and promote only updates older than
        current_time - confirmation_margin_ns into the trusted map.
        Returns number of newly promoted keyframes.
        """
        if self.state != RecoveryState.HEALTHY:
            raise RuntimeError(f"Cannot step_healthy while in state {self.state}")

        self.provisional_queue.append(delta)
        cutoff_ns = delta.timestamp_ns - self.confirmation_margin_ns
        promoted = 0
        remaining: List[BackendDelta] = []

        for item in self.provisional_queue:
            if item.timestamp_ns <= cutoff_ns:
                if item.keyframe_id is not None:
                    self.trusted_poses[item.keyframe_id] = item.pose_se3.copy()
                self.trusted_factors.extend(item.factor_ids)
                self.trusted_bias_acc = item.bias_acc.copy()
                self.trusted_bias_gyr = item.bias_gyr.copy()
                item.provisional = False
                promoted += 1
            else:
                remaining.append(item)

        if promoted > 0:
            self.trusted_version += 1
        self.provisional_queue = remaining
        return promoted

    def trigger_quarantine(
        self,
        estimated_onset_ns: int,
        current_ns: int,
        weak_direction_6d: np.ndarray,
        info_before_6x6: np.ndarray,
        propagated_cov_norm: float,
    ) -> QuarantineSegment:
        """
        Roll back provisional updates starting at t_{q,start} = \hat{t}_{onset} - \Delta t_{margin},
        promote any safe pre-onset deltas, freeze a trusted checkpoint, and open a QuarantineSegment.
        """
        t_q_start = estimated_onset_ns - self.confirmation_margin_ns
        safe_pre_onset = [d for d in self.provisional_queue if d.timestamp_ns < t_q_start]
        quarantined_deltas = [d for d in self.provisional_queue if d.timestamp_ns >= t_q_start]

        for item in safe_pre_onset:
            if item.keyframe_id is not None:
                self.trusted_poses[item.keyframe_id] = item.pose_se3.copy()
            self.trusted_factors.extend(item.factor_ids)
            self.trusted_bias_acc = item.bias_acc.copy()
            self.trusted_bias_gyr = item.bias_gyr.copy()
        if safe_pre_onset:
            self.trusted_version += 1

        ckpt = self.create_checkpoint(timestamp_ns=t_q_start)
        prov_factors: List[int] = []
        for d in quarantined_deltas:
            prov_factors.extend(d.factor_ids)

        self.provisional_queue = quarantined_deltas
        self.state = RecoveryState.QUARANTINED
        self.active_quarantine = QuarantineSegment(
            segment_id=f"quar_{ckpt.map_version}_{t_q_start}",
            checkpoint=ckpt,
            t_start_ns=t_q_start,
            t_end_ns=current_ns,
            weak_direction_6d=weak_direction_6d.copy(),
            info_before_6x6=info_before_6x6.copy(),
            propagated_cov_norm=propagated_cov_norm,
            provisional_factor_ids=prov_factors,
        )
        return self.active_quarantine

    def validate_and_resolve(
        self,
        candidate: Optional[CandidateMap],
        updated_propagated_cov_norm: Optional[float] = None,
    ) -> ValidationReport:
        """
        Run the unified 4-mode gate and execute atomic commit, soft-bridge wait, or hard sleep split.
        """
        if self.active_quarantine is None:
            raise RuntimeError("No active quarantine segment to validate")

        if updated_propagated_cov_norm is not None:
            self.active_quarantine.propagated_cov_norm = float(updated_propagated_cov_norm)

        self.state = RecoveryState.VALIDATING
        report = evaluate_four_mode_gate(
            self.active_quarantine,
            candidate,
            self.gate_thresholds,
        )

        if report.mode == RecoveryMode.MODE2_ATOMIC_COMMIT and candidate is not None:
            if candidate.parent_map_version != self.trusted_version:
                raise RuntimeError("Candidate parent_map_version does not match current trusted_version")
            new_poses = deepcopy(self.trusted_poses)
            for kf_id, pose in candidate.repaired_poses.items():
                new_poses[kf_id] = pose.copy()
            self.trusted_poses = new_poses
            self.trusted_version += 1
            self.provisional_queue.clear()
            self.active_quarantine = None
            self.state = RecoveryState.HEALTHY
            self.commit_history.append((self.trusted_version, candidate.candidate_id, report))
        elif report.mode in (RecoveryMode.MODE3_SOFT_BRIDGE_WAIT, RecoveryMode.MODE1_ONLINE_REWEIGHT):
            # Trusted map stays strictly invariant; system waits for delayed loop or auxiliary evidence
            self.state = RecoveryState.WAITING_FOR_EVIDENCE
        elif report.mode == RecoveryMode.MODE4_HARD_SLEEP_SPLIT:
            # Archive current trusted map into sleeping submaps and reset active trusted map cleanly
            if self.trusted_poses:
                self.sleeping_submaps.append(deepcopy(self.trusted_poses))
            self.provisional_queue.clear()
            self.active_quarantine = None
            self.state = RecoveryState.ABORTED

        return report
