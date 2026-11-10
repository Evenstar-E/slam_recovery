"""Unit tests for the native closed loop's pure parts -- no ROS master required.

The loop's job is orchestration: pair, feed, notice a quarantine, decide once, record. Those are
testable without a master, and testing them here is what keeps a wiring check from being the first
time the code runs.
"""

from __future__ import annotations

import json
import math
import types

import numpy as np
import pytest

from slam_recovery.core import RecoveryState
from slam_recovery.ros.recovery_node import (
    CANDIDATE_KEYS,
    FramePairer,
    LiveNis,
    NativeClosedLoop,
    build_summary,
    candidate_record,
    cloud_to_xyz,
    extrapolate_incumbent,
    nis_vs_map_size,
    pose_to_matrix,
    quat_to_rot,
    subsample,
)


# ---------------------------------------------------------------------------------------------
# pairing
# ---------------------------------------------------------------------------------------------
def test_pair_exact_and_within_window():
    p = FramePairer(dt_ns=20_000_000)
    assert p.add_pose(1_000_000_000, "P0") == []
    out = p.add_scan(1_010_000_000, "S0")
    assert out == [(1_000_000_000, 1_010_000_000, "P0", "S0")]
    assert p.paired == 1
    assert p.max_abs_dt_ns == 10_000_000


def test_pair_is_one_to_one_and_pairs_nearest_available():
    p = FramePairer(dt_ns=20_000_000)
    p.add_pose(0, "P0")
    p.add_pose(100_000_000, "P1")
    out = p.add_scan(95_000_000, "S0")          # 5 ms from P1, 95 ms from P0
    assert out == [(100_000_000, 95_000_000, "P1", "S0")]
    assert p.poses_unpaired == 1                # P0 can never match anything now
    out2 = p.add_scan(99_000_000, "S1")
    assert out2 == []


def test_stale_message_is_dropped_not_held():
    p = FramePairer(dt_ns=20_000_000)
    p.add_scan(0, "S0")
    p.add_pose(1_000_000_000, "P0")             # 1 s later: S0 is unusable
    assert p.scans_unpaired == 1
    assert p.paired == 0
    assert p.max_backlog >= 1


def test_flush_accounts_for_held_messages():
    p = FramePairer()
    p.add_pose(0, "P0")
    p.add_scan(500_000_000, "S0")
    p.flush()
    assert p.poses_unpaired + p.scans_unpaired >= 1
    assert p.paired == 0


def test_pairing_stats_expose_rates_not_just_counts():
    p = FramePairer(dt_ns=20_000_000)
    for i in range(4):
        p.add_pose(i * 100_000_000, f"P{i}")
        p.add_scan(i * 100_000_000 + 1_000_000, f"S{i}")
    s = p.stats()
    assert s["paired"] == 4
    assert s["paired_fraction_of_poses"] == 1.0
    assert s["max_abs_dt_ns"] == 1_000_000


# ---------------------------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------------------------
def test_quat_identity_and_quarter_turn():
    assert np.allclose(quat_to_rot(0, 0, 0, 1), np.eye(3))
    half = math.sqrt(0.5)
    R = quat_to_rot(0, 0, half, half)          # 90 deg about z
    assert np.allclose(R @ np.array([1.0, 0, 0]), np.array([0.0, 1.0, 0]), atol=1e-12)


def test_pose_to_matrix_is_t_wb_layout():
    T = pose_to_matrix((1, 2, 3), (0, 0, 0, 1))
    assert np.allclose(T[:3, 3], [1, 2, 3])
    assert np.allclose(T[3], [0, 0, 0, 1])
    # body points map to world as pts @ R.T + t, the convention used by the offline arms
    pts = np.array([[1.0, 0, 0]])
    world = pts @ T[:3, :3].T + T[:3, 3]
    assert np.allclose(world, [[2, 2, 3]])


