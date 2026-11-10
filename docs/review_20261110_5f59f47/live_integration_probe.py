"""Bounded actual-loop checks: ICP wiring, scan sampling, and service scheduling. No ROS."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REV = "5f59f47d22242140f5e65ecc4a5966e182f1a853"
for relative in (
    "slam_recovery/ros/recovery_node.py",
    "slam_recovery/repair/pose_reregistration.py",
    "slam_recovery/sim/transaction_manager_node.py",
    "slam_recovery/core.py",
):
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{REV}:{relative}"])
    actual = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(expected).digest() == hashlib.sha256(actual).digest(), relative
sys.path.insert(0, str(ROOT))
from slam_recovery.core import TangentFrame
from slam_recovery.ros.recovery_node import NativeClosedLoop, build_summary
from slam_recovery.repair.pose_reregistration import reregister_frame
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode

cloud = np.random.default_rng(0).normal(size=(400, 3)) * .16

def setup(source):
    node = OnlineRecoveryTransactionNode()
    node.scan_buffer_body[0] = cloud.copy()
    node._kf_timestamps[0] = 500_000_000
    node.tx_mgr.trusted_poses[0] = np.eye(4)
    node._sync_spatial_map_with_trusted_poses()
    frame = TangentFrame("body", "rot_trans", "scan:7")
    segment = node.tx_mgr.trigger_quarantine(
        0, 1_000_000_000, np.array([0, 0, 0, 1, 0, 0.]),
        np.diag([60, 60, 60, 20, 40, 40.]), .1,
        weak_direction_frame=frame, info_before_frame=frame, anchor_pose_world=np.eye(4),
    )
    loop = NativeClosedLoop(node, "synthetic", candidate_source=source)
    loop.next_kf_id = 1
    loop._open_episode(1_000_000_000, np.eye(4), segment)
    return node, loop

# Same input timestamps with different ordinary service scheduling. The direct event setup
# isolates orchestration, not the detector. No callback races or artificial production faults.
schedules = []
for defer in (False, True):
    node, loop = setup("host_poses")
    for ts in (3_000_000_000, 3_100_000_000, 3_200_000_000):
        loop.on_pair(ts, np.eye(4), cloud)
        if not defer:
            loop.service()
    if defer:
        loop.service()
    schedules.append({
        "service_deferred_until_3_2s": defer,
        "candidate_frames": loop._open.meta["candidate_frames"],
        "decision_input_ts_ns": loop.records[0]["t_decision_ns"],
        "episode_deadline_ns": loop._open.deadline_ns,
        "quarantine_pending": list(node.tx_mgr.active_quarantine.raw_frame_refs),
    })
assert [r["candidate_frames"] for r in schedules] == [1, 3]

# The real ICP branch returns details and calls the actual gate. The budget is disabled;
# this small fixture demonstrates call wiring only, not a native run or recovery success.
node, loop = setup("icp_reregistration")
for k in (1, 2, 3, 4):
    node.scan_buffer_body[k] = cloud.copy()
    node._kf_timestamps[k] = 1_000_000_000 + k * 100_000_000
    node.tx_mgr.register_quarantined_frame(k, node._kf_timestamps[k])
    loop._open.frames.append((k, node._kf_timestamps[k], np.eye(4)))
row = loop.decide(3_000_000_000, "synthetic")
detail = loop.icp_details[0]
assert detail["frames_candidate"] == 4
assert row["candidate_source"] == "icp_reregistration"
assert len(detail["per_frame"]) == 4

large = np.random.default_rng(3).uniform(-2, 2, (6000, 3))
large[:, 2] = 0
res = reregister_frame(large, large, np.eye(4))
assert res.scan_points == 2000
print(json.dumps({
    "target": REV,
    "scope": "actual Python node/loop, synthetic normal inputs, no ROS or native state restore",
    "service_schedules": schedules,
    "icp_branch": {"frames_candidate": detail["frames_candidate"], "statuses": detail["statuses"],
                   "mode": row["mode"], "accepted": row["accepted"],
                   "summary_validity_label": build_summary(loop, {})["gate_decision_validity"]},
    "sampling": {"buffer_points": 6000, "actual_icp_scan_points": res.scan_points},
}, indent=2))
