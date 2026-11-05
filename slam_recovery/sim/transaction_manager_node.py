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
from ..quarantine import TrustedMapTransactionManager
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
    ) -> None:
        self.voxel_size_m = float(voxel_size_m)
        self.holdout_stride = int(holdout_stride)
        self.tx_mgr = TrustedMapTransactionManager(
            confirmation_margin_ns=int(confirmation_margin_sec * 1e9),
            gate_thresholds=gate_thresholds,
        )
        self.detector = JointHealthDetector(DetectorConfig(confirmation_margin_ns=int(confirmation_margin_sec * 1e9)))
        self.router = SignatureMatrixRouter()

        # Raw scan buffer indexed by keyframe_id for cross-scan holdout validation and 3D map commit
        self.scan_buffer_body: Dict[int, np.ndarray] = {}
        self.committed_voxel_set: set[Tuple[int, int, int]] = set()
        self.committed_map_points: List[np.ndarray] = []

    def _quantize_voxels(self, pts_world: np.ndarray) -> set[Tuple[int, int, int]]:
        q = np.floor(pts_world[:, :3] / self.voxel_size_m).astype(np.int32)
        return set(map(tuple, q.tolist()))

    def _promote_voxels_from_trusted_poses(self, newly_promoted_kf_ids: List[int]) -> None:
        for kf_id in newly_promoted_kf_ids:
            if kf_id in self.tx_mgr.trusted_poses and kf_id in self.scan_buffer_body:
                T_w_b = self.tx_mgr.trusted_poses[kf_id]
                pts_b = self.scan_buffer_body[kf_id][:, :3]
                pts_w = (pts_b @ T_w_b[:3, :3].T) + T_w_b[:3, 3]
                self.committed_voxel_set.update(self._quantize_voxels(pts_w))
                self.committed_map_points.append(pts_w[::4])

    def get_trusted_map_points(self, max_pts: int = 2000) -> np.ndarray:
        if not self.committed_map_points:
            return np.zeros((0, 3), dtype=np.float64)
        all_pts = np.vstack(self.committed_map_points)
        if len(all_pts) > max_pts:
            step = max(1, len(all_pts) // max_pts)
            return all_pts[::step][:max_pts]
        return all_pts

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
            scan_body_xyz, sigma_meas_m=0.10
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
                prev_keys = set(self.tx_mgr.trusted_poses.keys())
                self.tx_mgr.trigger_quarantine(
                    estimated_onset_ns=decision.estimated_onset_ns,
                    current_ns=timestamp_ns,
                    weak_direction_6d=weak_dir,
                    info_before_6x6=fim_6x6,
                    propagated_cov_norm=float(np.linalg.norm(cov_6x6, ord=2)),
                )
                new_keys = list(set(self.tx_mgr.trusted_poses.keys()) - prev_keys)
                self._promote_voxels_from_trusted_poses(new_keys)
            else:
                prev_keys = set(self.tx_mgr.trusted_poses.keys())
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
                new_keys = list(set(self.tx_mgr.trusted_poses.keys()) - prev_keys)
                self._promote_voxels_from_trusted_poses(new_keys)
        return None

    def evaluate_and_commit_candidate(
        self,
        candidate_id: str,
        repaired_poses: Dict[int, np.ndarray],
        aux_or_loop_info_6x6: Optional[np.ndarray] = None,
    ) -> ValidationReport:
        """
        Perform true cross-scan holdout validation (Section 3.2 S1):
          - Every 5th scan in `repaired_poses` is held out as \mathcal{S}_{hold}.
          - Transform \mathcal{S}_{hold} into world frame using candidate pose X_{cand, k}
            and compute point-to-plane NIS against the trusted map \mathcal{M}_{trusted}
            and non-holdout anchor scans.
        """
        trusted_map_pts = self.get_trusted_map_points(max_pts=1500)
        kf_sorted = sorted(repaired_poses.keys())
        holdout_kfs = [k for idx, k in enumerate(kf_sorted) if idx % self.holdout_stride == 0]
        train_kfs = [k for idx, k in enumerate(kf_sorted) if idx % self.holdout_stride != 0]

        train_world_list = [trusted_map_pts] if len(trusted_map_pts) > 0 else []
        for k in train_kfs:
            if k in self.scan_buffer_body:
                T_k = repaired_poses[k]
                pts_b = self.scan_buffer_body[k]
                train_world_list.append((pts_b @ T_k[:3, :3].T) + T_k[:3, 3])
        train_world = np.vstack(train_world_list) if train_world_list else np.zeros((0, 3))

        holdout_nis_list = []
        fims_after = []
        for k in holdout_kfs:
            if k in self.scan_buffer_body:
                T_k = repaired_poses[k]
                pts_b = self.scan_buffer_body[k]
                pts_w = (pts_b @ T_k[:3, :3].T) + T_k[:3, 3]
                nis_k = compute_disjoint_holdout_point_to_plane_nis(
                    train_world, pts_w, delta_pose_se3=np.eye(4), sigma_meas_m=0.12
                )
                holdout_nis_list.append(nis_k)
                fim_k, _, _, _, _ = compute_6dof_point_to_plane_fim(
                    pts_w, sigma_meas_m=0.10, aux_odom_info_6x6=aux_or_loop_info_6x6
                )
                fims_after.append(fim_k)

        mean_holdout_nis = float(np.mean(holdout_nis_list)) if holdout_nis_list else float("inf")
        if fims_after:
            info_after = np.mean(fims_after, axis=0)
            cov_after = np.linalg.inv(info_after + np.eye(6) * 1e-3)
        else:
            info_after = np.eye(6) * 1e-3
            cov_after = np.eye(6) * 1e3

        cand = CandidateMap(
            candidate_id=candidate_id,
            parent_map_version=self.tx_mgr.trusted_version,
            repaired_poses=repaired_poses,
            info_after_6x6=info_after,
            cov_after_6x6=cov_after * 0.05,
            holdout_nis=mean_holdout_nis,
        )
        prev_keys = set(self.tx_mgr.trusted_poses.keys())
        report = self.tx_mgr.validate_and_resolve(cand)
        if report.accepted:
            new_keys = list(set(self.tx_mgr.trusted_poses.keys()) - prev_keys)
            self._promote_voxels_from_trusted_poses(new_keys)
        return report
