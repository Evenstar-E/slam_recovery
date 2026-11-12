"""Quarantine buffer, delayed commit, and atomic map state transactions (Sections 5.2, 5.3, 8.7)."""

from __future__ import annotations

from copy import deepcopy
import os
import time
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
    TangentFrame,
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
        wait_limit_ns: Optional[int] = None,
    ) -> None:
        self.confirmation_margin_ns = int(confirmation_margin_ns)
        self.gate_thresholds = gate_thresholds
        self.state: RecoveryState = RecoveryState.HEALTHY
        # How long a Mode 3 wait may stay open without new evidence before the segment is closed
        # unresolved. None keeps the old behaviour (wait indefinitely); a run that must reach a
        # second event declares a value before it starts, because a segment that waits forever
        # never returns to HEALTHY and the detector can never fire again.
        self.wait_limit_ns: Optional[int] = None if wait_limit_ns is None else int(wait_limit_ns)
        self.wait_started_ns: Optional[int] = None
        self._wait_diag_calls = 0
        self.unresolved_segments: List[QuarantineSegment] = []
        self.lifecycle_events: List[dict] = []

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

    def _insert_undo_entry(self, item: "BackendDelta", before_image) -> None:
        """A9: put an undo entry in time order instead of appending.

        promoted_history is a time-monotone stack that the rollback loops pop from the tail. A
        repair can cover frames older than the newest promotions, so appending it would break the
        invariant and stop the pop early. Inserting after every entry with an older timestamp keeps
        the stack ordered, and equal timestamps resolve in insertion order.
        """
        idx = len(self.promoted_history)
        while idx > 0 and self.promoted_history[idx - 1].timestamp_ns > item.timestamp_ns:
            idx -= 1
        self.promoted_history.insert(idx, item)
        self._promoted_before_images.insert(idx, before_image)

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
        *,
        weak_direction_frame: "TangentFrame",
        info_before_frame: "TangentFrame",
        anchor_pose_world: Optional[np.ndarray] = None,
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
        revoked_repair_keys: List[int] = []
        while self.promoted_history and self.promoted_history[-1].timestamp_ns >= t_q_start:
            item = self.promoted_history.pop()
            item.provisional = True
            # A repair undo entry is not a backend delta: it restores a frame the candidate wrote,
            # so it must not be re-queued as provisional evidence. The key it restored is still
            # suspect, though: it leaves the trusted map here, so it has to be listed as pending
            # or it ends up in no population at all (A5 normal path).
            if getattr(item, "undo_kind", "") != "repair":
                revoked_from_trusted.append(item)
            elif item.keyframe_id is not None:
                revoked_repair_keys.append(int(item.keyframe_id))
            if self._promoted_before_images:
                prev_pose, prev_factor_len, prev_ba, prev_bg = self._promoted_before_images.pop()
                if item.keyframe_id is not None:
                    if prev_pose is not None:
                        self.trusted_poses[item.keyframe_id] = prev_pose.copy()
                    else:
                        self.trusted_poses.pop(item.keyframe_id, None)
                if isinstance(prev_factor_len, list):
                    # A9: a repair entry carries the exact pre-repair factor list. Truncating by
                    # length would be wrong here, because the repair may sit in the middle of the
                    # log rather than at its end.
                    self.trusted_factors[:] = prev_factor_len
                else:
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
        # A5: the population of the quarantine is registered here, from the frames the system
        # itself rolled back -- not left empty for a candidate to declare later. Without this, a
        # candidate that commits one frame and declares no deferrals makes the pending set empty
        # and the manager returns to HEALTHY, silently dropping the rest.
        self.active_quarantine = QuarantineSegment(
            segment_id=f"quar_{ckpt.map_version}_{t_q_start}",
            checkpoint=ckpt,
            t_start_ns=t_q_start,
            t_end_ns=current_ns,
            weak_direction_6d=weak_direction_6d.copy(),
            info_before_6x6=info_before_6x6.copy(),
            propagated_cov_norm=propagated_cov_norm,
            raw_frame_refs=[str(int(d.keyframe_id)) for d in quarantined_deltas
                            if getattr(d, "keyframe_id", None) is not None] +
                           [str(k) for k in revoked_repair_keys],
            provisional_factor_ids=prov_factors,
            weak_direction_frame=weak_direction_frame,
            info_before_frame=info_before_frame,
            anchor_pose_world=(None if anchor_pose_world is None
                               else np.asarray(anchor_pose_world, dtype=np.float64).copy()),
        )
        self.active_quarantine.raw_frame_refs = sorted(
            set(self.active_quarantine.raw_frame_refs), key=lambda r: int(r))
        return self.active_quarantine

    def register_quarantined_frame(self, keyframe_id: int, timestamp_ns: int = 0) -> None:
        """A5: record a frame that arrives while a quarantine is open.

        The system, not the candidate, owns the pending population. Idempotent; the reference list
        stays sorted by integer key so the receipt is reproducible.

        A frame that arrives while the segment is waiting also moves its end time: the segment
        spans the frames it actually covers, so a receipt that keeps the trigger instant reads as
        if nothing arrived after it. Timestamps of 0 are taken as "unknown" and leave the end
        time alone, so a caller that has no clock cannot move it backwards.
        """
        if self.active_quarantine is None:
            return
        refs = {str(r) for r in self.active_quarantine.raw_frame_refs}
        refs.add(str(int(keyframe_id)))
        self.active_quarantine.raw_frame_refs = sorted(refs, key=lambda r: int(r))
        if int(timestamp_ns) > 0:
            self.active_quarantine.t_end_ns = max(int(self.active_quarantine.t_end_ns),
                                                  int(timestamp_ns))

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

        # DIAGNOSTIC (no behaviour change): which end time the waiting timer will start from, and
        # when this validation actually ran. Added to separate "the timer is wrong" from "the timer
        # was started late", which the archived runs could not distinguish.
        if os.environ.get("SLAM_RECOVERY_WAITDIAG"):
            print(f"[WAITDIAG] validate_enter wall={time.time():.6f} "
              f"state={self.state} t_end_ns={self.active_quarantine.t_end_ns} "
              f"wait_started_ns={self.wait_started_ns} wait_limit_ns={self.wait_limit_ns}",
              flush=True)

        if updated_propagated_cov_norm is not None:
            self.active_quarantine.propagated_cov_norm = float(updated_propagated_cov_norm)

        # VALIDATING is an attempt marker, not a committed state.
        state_before_attempt = self.state
        self.state = RecoveryState.VALIDATING
        try:
            report = evaluate_four_mode_gate(
                self.active_quarantine,
                candidate,
                self.gate_thresholds,
            )
        except BaseException:
            # The gate can refuse a candidate outright (e.g. an undeclared tangent frame). A
            # refusal is a rejected attempt, not a state transition: the manager must not be left
            # in VALIDATING, where no further step is possible.
            self.state = state_before_attempt
            raise

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
                        # The deferred segment is the same physical segment: it inherits the
                        # declared basis, it does not re-derive one.
                        weak_direction_frame=old_segment.weak_direction_frame,
                        info_before_frame=old_segment.info_before_frame,
                        anchor_pose_world=old_segment.anchor_pose_world,
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

            # ---- A9: make the repair visible to the undo log ------------------------------
            # Until here a Mode 2 commit was invisible to promoted_history, so a later onset that
            # reached back over a repaired frame could not undo it. Record one entry per committed
            # keyframe, timestamped at the segment's close, with the pre-repair state.
            _undo_ts = int(old_segment.t_end_ns) if old_segment is not None else 0
            _pre_factors = list(self.trusted_factors)
            _pre_ba = self.trusted_bias_acc.copy()
            _pre_bg = self.trusted_bias_gyr.copy()
            for _k in sorted(int(k) for k in committed_keys):
                _prev_pose = (self.trusted_poses[_k].copy()
                              if _k in self.trusted_poses else None)
                _entry = BackendDelta(
                    timestamp_ns=_undo_ts,
                    frame_id="map",
                    pose_se3=(_prev_pose.copy() if _prev_pose is not None else np.eye(4)),
                    velocity=np.zeros(3),
                    bias_acc=_pre_ba.copy(),
                    bias_gyr=_pre_bg.copy(),
                    cov_6x6=np.eye(6),
                    info_6x6=np.eye(6),
                    nis_value=0.0,
                    nis_dof=6,
                    factor_ids=[],
                    keyframe_id=_k,
                    provisional=False,
                )
                _entry.undo_kind = "repair"
                self._insert_undo_entry(_entry, (_prev_pose, _pre_factors, _pre_ba, _pre_bg))

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
            # An accepted candidate that leaves nothing pending ends the quarantine. The driver
            # releases the host's map hold from lifecycle events, and this path used to emit
            # none: a full Mode 2 commit returned to HEALTHY silently and the host kept its
            # map hold, so the repaired map was never written again.
            if new_state == RecoveryState.HEALTHY and new_segment is None and old_segment is not None:
                self.lifecycle_events.append({
                    "event": "commit_closed",
                    "segment_id": old_segment.segment_id,
                    "trusted_version": int(new_version),
                    "n_committed": len(committed_keys),
                    "t_end_ns": int(old_segment.t_end_ns),
                })
            if new_state == RecoveryState.WAITING_FOR_EVIDENCE and new_segment is not None:
                self.wait_started_ns = int(new_segment.t_end_ns)
                if os.environ.get("SLAM_RECOVERY_WAITDIAG"):
                    print(f"[WAITDIAG] wait_started_set(from new_segment) wall={time.time():.6f} "
                      f"started={self.wait_started_ns}", flush=True)
            self.commit_history.append(new_history)
        elif report.mode in (RecoveryMode.MODE3_SOFT_BRIDGE_WAIT, RecoveryMode.MODE1_ONLINE_REWEIGHT):
            # Trusted map stays strictly invariant; system waits for delayed loop or auxiliary evidence
            self.state = RecoveryState.WAITING_FOR_EVIDENCE
            # The wait starts at the last frame seen when this decision is recorded, not at the
            # configured deadline. Normally the two coincide within a frame. They diverge when the
            # caller cannot run the decision on time: run 112059Z's first rolling snapshot blocked
            # the driver for 16 s, the segment kept registering frames, and the wait started 11 s
            # late. That inflation belongs to the caller -- record it there rather than silently
            # shortening the interval here.
            self.wait_started_ns = int(self.active_quarantine.t_end_ns)
            if os.environ.get("SLAM_RECOVERY_WAITDIAG"):
                print(f"[WAITDIAG] wait_started_set(mode3) wall={time.time():.6f} "
                  f"started={self.wait_started_ns} t_end_ns={self.active_quarantine.t_end_ns}",
                  flush=True)
        elif report.mode == RecoveryMode.MODE4_HARD_SLEEP_SPLIT:
            # Archive current trusted map into sleeping submaps and reset active trusted map cleanly
            if self.trusted_poses:
                self.sleeping_submaps.append(deepcopy(self.trusted_poses))
            self.provisional_queue.clear()
            self.active_quarantine = None
            self.state = RecoveryState.ABORTED

        return report

    # ----------------------------------------------------------------------------------------
    # Lifecycle after a refusal: a waiting segment that never gets evidence must not stall the run.
    # ----------------------------------------------------------------------------------------
    def maybe_close_waiting_segment(self, now_ns: int) -> Optional[QuarantineSegment]:
        """Close a Mode 3 wait once its declared limit has passed with no new evidence.

        A segment in WAITING_FOR_EVIDENCE keeps `active_quarantine` set so that arriving frames
        still have a home. That is correct while evidence might arrive, but it also means the
        manager never returns to HEALTHY: the next fault can never open a new segment, so a
        two-event run silently becomes a one-event run. When a limit was declared for the run,
        the wait ends here and the frames it held are recorded as *unresolved* -- not committed,
        not silently deleted. The trusted map is untouched: it stays at the last commit.
        """
        # DIAGNOSTIC: the first ten evaluations, so the caller's clock can be compared with the
        # timer's start without changing either.
        if self._wait_diag_calls < 10:
            self._wait_diag_calls += 1
            if os.environ.get("SLAM_RECOVERY_WAITDIAG"):
                print(f"[WAITDIAG] close_check#{self._wait_diag_calls} wall={time.time():.6f} "
                  f"now_ns={now_ns} started={self.wait_started_ns} "
                  f"delta_s={(None if self.wait_started_ns is None else (int(now_ns) - int(self.wait_started_ns)) / 1e9)}",
                  flush=True)
        if (self.state != RecoveryState.WAITING_FOR_EVIDENCE
                or self.active_quarantine is None
                or self.wait_limit_ns is None
                or self.wait_started_ns is None):
            return None
        if int(now_ns) - int(self.wait_started_ns) < int(self.wait_limit_ns):
            return None
        seg = self.active_quarantine
        self.unresolved_segments.append(seg)
        self.lifecycle_events.append({
            "event": "wait_limit_closed",
            "segment_id": seg.segment_id,
            "wait_started_ns": int(self.wait_started_ns),
            "closed_ns": int(now_ns),
            "wait_limit_ns": int(self.wait_limit_ns),
            "t_start_ns": int(seg.t_start_ns),
            "t_end_ns": int(seg.t_end_ns),
            "frames_unresolved": list(seg.raw_frame_refs),
            "trusted_version": int(self.trusted_version),
        })
        self.active_quarantine = None
        self.wait_started_ns = None
        self.state = RecoveryState.ABORTED
        return seg

    def rearm(self) -> bool:
        """Return to HEALTHY after a segment closed without evidence.

        The frames of the closed segment are lost, not committed; the trusted map is exactly
        what the last commit left. The next promoted frame re-establishes the map at the host's
        current estimate, which is a declared discontinuity of the map, and the lifecycle event
        keeps that visible rather than letting the run look continuous.
        """
        if self.active_quarantine is not None or self.state != RecoveryState.ABORTED:
            return False
        self.lifecycle_events.append({
            "event": "rearm",
            "from_state": RecoveryState.ABORTED.value,
            "trusted_version": int(self.trusted_version),
            "n_sleeping_submaps": len(self.sleeping_submaps),
        })
        self.wait_started_ns = None
        self.state = RecoveryState.HEALTHY
        return True
