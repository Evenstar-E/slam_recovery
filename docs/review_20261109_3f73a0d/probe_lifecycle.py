"""Run from repo root; records partial-commit lifecycle and discontinuous subsets."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.core import CandidateMap, TangentFrame

rng = np.random.default_rng(1)
cloud = np.column_stack([rng.uniform(-2, 2, 600), rng.uniform(-2, 2, 600), np.zeros(600)])
for case in ('tail', 'gap'):
    node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0)
    node.committed_map_points = [cloud]
    node.tx_mgr.trigger_quarantine(int(10e9), int(20e9), np.array([0, 0, 0, 1, 0, 0]), np.eye(6) * 2, 1.2,
        weak_direction_frame=TangentFrame("world", "rot_trans", "world"),
        info_before_frame=TangentFrame("world", "rot_trans", "world"),
    )
    poses, incumbent = {}, {}
    for k in range(20):
        node.scan_buffer_body[k] = cloud.copy()
        poses[k] = np.eye(4)
        incumbent[k] = np.eye(4)
        incumbent[k][2, 3] = 0.3
        if case == 'tail' and k >= 8:
            poses[k][2, 3] = 100
        if case == 'gap':
            if k == 8:
                poses[k][2, 3] = 100
            elif k > 8:
                poses[k][0, 3] = 1.5
                incumbent[k][0, 3] = 1.5
    report = node.evaluate_and_commit_candidate(case, poses, np.eye(6) * 100, incumbent, np.eye(4))
    print(case, 'accepted=', report.accepted, 'committed=', report.committed_pose_keys,
          'deferred=', report.deferred_pose_keys, 'state=', node.tx_mgr.state.value,
          'active_quarantine=', node.tx_mgr.active_quarantine,
          'jump_evidence=', node.last_paired_evidence.get('reentry_pos_jump_m'))
    try:
        node.evaluate_and_commit_candidate('retry_deferred', {k: poses[k] for k in report.deferred_pose_keys},
                                          np.eye(6) * 100, incumbent, np.eye(4))
    except Exception as exc:
        print('retry_deferred:', type(exc).__name__, str(exc))
# Missing holdout should not produce a machine-readable PASSED evidence status.
node = OnlineRecoveryTransactionNode()
node.tx_mgr.trigger_quarantine(int(1e9), int(2e9), np.array([0, 0, 0, 1, 0, 0]), np.eye(6) * 2, 1.2,
    weak_direction_frame=TangentFrame("world", "rot_trans", "world"),
    info_before_frame=TangentFrame("world", "rot_trans", "world"),
)
candidate = CandidateMap(candidate_id='missing_holdout', parent_map_version=node.tx_mgr.trusted_version,
                         repaired_poses={0: np.eye(4)}, info_after_6x6=np.eye(6) * 100,
                         cov_after_6x6=np.eye(6) * .01, holdout_nis=float('inf'),
                         paired_benefit_approved=True, wilson_lower_bound=.9, reentry_pos_jump_m=0.,
    info_after_frame=TangentFrame("world", "rot_trans", "world"),
                         )
report = node.tx_mgr.validate_and_resolve(candidate)
print('missing_holdout:', 'accepted=', report.accepted, 'evidence_status=', report.evidence_status, 'reason=', report.reason)