def test_subsample_is_capped_and_stride_uniform():
    pts = np.arange(1000, dtype=float).reshape(-1, 1)
    out = subsample(pts, 100)
    assert len(out) <= 100
    assert out[0, 0] == 0.0


def test_extrapolate_holds_rotation_and_uses_tail_velocity():
    poses = {}
    for i, x in enumerate((0.0, 1.0, 2.0, 3.0)):
        T = np.eye(4)
        T[:3, 3] = [x, 0, 0]
        T[0, 0] = -1.0                     # a non-identity rotation that must be carried, not moved
        poses[i] = T
    ts = {i: i * 1_000_000_000 for i in range(4)}
    query = {10: 5_000_000_000}
    out, anchor, basis = extrapolate_incumbent(poses, ts, query, tail_frames=3)
    assert basis["status"] == "CONSTANT_VELOCITY"
    assert np.allclose(out[10][:3, 3], [5.0, 0, 0])     # 1 m/s from x=3 at t=3 -> x=5 at t=5
    assert np.allclose(anchor[:3, 3], [3, 0, 0])
    assert out[10][0, 0] == -1.0                        # rotation held


def test_extrapolate_without_trusted_frames_reports_it():
    out, anchor, basis = extrapolate_incumbent({}, {}, {0: 1})
    assert out == {} and anchor is None
    assert basis["status"] == "NO_TRUSTED_KEYFRAME"


# ---------------------------------------------------------------------------------------------
# the frozen record
# ---------------------------------------------------------------------------------------------
class _Report:
    def __init__(self, **kw):
        self.accepted = kw.get("accepted", False)
        self.mode = kw.get("mode", types.SimpleNamespace(value="MODE3_SOFT_BRIDGE_WAIT"))
        self.weak_dir_info_before = kw.get("weak_dir_info_before", 20.0)
        self.weak_dir_info_after = kw.get("weak_dir_info_after", 30.0)
        self.holdout_nis = kw.get("holdout_nis", 1.2)
        self.reason = kw.get("reason", "insufficient_paired_frames")
        self.evidence_status = kw.get("evidence_status", "MISSING")
        self.committed_pose_keys = kw.get("committed_pose_keys", [])
        self.deferred_pose_keys = kw.get("deferred_pose_keys", [1, 2])


def test_record_has_exactly_the_frozen_keys():
    row = candidate_record("run", "cand_0000", 1, 2, _Report(), {}, 3, "host_poses", np.eye(4))
    assert tuple(row.keys()) == CANDIDATE_KEYS
    dumped = json.loads(json.dumps(row))
    assert set(dumped) == set(CANDIDATE_KEYS)


def test_record_maps_report_fields_and_marks_absent_ones_null():
    ev = {"wilson_lower_bound": 0.9, "reentry_pos_jump_m": 0.05}
    row = candidate_record("run", "cand_0000", 1, 2, _Report(), ev, 3, "host_poses", np.eye(4))
    assert row["paired_benefit_status"] == "MISSING"
    assert row["refusal_reason"] == "insufficient_paired_frames"
    assert row["wilson_lower_bound"] == 0.9
    assert row["reentry_pos_jump_m"] == 0.05
    # evidence absent -> null, never a zero
    row2 = candidate_record("run", "c", 1, 2, _Report(), {}, 0, "host_poses", None)
    assert row2["wilson_lower_bound"] is None
    assert row2["reentry_pos_jump_m"] is None
    assert row2["pose_se3_first_trigger"] is None


def test_nonfinite_holdout_nis_becomes_null():
    row = candidate_record("run", "c", 1, 2, _Report(holdout_nis=float("inf")), {},
                           0, "host_poses", np.eye(4))
    assert row["holdout_nis"] is None
    assert json.dumps(row)          # must stay serialisable


def test_record_without_report_is_all_null_but_identity():
    row = candidate_record("run", "c", 11, 22, None, None, 5, "host_poses", np.eye(4))
    assert row["mode"] is None and row["accepted"] is None
    assert row["t_trigger_ns"] == 11 and row["t_decision_ns"] == 22
    assert row["parent_map_version"] == 5
    assert len(row["pose_se3_first_trigger"]) == 16
    assert row["pose_se3_first_trigger"][0] == 1.0


