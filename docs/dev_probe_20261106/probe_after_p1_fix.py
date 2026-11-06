"""Developer-side re-run of the four P1 observations from docs/review_20261106_1846b00.

The reviewer's `docs/review_20261106_a14bc1c/probe_boundaries.py` measures the *pre-fix*
behaviour. Two of its observations are now structurally impossible and one of them cannot even
be recomputed, because the thing it measured (a full factor-list copy per promotion) no longer
exists:

  * `try_candidate()`                      -> accepted True / pose 42 committed  (now False / False)
  * `try_candidate(wilson=0, jump=99)`     -> accepted False                    (still False, now FAILED)
  * `revoke_last_frame()["validation_reference"]` -> [[10, 0, 0]]              (now [])
  * `sum(len(before[1]) for before in m._promoted_before_images)` -> 31_125 / 124_750 references,
    and the expression now raises TypeError because `before[1]` is an int length marker, not a
    copied list. The replacement measurement below counts *stored factor references*, which is
    now 0 for every entry.

Run from the repository root:  python -B docs/dev_probe_20261106/probe_after_p1_fix.py
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slam_recovery.core import CandidateMap, RecoveryState
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.tests.test_atomic_commit import _make_delta


def try_candidate(**evidence):
    m = TrustedMapTransactionManager()
    m.trigger_quarantine(10_000_000_000, 14_000_000_000,
                         np.array([0., 0., 0., 1., 0., 0.]), np.eye(6), 1.)
    candidate = CandidateMap(candidate_id="review", parent_map_version=m.trusted_version,
                             repaired_poses={42: np.eye(4)}, info_after_6x6=np.eye(6) * 100,
                             cov_after_6x6=np.eye(6) * .01, holdout_nis=.1, **evidence)
    report = m.validate_and_resolve(candidate)
    return {"accepted": bool(report.accepted),
            "mode": report.mode.value,
            "evidence_status": report.evidence_status,
            "pose_42_committed": 42 in m.trusted_poses}


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
    """Stored factor references in the undo log, i.e. the pre-fix `n(n-1)/2` quantity."""
    m = TrustedMapTransactionManager(confirmation_margin_ns=0)
    for k in range(frames):
        m.step_healthy(_make_delta(k, k, k))
    return {"undo_records": len(m._promoted_before_images),
            "stored_factor_references": sum(len(rec[1]) if isinstance(rec[1], list) else 0
                                            for rec in m._promoted_before_images)}


def non_finite_evidence_is_not_treated_as_sufficient():
    """A repair that cannot be constructed reports inf NIS; it must wait, not commit."""
    m = TrustedMapTransactionManager()
    m.trigger_quarantine(10_000_000_000, 14_000_000_000,
                         np.array([0., 0., 0., 1., 0., 0.]), np.eye(6), 1.)
    candidate = CandidateMap(candidate_id="not_evaluable", parent_map_version=m.trusted_version,
                             repaired_poses={42: np.eye(4)}, info_after_6x6=np.eye(6) * 100,
                             cov_after_6x6=np.eye(6) * .01, holdout_nis=float("inf"),
                             paired_benefit_approved=True, wilson_lower_bound=0.9,
                             reentry_pos_jump_m=0.01)
    report = m.validate_and_resolve(candidate)
    return {"accepted": bool(report.accepted), "mode": report.mode.value,
            "pose_42_committed": 42 in m.trusted_poses}


if __name__ == "__main__":
    print(json.dumps({
        "omitted_evidence": try_candidate(),
        "explicit_adverse_evidence": try_candidate(
            wilson_lower_bound=0., reentry_pos_jump_m=99., paired_benefit_approved=True),
        "measured_passing_evidence": try_candidate(
            wilson_lower_bound=0.90, reentry_pos_jump_m=0.05, paired_benefit_approved=True),
        "last_frame_revoked": revoke_last_frame(),
        "undo_factor_references": {n: undo_slots(n) for n in (250, 500)},
        "non_finite_holdout_nis": non_finite_evidence_is_not_treated_as_sufficient(),
    }, indent=2))
