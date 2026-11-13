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
import os
import time

import numpy as np

from ..core import (
    BackendDelta,
    CandidateMap,
    GateThresholds,
    HealthWindow,
    RecoveryMode,
    RecoveryState,
    TangentFrame,
    ValidationReport,
    transport_information,
)
from ..diagnosis import SignatureMatrixRouter
from ..health import DetectorConfig, JointHealthDetector
from ..quarantine import SpatialMutationLog, TrustedMapTransactionManager
from ..validation import (
    compute_6dof_point_to_plane_fim,
    compute_disjoint_holdout_point_to_plane_nis,
    evaluate_paired_sequential_benefit,
)


def boundary_jump_within_envelope(jump_m: float, elapsed_s: float, jump_bound_m: float,
                                  speed_m_s: float = 2.0) -> bool:
    """Is a boundary displacement explainable as motion over `elapsed_s`?

    `max_reentry_jump_m` bounds a *discontinuity*. With a positive confirmation margin the pose
    being compared is seconds old, so the same bound applied without the elapsed time refuses
    every candidate on a moving platform: 1.25 m over 2.33 s is 0.54 m/s of ordinary walking.
    The envelope keeps the bound for the instantaneous case and scales it with elapsed time.
    """
    return float(jump_m) <= float(jump_bound_m) + float(speed_m_s) * max(0.0, float(elapsed_s))


