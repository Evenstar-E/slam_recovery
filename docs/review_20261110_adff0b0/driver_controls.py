"""Read-only normal driver controls; simulated acknowledgements are not native runs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
REV = 'adff0b084b55cc29059bf3e91cb71230d6e30a72'
for path in ('slam_recovery/ros/recovery_node.py', 'slam_recovery/sim/transaction_manager_node.py'):
    expected = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{REV}:{path}'])
    assert hashlib.sha256(expected).digest() == hashlib.sha256(
        (ROOT / path).read_bytes().replace(b'\r\n', b'\n')).digest(), path
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import RecoveryState
from slam_recovery.ros.recovery_node import CheckpointClient, Episode, NativeClosedLoop
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.tests import test_checkpoint_client as cp_tests

# These test functions do not depend on pytest; call directly, without installing a runner.
with tempfile.TemporaryDirectory(prefix='slam_review_cp_') as directory:
    cp_tests.test_a_silent_host_is_a_failure_not_a_success(Path(directory))
    cp_tests.test_a_disabled_client_sends_nothing(Path(directory))

with tempfile.TemporaryDirectory(prefix='slam_review_cp_') as directory:
    client = CheckpointClient(directory)
    seen = []
    node = OnlineRecoveryTransactionNode()
    cloud = np.random.default_rng(0).normal(size=(400, 3)) * .16
    node.step_frame(1, 10_000_000_000, np.eye(4), cloud, 10.)
    assert node.detector.state == RecoveryState.SUSPECT
    assert node.tx_mgr.active_quarantine is None
    def capture(command):
        event = {'command': command, 'ok': True, 'simulated_ack': True,
                 'detector_state_at_command': node.detector.state.value}
        seen.append(event)
        return event
    client._send = capture
    loop = NativeClosedLoop(node, 'review-only', checkpoint_client=client)
    loop.service()
    assert seen[0]['command'] == 'snapshot'
    suspect_snapshot = seen[0]

# Decision orchestration only: a valid gate report is represented, not manufactured via tuning.
with tempfile.TemporaryDirectory(prefix='slam_review_cp_') as directory:
    client = CheckpointClient(directory)
    client._send = lambda command: {'command': command, 'ok': False,
                                   'error': 'ack_timeout', 'simulated_ack': True}
    manager = SimpleNamespace(trusted_poses={}, trusted_version=0,
                              active_quarantine=None, confirmation_margin_ns=2_000_000_000,
                              state=RecoveryState.HEALTHY)
    report = SimpleNamespace(accepted=True, mode='MODE2', reason='synthetic gate report',
                             committed_pose_keys=[1], deferred_pose_keys=[], evidence_status='PASSED')
    node = SimpleNamespace(tx_mgr=manager, sigma_meas_m=.12, _kf_timestamps={},
                           last_paired_evidence={},
                           evaluate_and_commit_candidate=lambda *args, **kwargs: report)
    loop = NativeClosedLoop(node, 'review-only', checkpoint_client=client)
    loop._open = Episode(0, 10_000_000_000, np.eye(4), 12_000_000_000)
    loop._open.frames = [(1, 10_000_000_000, np.eye(4))]
    row = loop.decide(12_000_000_000, 'review-only')
    assert row['accepted'] is True and loop.cp_actions[-1]['ok'] is False
    acceptance = {'candidate_record_accepted': row['accepted'],
                  'native_action': loop.cp_actions[-1],
                  'episode_decided': loop._open.decided}

print(json.dumps({'target': REV, 'scope': 'local simulated driver controls, no ROS/native host',
                  'direct_test_functions_passed': 2,
                  'suspect_snapshot': suspect_snapshot,
                  'accepted_record_survives_failed_native_ack': acceptance}, indent=2))
