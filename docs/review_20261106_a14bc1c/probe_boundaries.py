"""Small, data-free review probes for a14bc1c. Prints observations as JSON."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from slam_recovery.core import CandidateMap, RecoveryState, TangentFrame
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.tests.test_atomic_commit import _make_delta


def try_candidate(**evidence):
    m = TrustedMapTransactionManager()
    m.trigger_quarantine(10_000_000_000, 14_000_000_000,
                         np.array([0., 0., 0., 1., 0., 0.]), np.eye(6), 1.,
        weak_direction_frame=TangentFrame("body", "rot_trans", "probe"),
        info_before_frame=TangentFrame("body", "rot_trans", "probe"),
                         )
    candidate = CandidateMap(candidate_id="review", parent_map_version=m.trusted_version,
                             repaired_poses={42: np.eye(4)}, info_after_6x6=np.eye(6) * 100,
                             cov_after_6x6=np.eye(6) * .01, holdout_nis=.1, **evidence,
        info_after_frame=TangentFrame("body", "rot_trans", "probe"),
        cov_after_frame=TangentFrame("body", "rot_trans", "probe"),
                             )
    report = m.validate_and_resolve(candidate)
    return {"accepted": bool(report.accepted), "pose_42_committed": 42 in m.trusted_poses}


def revoke_last_frame():
    node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0.)
    decisions = [SimpleNamespace(state=RecoveryState.HEALTHY),
                 SimpleNamespace(state=RecoveryState.QUARANTINED, estimated_onset_ns=0)]
    fim = (np.eye(6) * 100, np.eye(6) * .01, 100., 100., np.array([0., 0., 0., 1., 0., 0.]))
    scan = np.array([[10. + i * .01, 0., 0.] for i in range(4)])
    with patch.object(node.detector, "step", side_effect=decisions), patch(
        "slam_recovery.sim.transaction_manager_node.compute_6dof_point_to_plane_fim", return_value=fim
    ):
        for k in (1, 2):
            node.step_frame(k, k * 10**9, np.eye(4), scan, 1.)
    return {"trusted_poses": len(node.tx_mgr.trusted_poses), "voxels": len(node.voxel_store),
            "validation_reference": node.get_trusted_map_points().tolist()}


def undo_slots(frames):
    m = TrustedMapTransactionManager(confirmation_margin_ns=0)
    for k in range(frames):
        m.step_healthy(_make_delta(k, k, k))
    return sum(len(before[1]) for before in m._promoted_before_images)


if __name__ == "__main__":
    print(json.dumps({
        "omitted_evidence": try_candidate(),
        "explicit_adverse_evidence": try_candidate(wilson_lower_bound=0., reentry_pos_jump_m=99.),
        "last_frame_revoked": revoke_last_frame(),
        "undo_factor_references": {n: undo_slots(n) for n in (250, 500)},
    }, indent=2))
