"""Bounded controls for the new reference-tool changes; no ROS, bag or host run."""
import hashlib
import importlib.abc
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'eeda1224da57fa9d380811f4009cb954615286c7'


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
from slam_recovery.tests import test_independent_reference as tests
from slam_recovery.validation.independent_reference import score_rows, summarise, estimate_se3
suite = unittest.TestSuite()
for cls in (tests.TestReadPcd, tests.TestScore, tests.TestLoadRows, tests.TestGauge):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
has_scipy = importlib.util.find_spec('scipy') is not None
if has_scipy:
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(tests.TestAlignment))
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
body = np.zeros((200, 3)); body[20:, 0] = 10
trimmed = {'kf_id': 2, 'T_wb': np.eye(4).reshape(-1).tolist(), 'status': 'AVAILABLE',
           'support': {'points': [{'body': b.tolist()} for b in body[:20]],
                       'points_total': 200, 'supported_fraction': .8, 'pass': True}}
scored = score_rows([trimmed], np.zeros((1, 3)))[0]
population = summarise([scored])
assert scored['independent_fraction'] == 1.0 and np.mean(np.linalg.norm(body, axis=1) <= 1) == .1
assert population['frames_full_sample'] == 0 and population['both_pass'] == 0
assert population['partial_sample_not_evaluable'] == 1
row = {'kf_id': 3, 'T_wb': np.eye(4).reshape(-1).tolist(), 'status': 'UNAVAILABLE',
       'support': {'points': [{'body': b} for b in [[0., 0., 0.], [.1, 0., 0.], [.2, 0., 0.]]],
                   'points_total': 3, 'supported_fraction': 0., 'pass': False}}
far = score_rows([row], np.array([[100., 100., 100.]]))[0]
near = score_rows([row], np.array([[0., 0., 0.]]))[0]
neutral = summarise([near])
assert not far['independent_pass'] and near['independent_pass']
assert neutral['host_low_new_reference_pass'] == 1 and 'UNKNOWN' in neutral['reading']
# A single known gauge is composed with a nonidentity host pose; no per-frame fit.
host = np.eye(4); host[:3, 3] = [2., 1., -.5]
gauge = np.eye(4); gauge[:3, :3] = [[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]]
gauge[:3, 3] = [10., -3., 2.]
row['T_wb'] = host.reshape(-1).tolist()
body3 = np.array([p['body'] for p in row['support']['points']])
placed = body3 @ host[:3, :3].T + host[:3, 3]
reference = placed @ gauge[:3, :3].T + gauge[:3, 3]
without = score_rows([row], reference)[0]
with_gauge = score_rows([row], reference, reference_transform=gauge)[0]
assert without['independent_fraction'] == 0 and with_gauge['independent_fraction'] == 1
prefix = np.array([[0., 0., 0.], [1., 0., 0.], [0., 2., 0.], [0., 0., 3.]])
fit = estimate_se3(prefix, prefix @ gauge[:3, :3].T + gauge[:3, 3])
np.testing.assert_allclose(fit['T'], gauge, atol=1e-12)
payload = {'target': TARGET, 'exit': 0,
           'command': 'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_eeda122/run_checks.py',
           'source_loading': 'All slam_recovery modules loaded from exact target Git bytes',
           'loaded_sources_sha256': finder.loaded, 'selected_tests': result.testsRun,
           'scipy_alignment_test': 'PASS_LOCAL' if has_scipy else 'NOT_RUN_scipy_missing_no_install',
           'partial_population_control': {'status': 'PASS_LOCAL', 'saved_fraction': 1., 'full_fraction': .1, 'summary': population},
           'reference_only_control': {'status': 'PASS_LOCAL', 'same_pose': True, 'old_fraction': 0., 'new_fraction': 1., 'summary': neutral},
           'gauge_control': {'status': 'PASS_LOCAL', 'fraction_without': 0., 'fraction_with_single_gauge': 1.,
                             'known_prefix_rms_m': fit['rms_residual_m'], 'scope': 'Synthetic transform arithmetic, not actual run alignment'},
           'real_cross_run_scoring': 'NOT_EXECUTED', 'no_native_host_bag_or_parameter_execution': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in payload.items() if k != 'loaded_sources_sha256'}, ensure_ascii=False))
