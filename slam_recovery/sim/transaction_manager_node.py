"""Real-time ROS 1 Online Transaction Manager Node (`slam_recovery_ros_node`, Section 2.1 & 3.2 of REVIEW_AND_SIMULATION_PLAN.md).

Subscribes to:
  - `/Odometry` or `/lio_sam/mapping/odometry` (`nav_msgs/Odometry`)
  - `/velodyne_points` (`sensor_msgs/PointCloud2`)
Executes:
  - 2.0s delayed-commit ring buffering
  - Online 6-DoF point-to-plane FIM + NIS-CUSUM health monitoring
  - Zero-training Mechanism Signature Matrix diagnosis
  - Cross-scan holdout validation on every 5th scan (\mathcal{S}_{hold}) against trusted map voxels
Publishes:
  - `/slam_recovery/trusted_path` (`nav_msgs/Path`)
  - `/slam_recovery/gate_status` (`std_msgs/String`)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np

from ..core import (
    BackendDelta,
    CandidateMap,
    GateThresholds,
    HealthWindow,
    RecoveryMode,
    RecoveryState,
    ValidationReport,
)
from ..diagnosis import SignatureMatrixRouter
from ..health import DetectorConfig, JointHealthDetector
from ..quarantine import SpatialMutationLog, TrustedMapTransactionManager
from ..validation import (
    compute_6dof_point_to_plane_fim,
    compute_disjoint_holdout_point_to_plane_nis,
    evaluate_paired_sequential_benefit,
)


class OnlineRecoveryTransactionNode:
    """
    Stateful online recovery node that wraps an incremental LIO/VIO host,
    maintains a 3D trusted voxel map \mathcal{V}_{trusted}(t) alongside keyframe poses,
    and performs cross-scan holdout validation on held-out scans \mathcal{S}_{hold} (every 5th scan).
    """

    def __init__(
        self,
        confirmation_margin_sec: float = 2.0,
        voxel_size_m: float = 0.10,
        holdout_stride: int = 5,
        gate_thresholds: GateThresholds = GateThresholds(),
        min_paired_observations: int = 4,
        large_candidate_keyframe_threshold: int = 8,
        min_paired_observations_large_candidate: int = 8,
    ) -> None:
        self.voxel_size_m = float(voxel_size_m)
        self.holdout_stride = int(holdout_stride)
        # Smallest sample size at which a unanimous frame-wise improvement still clears the
        # 0.55 Wilson lower bound (n=3 -> 0.526, n=4 -> 0.596). Below this the paired test
        # cannot distinguish a genuine repair from luck, so the node reports MISSING evidence
        # and the gate refuses Mode 2 instead of assuming a pass (P1-1 fix).
        #
        # n=4 is a *floor*, not a sufficient sample for a large commit: a unanimous 4/4 window
        # clears the 0.55 bound by only 0.0465, so four frames of evidence would authorise an
        # irreversible trusted-map commit. A candidate that touches many keyframes has no excuse
        # for supplying so little evidence, so the requirement scales with candidate size:
        #   <8 keyframes  -> 4 paired frames (Wilson 0.5965, +0.0465 over threshold)
        #  >=8 keyframes  -> 8 paired frames (Wilson 0.7472, +0.1972 over threshold)
        self.min_paired_observations = int(min_paired_observations)
        self.large_candidate_keyframe_threshold = int(large_candidate_keyframe_threshold)
        self.min_paired_observations_large_candidate = int(min_paired_observations_large_candidate)
        # Diagnostics of the most recent paired-benefit measurement, recorded verbatim into the
        # run manifests so every Mode 2 decision can be traced back to its measured evidence.
        self.last_paired_evidence: Dict[str, object] = {}
        self.tx_mgr = TrustedMapTransactionManager(
            confirmation_margin_ns=int(confirmation_margin_sec * 1e9),
            gate_thresholds=gate_thresholds,
        )
        self.detector = JointHealthDetector(DetectorConfig(confirmation_margin_ns=int(confirmation_margin_sec * 1e9)))
        self.router = SignatureMatrixRouter()

        # Raw scan buffer indexed by keyframe_id for cross-scan holdout validation and 3D map commit
        self.scan_buffer_body: Dict[int, np.ndarray] = {}
        self.voxel_store: Dict[Tuple[int, int, int], int] = {}
        self.voxel_journal: SpatialMutationLog[Tuple[int, int, int], int] = SpatialMutationLog(self.voxel_store)
        self._kf_applied_poses: Dict[int, np.ndarray] = {}
        self._kf_map_points: Dict[int, np.ndarray] = {}
        self.committed_map_points: List[np.ndarray] = []

    @property
    def committed_voxel_set(self) -> set[Tuple[int, int, int]]:
        return set(self.voxel_store.keys())

    def _quantize_voxels(self, pts_world: np.ndarray) -> set[Tuple[int, int, int]]:
        q = np.floor(pts_world[:, :3] / self.voxel_size_m).astype(np.int32)
        return set(map(tuple, q.tolist()))

    def _sync_spatial_map_with_trusted_poses(self) -> None:
        """
        Keep `voxel_store`, `voxel_journal`, and `committed_map_points` strictly synchronized with
        `tx_mgr.trusted_poses` across promotions, late-onset revocations, and in-place pose updates (F3 fix).
        """
        cur_keys = set(self.tx_mgr.trusted_poses.keys())
        prev_keys = set(self._kf_applied_poses.keys())
        revoked_keys = prev_keys - cur_keys
        modified_keys = {
            k
            for k in (cur_keys & prev_keys)
            if not np.allclose(self._kf_applied_poses[k], self.tx_mgr.trusted_poses[k])
        }
        added_keys = cur_keys - prev_keys

        if revoked_keys or modified_keys:
            # Remove revoked or stale keyframe contributions and rebuild clean voxel ownership for surviving keyframes
            for rk in revoked_keys | modified_keys:
                self._kf_applied_poses.pop(rk, None)
                self._kf_map_points.pop(rk, None)
            to_delete = [v_key for v_key, owner in self.voxel_store.items() if owner in (revoked_keys | modified_keys)]
            for v_key in to_delete:
                self.voxel_journal.remove(v_key)
            # Re-assert surviving keyframes in case they shared any voxel key with a revoked keyframe
            for sk in sorted(self._kf_applied_poses.keys()):
                if sk in self.scan_buffer_body:
                    T_s = self._kf_applied_poses[sk]
                    pts_b = self.scan_buffer_body[sk][:, :3]
                    pts_w = (pts_b @ T_s[:3, :3].T) + T_s[:3, 3]
                    for v_key in self._quantize_voxels(pts_w):
                        self.voxel_journal.put(v_key, int(sk))

        for kf_id in sorted(added_keys | modified_keys):
            if kf_id in self.tx_mgr.trusted_poses and kf_id in self.scan_buffer_body:
                T_w_b = self.tx_mgr.trusted_poses[kf_id].copy()
                pts_b = self.scan_buffer_body[kf_id][:, :3]
                pts_w = (pts_b @ T_w_b[:3, :3].T) + T_w_b[:3, 3]
                for v_key in self._quantize_voxels(pts_w):
                    self.voxel_journal.put(v_key, int(kf_id))
                self._kf_applied_poses[kf_id] = T_w_b
                self._kf_map_points[kf_id] = pts_w[::4]

        # Always rebuild the derived validation reference, including the empty case: after the last
        # trusted keyframe is revoked, get_trusted_map_points() must return no points, otherwise the
        # next candidate is scored against a map that no longer exists (P1-2 fix).
        self.committed_map_points = [self._kf_map_points[k] for k in sorted(self._kf_map_points.keys())]

    def get_trusted_map_points(self, max_pts: int = 2000) -> np.ndarray:
        if not self.committed_map_points:
            return np.zeros((0, 3), dtype=np.float64)
        all_pts = np.vstack(self.committed_map_points)
        if len(all_pts) > max_pts:
            step = max(1, len(all_pts) // max_pts)
            return all_pts[::step][:max_pts]
        return all_pts

    def get_trusted_map_keys(self) -> set:
        """Keyframes that contributed points to the trusted reference cloud.

        A frame in this set cannot be scored against the trusted map: its own geometry is part of
        the reference, so agreement would be self-agreement. The caller must exclude these keys
        from both the paired test and the commit set, and it must be able to state the exclusion
        from actual provenance rather than from a comment (P2 fix).
        """
        return set(self._kf_map_points.keys())

    def step_frame(
        self,
        kf_id: int,
        timestamp_ns: int,
        pose_se3: np.ndarray,
        scan_body_xyz: np.ndarray,
        nis_value: float,
        loso_primary: float = 0.5,
        loso_aux: float = 0.5,
        sync_lag_sec: float = 0.0,
        loop_spike: float = 0.3,
    ) -> Optional[ValidationReport]:
        self.scan_buffer_body[kf_id] = np.asarray(scan_body_xyz, dtype=np.float64)[:, :3].copy()
        fim_6x6, cov_6x6, min_r, min_t, weak_dir = compute_6dof_point_to_plane_fim(
            scan_body_xyz, sigma_meas_m=0.075
        )

        win = HealthWindow(
            t_start_ns=timestamp_ns - int(0.1 * 1e9),
            t_end_ns=timestamp_ns,
            min_eig_rot=min_r,
            min_eig_trans=min_t,
            max_eig_rot_cov=float(np.max(np.linalg.eigvalsh(cov_6x6[:3, :3]))),
            max_eig_trans_cov=float(np.max(np.linalg.eigvalsh(cov_6x6[3:, 3:]))),
            weak_dir_6d=weak_dir,
            nis_mean=nis_value,
            nis_q90=nis_value * 1.35,
            nis_cusum=self.detector.cusum_g,
            loso_primary_conflict=loso_primary,
            loso_aux_conflict=loso_aux,
            Cross_corr_lag_sec=sync_lag_sec,
            loop_residual_spike=loop_spike,
        )
        decision = self.detector.step(win)

        if self.tx_mgr.state == RecoveryState.HEALTHY:
            if decision.state == RecoveryState.QUARANTINED:
                self.tx_mgr.trigger_quarantine(
                    estimated_onset_ns=decision.estimated_onset_ns,
                    current_ns=timestamp_ns,
                    weak_direction_6d=weak_dir,
                    info_before_6x6=fim_6x6,
                    propagated_cov_norm=float(np.linalg.norm(cov_6x6, ord=2)),
                )
                self._sync_spatial_map_with_trusted_poses()
            else:
                delta = BackendDelta(
                    timestamp_ns=timestamp_ns,
                    frame_id="map",
                    pose_se3=pose_se3.copy(),
                    velocity=np.zeros(3),
                    bias_acc=np.zeros(3),
                    bias_gyr=np.zeros(3),
                    cov_6x6=cov_6x6,
                    info_6x6=fim_6x6,
                    nis_value=nis_value,
                    nis_dof=6,
                    factor_ids=[kf_id],
                    keyframe_id=kf_id,
                )
                self.tx_mgr.step_healthy(delta)
                self._sync_spatial_map_with_trusted_poses()
        return None

    def _frame_has_reference_support(
        self,
        kf_id: int,
        ref_pts: np.ndarray,
        repaired_poses: Dict[int, np.ndarray],
        radius_m: float = 1.0,
        min_supported_fraction: float = 0.60,
    ) -> bool:
        """True when most of this frame's points land near the independent reference cloud.

        A frame far outside the reference's coverage cannot be validated: scoring it would compare
        the scan against a plane extrapolated from unrelated geometry.
        """
        if len(ref_pts) == 0:
            return False
        # A frame with no buffered scan or no candidate pose is *unmeasured*, not unsupported:
        # there is nothing to project, so it cannot contribute evidence. Returning False here and
        # letting the caller record the key as deferred keeps that distinction visible, and stops
        # the helper from raising KeyError on a hole in the scan buffer (P2 fix).
        if kf_id not in self.scan_buffer_body or kf_id not in repaired_poses:
            return False
        T = np.asarray(repaired_poses[kf_id], dtype=np.float64)
        if T.shape != (4, 4) or not np.all(np.isfinite(T)):
            return False
        pts_b = np.asarray(self.scan_buffer_body[kf_id], dtype=np.float64)[:, :3]
        if len(pts_b) == 0:
            return False
        pts_w = (pts_b @ T[:3, :3].T) + T[:3, 3]
        q = pts_w[:: max(1, len(pts_w) // 200)][:200]
        d = np.linalg.norm(q[:, None, :] - ref_pts[None, :, :], axis=-1)
        return bool(np.mean(d.min(axis=1) <= radius_m) >= min_supported_fraction)

    def _measure_paired_evidence(
        self,
        repaired_poses: Dict[int, np.ndarray],
        incumbent_poses: Optional[Dict[int, np.ndarray]] = None,
        reentry_anchor_pose: Optional[np.ndarray] = None,
        reference_world: Optional[np.ndarray] = None,
        reference_keys: Optional[set] = None,
        empty_reason: str = "no_repaired_poses",
    ) -> Tuple[Optional[bool], Optional[float], Optional[float]]:
        """
        Measure the paired-benefit / re-entry evidence of a candidate against its incumbent.

        Returns ``(paired_benefit_approved, wilson_lower_bound, reentry_position_jump_m)``.
        Every quantity that cannot be measured from data the node actually holds is returned
        as ``None``; the unified gate treats ``None`` as *missing evidence* and refuses Mode 2
        atomic commit rather than assuming a pass (P1-1).
        """
        keys = sorted(repaired_poses.keys())
        self.last_paired_evidence = {"num_paired_frames": 0, "reason": empty_reason}
        if not keys:
            return None, None, None

        # (a) Re-entry continuity: translation jump between the frozen pre-onset anchor pose and
        #     the candidate pose at the first frame re-entering the trusted timeline.
        anchor = reentry_anchor_pose
        seg = self.tx_mgr.active_quarantine
        if anchor is None and seg is not None and seg.checkpoint.keyframe_poses:
            anchor = seg.checkpoint.keyframe_poses[max(seg.checkpoint.keyframe_poses.keys())]
        reentry_jump: Optional[float] = None
        if anchor is not None:
            anchor_arr = np.asarray(anchor, dtype=np.float64)
            first_arr = np.asarray(repaired_poses[keys[0]], dtype=np.float64)
            if anchor_arr.shape == (4, 4) and first_arr.shape == (4, 4):
                reentry_jump = float(np.linalg.norm(first_arr[:3, 3] - anchor_arr[:3, 3]))

        # (b) Paired frame-wise benefit on an independent reference: the trusted map built before
        #     the quarantine opened. The candidate's own scans are deliberately excluded from the
        #     reference so that both arms are scored against the same independent cloud.
        if incumbent_poses is None:
            self.last_paired_evidence = {"num_paired_frames": 0, "reason": "no_incumbent_trajectory",
                                         "reentry_pos_jump_m": reentry_jump}
            return None, None, reentry_jump
        ref_pts = (
            np.asarray(reference_world, dtype=np.float64)[:, :3]
            if reference_world is not None and len(reference_world) > 0
            else self.get_trusted_map_points(max_pts=1500)
        )
        # P1-A: score only frames that did not contribute to the reference. With the reference now
        # built from the trusted map alone this excludes nothing, but the exclusion is enforced
        # structurally so that any future caller supplying anchor frames cannot silently re-introduce
        # the self-reference that fix 1 removed.
        pairable_keys = [
            k for k in keys
            if k in self.scan_buffer_body and k in incumbent_poses
            and k not in (reference_keys or set())
        ]
        # P1-A (second half): a frame can only be scored where an independent reference actually
        # exists. Once the candidate's own scans stop propping up the reference, frames that sit
        # beyond the trusted map's coverage would be compared against an extrapolated surface and
        # produce enormous but meaningless residuals -- that is "no evidence", not "bad candidate",
        # and the two must not be conflated. Keep only frames whose points are predominantly
        # supported by the reference cloud.
        paired_keys = [k for k in pairable_keys if self._frame_has_reference_support(k, ref_pts, repaired_poses)]
        unsupported = len(pairable_keys) - len(paired_keys)
        # Evidence requirement scales with how much of the map the candidate would commit. This is
        # a floor under both settings, so a caller that raises min_paired_observations above the
        # large-candidate requirement cannot end up demanding *less* evidence for a bigger commit.
        required_paired = max(
            self.min_paired_observations,
            self.min_paired_observations_large_candidate
            if len(keys) >= self.large_candidate_keyframe_threshold
            else 0,
        )
        if len(ref_pts) == 0 or len(paired_keys) < required_paired:
            self.last_paired_evidence = {
                "num_paired_frames": len(paired_keys),
                "reason": "empty_trusted_reference" if len(ref_pts) == 0 else "insufficient_paired_frames",
                # Same key in the failure and success branches, so a MISSING verdict is as
                # traceable as an accepted one.
                "required_paired_frames": required_paired,
                "candidate_keyframes": len(keys),
                "pairable_frames": len(pairable_keys),
                "frames_without_independent_reference": unsupported,
                "reference_frames_from_candidate": len(reference_keys or ()),
                "reentry_pos_jump_m": reentry_jump,
            }
            return None, None, reentry_jump

        incumbent_res: List[float] = []
        candidate_res: List[float] = []
        for k in paired_keys:
            pts_b = np.asarray(self.scan_buffer_body[k], dtype=np.float64)[:, :3]
            for pose, sink in ((incumbent_poses[k], incumbent_res), (repaired_poses[k], candidate_res)):
                T = np.asarray(pose, dtype=np.float64)
                pts_w = (pts_b @ T[:3, :3].T) + T[:3, 3]
                sink.append(
                    float(
                        compute_disjoint_holdout_point_to_plane_nis(
                            ref_pts, pts_w, delta_pose_se3=np.eye(4), sigma_meas_m=0.12
                        )
                    )
                )

        # The re-entry jump is judged separately by the gate against GateThresholds.max_reentry_jump_m,
        # so it is not fed into the benefit test; both now use the same 0.50 m bound rather than
        # carrying two different internal thresholds.
        report = evaluate_paired_sequential_benefit(
            np.asarray(incumbent_res, dtype=np.float64),
            np.asarray(candidate_res, dtype=np.float64),
            reentry_position_jump_m=0.0,
            min_observations=required_paired,
        )
        self.last_paired_evidence = {
            "num_paired_frames": int(report.num_observations),
            "required_paired_frames": required_paired,
            "candidate_keyframes": len(keys),
            "pairable_frames": len(pairable_keys),
            "frames_without_independent_reference": unsupported,
            "reference_frames_from_candidate": len(reference_keys or ()),
            "num_improved_frames": int(report.num_improved_frames),
            "improved_fraction": float(report.empirical_improved_fraction),
            "wilson_lower_bound": float(report.wilson_lower_bound),
            "approved": bool(report.approved),
            "reason": report.reason,
            "incumbent_mean_residual": float(np.mean(incumbent_res)),
            "candidate_mean_residual": float(np.mean(candidate_res)),
            "reentry_pos_jump_m": reentry_jump,
        }
        return bool(report.approved), float(report.wilson_lower_bound), reentry_jump

    def evaluate_and_commit_candidate(
        self,
        candidate_id: str,
        repaired_poses: Dict[int, np.ndarray],
        aux_or_loop_info_6x6: Optional[np.ndarray] = None,
        incumbent_poses: Optional[Dict[int, np.ndarray]] = None,
        reentry_anchor_pose: Optional[np.ndarray] = None,
    ) -> ValidationReport:
        """
        Perform true cross-scan holdout validation (Section 3.2 S1):
          - Every 5th scan in `repaired_poses` is held out as \mathcal{S}_{hold}.
          - Transform \mathcal{S}_{hold} into world frame using candidate pose X_{cand, k}
            and compute point-to-plane NIS against the trusted map \mathcal{M}_{trusted}
            and non-holdout anchor scans.
        """
        # P1-A: the validation reference must be independent of the candidate. It is built ONLY from
        # the trusted map as it stood before the quarantine opened. The candidate's non-holdout
        # scans used to be concatenated in here, which made the "independent holdout" partially
        # self-referential: a candidate was scored against geometry produced by the very poses it
        # was supposed to justify, so any self-consistent drift looked like agreement.
        trusted_map_pts = self.get_trusted_map_points(max_pts=1500)
        kf_sorted = sorted(repaired_poses.keys())

        train_world = trusted_map_pts if len(trusted_map_pts) > 0 else np.zeros((0, 3))

        # P2: take the exclusion set from the map's actual provenance. Until now `reference_keys`
        # was hard-wired to the empty set and the comment merely asserted independence; any future
        # reference built with anchor frames would have let a frame score itself.
        reference_keys = self.get_trusted_map_keys()

        # P1: the scored set and the committed set must be the same set.
        #
        # A candidate pose that moves its scan out of the trusted map's coverage used to drop that
        # frame from *scoring* while it stayed in *commit* -- the worse the pose, the less evidence
        # it produced, and a badly-wrong tail could ride in behind eight good frames. The commit is
        # therefore restricted to the maximal verified *prefix* of the candidate in keyframe order:
        #   - a frame is committable only if the independent reference supports it,
        #   - only if it did not contribute to that reference, and
        #   - only if an incumbent pose exists to pair it against.
        # Frames after the first non-committable one stay quarantined (`deferred`). They are not
        # rejected; they are not yet verifiable. Truncating at the first gap keeps the committed
        # submap contiguous with the trusted timeline, so the boundary and graph dependencies are
        # re-established at the cut rather than in the middle of the commit.
        incumbent_keys = set(incumbent_poses.keys()) if incumbent_poses is not None else None
        missing_scan_keys = [k for k in kf_sorted if k not in self.scan_buffer_body]
        committable = {
            k
            for k in kf_sorted
            if k not in reference_keys
            and (incumbent_keys is None or k in incumbent_keys)
            and self._frame_has_reference_support(k, train_world, repaired_poses)
        }
        commit_keys: List[int] = []
        stop_key: Optional[int] = None
        stop_reason: Optional[str] = None
        for k in kf_sorted:
            if k not in committable:
                stop_key = k
                # Say *why* the prefix stopped. "Zero frames committed" is not enough: a missing
                # scan, a frame that contributed to the reference, and a frame the reference does
                # not cover all truncate the same prefix but call for different fixes.
                stop_reason = (
                    "missing_scan"
                    if k not in self.scan_buffer_body
                    else "reference_overlap"
                    if k in reference_keys
                    else "no_incumbent_pose"
                    if (incumbent_keys is not None and k not in incumbent_keys)
                    else "no_reference_support"
                )
                break
            commit_keys.append(k)
        deferred_keys = [k for k in kf_sorted if k not in set(commit_keys)]
        candidate_poses = {k: repaired_poses[k] for k in commit_keys}

        holdout_kfs = [k for idx, k in enumerate(commit_keys) if idx % self.holdout_stride == 0]
        # Every committed frame already passed the support check, so no second filter is applied;
        # the counters are kept so a MISSING verdict says how many frames were even considered.
        scorable_holdout = holdout_kfs
        self._last_holdout_support = {
            "holdout_frames_total": len(holdout_kfs),
            "holdout_frames_scorable": len(scorable_holdout),
            "candidate_frames_total": len(kf_sorted),
            "candidate_frames_committable": len(committable),
            "candidate_frames_committed": len(commit_keys),
            "candidate_frames_deferred": len(deferred_keys),
            "frames_missing_scan": missing_scan_keys,
            "frames_in_reference": sorted(set(kf_sorted) & reference_keys),
            # Diagnostics for the truncation itself. A prefix can stop at its very first frame
            # while later frames are perfectly supportable; without these fields that case is
            # indistinguishable from "the candidate contained nothing".
            "prefix_stop_key": stop_key,
            "prefix_stop_reason": stop_reason,
            "committable_frames_after_prefix": (
                len([k for k in kf_sorted if k in committable and k not in set(commit_keys)])
                if stop_key is not None
                else 0
            ),
        }

        holdout_nis_list = []
        fims_after = []
        for k in scorable_holdout:
            T_k = repaired_poses[k]
            pts_b = self.scan_buffer_body[k]
            pts_w = (pts_b @ T_k[:3, :3].T) + T_k[:3, 3]
            nis_k = compute_disjoint_holdout_point_to_plane_nis(
                train_world, pts_w, delta_pose_se3=np.eye(4), sigma_meas_m=0.12
            )
            holdout_nis_list.append(nis_k)
            fim_k, _, _, _, _ = compute_6dof_point_to_plane_fim(
                pts_w, sigma_meas_m=0.075, aux_odom_info_6x6=aux_or_loop_info_6x6
            )
            fims_after.append(fim_k)

        mean_holdout_nis = float(np.mean(holdout_nis_list)) if holdout_nis_list else float("inf")
        if fims_after:
            info_after = np.mean(fims_after, axis=0)
            cov_after = np.linalg.inv(info_after + np.eye(6) * 1e-3)
        else:
            info_after = np.eye(6) * 1e-3
            cov_after = np.eye(6) * 1e3

        # Paired-benefit evidence must be measured, never assumed; unmeasured components stay None
        # and force the gate to wait (Mode 3/4) instead of committing.
        # The two ways the scored set can end up empty must not share one log string: an empty
        # *input* candidate and a candidate whose first frame has no reference support (prefix
        # length zero) send the operator to completely different places.
        paired_ok, wilson_lb, reentry_jump = self._measure_paired_evidence(
            candidate_poses,
            incumbent_poses=incumbent_poses,
            reentry_anchor_pose=reentry_anchor_pose,
            reference_world=train_world,
            reference_keys=reference_keys,
            empty_reason=(
                "no_committable_prefix" if (not commit_keys and kf_sorted) else "no_repaired_poses"
            ),
        )

        cand = CandidateMap(
            candidate_id=candidate_id,
            parent_map_version=self.tx_mgr.trusted_version,
            # Only verified frames enter the candidate. The transaction manager commits exactly
            # this dict, so there is no path by which an unscored frame reaches the trusted map.
            repaired_poses=candidate_poses,
            verified_pose_keys=frozenset(commit_keys),
            deferred_pose_keys=tuple(deferred_keys),
            info_after_6x6=info_after,
            cov_after_6x6=cov_after,
            holdout_nis=mean_holdout_nis,
            repairer_name=candidate_id,
            paired_benefit_approved=paired_ok,
            wilson_lower_bound=wilson_lb,
            reentry_pos_jump_m=reentry_jump,
        )
        report = self.tx_mgr.validate_and_resolve(cand)
        if report.accepted:
            self._sync_spatial_map_with_trusted_poses()
            self.voxel_journal.commit_generation()
        return report
