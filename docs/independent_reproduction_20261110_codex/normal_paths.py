"""Dataset-free A5/A9 acceptance probes. Exit 1 means the desired invariant fails.

Manager cases use supplied passing candidate evidence from the existing A9 fixture;
they do not test geometry quality. The node case supplies a detector decision only
to exercise the alarm ingest branch; detection accuracy is outside this test.
"""
import json
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from slam_recovery.core import HealthDecision, RecoveryState, TangentFrame
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.tests.test_a9_repair_undo import _candidate, _delta


def quarantine(manager, onset, now):
    frame = TangentFrame("world", "rot_trans", "world")
    return manager.trigger_quarantine(
        onset, now, np.array([0., 0., 0., 1., 0., 0.]), np.eye(6)*10, 1.,
        weak_direction_frame=frame, info_before_frame=frame)


def prepared():
    manager = TrustedMapTransactionManager(confirmation_margin_ns=0)
    for key in (1, 2, 3):
        manager.step_healthy(_delta(key, key*100_000_000, key*.1))
    quarantine(manager, 200_000_000, 300_000_000)
    return manager


def repair(manager, keys):
    poses = {key: np.eye(4) for key in keys}
    for key, pose in poses.items():
        pose[0, 3] = 9 + key*.1
    report = manager.validate_and_resolve(_candidate(manager.trusted_version, poses))
    assert report.accepted, "Fixture did not reach accepted repair; not a population result"


def snapshot(manager):
    return {"state": manager.state.name, "trusted": sorted(manager.trusted_poses),
            "pending": [] if manager.active_quarantine is None else
            sorted(map(int, manager.active_quarantine.raw_frame_refs))}


def partial_retry():
    manager = prepared()
    manager.register_quarantined_frame(4, 400_000_000)
    repair(manager, (2,))
    first = snapshot(manager)
    repair(manager, (3, 4))
    second = snapshot(manager)
    return {"passed": first["pending"] == [3, 4] and second["pending"] == []
            and second["trusted"] == [1, 2, 3, 4] and second["state"] == "HEALTHY",
            "after_partial": first, "after_retry": second}


def second_event():
    manager = prepared()
    repair(manager, (2, 3))
    manager.step_healthy(_delta(4, 400_000_000, .4))
    quarantine(manager, 100_000_000, 500_000_000)
    observed = snapshot(manager)
    lost = sorted({1, 2, 3, 4} - set(observed["trusted"]) - set(observed["pending"]))
    return {"passed": not lost, "expected_pending": [1, 2, 3, 4],
            "observed": observed, "lost_from_both": lost}


def late_arrival():
    manager = prepared()
    manager.register_quarantined_frame(4, 400_000_000)
    end = manager.active_quarantine.t_end_ns
    repair(manager, (2, 3, 4))
    undo = [{"key": item.keyframe_id, "timestamp_ns": item.timestamp_ns}
            for item in manager.promoted_history if getattr(item, "undo_kind", "") == "repair"]
    manager.step_healthy(_delta(5, 500_000_000, .5))
    quarantine(manager, 350_000_000, 600_000_000)
    observed = snapshot(manager)
    return {"passed": 4 not in observed["trusted"] and 4 in observed["pending"],
            "arrival_ns": 400_000_000, "onset_ns": 350_000_000,
            "recorded_segment_end_ns": end, "repair_undo_entries": undo,
            "expected_frame_4": "revoked and pending", "observed": observed}


def alarm_frame():
    node = OnlineRecoveryTransactionNode(confirmation_margin_sec=0.)
    cloud = np.random.default_rng(7).normal(size=(160, 3))
    decisions = [HealthDecision(RecoveryState.HEALTHY, 0., 0, 0, 1.),
                 HealthDecision(RecoveryState.QUARANTINED, 1., 200_000_000, 200_000_000, 1.),
                 HealthDecision(RecoveryState.QUARANTINED, 1., 200_000_000, 200_000_000, 1.)]
    snapshots = []
    with patch.object(node.detector, "step", side_effect=decisions):
        for key in (1, 2, 3):
            node.step_frame(key, key*100_000_000, np.eye(4), cloud, 1.)
            snapshots.append(snapshot(node.tx_mgr))
    return {"passed": 2 in snapshots[1]["pending"] and 3 in snapshots[2]["pending"],
            "alarm_key": 2, "after_alarm": snapshots[1], "after_following_frame": snapshots[2],
            "raw_scan_keys": sorted(node.scan_buffer_body),
            "qualification": "Raw data are retained, but alarm frame lacks pending membership."}


def main():
    result = {"scope": __doc__, "checks": {}}
    for name, function in (("partial_retry", partial_retry), ("second_event", second_event),
                           ("late_arrival", late_arrival), ("alarm_frame", alarm_frame)):
        try:
            value = function()
            value["status"] = "PASS" if value["passed"] else "FAIL"
        except Exception as error:
            value = {"status": "BLOCKED", "error": repr(error)}
        result["checks"][name] = value
    result["passed"] = all(v["status"] == "PASS" for v in result["checks"].values())
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
