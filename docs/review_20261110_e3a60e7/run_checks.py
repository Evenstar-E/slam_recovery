"""Targeted wait-path fix check and reuse of the unresolved-provisional control; no ROS."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TARGET = "e3a60e7d5c52dd3dd96da462d338117afab221bb"
for path in ["slam_recovery/ros/recovery_node.py", "slam_recovery/quarantine/manager.py",
             "slam_recovery/sim/transaction_manager_node.py", "slam_recovery/tests/test_lifecycle_rearm.py"]:
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{TARGET}:{path}"])
    assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == expected
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import BackendDelta, RecoveryState
from slam_recovery.ros.recovery_node import NativeClosedLoop
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.tests import test_lifecycle_rearm as tests

suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
cloud = np.random.default_rng(0).normal(size=(400, 3)) * .16

# Reuse the old actual on_pair/UNAVAILABLE control, now expecting closure and rearm.
node = OnlineRecoveryTransactionNode(wait_limit_sec=1.)
tests._open_waiting_segment(node.tx_mgr)
loop = NativeClosedLoop(node, "review-only")
loop.on_pair(2_000_000_000, np.eye(4), cloud)
closed = {
    "state": node.tx_mgr.state.value,
    "events": [e["event"] for e in node.tx_mgr.lifecycle_events],
    "unavailable_frames": loop.detection_counts["UNAVAILABLE"],
}
assert node.tx_mgr.state == RecoveryState.HEALTHY
assert closed["events"] == ["wait_limit_closed", "rearm"]
assert closed["unavailable_frames"] == 1

# The same rearm now reaches step_healthy. Reuse the archived key7 control through the changed
# ingest path, not a second manager-only test: old unresolved provisional remains promotable.
node = OnlineRecoveryTransactionNode(confirmation_margin_sec=1., wait_limit_sec=1.)
node.scan_buffer_body[7] = cloud.copy()
node._kf_timestamps[7] = 100_000_000
node.tx_mgr.step_healthy(BackendDelta(
    timestamp_ns=100_000_000, frame_id="map", pose_se3=np.eye(4),
    velocity=np.zeros(3), bias_acc=np.zeros(3), bias_gyr=np.zeros(3),
    cov_6x6=np.eye(6), info_6x6=np.eye(6), nis_value=.1, nis_dof=6,
    factor_ids=[7], keyframe_id=7))
tests._open_waiting_segment(node.tx_mgr, 500_000_000)
loop = NativeClosedLoop(node, "review-only")
loop.on_pair(2_000_000_000, np.eye(4), cloud)
segment = node.tx_mgr.unresolved_segments[-1]
leak = {
    "archived_unresolved_frames": segment.raw_frame_refs,
    "trusted_keys_after_rearm_ingest": sorted(node.tx_mgr.trusted_poses),
    "trusted_factors": node.tx_mgr.trusted_factors,
    "spatial_map_keys": sorted(node._kf_map_points),
    "unavailable_frames": loop.detection_counts["UNAVAILABLE"],
    "state": node.tx_mgr.state.value,
}
assert "7" in segment.raw_frame_refs
assert 7 in node.tx_mgr.trusted_poses and 7 in node.tx_mgr.trusted_factors
assert 7 in node._kf_map_points
print(json.dumps({
    "target": TARGET,
    "scope": "Source-pinned local lifecycle tests and two synthetic actual on_pair controls; no native/ROS/bag/tuning",
    "selected_suite": {"status": "PASS_LOCAL", "count": result.testsRun},
    "unavailable_wait_closure": {"status": "PASS_LOCAL", **closed},
    "unresolved_provisional_promotion": {"status": "FAIL_REPRODUCED_LOCAL", **leak},
    "developer_run": {
        "status": "DEVELOPER_REPORTED_NEGATIVE_ONLY",
        "e1": "FALSE_EARLY_TRIGGER_REFUSED",
        "e2": "NOT_TRIGGERED",
        "candidate_source": "host_poses",
        "post_e1_paired_frames": 498,
        "scan_pair_fraction": 542 / 598,
        "native_full_two_event": "NOT_COMPLETED",
    },
    "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED",
}, ensure_ascii=False, indent=2))
