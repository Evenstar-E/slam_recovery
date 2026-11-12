"""Exact-target bounded scripted boundary control. No ROS, bag or native execution."""
import ast
import hashlib
import importlib.abc
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'd86e57df09c076e531cb2e4edabdc70daac6b668'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


class GitModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self):
        self.paths = set(git('ls-tree', '-r', '--name-only', TARGET, '--', 'slam_recovery').decode().splitlines())
        self.loaded = {}

    def find_spec(self, fullname, path=None, target=None):
        if not (fullname == 'slam_recovery' or fullname.startswith('slam_recovery.')):
            return None
        stem = fullname.replace('.', '/')
        source = stem + '/__init__.py' if stem + '/__init__.py' in self.paths else stem + '.py'
        if source not in self.paths:
            return None
        spec = importlib.util.spec_from_loader(fullname, self, is_package=source.endswith('/__init__.py'))
        spec.loader_state = source
        return spec

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        source = module.__spec__.loader_state
        raw = git('show', TARGET + ':' + source)
        self.loaded[source] = hashlib.sha256(raw).hexdigest()
        module.__file__ = str(ROOT / source)
        exec(compile(raw, TARGET + ':' + source, 'exec'), module.__dict__)


assert not git('diff', 'HEAD', '--', 'slam_recovery').strip()
finder = GitModules()
sys.meta_path.insert(0, finder)
from slam_recovery.ros.recovery_node import arm_scripted_checkpoints
from slam_recovery.tests.test_checkpoint_client import CheckpointWiringTest
suite = unittest.TestSuite([CheckpointWiringTest('test_every_scripted_stamp_gets_its_own_armed_checkpoint')])
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()


class Recorder:
    def __init__(self):
        self.calls = []

    def hold(self, stamp):
        self.calls.append(['hold', int(stamp)])

    def snapshot_now(self, stamp):
        self.calls.append(['snapshot', int(stamp)])


recorder = Recorder()
arm_scripted_checkpoints(recorder, [20_000_000_000, 10_000_000_000], margin_ns=4_000_000_000)
assert recorder.calls == [['hold', 6_000_000_000], ['snapshot', 6_000_000_000],
                           ['hold', 16_000_000_000], ['snapshot', 16_000_000_000]]
raw_driver = git('show', TARGET + ':slam_recovery/ros/recovery_node.py')
main = next(n for n in ast.parse(raw_driver).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
call = next(n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == 'arm_scripted_checkpoints')
assert len(call.args) == 3 and isinstance(call.args[2], ast.Attribute) and call.args[2].attr == 'confirmation_margin_ns'
v5_path = 'docs/review_20261112_four_host/host_change_replay_suffix_ack/deployed_host_v5.diff'
v6_path = 'docs/review_20261112_four_host/host_change_boundary_checkpoint/deployed_host_v6.diff'
v5 = git('show', TARGET + ':' + v5_path).decode()
v6 = git('show', TARGET + ':' + v6_path).decode()
# Full deployed diffs carry changed hunk/index metadata, so compare only added source lines.
v5_added = [line[1:] for line in v5.splitlines() if line.startswith('+') and not line.startswith('+++')]
v6_added = [line[1:] for line in v6.splitlines() if line.startswith('+') and not line.startswith('+++')]
assert '  cp_stamp_ = LidarMeasures.last_lio_update_time;' in v5_added
assert '  cp_stamp_ = (cp_last_processed_lio_ > 0.0 ? cp_last_processed_lio_' in v6_added
assert '                                            : LidarMeasures.last_lio_update_time);' in v6_added
assert '      cp_last_processed_lio_ = LidarMeasures.measures.back().lio_time;' in v6_added
assert '  double cp_last_processed_lio_ = -1.0;' in v6_added
payload = {'target': TARGET, 'exit': 0,
           'command': 'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_d86e57d/run_checks.py',
           'source_loading': 'All package imports loaded from exact target Git bytes',
           'loaded_sources_sha256': finder.loaded, 'selected_tests': result.testsRun,
           'scripted_trigger_10s_margin_4s': {'status': 'PASS_LOCAL', 'queued_calls': recorder.calls,
                                            'scope': 'Command target arithmetic, not native application or state equivalence'},
           'main_wiring': 'PASS_SOURCE_passes_actual_loop_confirmation_margin',
           'host_v6_timestamp_change': {'status': 'PASS_SOURCE', 'v5_sha256': hashlib.sha256(v5.encode()).hexdigest(),
                                        'v6_sha256': hashlib.sha256(v6.encode()).hexdigest(),
                                        'scope': 'Declared full patch source only, no C++ build/runtime executed here'},
           'online_checkpoint_boundary': 'NOT_VERIFIED_by_scripted_prearming',
           'old_failed_unknown_ack_branch': 'UNCHANGED_not_retested_preserve_70e3e7c_scope',
           'no_native_host_bag_or_parameter_execution': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in payload.items() if k != 'loaded_sources_sha256'}, ensure_ascii=False))
