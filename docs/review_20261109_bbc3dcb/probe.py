"""Run from repository root: python -B docs/review_20261109_bbc3dcb/probe.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import json
import numpy as np
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode

rng = np.random.default_rng(1)
cloud = np.column_stack([rng.uniform(-2, 2, 600), rng.uniform(-2, 2, 600), np.zeros(600)])
node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0)
node.committed_map_points = [cloud]
node.tx_mgr.trigger_quarantine(int(10e9), int(20e9), np.array([0, 0, 0, 1, 0, 0]), np.eye(6) * 2, 1.2)
poses, incumbent = {}, {}
for k in range(20):
    node.scan_buffer_body[k] = cloud.copy()
    pose = np.eye(4)
    pose[2, 3] = 0 if k < 8 else 100
    poses[k] = pose
    old = np.eye(4)
    old[2, 3] = 0.3
    incumbent[k] = old
report = node.evaluate_and_commit_candidate(
    'unsupported_probe', poses, aux_or_loop_info_6x6=np.eye(6) * 100,
    incumbent_poses=incumbent, reentry_anchor_pose=np.eye(4))
result = {
    'accepted': report.accepted, 'mode': report.mode.value, 'holdout_nis': report.holdout_nis,
    'paired': node.last_paired_evidence, 'holdout': node._last_holdout_support,
    'committed_poses': len(node.tx_mgr.trusted_poses),
    'committed_100m_poses': int(sum(p[2, 3] == 100 for p in node.tx_mgr.trusted_poses.values())),
}
missing = OnlineRecoveryTransactionNode()
missing.committed_map_points = [cloud]
try:
    missing.evaluate_and_commit_candidate('missing_scan', {0: np.eye(4)})
    result['missing_scan_exception'] = None
except Exception as exc:
    result['missing_scan_exception'] = type(exc).__name__ + ': ' + str(exc)
print(json.dumps(result, indent=2))
# These deliberately describe the observed defects, not desired permanent regression expectations.
assert report.accepted and result['committed_100m_poses'] == 12
assert result['missing_scan_exception'] == 'KeyError: 0'
