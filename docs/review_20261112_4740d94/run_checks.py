"""Exact Git-module loading for minimal prediction/invariance controls, no host execution."""
import hashlib
import importlib.abc
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = '4740d94a583886afc04b361aee3c6403d5072ecf'
BASE = '70531bef27467519e370ac4819609398f1933533'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


class GitModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, version):
        self.version = version
        self.paths = set(git('ls-tree', '-r', '--name-only', version, '--', 'slam_recovery').decode().splitlines())
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
        raw = git('show', self.version + ':' + source)
        self.loaded[source] = hashlib.sha256(raw).hexdigest()
        module.__file__ = str(ROOT / source)
        exec(compile(raw, self.version + ':' + source, 'exec'), module.__dict__)


def worker(version, enabled):
    finder = GitModules(version)
    sys.meta_path.insert(0, finder)
    from slam_recovery.ros.recovery_node import NativeClosedLoop
    from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
    with tempfile.TemporaryDirectory(prefix='predicted-support-review-') as directory:
        node = OnlineRecoveryTransactionNode()
        loop = NativeClosedLoop(node, run_id='source-control', availability_log=str(Path(directory, 'frames.jsonl')) if enabled else None)
        cloud = np.random.default_rng(12).normal(size=(400, 3)) * .4
        for i in range(12):
            pose = np.eye(4)
            pose[0, 3] = .005 * i
            stamp = 1_000_000_000 + i * 250_000_000
            loop.on_pair(stamp, pose, cloud, stamp)
        loop.availability.close()
        outcome = {'diag': loop.diag, 'counts': dict(loop.detection_counts), 'records': loop.records,
                   'nis_counts': loop.nis.counts, 'trusted_version': node.tx_mgr.trusted_version,
                   'trusted_keys': sorted(node.tx_mgr.trusted_poses)}
        logged = [json.loads(line) for line in Path(directory, 'frames.jsonl').read_text().splitlines()] if enabled else []
    predicted = None
    if version == TARGET:
        t0, t1 = np.eye(4), np.eye(4)
        t1[0, 3] = 2
        fake = SimpleNamespace(node=SimpleNamespace(tx_mgr=SimpleNamespace(trusted_poses={1:t0, 2:t1}), _kf_timestamps={1:0, 2:1_000_000_000}))
        at2 = NativeClosedLoop._predicted_pose(fake, 2_000_000_000)
        assert at2[0, 3] == 4
        at20 = NativeClosedLoop._predicted_pose(fake, 20_000_000_000)
        assert at20[0, 3] == 40
        fake.node.tx_mgr.trusted_poses = {2:t1}
        one = NativeClosedLoop._predicted_pose(fake, 20_000_000_000)
        assert np.array_equal(one, t1)
        fake.node.tx_mgr.trusted_poses = {}
        assert NativeClosedLoop._predicted_pose(fake, 20_000_000_000) is None
        predicted = {'two_pose_test': 'PASS_LOCAL', 'at2_x': float(at2[0,3]),
                     'horizon_not_bounded': {'query_s':20, 'latest_trusted_s':1, 'x':float(at20[0,3])},
                     'one_trusted_pose_returns_last_pose_not_null': True,
                     'zero_trusted_pose_returns_null': True,
                     'log_rows': len(logged), 'prediction_present_rows':sum(r['support_under_predicted_pose'] is not None for r in logged)}
    print(json.dumps({'version': version, 'log_enabled': enabled, 'outcome': outcome,
                      'prediction': predicted, 'loaded_sources_sha256': finder.loaded}, default=float))


if len(sys.argv) > 1 and sys.argv[1] == '--worker':
    worker(sys.argv[2], sys.argv[3] == 'on')
else:
    assert not git('diff', 'HEAD', '--', 'slam_recovery').strip()
    runs = []
    for version, mode in [(BASE,'off'), (TARGET,'off'), (TARGET,'on')]:
        proc = subprocess.run([sys.executable,'-B','-W','ignore',str(Path(__file__).resolve()),'--worker',version,mode], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        runs.append(json.loads(proc.stdout))
    assert runs[0]['outcome'] == runs[1]['outcome'] == runs[2]['outcome']
    assert runs[2]['outcome']['counts']['AVAILABLE'] == 3
    assert runs[2]['outcome']['counts']['UNAVAILABLE'] == 9
    payload = {'target': TARGET, 'base': BASE, 'exit':0,
               'command':'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4740d94/run_checks.py',
               'base_target_log_on_off_equal':True, 'all_package_imports_from_exact_git_bytes':True,
               'new_pytest_dependent_tests':'NOT_RUN_no_install_or_shim_manual_actual_method_control_instead',
               'no_host_bag_algorithm_or_parameter_edits':True, 'runs':runs}
    output = Path(__file__).with_name('local_checks.json')
    assert not output.exists()
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'target':TARGET, 'equal':True, 'prediction':runs[2]['prediction']}))
