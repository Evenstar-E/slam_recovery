"""Reuse existing segment tests and the prior actual-loop setup. No ROS or production edits."""
from pathlib import Path
import inspect
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import slam_recovery.tests.test_pose_reregistration as tests

for name, fn in inspect.getmembers(tests, inspect.isfunction):
    if name.startswith("test_"):
        fn()
        print(name, "PASS")

p = ROOT / "docs/review_20261110_5f59f47/live_integration_probe.py"
source = p.read_text(encoding="utf-8").split("# Same input timestamps")[0]
source = source.replace(
    "5f59f47d22242140f5e65ecc4a5966e182f1a853",
    "9e0a36c98b30d7244e5d5208bcb3dfc23edc9a05",
)
ns = {"__file__": str(p), "__name__": "review_reuse"}
exec(compile(source, str(p), "exec"), ns)
for small in (False, True):
    node, loop = ns["setup"]("icp_reregistration")
    for k in (1, 2, 3, 4):
        node.scan_buffer_body[k] = ns["cloud"].copy()
        node._kf_timestamps[k] = 1_000_000_000 + k * 100_000_000
        node.tx_mgr.register_quarantined_frame(k, node._kf_timestamps[k])
        loop._open.frames.append((k, node._kf_timestamps[k], np.eye(4)))
    if small:
        node.committed_map_points = [np.zeros((10, 3))]
    poses, detail = loop._icp_candidate(loop._open)
    print("small_reference", small, "status", detail["status"], "candidate_keys", sorted(poses))
    assert len(poses) == 4
    if small:
        assert detail["status"] == "REFERENCE_TOO_SMALL"
        assert all(np.allclose(poses[k], np.eye(4)) for k in poses)
    else:
        assert detail["status"] in ("CONVERGED", "ITERATION_LIMIT")
print("Failure semantics reproduced; not a production-fix PASS")
