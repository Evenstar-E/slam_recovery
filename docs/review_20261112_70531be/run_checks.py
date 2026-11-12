"""Version-bound diagnostic controls; no ROS, archived code execution, or parameter edits."""
import hashlib
import importlib.abc
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = '70531bef27467519e370ac4819609398f1933533'
BASE = 'eeedb7fed53a91905b77bb38705a73aaae4927f3'


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
    sys.path.insert(0, str(ROOT))
    from slam_recovery.ros.recovery_node import NativeClosedLoop, cloud_to_xyz, subsample
    from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
    from slam_recovery.validation import compute_disjoint_holdout_point_to_plane_nis
    rng = np.random.default_rng(12)
    cloud = rng.normal(size=(400, 3)) * .4
    with tempfile.TemporaryDirectory(prefix='availability-review-') as directory:
        node = OnlineRecoveryTransactionNode()
        kwargs = {'availability_log': str(Path(directory) / 'frames.jsonl')} if version == TARGET and enabled else {}
        loop = NativeClosedLoop(node, run_id='source-control', **kwargs)
        for i in range(12):
            pose = np.eye(4)
            pose[0, 3] = .005 * i
            loop.on_pair(1_000_000_000 + i * 250_000_000, pose, cloud, 1_000_000_000 + i * 250_000_000)
        if version == TARGET:
            loop.availability.close()
        outcome = {'diag': loop.diag, 'detection_counts': dict(loop.detection_counts),
                   'records': loop.records, 'nis_counts': dict(loop.nis.counts),
                   'trusted_version': node.tx_mgr.trusted_version,
                   'trusted_keys': sorted(node.tx_mgr.trusted_poses),
                   'trusted_map_points': len(node.get_trusted_map_points())}
        row_count = len(Path(directory, 'frames.jsonl').read_text().splitlines()) if enabled else 0
    tests = {'status': 'NOT_RUN_BASE', 'count': 0}
    row_control = None
    mathematical = None
    if version == TARGET and enabled:
        from slam_recovery.tests import test_availability_log as tests_module
        suite = unittest.TestSuite()
        for cls in (tests_module.TestRecorder, tests_module.TestSupportDetail, tests_module.TestNisDetail):
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
        suite.addTest(tests_module.TestLoopRows('test_carried_forward_keeps_the_value_and_its_age'))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        assert result.wasSuccessful()
        tests = {'status': 'PASS_LOCAL', 'count': result.testsRun,
                 'not_run': 'Two fake-loop tests import pytest via test_recovery_node; no install or shim.'}
        raw = np.column_stack((np.arange(12), np.zeros(12), np.zeros(12))).astype('<f4')
        fields = [SimpleNamespace(name=name, count=1, datatype=7, offset=offset)
                  for name, offset in [('x', 0), ('y', 4), ('z', 8)]]
        msg = SimpleNamespace(fields=fields, width=12, height=1, point_step=12,
                              is_bigendian=False, data=raw.tobytes())
        placed = subsample(cloud_to_xyz(msg), 4)
        node.scan_buffer_body[999] = placed
        detail = {}
        assert node._frame_has_reference_support(999, placed, {999: np.eye(4)}, detail=detail)
        saved_rows = [p['row'] for p in detail['points']]
        raw_rows = [int(p['body'][0]) for p in detail['points']]
        assert saved_rows == [0, 1, 2, 3] and raw_rows == [0, 3, 6, 9]
        row_control = {'status': 'FAIL_REPRODUCED_ORIGINAL_ROW_CLAIM_ONLY',
                       'raw_points': 12, 'scan_cap': 4, 'saved_rows': saved_rows,
                       'actual_original_rows': raw_rows, 'support_boolean_unchanged': True}
        ref = rng.normal(size=(400, 3))
        query = ref + .1
        hold = {}
        with_detail = compute_disjoint_holdout_point_to_plane_nis(ref, query, details=hold)
        without_detail = compute_disjoint_holdout_point_to_plane_nis(ref, query)
        assert with_detail == without_detail
        used = [p['chi2'] for p in hold['points'] if hold['branch'] == 'all_residuals' or p['within_2m']]
        assert np.isclose(np.mean(used), with_detail)
        mathematical = {'status': 'PASS_LOCAL', 'nis': with_detail, 'branch': hold['branch'],
                        'detail_on_off_equal': True, 'stored_residual_mean_matches': True}
    print(json.dumps({'version': version, 'log_enabled': enabled, 'outcome': outcome,
                      'rows': row_count, 'tests': tests, 'original_row_control': row_control,
                      'holdout_control': mathematical, 'loaded_sources_sha256': finder.loaded}, default=float))


if len(sys.argv) > 1 and sys.argv[1] == '--worker':
    worker(sys.argv[2], sys.argv[3] == 'on')
else:
    assert not git('diff', 'HEAD', '--', 'slam_recovery').strip()
    assert not git('ls-files', '--others', '--exclude-standard', '--', 'slam_recovery').strip()
    runs = []
    for version, mode in [(BASE, 'off'), (TARGET, 'off'), (TARGET, 'on')]:
        command = [sys.executable, '-B', '-W', 'ignore', str(Path(__file__).resolve()), '--worker', version, mode]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.stderr:
            print(completed.stderr, file=sys.stderr)
        assert completed.returncode == 0, completed.stdout
        runs.append(json.loads(completed.stdout))
    assert runs[0]['outcome'] == runs[1]['outcome'] == runs[2]['outcome']
    assert runs[2]['rows'] == 12
    assert runs[2]['outcome']['detection_counts']['AVAILABLE'] > 0
    assert runs[2]['outcome']['detection_counts']['UNAVAILABLE'] > 0
    payload = {'target': TARGET, 'base': BASE,
               'command': 'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_70531be/run_checks.py',
               'exit': 0, 'source_loading': 'All slam_recovery imports from exact Git revision via memory loader',
               'base_target_and_log_on_off_equal': True, 'real_node_control_frames': 12,
               'runs': runs, 'no_ros_host_bag_or_parameter_execution': True}
    output = Path(__file__).with_name('local_checks.json')
    if output.exists():
        assert json.loads(output.read_text(encoding='utf-8'))['target'] == TARGET
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=float) + '\n', encoding='utf-8')
    print(json.dumps({k: payload[k] for k in ('target', 'base', 'exit', 'base_target_and_log_on_off_equal', 'real_node_control_frames')}))
