"""Small controls for changed batch and frame-freeze source only; no native/ROS run."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = '64bfed115f7d2058bbfe076caf103491036560c1'
BASE = '2f1f59bfdab1203a7ef6eb3eb2e72eb345a7b8cb'

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])

assert not git('diff', 'HEAD', '--', 'slam_recovery').strip()
assert not git('ls-files', '--others', '--exclude-standard', '--', 'slam_recovery').strip()
changed = set(git('diff', '--name-only', 'HEAD', TARGET, '--', 'slam_recovery').decode().splitlines())
assert changed <= {'slam_recovery/ros/cloud_repair.py', 'slam_recovery/ros/corrupt_relay.py',
                   'slam_recovery/ros/recovery_node.py', 'slam_recovery/ros/run_native_loop.sh',
                   'slam_recovery/tests/test_cloud_repair.py', 'slam_recovery/tests/test_frame_freeze.py',
                   'slam_recovery/tests/test_repair_sync.py'}
sys.path.insert(0, str(ROOT))
loaded = {}
def load(name, path):
    raw = git('show', TARGET + ':' + path)
    loaded[path] = hashlib.sha256(raw).hexdigest()
    mod = ModuleType(name)
    mod.__file__ = str(ROOT / path)
    mod.__package__ = name.rpartition('.')[0]
    sys.modules[name] = mod
    exec(compile(raw, TARGET + ':' + path, 'exec'), mod.__dict__)
    return mod

cloud = load('slam_recovery.ros.cloud_repair', 'slam_recovery/ros/cloud_repair.py')
recovery = load('slam_recovery.ros.recovery_node', 'slam_recovery/ros/recovery_node.py')
tests = load('slam_recovery.tests.test_cloud_repair', 'slam_recovery/tests/test_cloud_repair.py')
identity = np.eye(4)
class CP:
    def __init__(self, baseline, final, wait_results):
        self.counts = [baseline, final]
        self.results = list(wait_results)
        self.waits = []
    def read_repair_received(self, timeout_s=1):
        return self.counts.pop(0)
    def wait_for_repair_count(self, n, timeout_s=5):
        self.waits.append(n)
        return self.results.pop(0)

def batch(baseline, final, waits):
    node = SimpleNamespace(sigma_meas_m=.12, tx_mgr=SimpleNamespace(confirmation_margin_ns=2_000_000_000))
    loop = recovery.NativeClosedLoop(node, 'batch-source-control', repair_publish=True)
    loop.cp = CP(baseline, final, waits)
    loop._estimate_repair_bias = lambda ep: {'bias_z_m': .5, 'frames_estimated': 25}
    ep = recovery.Episode(0, 1000, identity, 2000)
    ep.frames = [(k, 1000 + k, identity) for k in range(25)]
    for k in range(25):
        msg = tests._Cloud()
        msg.header.stamp.nsecs = 1000 + k
        msg.set_points([(1., 2., .5, .5, .01, 7)])
        loop._scan_index[k] = (1000 + k, msg)
    published = []
    loop.publish_repair = published.append
    proceed, rep = loop._repair_gate(ep, accepted=True)
    return loop, proceed, rep, published

loop, proceed, rep, msgs = batch(25, 50, [True, True, True])
assert proceed and rep['synced'] and loop.cp.waits == [35, 45, 50]
assert [b['in_batch'] for b in rep['batches']] == [10, 10, 5]
assert [m.header.stamp.nsecs for m in msgs] == list(range(1000, 1025))
assert np.frombuffer(msgs[0].data, dtype=np.uint8).reshape(-1, 24)[:, 8:12].copy().view(np.float32).item() == 0
positive = {'status': 'PASS_LOCAL', 'baseline': 25, 'final': 50, 'expected_per_batch': loop.cp.waits,
            'batch_sizes': [10, 10, 5], 'header_order_preserved': True,
            'scope': 'Actual target batch/gate with synthetic valid bias and receipt results; not host execution'}

loop, proceed, rep, msgs = batch(25, 35, [True, False])
assert not proceed and not rep['synced'] and len(msgs) == 20 and loop.cp.waits == [35, 45]
partial = {'status': 'PASS_LOCAL', 'published_before_stop': len(msgs), 'expected_per_batch': loop.cp.waits,
           'reason': rep['reason'], 'scope': 'Synthetic receipt failure stops remaining batch; no native state/lifecycle claim'}

# Old host cumulative count 25, current clouds not received. A normal status timeout loses
# the baseline; the existing old count can satisfy every wait and the final equality.
loop, proceed, rep, msgs = batch(None, 25, [True, True, True])
assert proceed and rep['synced'] and loop.cp.waits == [10, 20, 25]
missing = {'status': 'FAIL_REPRODUCED_LOCAL', 'baseline': None, 'old_host_received': 25,
           'current_event_received': 0, 'published': len(msgs), 'expected_per_batch': loop.cp.waits,
           'final_received': rep['final_received'], 'synced': rep['synced'], 'gate_proceed': proceed,
           'scope': 'Actual target publisher/gate, simulated delayed status baseline and old receipts; not observed in four archives'}

node = SimpleNamespace(sigma_meas_m=.12, tx_mgr=SimpleNamespace(confirmation_margin_ns=2_000_000_000))
a, b = recovery.NativeClosedLoop(node, 'freeze-a'), recovery.NativeClosedLoop(node, 'freeze-b')
for loop in (a, b):
    loop._open = recovery.Episode(0, 1_000_000_000, identity, 3_000_000_000)
    for k in range(30):
        loop._track_episode(k, 1_000_000_000 + k * 100_000_000, identity)
    wall = loop._pending_decision_wall
    for k in range(30, 45):
        loop._track_episode(k, 1_000_000_000 + k * 100_000_000, identity)
    ep = loop._open
    assert ep.frozen and ep.frozen_at_ns == 3_000_000_000 and len(ep.frames) == 21
    assert len(ep.frozen_frames) == 21 and ep.frames_after_freeze == 24
    assert wall == loop._pending_decision_wall
assert [k for k, _, _ in a._open.frames] == [k for k, _, _ in b._open.frames]
freeze = {'status': 'PASS_LOCAL', 'frozen_at_ns': a._open.frozen_at_ns, 'candidate_frames': 21,
          'later_frames_not_added': 24, 'first_pending_wall_not_overwritten': True,
          'scope': 'Actual target tracking with identical synthetic timestamps; does not prove native replay extent or all pending ownership'}

payload = {'target': TARGET, 'base': BASE, 'loaded_sources_sha256': loaded,
           'source_loading': 'Target Git blobs in memory; remaining package source unchanged',
           'command': 'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_64bfed1/run_checks.py',
           'exit': 0, 'batch_nonzero_baseline': positive, 'batch_partial_receipt': partial,
           'missing_baseline_skill_finding': missing, 'candidate_freeze': freeze,
           'target_test_modules': 'NOT_RUN: frame_freeze and repair_sync import pytest-dependent helpers; no install/shim; direct target controls used',
           'unchanged_cloud_tests': 'Previously accepted; not rerun', 'native_host_or_bag_execution': False}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(payload, ensure_ascii=False, indent=2))