class _RadiusIndex:
    """Exact "is there a reference point within r" queries without a distance matrix.

    The support test asks one question per query point: is any reference point within `radius`.
    Answering it with the full distance matrix is O(queries * points) per call, and the decision
    calls it for every candidate frame twice -- 4 s of a 4.4 s decision on a 100k-point map.
    Bucketing the reference into cells of exactly `radius` answers the same question exactly:
    a point within `radius` of a query must lie in one of the 27 cells around it, so no true
    neighbour is ever missed and no approximate structure is introduced.
    """

    def __init__(self, points: np.ndarray, cell: float) -> None:
        self.cell = float(cell)
        pts = np.asarray(points, dtype=np.float64)[:, :3]
        self.points = pts
        q = np.floor(pts / self.cell).astype(np.int64)
        self.origin = q.min(axis=0) - 1
        q = q - self.origin
        self.dims = q.max(axis=0) + 2
        lin = (q[:, 0] * self.dims[1] + q[:, 1]) * self.dims[2] + q[:, 2]
        order = np.argsort(lin, kind="stable")
        self.sorted_lin = lin[order]
        self.sorted_idx = order

    def within_radius_mask(self, queries: np.ndarray, radius: float) -> np.ndarray:
        queries = np.asarray(queries, dtype=np.float64)[:, :3]
        cell = np.floor(queries / self.cell).astype(np.int64) - self.origin
        inside = np.zeros(len(queries), dtype=bool)
        r2 = float(radius) * float(radius)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    c = cell + np.array([dx, dy, dz], dtype=np.int64)
                    valid = np.all((c >= 0) & (c < self.dims), axis=1)
                    if not valid.any():
                        continue
                    valid &= ~inside
                    lin = (c[:, 0] * self.dims[1] + c[:, 1]) * self.dims[2] + c[:, 2]
                    lo = np.searchsorted(self.sorted_lin, lin, side="left")
                    hi = np.searchsorted(self.sorted_lin, lin, side="right")
                    hit = valid & (hi > lo)
                    for i in np.flatnonzero(hit):
                        if inside[i]:
                            continue
                        cand = self.sorted_idx[lo[i]:hi[i]]
                        d2 = np.sum((self.points[cand] - queries[i]) ** 2, axis=1)
                        if d2.size and d2.min() <= r2:
                            inside[i] = True
        return inside


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
        sigma_meas_m: float = 0.12,
        wait_limit_sec: Optional[float] = None,
    ) -> None:
        # Point-to-plane noise scale used by every holdout/paired NIS in this node.
        #
        # NIS scales as 1/sigma^2, so this constant decides verdicts and must be calibrated, not
        # guessed: on room_dark_02 the clean run scores 0.77-0.99 at sigma=0.25 but 3.35-4.30 at
        # 0.12, i.e. at the old default the gate rejects *healthy* data. The default is kept for
        # backward compatibility with the simulator; any real host must pass the value obtained by
        # setting the clean run's NIS to 1 (sigma* = RMS of its point-to-plane residuals).
        self.sigma_meas_m = float(sigma_meas_m)
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
            wait_limit_ns=(None if wait_limit_sec is None
                           else int(float(wait_limit_sec) * 1e9)),
        )
        self.detector = JointHealthDetector(DetectorConfig(confirmation_margin_ns=int(confirmation_margin_sec * 1e9)))
        self.router = SignatureMatrixRouter()

        # Raw scan buffer indexed by keyframe_id for cross-scan holdout validation and 3D map commit
        self.scan_buffer_body: Dict[int, np.ndarray] = {}
        # Per-keyframe timestamps, used to scale a segment-boundary bound by the elapsed time.
        self._kf_timestamps: Dict[int, int] = {}
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

    def support_reference(self, voxel_m: float = 0.30) -> np.ndarray:
        """Reference cloud for the coverage test, sampled by space rather than by a point cap.

        `_frame_has_reference_support` asks whether the trusted map *covers* a scan. Handing it a
        globally capped cloud answers a different question: the cap sets the point spacing, so a
        fixed `max_pts` turns the same geometry from "covered" to "not covered" as the map grows.
        In the four-arm replay this alone flipped a frame's support fraction from 0.82 at 4 000
        points to 0.29 at 1 500 points, with identical poses and identical scans. Sampling one
        point per occupied voxel fixes the spacing at `voxel_m` and lets the count follow the
        mapped area instead of a constant.
        """
        pts = self.get_trusted_map_points(max_pts=1 << 30)
        if len(pts) == 0:
            return pts
        q = np.floor(np.asarray(pts[:, :3], dtype=np.float64) / float(voxel_m)).astype(np.int64)
        # Row-wise np.unique(axis=0) on the whole map is O(N log N) with a wide comparison and
        # was a multi-second cost per refresh on large maps; the driver's per-frame callback
        # averaged 244 ms and the host hibernated before E1. Packing the three voxel indices
        # into one int64 preserves the same first-occurrence selection (np.unique returns the
        # first occurrence of each key) and sorts scalars instead of rows.
        key = ((q[:, 0] & 0x1FFFFF) << 42) | ((q[:, 1] & 0x1FFFFF) << 21) | (q[:, 2] & 0x1FFFFF)
        _, first = np.unique(key, return_index=True)
        return pts[np.sort(first)]

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
        self._kf_timestamps[kf_id] = int(timestamp_ns)
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

        # A wait that never ends is a run that can never see a second event. When the run declared
        # a wait limit, close the segment here and re-arm; the frames it was holding are recorded
        # as unresolved by the manager, and the current frame is ingested on the normal path.
        if self.tx_mgr.maybe_close_waiting_segment(timestamp_ns) is not None:
            self.detector.reset()
            self.tx_mgr.rearm()
        elif (self.tx_mgr.state == RecoveryState.ABORTED
              and self.tx_mgr.active_quarantine is None):
            # Mode 4 archived the map into sleeping submaps and left the manager terminal; the
            # next frame starts a new segment rather than being dropped with nowhere to go.
            self.detector.reset()
            self.tx_mgr.rearm()

        if self.tx_mgr.state == RecoveryState.HEALTHY:
            if decision.state == RecoveryState.QUARANTINED:
                # `weak_dir` and `fim_6x6` are produced from this scan's own points, i.e. in the
                # body frame of `kf_id`, and that frame is kept as the gate's evaluation basis.
                # The repaired candidate is assembled from world-frame points, so it carries the
                # anchor pose and the gate brings the candidate's information and covariance back
                # into this body frame. Transporting the *direction* into world instead would be
                # the same physics in principle, but the world vector is not unit length (Ad is not
                # orthogonal), and re-normalising it there rescales the information.
                self.tx_mgr.trigger_quarantine(
                    estimated_onset_ns=decision.estimated_onset_ns,
                    current_ns=timestamp_ns,
                    weak_direction_6d=weak_dir,
                    info_before_6x6=fim_6x6,
                    propagated_cov_norm=float(np.linalg.norm(cov_6x6, ord=2)),
                    weak_direction_frame=TangentFrame("body", "rot_trans", f"scan:{kf_id}"),
                    info_before_frame=TangentFrame("body", "rot_trans", f"scan:{kf_id}"),
                    anchor_pose_world=pose_se3.copy(),
                )
                # A5 normal path: this frame set off the alarm, so it was never handed to
                # step_healthy and therefore is not among the deltas the trigger rolled back.
                # Without this line it belongs to no population at all -- not trusted, not
                # pending -- and can never be resolved.
                self.tx_mgr.register_quarantined_frame(kf_id, timestamp_ns)
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
        elif self.tx_mgr.active_quarantine is not None:
            # A5: a frame that arrives while the quarantine is open belongs to it whether or not
            # any candidate ever names it. step_frame is the single ingest path, so the
            # registration goes here rather than at each caller.
            self.tx_mgr.register_quarantined_frame(kf_id, timestamp_ns)
        return None

    def _frame_has_reference_support(
        self,
        kf_id: int,
        ref_pts: np.ndarray,
        repaired_poses: Dict[int, np.ndarray],
        radius_m: float = 1.0,
        min_supported_fraction: float = 0.60,
        index: Optional["_RadiusIndex"] = None,
        detail: Optional[dict] = None,
    ) -> bool:
        """True when most of this frame's points land near the independent reference cloud.

        A frame far outside the reference's coverage cannot be validated: scoring it would compare
        the scan against a plane extrapolated from unrelated geometry.

        ``detail`` is filled with the inputs and the per-sample answer of this same evaluation. It
        is an observation channel: it never changes the boolean or does a second computation.
        """
        def fail(reason: str) -> bool:
            if detail is not None:
                detail.update({"reason": reason, "radius_m": float(radius_m),
                               "threshold_fraction": float(min_supported_fraction),
                               "reference_points": int(len(ref_pts))})
            return False

        if len(ref_pts) == 0:
            return fail("empty_reference")
        # A frame with no buffered scan or no candidate pose is *unmeasured*, not unsupported:
        # there is nothing to project, so it cannot contribute evidence. Returning False here and
        # letting the caller record the key as deferred keeps that distinction visible, and stops
        # the helper from raising KeyError on a hole in the scan buffer (P2 fix).
        if kf_id not in self.scan_buffer_body:
            return fail("missing_scan")
        if kf_id not in repaired_poses:
            return fail("missing_pose")
        T = np.asarray(repaired_poses[kf_id], dtype=np.float64)
        if T.shape != (4, 4) or not np.all(np.isfinite(T)):
            return fail("invalid_pose")
        pts_b = np.asarray(self.scan_buffer_body[kf_id], dtype=np.float64)[:, :3]
        if len(pts_b) == 0:
            return fail("empty_scan")
        pts_w = (pts_b @ T[:3, :3].T) + T[:3, 3]
        stride = max(1, len(pts_w) // 200)
        rows = np.arange(0, len(pts_w), stride)[:200]
        q = pts_w[rows]
        index = index if index is not None else _RadiusIndex(ref_pts, radius_m)
        inside = index.within_radius_mask(q, radius_m)
        fraction = float(np.mean(inside))
        passed = bool(fraction >= min_supported_fraction)
        if detail is not None:
            detail.update({
                "reason": ("ok" if passed else "fraction_below_threshold"),
                "radius_m": float(radius_m),
                "threshold_fraction": float(min_supported_fraction),
                "reference_points": int(len(ref_pts)),
                "scan_points": int(len(pts_b)), "sampled_query_count": int(len(q)),
                "query_stride": int(stride),
                "within_radius_count": int(np.count_nonzero(inside)),
                "supported_fraction": fraction, "pass": passed,
                "points": [
                    {"row": int(rows[i]), "body": [float(v) for v in pts_b[rows[i]]],
                     "world": [float(v) for v in q[i]], "within_1m": bool(inside[i])}
                    for i in range(len(q))
                ],
            })
        return passed

    @staticmethod
    def _contiguous_runs(keys) -> List[List[int]]:
        ks = sorted(int(k) for k in keys)
        if not ks:
            return []
        runs = [[ks[0], ks[0]]]
        for k in ks[1:]:
            if k == runs[-1][1] + 1:
                runs[-1][1] = k
            else:
                runs.append([k, k])
        return runs

    def _noncommittable_reason(self, kf_id: int, reference_keys: set,
                               incumbent_keys: Optional[set]) -> str:
        """Why a candidate frame cannot be committed. Same cases the support test separates."""
        if kf_id not in self.scan_buffer_body:
            return "missing_scan"
        if kf_id in reference_keys:
            return "reference_overlap"
        if incumbent_keys is not None and kf_id not in incumbent_keys:
            return "no_incumbent_pose"
        return "no_reference_support"

    def _measure_paired_evidence(
        self,
        repaired_poses: Dict[int, np.ndarray],
        incumbent_poses: Optional[Dict[int, np.ndarray]] = None,
        reentry_anchor_pose: Optional[np.ndarray] = None,
        reference_world: Optional[np.ndarray] = None,
        reference_keys: Optional[set] = None,
        empty_reason: str = "no_repaired_poses",
        support_reference: Optional[np.ndarray] = None,
        reentry_candidate_pose: Optional[np.ndarray] = None,
        support_index: Optional["_RadiusIndex"] = None,
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
        #     the candidate pose at the *boundary* frame -- the first candidate frame in time.
        #
        #     That frame is not necessarily committed: the commit set is every supportable frame,
        #     and the first frames after an occlusion may be unsupported. Measuring the jump to
        #     the first *committed* frame compares the anchor against a pose tens of seconds and
        #     metres later, which is elapsed motion, not a discontinuity. The four-arm replay hit
        #     exactly this: frame 0 sat 0.019 m from the anchor, the first committed frame sat
        #     3.073 m away after 19.44 s, and the gate reported a 3.09 m "jump". Continuity is a
        #     property of the candidate trajectory at the boundary, so the boundary frame is used.
        anchor = reentry_anchor_pose
        seg = self.tx_mgr.active_quarantine
        if anchor is None and seg is not None and seg.checkpoint.keyframe_poses:
            anchor = seg.checkpoint.keyframe_poses[max(seg.checkpoint.keyframe_poses.keys())]
        reentry_jump: Optional[float] = None
        if anchor is not None:
            anchor_arr = np.asarray(anchor, dtype=np.float64)
            boundary_pose = (
                reentry_candidate_pose
                if reentry_candidate_pose is not None
                else repaired_poses[keys[0]]
            )
            first_arr = np.asarray(boundary_pose, dtype=np.float64)
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
        # Coverage of the paired frame is decided on the spatially sampled reference, for the same
        # reason as the commit prefix: the 1500-point scoring cloud is a budget, not a coverage
        # definition. Using it here made every paired frame look unsupported in the four-arm replay
        # even though the same frames had already passed the (correct) prefix check.
        support = ref_pts if support_reference is None else support_reference
        paired_keys = [k for k in pairable_keys
                       if self._frame_has_reference_support(k, support, repaired_poses,
                                                            index=support_index)]
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
                            ref_pts, pts_w, delta_pose_se3=np.eye(4), sigma_meas_m=self.sigma_meas_m
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
        reentry_anchor_ts_ns: Optional[int] = None,
    ) -> ValidationReport:
        """
        Perform true cross-scan holdout validation (Section 3.2 S1):
          - Every 5th scan in `repaired_poses` is held out as \mathcal{S}_{hold}.
          - Transform \mathcal{S}_{hold} into world frame using candidate pose X_{cand, k}
            and compute point-to-plane NIS against the trusted map \mathcal{M}_{trusted}
            and non-holdout anchor scans.
        """
        # Decision latency is part of the experiment: this call runs inside the confirmation
        # window, and the quarantine keeps registering frames while it runs. Env-gated so a run's
        # log stays quiet; the numbers are what decide whether the window is even meetable.
        _t = {"start": time.perf_counter()}

        def _mark(name: str) -> None:
            _t[name] = time.perf_counter()
            if os.environ.get("SLAM_RECOVERY_DECISION_TIMING"):
                print(f"[DECIDE_TIMING] {candidate_id} {name} "
                      f"{1000.0 * (_t[name] - _t['start']):.1f} ms elapsed", flush=True)

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
        # therefore restricted to the frames the reference supports:
        #   - a frame is committable only if the independent reference supports it,
        #   - only if it did not contribute to that reference, and
        #   - only if an incumbent pose exists to pair it against.
        # Unsupported frames stay quarantined (`deferred`). They are not rejected; they are not yet
        # verifiable.
        #
        # An earlier version committed only the *contiguous prefix* of committable frames. The
        # four-arm replay showed why that is wrong: one unsupported frame at index 14 stopped the
        # commit at 14 while 303 later frames were supported, and the gate was then judged on the
        # hardest 14 frames (Wilson 0.0) instead of on the 317-frame set it would commit (Wilson
        # 0.925). The review allows "an independently verified committable subset"; it does not
        # require that subset to be contiguous, and keyframe factors are added per committed id, so
        # a gap does not break the commit.
        incumbent_keys = set(incumbent_poses.keys()) if incumbent_poses is not None else None
        missing_scan_keys = [k for k in kf_sorted if k not in self.scan_buffer_body]
        # The coverage test gets a spatially sampled reference, not the 1500-point cloud used for
        # scoring: that cap is a point budget, and letting it decide coverage makes the answer a
        # function of map size rather than of geometry (see support_reference()).
        support_ref = self.support_reference()
        # One index for the whole decision: the same reference answers the commit-prefix test and
        # the paired-evidence coverage test, and rebuilding it (or the distance matrix) per frame
        # was most of the decision's 4.4 s.
        support_index = (_RadiusIndex(support_ref, 1.0) if len(support_ref) else None)
        committable = {
            k
            for k in kf_sorted
            if k not in reference_keys
            and (incumbent_keys is None or k in incumbent_keys)
            and self._frame_has_reference_support(k, support_ref, repaired_poses,
                                                 index=support_index)
        }
        commit_keys: List[int] = [k for k in kf_sorted if k in committable]
        deferred_keys = [k for k in kf_sorted if k not in set(commit_keys)]
        candidate_poses = {k: repaired_poses[k] for k in commit_keys}

        # A non-contiguous commit has one boundary per gap. Measure each of them: a run that
        # starts 1.5 m from the last committed keyframe is a map discontinuity even when every
        # individual frame fits the reference (a tangential shift on a plane leaves point-to-plane
        # residual at zero). The bound is the gate's re-entry bound plus the distance the host
        # could have travelled over the elapsed time at a conservative 2 m/s; without timestamps
        # the absolute bound applies.
        runs = self._contiguous_runs(commit_keys)
        jump_bound = float(self.tx_mgr.gate_thresholds.max_reentry_jump_m)
        boundary_jumps: List[float] = []
        boundary_ok = True
        for prev_run, run in zip(runs, runs[1:]):
            prev_k, next_k = prev_run[-1], run[0]
            jump = float(np.linalg.norm(
                np.asarray(repaired_poses[next_k], dtype=np.float64)[:3, 3]
                - np.asarray(repaired_poses[prev_k], dtype=np.float64)[:3, 3]
            ))
            dt = 0.0
            if prev_k in self._kf_timestamps and next_k in self._kf_timestamps:
                dt = max(0.0, (self._kf_timestamps[next_k] - self._kf_timestamps[prev_k]) * 1e-9)
            boundary_jumps.append(jump)
            if not boundary_jump_within_envelope(jump, dt, jump_bound):
                boundary_ok = False
        # The first committed run is measured against the trusted anchor as well; the re-entry
        # check above uses the candidate's boundary frame, which may not itself be committed.
        first_run_jump: Optional[float] = None
        if runs and reentry_anchor_pose is not None:
            anchor_arr = np.asarray(reentry_anchor_pose, dtype=np.float64)
            head = np.asarray(repaired_poses[runs[0][0]], dtype=np.float64)
            if anchor_arr.shape == (4, 4) and head.shape == (4, 4):
                first_run_jump = float(np.linalg.norm(head[:3, 3] - anchor_arr[:3, 3]))
                # The elapsed time that matters is between the *anchor* and the first committed
                # frame, not between two candidate frames. The anchor is the last trusted pose,
                # which with a confirmation margin is seconds older than the candidate: measuring
                # the jump without that interval compares motion to a discontinuity bound and
                # refuses every candidate on a moving platform (1.25 m over 2.33 s at 0.54 m/s).
                dt0 = 0.0
                if runs[0][0] in self._kf_timestamps:
                    if reentry_anchor_ts_ns is not None:
                        dt0 = max(0.0, (self._kf_timestamps[runs[0][0]]
                                        - int(reentry_anchor_ts_ns)) * 1e-9)
                    elif kf_sorted[0] in self._kf_timestamps:
                        # Legacy callers that cannot date their anchor keep the old, stricter
                        # reading; the report says so through boundary_basis.
                        dt0 = max(0.0, (self._kf_timestamps[runs[0][0]]
                                        - self._kf_timestamps[kf_sorted[0]]) * 1e-9)
                if not boundary_jump_within_envelope(first_run_jump, dt0, jump_bound):
                    boundary_ok = False
        # Without an independent relative-motion measurement the check is an elapsed-time speed
        # envelope, not geometric continuity; say so rather than presenting it as verified.
        boundary_basis = "BOUND_ONLY"

        _mark("support_and_boundary")
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
            # Deferred frames are holes in the commit, not a truncated tail. Record each contiguous
            # run so the graph consequence is visible: a single unverifiable keyframe between two
            # committed ones is a gap, not a reason to discard everything after it.
            "deferred_runs": self._contiguous_runs(deferred_keys),
            "segment_boundary_jumps_m": boundary_jumps,
            "segment_boundary_ok": boundary_ok,
            "first_run_jump_m": first_run_jump,
            "boundary_basis": boundary_basis,
            "first_deferred_reason": (
                self._noncommittable_reason(
                    deferred_keys[0], reference_keys, incumbent_keys
                )
                if deferred_keys
                else None
            ),
        }

        holdout_nis_list = []
        fims_after = []
        for k in scorable_holdout:
            T_k = repaired_poses[k]
            pts_b = self.scan_buffer_body[k]
            pts_w = (pts_b @ T_k[:3, :3].T) + T_k[:3, 3]
            nis_k = compute_disjoint_holdout_point_to_plane_nis(
                train_world, pts_w, delta_pose_se3=np.eye(4), sigma_meas_m=self.sigma_meas_m
            )
            holdout_nis_list.append(nis_k)
            fim_k, _, _, _, _ = compute_6dof_point_to_plane_fim(
                pts_w, sigma_meas_m=0.075, aux_odom_info_6x6=aux_or_loop_info_6x6
            )
            fims_after.append(fim_k)

        _mark("holdout_nis_and_fim")
        mean_holdout_nis = float(np.mean(holdout_nis_list)) if holdout_nis_list else float("inf")
        # The gate reads ||P_after|| against a fixed bound, and a covariance depends on where the
        # tangent-space origin is. The regulariser that builds it therefore has to be added in the
        # basis the gate evaluates in: epsilon*I in world, inverted and then transported, is
        # not epsilon*I in the anchor body frame (Ad is not orthogonal once the translation is
        # non-zero). On the fixed 400-point fixture a pure 20 m world-origin change moved the norm
        # from .4876 to .4336 with the same physical cloud -- re-expressing the problem, not
        # changing it. Build the covariance in the anchor body frame instead.
        segment = self.tx_mgr.active_quarantine
        frame_after = TangentFrame("world", "rot_trans", "world")
        anchor_frame = (None if segment is None else segment.weak_direction_frame)
        if (fims_after and segment is not None and segment.anchor_pose_world is not None
                and anchor_frame is not None and anchor_frame.frame == "body"):
            T_body_world = np.linalg.inv(np.asarray(segment.anchor_pose_world,
                                                    dtype=np.float64))
            info_after = transport_information(np.mean(fims_after, axis=0), T_body_world)
            frame_after = TangentFrame("body", "rot_trans", anchor_frame.anchor)
        elif fims_after:
            info_after = np.mean(fims_after, axis=0)
        if fims_after:
            cov_after = np.linalg.inv(info_after + np.eye(6) * 1e-3)
        else:
            info_after = np.eye(6) * 1e-3
            cov_after = np.eye(6) * 1e3

        # Paired-benefit evidence must be measured, never assumed; unmeasured components stay None
        # and force the gate to wait (Mode 3/4) instead of committing.
        # The two ways the scored set can end up empty must not share one log string: an empty
        # *input* candidate and a non-empty candidate with no supportable frame send the operator
        # to completely different places.
        paired_ok, wilson_lb, reentry_jump = self._measure_paired_evidence(
            candidate_poses,
            incumbent_poses=incumbent_poses,
            reentry_anchor_pose=reentry_anchor_pose,
            reference_world=train_world,
            reference_keys=reference_keys,
            empty_reason=(
                "no_committable_frames" if (not commit_keys and kf_sorted) else "no_repaired_poses"
            ),
            support_reference=support_ref,
            support_index=support_index,
            # The boundary frame of the *candidate*, independent of which frames are committable.
            reentry_candidate_pose=(repaired_poses[kf_sorted[0]] if kf_sorted else None),
        )

        _mark("paired_evidence")
        cand = CandidateMap(
            candidate_id=candidate_id,
            parent_map_version=self.tx_mgr.trusted_version,
            # Only verified frames enter the candidate. The transaction manager commits exactly
            # this dict, so there is no path by which an unscored frame reaches the trusted map.
            repaired_poses=candidate_poses,
            verified_pose_keys=frozenset(commit_keys),
            deferred_pose_keys=tuple(deferred_keys),
            boundary_continuity_ok=boundary_ok,
            boundary_jumps_m=boundary_jumps,
            boundary_basis=boundary_basis,
            info_after_6x6=info_after,
            cov_after_6x6=cov_after,
            # Both quantities are expressed in `frame_after`: the candidate's information and
            # covariance are moved out of world once, together, and are inverted/regularised in
            # that one basis, so the bound the gate applies does not depend on the world origin.
            info_after_frame=frame_after,
            cov_after_frame=frame_after,
            holdout_nis=mean_holdout_nis,
            reentry_elapsed_s=(
                None if (reentry_anchor_ts_ns is None or not kf_sorted
                         or kf_sorted[0] not in self._kf_timestamps)
                else max(0.0, (self._kf_timestamps[kf_sorted[0]]
                               - int(reentry_anchor_ts_ns)) * 1e-9)),
            repairer_name=candidate_id,
            paired_benefit_approved=paired_ok,
            wilson_lower_bound=wilson_lb,
            reentry_pos_jump_m=reentry_jump,
        )
        _mark("candidate_built")
        report = self.tx_mgr.validate_and_resolve(cand)
        _mark("gate_and_commit")
        if report.accepted:
            self._sync_spatial_map_with_trusted_poses()
            self.voxel_journal.commit_generation()
        return report
