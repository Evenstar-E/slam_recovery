"""Review-only normal-motion probe; does not run ROS or change admission thresholds."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REV = "0bdd1f494f62f3941865700a8f321b080933f1b2"
PATHS = (
    "slam_recovery/core.py",
    "slam_recovery/sim/transaction_manager_node.py",
    "slam_recovery/ros/recovery_node.py",
)
for relative in PATHS:
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{REV}:{relative}"])
    actual = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(expected).digest() != hashlib.sha256(actual).digest():
        raise SystemExit(f"Source differs from target: {relative}")
sys.path.insert(0, str(ROOT))
from slam_recovery.ros.recovery_node import extrapolate_incumbent
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode

anchor_ns = 1627643757330770969
first_ns = 1627643759659727812
dt = (first_ns - anchor_ns) * 1e-9
node = OnlineRecoveryTransactionNode()
rows = []
for speed in (0.3, 0.1):
    old_pose = np.eye(4)
    old_pose[0, 3] = -speed
    poses, anchor, basis = extrapolate_incumbent(
        {0: old_pose, 1: np.eye(4)},
        {0: anchor_ns - 1_000_000_000, 1: anchor_ns},
        {2: first_ns},
    )
    continuous = poses[2].copy()
    _, _, raw_jump = node._measure_paired_evidence(
        {2: continuous}, reentry_anchor_pose=anchor,
        reentry_candidate_pose=continuous,
    )
    discontinuous = continuous.copy()
    discontinuous[0, 3] += 1.0
    aligned_jump = float(np.linalg.norm(continuous[:3, 3] - poses[2][:3, 3]))
    true_jump = float(np.linalg.norm(discontinuous[:3, 3] - poses[2][:3, 3]))
    rows.append({
        "speed_mps": speed, "elapsed_s": dt,
        "actual_node_raw_jump_m": raw_jump,
        "raw_exceeds_default_0_5_m": raw_jump > node.tx_mgr.gate_thresholds.max_reentry_jump_m,
        "time_aligned_difference_m": aligned_jump,
        "time_aligned_1_m_discontinuity_m": true_jump,
        "basis": basis["status"],
    })
assert rows[0]["raw_exceeds_default_0_5_m"]
assert not rows[1]["raw_exceeds_default_0_5_m"]
assert all(r["time_aligned_difference_m"] == 0.0 for r in rows)
assert all(np.isclose(r["time_aligned_1_m_discontinuity_m"], 1.0, rtol=0.0, atol=1e-12) for r in rows)
print(json.dumps({
    "target": REV, "module": str(sys.modules[OnlineRecoveryTransactionNode.__module__].__file__),
    "scope": "synthetic normal-motion, actual node raw metric; aligned differences are review arithmetic, not an implemented fix or full gate PASS",
    "rows": rows,
}, indent=2))
