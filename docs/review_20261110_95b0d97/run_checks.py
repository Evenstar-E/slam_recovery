"""Source-bound scheduler timestamp control; no native execution or timing experiment."""
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
TARGET = "95b0d979de2bdd2ea03ac0b28ac870895151a0e7"
PATH = "slam_recovery/ros/recovery_node.py"
expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{TARGET}:{PATH}"])
assert (ROOT / PATH).read_bytes().replace(b"\r\n", b"\n") == expected
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.ros.recovery_node import Episode, NativeClosedLoop
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode

loop = NativeClosedLoop(OnlineRecoveryTransactionNode(), "review-only")
loop._open = Episode(0, 0, np.eye(4), 1_000_000_000)
with patch("slam_recovery.ros.recovery_node.time.time", return_value=100.):
    loop._track_episode(1, 1_000_000_000, np.eye(4))
first_pending_wall = loop._pending_decision_wall
with patch("slam_recovery.ros.recovery_node.time.time", return_value=124.):
    loop._track_episode(2, 2_000_000_000, np.eye(4))
last_pending_wall = loop._pending_decision_wall
assert first_pending_wall == 100. and last_pending_wall == 124.
actual_entry_wall = 125.
print(json.dumps({
    "target": TARGET,
    "scope": "Synthetic normal episode frame tracking with supplied wall times; no ROS/native/bag/tuning",
    "scheduler_clock": {
        "status": "FAIL_REPRODUCED_LOCAL",
        "first_eligible_wall": first_pending_wall,
        "stored_pending_wall_after_next_frame": last_pending_wall,
        "synthetic_decide_entry_wall": actual_entry_wall,
        "reported_formula_delay_s": actual_entry_wall - last_pending_wall,
        "first_eligibility_delay_s": actual_entry_wall - first_pending_wall,
        "limit": "Proves timestamp overwrite, not the actual 24.126 s delay in the reported run",
    },
    "native_timeout": "DEVELOPER_REPORTED_ACK_TIMEOUT_NOT_PROOF_OF_OPERATION_NOT_APPLIED",
    "host_thread_proposal": "NOT_IMPLEMENTED_IN_THIS_REVISION_NOT_USER_METHOD_SELECTION",
    "native_full_two_event": "NOT_COMPLETED",
    "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED",
}, ensure_ascii=False, indent=2))
