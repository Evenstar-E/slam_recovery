"""Source provenance and one scripted-boundary / archived failed-ACK control."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
MAIN = '4b5e63cbdba6b8e936a5d3b13fa6770c2d212424'
TRACE = '553e2b8b74f11ab675b3f0afc5d5565498268c99'
OLD = '290aae8441fedc24dfbf316b8150880b63fae0b1'
PREFIX = 'docs/review_20261112_four_host/'


def blob(ref, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])


old_raw = blob(OLD, PREFIX + 'trace_fl_native_20261112T115734Z_483777/run_summary.json')
old = json.loads(old_raw)
failed_ep = next(e for e in old['quarantine']['episode_detail'] if (e.get('native_checkpoint') or {}).get('ok') is False)
action = failed_ep['native_checkpoint']
assert action['ack'].startswith('FAIL restore valid=0 stamp_ns=-1000000000 frame=0 ')
cls = next(n for n in ast.parse(blob(MAIN, 'slam_recovery/ros/recovery_node.py')).body if isinstance(n, ast.ClassDef) and n.name == 'NativeClosedLoop')
names = ('_checkpoint_boundary', '_record_checkpoint_check', '_finalize_checkpoint_checks')
methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
ns = {}
module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + methods, type_ignores=[])
exec(compile(ast.fix_missing_locations(module), MAIN + ':reviewed_metadata', 'exec'), ns)
Control = type('Control', (), {name: ns[name] for name in names})
loop = Control()
loop.scripted_trigger_stamps_ns = [1000]
loop.confirmation_margin_ns = 20
scripted = SimpleNamespace(trigger_ts_ns=1000, quarantine_start_ns=970, meta={})
loop.episodes = [scripted]
loop._record_checkpoint_check(scripted, {'ok': True, 'ack': 'OK restore valid=1 stamp_ns=975 frame=1'})
loop._finalize_checkpoint_checks()
assert scripted.meta['checkpoint_check']['boundary_stamp_ns'] == 980
assert scripted.meta['checkpoint_check']['status'] == 'AT_OR_BEFORE_BOUNDARY'
loop.scripted_trigger_stamps_ns = []
ep = SimpleNamespace(trigger_ts_ns=failed_ep['trigger_ts_ns'], quarantine_start_ns=failed_ep['quarantine_start_ns'], meta={})
loop.episodes = [ep]
loop._record_checkpoint_check(ep, dict(action))
loop._finalize_checkpoint_checks()
assert ep.meta['checkpoint_check']['rollback_support'] == 'WITHIN_DECLARED_BOUNDARY'
files = ['src_LIVMapper.cpp.v8', 'src_voxel_map.cpp.v8', 'include_common_lib.h.v8', 'include_LIVMapper.h.v8', 'include_voxel_map.h.v8', 'host_build_v8.log', 'v8_sha.txt']
raw = {name: blob(TRACE, PREFIX + 'host_change_trace_cov/' + name) for name in files}
lib = raw['v8_sha.txt'].decode().split()[0]
receipt = json.loads(blob(TRACE, PREFIX + 'trace_online_fl_native_20261112T124217Z_521833/receipt.json'))
assert lib == receipt['inputs']['runtime_library_sha256']
assert '[ 88%] Built target laser_mapping' in raw['host_build_v8.log'].decode()
assert 'Invoking "make -j8" failed' in raw['host_build_v8.log'].decode()
result = {'main': MAIN, 'archive': TRACE, 'old_archive': OLD,
          'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4b5e63c/provenance_checks.py',
          'old_summary_sha256': hashlib.sha256(old_raw).hexdigest(),
          'scripted_boundary_control': {'status': 'PASS_LOCAL', 'checkpoint_check': scripted.meta['checkpoint_check']},
          'archived_failed_restore_metadata_control': {'status': 'FAIL_REPRODUCED', 'source_episode': failed_ep['index'],
              'original_action': action, 'checkpoint_check': ep.meta['checkpoint_check'],
              'scope': 'Apply reviewed main metadata methods to previously archived ordinary failed restore, not a new native run'},
          'v8_source_and_build_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in raw.items()},
          'v8_library_declared_hash_matches_run_receipt': True,
          'v8_build_status': 'laser_mapping target built; aggregate make failed at test_vk_common_patch_score CXXABI symbol',
          'source_to_executed_binary_independent_rebuild': 'NOT_EXECUTED', 'native_execution': False}
output = Path(__file__).with_name('provenance_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
