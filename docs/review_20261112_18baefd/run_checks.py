"""Target-bound small controls; no ROS, native host, bag or parameter experiment."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import threading
import time
from types import ModuleType, SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = "18baefd89e70a65b1a493b0c1e532558b6bff6e0"
BASE = "f48b23f66707e9491350c1c62972fbf542f94fa3"
OUT = Path(__file__).with_name("local_checks.json")

def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])

def blob(path, version=TARGET):
    return git("show", version + ":" + path)

allowed = {"slam_recovery/ros/cloud_repair.py", "slam_recovery/ros/corrupt_relay.py",
           "slam_recovery/ros/recovery_node.py", "slam_recovery/ros/run_native_loop.sh",
           "slam_recovery/tests/test_cloud_repair.py", "slam_recovery/tests/test_repair_sync.py"}
changed = set(git("diff", "--name-only", "HEAD", TARGET, "--", "slam_recovery").decode().splitlines())
assert changed <= allowed, changed
assert not git("diff", "HEAD", "--", "slam_recovery").strip()
assert not git("ls-files", "--others", "--exclude-standard", "--", "slam_recovery").strip()
sys.path.insert(0, str(ROOT))
loaded = {}

def load(name, path):
    raw = blob(path)
    loaded[path] = {"git_blob": git("rev-parse", TARGET + ":" + path).decode().strip(),
                    "sha256": hashlib.sha256(raw).hexdigest()}
    module = ModuleType(name)
    module.__file__ = str(ROOT / path)
    module.__package__ = name.rpartition(".")[0]
    sys.modules[name] = module
    exec(compile(raw, TARGET + ":" + path, "exec"), module.__dict__)
    return module

cloud = load("slam_recovery.ros.cloud_repair", "slam_recovery/ros/cloud_repair.py")
recovery = load("slam_recovery.ros.recovery_node", "slam_recovery/ros/recovery_node.py")
cloud_tests = load("slam_recovery.tests.test_cloud_repair", "slam_recovery/tests/test_cloud_repair.py")
suite = unittest.defaultTestLoader.loadTestsFromModule(cloud_tests)
started = time.perf_counter()
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
unit = {"status": "PASS_LOCAL", "count": result.testsRun,
        "seconds": time.perf_counter() - started,
        "scope": "Target cloud helpers on declared little-endian packed Velodyne layout"}

# Same full-acceptance control as the prior review, with a real target client and driver.
# Only the gate outcome is simulated, isolating the new publish/sync-to-native boundary.
from slam_recovery.core import RecoveryState

def scenario(directory, sync, available=True):
    mgr = SimpleNamespace(trusted_poses={}, trusted_version=0, active_quarantine=object(),
                          confirmation_margin_ns=2_000_000_000,
                          state=RecoveryState.QUARANTINED, lifecycle_events=[])
    report = SimpleNamespace(accepted=True, mode="MODE2", reason="synthetic full acceptance",
                             committed_pose_keys=[1, 2], deferred_pose_keys=[],
                             partial_commit=False, evidence_status="PASSED")
    def evaluate(candidate_id, poses, **kwargs):
        mgr.trusted_poses = {k: p.copy() for k, p in poses.items()}
        mgr.trusted_version += 1
        mgr.active_quarantine = None
        mgr.state = RecoveryState.HEALTHY
        mgr.lifecycle_events.append({"event": "commit_closed", "segment_id": "synthetic", "n_committed": 2})
        return report
    node = SimpleNamespace(tx_mgr=mgr, sigma_meas_m=.12, _kf_timestamps={},
                           last_paired_evidence={}, evaluate_and_commit_candidate=evaluate)
    cp = recovery.CheckpointClient(directory)
    loop = recovery.NativeClosedLoop(node, "local-control", checkpoint_client=cp,
                                    repair_publish=True)
    ep = recovery.Episode(0, 10_000_000_000, np.eye(4), 12_000_000_000)
    ep.frames = [(1, 10_000_000_000, np.eye(4)), (2, 11_000_000_000, np.eye(4))]
    loop._open = ep
    loop.episodes = [ep]
    loop._last_icp_delta = np.eye(4)
    msg = cloud_tests._Cloud()
    msg.set_points(cloud_tests.ROWS)
    if available:
        loop._scan_index = {1: (1001, msg), 2: (1002, msg)}
    published = []
    loop.publish_repair = published.append
    cp.wait_for_repair_count = lambda *args, **kwargs: sync
    return loop, ep, cp, mgr, published

with tempfile.TemporaryDirectory(prefix="repair-sync-positive-") as directory:
    loop, ep, cp, mgr, published = scenario(directory, True)
    assert loop.decide(12_000_000_000, "review")['accepted']
    assert ep.meta['repair_publish']['synced'] and len(published) == 2
    assert [v['command'] for v in cp._pending] == ['reprocess']
    assert [v[1] for v in cp._outbox] == ['set_state']
    positive = {"status": "PASS_LOCAL", "published": 2, "physical_first_command": "reprocess",
                "scope": "Actual target driver/client, synthetic gate and successful receipt; not native execution"}

with tempfile.TemporaryDirectory(prefix="repair-zero-control-") as directory:
    loop, ep, cp, mgr, published = scenario(directory, False, available=False)
    assert loop.decide(12_000_000_000, "review")['accepted']
    assert ep.meta['repair_publish']['published'] == 0 and not published
    assert Path(directory, 'cmd').read_text().splitlines()[0] == 'reprocess'
    zero = {"status": "FAIL_REPRODUCED_LOCAL", "published": 0,
            "missing_clouds": ep.meta['repair_publish']['missing_clouds'],
            "synced": ep.meta['repair_publish']['synced'], "physical_command": "reprocess",
            "scope": "Missing cached clouds on an otherwise accepted candidate; not observed in archived run"}

with tempfile.TemporaryDirectory(prefix="repair-timeout-control-") as directory:
    loop, ep, cp, mgr, published = scenario(directory, False)
    assert loop.decide(12_000_000_000, "review")['accepted']
    assert ep.meta['native_checkpoint_skipped'] == 'repair_sync_timeout'
    assert not Path(directory, 'cmd').exists()
    loop._apply_lifecycle()
    assert Path(directory, 'cmd').read_text().splitlines()[0] == 'resume'
    timeout = {"status": "FAIL_REPRODUCED_LOCAL", "published": len(published),
               "replay_sent": False, "trusted_version": mgr.trusted_version,
               "manager_state": mgr.state.value, "after_commit_closed_command": "resume",
               "scope": "Synthetic legal full commit + no receipt; actual target lifecycle sends resume; not archived failure"}

# One status response avoids the existing Windows fake-host rename(cmd, cmd.done) portability issue.
with tempfile.TemporaryDirectory(prefix="repair-cumulative-control-") as directory:
    cp = recovery.CheckpointClient(directory)
    errors = []
    def host():
        try:
            deadline = time.time() + 3
            path = Path(directory, 'cmd')
            while not path.exists() and time.time() < deadline:
                time.sleep(.005)
            assert path.read_text().splitlines()[0] == 'status'
            path.rename(Path(directory, 'cmd.done'))
            Path(directory, 'ack').write_text('OK status repair_received=25 repair_applied=25 repair_queued=0\n')
        except BaseException as exc:
            errors.append(str(exc))
    worker = threading.Thread(target=host)
    worker.start()
    synced = cp.wait_for_repair_count(25, timeout_s=2)
    worker.join(timeout=3)
    assert not worker.is_alive() and not errors and synced
    cumulative = {"status": "FAIL_REPRODUCED_LOCAL", "old_received": 25,
                  "current_event_received": 0, "current_event_expected": 25,
                  "method_returned_synced": synced,
                  "scope": "Actual target file-client; simulated second event with only previous cumulative receipt"}

# Exact, favourable translation-only example, not a claim about the archived ICP fit.
# A +0.5 body-z corruption and independently correct pose need either a -0.5 pose correction
# OR a -0.5 measurement correction. Applying both changes the world point twice.
pose = np.eye(4)
delta = np.eye(4)
delta[2, 3] = -.5
msg = cloud_tests._Cloud()
msg.set_points([(0., 0., 1., .5, .01, 7)])
bad = cloud.shift_z_cloud(msg, .5)
bias, _ = cloud.body_z_bias([(1, 0, pose)], delta)
fixed = cloud.shift_z_cloud(bad, bias)
z_bad = np.frombuffer(bad.data, dtype=np.uint8).reshape(-1, 24)[:, 8:12].copy().view(np.float32).item()
z_fixed = np.frombuffer(fixed.data, dtype=np.uint8).reshape(-1, 24)[:, 8:12].copy().view(np.float32).item()
gate_world_z = float(((delta @ pose) @ np.array([0., 0., z_bad, 1.]))[2])
repaired_candidate_world_z = float(((delta @ pose) @ np.array([0., 0., z_fixed, 1.]))[2])
assert bias == -.5 and z_fixed == 1 and gate_world_z == 1 and repaired_candidate_world_z == .5
geometry = {"status": "FAIL_REPRODUCED_LOCAL", "clean_world_z": 1., "corrupted_body_z": z_bad,
            "delta_z": -.5, "producer_bias_z": bias, "repaired_body_z": z_fixed,
            "gate_candidate_on_raw_scan_world_z": gate_world_z,
            "same_candidate_on_published_repair_world_z": repaired_candidate_world_z,
            "scope": "Exact arithmetic with target producer; illustrates pose/measurement consistency, not observed causal diagnosis"}

prefix = 'docs/review_20261112_four_host/'
checks = []
for line in blob(prefix + 'SHA256SUMS').decode().splitlines():
    expected, path = line.split(maxsplit=1)
    path = str(PurePosixPath(path.lstrip('*')))
    assert not path.startswith('/') and '..' not in PurePosixPath(path).parts
    if path.startswith('injection_repair_20261112/') or path == 'README.md':
        checks.append({'path': path, 'ok': hashlib.sha256(blob(prefix + path)).hexdigest() == expected})
assert checks and all(v['ok'] for v in checks)
run_version = 'cd90e127f276922e59f8c402d377f561c4b68c67'
recorded_sha = blob(prefix + 'injection_repair_20261112/recovery_node_source.sha256').decode().split()[0]
source_binding = {"reported_run_version": run_version, "recorded_driver_sha256": recorded_sha,
                  "target_driver_sha256": loaded['slam_recovery/ros/recovery_node.py']['sha256'],
                  "run_version_driver_sha256": hashlib.sha256(blob('slam_recovery/ros/recovery_node.py', run_version)).hexdigest()}
source_binding['matches_target_driver'] = recorded_sha == source_binding['target_driver_sha256']
source_binding['matches_run_version_driver'] = recorded_sha == source_binding['run_version_driver_sha256']
payload = {"target": TARGET, "comparison_base": BASE,
           "worktree_head": git('rev-parse', 'HEAD').decode().strip(), "loaded_sources": loaded,
           "source_loading": "Target Git blobs in memory, unchanged package dependencies from worktree",
           "command": 'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_18baefd/run_checks.py',
           "initial_attempt": "python -I exit1: numpy unavailable on isolated sys.path; no dependency installation. This authored source-control script uses the existing repository Python environment; archives are read as bytes only.",
           "exit": 0, "cloud_tests": unit, "positive_publish": positive,
           "zero_publish_replay": zero, "sync_failure_release": timeout,
           "cumulative_receipt": cumulative, "pose_measurement_consistency": geometry,
           "new_archive_integrity": {"matched": sum(v['ok'] for v in checks), "total": len(checks),
                                     "checks": checks, "scope": "16 injection records + updated README only; not external bag/binary"},
           "archive_source_binding": source_binding,
           "repair_sync_test_module": "NOT_RUN: imports pytest-dependent test_recovery_node; no install/shim; small actual-target controls used",
           "no_native_host_or_bag_execution": True}
assert not OUT.exists()
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(payload, ensure_ascii=False, indent=2))