def test_pose_first_trigger_is_row_major():
    T = np.arange(16, dtype=float).reshape(4, 4)
    row = candidate_record("run", "c", 1, 2, None, None, 0, "host_poses", T)
    assert row["pose_se3_first_trigger"] == list(range(16))


# ---------------------------------------------------------------------------------------------
# live NIS provenance
# ---------------------------------------------------------------------------------------------
class _FakeNode:
    sigma_meas_m = 0.12

    def __init__(self, trusted=None):
        self._trusted = np.zeros((0, 3)) if trusted is None else np.asarray(trusted, float)
        self.tx_mgr = types.SimpleNamespace(trusted_version=0, trusted_poses={})

    def get_trusted_map_points(self, max_pts=2000):
        return self._trusted

    def support_reference(self):
        return self._trusted


def _scan(n=200, z=0.0):
    rng = np.random.default_rng(0)
    return rng.normal(scale=0.5, size=(n, 3)) + np.array([0.0, 0.0, z])


def test_nis_uses_the_node_map_when_available():
    pts = _scan(400)
    n = LiveNis(_FakeNode(pts))
    pose = np.eye(4)
    v, src, ref = n.measure(pose, _scan(200))
    assert src == "computed" and ref == "node_map"
    assert math.isfinite(v)


def test_nis_falls_back_to_previous_scan_only_while_map_is_empty():
    n = LiveNis(_FakeNode(None))
    pose = np.eye(4)
    v0, src0, ref0 = n.measure(pose, _scan(200))
    assert v0 is None and src0 == "unavailable" and ref0 == "none"
    v1, src1, ref1 = n.measure(pose, _scan(200))
    assert src1 == "computed" and ref1 == "prev_scan"


def test_nis_never_invents_a_value_after_the_first_success():
    n = LiveNis(_FakeNode(None))
    n.measure(np.eye(4), _scan(200))
    n.measure(np.eye(4), _scan(200))
    assert n.counts["computed"] == 1
    # a cloud with too few points cannot be scored; the last value is reused and labelled
    tiny = np.zeros((3, 3))
    v, src, _ = n.measure(np.eye(4), tiny)
    assert src == "carried_forward" and v is not None
    assert n.counts["carried_forward"] == 1


# ---------------------------------------------------------------------------------------------
# the loop's orchestration
# ---------------------------------------------------------------------------------------------
class _FakeTxMgr:
    def __init__(self):
        self.active_quarantine = None
        self.trusted_poses = {}
        self.trusted_version = 7
        self.confirmation_margin_ns = 2_000_000_000
        self.state = RecoveryState.HEALTHY
        self.promoted = []
        self.registered = []

    def register_quarantined_frame(self, keyframe_id, timestamp_ns=0):
        self.registered.append(int(keyframe_id))

    def step_healthy(self, delta):
        self.promoted.append(delta.keyframe_id)
        self.trusted_poses[delta.keyframe_id] = np.asarray(delta.pose_se3).copy()
        return 1


