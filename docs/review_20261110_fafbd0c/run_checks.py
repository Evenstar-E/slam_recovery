"""Small source-pinned scripted-trigger integration and wait-clock controls; no ROS/native run."""
import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = "fafbd0cbfb21e4456b8c187494638b778a0d3466"
for path in ["slam_recovery/ros/recovery_node.py", "slam_recovery/ros/run_native_loop.sh",
             "slam_recovery/quarantine/manager.py", "slam_recovery/sim/transaction_manager_node.py"]:
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{TARGET}:{path}"])
    assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == expected
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import BackendDelta
from slam_recovery.ros.recovery_node import NativeClosedLoop, build_summary
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.tests.test_lifecycle_rearm import _open_waiting_segment

cloud = np.random.default_rng(0).normal(size=(400, 3)) * .16
node = OnlineRecoveryTransactionNode(confirmation_margin_sec=1.)
for key, stamp in [(7, 500_000_000), (8, 1_500_000_000)]:
    node.scan_buffer_body[key] = cloud.copy()
    node._kf_timestamps[key] = stamp
    node.tx_mgr.step_healthy(BackendDelta(
        timestamp_ns=stamp, frame_id="map", pose_se3=np.eye(4),
        velocity=np.zeros(3), bias_acc=np.zeros(3), bias_gyr=np.zeros(3),
        cov_6x6=np.eye(6), info_6x6=np.eye(6), nis_value=.1, nis_dof=6,
        factor_ids=[key], keyframe_id=key))
node._sync_spatial_map_with_trusted_poses()
assert 7 in node.tx_mgr.trusted_poses and 7 in node._kf_map_points
loop = NativeClosedLoop(node, "scripted-review", detection_enabled=False)
loop.scripted_triggers_s = [0.]
loop.on_pair(1_500_000_000, np.eye(4), cloud)
assert len(loop.scripted_fired) == 1 and len(loop.episodes) == 1
assert "0" in node.tx_mgr.active_quarantine.raw_frame_refs
assert loop._open.frames == []
assert 7 not in node.tx_mgr.trusted_poses and 7 in node._kf_map_points
first_state = {
    "trigger_key": 0,
    "pending_keys": node.tx_mgr.active_quarantine.raw_frame_refs,
    "candidate_frame_keys": [k for k, _, _ in loop._open.frames],
    "trusted_keys": sorted(node.tx_mgr.trusted_poses),
    "spatial_map_keys": sorted(node._kf_map_points),
    "trusted_map_points": len(node.get_trusted_map_points()),
}
loop.on_pair(1_600_000_000, np.eye(4), cloud)
assert [k for k, _, _ in loop._open.frames] == [1]
assert 7 in node._kf_map_points

# A normal uninterrupted frame stream changes t_end but not the frozen WAIT origin.
node = OnlineRecoveryTransactionNode(wait_limit_sec=2.)
_open_waiting_segment(node.tx_mgr)
wait_start = node.tx_mgr.wait_started_ns
for stamp in [500_000_000, 1_000_000_000, 1_500_000_000]:
    node.tx_mgr.register_quarantined_frame(stamp, stamp)
    assert node.tx_mgr.wait_started_ns == wait_start
    assert node.tx_mgr.maybe_close_waiting_segment(stamp) is None
closed = node.tx_mgr.maybe_close_waiting_segment(2_005_000_000)
assert closed is not None

# A declaration alone still labels the receipt CONTROLLED_INTERFACE_TEST even if no trigger fired.
node = OnlineRecoveryTransactionNode()
unfired = NativeClosedLoop(node, "unfired", detection_enabled=False)
unfired.scripted_triggers_s = [42.]
summary_mode = build_summary(unfired, {})["run_mode"]
assert summary_mode == "CONTROLLED_TRIGGERS_NOT_FIRED"
source = (ROOT / "slam_recovery/ros/run_native_loop.sh").read_text(encoding="utf-8")
receipt_block = source.split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
tree = ast.parse(receipt_block)
mode_expression = next(
    value for node in ast.walk(tree) if isinstance(node, ast.Dict)
    for key, value in zip(node.keys, node.values)
    if isinstance(key, ast.Constant) and key.value == "run_mode")
receipt_mode = eval(compile(ast.Expression(mode_expression), "receipt-mode", "eval"),
                    {"scripted": "42"})
assert receipt_mode == "CONTROLLED_INTERFACE_TEST"
print(json.dumps({
    "target": TARGET,
    "scope": "Synthetic actual node/loop controls and receipt expression; no native/ROS/bag/tuning",
    "scripted_trigger_and_episode": "PASS_LOCAL",
    "trigger_frame_tracking": {"status": "FAIL_REPRODUCED_LOCAL", **first_state,
        "next_candidate_keys": [1], "limit": "Trigger belongs to pending but is omitted from candidate input, not lost from manager accounting"},
    "revoked_reference_sync": {"status": "FAIL_REPRODUCED_LOCAL", "revoked_key": 7,
        "stale_after_next_quarantined_frame": True, "limit": "Python spatial reference, not measured host map pollution"},
    "wait_stream_control": {"status": "PASS_LOCAL_NO_CONTINUOUS_RESET", "wait_started_ns": wait_start,
        "closed_ns": 2_005_000_000, "limit": "Does not identify the deployed delayed-start cause"},
    "unfired_mode_control": {"summary_mode": summary_mode, "receipt_mode": receipt_mode,
        "status": "FAIL_LOCAL_MODE_MISMATCH"},
    "developer_run": "REPORTED_CONTROLLED_REFUSAL_RESTORE_REENTRY_SECOND_REFUSAL_TERMINAL_WAIT",
    "actual_repair_and_full_two_event": "NOT_COMPLETED",
    "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED",
}, ensure_ascii=False, indent=2))
