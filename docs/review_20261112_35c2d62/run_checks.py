"""Bounded exact-target refusal metadata control; no ROS or native execution."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
TARGET = '35c2d62b6412d5b651ef6d211a5c8d16a77cc5f1'
raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', TARGET + ':slam_recovery/ros/recovery_node.py'])
tree = ast.parse(raw)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeClosedLoop')
decide = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'decide')
branch = next(n for n in ast.walk(decide) if isinstance(n, ast.If) and any(
    isinstance(a, ast.Assign) and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                                    and t.slice.value == 'restore_disposition' for t in a.targets)
    for a in n.orelse))
wrapper = ast.parse('def control(self, ep, now_ts_ns):\n    pass\n').body[0]
wrapper.body = branch.orelse
module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
namespace = {}
exec(compile(module, TARGET + ':refusal_else_body', 'exec'), namespace)
actual_checkpoint_ns = 975
loop = SimpleNamespace(confirmation_margin_ns=20,
                       cp=SimpleNamespace(restore=lambda: {'command': 'restore', 'ok': True,
                                                         'ack': f'OK restore valid=1 stamp_ns={actual_checkpoint_ns} hold=1'}))
episode = SimpleNamespace(trigger_ts_ns=1_000, meta={})
namespace['control'](loop, episode, 1_500)
disposition = episode.meta['restore_disposition']
assert disposition['checkpoint_stamp_ns'] == 980
assert disposition['checkpoint_stamp_ns'] != actual_checkpoint_ns
assert disposition['catch_up'] == 'NOT_IMPLEMENTED'
payload = {'target': TARGET, 'command': 'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_35c2d62/run_checks.py',
           'source_sha256': hashlib.sha256(raw).hexdigest(),
           'source_loading': 'Only reviewed exact-target refusal else body compiled in memory',
           'changed_test': {'status': 'NOT_EXECUTED_LOCAL', 'reason': 'Target test module imports pytest, absent locally; initial import exit1; no installation or shim'},
           'normal_checkpoint_metadata_control': {'status': 'FAIL_REPRODUCED_METADATA', 'actual_restore_ack_stamp_ns': actual_checkpoint_ns,
                                                  'recorded_disposition': disposition,
                                                  'scope': 'Valid restore with earlier processed-group checkpoint; wrong provenance interval, not new input loss or actual native run'},
           'old_ack_writeback_behavior_not_retested': True, 'no_native_ROS_bag_parameter_or_archived_CLI_execution': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(payload, ensure_ascii=False, indent=2))
