"""Two small source-bound checks for the new reference and wait-clock claims; no ROS."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = "1b8a4492c1db21682f12f37d07a389eee92e20d5"
for path in ["slam_recovery/ros/recovery_node.py", "slam_recovery/quarantine/manager.py",
             "slam_recovery/sim/transaction_manager_node.py"]:
    source = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{TARGET}:{path}"])
    assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == source
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import RecoveryState
from slam_recovery.ros.recovery_node import NativeClosedLoop
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.tests.test_lifecycle_rearm import V, INFO_BEFORE, WORLD

# Different predicates: NIS needs 30 nearby reference samples, spatial support needs 60% coverage.
# A small reference can geometrically cover a query while NIS uses a separate previous scan.
rng = np.random.default_rng(8)
cloud = rng.normal(size=(400, 3)) * .16
reference = rng.normal(size=(20, 3)) * .16
previous = rng.normal(size=(400, 3)) * .16
node = OnlineRecoveryTransactionNode()
loop = NativeClosedLoop(node, "review-only")
loop.nis._support_cache = reference
loop.nis._support_key = (node.tx_mgr.trusted_version, len(node.tx_mgr.trusted_poses))
loop.nis._last_refresh_ns = 0
loop.nis._prev_world = previous
loop.on_pair(0, np.eye(4), cloud)
row = loop.diag[-1]
assert row["nis_reference"] == "prev_scan"
assert row["detection_status"] == "AVAILABLE"
assert loop.frames_fed == 1

# Rejection does not accept a decision timestamp. A decision evaluated at 8s after the last
# ingested segment frame at 4s still starts the wait at 4s, not at that decision time.
node = OnlineRecoveryTransactionNode(wait_limit_sec=2.)
manager = node.tx_mgr
manager.trigger_quarantine(1_000_000_000, 1_000_000_000, V, INFO_BEFORE, 1.,
                          weak_direction_frame=WORLD, info_before_frame=WORLD,
                          anchor_pose_world=np.eye(4))
manager.register_quarantined_frame(1, 4_000_000_000)
simulated_decision_ns = 8_000_000_000
manager.validate_and_resolve(None)
assert manager.state == RecoveryState.WAITING_FOR_EVIDENCE
actual_wait_start = manager.wait_started_ns
closed = manager.maybe_close_waiting_segment(9_000_000_000)
assert actual_wait_start == 4_000_000_000 and closed is not None
print(json.dumps({
    "target": TARGET,
    "scope": "Synthetic actual on_pair and manager controls; no native/ROS/bag/tuning",
    "reference_predicate_control": {
        "status": "COUNTEREXAMPLE_REPRODUCED_LOCAL",
        "reference_points": len(reference), "nis_reference": row["nis_reference"],
        "detection_status": row["detection_status"], "fed_to_step_frame": loop.frames_fed,
        "limit": "prev_scan does not imply UNAVAILABLE; not a reproduction of the reported 169 frames",
    },
    "wait_origin_control": {
        "status": "SOURCE_SEMANTICS_CONFIRMED_LOCAL",
        "simulated_decision_ns": simulated_decision_ns,
        "last_segment_frame_ns": 4_000_000_000,
        "actual_wait_start_ns": actual_wait_start,
        "arrival_ns": 9_000_000_000,
        "closed": closed is not None,
        "would_close_under_decision_origin": 9_000_000_000 >= simulated_decision_ns + 2_000_000_000,
        "limit": "Documents current clock origin, not a deployed 2s trial or an actual timing failure",
    },
    "second_run": "DEVELOPER_REPORTED_WAIT_CLOSE_REARM_RESUME_E2_NOT_TRIGGERED",
    "native_full_two_event": "NOT_COMPLETED",
    "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED",
}, ensure_ascii=False, indent=2))
