"""Small target-bound file controls; no ROS, native host, bag, or parameter changes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
TARGET = "bbe916f948d7d8652783757844b0294592bf7c46"
OUT = Path(__file__).with_name("local_checks.json")

def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])

allowed = {"slam_recovery/quarantine/manager.py", "slam_recovery/ros/recovery_node.py",
           "slam_recovery/ros/run_native_loop.sh", "slam_recovery/tests/test_checkpoint_client.py",
           "slam_recovery/tests/test_lifecycle_rearm.py", "slam_recovery/tests/test_scripted_trigger.py"}
changed = set(git("diff", "--name-only", "HEAD", TARGET, "--", "slam_recovery").decode().splitlines())
assert changed <= allowed, changed
assert not git("diff", "HEAD", "--", "slam_recovery").strip()
assert not git("ls-files", "--others", "--exclude-standard", "--", "slam_recovery").strip()
sys.path.insert(0, str(ROOT))
import numpy as np
import slam_recovery.quarantine as quarantine

sources = {}
def load(name, path):
    raw = git("show", f"{TARGET}:{path}")
    sources[path] = {"git_blob": git("rev-parse", f"{TARGET}:{path}").decode().strip(),
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
checkpoint = load("slam_recovery.tests._review_target_checkpoint", "slam_recovery/tests/test_checkpoint_client.py")
from slam_recovery.core import RecoveryState
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode

# The target scripted test imports test_recovery_node, which requires unavailable pytest.
# No installation or shim: exercise the real target trigger with the actual node instead.
suite = unittest.TestSuite([
    checkpoint.CheckpointClientTest("test_a_queued_command_is_not_timed_out_before_it_is_sent")])
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
trigger_node = OnlineRecoveryTransactionNode()
trigger_loop = recovery.NativeClosedLoop(trigger_node, "absolute-trigger-review")
trigger_loop.scripted_trigger_stamps_ns = [1_300_000_000]
scan = np.random.default_rng(3).normal(size=(400, 3))
assert not trigger_loop._maybe_scripted_trigger(1, 1_000_000_000, np.eye(4), scan)
assert not trigger_loop._maybe_scripted_trigger(2, 1_299_999_999, np.eye(4), scan)
assert trigger_loop._maybe_scripted_trigger(3, 1_300_000_000, np.eye(4), scan)
assert trigger_loop.scripted_fired[0]["ts_ns"] == 1_300_000_000
assert "3" in trigger_node.tx_mgr.active_quarantine.raw_frame_refs
absolute_trigger = {"status": "PASS_LOCAL", "declared_ns": 1_300_000_000,
                    "actual_ns": trigger_loop.scripted_fired[0]["ts_ns"],
                    "scope": "Actual target trigger and actual transaction node, no detector/host/bag"}

# Deterministic actual-file counterpart to the multi-command fake-host tests. It does not
# change the production or test host to work around Windows rename(cmd, existing cmd.done).
with tempfile.TemporaryDirectory(prefix="serialized-review-") as directory:
    cp = recovery.CheckpointClient(directory)
    events = [cp.reprocess(), cp.set_state(np.eye(4)), cp.resume()]
    assert len(cp._pending) == 1 and len(cp._outbox) == 2
    assert events[1]["wall"] is None and events[2]["wall"] is None
    observed = []
    for command, event in zip(["reprocess", "set_state", "resume"], events):
        assert Path(directory, "cmd").read_text(encoding="utf-8").splitlines()[0] == command
        observed.append(command)
        Path(directory, "ack_received").write_text(f"RECEIVED {command} wall={event['wall'] + .01}\n", encoding="utf-8")
        assert cp.poll() is None and cp.pending()
        Path(directory, "ack").write_text(f"OK {command} done\n", encoding="utf-8")
        assert cp.poll() is event and event["ok"]
    assert not cp.pending() and cp.reprocesses == 1 and cp.resumes == 1
    success = {"status": "PASS_LOCAL", "physical_command_order": observed,
               "received_alone_does_not_advance": True, "queued_wall_unset_until_sent": True,
               "scope": "Actual target client with controlled file acknowledgements, no native host"}

# Reuse the full-acceptance normal scenario from the preceding review, now loading the new
# target driver/client. The candidate is simulated; source ordering and payload are real.
with tempfile.TemporaryDirectory(prefix="accepted-failure-review-") as directory:
    cp = recovery.CheckpointClient(directory)
    mgr = SimpleNamespace(trusted_poses={}, trusted_version=0, active_quarantine=object(),
                          confirmation_margin_ns=2_000_000_000,
                          state=RecoveryState.QUARANTINED, lifecycle_events=[])
    repaired = {1: np.eye(4), 2: np.eye(4)}
    repaired[1][0, 3], repaired[2][0, 3] = 1., 2.
    report = SimpleNamespace(accepted=True, mode="MODE2", reason="simulated full acceptance",
                             committed_pose_keys=[1, 2], deferred_pose_keys=[],
                             partial_commit=False, evidence_status="PASSED")
    def evaluate(candidate_id, poses, **kwargs):
        mgr.trusted_poses = {k: p.copy() for k, p in poses.items()}
        mgr.trusted_version += 1
        mgr.active_quarantine = None
        mgr.state = RecoveryState.HEALTHY
        mgr.lifecycle_events.append({"event": "commit_closed", "segment_id": "old", "n_committed": 2})
        return report
    node = SimpleNamespace(tx_mgr=mgr, sigma_meas_m=.12, _kf_timestamps={},
                           last_paired_evidence={}, evaluate_and_commit_candidate=evaluate)
    loop = recovery.NativeClosedLoop(node, "review-only", candidate_source="icp_reregistration", checkpoint_client=cp)
    old1, old2 = np.eye(4), np.eye(4)
    old1[0, 3], old2[0, 3] = 10., 20.
    loop._open = recovery.Episode(0, 10_000_000_000, old1, 12_000_000_000)
    loop._open.frames = [(1, 10_000_000_000, old1), (2, 11_000_000_000, old2)]
    loop._icp_candidate = lambda ep: (repaired, {"status": "synthetic correction"})
    assert loop.decide(12_000_000_000, "review-only")["accepted"]
    loop.service()
    assert [e["command"] for e in cp._pending] == ["reprocess"]
    assert [e[1] for e in cp._outbox] == ["set_state", "resume"]
    assert Path(directory, "cmd").read_text(encoding="utf-8").splitlines()[0] == "reprocess"
    Path(directory, "ack").write_text("FAIL reprocess replay_failed\n", encoding="utf-8")
    failure = cp.poll()
    assert failure["ok"] is False
    state_lines = Path(directory, "cmd").read_text(encoding="utf-8").splitlines()
    assert state_lines[0] == "set_state" and float(state_lines[1].split()[0]) == 20.
    Path(directory, "ack").write_text("OK set_state done\n", encoding="utf-8")
    assert cp.poll()["ok"] is True
    assert Path(directory, "cmd").read_text(encoding="utf-8").splitlines()[0] == "resume"
    failed_dependency = {"status": "FAIL_REPRODUCED_LOCAL",
                         "initial_cmd_preserved": "reprocess",
                         "before_fail_outbox": ["set_state", "resume"],
                         "reprocess_ack": failure["ack"], "command_after_fail": state_lines[0],
                         "state_payload_x": float(state_lines[1].split()[0]),
                         "trusted_repaired_tail_x": 2., "command_after_set_state_ack": "resume",
                         "scope": "Actual target driver/client, simulated full gate report; no deployed accepted run"}

archive_path = "docs/review_20261112_accepted_chain"
archive_listing = git("ls-tree", "-r", "--name-only", TARGET, "--", archive_path).decode().splitlines()
assert not archive_listing
payload = {"target": TARGET, "comparison_base": "70f68fbc3450569677659e8220d34fa2e3abaa4b",
           "worktree_head": git("rev-parse", "HEAD").decode().strip(), "loaded_sources": sources,
           "source_loading": "Target Git blobs in memory; other package dependencies unchanged",
           "command": "python -B -W ignore docs/review_20261112_bbe916f/run_checks.py", "exit": 0,
           "selected_tests": {"status": "PASS_LOCAL", "count": result.testsRun},
           "absolute_trigger_control": absolute_trigger,
           "skipped_scripted_test": "BLOCKED_LOCAL_pytest_dependency; actual-node control used instead, no installation/shim",
           "serialized_success": success, "failed_reprocess_dependency": failed_dependency,
           "reported_accepted_run_archive": {"status": "UNAVAILABLE_IN_TARGET", "path": archive_path},
           "actual_measurement_repair_native_two_event": "NOT_VERIFIED",
           "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED"}
assert not OUT.exists()
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
