"""Small target source controls, no native host, ROS, bag or parameter sweep."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = '2f1f59bfdab1203a7ef6eb3eb2e72eb345a7b8cb'
changed = set(subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', 'HEAD', TARGET, '--', 'slam_recovery']).decode().splitlines())
assert changed <= {'slam_recovery/ros/cloud_repair.py', 'slam_recovery/ros/corrupt_relay.py',
                   'slam_recovery/ros/recovery_node.py', 'slam_recovery/ros/run_native_loop.sh',
                   'slam_recovery/tests/test_cloud_repair.py', 'slam_recovery/tests/test_repair_sync.py'}
assert not subprocess.check_output(['git', '-C', str(ROOT), 'diff', 'HEAD', '--', 'slam_recovery']).strip()
sys.path.insert(0, str(ROOT))
loaded = {}

def load(name, path):
    raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', TARGET + ':' + path])
    loaded[path] = hashlib.sha256(raw).hexdigest()
    module = ModuleType(name)
    module.__file__ = str(ROOT / path)
    module.__package__ = name.rpartition('.')[0]
    sys.modules[name] = module
    exec(compile(raw, TARGET + ':' + path, 'exec'), module.__dict__)
    return module

cloud = load('slam_recovery.ros.cloud_repair', 'slam_recovery/ros/cloud_repair.py')
recovery = load('slam_recovery.ros.recovery_node', 'slam_recovery/ros/recovery_node.py')
tests = load('slam_recovery.tests.test_cloud_repair', 'slam_recovery/tests/test_cloud_repair.py')
started = time.perf_counter()
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
assert result.wasSuccessful()
seconds = time.perf_counter() - started
plane = tests._plane()
bad_scan = tests._plane(z=.5)[::4]
identity = np.eye(4)

# Verify the skill's proposed finding with actual estimator, not injected return values.
node = SimpleNamespace(sigma_meas_m=.12, support_reference=lambda: plane,
                       scan_buffer_body={1: bad_scan, 2: bad_scan[:10], 3: bad_scan[:10]},
                       tx_mgr=SimpleNamespace(confirmation_margin_ns=2_000_000_000))
loop = recovery.NativeClosedLoop(node, 'small-reference-control')
loop._last_incumbent = {k: identity for k in (1, 2, 3)}
ep = recovery.Episode(0, 1_000, identity, 2_000)
ep.frames = [(k, 1_000, identity) for k in (1, 2, 3)]
est = loop._estimate_repair_bias(ep)
assert est['per_frame'][0]['bias_z_m'] == .5
assert est['per_frame'][1]['valid_points'] == 0 and est['per_frame'][2]['valid_points'] == 0
assert est['bias_z_m'] == 0 and est['frames_estimated'] == 3
invalid = {'status': 'FAIL_REPRODUCED_LOCAL', 'estimate': est,
           'scope': 'Actual target estimator: one supported +0.5 estimate, two nonempty low-support scans; invalid zero results become the median. Not the archived run, whose all n_valid>=27.'}

# Actual decide/publish/set_state payload, simulated legal gate and candidate geometry.
# A pose that has absorbed +0.5 measurement displacement places the raw plane correctly.
from slam_recovery.core import RecoveryState
host_pose = np.eye(4)
host_pose[2, 3] = -.5
mgr = SimpleNamespace(trusted_poses={900: identity.copy(), 901: identity.copy()}, trusted_version=1,
                      confirmation_margin_ns=2_000_000_000, state=RecoveryState.QUARANTINED,
                      active_quarantine=object(), lifecycle_events=[])
report = SimpleNamespace(accepted=True, mode='MODE2', reason='synthetic accepted raw candidate',
                         committed_pose_keys=[1], deferred_pose_keys=[], evidence_status='PASSED')
seen = {}
def evaluate(candidate_id, repaired, **kwargs):
    seen['gate_world_z'] = float((node.scan_buffer_body[1] @ repaired[1][:3, :3].T + repaired[1][:3, 3])[0, 2])
    return report
node = SimpleNamespace(sigma_meas_m=.12, tx_mgr=mgr, scan_buffer_body={1: bad_scan},
                       _kf_timestamps={900: 0, 901: 500_000_000}, last_paired_evidence={},
                       support_reference=lambda: plane, evaluate_and_commit_candidate=evaluate)
class CP:
    enabled = True
    _last_snapshot_wall = 0
    def wait_for_repair_count(self, *args, **kwargs):
        return True
    def reprocess(self):
        return {'command': 'reprocess'}
    def set_state(self, pose):
        seen['set_state_z'] = float(pose[2, 3])
        return {'command': 'set_state'}
loop = recovery.NativeClosedLoop(node, 'candidate-measurement-control', candidate_source='icp_reregistration',
                                checkpoint_client=CP(), repair_publish=True)
loop._icp_candidate = lambda ep: ({1: host_pose.copy()}, {'scope': 'synthetic absorbed pose'})
ep = recovery.Episode(0, 1_000_000_000, host_pose, 2_000_000_000)
ep.frames = [(1, 1_000_000_000, host_pose)]
loop._open = ep
msg = tests._Cloud()
msg.set_points([(float(x), float(y), float(z), 0., 0., 0) for x, y, z in bad_scan])
loop._scan_index = {1: (1001, msg)}
published = []
loop.publish_repair = published.append
assert loop.decide(2_000_000_000, 'review')['accepted']
assert ep.meta['repair_publish']['bias_z_m'] == .5
z_repaired = float(np.frombuffer(published[0].data, dtype=np.uint8).reshape(-1, 24)[:, 8:12].copy().view(np.float32).reshape(-1)[0])
seen['published_body_z'] = z_repaired
seen['candidate_pose_plus_repaired_cloud_world_z'] = z_repaired + seen['set_state_z']
assert seen['gate_world_z'] == 0 and seen['published_body_z'] == 0 and seen['candidate_pose_plus_repaired_cloud_world_z'] == -.5
geometry = {'status': 'FAIL_REPRODUCED_LOCAL', **seen, 'bias_m': .5, 'repair_shift_m': -.5,
            'scope': 'Actual target decide and producer; gate and host-absorbed ICP pose simulated, no host estimator execution. Accepted raw geometry differs from published repaired geometry; not an observed 0.5m error in archived run.'}
payload = {'target': TARGET, 'base': '18baefd89e70a65b1a493b0c1e532558b6bff6e0',
           'loaded_source_sha256': loaded, 'source_loading': 'Target Git blobs, unchanged worktree dependencies',
           'command': 'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_2f1f59b/run_checks.py',
           'exit': 0, 'cloud_tests': {'status': 'PASS_LOCAL', 'count': result.testsRun, 'seconds': seconds},
           'skill_finding_verification': invalid, 'candidate_measurement_mismatch': geometry,
           'repair_sync_tests': 'NOT_RUN: pytest-dependent helper and existing Windows fake-host rename issue; no install/shim',
           'no_native_host_or_bag_execution': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(payload, ensure_ascii=False, indent=2))
