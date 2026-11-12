"""Target-bound stamped-command controls only; no native host or parameter changes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'e82d90041c090dcb8a9df6402ebfdb98f465a0b8'
BASE = 'd193680aa6f3bb7945e8bf01fdd2d8932819c49c'

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])
assert not git('diff', 'HEAD', '--', 'slam_recovery').strip()
assert not git('ls-files', '--others', '--exclude-standard', '--', 'slam_recovery').strip()
allowed = {'slam_recovery/ros/cloud_repair.py', 'slam_recovery/ros/corrupt_relay.py',
           'slam_recovery/ros/recovery_node.py', 'slam_recovery/ros/run_native_loop.sh',
           'slam_recovery/tests/test_checkpoint_client.py', 'slam_recovery/tests/test_cloud_repair.py',
           'slam_recovery/tests/test_frame_freeze.py', 'slam_recovery/tests/test_repair_sync.py'}
assert set(git('diff', '--name-only', 'HEAD', TARGET, '--', 'slam_recovery').decode().splitlines()) <= allowed
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
load('slam_recovery.ros.cloud_repair', 'slam_recovery/ros/cloud_repair.py')
recovery = load('slam_recovery.ros.recovery_node', 'slam_recovery/ros/recovery_node.py')
tests = load('slam_recovery.tests._review_stamped', 'slam_recovery/tests/test_checkpoint_client.py')
# Single-response test is portable; do not modify the multi-command fake host's Windows rename.
result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([
    tests.CheckpointClientTest('test_a_deferred_ack_is_a_receipt')]))
assert result.wasSuccessful()
with tempfile.TemporaryDirectory(prefix='armed-receipt-review-') as directory:
    cp = recovery.CheckpointClient(directory)
    stamp = 1627785276215170145
    hold = cp.hold(stamp)
    snapshot = cp.snapshot_now(stamp)
    assert Path(directory, 'cmd').read_text().splitlines() == ['hold', str(stamp)]
    assert snapshot['wall'] is None
    Path(directory, 'ack').write_text('OK hold deferred stamp=' + str(stamp) + '\n')
    assert cp.poll() is hold and hold['ok']
    assert Path(directory, 'cmd').read_text().splitlines() == ['snapshot', str(stamp)]
    Path(directory, 'ack').write_text('OK snapshot deferred stamp=' + str(stamp) + '\n')
    assert cp.poll() is snapshot and snapshot['ok']
    receipt = {'status': 'PASS_LOCAL_RECEIPT_ONLY', 'stamp_ns': stamp,
               'hold_then_snapshot_payloads': True, 'client_pending_after_deferred_receipts': cp.pending(),
               'host_application_proven_by_this_control': False}
    cp.stop()
with tempfile.TemporaryDirectory(prefix='open-fallback-review-') as directory:
    cp = recovery.CheckpointClient(directory)
    node = SimpleNamespace(sigma_meas_m=.12, tx_mgr=SimpleNamespace(confirmation_margin_ns=2_000_000_000))
    loop = recovery.NativeClosedLoop(node, 'open-fallback', checkpoint_client=cp)
    loop._open_episode(1_000_000_000, np.eye(4))
    assert Path(directory, 'cmd').read_text().splitlines() == ['hold', '']
    assert not cp._outbox
    opening = {'status': 'PASS_LOCAL_DECLARED_FALLBACK', 'command': 'hold', 'snapshot_sent': False,
               'scope': 'Actual target opening, no prearming simulated. Online/next event does not obtain the first scripted timestamp guarantee.'}
raw = git('show', TARGET + ':slam_recovery/ros/recovery_node.py').decode()
assert 'first_trigger = int(min(loop.scripted_trigger_stamps_ns))' in raw
assert 'self.cp.reprocess(ep.frozen_at_ns + REPLAY_END_GRACE_NS)' in raw
patch_path = 'docs/review_20261112_four_host/host_change_deferred_stamp/deployed_host_v3.diff'
patch = git('show', TARGET + ':' + patch_path)
body = patch.decode().split('+bool LIVMapper::reprocessCheckpoint', 1)[1].split('+std::string LIVMapper::checkpointStatus', 1)[0]
assert '++truncated;\n+      continue;' in body and 'replay_buffer_.clear();' in body
payload = {'target': TARGET, 'base': BASE, 'source_loading': 'Target Git blobs with unchanged package dependencies',
           'loaded_sources_sha256': loaded,
           'command': 'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_e82d900/run_checks.py',
           'exit': 0, 'selected_tests': {'status': 'PASS_LOCAL', 'count': result.testsRun},
           'deferred_receipt': receipt, 'episode_open_fallback': opening,
           'first_scripted_trigger_only_prearmed': True, 'replay_end_grace_ns': recovery.REPLAY_END_GRACE_NS,
           'consumed_suffix_skip_and_clear_still_in_v3': True,
           'v3_patch_sha256': hashlib.sha256(patch).hexdigest(),
           'multicommand_checkpoint_tests': 'NOT_RUN_existing_Windows_fake_host_rename_over_cmd.done',
           'repair_sync_tests': 'NOT_RUN_pytest_helper_dependency_no_install_or_shim',
           'no_native_host_or_bag_execution': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(payload, ensure_ascii=False, indent=2))
