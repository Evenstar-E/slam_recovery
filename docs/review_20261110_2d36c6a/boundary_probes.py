"""Reproduce remaining Python transaction boundaries without ROS, bags or file writes."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "slam_recovery" / "tests"))

import numpy as np

from test_atomic_commit import TestAtomicPublish
from slam_recovery.core import RecoveryState
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode


def main():
    results = {"source_root": str(ROOT), "scope": "Python in-memory probes, not native host runs"}

    mgr = TestAtomicPublish._manager()
    state_before = mgr.state
    try:
        mgr.validate_and_resolve(TestAtomicPublish._candidate(
            mgr, parent_map_version=mgr.trusted_version + 1))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Stale-parent candidate was unexpectedly accepted")
    results["A8_precondition_exception"] = {
        "state_before": state_before.value, "state_after": mgr.state.value,
        "fully_restored": mgr.state == state_before,
    }
    assert mgr.state == RecoveryState.VALIDATING and mgr.state != state_before

    node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0)
    node.detector.step = lambda window: SimpleNamespace(
        state=RecoveryState.QUARANTINED, estimated_onset_ns=200_000_000)
    fim = (np.eye(6) * 10, np.eye(6) * 0.1, 10.0, 10.0,
           np.array([0, 0, 0, 1, 0, 0.0]))
    with patch("slam_recovery.sim.transaction_manager_node.compute_6dof_point_to_plane_fim",
               return_value=fim):
        node.step_frame(2, 200_000_000, np.eye(4), np.zeros((10, 3)), 1.0)
    results["A5_trigger_frame"] = {
        "buffer_keys": sorted(node.scan_buffer_body),
        "registered_refs": list(node.tx_mgr.active_quarantine.raw_frame_refs),
        "trigger_frame_registered": "2" in node.tx_mgr.active_quarantine.raw_frame_refs,
    }
    assert 2 in node.scan_buffer_body and "2" not in node.tx_mgr.active_quarantine.raw_frame_refs

    mgr = TestAtomicPublish._manager()
    cand = TestAtomicPublish._candidate(
        mgr, repaired_poses={2: np.eye(4), 42: np.eye(4)}, repaired_factor_ids=[420],
        repaired_bias_acc=np.ones(3), repaired_bias_gyr=np.ones(3))
    report = mgr.validate_and_resolve(cand)
    assert report.accepted and mgr.state == RecoveryState.HEALTHY
    mgr.trigger_quarantine(
        estimated_onset_ns=2_000_000_000, current_ns=8_000_000_000,
        weak_direction_6d=np.array([0, 0, 0, 1, 0, 0.0]),
        info_before_6x6=np.eye(6) * 10, propagated_cov_norm=1.0)
    results["A9_second_event"] = {
        "trusted_pose_keys": sorted(mgr.trusted_poses),
        "factors": list(mgr.trusted_factors), "bias_acc": mgr.trusted_bias_acc.tolist(),
        "registered_refs": list(mgr.active_quarantine.raw_frame_refs),
        "repair_pose_42_survives": 42 in mgr.trusted_poses,
    }
    assert 42 in mgr.trusted_poses
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("Three remaining boundary counterexamples reproduced; no repository files changed.")


if __name__ == "__main__":
    main()
