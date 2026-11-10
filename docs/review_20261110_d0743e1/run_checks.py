"""Known-layout repaired-scan byte check with a local message double, not a ROS/native run."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
REV = 'd0743e13b05c2535673de79739f0e3db1a0a9bd5'
REL = 'slam_recovery/ros/inject_repaired_scan.py'
source = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{REV}:{REL}'])
assert hashlib.sha256(source).digest() == hashlib.sha256(
    (ROOT / REL).read_bytes().replace(b'\r\n', b'\n')).digest()
sys.path.insert(0, str(ROOT))
import numpy as np

# Load only the known-layout byte helper, with a test message type; no rospy/subscriber/host.
node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'shift_cloud')
namespace = {'np': np}
exec(compile(ast.Module(body=[node], type_ignores=[]), REL, 'exec'), namespace)
msg_module = ModuleType('sensor_msgs.msg')
msg_module.PointCloud2 = SimpleNamespace
sensor_module = ModuleType('sensor_msgs')
sensor_module.msg = msg_module
records = np.arange(4 * 24, dtype=np.uint8).reshape(4, 24)
z = records[:, 8:12].view(np.float32).reshape(-1)
z[:] = [-.5, 0., 1., 4.]
header = SimpleNamespace(stamp=SimpleNamespace(secs=10, nsecs=123), frame_id='lidar')
msg = SimpleNamespace(data=records.tobytes(), point_step=24, header=header,
                      fields=['known 24-byte x/y/z/intensity/time/ring layout'])
original = records.copy()
with patch.dict(sys.modules, {'sensor_msgs': sensor_module, 'sensor_msgs.msg': msg_module}):
    shifted = namespace['shift_cloud'](msg, 1.)
out = np.frombuffer(shifted.data, dtype=np.uint8).reshape(-1, 24)
keep = [i for i in range(24) if i not in range(8, 12)]
assert np.array_equal(original[:, keep], out[:, keep])
assert np.allclose(out[:, 8:12].view(np.float32).reshape(-1), [-.5+1, 1., 2., 5.])
assert shifted.header is header and shifted.point_step == 24
old_patch = subprocess.check_output(['git', '-C', str(ROOT), 'show',
    'e2db4b3:docs/review_20261110_native_checkpoint/fastlivo2_worktree.diff'])
current_patch = subprocess.check_output(['git', '-C', str(ROOT), 'show',
    f'{REV}:docs/review_20261110_native_checkpoint/fastlivo2_worktree.diff'])
assert old_patch == current_patch
print(json.dumps({'target': REV, 'scope': 'known-layout helper with local test message; no ROS/native host',
                  'byte_control': {'status': 'PASS', 'records': 4, 'point_step': 24,
                                   'unchanged_offsets': keep, 'header_preserved': True},
                  'host_patch_unchanged': True,
                  'host_patch_sha256': hashlib.sha256(current_patch).hexdigest(),
                  'smoke_defaults': {'play_duration_bag_s': 26, 'rate': .5,
                                     'play_duration_wall_s': 52, 'fixed_sleeps_before_reprocess_s': 52,
                                     'note': 'Ack costs add delay; exact run duration/config needs receipt'},
                  'native_replacement': 'DEVELOPER_REPORTED 10/20, not locally verified'}, indent=2))
