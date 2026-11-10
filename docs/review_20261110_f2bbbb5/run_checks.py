"""Normal Python wiring controls only; no host, ROS, parameter tuning or production edits."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
REV = 'f2bbbb54faac950845e6543233cff4465e695060'
for name in ('slam_recovery/ros/recovery_node.py', 'slam_recovery/quarantine/manager.py',
             'slam_recovery/sim/transaction_manager_node.py'):
    expected = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{REV}:{name}'])
    assert hashlib.sha256(expected).digest() == hashlib.sha256(
        (ROOT / name).read_bytes().replace(b'\r\n', b'\n')).digest(), name
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import RecoveryState, TangentFrame
from slam_recovery.ros.recovery_node import CheckpointClient, NativeClosedLoop, candidate_detail_record
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.tests.test_checkpoint_client import CheckpointClientTest
from slam_recovery.tests.test_candidate_detail_record import TestCandidateDetailRecord

suite = unittest.TestSuite([
    CheckpointClientTest('test_a_silent_host_is_a_failure_not_a_success'),
    CheckpointClientTest('test_a_disabled_client_sends_nothing'),
    unittest.defaultTestLoader.loadTestsFromTestCase(TestCandidateDetailRecord),
])
result = unittest.TextTestRunner(verbosity=1).run(suite)
assert result.wasSuccessful()

# Two outstanding commands are queued as events, but share one physical command and ack file.
# No timing/race needed: a callback hold followed by a main-thread command overwrites the first.
with tempfile.TemporaryDirectory(prefix='review_cp_') as directory:
    client = CheckpointClient(directory)
    client.hold()
    client._write('restore')
    command_seen = (Path(directory) / 'cmd').read_text().strip()
    (Path(directory) / 'ack').write_text('OK restore done\n')
    first, second = client.collect(.1), client.collect(.1)
    assert command_seen == 'restore'
    assert first['command'] == 'hold' and first['ack'].startswith('OK restore')
    assert second['ok'] and client.holds == 1 and client.restores == 1
    mismatch = {'host_command': command_seen, 'events': [first, second],
                'counted_holds': client.holds, 'counted_restores': client.restores}

# service() treats its short collection poll as a final timeout, discarding the outstanding hold.
# A later hold acknowledgement is then eligible to be counted as the following restore.
with tempfile.TemporaryDirectory(prefix='review_cp_') as directory:
    client = CheckpointClient(directory)
    client.hold()
    poll = client.collect(.05)
    assert poll['error'] == 'ack_timeout' and not client._pending
    client._write('restore')
    (Path(directory) / 'ack').write_text('OK hold done\n')
    following = client.collect(.1)
    assert following['command'] == 'restore' and following['ok']
    late_ack = {'short_poll': poll, 'following_action': following,
                'counted_restores': client.restores, 'scope': 'deterministic staged ack, no threads'}

# A full accepted commit becomes HEALTHY without a manager rearm event. Only rearm sends resume.
class Recorder:
    enabled = True
    def __init__(self):
        self.commands = []
        self._last_snapshot_wall = 0.
    def _command(self, command):
        self.commands.append(command)
        return {'command': command, 'ok': True, 'simulated_ack': True}
    def hold(self): return self._command('hold')
    def reprocess(self): return self._command('reprocess')
    def restore(self): return self._command('restore')
    def resume(self): return self._command('resume')

manager = SimpleNamespace(trusted_poses={}, trusted_version=0, active_quarantine=None,
                          state=RecoveryState.HEALTHY, confirmation_margin_ns=2_000_000_000,
                          lifecycle_events=[])
report = SimpleNamespace(accepted=True, mode='MODE2', reason='simulated full commit',
                         committed_pose_keys=[1], deferred_pose_keys=[], evidence_status='PASSED')
node = SimpleNamespace(tx_mgr=manager, sigma_meas_m=.12, _kf_timestamps={},
                       last_paired_evidence={},
                       evaluate_and_commit_candidate=lambda *args, **kwargs: report)
cp = Recorder()
loop = NativeClosedLoop(node, 'review-only', checkpoint_client=cp)
loop._open_episode(10_000_000_000, np.eye(4))
loop._open.frames = [(1, 10_000_000_000, np.eye(4))]
row = loop.decide(12_000_000_000, 'review-only')
loop._apply_lifecycle()
assert row['accepted'] and cp.commands == ['hold', 'reprocess']
accepted = {'commands': cp.commands, 'manager_state': manager.state.value,
            'lifecycle_events': manager.lifecycle_events, 'gate_accepted': row['accepted'],
            'scope': 'simulated full commit orchestration; not host success'}

# Actual node filters support before selecting every fifth verified frame for info_after.
cloud = np.random.default_rng(0).normal(size=(400, 3)) * .16
node = OnlineRecoveryTransactionNode()
node.scan_buffer_body[0] = cloud.copy()
node.tx_mgr.trusted_poses[0] = np.eye(4)
node._sync_spatial_map_with_trusted_poses()
frame = TangentFrame('body', 'rot_trans', 'review-anchor')
node.tx_mgr.trigger_quarantine(0, 4_000_000_000, np.array([0., 0., 0., 1., 0., 0.]),
                               np.diag([60., 60., 60., 20., 40., 40.]), .1,
                               weak_direction_frame=frame, info_before_frame=frame,
                               anchor_pose_world=np.eye(4))
poses, incumbent, times = {}, {}, {}
for k in range(1, 8):
    pose = np.eye(4)
    if k == 4:
        pose[0, 3] = 10.
    poses[k] = pose
    incumbent[k] = pose.copy()
    incumbent[k][0, 3] += .12
    node.scan_buffer_body[k] = cloud.copy()
    times[k] = k * 100_000_000
    node._kf_timestamps[k] = times[k]
    node.tx_mgr.register_quarantined_frame(k, times[k])
node.evaluate_and_commit_candidate('review-set', poses, incumbent_poses=incumbent,
                                   reentry_anchor_pose=np.eye(4))
verified = [k for k in poses if k != 4]
actual_fim_keys = verified[::node.holdout_stride]
detail = candidate_detail_record('review-set', 4_000_000_000, 5_000_000_000,
                                  list(poses), times, poses)
assert node._last_holdout_support['candidate_frames_committable'] == 6
assert node._last_holdout_support['holdout_frames_total'] == 2
assert actual_fim_keys == [1, 7]
assert detail['candidate_frame_ids'] == list(range(1, 8))
print(json.dumps({'target': REV, 'scope': 'local normal controls; source-pin PASS',
                  'selected_tests_passed': result.testsRun,
                  'one_slot_ack_misattribution': mismatch,
                  'short_poll_late_ack_misattribution': late_ack,
                  'accepted_path_no_resume': accepted,
                  'candidate_detail_population': {
                      'recorded_input_keys': detail['candidate_frame_ids'],
                      'verified_keys': verified, 'info_after_keys': actual_fim_keys,
                      'actual_node_counts': node._last_holdout_support}}, indent=2))
