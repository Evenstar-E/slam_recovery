"""Source-bound radius-index equivalence checks; no native performance measurement."""
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TARGET = "9862ad5bb7cd5056421fb9ea865787f16d421a5f"
for path in ["slam_recovery/sim/transaction_manager_node.py", "slam_recovery/tests/test_radius_index.py"]:
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{TARGET}:{path}"])
    assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == expected
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode, _RadiusIndex
from slam_recovery.tests import test_radius_index

suite = unittest.defaultTestLoader.loadTestsFromModule(test_radius_index)
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
node = OnlineRecoveryTransactionNode()
rng = np.random.default_rng(19)
reference = rng.normal(size=(600, 3)) * .6
scan = rng.normal(size=(400, 3)) * .6
node.scan_buffer_body[1] = scan
shared = _RadiusIndex(reference, 1.)
observations = []
for x in [0., 4.]:
    pose = np.eye(4)
    pose[0, 3] = x
    queries = (scan + pose[:3, 3])[::max(1, len(scan) // 200)][:200]
    brute = bool(np.mean(np.min(np.sum((queries[:, None, :] - reference[None, :, :]) ** 2,
                                       axis=-1), axis=1) <= 1.) >= .6)
    direct = node._frame_has_reference_support(1, reference, {1: pose})
    cached = node._frame_has_reference_support(1, reference, {1: pose}, index=shared)
    assert brute == direct == cached
    observations.append({"pose_x": x, "brute": brute, "new_index": direct, "shared_index": cached})
print(json.dumps({
    "target": TARGET,
    "scope": "Three local radius-index tests and actual support-predicate equivalence; no ROS/native/bag/tuning/performance benchmark",
    "selected_tests": {"count": result.testsRun, "status": "PASS_LOCAL"},
    "support_predicate_equivalence": {"status": "PASS_LOCAL", "observations": observations},
    "report_arithmetic": {
        "reported_cumulative_ms_before": "4356.5", "reported_cumulative_ms_after": "842.9",
        "reported_ratio": str(Decimal("4356.5") / Decimal("842.9")),
        "candidate_frames_before_after": [16, 13],
        "limit": "Different candidate populations; ratio not an isolated native speedup measurement",
    },
    "remaining_time_gap": "MESSAGE_TIME_MINUS_WALL_ELAPSED_IS_NOT_INDEPENDENTLY_MEASURED_WALL_STAGE",
    "native_full_two_event": "NOT_COMPLETED",
    "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED",
}, ensure_ascii=False, indent=2))
