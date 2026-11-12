"""Small driver controls and source-bound replay bookkeeping illustration; no host build/run."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'd193680aa6f3bb7945e8bf01fdd2d8932819c49c'
BASE = '64bfed115f7d2058bbfe076caf103491036560c1'

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
    module = ModuleType(name)
    module.__file__ = str(ROOT / path)
    module.__package__ = name.rpartition('.')[0]
    sys.modules[name] = module
    exec(compile(raw, TARGET + ':' + path, 'exec'), module.__dict__)
    return module
cloud = load('slam_recovery.ros.cloud_repair', 'slam_recovery/ros/cloud_repair.py')
recovery = load('slam_recovery.ros.recovery_node', 'slam_recovery/ros/recovery_node.py')
cloud_tests = load('slam_recovery.tests.test_cloud_repair', 'slam_recovery/tests/test_cloud_repair.py')
identity = np.eye(4)

with tempfile.TemporaryDirectory(prefix='terminal-client-review-') as directory:
    cp = recovery.CheckpointClient(directory)
    loop = recovery.NativeClosedLoop(SimpleNamespace(sigma_meas_m=.12,
                     tx_mgr=SimpleNamespace(confirmation_margin_ns=2_000_000_000)),
                     'open-client-control', checkpoint_client=cp)
    loop._open_episode(1_000_000_000, identity)
    assert Path(directory, 'cmd').read_text().splitlines()[0] == 'hold'
    assert [entry[1] for entry in cp._outbox] == ['snapshot']
    Path(directory, 'ack').write_text('OK hold done\n')
    assert cp.poll()['ok']
    assert Path(directory, 'cmd').read_text().splitlines()[0] == 'snapshot'
    Path(directory, 'ack').write_text('OK snapshot done\n')
    assert cp.poll()['ok']
    event = cp.reprocess(1627785280281185627)
    lines = Path(directory, 'cmd').read_text().splitlines()
    assert lines == ['reprocess', '1627785280281185627']
    Path(directory, 'ack').write_text('OK reprocess done\n')
    assert cp.poll() is event
    cp.reprocess()
    assert Path(directory, 'cmd').read_text().splitlines() == ['reprocess', '']
    client = {'status': 'PASS_LOCAL', 'physical_order': ['hold', 'snapshot', 'reprocess'],
              'end_payload': '1627785280281185627', 'default_payload': '',
              'scope': 'Actual target client/episode open with file ACKs; no native timestamp-equivalence claim'}

class CP:
    def __init__(self):
        self.counts = [0, 1]
    def read_repair_received(self, timeout_s=1):
        return self.counts.pop(0)
    def wait_for_repair_count(self, n, timeout_s=5):
        return n == 1
node = SimpleNamespace(sigma_meas_m=.12, tx_mgr=SimpleNamespace(confirmation_margin_ns=2_000_000_000))
loop = recovery.NativeClosedLoop(node, 'sham-control', repair_sham=True)
loop.cp = CP()
loop._estimate_repair_bias = lambda ep: {'bias_z_m': .4, 'frames_estimated': 1}
ep = recovery.Episode(0, 1000, identity, 2000)
ep.frames = [(1, 1000, identity)]
msg = cloud_tests._Cloud()
msg.set_points(cloud_tests.ROWS)
loop._scan_index[1] = (1000, msg)
published = []
loop.publish_repair = published.append
rep = loop._publish_repaired_scans(ep)
assert rep['sham'] and rep['synced'] and rep['repair_shift_z_m'] == 0
assert len(published) == 1 and bytes(published[0].data) == bytes(msg.data)
sham = {'status': 'PASS_LOCAL', 'shift_m': 0, 'entire_point_data_unchanged': True,
        'scope': 'Actual target publisher with synthetic estimate/receipt; not proof identical runtime timing'}

# Bind the newly added skip to the existing clear using actual archived C++ source.
# This arithmetic is a small semantic illustration, not execution of the native estimator.
path = 'docs/review_20261112_four_host/host_change_terminal_stamp/deployed_host_v2.diff'
raw = git('show', TARGET + ':' + path)
loaded[path] = hashlib.sha256(raw).hexdigest()
text = raw.decode()
body = text[text.index('+bool LIVMapper::reprocessCheckpoint'):text.index('+std::string LIVMapper::checkpointStatus')]
assert '++truncated;\n+      continue;' in body
assert 'replay_buffer_.clear();' in body and 'replay_capture_ = false;' in body
assert body.index('++truncated;') < body.index('replay_buffer_.clear();')
end_ns = 2_000_000_000
captured = [1_000_000_000, 2_000_000_000, 3_000_000_000, 4_000_000_000]
replayed = [stamp for stamp in captured if stamp <= end_ns]
skipped = [stamp for stamp in captured if stamp > end_ns]
retained_after_clear = []
next_live_ns = 5_000_000_000
suffix = {'status': 'SOURCE_CONFIRMED_WITH_BOOKKEEPING_ILLUSTRATION',
          'captured_ns': captured, 'bounded_replayed_ns': replayed,
          'already_consumed_skipped_ns': skipped, 'retained_after_clear': retained_after_clear,
          'next_live_ns': next_live_ns,
          'scope': 'New C++ truncation skips consumed suffix, then existing clear discards it. Does not compute actual dynamics/trajectory; archived truncated451/509 separately corroborate affected population.'}
payload = {'target': TARGET, 'base': BASE, 'loaded_sources_sha256': loaded,
           'command': 'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_d193680/run_checks.py',
           'exit': 0, 'client_endpoint': client, 'sham_publisher': sham, 'truncated_suffix': suffix,
           'new_checkpoint_multicommand_test': 'NOT_RUN: Windows fake host renames over existing cmd.done; manual file protocol control avoids modifying target test/production',
           'repair_sync_tests': 'NOT_RUN: imports pytest-dependent helper; no installation/shim',
           'unchanged_tests': 'Prior accepted components not rerun', 'no_native_host_or_bag_execution': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(payload, ensure_ascii=False, indent=2))
