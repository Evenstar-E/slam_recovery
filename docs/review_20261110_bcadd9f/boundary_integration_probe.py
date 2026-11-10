"""Actual-node normal-motion integration probe; no ROS, no modified gate thresholds."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REV = "bcadd9f6a03846589ef5a3ae73309c977f6d97c4"
for relative in (
    "slam_recovery/core.py",
    "slam_recovery/sim/transaction_manager_node.py",
    "slam_recovery/validation/fim_and_holdout.py",
):
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{REV}:{relative}"])
    actual = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(actual).digest() != hashlib.sha256(expected).digest():
        raise SystemExit(f"Source differs: {relative}")
sys.path.insert(0, str(ROOT))
from slam_recovery.core import TangentFrame
from slam_recovery.sim.transaction_manager_node import (
    OnlineRecoveryTransactionNode, boundary_jump_within_envelope,
)

assert boundary_jump_within_envelope(1.2506, 2.329, .5)
assert not boundary_jump_within_envelope(1.2506, 0, .5)
assert not boundary_jump_within_envelope(7, 2.329, .5)
cloud = np.random.default_rng(0).normal(size=(400, 3)) * .16
rows = []
for speed in (.3, .1):
    node = OnlineRecoveryTransactionNode()
    anchor = np.eye(4)
    node.scan_buffer_body[0] = cloud.copy()
    node.tx_mgr.trusted_poses[0] = anchor.copy()
    node._kf_timestamps[0] = 1_000_000_000
    node._sync_spatial_map_with_trusted_poses()
    frame = TangentFrame("body", "rot_trans", "scan:7")
    node.tx_mgr.trigger_quarantine(
        1_000_000_000, 4_000_000_000,
        np.array([0, 0, 0, 1, 0, 0.]), np.diag([60, 60, 60, 20, 40, 40.]), .1,
        weak_direction_frame=frame, info_before_frame=frame, anchor_pose_world=anchor,
    )
    candidate, incumbent = {}, {}
    for k in (1, 2, 3, 4):
        ts = 3_328_956_843 + (k - 1) * 100_000_000
        pose = anchor.copy()
        pose[0, 3] = speed * ((ts - 1_000_000_000) * 1e-9)
        node.scan_buffer_body[k] = cloud - pose[:3, 3]
        node._kf_timestamps[k] = ts
        node.tx_mgr.register_quarantined_frame(k, ts)
        candidate[k] = pose
        incumbent[k] = pose.copy()
        incumbent[k][0, 3] += .12
    report = node.evaluate_and_commit_candidate(
        "continuous", candidate, incumbent_poses=incumbent,
        reentry_anchor_pose=anchor, reentry_anchor_ts_ns=1_000_000_000,
    )
    rows.append({
        "speed_mps": speed,
        "boundary_ok": node._last_holdout_support["segment_boundary_ok"],
        "first_run_jump_m": node._last_holdout_support["first_run_jump_m"],
        "reentry_jump_m": node.last_paired_evidence["reentry_pos_jump_m"],
        "paired_approved": node.last_paired_evidence["approved"],
        "evidence_status": report.evidence_status,
        "reason": report.reason, "mode": report.mode.value,
        "info_after": report.weak_dir_info_after,
        "cov_norm": report.posterior_cov_norm,
        "accepted": report.accepted,
    })
assert rows[0]["boundary_ok"] and rows[0]["paired_approved"]
assert rows[0]["evidence_status"] == "FAILED" and not rows[0]["accepted"]
assert rows[1]["boundary_ok"] and rows[1]["evidence_status"] == "PASSED"
print(json.dumps({
    "target": REV, "module": str(sys.modules[OnlineRecoveryTransactionNode.__module__].__file__),
    "scope": "synthetic actual-node integration; identical world scene and continuous constant velocity; direct quarantine entry, not detection/native evidence",
    "helper_three_controls": "PASS", "rows": rows,
    "status": "PASS means remaining duplicate raw-distance refusal reproduced, not fixed/full gate PASS",
}, indent=2))