class _FakeLoopNode:
    sigma_meas_m = 0.12

    def __init__(self, trigger_at):
        self.tx_mgr = _FakeTxMgr()
        # A real run reaches the onset with a populated trusted map: step_healthy has been
        # promoting keyframes since the first frame. Without it the gate has no incumbent
        # trajectory and reports MISSING, which is the honest answer for a cold start.
        self._kf_timestamps = {900: 0, 901: 500_000_000}
        for k, x in ((900, 0.0), (901, 1.0)):
            T = np.eye(4)
            T[0, 3] = x
            self.tx_mgr.trusted_poses[k] = T
        self._trigger_at = trigger_at
        self.detector = types.SimpleNamespace(
            state=types.SimpleNamespace(value="HEALTHY"), cusum_g=0.0, suspect_dwell=0)
        self.scan_buffer_body = {}
        self.last_paired_evidence = {"wilson_lower_bound": 0.0, "reentry_pos_jump_m": 0.5}
        self.calls = []
        self._trusted = _scan(400)

    def get_trusted_map_points(self, max_pts=2000):
        return self._trusted

    def support_reference(self):
        return self._trusted

    def _frame_has_reference_support(self, kf_id, ref_pts, repaired_poses,
                                     radius_m=1.0, min_supported_fraction=0.60):
        # the real predicate compares the placed scan against the reference; for the fake, "is
        # there a reference at all" is the same distinction
        return len(ref_pts) >= 30

    def step_frame(self, kf_id, ts_ns, pose, scan, nis):
        self.calls.append((kf_id, ts_ns))
        self.scan_buffer_body[kf_id] = scan
        self._kf_timestamps[kf_id] = ts_ns
        if self.tx_mgr.active_quarantine is None and len(self.calls) == self._trigger_at:
            self.tx_mgr.active_quarantine = object()
        return None

    def evaluate_and_commit_candidate(self, candidate_id, repaired_poses, incumbent_poses=None,
                                      reentry_anchor_pose=None, reentry_anchor_ts_ns=None):
        self.last_call = dict(candidate_id=candidate_id,
                              repaired=sorted(repaired_poses),
                              incumbent=sorted(incumbent_poses or {}),
                              anchor=None if reentry_anchor_pose is None else
                              reentry_anchor_pose[:3, 3].tolist(),
                              anchor_ts_ns=reentry_anchor_ts_ns)
        self.tx_mgr.active_quarantine = None
        return _Report(accepted=False, committed_pose_keys=[], deferred_pose_keys=[0, 1])


def test_loop_decides_once_at_the_confirmation_margin():
    node = _FakeLoopNode(trigger_at=3)
    loop = NativeClosedLoop(node, run_id="run", confirmation_margin_ns=2_000_000_000)
    t0 = 1_000_000_000
    for i in range(40):
        loop.on_pair(t0 + i * 100_000_000, np.eye(4), _scan(200))
    assert len(loop.episodes) == 1
    assert len(loop.records) == 1
    row = loop.records[0]
    assert row["t_trigger_ns"] == t0 + 2 * 100_000_000
    assert row["t_decision_ns"] >= row["t_trigger_ns"] + 2_000_000_000
    assert node.last_call["candidate_id"] == "cand_0000"
    # the candidate is the frames registered while the segment was open, incumbent covers them
    assert node.last_call["repaired"] == node.last_call["incumbent"]
    assert node.last_call["repaired"] == list(range(2, 23))


def test_loop_keeps_counting_frames_after_the_decision():
    node = _FakeLoopNode(trigger_at=2)
    loop = NativeClosedLoop(node, run_id="run", confirmation_margin_ns=1_000_000_000)
    t0 = 0
    for i in range(20):
        loop.on_pair(t0 + i * 100_000_000, np.eye(4), _scan(200))
    assert len(loop.records) == 1
    assert loop.frames_after_first_decision > 0


def test_bag_end_decides_an_open_segment():
    node = _FakeLoopNode(trigger_at=8)
    loop = NativeClosedLoop(node, run_id="run", confirmation_margin_ns=60_000_000_000)
    for i in range(10):
        loop.on_pair(i * 100_000_000, np.eye(4), _scan(200))
    assert loop.records == []
    loop.finish()
    assert len(loop.records) == 1
    assert loop.episodes[0].meta["decision_basis"] == "bag_end"


def test_summary_counts_gate_outcomes_and_nulls():
    node = _FakeLoopNode(trigger_at=2)
    loop = NativeClosedLoop(node, run_id="run", confirmation_margin_ns=1_000_000_000)
    for i in range(20):
        loop.on_pair(i * 100_000_000, np.eye(4), _scan(200))
    s = build_summary(loop, {})
    assert s["gate"]["rejected"] == 1 and s["gate"]["accepted"] == 0
    assert s["quarantine"]["second_and_later_events"] == 0
    assert set(s["null_field_counts"]) == set(CANDIDATE_KEYS)
    assert s["frames"]["consumed_after_first_decision"] > 0
    json.dumps(s)


