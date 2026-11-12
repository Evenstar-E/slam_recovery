#!/usr/bin/env python3
"""Native same-process closed loop: the recovery transaction node, hosted next to FAST-LIVO2.

What this is
------------
`OnlineRecoveryTransactionNode` was written to run online but has only ever been driven by offline
replays, which build the candidate poses by hand and skip `step_frame` entirely (see
`experiments/run_four_arm_same_input.py`: *"step_frame() is bypassed by this replay"*). This module
wraps it in a ROS node that consumes the host's own output while the host runs, so the admission
path -- detect -> quarantine -> candidate -> gate -> commit/refuse -> continue -- is exercised end to
end rather than asserted.

What this is NOT
----------------
The candidate is the **host's own poses recorded during the quarantine** (`candidate_source =
"host_poses"`). This stage measures the gate's *refusal* behaviour on a candidate that the archived
four-arm already showed it refuses; it does not measure a re-estimating repairer, and a run that
refuses every candidate must not be read as "the repair works". A second stage,
`candidate_source = "icp_reregistration"`, is archived separately and never pooled with this one.

Contract with the gate (read before changing anything)
------------------------------------------------------
* `step_frame(kf_id, timestamp_ns, pose_se3, scan_body_xyz, nis_value)` is the only ingest path.
  On this revision it returns ``None`` on every branch; the ``ValidationReport`` is produced by
  ``evaluate_and_commit_candidate``, which needs ``repaired_poses``, ``incumbent_poses`` and
  ``reentry_anchor_pose``. Supplying all three is what makes a decision possible at all.
* ``pose_se3`` is **T_wb (body -> world)**, the same convention the offline arms use
  (``world_points = pts @ R.T + t``). A reversed convention is invisible in
  ``weak_dir_info_before`` -- the quadratic form is invariant under the transport -- and shows up
  only in ``weak_dir_info_after``, so the raw first-trigger matrix is recorded per candidate.

Nothing in this file changes the gate, the transaction manager, the quarantine manager or the NIS
estimator's defaults. Every number it writes is either produced by those components or counted here.
"""

from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from slam_recovery.core import BackendDelta, RecoveryState, TangentFrame
from slam_recovery.repair.pose_reregistration import ICP_CONFIG, reregister_segment
from slam_recovery.ros.availability_log import AvailabilityRecorder
from slam_recovery.ros.cloud_repair import (
    ReferenceGrid,
    body_z_bias,
    estimate_body_z_bias,
    shift_z_cloud,
)
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.validation import (
    compute_6dof_point_to_plane_fim,
    compute_disjoint_holdout_point_to_plane_nis,
)

# ---- declared parameters (frozen for the run; every one is written into the receipt) ----------
# The pose stream is 15 Hz (measured interarrival 66.6 ms) and the scan stream 10 Hz, and the odom
# stamp is the last IMU time in the processed group, not the lidar stamp. The measured offset
# between a scan and its nearest pose is p10 -27 ms / median +1.5 ms / p90 +30 ms, so a 20 ms
# window pairs 58% of scans and a window of half the pose period pairs the intended partner.
PAIR_DT_NS = 40_000_000
SCAN_CAP = 6000                  # points kept per scan, by uniform stride, for FIM and NIS
NIS_RADIUS_M = 3.0               # "trusted map points near the current pose"
NIS_MIN_TRAIN = 30               # below this the estimator itself has no reference
NIS_MIN_HOLDOUT = 10             # below this the estimator itself has no holdout
EXTRAP_FRAMES = 5                # tail length for the incumbent's constant-velocity extrapolation
# The frozen stamp is the deadline frame's pose stamp; its group ends ~35-70 ms later, and a
# terminal stamp equal to the pose stamp would truncate that frame's group and leave its repaired
# cloud unmatched. The grace is declared here, not tuned per run.
REPLAY_END_GRACE_NS = 100_000_000
RSS_POLL_SEC = 1.0
# How often the spatially sampled reference is rebuilt. Not a point budget: the voxel size still
# fixes the point spacing; this only bounds how far the reference can lag the map.
REFERENCE_REFRESH_NS = 500_000_000

# The frozen per-candidate record, in schema order. Exactly these keys, missing values as null;
# no extra keys are added here -- anything else belongs in the run summary, not in the stream.
CANDIDATE_KEYS = (
    "run_id",
    "candidate_id",
    "t_trigger_ns",
    "t_decision_ns",
    "mode",
    "accepted",
    "deferred_pose_keys",
    "committed_pose_keys",
    "refusal_reason",
    "weak_dir_info_before",
    "weak_dir_info_after",
    "holdout_nis",
    "paired_benefit_status",
    "wilson_lower_bound",
    "reentry_pos_jump_m",
    "parent_map_version",
    "candidate_source",
    "pose_se3_first_trigger",
)

_POINT_FIELD_DTYPE = {1: "i1", 2: "u1", 3: "i2", 4: "u2", 5: "i4", 6: "u4", 7: "f4", 8: "f8"}


