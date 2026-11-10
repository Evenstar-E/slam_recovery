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
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from slam_recovery.core import BackendDelta, RecoveryState
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
        self._support_cache: Optional[np.ndarray] = None
        self._support_key: Optional[tuple] = None
        self._last_refresh_ns: Optional[int] = None
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
            self.refresh_count += 1
        return (self._support_cache if self._support_cache is not None
                else np.zeros((0, 3), dtype=np.float64))

    def _reference(self, pose: np.ndarray, now_ts_ns: Optional[int] = None
                   ) -> Tuple[Optional[np.ndarray], str]:
        trusted = self.support_reference(now_ts_ns)
        if len(trusted) >= self.min_train:
            d = np.linalg.norm(trusted - pose[:3, 3], axis=1)
            near = trusted[d <= self.radius_m]
            if len(near) >= self.min_train:
                return near, "node_map"
        if self._prev_world is not None and len(self._prev_world) >= self.min_train:
            return self._prev_world, "prev_scan"
        return None, "none"

    def measure(self, pose: np.ndarray, scan_body: np.ndarray,
                now_ts_ns: Optional[int] = None) -> Tuple[Optional[float], str, str]:
        """Return ``(value, source, reference)``. ``value`` is None only when nothing is available."""
        # Transform first, then resolve the reference: the fallback reference is the *previous*
        # frame's cloud, so it must be read before this frame replaces it.
        world = (np.asarray(scan_body, dtype=np.float64)[:, :3] @ pose[:3, :3].T) + pose[:3, 3]
        ref, ref_name = self._reference(pose, now_ts_ns)
        value: Optional[float] = None
        if ref is not None and len(world) >= self.min_holdout:
            v = float(compute_disjoint_holdout_point_to_plane_nis(
                ref, world, delta_pose_se3=np.eye(4), sigma_meas_m=self.node.sigma_meas_m))
            if math.isfinite(v):
                value = v
            else:
                self.nonfinite += 1
        if value is not None:
            self._prev_world = world
            self._last_value = value
            self.counts["computed"] += 1
            self.counts[f"reference_{ref_name}"] += 1
            return value, "computed", ref_name
        if self._last_value is not None:
            self._prev_world = world
            self.counts["carried_forward"] += 1
            self.counts["reference_none"] += 1
            return self._last_value, "carried_forward", "none"
        # No measurement was possible. The frame can still serve as the next frame's reference:
        # it is a real observation, just not one this estimator could score.
        if len(world) >= self.min_holdout:
            self._prev_world = world
        self.counts["unavailable"] += 1
        self.counts["reference_none"] += 1
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
        self.decided = False
        self.candidate_id = f"cand_{index:04d}"


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
    ) -> None:
        self.node = node
        self.run_id = run_id
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

    def on_pair(self, pose_stamp_ns: int, pose: np.ndarray, scan_body: np.ndarray) -> None:
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

        value, source, reference = self.nis.measure(pose, scan_body, now_ts_ns=ts_ns)
        support_ref = self.nis.support_reference(ts_ns)
        # Map size as it stood when this frame's NIS was computed -- not after this frame has been
        # ingested. The diagnostic bins NIS by reference size, so the two must be the same instant.
        kfs_before = int(len(self.node.tx_mgr.trusted_poses))
        pts_before = int(len(support_ref))

        if not self.detection_enabled:
            # Diagnosis mode: the map grows, the NIS is computed and recorded, and nothing is
            # judged. This is how the NIS-versus-map-size curve is obtained without a threshold.
            status = "DISABLED_FOR_DIAGNOSIS"
            self.detection_counts[status] += 1
            self._ingest_without_detection(kf_id, ts_ns, pose, scan_body, value)
            self._record_diag(kf_id, ts_ns, value, source, reference, status,
                              kfs_before, pts_before)
            return

        supported = self.node._frame_has_reference_support(
            kf_id, support_ref, {kf_id: np.asarray(pose, dtype=np.float64)})
        # Detection is available only when the frame can actually be scored against an independent
        # reference. "Unsupported" and "healthy" are different statements and are recorded as such:
        # an unsupported frame is ingested so the map can grow, but the detector does not judge it.
        available = bool(supported) and value is not None
        status = "AVAILABLE" if available else "UNAVAILABLE"
        self.detection_counts[status] += 1

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
        if before is None and after is not None:
            self._open_episode(ts_ns, pose, after)
        if self._open is not None and not self._open.decided:
            self._open.frames.append((kf_id, ts_ns, np.asarray(pose, dtype=np.float64).copy()))
            if ts_ns >= self._open.deadline_ns:
                self.decide(ts_ns, "confirmation_margin")

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

    # -- decision -----------------------------------------------------------------------------
    def decide(self, now_ts_ns: int, basis: str) -> Optional[Dict[str, Any]]:
        ep = self._open
        if ep is None or ep.decided:
            return None
        ep.decided = True
        keys = [kf for kf, _ts, _p in ep.frames]
        repaired = {kf: pose for kf, _ts, pose in ep.frames}
        ts_by_key = {kf: ts for kf, ts, _p in ep.frames}

        incumbent, anchor, extrap_basis = extrapolate_incumbent(
            self.node.tx_mgr.trusted_poses, self.node._kf_timestamps, ts_by_key)

        version_before = int(self.node.tx_mgr.trusted_version)
        report = None
        error = None
        try:
            report = self.node.evaluate_and_commit_candidate(
                ep.candidate_id,
                repaired,
                incumbent_poses=incumbent,
                reentry_anchor_pose=anchor,
            )
        except BaseException as exc:       # a refused attempt must still be recorded
            error = {"candidate_id": ep.candidate_id, "error": f"{type(exc).__name__}: {exc}"}
            self.decision_errors.append(error)

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
        }
        return row

    def finish(self) -> None:
        """Bag end: decide anything still open, and account for unpaired messages."""
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
        # A7 (review): the gate's mode depends on the world origin, because the transported weak
        # direction is re-normalised by a length that is not Ad-invariant and because the
        # covariance norm is compared against a fixed tolerance although the spectral norm is not
        # translation invariant. Until that is fixed, a decision from this run says what the gate
        # did, not what the gate is worth -- so every record carries the caveat.
        "gate_decision_validity": "GAUGE_DEPENDENT_UNTIL_A7_FIX",
        "gate_decision_caveat": "A7 is unaccepted: the same physical scene changes Mode when the "
                                "world origin changes. Do not use these accept/refuse outcomes to "
                                "compare against the offline A3 arm, and do not feed them into the "
                                "B10 four-strategy table or the B5 confusion matrix.",
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
        "null_field_counts": null_counts,
        "holdout_nis_nonfinite": sum(1 for r in rows if r["holdout_nis"] is None)
        if rows else 0,
        "decision_errors": loop.decision_errors,
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
        rospy.loginfo("[slam_recovery] listening on %s and %s", pose_topic, scan_topic)

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
        for pose_ns, _scan_ns, pose, scan in self.loop.pairer.add_pose(ns, T):
            self._dispatch(pose_ns, pose, scan)

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
        for pose_ns, _scan_ns, pose, scan in self.loop.pairer.add_scan(ns, xyz):
            self._dispatch(pose_ns, pose, scan)

    def _dispatch(self, pose_ns: int, pose: np.ndarray, scan: np.ndarray) -> None:
        try:
            self.loop.on_pair(pose_ns, pose, scan)
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
    ap.add_argument("--detection", default="on", choices=("on", "off"),
                    help="off = diagnosis only: the map grows and the NIS is recorded, "
                         "but nothing is judged")
    args, _unknown = ap.parse_known_args(argv)

    import rospy
    rospy.init_node("slam_recovery_native_loop", anonymous=False, disable_signals=False)

    node = OnlineRecoveryTransactionNode(
        confirmation_margin_sec=args.confirmation_margin_sec,
        sigma_meas_m=args.sigma_meas_m,
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
    )
    driver = RosDriver(loop, args.pose_topic, args.scan_topic, args.status_topic)

    started = time.time()
    rate = rospy.Rate(2.0)
    try:
        while not rospy.is_shutdown():
            rate.sleep()
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
    rospy.loginfo("[slam_recovery] wrote %d candidate rows to %s", len(loop.records),
                  args.run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
