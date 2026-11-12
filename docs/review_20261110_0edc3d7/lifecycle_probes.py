"""Normal lifecycle integration controls; exit zero means defects reproduced, not fix PASS."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REV = '0edc3d76a43ddbed396eaf2dd2733f48d4ecffc4'
for name in ('slam_recovery/ros/recovery_node.py',
             'slam_recovery/sim/transaction_manager_node.py',
             'slam_recovery/quarantine/manager.py', 'slam_recovery/health/detector.py'):
    expected = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{REV}:{name}'])
    assert hashlib.sha256(expected).digest() == hashlib.sha256(
        (ROOT / name).read_bytes().replace(b'\r\n', b'\n')).digest(), name
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import BackendDelta, RecoveryState
from slam_recovery.ros.recovery_node import NativeClosedLoop
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.tests.test_lifecycle_rearm import _open_waiting_segment

cloud = np.random.default_rng(0).normal(size=(400, 3)) * .16

# Same support-UNAVAILABLE path that the hall ICP archive used after trusted map became empty.
node = OnlineRecoveryTransactionNode(wait_limit_sec=1.)
_open_waiting_segment(node.tx_mgr)
loop = NativeClosedLoop(node, 'review-only')
for seconds in (2, 4, 8):
    loop.on_pair(seconds * 1_000_000_000, np.eye(4), cloud)
unavailable = {
    'state': node.tx_mgr.state.value,
    'wait_limit_ns': node.tx_mgr.wait_limit_ns,
    'last_input_ns': 8_000_000_000,
    'lifecycle_events': node.tx_mgr.lifecycle_events,
    'unavailable_frames': loop.detection_counts['UNAVAILABLE'],
}
assert unavailable['unavailable_frames'] == 3
assert node.tx_mgr.state == RecoveryState.WAITING_FOR_EVIDENCE
assert not node.tx_mgr.lifecycle_events

# Detector decision is computed before the wait closes, so its old QUARANTINED decision is used
# immediately after reset/rearm, reopening E1 instead of establishing a new dwell for E2.
node = OnlineRecoveryTransactionNode(wait_limit_sec=1.)
_open_waiting_segment(node.tx_mgr)
for seconds in (1, 2):
    node.step_frame(seconds, seconds * 100_000_000, np.eye(4), cloud, 10.)
old_segment = node.tx_mgr.active_quarantine.segment_id
node.step_frame(3, 2_000_000_000, np.eye(4), cloud, 10.)
stale = {
    'closed_segment': old_segment,
    'lifecycle_events': node.tx_mgr.lifecycle_events,
    'manager_state': node.tx_mgr.state.value,
    'detector_state': node.detector.state.value,
    'detector_dwell': node.detector.suspect_dwell,
    'active_segment': node.tx_mgr.active_quarantine.segment_id,
}
assert node.tx_mgr.state == RecoveryState.QUARANTINED
assert node.detector.state == RecoveryState.HEALTHY
assert node.detector.suspect_dwell == 0

# A provisional delta revoked by E1 remains in provisional_queue. Closing the segment marks it
# unresolved, yet rearm does not remove it, and normal step_healthy promotes it into trusted.
node = OnlineRecoveryTransactionNode(confirmation_margin_sec=1., wait_limit_sec=1.)
node.tx_mgr.step_healthy(BackendDelta(
    timestamp_ns=100_000_000, frame_id='map', pose_se3=np.eye(4),
    velocity=np.zeros(3), bias_acc=np.zeros(3), bias_gyr=np.zeros(3),
    cov_6x6=np.eye(6), info_6x6=np.eye(6), nis_value=.1, nis_dof=6,
    factor_ids=[7], keyframe_id=7))
_open_waiting_segment(node.tx_mgr, 500_000_000)
closed = node.tx_mgr.maybe_close_waiting_segment(2_000_000_000)
assert closed is not None and '7' in closed.raw_frame_refs
assert node.tx_mgr.rearm()
node.tx_mgr.step_healthy(BackendDelta(
    timestamp_ns=3_000_000_000, frame_id='map', pose_se3=np.eye(4),
    velocity=np.zeros(3), bias_acc=np.zeros(3), bias_gyr=np.zeros(3),
    cov_6x6=np.eye(6), info_6x6=np.eye(6), nis_value=.1, nis_dof=6,
    factor_ids=[8], keyframe_id=8))
leak = {
    'archived_unresolved_frames': closed.raw_frame_refs,
    'trusted_after_rearm_ingest': sorted(node.tx_mgr.trusted_poses),
    'trusted_factors': node.tx_mgr.trusted_factors,
}
assert 7 in node.tx_mgr.trusted_poses
print(json.dumps({'target': REV, 'scope': 'synthetic normal actual loop/node/manager; no ROS',
    'unavailable_timer_not_serviced': unavailable,
    'stale_decision_reopens_segment': stale,
    'unresolved_provisional_promoted': leak}, indent=2))
