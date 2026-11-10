"""Normal writeback orchestration controls; simulated reports are not gate/host success evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
REV = '930563d31b826420fd6960e5b240f7c5b1b3f5f5'
relative = 'slam_recovery/ros/recovery_node.py'
expected = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{REV}:{relative}'])
assert hashlib.sha256(expected).digest() == hashlib.sha256(
    (ROOT / relative).read_bytes().replace(b'\r\n', b'\n')).digest()
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import RecoveryState
from slam_recovery.ros.recovery_node import NativeClosedLoop
from slam_recovery.tests.test_checkpoint_client import WritebackTest

suite = unittest.TestSuite([
    WritebackTest('test_identity_rotation_is_the_identity_quaternion'),
    WritebackTest('test_ninety_degrees_about_z'),
])
result = unittest.TextTestRunner(verbosity=1).run(suite)
assert result.wasSuccessful()

class Recorder:
    enabled = True
    def __init__(self, reprocess_ok=True):
        self.events = []
        self._last_snapshot_wall = 0.
        self.reprocess_ok = reprocess_ok
    def hold(self): return {'command': 'hold', 'ok': True}
    def reprocess(self):
        event = {'command': 'reprocess', 'ok': self.reprocess_ok, 'simulated_ack': True}
        self.events.append(event)
        return event
    def restore(self): return {'command': 'restore', 'ok': True}
    def set_state(self, pose):
        event = {'command': 'set_state', 'pose_x': float(pose[0, 3]),
                 'ok': True, 'simulated_ack': True}
        self.events.append(event)
        return event

def case(label, partial=False, reprocess_ok=True):
    manager = SimpleNamespace(trusted_poses={}, trusted_version=0, active_quarantine=None,
                              confirmation_margin_ns=2_000_000_000, state=RecoveryState.HEALTHY,
                              lifecycle_events=[])
    repaired1, repaired2 = np.eye(4), np.eye(4)
    repaired1[0, 3], repaired2[0, 3] = 1., 2.
    committed = [1] if partial else [1, 2]
    report = SimpleNamespace(accepted=True, mode='MODE2', reason='simulated gate report',
                             committed_pose_keys=committed, deferred_pose_keys=[2] if partial else [],
                             partial_commit=partial, evidence_status='PASSED')
    def evaluate(candidate_id, repaired, **kwargs):
        assert np.isclose(repaired[1][0, 3], 1.) and np.isclose(repaired[2][0, 3], 2.)
        manager.trusted_poses = {k: repaired[k].copy() for k in committed}
        manager.trusted_version += 1
        if partial:
            manager.active_quarantine = object()
            manager.state = RecoveryState.WAITING_FOR_EVIDENCE
        return report
    node = SimpleNamespace(tx_mgr=manager, sigma_meas_m=.12, _kf_timestamps={},
                           last_paired_evidence={}, evaluate_and_commit_candidate=evaluate)
    cp = Recorder(reprocess_ok)
    loop = NativeClosedLoop(node, 'review-only', candidate_source='icp_reregistration',
                            checkpoint_client=cp)
    old1, old2 = np.eye(4), np.eye(4)
    old1[0, 3], old2[0, 3] = 10., 20.
    loop._open_episode(10_000_000_000, old1)
    loop._open.frames = [(1, 10_000_000_000, old1), (2, 11_000_000_000, old2)]
    loop._icp_candidate = lambda ep: ({1: repaired1, 2: repaired2}, {'status': 'synthetic normal correction'})
    row = loop.decide(12_000_000_000, 'review-only')
    assert row['accepted'] and cp.events[-1]['pose_x'] == 20.
    return {'case': label, 'committed_keys': row['committed_pose_keys'],
            'deferred_keys': row['deferred_pose_keys'],
            'trusted_pose_x': {str(k): float(p[0, 3]) for k, p in manager.trusted_poses.items()},
            'repairer_pose_x': {'1': 1., '2': 2.},
            'native_actions': cp.events, 'manager_state': manager.state.value}

rows = [case('full_corrected_candidate'), case('partial_tail_deferred', partial=True),
        case('reprocess_failed', reprocess_ok=False)]
assert rows[1]['committed_keys'] == [1] and rows[1]['native_actions'][-1]['pose_x'] == 20.
assert not rows[2]['native_actions'][0]['ok'] and rows[2]['native_actions'][1]['command'] == 'set_state'
print(json.dumps({'target': REV, 'scope': 'local source-pin and simulated normal driver reports; no ROS/native host',
                  'selected_tests_passed': result.testsRun, 'controls': rows,
                  'note': 'Zero exit means wrong writeback source reproduced, not a repair or gate PASS'}, indent=2))
