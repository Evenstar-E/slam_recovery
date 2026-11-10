"""Read-only Python probes for A9 rollback population, event times and A8 staging."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "slam_recovery" / "tests"))

import numpy as np

from test_a9_repair_undo import _candidate, _delta
from slam_recovery.quarantine import TrustedMapTransactionManager


def trigger(mgr, onset_ns, current_ns):
    return mgr.trigger_quarantine(
        estimated_onset_ns=onset_ns, current_ns=current_ns,
        weak_direction_6d=np.array([0, 0, 0, 1, 0, 0.0]),
        info_before_6x6=np.eye(6) * 10, propagated_cov_norm=1.0)


def setup():
    mgr = TrustedMapTransactionManager(confirmation_margin_ns=0)
    for key in (1, 2, 3):
        mgr.step_healthy(_delta(key, key * 100_000_000, key * 0.1))
    trigger(mgr, 200_000_000, 300_000_000)
    return mgr


def main():
    results = {"source_root": str(ROOT), "scope": "in-memory Python, no ROS/bag runs"}

    mgr = setup()
    mgr.validate_and_resolve(_candidate(mgr.trusted_version, {2: np.eye(4), 3: np.eye(4)}))
    mgr.step_healthy(_delta(4, 400_000_000, 0.4))
    segment = trigger(mgr, 100_000_000, 500_000_000)
    results["revoked_repair_population"] = {
        "trusted_keys": sorted(mgr.trusted_poses),
        "pending_refs": list(segment.raw_frame_refs),
        "provisional_keys": [delta.keyframe_id for delta in mgr.provisional_queue],
    }
    assert 2 not in mgr.trusted_poses and 3 not in mgr.trusted_poses
    assert "2" not in segment.raw_frame_refs and "3" not in segment.raw_frame_refs

    mgr = setup()
    mgr.register_quarantined_frame(4, 400_000_000)
    report = mgr.validate_and_resolve(_candidate(
        mgr.trusted_version, {2: np.eye(4), 3: np.eye(4)}))
    assert report.remaining_pending_pose_keys == [4]
    mgr.validate_and_resolve(_candidate(mgr.trusted_version, {4: np.eye(4)}))
    mgr.step_healthy(_delta(5, 500_000_000, 0.5))
    segment = trigger(mgr, 350_000_000, 600_000_000)
    results["later_arrival_old_segment_end"] = {
        "trusted_keys": sorted(mgr.trusted_poses),
        "pending_refs": list(segment.raw_frame_refs),
        "undo_entries": [[d.keyframe_id, d.timestamp_ns] for d in mgr.promoted_history],
        "frame_4_timestamp_ns": 400_000_000, "rollback_onset_ns": 350_000_000,
    }
    assert 4 in mgr.trusted_poses

    mgr = setup()
    before = (len(mgr.promoted_history), len(mgr._promoted_before_images),
              mgr.state.value, mgr.trusted_version)
    original = mgr._insert_undo_entry
    calls = 0

    def failing_second_insert(entry, image):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected second undo insertion failure")
        original(entry, image)

    with patch.object(mgr, "_insert_undo_entry", side_effect=failing_second_insert):
        try:
            mgr.validate_and_resolve(_candidate(
                mgr.trusted_version, {2: np.eye(4), 3: np.eye(4)}))
        except RuntimeError:
            pass
        else:
            raise AssertionError("Injected failure not observed")
    after = (len(mgr.promoted_history), len(mgr._promoted_before_images),
             mgr.state.value, mgr.trusted_version)
    results["undo_insert_failure"] = {
        "before": before, "after": after, "trusted_keys": sorted(mgr.trusted_poses),
    }
    assert after[0] == before[0] + 1 and after[3] == before[3] and after[2] != before[2]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print("Three boundary failures reproduced; no algorithm or repository files changed.")


if __name__ == "__main__":
    main()
