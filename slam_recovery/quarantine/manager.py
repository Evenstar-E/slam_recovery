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
        self.promoted_history: List[BackendDelta] = []
        # Before-image undo records aligned 1-to-1 with promoted_history for exact rollback (F5 fix).
        # Each entry is (prev_pose, prev_factor_len, prev_bias_acc, prev_bias_gyr); the factor list is
        # append-only, so a length marker is an exact before-image at O(1) memory (P1-4 fix).
        self._promoted_before_images: List[Tuple[Optional[np.ndarray], int, np.ndarray, np.ndarray]] = []
        self.checkpoints: List[Checkpoint] = []
        self.active_quarantine: Optional[QuarantineSegment] = None
        self.sleeping_submaps: List[Dict[int, np.ndarray]] = []
        self.commit_history: List[Tuple[int, str, ValidationReport]] = []

    def _apply_promote(self, item: BackendDelta) -> None:
        prev_pose = (
            self.trusted_poses[item.keyframe_id].copy()
            if (item.keyframe_id is not None and item.keyframe_id in self.trusted_poses)
            else None
        )
        # Append-only factor log: record the pre-promotion length instead of a full history copy,
        # so rollback is a truncation and the undo log grows O(1) per promotion (P1-4 fix).
        prev_factor_len = len(self.trusted_factors)
        prev_ba = self.trusted_bias_acc.copy()
        prev_bg = self.trusted_bias_gyr.copy()
        self._promoted_before_images.append((prev_pose, prev_factor_len, prev_ba, prev_bg))

        if item.keyframe_id is not None:
            self.trusted_poses[item.keyframe_id] = item.pose_se3.copy()
        self.trusted_factors.extend(item.factor_ids)
        self.trusted_bias_acc = item.bias_acc.copy()
        self.trusted_bias_gyr = item.bias_gyr.copy()
        item.provisional = False
        self.promoted_history.append(item)

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
        # Synchronize promoted history to checkpoint timestamp
        while self.promoted_history and self.promoted_history[-1].timestamp_ns >= ckpt.timestamp_ns:
            self.promoted_history.pop()
            if self._promoted_before_images:
                self._promoted_before_images.pop()

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
                self._apply_promote(item)
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

        # Undo-log rollback for late-detected faults (R2 & F5 fix): roll back in reverse chronological order
        # using recorded before-images so overwritten keys and initial biases are restored bit-for-bit!
        revoked_from_trusted: List[BackendDelta] = []
        while self.promoted_history and self.promoted_history[-1].timestamp_ns >= t_q_start:
            item = self.promoted_history.pop()
            item.provisional = True
            revoked_from_trusted.append(item)
            if self._promoted_before_images:
                prev_pose, prev_factor_len, prev_ba, prev_bg = self._promoted_before_images.pop()
                if item.keyframe_id is not None:
                    if prev_pose is not None:
                        self.trusted_poses[item.keyframe_id] = prev_pose.copy()
                    else:
                        self.trusted_poses.pop(item.keyframe_id, None)
                # Truncate the append-only factor log back to its pre-promotion length
                del self.trusted_factors[int(prev_factor_len):]
                self.trusted_bias_acc = prev_ba.copy()
                self.trusted_bias_gyr = prev_bg.copy()
            else:
                if item.keyframe_id is not None:
                    self.trusted_poses.pop(item.keyframe_id, None)
                for fid in item.factor_ids:
                    if fid in self.trusted_factors:
                        self.trusted_factors.remove(fid)
                self.trusted_bias_acc = np.zeros(3, dtype=np.float64)
                self.trusted_bias_gyr = np.zeros(3, dtype=np.float64)
        revoked_from_trusted.reverse()

        for item in safe_pre_onset:
            self._apply_promote(item)
        if safe_pre_onset or revoked_from_trusted:
            self.trusted_version += 1

        quarantined_deltas = revoked_from_trusted + quarantined_deltas

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

        # VALIDATING is an attempt marker, not a committed state.
        state_before_attempt = self.state
        self.state = RecoveryState.VALIDATING
        report = evaluate_four_mode_gate(
            self.active_quarantine,
            candidate,
            self.gate_thresholds,
        )

        if candidate is not None:
            # Report the split on every path, so a Mode 3 wait says which frames it is waiting on
            # just as clearly as a partial Mode 2 commit does.
            report.deferred_pose_keys = [int(k) for k in candidate.deferred_pose_keys]
            report.committed_pose_keys = []
            report.boundary_basis = candidate.boundary_basis

        if report.mode == RecoveryMode.MODE2_ATOMIC_COMMIT and candidate is not None:
            if candidate.parent_map_version != self.trusted_version:
                raise RuntimeError("Candidate parent_map_version does not match current trusted_version")
            # Commit invariant (P1): the manager writes exactly candidate.repaired_poses into the
            # trusted map, so any frame in there must have been independently scored. A caller that
            # declares a verified set that does not cover the candidate is rejected outright rather
            # than allowed to commit unscored frames. ``None`` is the legacy contract: the caller
            # makes no verification claim and the manager cannot check one, which is recorded in
            # the report instead of being silently treated as full coverage.
            if candidate.verified_pose_keys is not None:
                unverified = set(candidate.repaired_poses.keys()) - set(candidate.verified_pose_keys)
                if unverified:
                    raise RuntimeError(
                        "Mode 2 candidate contains frames with no verification evidence: "
                        f"{sorted(unverified)}"
                    )
            try:
                # ---- materialize ---------------------------------------------------------
                # Every caller-supplied object is consumed here, before `self` is touched. A
                # generator (or a mapping whose .items() raises) used to blow up half-way through
                # the commit, leaving the map written, the factors partially extended, the version
                # unchanged and no history entry: four states telling four different stories.
                factor_ids = (None if candidate.repaired_factor_ids is None
                              else [int(f) for f in candidate.repaired_factor_ids])
                pose_items = [(int(k), np.asarray(p, dtype=np.float64).copy())
                              for k, p in candidate.repaired_poses.items()]
                deferred_keys = [int(k) for k in candidate.deferred_pose_keys]
                committed_keys = {k for k, _ in pose_items}
                new_version = self.trusted_version + 1

                # ---- stage --------------------------------------------------------------
                # Everything below computes into locals; `self` is only read, never written.
                new_poses = deepcopy(self.trusted_poses)
                for kf_id, pose in pose_items:
                    new_poses[kf_id] = pose
                new_factors = list(self.trusted_factors)
                if factor_ids is not None:
                    new_factors.extend(factor_ids)
                else:
                    for kf_id in sorted(committed_keys):
                        fid = int(kf_id) * 10
                        if fid not in new_factors:
                            new_factors.append(fid)
                new_bias_acc = (self.trusted_bias_acc if candidate.repaired_bias_acc is None
                                else np.asarray(candidate.repaired_bias_acc,
                                                dtype=np.float64).copy())
                new_bias_gyr = (self.trusted_bias_gyr if candidate.repaired_bias_gyr is None
                                else np.asarray(candidate.repaired_bias_gyr,
                                                dtype=np.float64).copy())
                # A partial commit does not end the quarantine. The deferred frames are still
                # suspect, and clearing the segment would discard their pending subtransaction.
                old_segment = self.active_quarantine
                # pending = old - committed + newly deferred; the quarantine ends only when empty.
                old_pending = set()
                if old_segment is not None:
                    for ref in old_segment.raw_frame_refs:
                        try:
                            old_pending.add(int(ref))
                        except (TypeError, ValueError):
                            continue
                pending = (old_pending | set(deferred_keys)) - committed_keys
                new_checkpoint = None
                new_segment = None
                if pending and old_segment is not None:
                    # Built from the staged post-commit state, which is what create_checkpoint
                    # would have captured after the assignment; only the append is deferred.
                    new_checkpoint = Checkpoint(
                        checkpoint_id=f"ckpt_v{new_version}_{old_segment.t_end_ns}",
                        timestamp_ns=old_segment.t_end_ns,
                        map_version=new_version,
                        keyframe_poses=deepcopy(new_poses),
                        factor_ids=list(new_factors),
                        imu_bias_acc=new_bias_acc.copy(),
                        imu_bias_gyr=new_bias_gyr.copy(),
                    )
                    new_checkpoint.state_hash = new_checkpoint.compute_hash()
                    new_segment = QuarantineSegment(
                        segment_id=f"{old_segment.segment_id}:deferred",
                        checkpoint=new_checkpoint,
                        t_start_ns=old_segment.t_start_ns,
                        t_end_ns=old_segment.t_end_ns,
                        weak_direction_6d=np.asarray(old_segment.weak_direction_6d,
                                                     dtype=np.float64).copy(),
                        info_before_6x6=np.asarray(old_segment.info_before_6x6,
                                                   dtype=np.float64).copy(),
                        propagated_cov_norm=float(old_segment.propagated_cov_norm),
                        raw_frame_refs=[str(k) for k in sorted(pending)],
                    )
                # The receipt describes the *remaining pending set*, not only this candidate's
                # deferrals: a retry committing 8..11 while deferring nothing still leaves 12..19
                # pending, and deferred=[] / partial_commit=False would say the quarantine is done.
                report.committed_pose_keys = sorted(committed_keys)
                report.newly_deferred_pose_keys = sorted(deferred_keys)
                report.remaining_pending_pose_keys = sorted(pending)
                report.deferred_pose_keys = sorted(pending)
                report.partial_commit = bool(pending)
                new_state = (RecoveryState.WAITING_FOR_EVIDENCE
                             if pending and old_segment is not None else RecoveryState.HEALTHY)
                new_history = (new_version, candidate.candidate_id, report)
            except BaseException:
                # No half-written manager, and not stranded in VALIDATING: the caller sees the
                # same exception, and every piece of trusted state is as it was on entry.
                self.state = state_before_attempt
                raise

            # ---- publish ---------------------------------------------------------------------
            # Attribute assignments only: nothing here can fail on caller input.
            self.trusted_poses = new_poses
            self.trusted_factors = new_factors
            self.trusted_bias_acc = new_bias_acc
            self.trusted_bias_gyr = new_bias_gyr
            self.trusted_version = new_version
            if new_checkpoint is not None:
                self.checkpoints.append(new_checkpoint)
            self.provisional_queue.clear()
            self.active_quarantine = new_segment
            self.state = new_state
            self.commit_history.append(new_history)
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
