"""Recheck the previous normal-path examples; no ROS, algorithms or old files changed."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "slam_recovery" / "tests"))

import numpy as np

from slam_recovery.core import RecoveryState
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from test_transaction_normal_path import _candidate, _delta, _trigger


def setup():
    mgr = TrustedMapTransactionManager(confirmation_margin_ns=0)
    for k in (1, 2, 3):
        mgr.step_healthy(_delta(k, k * 100_000_000, 0.1 * k))
    _trigger(mgr, 200_000_000, 300_000_000)
    return mgr


def main():
    results = {"source_revision": "21fa6506f8b1c63f95b135f7052b2fb84ea7c9c3",
               "scope": "in-memory Python, original cases adapted to current frame/cov/anchor contract"}
    node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0)
    node.detector.step = lambda win: SimpleNamespace(
        state=RecoveryState.QUARANTINED, estimated_onset_ns=200_000_000)
    fim = (np.eye(6) * 10, np.eye(6) * 0.1, 10.0, 10.0,
           np.array([0, 0, 0, 1, 0, 0.0]))
    with patch("slam_recovery.sim.transaction_manager_node.compute_6dof_point_to_plane_fim",
               return_value=fim):
        node.step_frame(2, 200_000_000, np.eye(4), np.zeros((10, 3)), 1.0)
    assert 2 in node.scan_buffer_body
    assert "2" in node.tx_mgr.active_quarantine.raw_frame_refs
    results["alarm_frame"] = {"status": "PASS", "buffer_keys": sorted(node.scan_buffer_body),
                              "pending": node.tx_mgr.active_quarantine.raw_frame_refs}

    mgr = setup()
    assert mgr.validate_and_resolve(_candidate(mgr.trusted_version, {2: np.eye(4), 3: np.eye(4)})).accepted
    mgr.step_healthy(_delta(4, 400_000_000, 0.4))
    seg = _trigger(mgr, 100_000_000, 500_000_000)
    assert not mgr.trusted_poses
    assert set(seg.raw_frame_refs) == {"1", "2", "3", "4"}
    results["revoked_repair_population"] = {
        "status": "PASS", "trusted_keys": sorted(mgr.trusted_poses),
        "pending": list(seg.raw_frame_refs),
        "provisional_keys": [d.keyframe_id for d in mgr.provisional_queue]}

    mgr = setup()
    mgr.register_quarantined_frame(4, 400_000_000)
    report = mgr.validate_and_resolve(_candidate(mgr.trusted_version, {2: np.eye(4), 3: np.eye(4)}))
    assert report.accepted and report.remaining_pending_pose_keys == [4]
    report = mgr.validate_and_resolve(_candidate(mgr.trusted_version, {4: np.eye(4)}))
    assert report.accepted and mgr.state == RecoveryState.HEALTHY
    undo_before = [[d.keyframe_id, d.timestamp_ns] for d in mgr.promoted_history]
    mgr.step_healthy(_delta(5, 500_000_000, 0.5))
    seg = _trigger(mgr, 350_000_000, 600_000_000)
    assert 4 not in mgr.trusted_poses and "4" in seg.raw_frame_refs
    assert "5" in seg.raw_frame_refs
    results["later_arrival_and_partial_retry"] = {
        "status": "PASS", "undo_before_second_event": undo_before,
        "trusted_keys": sorted(mgr.trusted_poses), "pending": list(seg.raw_frame_refs),
        "frame_4_timestamp_ns": 400_000_000, "rollback_onset_ns": 350_000_000,
        "note": "Repair batch shares updated segment end; this checks the original missed rollback, not arbitrary per-key write dependencies."}
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