def test_detection_off_grows_the_map_and_judges_nothing():
    node = _WarmupNode()
    loop = NativeClosedLoop(node, run_id="run", detection_enabled=False)
    for i in range(25):
        loop.on_pair(i * 100_000_000, np.eye(4), _scan(200))
    assert loop.detection_counts["DISABLED_FOR_DIAGNOSIS"] == 25
    assert loop.detection_counts["AVAILABLE"] == 0
    assert node.step_frame_calls == 0, "nothing may be judged in diagnosis mode"
    assert len(node.tx_mgr.trusted_poses) > 0, "the map still grows"
    assert loop.records == []
    assert all(d["detection_status"] == "DISABLED_FOR_DIAGNOSIS" for d in loop.diag)
    s = build_summary(loop, {})          # the summary must be writable with no decision at all
    assert s["detection_enabled"] is False
    assert s["quarantine"]["decisions"] == 0
    assert s["pose_convention"]["one_frame_check"]["status"] == "NOT_REACHED"


def test_nis_vs_map_size_bins_every_node_map_frame_once():
    node = _WarmupNode()
    loop = NativeClosedLoop(node, run_id="run", detection_enabled=False)
    for i in range(30):
        loop.on_pair(i * 100_000_000, np.eye(4), _scan(200))
    t = nis_vs_map_size(loop.diag)
    n_rows = sum(b["n"] for b in t["by_trusted_keyframes"])
    assert n_rows == sum(1 for d in loop.diag
                         if d["nis"] is not None and d["nis_reference"] == "node_map")


def test_nis_bins_report_real_quantiles_at_small_n():
    diag = [{"nis": v, "nis_reference": "node_map", "trusted_keyframes": 2, "map_points": 900}
            for v in (53.49, 55.045)]
    t = nis_vs_map_size(diag)
    b = t["by_trusted_keyframes"][0]
    assert b["n"] == 2
    assert b["min"] == 53.49 and b["max"] == 55.045
    assert b["median"] == pytest.approx(54.2675)      # between the samples, not sel[n//2]
    assert b["p90"] >= b["median"] >= b["min"]


def test_no_quarantine_means_no_records_and_a_readable_summary():
    node = _FakeLoopNode(trigger_at=10 ** 9)
    loop = NativeClosedLoop(node, run_id="run")
    for i in range(5):
        loop.on_pair(i * 100_000_000, np.eye(4), _scan(200))
    loop.finish()
    assert loop.records == []
    s = build_summary(loop, {})
    assert s["quarantine"]["episodes"] == 0
    assert s["gate"]["accepted"] == 0 and s["gate"]["rejected"] == 0


class _WarmupNode(_FakeLoopNode):
    """Starts with an empty map, which is the only state in which warm-up is needed."""

    def __init__(self):
        super().__init__(trigger_at=10 ** 9)
        self.tx_mgr.trusted_poses = {}
        self._kf_timestamps = {}
        self._trusted = np.zeros((0, 3))
        self.step_frame_calls = 0

    def _sync_spatial_map_with_trusted_poses(self):
        keys = [k for k in self.tx_mgr.trusted_poses if k in self.scan_buffer_body]
        self._trusted = (np.vstack([self.scan_buffer_body[k] for k in sorted(keys)])
                         if keys else np.zeros((0, 3)))

    def step_frame(self, kf_id, ts_ns, pose, scan, nis):
        self.step_frame_calls += 1
        return super().step_frame(kf_id, ts_ns, pose, scan, nis)