# ---------------------------------------------------------------------------------------------
# geometry helpers (no ROS dependency, so they are testable without a master)
# ---------------------------------------------------------------------------------------------
def quat_to_rot(x: float, y: float, z: float, w: float) -> np.ndarray:
    """Unit-quaternion (x, y, z, w) to a 3x3 rotation matrix."""
    n = x * x + y * y + z * z + w * w
    if n < 1e-12:
        return np.eye(3)
    s = 2.0 / n
    return np.array(
        [
            [1.0 - s * (y * y + z * z), s * (x * y - z * w), s * (x * z + y * w)],
            [s * (x * y + z * w), 1.0 - s * (x * x + z * z), s * (y * z - x * w)],
            [s * (x * z - y * w), s * (y * z + x * w), 1.0 - s * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def pose_to_matrix(translation, quaternion) -> np.ndarray:
    """(px, py, pz) + (qx, qy, qz, qw) to a homogeneous T_wb."""
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = quat_to_rot(*[float(v) for v in quaternion])
    T[:3, 3] = [float(v) for v in translation]
    return T


def _rotation_to_quaternion(R: np.ndarray) -> List[float]:
    """Rotation matrix -> (x, y, z, w) without a scipy dependency."""
    m = np.asarray(R, dtype=np.float64)
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0.0:
        s = np.sqrt(tr + 1.0) * 2.0
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2.0
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2.0
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2.0
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    q = np.array([x, y, z, w], dtype=np.float64)
    return list(q / np.linalg.norm(q))


def subsample(pts: np.ndarray, cap: int) -> np.ndarray:
    """Uniform stride subsample, so the retained index set is reproducible and order-preserving."""
    if len(pts) <= cap:
        return pts
    step = max(1, len(pts) // cap)
    return pts[::step][:cap]


def extrapolate_incumbent(
    trusted_poses: Dict[int, np.ndarray],
    kf_timestamps: Dict[int, int],
    query_timestamps_ns: Dict[int, int],
    tail_frames: int = EXTRAP_FRAMES,
) -> Tuple[Dict[int, np.ndarray], Optional[np.ndarray], Dict[str, Any]]:
    """Constant-velocity extrapolation from the last committed keyframes.

    Same recipe as the offline four-arm arm (`run_four_arm_same_input.py`): velocity is the
    displacement across the last ``tail_frames`` trusted keyframes divided by their elapsed time,
    the anchor is the newest of them, and only the translation is extrapolated -- the rotation is
    held at the anchor, so the extrapolation never claims an attitude the map did not observe.
    """
    keys = sorted(k for k in trusted_poses if k in kf_timestamps)
    basis: Dict[str, Any] = {
        "tail_frames_requested": int(tail_frames),
        "trusted_keyframes": len(keys),
        "anchor_key": None,
        "velocity_mps": None,
        "rotation_held": True,
    }
    if not keys:
        basis["status"] = "NO_TRUSTED_KEYFRAME"
        return {}, None, basis

    if len(keys) >= 2:
        tail = keys[-tail_frames:] if len(keys) >= tail_frames else keys
        t0, t1 = int(kf_timestamps[tail[0]]), int(kf_timestamps[tail[-1]])
        dt = (t1 - t0) * 1e-9
        if dt > 1e-9:
            v = (np.asarray(trusted_poses[tail[-1]], dtype=np.float64)[:3, 3]
                 - np.asarray(trusted_poses[tail[0]], dtype=np.float64)[:3, 3]) / dt
            basis["status"] = "CONSTANT_VELOCITY"
        else:
            v = np.zeros(3, dtype=np.float64)
            basis["status"] = "ZERO_VELOCITY_DEGENERATE_TAIL"
        basis["tail_keys"] = [int(k) for k in tail]
        basis["velocity_mps"] = [float(x) for x in v]
    else:
        v = np.zeros(3, dtype=np.float64)
        basis["status"] = "ZERO_VELOCITY_SINGLE_KEYFRAME"

    anchor_key = keys[-1]
    anchor = np.asarray(trusted_poses[anchor_key], dtype=np.float64).copy()
    anchor_ts = int(kf_timestamps[anchor_key])
    basis["anchor_key"] = int(anchor_key)
    basis["anchor_timestamp_ns"] = anchor_ts

    out: Dict[int, np.ndarray] = {}
    for kf_id, ts_ns in query_timestamps_ns.items():
        T = anchor.copy()
        T[:3, 3] = anchor[:3, 3] + v * ((int(ts_ns) - anchor_ts) * 1e-9)
        out[kf_id] = T
    return out, anchor.copy(), basis


def candidate_record(
    run_id: str,
    candidate_id: str,
    t_trigger_ns: Optional[int],
    t_decision_ns: Optional[int],
    report: Any,
    evidence: Optional[Dict[str, Any]],
    parent_map_version: Optional[int],
    candidate_source: str,
    pose_first_trigger: Optional[np.ndarray],
) -> Dict[str, Any]:
    """Build one frozen-schema row from a ValidationReport plus the two values it does not carry.

    ``wilson_lower_bound`` and ``reentry_pos_jump_m`` live on ``CandidateMap`` / the node's paired-
    evidence diagnostics, never on ``ValidationReport``; they are read here, not recomputed. A
    non-finite ``holdout_nis`` is written as null and counted separately in the summary, so
    "measured as infinite" and "not recorded" stay distinguishable.
    """
    ev = evidence or {}

    def _f(x):
        if x is None:
            return None
        x = float(x)
        return x if math.isfinite(x) else None

    row: Dict[str, Any] = {k: None for k in CANDIDATE_KEYS}
    row["run_id"] = run_id
    row["candidate_id"] = candidate_id
    row["t_trigger_ns"] = None if t_trigger_ns is None else int(t_trigger_ns)
    row["t_decision_ns"] = None if t_decision_ns is None else int(t_decision_ns)
    row["candidate_source"] = candidate_source
    row["parent_map_version"] = None if parent_map_version is None else int(parent_map_version)
    if pose_first_trigger is not None:
        row["pose_se3_first_trigger"] = [float(x) for x in
                                         np.asarray(pose_first_trigger, dtype=np.float64)
                                         .reshape(16)]
    if report is None:
        return row
    mode = getattr(report, "mode", None)
    row["mode"] = getattr(mode, "value", mode)
    row["accepted"] = None if getattr(report, "accepted", None) is None else bool(report.accepted)
    row["deferred_pose_keys"] = _int_list(getattr(report, "deferred_pose_keys", None))
    row["committed_pose_keys"] = _int_list(getattr(report, "committed_pose_keys", None))
    row["refusal_reason"] = getattr(report, "reason", None)
    row["weak_dir_info_before"] = _f(getattr(report, "weak_dir_info_before", None))
    row["weak_dir_info_after"] = _f(getattr(report, "weak_dir_info_after", None))
    row["holdout_nis"] = _f(getattr(report, "holdout_nis", None))
    row["paired_benefit_status"] = getattr(report, "evidence_status", None)
    row["wilson_lower_bound"] = _f(ev.get("wilson_lower_bound"))
    row["reentry_pos_jump_m"] = _f(ev.get("reentry_pos_jump_m"))
    return row


def candidate_detail_record(
    candidate_id: str,
    t_trigger_ns: Optional[int],
    t_decision_ns: Optional[int],
    keys: List[int],
    ts_by_key: Dict[int, int],
    repaired_poses: Dict[int, np.ndarray],
) -> Dict[str, Any]:
    """Record the frame set and poses the gate scored, so `after` can be recomputed offline.

    The archived stream says *whether* a candidate passed; it does not say which frames formed
    `after` or with which poses. A later producer change therefore could not be re-derived from
    it -- the frame set would have to be invented, which is a different quantity wearing the same
    name. This sidecar keeps the actual input to `info_after` for the next run.
    """
    return {
        "candidate_id": candidate_id,
        "t_trigger_ns": None if t_trigger_ns is None else int(t_trigger_ns),
        "t_decision_ns": None if t_decision_ns is None else int(t_decision_ns),
        "candidate_frame_ids": [int(k) for k in keys],
        "candidate_frame_ts_ns": [int(ts_by_key.get(int(k), 0)) for k in keys],
        "repaired_poses": {
            str(int(k)): [float(v) for v in np.asarray(p, dtype=np.float64).reshape(16)]
            for k, p in repaired_poses.items()
        },
    }


def _int_list(v) -> Optional[List[int]]:
    if v is None:
        return None
    try:
        return [int(x) for x in v]
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------------------------
# pairing
# ---------------------------------------------------------------------------------------------
class FramePairer:
    """One-to-one nearest pairing of pose and scan streams inside a fixed time window.

    Messages are matched from the front of each queue. A message that falls more than ``dt_ns``
    behind the other stream's head can never be matched to anything still coming, so it is counted
    as dropped instead of being held (and instead of being silently paired with a stale partner).
    """

    def __init__(self, dt_ns: int = PAIR_DT_NS) -> None:
        self.dt_ns = int(dt_ns)
        self._poses: deque = deque()
        self._scans: deque = deque()
        self.paired = 0
        self.poses_received = 0
        self.scans_received = 0
        self.poses_unpaired = 0
        self.scans_unpaired = 0
        self.max_abs_dt_ns = 0
        self.max_backlog = 0
        # Raw stamps, so a poor pairing rate can be diagnosed from the artefacts instead of
        # guessed at. Bounded: a long bag must not turn the summary into a dump.
        self.pose_stamps_ns: List[int] = []
        self.scan_stamps_ns: List[int] = []
        self.stamp_log_cap = 4000

    def add_pose(self, stamp_ns: int, payload) -> List[Tuple[int, int, Any, Any]]:
        self.poses_received += 1
        if len(self.pose_stamps_ns) < self.stamp_log_cap:
            self.pose_stamps_ns.append(int(stamp_ns))
        self._poses.append((int(stamp_ns), payload))
        return self._drain()

    def add_scan(self, stamp_ns: int, payload) -> List[Tuple[int, int, Any, Any]]:
        self.scans_received += 1
        if len(self.scan_stamps_ns) < self.stamp_log_cap:
            self.scan_stamps_ns.append(int(stamp_ns))
        self._scans.append((int(stamp_ns), payload))
        return self._drain()

    def _drain(self) -> List[Tuple[int, int, Any, Any]]:
        out = []
        while self._poses and self._scans:
            p_ns, p = self._poses[0]
            s_ns, s = self._scans[0]
            dt = p_ns - s_ns
            if abs(dt) <= self.dt_ns:
                self._poses.popleft()
                self._scans.popleft()
                self.paired += 1
                self.max_abs_dt_ns = max(self.max_abs_dt_ns, abs(dt))
                out.append((p_ns, s_ns, p, s))
            elif dt < 0:
                self._poses.popleft()
                self.poses_unpaired += 1
            else:
                self._scans.popleft()
                self.scans_unpaired += 1
        self.max_backlog = max(self.max_backlog, len(self._poses), len(self._scans))
        return out

    def flush(self) -> None:
        self.poses_unpaired += len(self._poses)
        self.scans_unpaired += len(self._scans)
        self._poses.clear()
        self._scans.clear()

    def stats(self) -> Dict[str, Any]:
        matched = self.poses_received + self.scans_received
        return {
            "pair_window_ns": self.dt_ns,
            "poses_received": self.poses_received,
            "scans_received": self.scans_received,
            "paired": self.paired,
            "poses_unpaired": self.poses_unpaired,
            "scans_unpaired": self.scans_unpaired,
            "paired_fraction_of_poses": (self.paired / self.poses_received
                                         if self.poses_received else None),
            "paired_fraction_of_scans": (self.paired / self.scans_received
                                         if self.scans_received else None),
            "max_abs_dt_ns": self.max_abs_dt_ns,
            "max_backlog_messages": self.max_backlog,
            "messages_considered": matched,
        }


# ---------------------------------------------------------------------------------------------
# live NIS
# ---------------------------------------------------------------------------------------------
class LiveNis:
    """Per-frame NIS from the node's own estimator, with an explicit provenance for every frame.

    Roles, fixed before the run (the estimator is never given a made-up reference):

      * ``node_map``     -- the trusted map, sampled **spatially** (one point per occupied voxel,
                            via the node's own ``support_reference``), then restricted to points
                            within ``radius_m`` of the current pose. The point-count cap that
                            ``get_trusted_map_points`` applies is not used here: as that method's
                            own docstring says for the coverage test, a point budget makes the
                            point *spacing* a function of map size, which is a property of the
                            budget rather than of the geometry being scored.
      * ``prev_scan``    -- world points of the previous frame. Used only while the trusted map
                            holds no points at all. The previous scan is a real, disjoint
                            observation of the same scene, not a constant.
      * no reference     -- the frame is **not fed** to the gate. Carrying a constant forward would
                            fabricate a measurement; a frame with no evidence is counted, not gated.
      * ``carried_forward`` -- once a value has been computed, a later frame without a reference
                            reuses it. Declared, counted, and distinguishable from ``computed``.

    ``sigma`` is the node's own ``sigma_meas_m``; this class never picks a noise scale.
    """

    def __init__(self, node: OnlineRecoveryTransactionNode, radius_m: float = NIS_RADIUS_M,
                 min_train: int = NIS_MIN_TRAIN, min_holdout: int = NIS_MIN_HOLDOUT,
                 refresh_ns: int = REFERENCE_REFRESH_NS) -> None:
        self.node = node
        self.radius_m = float(radius_m)
        self.min_train = int(min_train)
        self.min_holdout = int(min_holdout)
        self.refresh_ns = int(refresh_ns)
        self._prev_world: Optional[np.ndarray] = None
        self._last_value: Optional[float] = None
        self._last_value_kf: Optional[int] = None
        self._last_value_ts_ns: Optional[int] = None
        self._support_cache: Optional[np.ndarray] = None
        self._support_key: Optional[tuple] = None
        self._last_refresh_ns: Optional[int] = None
        self._support_hash: Optional[str] = None
        self.refresh_count = 0
        self.counts = {
            "computed": 0,
            "carried_forward": 0,
            "unavailable": 0,
            "reference_node_map": 0,
            "reference_prev_scan": 0,
            "reference_none": 0,
        }
        self.nonfinite = 0

    def support_reference(self, now_ts_ns: Optional[int] = None) -> np.ndarray:
        """The node's spatially sampled trusted map, cached between refreshes.

        `support_reference` de-duplicates every trusted point by voxel, which is O(map points); at
        ten frames a second on a growing map that alone would make the loop quadratic. The cloud is
        therefore rebuilt when the trusted map version changes **and** at least ``refresh_ns`` of
        message time has passed, so the reference lags the map by at most one refresh period. The
        lag is recorded; it is not a point budget, so the point *spacing* still comes from the
        voxel size rather than from the map size.
        """
        key = (int(self.node.tx_mgr.trusted_version), len(self.node.tx_mgr.trusted_poses))
        now = None if now_ts_ns is None else int(now_ts_ns)
        due = (self._support_cache is None or self._support_key != key) and (
            self._last_refresh_ns is None or now is None
            or (now - self._last_refresh_ns) >= self.refresh_ns)
        if due:
            self._support_cache = self.node.support_reference()
            self._support_key = key
            self._last_refresh_ns = now if now is not None else self._last_refresh_ns
            # Identity of the cloud this and the support test both use. Hashed once per refresh:
            # a per-frame hash of tens of thousands of points would make the diagnostic the cost.
            import hashlib
            arr = np.ascontiguousarray(np.asarray(self._support_cache, dtype=np.float32)[:, :3])
            self._support_hash = hashlib.sha256(arr.tobytes()).hexdigest()
            self.refresh_count += 1
        return (self._support_cache if self._support_cache is not None
                else np.zeros((0, 3), dtype=np.float64))

    def reference_identity(self) -> Dict[str, Any]:
        """What reference this frame was scored against, without recomputing it."""
        return {
            "cache_key": (None if self._support_key is None else list(self._support_key)),
            "refresh_ns": self._last_refresh_ns,
            "points": (None if self._support_cache is None else int(len(self._support_cache))),
            "sha256": self._support_hash,
        }

    def _reference(self, pose: np.ndarray, now_ts_ns: Optional[int] = None,
                   detail: Optional[dict] = None) -> Tuple[Optional[np.ndarray], str]:
        trusted = self.support_reference(now_ts_ns)
        near_count = 0
        if len(trusted) >= self.min_train:
            d = np.linalg.norm(trusted - pose[:3, 3], axis=1)
            near_count = int(np.count_nonzero(d <= self.radius_m))
            near = trusted[d <= self.radius_m]
            if len(near) >= self.min_train:
                if detail is not None:
                    detail.update({"trusted_total": int(len(trusted)),
                                   "near_radius_count": near_count,
                                   "near_radius_m": float(self.radius_m),
                                   "prev_scan_points": (None if self._prev_world is None
                                                        else int(len(self._prev_world))),
                                   "selected_reference_source": "node_map",
                                   "selected_reference_points": int(len(near))})
                return near, "node_map"
        if self._prev_world is not None and len(self._prev_world) >= self.min_train:
            if detail is not None:
                detail.update({"trusted_total": int(len(trusted)),
                               "near_radius_count": near_count,
                               "near_radius_m": float(self.radius_m),
                               "prev_scan_points": int(len(self._prev_world)),
                               "selected_reference_source": "prev_scan",
                               "selected_reference_points": int(len(self._prev_world))})
            return self._prev_world, "prev_scan"
        if detail is not None:
            detail.update({"trusted_total": int(len(trusted)),
                           "near_radius_count": near_count,
                           "near_radius_m": float(self.radius_m),
                           "prev_scan_points": (None if self._prev_world is None
                                                else int(len(self._prev_world))),
                           "selected_reference_source": "none",
                           "selected_reference_points": 0})
        return None, "none"

    def measure(self, pose: np.ndarray, scan_body: np.ndarray,
                now_ts_ns: Optional[int] = None, kf_id: Optional[int] = None,
                detail: Optional[dict] = None) -> Tuple[Optional[float], str, str]:
        """Return ``(value, source, reference)``. ``value`` is None only when nothing is available.

        ``detail`` receives the branch that produced this frame's answer, the raw value class, and
        the provenance of a carried-forward value. Filling it does not change the answer.
        """
        # Transform first, then resolve the reference: the fallback reference is the *previous*
        # frame's cloud, so it must be read before this frame replaces it.
        world = (np.asarray(scan_body, dtype=np.float64)[:, :3] @ pose[:3, :3].T) + pose[:3, 3]
        if detail is not None:
            detail.update({"current_points": int(len(world)),
                           "sigma": float(self.node.sigma_meas_m),
                           "min_train": int(self.min_train),
                           "min_holdout": int(self.min_holdout),
                           "attempted": False, "computed": False})
        ref, ref_name = self._reference(pose, now_ts_ns, detail=detail)
        value: Optional[float] = None
        if ref is not None and len(world) >= self.min_holdout:
            if detail is not None:
                detail.update({"attempted": True, "train_input_points": int(len(ref)),
                               "query_input_points": int(len(world))})
            nis_detail = detail.setdefault("holdout", {}) if detail is not None else None
            v = float(compute_disjoint_holdout_point_to_plane_nis(
                ref, world, delta_pose_se3=np.eye(4), sigma_meas_m=self.node.sigma_meas_m,
                details=nis_detail))
            if math.isfinite(v):
                value = v
                if detail is not None:
                    detail.update({"computed": True, "raw_kind": "finite", "raw_value": float(v)})
            else:
                self.nonfinite += 1
                if detail is not None:
                    kind = "nan" if math.isnan(v) else "inf"
                    detail.update({"computed": True, "raw_kind": kind, "raw_value": float(v)})
        elif detail is not None:
            detail.update({"raw_kind": "not_computed",
                           "raw_reason": ("no_reference" if ref is None
                                          else "current_below_min_holdout")})
        if value is not None:
            self._prev_world = world
            self._last_value = value
            self._last_value_kf = kf_id
            self._last_value_ts_ns = None if now_ts_ns is None else int(now_ts_ns)
            self.counts["computed"] += 1
            self.counts[f"reference_{ref_name}"] += 1
            if detail is not None:
                detail.update({"source": "computed", "effective_nis": float(value),
                               "carried": None})
            return value, "computed", ref_name
        if self._last_value is not None:
            self._prev_world = world
            self.counts["carried_forward"] += 1
            self.counts["reference_none"] += 1
            if detail is not None:
                detail.update({"source": "carried_forward", "effective_nis": float(self._last_value),
                               "carried": {"kf_id": self._last_value_kf,
                                           "stamp_ns": self._last_value_ts_ns,
                                           "age_s": (None if (now_ts_ns is None or
                                                              self._last_value_ts_ns is None)
                                                     else round((int(now_ts_ns)
                                                                 - self._last_value_ts_ns) * 1e-9, 3))}})
            return self._last_value, "carried_forward", "none"
        # No measurement was possible. The frame can still serve as the next frame's reference:
        # it is a real observation, just not one this estimator could score.
        if len(world) >= self.min_holdout:
            self._prev_world = world
        self.counts["unavailable"] += 1
        self.counts["reference_none"] += 1
        if detail is not None:
            detail.update({"source": "unavailable", "effective_nis": None,
                           "raw_kind": detail.get("raw_kind", "not_computed"),
                           "raw_reason": detail.get("raw_reason", "no_reference")})
        return None, "unavailable", "none"


# ---------------------------------------------------------------------------------------------
# the closed loop
# ---------------------------------------------------------------------------------------------
class Episode:
    """One quarantine segment: its trigger frame and every frame registered while it is open."""

    def __init__(self, index: int, trigger_ts_ns: int, pose: np.ndarray,
                 deadline_ns: int, estimated_onset_ns: Optional[int] = None,
                 first_alarm_ts_ns: Optional[int] = None,
                 quarantine_start_ns: Optional[int] = None) -> None:
        self.index = index
        self.trigger_ts_ns = int(trigger_ts_ns)
        self.deadline_ns = int(deadline_ns)
        # The detector's back-dated estimate of when the fault began, as the segment records it.
        # Reporting only the frame that opened the quarantine conflates detection latency with
        # the detector's onset backtracking, and those are separate errors.
        self.estimated_onset_ns = estimated_onset_ns
        self.first_alarm_ts_ns = first_alarm_ts_ns
        # The segment's own t_start_ns is the *quarantine start*, i.e. its onset estimate minus
        # the confirmation margin; reporting it as the estimate would overstate the error by
        # exactly the margin. Both are kept so the arithmetic is checkable.
        self.quarantine_start_ns = quarantine_start_ns
        self.pose = np.asarray(pose, dtype=np.float64).copy()
        self.frames: List[Tuple[int, int, np.ndarray]] = []   # (kf_id, ts_ns, pose)
        # The candidate population is frozen the moment a frame crosses the decision deadline.
        # Frames that arrive afterwards belong to the segment (and, if the commit is partial, to
        # the deferred set) but not to this candidate. Without the freeze, a decision delayed by a
        # pending command or the service tick silently scores a larger population than the other
        # arm of an A/B, which made the repair/control map comparison non-comparable.
        self.frozen = False
        self.frozen_frames: List[Tuple[int, int, np.ndarray]] = []
        self.frozen_at_ns: Optional[int] = None
        self.frames_after_freeze = 0
        self.decided = False
        self.candidate_id = f"cand_{index:04d}"


class CheckpointClient:
    """Drive the host's native checkpoint over a directory of command files.

    The host has no restore entry point, so this is the whole wiring: one command file, which the
    host renames to ``cmd.done`` before executing so it runs exactly once, and one ack file it
    writes back. Nothing here changes a decision -- it only tells the host to copy, restore, or
    replay its own state and map, and records what the host said it did.
    """

    def __init__(self, directory: str, snapshot_period_s: float = 2.0,
                 ack_timeout_s: float = 30.0) -> None:
        self.dir = directory or ""
        self.enabled = bool(self.dir)
        self.period_s = float(snapshot_period_s)
        self.ack_timeout_s = float(ack_timeout_s)
        self.events: List[Dict[str, Any]] = []
        self.snapshots = 0
        self.restores = 0
        self.reprocesses = 0
        self.holds = 0
        self.resumes = 0
        self.failures = 0
        # The hold is written from the subscriber callback (a quarantine opens there) while the
        # ack is collected on the main thread; the queue keeps the two from dropping each other.
        self._pending: List[Dict[str, Any]] = []
        # Commands issued while another is in flight wait here instead of overwriting the shared
        # `cmd` file. The host polls that file on its own thread; two writes inside one poll
        # interval meant the second replaced the first unread, and the decision path issued
        # reprocess and set_state back to back. The lost command also stranded the queue head:
        # poll() matches the oldest command's name, so a later ack never matched it.
        self._outbox: List[Tuple[Dict[str, Any], str, str]] = []
        self._lock = threading.Lock()
        self._io_lock = threading.RLock()
        # Nothing is asked of the host until it has answered once. Its control poll only runs in
        # the host's main loop, which starts ~16 s after launch; a snapshot written before that
        # blocked the driver's main loop for 16.4 s and pushed a decision 18 s past its deadline.
        self.host_ready = False
        self.snapshot_ack_timeouts = 0
        self.snapshots_superseded = 0
        self.snapshot_ack_s: List[float] = []
        self._last_snapshot_wall = 0.0
        self._stopped = False
        if self.enabled:
            os.makedirs(self.dir, exist_ok=True)

    def _write(self, cmd: str, payload: str = "",
               preempt_snapshot: bool = False) -> Dict[str, Any]:
        """Issue one command: write it now, or queue it behind the command in flight.

        A snapshot is read-only, so a time-sensitive command may drop it rather than wait; every
        other command keeps its place. The event is returned immediately either way; its ``wall``
        is filled in when it is actually written, and the ack is collected by poll()/collect().
        """
        event: Dict[str, Any] = {"command": cmd, "wall": None}
        with self._io_lock:
            self._start_or_queue(event, cmd, payload, preempt_snapshot)
        return event

    def _start_or_queue(self, event: Dict[str, Any], cmd: str, payload: str,
                        preempt_snapshot: bool) -> None:
        with self._lock:
            if self._pending:
                head = self._pending[0]
                if preempt_snapshot and head.get("command") == "snapshot":
                    self._pending.pop(0)
                    self.snapshots_superseded += 1
                    head.update(ok=False, error="superseded")
                    self.events.append(head)
                else:
                    self._outbox.append((event, cmd, payload))
                    return
            event["wall"] = round(time.time(), 3)
            self._pending.append(event)
        self._write_file(event, cmd, payload)

    def _write_file(self, event: Dict[str, Any], cmd: str, payload: str) -> None:
        path = os.path.join(self.dir, "cmd")
        ack = os.path.join(self.dir, "ack")
        try:
            if os.path.exists(ack):
                os.unlink(ack)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(cmd + "\n" + payload + "\n")
            os.replace(tmp, path)
        except OSError as exc:
            with self._lock:
                if self._pending and self._pending[-1] is event:
                    self._pending.pop()
                event.update(ok=False, error=f"write: {exc}")
                self.failures += 1
                self.events.append(event)
            self._flush_outbox()

    def _flush_outbox(self) -> None:
        """Send the next queued command once nothing is in flight. Called after every pop."""
        while True:
            with self._io_lock:
                with self._lock:
                    if self._pending or not self._outbox:
                        return
                    event, cmd, payload = self._outbox.pop(0)
                self._start_or_queue(event, cmd, payload, preempt_snapshot=False)

    def collect(self, timeout_s: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Wait for the ack of the oldest outstanding command and account for it exactly once."""
        with self._lock:
            if not self._pending:
                return None
            event = self._pending.pop(0)
        if event.get("ok") is False:            # the write itself failed
            return event
        cmd = event["command"]
        ack = os.path.join(self.dir, "ack")
        deadline = time.time() + (self.ack_timeout_s if timeout_s is None else timeout_s)
        line = self._read_ack_for(cmd)
        while not line and time.time() < deadline:
            time.sleep(0.02)
            line = self._read_ack_for(cmd)
        if line:
            event.update(ok=line.startswith("OK"), ack=line, ack_wall=round(time.time(), 3))
            self.host_ready = True
        else:
            event.update(ok=False, error="ack_timeout")
        if event.get("ok"):
            self._count(cmd)
        else:
            self.failures += 1
        self.events.append(event)
        self._flush_outbox()
        return event

    def _read_ack_for(self, cmd: str) -> str:
        """Read the ack once and return it only if it answers *this* command.

        The ack file is shared, so a late ack for an earlier command must not be mistaken for a
        reply to the current one; the host writes "OK <cmd> ..." for exactly this check.
        """
        try:
            with open(os.path.join(self.dir, "ack"), "r", encoding="utf-8") as fh:
                line = fh.read().strip()
        except OSError:
            return ""
        if not line:
            return ""
        parts = line.split()
        return line if len(parts) >= 2 and parts[1] == cmd else ""

    def _read_received_for(self, cmd: str) -> Optional[float]:
        try:
            with open(os.path.join(self.dir, "ack_received"), "r", encoding="utf-8") as fh:
                line = fh.read().strip()
        except OSError:
            return None
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "RECEIVED" and parts[1] == cmd:
            for p in parts[2:]:
                if p.startswith("wall="):
                    try:
                        return float(p[5:])
                    except ValueError:
                        return None
        return None

    def poll(self) -> Optional[Dict[str, Any]]:
        """Account for a pending command without waiting. Never blocks the main loop."""
        with self._lock:
            if not self._pending:
                return None
            event = self._pending[0]
        if event.get("received_wall") is None:
            rec = self._read_received_for(event["command"])
            if rec:
                event["received_wall"] = rec
                event["received_s"] = round(rec - float(event.get("wall", rec)), 3)
        line = self._read_ack_for(event["command"])
        if not line:
            return None
        with self._lock:
            self._pending.pop(0)
        event.update(ok=line.startswith("OK"), ack=line, ack_wall=round(time.time(), 3))
        if event.get("ok"):
            self.host_ready = True
            if event["command"] == "snapshot":
                self.snapshot_ack_s.append(round(time.time() - float(event.get("wall", 0)), 3))
            self._count(event["command"])
        else:
            self.failures += 1
        self.events.append(event)
        self._flush_outbox()
        return event

    def _count(self, cmd: str) -> None:
        if cmd == "snapshot":
            self.snapshots += 1
        elif cmd == "restore":
            self.restores += 1
        elif cmd == "reprocess":
            self.reprocesses += 1
        elif cmd == "hold":
            self.holds += 1
        elif cmd == "resume":
            self.resumes += 1

    def expire_pending(self, age_s: float) -> None:
        """Drop a snapshot that has not answered within its budget; record it, never wait."""
        with self._lock:
            if not self._pending:
                return
            event = self._pending[0]
        if event["command"] != "snapshot":
            return
        if time.time() - float(event.get("wall", 0)) <= age_s:
            return
        with self._lock:
            if self._pending and self._pending[0] is event:
                self._pending.pop(0)
        if age_s > 0:
            self.snapshot_ack_timeouts += 1
            self.failures += 1
            event.update(ok=False, error="snapshot_ack_timeout")
        else:
            # Dropped to make room for a blocking command: superseded, not failed.
            self.snapshots_superseded += 1
            event.update(ok=False, error="superseded")
        self.events.append(event)
        self._flush_outbox()

    def _send(self, cmd: str, payload: str = "") -> Dict[str, Any]:
        """Issue a command without waiting for it to be applied.

        Blocking here was what cost 30 s when the host was slow inside one LIO frame; the caller now
        gets the event back immediately and poll() fills in received/applied as they arrive.
        """
        self.expire_pending(0.0)
        return self._write(cmd, payload=payload, preempt_snapshot=True)

    def pending(self) -> bool:
        with self._lock:
            return bool(self._pending or self._outbox)

    def read_repair_received(self, timeout_s: float = 1.0) -> Optional[int]:
        """One status round-trip; returns the host's cumulative `repair_received`, or None.

        The repair clouds travel on a topic while the commands travel on the command file. The
        host's ack already carries `repair_received` (checkpointStatus), so the receipt itself is
        the barrier: no new host interface is needed. A status command queues behind any command in
        flight (the client is serialized), and its ack is collected here.
        """
        import re
        import time as _time

        event = self._send("status")
        deadline = _time.time() + float(timeout_s)
        while _time.time() < deadline and not event.get("ack"):
            self.poll()
            _time.sleep(0.01)
        ack = event.get("ack") or ""
        m = re.search(r"repair_received=(\d+)", ack)
        return int(m.group(1)) if m else None

    def wait_for_repair_count(self, expected: int, timeout_s: float = 5.0) -> bool:
        """Block until the host's ack reports `repair_received >= expected`."""
        import time as _time

        expected = int(expected)
        deadline = _time.time() + float(timeout_s)
        while _time.time() < deadline:
            n = self.read_repair_received(min(1.0, max(0.05, deadline - _time.time())))
            if n is not None and n >= expected:
                return True
            _time.sleep(0.05)
        return False

    def hold(self, apply_stamp_ns: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Stop the host writing its map, without waiting: this is called from a callback.

        With `apply_stamp_ns` the host queues the command and executes it just before the first
        group whose lio_time reaches the stamp; without one it applies at the next frame boundary.
        """
        payload = "" if apply_stamp_ns is None else str(int(apply_stamp_ns))
        return self._write("hold", payload=payload, preempt_snapshot=True)

    def tick(self, now_wall: float, quiescent: bool) -> Optional[Dict[str, Any]]:
        """Rolling snapshot while nothing is being judged; nothing at all once stopped.

        Never waits: the command is written and the ack is collected by poll() on a later tick.
        Until the host has answered something, a cheap ``status`` probe is used instead, so the
        driver learns the host is up without asking it for a 100 ms map copy.
        """
        if not self.enabled or self._stopped or not quiescent:
            return None
        if self.pending():
            return None                       # one outstanding command at a time
        if now_wall - self._last_snapshot_wall < self.period_s:
            return None
        self._last_snapshot_wall = now_wall
        if not self.host_ready:
            return self._write("status")
        event = self._write("snapshot")
        event["sent_wall"] = round(time.time(), 3)
        return event

    def restore(self) -> Dict[str, Any]:
        return self._send("restore")

    def snapshot_now(self, apply_stamp_ns: Optional[int] = None) -> Dict[str, Any]:
        """Snapshot; queued behind any command in flight. A stamp defers it in the host."""
        payload = "" if apply_stamp_ns is None else str(int(apply_stamp_ns))
        event = self._send("snapshot", payload)
        event["sent_wall"] = round(time.time(), 3)
        return event

    def reprocess(self, end_stamp_ns: Optional[int] = None) -> Dict[str, Any]:
        """Replay the host's captured frames, optionally only up to `end_stamp_ns`."""
        payload = "" if end_stamp_ns is None else str(int(end_stamp_ns))
        return self._send("reprocess", payload)

    def resume(self) -> Dict[str, Any]:
        """Let the host write its map again; the host side of the recovery loop's re-arm."""
        return self._send("resume")

    def set_state(self, pose) -> Dict[str, Any]:
        # (async, like every other command: the ack is collected by poll())
        """Write an accepted pose back into the host, so it continues from there.

        ``pose`` is 4x4 body-to-world, the same convention as every other pose here.
        """
        import numpy as np

        T = np.asarray(pose, dtype=np.float64)
        q = _rotation_to_quaternion(T[:3, :3])
        payload = " ".join(f"{v:.9f}" for v in
                           (T[0, 3], T[1, 3], T[2, 3], q[0], q[1], q[2], q[3]))
        return self._write("set_state", payload=payload)

    def stop(self) -> None:
        self._stopped = True

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "host_ready": self.host_ready,
            "snapshot_ack_timeouts": self.snapshot_ack_timeouts,
            "snapshots_superseded": self.snapshots_superseded,
            "snapshot_ack_s": list(self.snapshot_ack_s[-50:]),
            "dir": self.dir,
            "snapshot_period_s": self.period_s,
            "snapshots": self.snapshots,
            "restores": self.restores,
            "reprocesses": self.reprocesses,
            "holds": self.holds,
            "resumes": self.resumes,
            "failures": self.failures,
            "events": self.events,
            "note": ("the checkpoint is the host's own _state and voxel map plus the IMU "
                     "pre-integrator's cross-frame values; a snapshot taken while healthy is the "
                     "trusted checkpoint, and its age at the trigger is the snapshot period"),
        }


class NativeClosedLoop:
    """Pairs host output, feeds ``step_frame``, and decides once per quarantine episode."""

    def __init__(
        self,
        node: OnlineRecoveryTransactionNode,
        run_id: str,
        candidate_source: str = "host_poses",
        confirmation_margin_ns: Optional[int] = None,
        pair_dt_ns: int = PAIR_DT_NS,
        scan_cap: int = SCAN_CAP,
        detection_enabled: bool = True,
        icp_time_budget_s: float = 0.0,
        checkpoint_client: Optional["CheckpointClient"] = None,
        repair_publish: bool = False,
        repair_sync_timeout_s: float = 5.0,
        repair_dry_run: bool = False,
        repair_sham: bool = False,
        availability_log: Optional[str] = None,
    ) -> None:
        self.node = node
        self.run_id = run_id
        # Per-frame availability evidence, separate from the capped summary diagnostics.
        self.availability = AvailabilityRecorder(availability_log, run_id=run_id)
        self._last_avail_status: Optional[str] = None
        # The host's own state/map checkpoint, if this run was given a control directory. Without
        # one the run is exactly the observational loop it was before.
        self.cp = checkpoint_client if (checkpoint_client is not None
                                        and checkpoint_client.enabled) else None
        self.cp_actions: List[Dict[str, Any]] = []
        # How many of the manager's lifecycle events this loop has already acted on. A re-arm is
        # the moment the host is allowed to write its map again.
        self._lifecycle_seen = 0
        # CONTROLLED_INTERFACE_TEST: times (seconds from the first frame) at which the loop opens a
        # quarantine itself, through the same manager entry the detector uses. No detector and no
        # truth label is read; the run is labelled by what kind of trigger it used.
        self.scripted_triggers_s: List[float] = []
        self._scripted_done: List[bool] = []
        # Absolute pose stamps: the reproducible anchor. See _maybe_scripted_trigger.
        self.scripted_trigger_stamps_ns: List[int] = []
        self._scripted_done_ns: List[bool] = []
        self._first_frame_ts_ns: Optional[int] = None
        self.scripted_fired: List[Dict[str, Any]] = []
        self.candidate_source = candidate_source
        self.detection_enabled = bool(detection_enabled)
        self.confirmation_margin_ns = int(
            confirmation_margin_ns if confirmation_margin_ns is not None
            else node.tx_mgr.confirmation_margin_ns)
        self.scan_cap = int(scan_cap)
        self.pairer = FramePairer(pair_dt_ns)
        self.nis = LiveNis(node)
        self.next_kf_id = 0
        self.episodes: List[Episode] = []
        self._open: Optional[Episode] = None
        self.records: List[Dict[str, Any]] = []
        self.decision_errors: List[Dict[str, Any]] = []
        # Per-candidate ICP detail, kept beside the frozen 18-key stream rather than inside
        # it: the schema is frozen, and an extra key on some rows would break every consumer
        # that parses by key.
        self.icp_details: List[Dict[str, Any]] = []
        # What the gate actually evaluated, per candidate: which frames formed `after` and the
        # poses it was built from. Without these, `after` cannot be recomputed offline under a
        # different producer -- the archived streams carry only a trigger pose, so any later
        # re-derivation would have to invent a frame set. Kept in its own file for the same
        # reason as `icp_details`: the 18-key stream is frozen.
        self.candidate_details: List[Dict[str, Any]] = []
        self.icp_seconds_total = 0.0
        # The measurement-repair path (INJECTION test). The raw scan message and its own stamp are
        # kept per keyframe so an accepted candidate's frames can be republished on the host's
        # repair channel; the original message is kept, not a re-encoded xyz array, because the
        # host parses x,y,z,intensity,time,ring.
        self._scan_msgs: Dict[int, Any] = {}
        self._scan_index: Dict[int, Tuple[int, Any]] = {}
        self.repair_publish_enabled = bool(repair_publish or repair_sham)
        # Control mode: run the same bias estimation (so the decision costs the same) but publish
        # nothing and send no replay gate. Used to isolate the repair's effect from the corruption.
        self.repair_dry_run = bool(repair_dry_run)
        # Sham control: same publisher, batching, receipts and command time, but the cloud is
        # forwarded unchanged (zero shift). The only difference from the repair arm is whether the
        # measurement is corrected, so replay spans and timing must match.
        self.repair_sham = bool(repair_sham)
        self.publish_repair = None            # callable(PointCloud2), set by the ROS driver
        self.repair_sync_timeout_s = float(repair_sync_timeout_s)
        self._last_icp_delta: Optional[np.ndarray] = None
        self._last_incumbent: Dict[int, np.ndarray] = {}
        # 0 = no budget. A budget that is hit is recorded, because truncating the candidate
        # changes what the gate sees and must never happen silently.
        self.icp_time_budget_s = float(icp_time_budget_s)
        # A decision is requested by the callback and performed by the main loop. Performing it
        # in the callback put a multi-second candidate construction inside a subscriber thread:
        # it raced with shutdown, and on 2026-11-10 a run was killed mid-decision with the
        # summary already written and the record missing.
        self.pending_decision: Optional[str] = None
        self._pending_decision_wall: Optional[float] = None
        self.frames_fed = 0
        self.frames_after_first_decision = 0
        self._first_decision_ts_ns: Optional[int] = None
        self.bag_end_ts_ns: Optional[int] = None
        self._last_ts_ns: Optional[int] = None
        # Per-frame detector state, recorded from what step_frame already computed. Without it a
        # quarantine that opens on the first frames cannot be attributed to the NIS path, the
        # geometry path or the dwell counter after the fact.
        self.diag: List[Dict[str, Any]] = []
        self.diag_cap = 2000
        # Detection availability. The gate is not asked to judge a frame that has no independent
        # reference to be judged against; such frames still grow the map, and are counted as
        # UNAVAILABLE rather than assumed healthy.
        self.detection_counts = {"AVAILABLE": 0, "UNAVAILABLE": 0, "DISABLED_FOR_DIAGNOSIS": 0}
        self.ingested_undetected = 0
        self.first_detected_kf: Optional[int] = None
        self.pose_convention_check: Dict[str, Any] = {"status": "NOT_REACHED"}
        # The first frame at which the detector left HEALTHY. The quarantine opens one dwell
        # window later, so the two timestamps measure different things.
        self._first_alarm_ts_ns: Optional[int] = None

    # -- ingest -------------------------------------------------------------------------------
    def _fed(self, ts_ns: int) -> bool:
        return self._first_decision_ts_ns is None or ts_ns <= self._first_decision_ts_ns

    def on_pair(self, pose_stamp_ns: int, pose: np.ndarray, scan_body: np.ndarray,
                scan_ns: Optional[int] = None) -> None:
        ts_ns = int(pose_stamp_ns)
        self._last_ts_ns = ts_ns
        self.bag_end_ts_ns = ts_ns
        if self._first_decision_ts_ns is not None and ts_ns > self._first_decision_ts_ns:
            self.frames_after_first_decision += 1

        kf_id = self.next_kf_id
        self.next_kf_id += 1
        # Both paths below register the frame; step_frame would do the same, so storing it here
        # only makes the support predicate usable before the decision to gate or not.
        self.node.scan_buffer_body[kf_id] = np.asarray(scan_body, dtype=np.float64)[:, :3].copy()
        self.node._kf_timestamps[kf_id] = ts_ns
        # Keep the scan's own stamp and original message for the repair channel. The host matches
        # a repaired cloud by the scan stamp (not the pose stamp), and it re-parses the full point
        # layout, so a re-encoded xyz array would not do.
        if scan_ns is not None:
            self._scan_index[kf_id] = (int(scan_ns), self._scan_msgs.get(int(scan_ns)))
            if len(self._scan_index) > 256:
                for stale in list(self._scan_index)[:64]:
                    self._scan_index.pop(stale, None)

        nis_detail: Dict[str, Any] = {}
        value, source, reference = self.nis.measure(
            pose, scan_body, now_ts_ns=ts_ns, kf_id=kf_id,
            detail=(nis_detail if self.availability.enabled else None))
        support_ref = self.nis.support_reference(ts_ns)
        # Map size as it stood when this frame's NIS was computed -- not after this frame has been
        # ingested. The diagnostic bins NIS by reference size, so the two must be the same instant.
        kfs_before = int(len(self.node.tx_mgr.trusted_poses))
        pts_before = int(len(support_ref))

        if self._maybe_scripted_trigger(kf_id, ts_ns, pose, scan_body):
            # The frame opened the segment; it belongs to it, and the normal ingest must not run.
            self.frames_fed += 1
            self._record_diag(kf_id, ts_ns, value, source, reference,
                              "SCRIPTED_TRIGGER", kfs_before, pts_before)
            after = self.node.tx_mgr.active_quarantine
            if after is not None:
                self._open_episode(ts_ns, pose, after)
            return

        if not self.detection_enabled:
            # Diagnosis mode: the map grows, the NIS is computed and recorded, and nothing is
            # judged. This is how the NIS-versus-map-size curve is obtained without a threshold.
            status = "DISABLED_FOR_DIAGNOSIS"
            self.detection_counts[status] += 1
            self._record_availability(kf_id, ts_ns, scan_ns, pose, scan_body, {},
                                      nis_detail, None, value is not None, "DISABLED")
            self._ingest_without_detection(kf_id, ts_ns, pose, scan_body, value)
            self._record_diag(kf_id, ts_ns, value, source, reference, status,
                              kfs_before, pts_before)
            self._track_episode(kf_id, ts_ns, pose)
            return

        support_detail: Dict[str, Any] = {}
        supported = self.node._frame_has_reference_support(
            kf_id, support_ref, {kf_id: np.asarray(pose, dtype=np.float64)},
            detail=(support_detail if self.availability.enabled else None))
        predicted_support: Optional[Dict[str, Any]] = None
        prediction_basis: Optional[Dict[str, Any]] = None
        if self.availability.enabled:
            predicted_result = self._predicted_pose(ts_ns)
            if predicted_result is not None:
                predicted, prediction_basis = predicted_result
                predicted_support = {}
                self.node._frame_has_reference_support(
                    kf_id, support_ref, {kf_id: predicted}, detail=predicted_support)
        # Detection is available only when the frame can actually be scored against an independent
        # reference. "Unsupported" and "healthy" are different statements and are recorded as such:
        # an unsupported frame is ingested so the map can grow, but the detector does not judge it.
        available = bool(supported) and value is not None
        status = "AVAILABLE" if available else "UNAVAILABLE"
        self.detection_counts[status] += 1
        self._record_availability(kf_id, ts_ns, scan_ns, pose, scan_body, support_detail,
                                  nis_detail, bool(supported), value is not None, status,
                                  predicted_support=predicted_support,
                                  prediction_basis=prediction_basis)

        before = self.node.tx_mgr.active_quarantine
        if available:
            if self.first_detected_kf is None:
                self.first_detected_kf = kf_id
                self.pose_convention_check = self._pose_convention_check(pose, scan_body, ts_ns)
            self.node.step_frame(kf_id, ts_ns, pose, scan_body, value)
            self.frames_fed += 1
            det_state = getattr(self.node.detector.state, "value", self.node.detector.state)
            if self._first_alarm_ts_ns is None and det_state != "HEALTHY":
                self._first_alarm_ts_ns = int(ts_ns)
        else:
            self.ingested_undetected += 1
            self._ingest_without_detection(kf_id, ts_ns, pose, scan_body, value)
        self._record_diag(kf_id, ts_ns, value, source, reference, status,
                          kfs_before, pts_before)

        after = self.node.tx_mgr.active_quarantine
        # A new segment can open in the same call that closes an old one: `step_frame` may expire
        # the wait, re-arm, and then trigger on the very same frame. Comparing against None only
        # would miss that transition -- the third segment of run 105118Z had no episode, so it was
        # never decided, never closed, and froze the map for the remaining 370 frames.
        if after is not None and after is not before:
            self._open_episode(ts_ns, pose, after)
        self._track_episode(kf_id, ts_ns, pose)

    def _track_episode(self, kf_id: int, ts_ns: int, pose: np.ndarray) -> None:
        """Give the open segment this frame, and ask for a decision at its deadline.

        This was a tail block of ``on_pair``, which the diagnosis branch returns before -- so with
        detection off a forced segment got no frames at all and could only be decided at bag end.
        """
        if self._open is not None:
            if self._open.frozen:
                # The candidate is already fixed; this frame is still part of the segment.
                self._open.frames_after_freeze += 1
                return
            if self._open.decided:
                return
            self._open.frames.append((kf_id, ts_ns, np.asarray(pose, dtype=np.float64).copy()))
            if ts_ns >= self._open.deadline_ns:
                self._open.frozen = True
                self._open.frozen_frames = list(self._open.frames)
                self._open.frozen_at_ns = int(ts_ns)
                self.pending_decision = "confirmation_margin"
                self._pending_decision_wall = time.time()

    def _maybe_scripted_trigger(self, kf_id: int, ts_ns: int, pose: np.ndarray,
                                scan_body: np.ndarray) -> bool:
        """Open a quarantine at a pre-declared time, through the manager's own entry point.

        This is the controlled interface test: it calls ``trigger_quarantine`` with the same
        arguments the node's HEALTHY branch builds, then registers the frame exactly as that branch
        does. It does not consult the detector and it never reads a fault label -- the trigger time
        comes from the test declaration, not from the data.

        Two anchors are supported. Seconds-since-first-frame is convenient but not reproducible to
        the frame: the first *paired* frame moves with startup and load, and a scan whose weak
        direction is one frame away can be refused where its neighbour is accepted. Absolute pose
        stamps (``scripted_trigger_stamps_ns``) make a controlled test reproducible: the trigger
        fires on the first frame at or after the declared stamp, so the declaration names the same
        frame every run (as long as that frame is paired at all).
        """
        if not self.scripted_triggers_s and not self.scripted_trigger_stamps_ns:
            return False
        if self._first_frame_ts_ns is None:
            self._first_frame_ts_ns = int(ts_ns)
            self._scripted_done = [False] * len(self.scripted_triggers_s)
            self._scripted_done_ns = [False] * len(self.scripted_trigger_stamps_ns)
        elapsed_s = (int(ts_ns) - self._first_frame_ts_ns) / 1e9
        for i, at_ns in enumerate(self.scripted_trigger_stamps_ns):
            if self._scripted_done_ns[i] or int(ts_ns) < int(at_ns):
                continue
            if self.node.tx_mgr.state != RecoveryState.HEALTHY:
                continue                      # a segment is already open; the stamp has passed
            self._trigger_segment_now(kf_id, ts_ns, pose, scan_body)
            self._scripted_done_ns[i] = True
            self.scripted_fired.append({
                "declared_ns": int(at_ns), "actual_s": round(elapsed_s, 3),
                "kf_id": int(kf_id), "ts_ns": int(ts_ns),
                "basis": "CONTROLLED_INTERFACE_TEST (trigger_quarantine called directly, "
                         "absolute pose stamp)"})
            return True
        for i, at_s in enumerate(self.scripted_triggers_s):
            if self._scripted_done[i] or elapsed_s < at_s:
                continue
            if self.node.tx_mgr.state != RecoveryState.HEALTHY:
                continue                      # a segment is already open; the time has passed
            self._trigger_segment_now(kf_id, ts_ns, pose, scan_body)
            self._scripted_done[i] = True
            self.scripted_fired.append({
                "declared_at_s": float(at_s), "actual_s": round(elapsed_s, 3),
                "kf_id": int(kf_id), "ts_ns": int(ts_ns),
                "basis": "CONTROLLED_INTERFACE_TEST (trigger_quarantine called directly)"})
            return True
        return False

    def _trigger_segment_now(self, kf_id: int, ts_ns: int, pose: np.ndarray,
                             scan_body: np.ndarray) -> None:
        """The body shared by both trigger anchors: same manager entry, same arguments."""
        fim_6x6, cov_6x6, _min_r, _min_t, weak = compute_6dof_point_to_plane_fim(
            scan_body, sigma_meas_m=0.075)
        self.node.tx_mgr.trigger_quarantine(
            estimated_onset_ns=int(ts_ns),
            current_ns=int(ts_ns),
            weak_direction_6d=np.asarray(weak, dtype=np.float64),
            info_before_6x6=fim_6x6,
            propagated_cov_norm=float(np.linalg.norm(cov_6x6, ord=2)),
            weak_direction_frame=TangentFrame("body", "rot_trans", f"scan:{kf_id}"),
            info_before_frame=TangentFrame("body", "rot_trans", f"scan:{kf_id}"),
            anchor_pose_world=np.asarray(pose, dtype=np.float64).copy(),
        )
        self.node.tx_mgr.register_quarantined_frame(kf_id, int(ts_ns))
        self._first_alarm_ts_ns = int(ts_ns)

    def _predicted_pose(self, ts_ns: int) -> Optional[Tuple[np.ndarray, Dict[str, Any]]]:
        """Short-horizon constant-velocity prediction from the last two trusted poses.

        Used only by the availability diagnostic: it answers whether the support fraction is low
        because the host pose has moved away from the (frozen) trusted map, or because the map
        itself does not cover the scan. It never enters a decision.
        """
        poses = self.node.tx_mgr.trusted_poses
        if not poses:
            return None
        keys = sorted(poses)
        if len(keys) < 2:
            T = np.asarray(poses[keys[-1]], dtype=np.float64).copy()
            return T, {"mode": "last_pose", "base_keys": [int(keys[-1])],
                       "base_stamps_ns": [self.node._kf_timestamps.get(keys[-1])],
                       "velocity_mps": None, "horizon_s": None,
                       "predicted_T": [float(v) for v in T.reshape(-1)]}
        k2, k1 = keys[-1], keys[-2]
        t2 = self.node._kf_timestamps.get(k2)
        t1 = self.node._kf_timestamps.get(k1)
        T = np.asarray(poses[k2], dtype=np.float64).copy()
        if t1 is None or t2 is None or int(t2) == int(t1):
            return T, {"mode": "last_pose", "base_keys": [int(k2)],
                       "base_stamps_ns": [t2], "velocity_mps": None, "horizon_s": None,
                       "predicted_T": [float(v) for v in T.reshape(-1)]}
        v = (np.asarray(poses[k2], dtype=np.float64)[:3, 3]
             - np.asarray(poses[k1], dtype=np.float64)[:3, 3]) / ((int(t2) - int(t1)) * 1e-9)
        horizon = (int(ts_ns) - int(t2)) * 1e-9
        T[:3, 3] = np.asarray(poses[k2], dtype=np.float64)[:3, 3] + v * horizon
        return T, {"mode": "velocity", "base_keys": [int(k1), int(k2)],
                   "base_stamps_ns": [int(t1), int(t2)],
                   "velocity_mps": [float(x) for x in v],
                   "horizon_s": round(horizon, 3),
                   "predicted_T": [float(x) for x in T.reshape(-1)]}

    def _record_availability(self, kf_id: int, ts_ns: int, scan_ns: Optional[int],
                             pose: np.ndarray, scan_body: np.ndarray,
                             support: Dict[str, Any], nis: Dict[str, Any],
                             support_pass: Optional[bool], nis_present: bool,
                             status: str,
                             predicted_support: Optional[Dict[str, Any]] = None,
                             prediction_basis: Optional[Dict[str, Any]] = None) -> None:
        """Write this frame's availability evidence. Derived status is never asserted here."""
        if not self.availability.enabled:
            return
        msg = self._scan_msgs.get(int(scan_ns)) if scan_ns is not None else None
        frame_id = getattr(getattr(msg, "header", None), "frame_id", None) if msg is not None else None
        pts = np.asarray(scan_body, dtype=np.float64)[:, :3]
        finite = int(np.count_nonzero(np.all(np.isfinite(pts), axis=1))) if pts.size else 0
        mgr = self.node.tx_mgr
        seg = mgr.active_quarantine
        derived = ("DISABLED" if status == "DISABLED"
                   else "AVAILABLE" if (support_pass and nis_present) else "UNAVAILABLE")
        row = {
            "kf_id": int(kf_id),
            "pose_stamp_ns": int(ts_ns),
            "scan_stamp_ns": None if scan_ns is None else int(scan_ns),
            "pose_scan_dt_ns": (None if scan_ns is None else int(ts_ns) - int(scan_ns)),
            "scan_frame_id": frame_id,
            "T_wb": [float(v) for v in np.asarray(pose, dtype=np.float64).reshape(-1)],
            "scan": {"points": int(len(pts)), "finite": finite},
            "manager": {"state": getattr(mgr.state, "value", str(mgr.state)),
                        "trusted_version": int(mgr.trusted_version),
                        "trusted_keyframes": int(len(mgr.trusted_poses)),
                        "active_segment": (None if seg is None else seg.segment_id)},
            "reference": self.nis.reference_identity(),
            "support": support or None,
            "support_under_predicted_pose": predicted_support,
            "prediction": prediction_basis,
            "boundary": bool(self._last_avail_status is not None
                             and self._last_avail_status != status),
            "nis": nis or None,
            "support_pass": support_pass,
            "nis_present": bool(nis_present),
            "status": status,
            "status_from_conditions": derived,
        }
        self.availability.record(row)
        self._last_avail_status = status

    def _record_diag(self, kf_id: int, ts_ns: int, value: Optional[float], source: str,
                     reference: str, status: str, kfs_before: int, pts_before: int) -> None:
        if len(self.diag) >= self.diag_cap:
            return
        det = self.node.detector
        self.diag.append({
            "kf_id": int(kf_id), "ts_ns": int(ts_ns),
            "nis": None if value is None else float(value),
            "nis_source": source, "nis_reference": reference,
            "detection_status": str(status),
            "detector_state": getattr(det.state, "value", det.state),
            "cusum": float(getattr(det, "cusum_g", float("nan"))),
            "suspect_dwell": int(getattr(det, "suspect_dwell", -1)),
            "map_points": int(pts_before),
            "trusted_keyframes": int(kfs_before),
        })

    def _ingest_without_detection(self, kf_id: int, ts_ns: int, pose: np.ndarray,
                                  scan_body: np.ndarray, nis_value: Optional[float]) -> None:
        """Promote a frame into the trusted map without asking the detector to judge it.

        This mirrors `OnlineRecoveryTransactionNode.step_frame`'s HEALTHY branch line for line --
        store the scan, build the 6-DoF FIM, append the delta to the confirmation-margin queue,
        resync the spatial map -- and differs in exactly one thing: it does not call
        `detector.step`. The reason is not that the frame is believed healthy; it is that the
        frame cannot be scored against an independent reference, so the detector would have no
        evidence to judge. It is recorded as UNAVAILABLE, which is what it is.

        While a quarantine is open the manager forbids `step_healthy` -- and rightly so, the frame
        belongs to the segment. The frame is then registered on the segment instead, which is the
        same thing `step_frame` does for a quarantined frame.
        """
        self.node.scan_buffer_body[kf_id] = np.asarray(scan_body, dtype=np.float64)[:, :3].copy()
        self.node._kf_timestamps[kf_id] = int(ts_ns)
        # A wait must be allowed to end on this path too. `step_frame` checks it, but while the
        # reference is frozen almost every frame is UNAVAILABLE and never reaches `step_frame`;
        # the first two-event run ended with the segment open and `lifecycle.events = []` for
        # exactly this reason, which made a second event structurally impossible.
        if self.node.tx_mgr.maybe_close_waiting_segment(int(ts_ns)) is not None:
            self.node.detector.reset()
            self.node.tx_mgr.rearm()
        if self.node.tx_mgr.state != RecoveryState.HEALTHY:
            # The segment owns this frame. step_healthy raises here by design, and swallowing that
            # into a callback error would hide 200+ frames of the quarantine.
            self.node.tx_mgr.register_quarantined_frame(kf_id, int(ts_ns))
            return
        fim_6x6, cov_6x6, _min_r, _min_t, _weak = compute_6dof_point_to_plane_fim(
            scan_body, sigma_meas_m=0.075)
        delta = BackendDelta(
            timestamp_ns=int(ts_ns),
            frame_id="map",
            pose_se3=np.asarray(pose, dtype=np.float64).copy(),
            velocity=np.zeros(3),
            bias_acc=np.zeros(3),
            bias_gyr=np.zeros(3),
            cov_6x6=cov_6x6,
            info_6x6=fim_6x6,
            nis_value=float(nis_value) if nis_value is not None else 0.0,
            nis_dof=6,
            factor_ids=[kf_id],
            keyframe_id=kf_id,
        )
        self.node.tx_mgr.step_healthy(delta)
        self.node._sync_spatial_map_with_trusted_poses()

    def _pose_convention_check(self, pose: np.ndarray, scan_body: np.ndarray,
                               now_ts_ns: Optional[int] = None) -> Dict[str, Any]:
        """Score one frame under T_wb and under the reversed reading, once.

        The peer's caution: a reversed pose is invisible in ``weak_dir_info_before`` (the quadratic
        form is invariant) and shows only in ``info_after``. The same asymmetry applies here, so
        the convention is checked on the quantity that actually depends on it -- the residual of
        the scan placed by the pose -- and the two numbers are recorded side by side.
        """
        ref, ref_name = self.nis._reference(pose, now_ts_ns)
        out: Dict[str, Any] = {"reference": ref_name, "frames": 1}
        if ref is None:
            out["status"] = "NO_REFERENCE"
            return out
        pts = np.asarray(scan_body, dtype=np.float64)[:, :3]
        forward = pts @ pose[:3, :3].T + pose[:3, 3]
        reversed_ = pts @ pose[:3, :3] + pose[:3, 3]
        out["nis_forward_T_wb"] = float(compute_disjoint_holdout_point_to_plane_nis(
            ref, forward, np.eye(4), self.node.sigma_meas_m))
        out["nis_reversed_T_bw"] = float(compute_disjoint_holdout_point_to_plane_nis(
            ref, reversed_, np.eye(4), self.node.sigma_meas_m))
        out["status"] = "FORWARD_SELECTED" if (out["nis_forward_T_wb"]
                                               <= out["nis_reversed_T_bw"]) else "REVERSED_SELECTED"
        return out

    def _icp_candidate(self, ep: "Episode", incumbent_poses: Optional[Dict[int, np.ndarray]] = None):
        """One rigid correction for the whole segment, fitted against the frozen trusted map.

        A per-frame registration costs 13 s per frame live -- 23 frames would be five minutes
        inside a decision point. One rigid fit over the segment describes the same repair at one
        registration's cost, and every quarantined keyframe still gets a candidate pose, so the
        paired-evidence population is unchanged.

        The reference is the trusted map as it stood when the quarantine opened: frozen, so the
        candidate cannot be scored against geometry it produced.

        The initial poses matter for a measurement bias. A uniform body-frame shift is absorbed by
        the estimator into its own pose, so registering at the host's pose sees the corrupted cloud
        already aligned and reports ~0 (run 043602Z: 0.003 m against an injected 0.5 m). The
        trusted map's constant-velocity extrapolation (`incumbent_poses`) is an independent pose:
        there the corrupted cloud is displaced by the bias and the fit can recover it.
        """
        scans = {kf: self.node.scan_buffer_body[kf]
                 for kf, _ts, _p in ep.frames if kf in self.node.scan_buffer_body}
        if incumbent_poses:
            inits = {kf: np.asarray(incumbent_poses[kf], dtype=np.float64)
                     for kf, _ts, _p in ep.frames if kf in incumbent_poses}
        else:
            inits = {kf: pose for kf, _ts, pose in ep.frames}
        reference = self.node.get_trusted_map_points(max_pts=1 << 30)
        started = time.perf_counter()
        res = reregister_segment(scans, inits, reference, ICP_CONFIG)
        elapsed = time.perf_counter() - started
        self.icp_seconds_total += elapsed
        corpus = np.vstack([np.asarray(v, dtype=np.float64)[:, :3] @ inits[k][:3, :3].T
                            + inits[k][:3, 3] for k, v in sorted(scans.items())]) \
            if scans else np.zeros((0, 3))
        delta = np.asarray(res.pose, dtype=np.float64)
        # The same correction that makes the candidate poses also describes the measurement bias
        # for the frames it covers; the repair publisher projects it onto the declared body axis,
        # using the rotations of the same initial poses.
        self._last_icp_delta = delta.copy()
        poses = {k: delta @ np.asarray(inits[k], dtype=np.float64) for k in inits}
        detail = {
            "mode": "single_rigid_transform_for_the_segment",
            "init_poses": "incumbent" if incumbent_poses else "host_poses",
            "seconds": elapsed,
            "frames_with_scan": len(scans),
            "frames_candidate": len(poses),
            "reference_points_total": int(len(reference)),
            "segment_points_before_sampling": int(len(corpus)),
            "status": res.status,
            "icp_iterations": int(res.iterations),
            "icp_residual": float(res.final_residual_m),
            "icp_converged": bool(res.converged),
            "icp_inliers": int(res.inliers),
            "reference_points_used": int(res.reference_points),
            "scan_points_used": int(res.scan_points),
            "correction_translation_m": float(np.linalg.norm(delta[:3, 3])),
            "correction_rotation_deg": float(res.rotation_from_init_deg),
        }
        return poses, detail

    def _open_episode(self, ts_ns: int, pose: np.ndarray, segment=None) -> None:
        estimated = None
        q_start = None
        if segment is not None:
            q_start = int(getattr(segment, "t_start_ns", 0)) or None
            if q_start is not None:
                estimated = q_start + self.confirmation_margin_ns
        ep = Episode(len(self.episodes), ts_ns,
                     pose, ts_ns + self.confirmation_margin_ns,
                     estimated_onset_ns=estimated,
                     first_alarm_ts_ns=self._first_alarm_ts_ns,
                     quarantine_start_ns=q_start)
        self.episodes.append(ep)
        self._open = ep
        # The host keeps writing its map until told otherwise. The command is only written here --
        # waiting for the ack inside a subscriber callback would stall the pairing.
        if self.cp is not None:
            # A rolling snapshot sent before the trigger can be applied after it under a playback
            # backlog, so the restore would roll back only part of the segment. Drop any snapshot
            # still queued (read-only, never a state command) before the hold: the host's pending
            # slot is then overwritten by the hold, and the checkpoint in use is the one taken
            # before the trigger. Counted as superseded, not as a failure.
            self.cp.expire_pending(0.0)
            # Idempotent fallback. The checkpoint and capture start are declared at the trigger
            # stamp ahead of time (see main()), because a command sent here is applied at the
            # host's next processed frame, which lags the trigger under a playback backlog.
            self.cp.hold()

    # -- decision -----------------------------------------------------------------------------
    def _repair_gate(self, ep: "Episode", accepted: bool) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Publish the repaired measurements and decide whether the replay may be sent.

        Returns (proceed, repair_meta). When repairs were published but the host did not confirm
        receiving them, `proceed` is False and no `reprocess` may be issued: a replay that cannot
        see the repaired measurements would repeat the previous run's `repairs applied=0`.
        """
        if self.repair_dry_run:
            # Same estimator, same decision cost, no publication: the control for the repair run.
            if not accepted:
                return True, None
            est = self._estimate_repair_bias(ep)
            est.update({"dry_run": True, "published": 0, "synced": False, "batches": []})
            return True, est
        if not (accepted and self.repair_publish_enabled):
            return True, None
        rep = self._publish_repaired_scans(ep)
        if rep.get("published") and not rep.get("synced"):
            return False, rep
        return True, rep

    def _estimate_repair_bias(self, ep: "Episode") -> Dict[str, Any]:
        """Per-frame body-z bias, estimated at the incumbent pose against the trusted map.

        The host pose absorbed the bias, so the scan placed with it is already map-aligned and a
        registration there reports ~0 (run 043602Z: 0.003 m). The gate's incumbent is computed from
        the trusted keyframes and is independent of that pose; at it the corrupted scan is
        displaced along body z and a one-dimensional search recovers the shift.
        """
        reference = self.node.support_reference()
        out: Dict[str, Any] = {"reference_points": int(len(reference)), "per_frame": [],
                               "bias_z_m": None, "mad_m": None, "frames_estimated": 0,
                               "tolerance_m": 0.15, "expected_bias_m": 0.5}
        if len(reference) == 0:
            out["reason"] = "no_reference"
            return out
        grid = ReferenceGrid(reference)
        vals = []
        for kf, _ts, pose in ep.frames:
            scan = self.node.scan_buffer_body.get(kf)
            if scan is None or len(scan) == 0:
                continue
            inc = self._last_incumbent.get(kf, pose)
            bias, _curve, n_valid = estimate_body_z_bias(scan, inc, grid)
            out["per_frame"].append({"kf": int(kf), "bias_z_m": round(float(bias), 4),
                                     "valid_points": int(n_valid)})
            vals.append(float(bias))
        if vals:
            med = float(np.median(vals))
            out["bias_z_m"] = round(med, 4)
            out["mad_m"] = round(float(np.median(np.abs(np.asarray(vals) - med))), 4)
            out["frames_estimated"] = len(vals)
            out["within_declared_tolerance"] = bool(abs(med - 0.5) <= 0.15)
        return out

    def _publish_repaired_scans(self, ep: "Episode") -> Dict[str, Any]:
        """Republish the episode's frames with the estimated body-z bias removed.

        INJECTION test only. The bias is estimated per frame with the decoupled 1-D search at the
        incumbent pose; the candidate poses are untouched (they come from the host-pose ICP the
        gate accepted). Every frame keeps its own header stamp and full point layout; only x/y/z
        bytes change. The clouds go out before `reprocess` and the caller waits for the host to
        acknowledge receipt, because the command and the topic travel on different paths.
        """
        out: Dict[str, Any] = {"enabled": True, "published": 0, "bias_z_m": None,
                               "missing_clouds": 0, "synced": False, "frames": []}
        if self.publish_repair is None:
            out["reason"] = "no_repair_publisher"
            return out
        est = self._estimate_repair_bias(ep)
        out.update({k: est[k] for k in ("bias_z_m", "mad_m", "frames_estimated",
                                        "per_frame", "reference_points", "tolerance_m",
                                        "expected_bias_m", "within_declared_tolerance")
                    if k in est})
        if est.get("bias_z_m") is None:
            out["reason"] = est.get("reason", "no_bias_estimate")
            return out
        bias = float(est["bias_z_m"])
        # Sham control publishes the same number of clouds with the same receipts and command
        # time, but the cloud is unchanged (shift 0). Comparing it with the repair arm isolates
        # the correction itself from every timing and transport effect.
        shift = 0.0 if self.repair_sham else -bias
        out["sham"] = bool(self.repair_sham)
        out["repair_shift_z_m"] = round(float(shift), 4)
        # The host's repaired-scan subscriber queues 20 (LIVMapper.cpp:320-321). A burst of 26 in
        # one decision dropped six before any callback saw them, so publish in batches and wait for
        # the cumulative receipt after each one. The receipt is the host's own count, not a timer.
        items = []
        for kf, _ts, _pose in ep.frames:
            rec = self._scan_index.get(kf)
            if not rec or rec[1] is None:
                out["missing_clouds"] += 1
                continue
            scan_ns, msg = rec
            # bias is the estimated injected corruption; the repair removes it.
            items.append((int(scan_ns), shift_z_cloud(msg, shift)))
        baseline = self.cp.read_repair_received(timeout_s=1.0)
        out["repair_received_baseline"] = baseline
        base = int(baseline or 0)
        batch_size = 10
        published = 0
        out["batches"] = []
        for start in range(0, len(items), batch_size):
            batch = items[start:start + batch_size]
            for scan_ns, cloud in batch:
                self.publish_repair(cloud)
                out["frames"].append(scan_ns)
            published += len(batch)
            ok = self.cp.wait_for_repair_count(base + published,
                                               timeout_s=self.repair_sync_timeout_s)
            out["batches"].append({"batch": len(out["batches"]) + 1,
                                   "in_batch": len(batch),
                                   "published_total": published,
                                   "received_ok": bool(ok)})
            if not ok:
                # Do not publish the rest and do not replay with a partial repair set.
                out["published"] = int(published)
                out["synced"] = False
                out["failed_after_published"] = int(published)
                out["reason"] = "batch_receipt_timeout"
                return out
        out["published"] = int(published)
        final = self.cp.read_repair_received(timeout_s=self.repair_sync_timeout_s)
        out["final_received"] = final
        out["synced"] = bool(final is not None and final == base + published)
        if not out["synced"]:
            out["reason"] = "receipt_mismatch"
        return out

    def decide(self, now_ts_ns: int, basis: str) -> Optional[Dict[str, Any]]:
        ep = self._open
        if ep is None or ep.decided:
            return None
        # A bag-end decision can reach here without the deadline frame having frozen the set; fix
        # it now. From this point `ep.frames` cannot grow (`_track_episode` guards on `frozen`).
        if not ep.frozen:
            ep.frozen = True
            ep.frozen_frames = list(ep.frames)
            ep.frozen_at_ns = int(ep.frames[-1][1]) if ep.frames else None
        # Three timestamps, so the interval that the five stage timers do not cover can be split
        # into "the main loop took this long to get to the decision" and "decide() spent this long
        # before handing over to evaluate_and_commit_candidate". Recorded, not optimised.
        t_enter = time.time()
        sched_delay_s = (None if self._pending_decision_wall is None
                         else round(t_enter - self._pending_decision_wall, 3))
        ep.decided = True
        keys = [kf for kf, _ts, _p in ep.frames]
        repaired = {kf: pose for kf, _ts, pose in ep.frames}
        ts_by_key = {kf: ts for kf, ts, _p in ep.frames}

        # The incumbent is computed first: the ICP source registers at these independent poses,
        # because a uniform measurement bias is absorbed by the host's own pose and is invisible
        # when the corrupted cloud is placed with that pose.
        incumbent, anchor, extrap_basis = extrapolate_incumbent(
            self.node.tx_mgr.trusted_poses, self.node._kf_timestamps, ts_by_key)
        self._last_incumbent = dict(incumbent)

        icp_detail = None
        if self.candidate_source == "icp_reregistration":
            # A failure while building the candidate must leave a record, not a silent gap: the
            # episode is already marked decided by the time we get here, so an uncaught exception
            # would drop the decision entirely and the stream would show nothing happened.
            try:
                # The candidate stays at the host-pose initialisation: that is the fit the gate
                # accepted. The measurement bias is estimated separately, at the incumbent pose,
                # because a single rigid fit at an 0.8 m-off init does not converge inside the
                # correspondence gate.
                repaired, icp_detail = self._icp_candidate(ep)
                self.icp_details.append({"candidate_id": ep.candidate_id, **icp_detail})
            except BaseException as exc:
                self.decision_errors.append({
                    "candidate_id": ep.candidate_id, "stage": "icp_candidate",
                    "error": f"{type(exc).__name__}: {exc}"})
                repaired = {}          # no candidate; do not silently substitute the host poses
        # The anchor is the last trusted keyframe; its timestamp is what makes the re-entry bound
        # an elapsed-time envelope instead of a bare distance.
        anchor_ts_ns = None
        if self.node.tx_mgr.trusted_poses:
            anchor_key = max(self.node.tx_mgr.trusted_poses.keys())
            anchor_ts_ns = self.node._kf_timestamps.get(anchor_key)

        # How far the segment's end had moved past this episode's deadline when the decision ran.
        # This is the quantity that inflates wait_started_ns, so it is recorded per decision.
        seg = self.node.tx_mgr.active_quarantine
        seg_end = getattr(seg, "t_end_ns", None)
        wait_offset_s = (None if seg_end is None
                         else round((int(seg_end) - int(ep.deadline_ns)) / 1e9, 3))

        version_before = int(self.node.tx_mgr.trusted_version)
        t_before_eval = time.time()
        report = None
        error = None
        try:
            report = self.node.evaluate_and_commit_candidate(
                ep.candidate_id,
                repaired,
                incumbent_poses=incumbent,
                reentry_anchor_pose=anchor,
                reentry_anchor_ts_ns=anchor_ts_ns,
            )
        except BaseException as exc:       # a refused attempt must still be recorded
            error = {"candidate_id": ep.candidate_id, "error": f"{type(exc).__name__}: {exc}"}
            self.decision_errors.append(error)

        t_after_eval = time.time()
        evidence = dict(getattr(self.node, "last_paired_evidence", {}) or {})
        row = candidate_record(
            run_id=self.run_id,
            candidate_id=ep.candidate_id,
            t_trigger_ns=ep.trigger_ts_ns,
            t_decision_ns=int(now_ts_ns),
            report=report,
            evidence=evidence,
            parent_map_version=version_before,
            candidate_source=self.candidate_source,
            pose_first_trigger=ep.pose,
        )
        self.records.append(row)
        self.candidate_details.append(
            candidate_detail_record(ep.candidate_id, ep.trigger_ts_ns, int(now_ts_ns),
                                    keys, ts_by_key, repaired))
        if self._first_decision_ts_ns is None:
            self._first_decision_ts_ns = int(now_ts_ns)
        ep.meta = {                                  # summary-only, never in the stream
            "decision_basis": basis,
            "candidate_frames": len(keys),
            "incumbent_basis": extrap_basis,
            "paired_evidence": evidence,
            "error": error,
            "state_after": getattr(self.node.tx_mgr.state, "value",
                                   self.node.tx_mgr.state),
            "quarantine_still_open": self.node.tx_mgr.active_quarantine is not None,
            "wait_start_offset_s": wait_offset_s,
            "decide_timing_s": {
                "scheduler_delay_s": sched_delay_s,
                "pre_eval_s": round(t_before_eval - t_enter, 3),
                "eval_s": round(t_after_eval - t_before_eval, 3),
                "post_eval_s": round(time.time() - t_after_eval, 3),
            },
        }
        # Native writeback. A refused candidate leaves the host's map holding the frames it was
        # asked to judge, so the host is rolled back to its own checkpoint; an accepted one is
        # re-derived from that checkpoint through the host's own estimator. Both are recorded with
        # the host's ack, because "the command was sent" and "the host did it" are different facts.
        if self.cp is not None:
            # INJECTION measurement repair: publish the corrected clouds before the replay command
            # and wait until the host has queued them. The host applies the command at a frame
            # boundary; the clouds arrive on a ROS topic. Without the receipt check, `reprocess`
            # can run on a queue that is still empty, which is exactly what the previous run
            # recorded (repair_received=0, repairs applied=0).
            proceed, repair = self._repair_gate(ep, row.get("accepted") is True)
            if repair is not None:
                ep.meta["repair_publish"] = repair
            if not proceed:
                # Do not send a replay that cannot see the repaired measurements.
                ep.meta["native_checkpoint_skipped"] = "repair_sync_timeout"
                return row
            # The event object is the one poll() will account for; appending it here as well would
            # list the same command twice.
            # The terminal stamp bounds the host's replay to the frozen candidate's frames, so
            # wall-clock work done after the decision cannot extend the replay window.
            if row.get("accepted") is True:
                action = self.cp.reprocess(ep.frozen_at_ns + REPLAY_END_GRACE_NS)
                ep.meta["native_checkpoint"] = action
                # Wait for the replay ack: it carries replay_suffix, i.e. whether the host's own
                # estimate already ran past the candidate window to the captured boundary. If it
                # did, writing the last candidate pose back would rewind the state by seconds
                # while the map stays at the boundary (the run before this one: 3.9 m / 15 s).
                ack_event = self.cp.collect(timeout_s=90.0)
                if ack_event is not None and ack_event.get("command") != "status":
                    self.cp_actions.append(ack_event)
                import re as _re
                m = _re.search(r"replay_suffix=(\d+)", (ack_event or {}).get("ack", "") or "")
                suffix = int(m.group(1)) if m else None
                ep.meta["replay_suffix"] = suffix
                if suffix is not None and suffix > 0:
                    ep.meta["native_writeback_skipped"] = {"reason": "replay_suffix",
                                                          "replay_suffix": suffix}
                elif ep.frames:
                    # An accepted repair is only accepted if the host continues from it: the last
                    # candidate pose becomes the host's state. Use the same (bias-corrected) pose
                    # the candidate and the repairs used, not the host pose they replace.
                    last_key = ep.frames[-1][0]
                    writeback = self.cp.set_state(repaired.get(last_key, ep.frames[-1][2]))
                    writeback["trigger"] = "accepted_pose"
                    ep.meta["native_writeback"] = writeback
            else:
                ep.meta["native_checkpoint"] = self.cp.restore()
            # The decision is made; the next event needs its own trusted checkpoint.
            self.cp._last_snapshot_wall = time.time()
        return row

    def service(self, backlog_limit: int = 0) -> Optional[Dict[str, Any]]:
        """Perform a decision the callbacks have asked for. Runs on the main thread only."""
        if self.cp is not None:
            # Account for commands written from the callback (the hold) before issuing anything
            # blocking, so one ack is never attributed to the wrong command.
            ack = self.cp.poll()
            while ack is not None:
                if ack.get("command") != "status":
                    self.cp_actions.append(ack)
                ack = self.cp.poll()
            # A snapshot that has not answered in half a second is dropped, not waited on: the
            # decision path runs on this thread and must never queue behind a map copy.
            self.cp.expire_pending(0.5)
            self._apply_lifecycle()
        # The rolling checkpoint is taken here, on the main thread, while no episode is open: a
        # deep copy of the map inside a subscriber callback would delay exactly the frames the
        # pairing depends on.
        if (self.cp is not None and self.node.tx_mgr.active_quarantine is None
                and not self.scripted_trigger_stamps_ns):
            # A scripted run declares its checkpoints at the trigger stamps ahead of time. Rolling
            # snapshots are not just redundant there: one issued before a trigger can be applied
            # after it under backlog and overwrite the armed checkpoint, so the restore then rolls
            # back only part of the segment. Online runs keep the rolling snapshot.
            self.cp.tick(time.time(), quiescent=True)
        if self.cp is not None and self.cp.pending():
            # A command is in flight: no new candidate is built until the host has applied it.
            return None
        if self.pending_decision is None or self._open is None or self._open.decided:
            return None
        if backlog_limit and (len(self.pairer._poses) + len(self.pairer._scans)) > backlog_limit:
            # Let the backlog drain first: a decision made with a queue this deep would be
            # scored against frames the node has not seen yet.
            return None
        basis = self.pending_decision
        self.pending_decision = None
        return self.decide(self._last_ts_ns or self._open.trigger_ts_ns, basis)

    def _apply_lifecycle(self) -> None:
        """Follow the manager's lifecycle: the host may write again when quarantine ends.

        Two events end it, and both look the same to the host: `rearm` after a wait closed
        unresolved (the frames are lost, the map stays at its last commit) and `commit_closed`
        after an accepted repair left nothing pending (the frames are committed). `resume` is
        sent on either; keying only on `rearm` left the accepted path holding the map forever.
        """
        events = getattr(self.node.tx_mgr, "lifecycle_events", None)
        if not events:
            return
        for ev in events[self._lifecycle_seen:]:
            if ev.get("event") in ("rearm", "commit_closed"):
                action = self.cp.resume()
                action["trigger"] = ev.get("event")
        self._lifecycle_seen = len(events)

    def finish(self) -> None:
        """Bag end: decide anything still open, and account for unpaired messages."""
        self.service()
        if self.cp is not None:
            self.cp.stop()
        if self._open is not None and not self._open.decided:
            if self.bag_end_ts_ns is not None:
                self.decide(self.bag_end_ts_ns, "bag_end")
        self.pairer.flush()


# ---------------------------------------------------------------------------------------------
# summaries
# ---------------------------------------------------------------------------------------------
def build_summary(loop: NativeClosedLoop, extra: Dict[str, Any]) -> Dict[str, Any]:
    rows = loop.records
    gate_accept = sum(1 for r in rows if r["accepted"] is True)
    gate_reject = sum(1 for r in rows if r["accepted"] is False)
    null_counts = {k: sum(1 for r in rows if r[k] is None) for k in CANDIDATE_KEYS}
    return {
        "run_id": loop.run_id,
        "candidate_source": loop.candidate_source,
        "detection_enabled": loop.detection_enabled,
        # A7 v2 cleared the gauge dependence: the transported weak direction is no longer
        # re-normalised by a non-Ad-invariant length, and the covariance is carried back to the
        # trigger frame's body basis before it meets a fixed tolerance. Verified locally by
        # slam_recovery/tests/test_a7_tangent_frames.py (18 tests, including a plain translation
        # and a rotated anchor with translation); reproduced by S1. The earlier
        # GAUGE_DEPENDENT_UNTIL_A7_FIX label is obsolete and must not be quoted any more.
        "gate_decision_validity": "A7_V2_GAUGE_CLEARED",
        "gate_decision_caveat": "Gauge dependence was cleared by A7 v2. This statement is about "
                                "the gate's invariance, not about whether a given candidate is "
                                "good: the accept/refuse outcome still needs independent labels "
                                "before it means anything in B10.",
        "protocol": {
            "ingest": "step_frame(kf_id, timestamp_ns, pose_se3=T_wb, scan_body_xyz, nis_value)",
            "pose_convention": "T_wb (body -> world), matching world_points = pts @ R.T + t",
            "decision": "once per quarantine episode, at t_trigger + confirmation_margin_ns, "
                        "or at bag end with decision_basis=bag_end",
            "candidate": "host poses recorded during the quarantine (candidate_source=host_poses)",
            "incumbent": "constant-velocity translation extrapolation from the last "
                         "trusted keyframes, rotation held at the anchor",
            "what_this_proves": "the admission path only -- detect, quarantine, candidate, gate, "
                                "commit or refuse. Not a re-estimating repairer.",
            "pre_registered_expectation": "on this candidate population the archived four-arm "
                                          "already shows the gate refuses; a run whose gate "
                                          "accepts nothing measures the harmful side of B10 and "
                                          "the refusal half of B5, not the benefit side.",
        },
        "parameters": {
            "confirmation_margin_ns": loop.confirmation_margin_ns,
            "pair_window_ns": loop.pairer.dt_ns,
            "scan_cap": loop.scan_cap,
            "nis_radius_m": loop.nis.radius_m,
            "extrap_frames": EXTRAP_FRAMES,
            "sigma_meas_m": float(loop.node.sigma_meas_m),
        },
        "pairing": {**loop.pairer.stats(),
                    "pairing_rule": f"nearest pose within {loop.pairer.dt_ns // 1_000_000} ms, "
                                    f"no pose reused" },
        "pairing_diagnosis": pairing_diagnosis(loop.pairer),
        "nis": {**loop.nis.counts, "nonfinite_estimator_output": loop.nis.nonfinite,
                "sigma_meas_m": float(loop.node.sigma_meas_m)},
        "frames": {
            "paired": loop.pairer.paired,
            "ingested": int(loop.next_kf_id),
            "fed_to_step_frame": loop.frames_fed,
            "ingested_without_detection": loop.ingested_undetected,
            "consumed_after_first_decision": loop.frames_after_first_decision,
            "first_decision_ts_ns": loop._first_decision_ts_ns,
        },
        "quarantine": {
            "episodes": len(loop.episodes),
            "trigger_ts_ns": [ep.trigger_ts_ns for ep in loop.episodes],
            "decisions": len(rows),
            "second_and_later_events": max(0, len(loop.episodes) - 1),
            "episode_detail": [
                {"index": ep.index, "trigger_ts_ns": ep.trigger_ts_ns,
                 "deadline_ns": ep.deadline_ns, "decided": ep.decided,
                 "estimated_onset_ns": ep.estimated_onset_ns,
                 "quarantine_start_ns": ep.quarantine_start_ns,
                 "first_alarm_ts_ns": ep.first_alarm_ts_ns,
                 "frame_freeze": {
                     "frozen": bool(ep.frozen),
                     "frozen_at_ns": ep.frozen_at_ns,
                     "frozen_frames": len(ep.frozen_frames),
                     "frames_after_freeze": int(ep.frames_after_freeze),
                 },
                 "frames_registered": len(ep.frames), **(getattr(ep, "meta", {}) or {})}
                for ep in loop.episodes
            ],
        },
        "warmup": {
            "policy": "a frame the node cannot support against its own spatially sampled trusted "
                      "map is ingested through the manager's healthy path but is NOT judged by "
                      "the detector; it is recorded as detection_status=UNAVAILABLE. In diagnosis "
                      "mode (detection=off) every frame is recorded as DISABLED_FOR_DIAGNOSIS "
                      "and nothing is judged at all.",
            "detection_status_counts": loop.detection_counts,
            "frames_ingested_without_detection": loop.ingested_undetected,
            "first_detected_kf": loop.first_detected_kf,
            "not_an_assumption": "no frame is labelled healthy; UNAVAILABLE says the detector had "
                                 "no reference, which is a statement about the evidence, not "
                                 "about the frame",
        },
        "pose_convention": {
            "declared": "T_wb (body -> world), matching world_points = pts @ R.T + t",
            "one_frame_check": loop.pose_convention_check,
        },
        "gate": {
            "accepted": gate_accept,
            "rejected": gate_reject,
            "errored": len(loop.decision_errors),
            "modes": [r["mode"] for r in rows],
            "committed_key_total": sum(len(r["committed_pose_keys"] or []) for r in rows),
            "deferred_key_total": sum(len(r["deferred_pose_keys"] or []) for r in rows),
        },
        # What happened to a segment that never got evidence. Without a declared wait limit a
        # refused Mode 3 keeps its segment open forever and no second event can ever fire; with
        # one, the segment closes as unresolved and the run re-arms. Both the close and the lost
        # frames are recorded here, so "the run continued" cannot hide dropped input.
        "lifecycle": {
            "wait_limit_ns": loop.node.tx_mgr.wait_limit_ns,
            "state": getattr(loop.node.tx_mgr.state, "value", loop.node.tx_mgr.state),
            "events": list(loop.node.tx_mgr.lifecycle_events),
            "unresolved_segments": len(loop.node.tx_mgr.unresolved_segments),
            # The host side of the same lifecycle: when its map was held and when it was released.
            # A re-arm the host never heard would otherwise look like a re-arm that happened.
            "native_checkpoint_actions": loop.cp_actions,
        },
        # The label has to describe what actually happened, not what was asked for. A run that
        # declared scripted triggers and fired none is an online run, and saying otherwise would
        # let a detector-driven result be quoted as a controlled one.
        "run_mode": (
            "CONTROLLED_INTERFACE_TEST"
            if (loop.scripted_triggers_s or loop.scripted_trigger_stamps_ns)
            and len(loop.scripted_fired) == (len(loop.scripted_triggers_s)
                                             + len(loop.scripted_trigger_stamps_ns))
            else "CONTROLLED_TRIGGERS_NOT_FIRED"
            if (loop.scripted_triggers_s or loop.scripted_trigger_stamps_ns)
            else "ONLINE_DETECTION"),
        "scripted_triggers": {
            "declared_s": list(loop.scripted_triggers_s),
            "declared_ns": list(loop.scripted_trigger_stamps_ns),
            "fired": loop.scripted_fired,
            "note": ("the segment was opened by calling trigger_quarantine directly at a declared "
                     "time; no detector output and no fault label was used, so this run says "
                     "nothing about detection performance"),
        },
        "native_checkpoint": (loop.cp.status() if loop.cp is not None
                              else {"enabled": False, "note": "no checkpoint directory was given"}),
        "native_checkpoint_actions": loop.cp_actions,
        "null_field_counts": null_counts,
        "holdout_nis_nonfinite": sum(1 for r in rows if r["holdout_nis"] is None)
        if rows else 0,
        "decision_errors": loop.decision_errors,
        "candidate_source_detail": {
            "candidate_source": loop.candidate_source,
            "icp_seconds_total": loop.icp_seconds_total,
            "icp_candidates": len(loop.icp_details),
            "note": "the frozen 18-key stream stays at 18 keys; the ICP fields are written to "
                    "icp_detail.jsonl and repeated here, because adding keys to some rows would "
                    "break every consumer that parses by key",
            "details": loop.icp_details,
        },
        # The frame set and poses behind `info_after`, one row per decision, in
        # candidates_detail.jsonl. Without them a producer change cannot be re-derived offline.
        "candidate_detail_rows": len(loop.candidate_details),
        "nis_vs_map_size": nis_vs_map_size(loop.diag),
        "frame_diagnostics": loop.diag,
        "final_state": getattr(loop.node.tx_mgr.state, "value", loop.node.tx_mgr.state),
        "quarantine_open_at_exit": loop.node.tx_mgr.active_quarantine is not None,
        "trusted_keyframes_at_exit": len(loop.node.tx_mgr.trusted_poses),
        **extra,
    }


def simulate_pairing(pose_stamps: List[int], scan_stamps: List[int], dt_ns: int) -> Dict[str, Any]:
    """Re-run the same front-of-queue matcher at a different window, from the logged stamps.

    Lets a report say what the window change bought without another run. The stamps are logged in
    arrival order, which is the order the live matcher saw.
    """
    poses, scans = list(pose_stamps), list(scan_stamps)
    i = j = paired = 0
    max_dt = 0
    while i < len(poses) and j < len(scans):
        dt = poses[i] - scans[j]
        if abs(dt) <= dt_ns:
            paired += 1
            max_dt = max(max_dt, abs(dt))
            i += 1
            j += 1
        elif dt < 0:
            i += 1
        else:
            j += 1
    return {"window_ns": int(dt_ns), "paired": paired,
            "fraction_of_scans": (paired / len(scans)) if scans else None,
            "fraction_of_poses": (paired / len(poses)) if poses else None,
            "max_abs_dt_ns": int(max_dt)}


def nis_vs_map_size(diag: List[Dict[str, Any]]) -> Dict[str, Any]:
    """NIS distribution as a function of how much map the reference held.

    This is the curve the start condition has to be read off. It is computed from the recorded
    frames only -- no extra run, and no selection of "the segment that looked best": every frame
    with a computed node-map NIS enters exactly one bin.
    """
    bins = [(1, 2), (3, 5), (6, 10), (11, 20), (21, 50), (51, 100), (101, 10 ** 9)]
    rows = [d for d in diag if d.get("nis") is not None and d.get("nis_reference") == "node_map"]
    out: Dict[str, Any] = {
        "frames_with_node_map_nis": len(rows),
        "bins_are_half_open": "lo <= k <= hi inclusive at both ends",
        "by_trusted_keyframes": [], "by_map_points": [],
    }

    def _bin(field, lo_attr, hi_attr, bucket):
        sel = [d["nis"] for d in rows if lo_attr <= d[field] <= hi_attr]
        if not sel:
            return None
        sel.sort()
        n = len(sel)
        # Linear interpolation, so a two-sample bin reports a median between its samples instead
        # of whichever sample happens to sit at index n//2 (which also produced a p90 below the
        # median for n < 3).
        return {"lo": lo_attr, "hi": (None if hi_attr >= 10 ** 9 else hi_attr), "n": n,
                "min": float(sel[0]),
                "median": float(np.percentile(sel, 50)),
                "p90": float(np.percentile(sel, 90)),
                "max": float(sel[-1])}

    for lo, hi in bins:
        r = _bin("trusted_keyframes", lo, hi, "kf")
        if r:
            out["by_trusted_keyframes"].append(r)
    for lo, hi in ((1, 50), (51, 100), (101, 200), (201, 500), (501, 1000),
                   (1001, 2000), (2001, 5000), (5001, 10 ** 9)):
        r = _bin("map_points", lo, hi, "pts")
        if r:
            out["by_map_points"].append(r)
    return out


def pairing_diagnosis(pairer: FramePairer) -> Dict[str, Any]:
    """How far each scan's nearest pose in *time* was, over the stamps actually received.

    The streaming matcher only pairs inside its window, so a low pairing rate is either "the two
    streams are offset" or "the window is too tight" -- and those need different fixes. This
    answers which, from the received stamps alone, without another run.
    """
    pose = np.asarray(pairer.pose_stamps_ns, dtype=np.int64)
    scan = np.asarray(pairer.scan_stamps_ns, dtype=np.int64)
    out: Dict[str, Any] = {
        "pose_stamps_logged": int(len(pose)), "scan_stamps_logged": int(len(scan)),
        "stamp_log_cap": int(pairer.stamp_log_cap),
        "truncated": bool(len(pose) >= pairer.stamp_log_cap
                          or len(scan) >= pairer.stamp_log_cap),
    }
    if len(pose) < 2 or len(scan) < 1:
        return out
    order = np.argsort(pose)
    pose_sorted = pose[order]
    idx = np.clip(np.searchsorted(pose_sorted, scan), 1, len(pose_sorted) - 1)
    lo, hi = pose_sorted[idx - 1], pose_sorted[idx]
    nearest = np.where(np.abs(scan - lo) <= np.abs(hi - scan), lo, hi)
    dt = (nearest - scan).astype(np.float64) / 1e6        # ms
    out.update({
        "nearest_pose_dt_ms": {
            "min": float(dt.min()), "median": float(np.median(dt)),
            "mean": float(dt.mean()), "max": float(dt.max()),
            "p10": float(np.percentile(dt, 10)), "p90": float(np.percentile(dt, 90)),
        },
        "fraction_within_window": float(np.mean(np.abs(dt) * 1e6 <= pairer.dt_ns)),
        "nearest_pose_dt_ms_p10_median_p90": [float(np.percentile(dt, 10)), float(np.median(dt)),
                                              float(np.percentile(dt, 90))],
        "same_matcher_at_20_and_40_ms": {
            f"{w // 1_000_000}ms": simulate_pairing(pairer.pose_stamps_ns, pairer.scan_stamps_ns, w)
            for w in (20_000_000, 40_000_000)},
        "comparability": "the offline arms pair at 20 ms; a run at 40 ms is a different pairing "
                         "and must not be pooled with them in one table",
        "pose_interarrival_ms": {
            "median": float(np.median(np.diff(pose_sorted)) / 1e6),
            "min": float(np.diff(pose_sorted).min() / 1e6),
        },
        "scan_interarrival_ms": {
            "median": float(np.median(np.diff(np.sort(scan))) / 1e6) if len(scan) > 1 else None,
        },
    })
    return out


def peak_rss_kb() -> Optional[int]:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1])
    except OSError:
        return None
    return None


# ---------------------------------------------------------------------------------------------
# ROS driver
# ---------------------------------------------------------------------------------------------
def cloud_to_xyz(msg) -> np.ndarray:
    """Fast PointCloud2 -> (N, 3) float64, honouring per-field offsets and endianness."""
    by_name = {f.name: f for f in msg.fields}
    if not {"x", "y", "z"} <= set(by_name):
        raise ValueError(f"point cloud lacks x/y/z fields: {sorted(by_name)}")
    for name in ("x", "y", "z"):
        if by_name[name].count != 1:
            raise ValueError(f"field {name} has count {by_name[name].count}, expected 1")
        if by_name[name].datatype not in _POINT_FIELD_DTYPE:
            raise ValueError(f"field {name} has unsupported datatype {by_name[name].datatype}")
    endian = ">" if getattr(msg, "is_bigendian", False) else "<"
    dt = np.dtype({
        "names": ["x", "y", "z"],
        "formats": [endian + _POINT_FIELD_DTYPE[by_name[n].datatype] for n in ("x", "y", "z")],
        "offsets": [by_name[n].offset for n in ("x", "y", "z")],
        "itemsize": int(msg.point_step),
    })
    n = int(msg.width) * int(msg.height)
    arr = np.frombuffer(msg.data, dtype=dt, count=n)
    out = np.column_stack([arr["x"], arr["y"], arr["z"]]).astype(np.float64)
    return out[np.isfinite(out).all(axis=1)]


def arm_scripted_checkpoints(cp, stamps, margin_ns: int = 0) -> None:
    """Queue hold+snapshot at each declared stamp minus the confirmation margin.

    The manager's quarantine starts at ``estimated_onset - confirmation_margin``, so the checkpoint
    and the map hold belong at that boundary, not at the trigger itself: frames in the confirmation
    window are already part of the segment and must not be folded into the trusted map.
    """
    for stamp in sorted(int(s) for s in stamps):
        at = int(stamp) - int(margin_ns)
        cp.hold(at)
        cp.snapshot_now(at)


class RosDriver:
    def __init__(self, loop: NativeClosedLoop, pose_topic: str, scan_topic: str,
                 status_topic: str) -> None:
        import rospy
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import PointCloud2
        from std_msgs.msg import String

        self._rospy = rospy
        self.loop = loop
        self.errors: List[Dict[str, Any]] = []
        self.pose_count = 0
        self.scan_count = 0
        self._published = 0
        self._pub = rospy.Publisher(status_topic, String, queue_size=20)
        self._sub_pose = rospy.Subscriber(pose_topic, Odometry, self._on_pose, queue_size=200)
        self._sub_scan = rospy.Subscriber(scan_topic, PointCloud2, self._on_scan, queue_size=20)
        # INJECTION measurement repair: the corrected clouds go to the host's existing channel.
        # The publisher lives here because the node owns the trusted map the correction came from;
        # a separate process would have no reference to repair against.
        self._pub_repair = None
        if loop.repair_publish_enabled:
            self._pub_repair = rospy.Publisher("/native_recovery/repaired_scan", PointCloud2,
                                               queue_size=200)
            loop.publish_repair = self._pub_repair.publish
        rospy.loginfo("[slam_recovery] listening on %s and %s (repair publisher: %s)",
                      pose_topic, scan_topic, "on" if self._pub_repair else "off")

    @staticmethod
    def _stamp_ns(stamp) -> int:
        return int(stamp.secs) * 10**9 + int(stamp.nsecs)

    def _on_pose(self, msg) -> None:
        self.pose_count += 1
        ns = self._stamp_ns(msg.header.stamp)
        p = msg.pose.pose
        try:
            T = pose_to_matrix((p.position.x, p.position.y, p.position.z),
                               (p.orientation.x, p.orientation.y, p.orientation.z,
                                p.orientation.w))
        except Exception as exc:                       # never let one bad message kill the loop
            self.errors.append({"topic": "pose", "stamp_ns": ns,
                                "error": f"{type(exc).__name__}: {exc}"})
            return
        for pose_ns, scan_ns, pose, scan in self.loop.pairer.add_pose(ns, T):
            self._dispatch(pose_ns, pose, scan, scan_ns)

    def _on_scan(self, msg) -> None:
        self.scan_count += 1
        ns = self._stamp_ns(msg.header.stamp)
        try:
            xyz = subsample(cloud_to_xyz(msg), self.loop.scan_cap)
        except Exception as exc:
            self.errors.append({"topic": "scan", "stamp_ns": ns,
                                "error": f"{type(exc).__name__}: {exc}"})
            return
        if len(xyz) == 0:
            self.errors.append({"topic": "scan", "stamp_ns": ns, "error": "empty_cloud"})
            return
        # Keep the message itself: the repair channel republishes the original point layout.
        self.loop._scan_msgs[ns] = msg
        if len(self.loop._scan_msgs) > 512:
            for stale in list(self.loop._scan_msgs)[:128]:
                self.loop._scan_msgs.pop(stale, None)
        for pose_ns, scan_ns, pose, scan in self.loop.pairer.add_scan(ns, xyz):
            self._dispatch(pose_ns, pose, scan, scan_ns)

    def _dispatch(self, pose_ns: int, pose: np.ndarray, scan: np.ndarray,
                  scan_ns: Optional[int] = None) -> None:
        try:
            self.loop.on_pair(pose_ns, pose, scan, scan_ns)
        except Exception as exc:                       # recorded, never swallowed
            self.errors.append({"stage": "on_pair", "stamp_ns": int(pose_ns),
                                "error": f"{type(exc).__name__}: {exc}"})
        if self.loop.records and len(self.loop.records) != self._published:
            self._publish_status()

    def _publish_status(self) -> None:
        from std_msgs.msg import String
        row = self.loop.records[-1]
        self._published = len(self.loop.records)
        payload = json.dumps({k: row[k] for k in
                              ("candidate_id", "t_trigger_ns", "t_decision_ns", "mode",
                               "accepted", "refusal_reason", "committed_pose_keys",
                               "deferred_pose_keys")})
        self._pub.publish(String(data=payload))


# ---------------------------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------------------------
def _write_json(path: str, payload) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=False, default=float)
    os.replace(tmp, path)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--pose-topic", default="/aft_mapped_to_init")
    ap.add_argument("--scan-topic", default="/velodyne_points")
    ap.add_argument("--status-topic", default="/slam_recovery/gate_status")
    ap.add_argument("--candidate-source", default="host_poses",
                    choices=("host_poses", "icp_reregistration"))
    ap.add_argument("--confirmation-margin-sec", type=float, default=2.0)
    ap.add_argument("--pair-dt-ms", type=float, default=PAIR_DT_NS / 1e6)
    ap.add_argument("--scan-cap", type=int, default=SCAN_CAP)
    ap.add_argument("--sigma-meas-m", type=float, default=0.12,
                    help="the node's own noise scale; recorded, never re-derived here")
    ap.add_argument("--duration-sec", type=float, default=0.0,
                    help="stop after this many seconds of wall time (0 = run until shutdown)")
    ap.add_argument("--max-pairs", type=int, default=0,
                    help="stop after this many paired frames (0 = no limit); wiring checks use it")
    ap.add_argument("--icp-time-budget-sec", type=float, default=0.0,
                    help="0 = no limit; a hit budget is recorded, never silent")
    ap.add_argument("--detection", default="on", choices=("on", "off"),
                    help="off = diagnosis only: the map grows and the NIS is recorded, "
                         "but nothing is judged")
    ap.add_argument("--scripted-triggers", default="",
                    help="CONTROLLED_INTERFACE_TEST only: comma-separated seconds from the first "
                         "frame at which the loop opens a quarantine through trigger_quarantine, "
                         "without the detector. Empty = the detector decides, as in every other run")
    ap.add_argument("--scripted-trigger-stamps", default="",
                    help="CONTROLLED_INTERFACE_TEST only: comma-separated absolute pose stamps "
                         "(ns). Fires on the first frame at or after each stamp. Unlike seconds "
                         "from the first frame this names the same frame across runs, which a "
                         "controlled test needs when the gate's answer differs between "
                         "neighbouring scans")
    ap.add_argument("--checkpoint-dir", default="",
                    help="directory shared with the host's native checkpoint poll; empty = the "
                         "host is not asked to snapshot or restore anything")
    ap.add_argument("--checkpoint-period-sec", type=float, default=2.0,
                    help="how often a rolling snapshot is taken while no segment is open; this "
                         "is also the worst-case age of the trusted checkpoint at a trigger")
    ap.add_argument("--wait-limit-sec", type=float, default=0.0,
                    help="close a Mode 3 wait as unresolved after this many seconds without "
                         "evidence and re-arm (0 = wait indefinitely, which means a refused "
                         "first event can never be followed by a second one)")
    ap.add_argument("--repair-publish", action="store_true", default=False,
                    help="INJECTION test only: on an accepted candidate, republish its frames on "
                         "/native_recovery/repaired_scan with the estimated body-z bias removed, "
                         "then wait for the host's repair_received receipt before reprocess")
    ap.add_argument("--repair-sync-timeout-sec", type=float, default=5.0,
                    help="how long to wait for repair_received to reach the published count; on "
                         "timeout the replay is not sent")
    ap.add_argument("--repair-dry-run", action="store_true", default=False,
                    help="control for the INJECTION test: run the same bias estimation (same "
                         "decision cost) but publish nothing; the replay uses the original scans")
    ap.add_argument("--availability-log", default="",
                    help="write one JSON line per paired frame to this path: the support mask "
                         "evaluation and the NIS branch that decided whether the frame was fed to "
                         "the detector. No cap, no change to the decision")
    ap.add_argument("--repair-sham", action="store_true", default=False,
                    help="sham control: publish the same number of clouds with the same batching "
                         "and receipts, but unchanged (zero shift); isolates the correction")
    args, _unknown = ap.parse_known_args(argv)

    import rospy
    rospy.init_node("slam_recovery_native_loop", anonymous=False, disable_signals=False)

    node = OnlineRecoveryTransactionNode(
        confirmation_margin_sec=args.confirmation_margin_sec,
        sigma_meas_m=args.sigma_meas_m,
        wait_limit_sec=(args.wait_limit_sec if args.wait_limit_sec > 0 else None),
    )
    run_id = os.path.basename(os.path.normpath(args.run_dir))
    loop = NativeClosedLoop(
        node,
        run_id=run_id,
        candidate_source=args.candidate_source,
        confirmation_margin_ns=int(args.confirmation_margin_sec * 1e9),
        pair_dt_ns=int(args.pair_dt_ms * 1e6),
        scan_cap=args.scan_cap,
        detection_enabled=(args.detection == "on"),
        icp_time_budget_s=args.icp_time_budget_sec,
        checkpoint_client=(
            CheckpointClient(args.checkpoint_dir, snapshot_period_s=args.checkpoint_period_sec)
            if args.checkpoint_dir else None),
        repair_publish=args.repair_publish,
        repair_sync_timeout_s=args.repair_sync_timeout_sec,
        repair_dry_run=args.repair_dry_run,
        repair_sham=args.repair_sham,
        availability_log=(args.availability_log or None),
    )
    if args.scripted_triggers:
        loop.scripted_triggers_s = [float(x) for x in args.scripted_triggers.split(",") if x.strip()]
        loop._scripted_done = [False] * len(loop.scripted_triggers_s)
    if args.scripted_trigger_stamps:
        loop.scripted_trigger_stamps_ns = [int(x) for x in args.scripted_trigger_stamps.split(",")
                                           if x.strip()]
        loop._scripted_done_ns = [False] * len(loop.scripted_trigger_stamps_ns)
    # Declare the checkpoint and capture start at the first scripted trigger stamp, ahead of time.
    # A command sent when the trigger fires is applied at the host's next processed frame, which
    # lags the trigger under a playback backlog; a stamped command is queued now and executed by
    # the host just before the first group whose lio_time reaches the trigger. Only scripted runs
    # get this; the online path keeps the immediate behaviour.
    if loop.cp is not None and loop.scripted_trigger_stamps_ns:
        # Every scripted stamp gets its own armed hold/snapshot. The first one was enough while
        # the run had a single event; a second event otherwise falls back to a rolling checkpoint
        # that can be applied after its trigger and roll back only part of the segment.
        arm_scripted_checkpoints(loop.cp, loop.scripted_trigger_stamps_ns,
                                 loop.confirmation_margin_ns)
    driver = RosDriver(loop, args.pose_topic, args.scan_topic, args.status_topic)

    started = time.time()
    rate = rospy.Rate(2.0)
    try:
        while not rospy.is_shutdown():
            rate.sleep()
            loop.service()
            if args.duration_sec and (time.time() - started) >= args.duration_sec:
                break
            if args.max_pairs and loop.pairer.paired >= args.max_pairs:
                break
    except rospy.ROSInterruptException:
        # SIGINT is a normal end of run: the records still have to reach disk.
        pass

    loop.finish()
    summary = build_summary(loop, {
        "runtime": {
            "wall_sec": round(time.time() - started, 3),
            "pid": os.getpid(),
            "pgid": os.getpgid(0),
            "peak_rss_kb": peak_rss_kb(),
            "pose_messages": driver.pose_count,
            "scan_messages": driver.scan_count,
            "callback_errors": driver.errors[:50],
            "callback_error_count": len(driver.errors),
        },
        "launch_args": vars(args),
    })
    os.makedirs(args.run_dir, exist_ok=True)
    _write_json(os.path.join(args.run_dir, "run_summary.json"), summary)
    with open(os.path.join(args.run_dir, "candidates.jsonl"), "w", encoding="utf-8") as fh:
        for row in loop.records:
            fh.write(json.dumps({k: row[k] for k in CANDIDATE_KEYS}, default=float) + "\n")
    if loop.icp_details:
        # One row per candidate. Segment registration produces one fit for the whole segment, so
        # there is no per-frame table; the row is the fit itself plus the frames it applied to.
        with open(os.path.join(args.run_dir, "icp_detail.jsonl"), "w", encoding="utf-8") as fh:
            for det in loop.icp_details:
                fh.write(json.dumps(det, default=float) + "\n")
    if loop.candidate_details:
        # The frame set and poses that produced `after`, so a later producer change can be
        # re-derived from this run instead of from an invented frame set.
        with open(os.path.join(args.run_dir, "candidates_detail.jsonl"), "w",
                  encoding="utf-8") as fh:
            for det in loop.candidate_details:
                fh.write(json.dumps(det, default=float) + "\n")
    rospy.loginfo("[slam_recovery] wrote %d candidate rows to %s", len(loop.records),
                  args.run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
