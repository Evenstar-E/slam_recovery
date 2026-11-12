"""Version-bound local acceptance controls; no ROS, host, bag, or tuning."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
TARGET = "70f68fbc3450569677659e8220d34fa2e3abaa4b"
BASE = "ebf76f59993d9d2b965f0d8e29f9a6cb0d237296"
OUT = Path(__file__).with_name("local_checks.json")

def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])

def blob(path):
    return git("show", f"{TARGET}:{path}")

# The worktree is deliberately not checked out or merged to the review target. The changed
# production modules and selected test module are loaded from the target; all other package
# dependencies must have identical Git objects and unchanged tracked worktree bytes.
changed = set(git("diff", "--name-only", "HEAD", TARGET, "--", "slam_recovery").decode().splitlines())
allowed = {"slam_recovery/quarantine/manager.py", "slam_recovery/ros/recovery_node.py",
           "slam_recovery/tests/test_checkpoint_client.py", "slam_recovery/tests/test_lifecycle_rearm.py"}
assert changed <= allowed, changed
assert not git("diff", "HEAD", "--", "slam_recovery").strip(), "Tracked package worktree has edits"
assert not git("ls-files", "--others", "--exclude-standard", "--", "slam_recovery").strip()
sys.path.insert(0, str(ROOT))
import numpy as np
import slam_recovery.quarantine as quarantine

loaded = {}
def load(name, path):
    raw = blob(path)
    loaded[path] = {"git_blob": git("rev-parse", f"{TARGET}:{path}").decode().strip(),
                    "sha256": hashlib.sha256(raw).hexdigest()}
    module = ModuleType(name)
    module.__file__ = str(ROOT / path)
    module.__package__ = name.rpartition(".")[0]
    sys.modules[name] = module
    exec(compile(raw, f"{TARGET}:{path}", "exec"), module.__dict__)
    return module

manager_module = load("slam_recovery.quarantine.manager", "slam_recovery/quarantine/manager.py")
quarantine.manager = manager_module
quarantine.TrustedMapTransactionManager = manager_module.TrustedMapTransactionManager
recovery = load("slam_recovery.ros.recovery_node", "slam_recovery/ros/recovery_node.py")
lifecycle = load("slam_recovery.tests._review_target_lifecycle", "slam_recovery/tests/test_lifecycle_rearm.py")
from slam_recovery.core import RecoveryState

suite = unittest.TestLoader().loadTestsFromTestCase(lifecycle.TestAcceptedCommitReleasesTheHold)
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()

# A full accepted report triggers the real driver's asynchronous native calls. No fake
# host thread is needed: a normal slow host has not consumed the file yet.
with tempfile.TemporaryDirectory(prefix="accepted-target-review-") as directory:
    cp = recovery.CheckpointClient(directory)
    manager = SimpleNamespace(trusted_poses={}, trusted_version=0, active_quarantine=object(),
                              confirmation_margin_ns=2_000_000_000,
                              state=RecoveryState.QUARANTINED, lifecycle_events=[])
    repaired = {1: np.eye(4), 2: np.eye(4)}
    repaired[1][0, 3], repaired[2][0, 3] = 1., 2.
    report = SimpleNamespace(accepted=True, mode="MODE2", reason="simulated full acceptance",
                             committed_pose_keys=[1, 2], deferred_pose_keys=[],
                             partial_commit=False, evidence_status="PASSED")
    def evaluate(candidate_id, poses, **kwargs):
        manager.trusted_poses = {k: p.copy() for k, p in poses.items()}
        manager.trusted_version += 1
        manager.active_quarantine = None
        manager.state = RecoveryState.HEALTHY
        manager.lifecycle_events.append({"event": "commit_closed", "segment_id": "old",
                                         "n_committed": 2})
        return report
    node = SimpleNamespace(tx_mgr=manager, sigma_meas_m=.12, _kf_timestamps={},
                           last_paired_evidence={}, evaluate_and_commit_candidate=evaluate)
    loop = recovery.NativeClosedLoop(node, "review-only", candidate_source="icp_reregistration",
                                     checkpoint_client=cp)
    old1, old2 = np.eye(4), np.eye(4)
    old1[0, 3], old2[0, 3] = 10., 20.
    loop._open = recovery.Episode(0, 10_000_000_000, old1, 12_000_000_000)
    loop._open.frames = [(1, 10_000_000_000, old1), (2, 11_000_000_000, old2)]
    loop._icp_candidate = lambda ep: (repaired, {"status": "synthetic correction"})
    row = loop.decide(12_000_000_000, "review-only")
    before = Path(directory, "cmd").read_text(encoding="utf-8").splitlines()
    pending_before = [e["command"] for e in cp._pending]
    assert row["accepted"] and pending_before == ["reprocess", "set_state"]
    assert before[0] == "set_state" and float(before[1].split()[0]) == 20.
    loop.service()
    after = Path(directory, "cmd").read_text(encoding="utf-8").splitlines()
    pending_after = [e["command"] for e in cp._pending]
    assert after[0] == "resume" and pending_after == ["reprocess", "set_state", "resume"]
    Path(directory, "ack").write_text("OK resume hold=0\n", encoding="utf-8")
    assert cp.poll() is None and cp.pending()
    accepted = {"status": "FAIL_REPRODUCED_LOCAL", "pending_at_decision": pending_before,
                "command_at_decision": before[0], "state_payload_x": float(before[1].split()[0]),
                "trusted_repaired_tail_x": 2., "pending_after_service": pending_after,
                "command_after_service": after[0], "any_reprocess_applied_ack": False,
                "resume_ack_blocked_by_fifo_head": True,
                "scope": "Actual target driver/client, simulated full gate report; no deployed host"}

# Actual target manager closes one segment, then opens the next through its normal entry
# point before the next service. This is serial, not a hypothetical simultaneous race.
with tempfile.TemporaryDirectory(prefix="segment-target-review-") as directory:
    mgr, old_segment, report = lifecycle.TestAcceptedCommitReleasesTheHold()._accepted_commit()
    assert report.accepted
    new_segment = mgr.trigger_quarantine(
        estimated_onset_ns=8_000_000_000, current_ns=10_000_000_000,
        weak_direction_6d=np.array([0., 0., 0., 1., 0., 0.]),
        info_before_6x6=np.diag([60., 60., 60., 3., 60., 60.]),
        propagated_cov_norm=1.8, weak_direction_frame=lifecycle.FRAME,
        info_before_frame=lifecycle.FRAME, anchor_pose_world=np.eye(4))
    cp = recovery.CheckpointClient(directory)
    node = SimpleNamespace(tx_mgr=mgr)
    loop = recovery.NativeClosedLoop(node, "segment-review", checkpoint_client=cp)
    loop._open_episode(10_000_000_000, np.eye(4), new_segment)
    assert Path(directory, "cmd").read_text(encoding="utf-8").splitlines()[0] == "hold"
    loop._apply_lifecycle()
    command = Path(directory, "cmd").read_text(encoding="utf-8").splitlines()[0]
    assert command == "resume" and mgr.active_quarantine is new_segment
    stale = {"status": "FAIL_REPRODUCED_LOCAL", "old_segment": old_segment.segment_id,
             "active_segment": new_segment.segment_id, "command_after_old_close": command,
             "pending": [e["command"] for e in cp._pending],
             "scope": "Actual target manager close/reopen and driver; serial normal calls, no host"}

# Confirm the specific archived E2 checkpoint ordering, not the entire archive audit again.
archive = "docs/review_20261110_native_checkpoint/chain_run_fl_native_20261110T115717Z_3390402/"
candidates = [json.loads(line) for line in blob(archive + "candidates.jsonl").decode().splitlines() if line]
events = json.loads(blob(archive + "native_checkpoint_events.json"))
life = json.loads(blob(archive + "lifecycle_events.json"))
trigger = candidates[1]["t_trigger_ns"]
# Parse key/value ack fields without trusting descriptive text or rounded elapsed time.
def ack_values(event):
    return dict(token.split("=", 1) for token in event.get("ack", "").split() if "=" in token)
restores = [e for e in events if e.get("command") == "restore" and e.get("ok")]
assert len(restores) == 2
restore_ack = ack_values(restores[1])
print("E2 restore ack:", restores[1].get("ack"), file=sys.stderr)
# Field names are preserved in the result; locate the checkpoint stamp in the ack.
late_snapshot_candidates = [(e, ack_values(e)) for e in events if e.get("command") == "snapshot" and e.get("ok")]
last_snapshot = max((e for e, fields in late_snapshot_candidates if e["wall"] < restores[1]["wall"]), key=lambda e: e["wall"])
archive_control = {"status": "ARCHIVE_READBACK", "e2_trigger_ns": trigger,
                   "e2_last_snapshot_event": last_snapshot, "e2_restore_event": restores[1],
                   "scope": "Archived d356 controlled two-refusal run, not target70 native execution"}

payload = {"target": TARGET, "comparison_base": BASE,
           "worktree_head": git("rev-parse", "HEAD").decode().strip(),
           "source_loading": "Target Git blobs executed in memory; other tracked package dependencies unchanged",
           "loaded_sources": loaded,
           "selected_tests": {"status": "PASS_LOCAL", "count": result.testsRun},
           "accepted_native_order": accepted, "stale_close_releases_new_segment": stale,
           "archive_checkpoint_order": archive_control,
           "actual_measurement_repair_native_two_event": "NOT_COMPLETED_BY_THIS_CHECK",
           "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED"}
assert not OUT.exists(), "Do not overwrite an earlier result"
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