def test_unsupported_frames_are_ingested_as_unavailable_not_as_healthy():
    node = _WarmupNode()
    loop = NativeClosedLoop(node, run_id="run")
    for i in range(6):
        loop.on_pair(i * 100_000_000, np.eye(4), _scan(200))
    assert loop.ingested_undetected >= 1, "frames with no reference still enter the map"
    assert loop.detection_counts["UNAVAILABLE"] >= 1
    assert loop.detection_counts["AVAILABLE"] >= 1, "gating resumes once the map is usable"
    assert loop.first_detected_kf is not None
    undetected = [d for d in loop.diag if d["detection_status"] == "UNAVAILABLE"]
    assert undetected and all(d["detector_state"] == "HEALTHY" for d in undetected)
    w = build_summary(loop, {})["warmup"]
    assert w["frames_ingested_without_detection"] == loop.ingested_undetected
    assert w["detection_status_counts"]["UNAVAILABLE"] == loop.detection_counts["UNAVAILABLE"]


# ---------------------------------------------------------------------------------------------
# cloud decoding
# ---------------------------------------------------------------------------------------------
def _fake_cloud(points, point_step=16, is_bigendian=False):
    """A PointCloud2-shaped object: x,y,z,intensity float32 at 0,4,8,12."""
    arr = np.zeros((len(points), 4), dtype=np.float32)
    arr[:, :3] = points
    fields = [types.SimpleNamespace(name=n, offset=o, datatype=7, count=1)
              for n, o in (("x", 0), ("y", 4), ("z", 8), ("intensity", 12))]
    return types.SimpleNamespace(fields=fields, point_step=point_step,
                                 width=len(points), height=1,
                                 data=arr.tobytes(), is_bigendian=is_bigendian)


def test_cloud_to_xyz_reads_by_offset():
    pts = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    out = cloud_to_xyz(_fake_cloud(pts))
    assert np.allclose(out, pts)


def test_cloud_to_xyz_drops_non_finite_points():
    pts = np.array([[1.0, 2.0, 3.0], [np.nan, 5.0, 6.0]])
    out = cloud_to_xyz(_fake_cloud(pts))
    assert len(out) == 1


def test_cloud_to_xyz_rejects_a_cloud_without_xyz():
    msg = _fake_cloud(np.zeros((2, 3)))
    msg.fields = [f for f in msg.fields if f.name != "z"]
    with pytest.raises(ValueError):
        cloud_to_xyz(msg)


def test_the_reentry_bound_is_scaled_by_time_since_the_anchor():
    """1.2506 m over the 2.329 s confirmation margin is walking, not a discontinuity.

    The live run at sigma=0.884 refused its only candidate on this number. The anchor was
    2.329 s older than the trigger, so the distance contained 0.54 m/s of ordinary motion and the
    bound was applied as if the two poses were instantaneous neighbours.
    """
    from slam_recovery.sim.transaction_manager_node import boundary_jump_within_envelope

    bound = 0.5
    assert boundary_jump_within_envelope(1.2506, 2.329, bound), \
        "continuous motion over the margin must fit the envelope"
    assert not boundary_jump_within_envelope(1.2506, 0.0, bound), \
        "the same displacement with no elapsed time is a real discontinuity"
    assert not boundary_jump_within_envelope(7.0, 2.329, bound), \
        "a jump beyond what 2 m/s could cover in the interval is still refused"


def test_the_loop_dates_the_anchor_it_passes():
    """The envelope is only correct if the anchor's own timestamp reaches the evaluator."""
    node = _FakeLoopNode(trigger_at=3)
    loop = NativeClosedLoop(node, run_id="run", confirmation_margin_ns=2_000_000_000)
    t0 = 1_000_000_000
    for i in range(40):
        loop.on_pair(t0 + i * 100_000_000, np.eye(4), _scan(200))
    call = node.last_call
    trusted_keys = [k for k in node._kf_timestamps if k in node.tx_mgr.trusted_poses]
    if trusted_keys:
        expected = node._kf_timestamps[max(trusted_keys)]
        assert call["anchor_ts_ns"] == expected
    else:
        assert call["anchor_ts_ns"] is None
