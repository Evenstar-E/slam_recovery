"""Bounded summary-expression controls and fixed C-prime archive reader, no native run."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
MAIN = 'c91519734de99397e97e368d015f17694ffe303f'
ARCHIVE = '99bfe1e'
OLD = '553e2b8b74f11ab675b3f0afc5d5565498268c99'
PREFIX = 'docs/review_20261112_four_host/'
RUN = PREFIX + 'cphist_fl_native_20261112T131213Z_563253/'
HOST = PREFIX + 'host_change_trace_cov/'


def blob(ref, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])


def checkpoint_expr(ref):
    tree = ast.parse(blob(ref, 'slam_recovery/ros/recovery_node.py'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_summary')
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == 'checkpoint_checks':
                    assert isinstance(value, ast.ListComp)
                    return compile(ast.fix_missing_locations(ast.Expression(body=value)), ref + ':reviewed_summary_expression', 'eval')
    raise AssertionError('checkpoint_checks expression missing')


old_expr, new_expr = checkpoint_expr('4b5e63c'), checkpoint_expr(MAIN)
checks = []
for name, eps, expected in [('undecided', [SimpleNamespace()], []),
                             ('mixed', [SimpleNamespace(), SimpleNamespace(meta={'checkpoint_check': {'status': 'NO_ACK'}})], [{'status': 'NO_ACK'}]),
                             ('decided', [SimpleNamespace(meta={'checkpoint_check': {'status': 'LATE_AFTER_BOUNDARY'}})], [{'status': 'LATE_AFTER_BOUNDARY'}])]:
    scope = {'loop': SimpleNamespace(episodes=eps)}
    try:
        before = eval(old_expr, scope)
    except AttributeError:
        before = 'AttributeError'
    after = eval(new_expr, scope)
    assert after == expected
    if name != 'decided':
        assert before == 'AttributeError'
    checks.append({'name': name, 'old': before, 'new': after, 'verdict': 'PASS_LOCAL_expression_only'})


files = ['receipt.json', 'run_summary.json', 'wiring.json', 'launch_pair.sh', 'rss.txt']
raw = {f: blob(ARCHIVE, RUN + f) for f in files}
manifest = blob(ARCHIVE, RUN + 'SHA256SUMS').decode().splitlines()
manifest_map = dict(line.split(maxsplit=1) for line in manifest)
for digest, path in manifest_map.items():
    file = path.removeprefix('./')
    if file in raw:
        assert hashlib.sha256(raw[file]).hexdigest() == digest
receipt, summary = json.loads(raw['receipt.json']), json.loads(raw['run_summary.json'])
source = blob(MAIN, 'slam_recovery/ros/recovery_node.py')
driver_sha = hashlib.sha256(source).hexdigest()
driver_matches = driver_sha == receipt['inputs']['recovery_node_source']
# Retain a source-binding gap instead of treating an archived runtime as this main revision.
assert '_cp_history_k:=3' in raw['launch_pair.sh'].decode()
assert receipt['launch']['detection'] == 'on' and receipt['launch']['scripted_triggers_ns'] == ''
assert summary['pairing']['paired'] == 341
assert summary['gate']['accepted'] == 0 and summary['gate']['rejected'] == 1
assert summary['quarantine']['episodes'] == 1


def fields(ack):
    return dict(re.findall(r'(\w+)=([^\s]+)', ack))


ep = summary['quarantine']['episode_detail'][0]
ack = fields(ep['native_checkpoint']['ack'])
assert ep['native_checkpoint']['ok'] and ack['valid'] == '1'
history = [dict(zip(('stamp_ns', 'frame', 'voxels', 'points'), map(int, row.split(':')))) for row in ack['hist'].strip(';').split(';')]
qstart = ep['quarantine_start_ns']
for h in history:
    h['delta_to_qstart_ns'] = h['stamp_ns'] - qstart
eligible = [h for h in history if h['stamp_ns'] <= qstart]
assert len(eligible) == 1 and eligible[0]['delta_to_qstart_ns'] == -36967360
assert int(ack['stamp_ns']) - qstart == 3366059328
assert int(ack['repair_applied']) == 0
assert int(ack['replay_within_end']) == int(ack['replay_suffix']) == 0
assert ep['restore_disposition']['catch_up'] == 'NOT_IMPLEMENTED'
assert summary['lifecycle']['unresolved_segments'] == 1
estimated = []
for action in summary['lifecycle']['native_checkpoint_actions']:
    f = fields(action.get('ack', ''))
    if 'hist_bytes' in f:
        estimated.append(int(f['hist_bytes']))
rss = [tuple(map(int, row.split())) for row in raw['rss.txt'].decode().splitlines() if row.strip()]
assert all(len(row) == 2 for row in rss)
poses_raw = blob(ARCHIVE, RUN + 'host_logs/M2DGR_room_02.txt')
poses = [row.split() for row in poses_raw.decode().splitlines() if row.strip() and not row.startswith('#')]

v9 = {name: blob(ARCHIVE, HOST + name + '.v9') for name in ('src_LIVMapper.cpp', 'src_voxel_map.cpp', 'include_LIVMapper.h', 'include_common_lib.h', 'include_voxel_map.h')}
v8 = {name: blob(OLD, HOST + name + '.v8') for name in v9}
for name in ('src_voxel_map.cpp', 'include_common_lib.h', 'include_voxel_map.h'):
    assert v9[name] == v8[name]


def function(text, name):
    match = re.search(r'bool LIVMapper::' + name + r'\([^)]*\)\s*\{', text)
    assert match
    i, depth = match.end(), 1
    while depth:
        depth += (text[i] == '{') - (text[i] == '}')
        i += 1
    return text[match.start():i]


old_cpp, new_cpp = v8['src_LIVMapper.cpp'].decode(), v9['src_LIVMapper.cpp'].decode()
assert function(old_cpp, 'restoreCheckpoint') == function(new_cpp, 'restoreCheckpoint')
assert 'h.map = std::move(cp_map_)' in new_cpp
assert 'h.points * 32 + h.voxels * 96' in new_cpp
snapshot = function(new_cpp, 'snapshotCheckpoint')
assert 'p_imu->getCheckpointState(' in snapshot and 'replay_buffer_.clear();' in snapshot
assert 'replay_buffer_' not in new_cpp[new_cpp.index('struct CpHistoryEntry'):new_cpp.index('static std::deque<CpHistoryEntry>')]
start = new_cpp.index('struct CpHistoryEntry')
end = new_cpp.index('static std::deque<CpHistoryEntry>')
retained_struct = new_cpp[start:end]
assert 'cp_last_imu_' not in retained_struct and 'cp_last_prop_end_time_' not in retained_struct
probe = {}
for stage in ('v9', 'v9b', 'v9c'):
    results = [blob(ARCHIVE, HOST + f'probe_{stage}_pre_{i}/result.txt').decode().strip() for i in range(1, 6)]
    probe[stage] = {'results': results, 'counts': dict(Counter('PASS' if r.startswith('PASS') else 'FAIL' for r in results))}
build = blob(ARCHIVE, HOST + 'host_build_v9c.log')
lib = blob(ARCHIVE, HOST + 'v9_sha.txt').decode().split()[0]
assert lib == receipt['inputs']['runtime_library_sha256']
assert 'Built target laser_mapping' in build.decode() and 'Invoking "make -j8" failed' in build.decode()
result = {
    'main': MAIN, 'archive': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', ARCHIVE]).decode().strip(),
    'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_c915197/run_checks.py',
    'summary_expression_controls': checks, 'driver_sha_matches_run': driver_matches,
    'main_driver_sha256': driver_sha, 'receipt_driver_sha256': receipt['inputs']['recovery_node_source'],
    'runtime_driver_source_binding': 'UNAVAILABLE in reviewed main; archived ACK/data retained separately',
    'initial_reader_exit': '1: main driver identity assertion failed; gap preserved, not repaired by changing archive',
    'run_sha256': {f: hashlib.sha256(data).hexdigest() for f, data in raw.items()},
    'manifest_selected_files_verified': files, 'manifest_self_entry_not_verifiable': True,
    'host_pose_sha256': hashlib.sha256(poses_raw).hexdigest(),
    'retained_history': history, 'time_eligible_history': eligible,
    'actual_restore': {'stamp_ns': int(ack['stamp_ns']), 'frame': int(ack['frame']), 'delta_to_qstart_ns': int(ack['stamp_ns']) - qstart,
                       'status': ep['checkpoint_check']['status'], 'repair_applied': int(ack['repair_applied']),
                       'replay_within_end': int(ack['replay_within_end']), 'replay_suffix': int(ack['replay_suffix'])},
    'paired': summary['pairing']['paired'], 'gate': summary['gate'], 'final_state': summary['final_state'],
    'unresolved_segments': summary['lifecycle']['unresolved_segments'],
    'restore_disposition': ep['restore_disposition'],
    'archive_runtime_recovery_node': summary['runtime'],
    'external_rss_samples': {'rows': len(rss), 'peak_value_kb_as_reported': max(row[1] for row in rss),
                             'pid_sampling_command': 'NOT_ARCHIVED in launch_pair.sh; do not conflate with summary runtime pid'},
    'history_bytes_ack_estimate_min_max': [min(estimated), max(estimated)],
    'history_bytes_scope': 'retained old entries only, points*32+voxels*96; excludes active checkpoint and explicit node allocations/caches/allocator',
    'pose_rows': len(poses), 'last_pose_record': poses[-1],
    'source_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in v9.items()},
    'restore_function_unchanged': True, 'history_struct': retained_struct,
    'history_complete_checkpoint': 'NOT_IMPLEMENTED: old entry omits matching IMU continuation state/cache fields; no history restore selection executed',
    'probe_archives': probe, 'build_scope': 'laser_mapping target built, aggregate make failed',
    'runtime_library_sha256': lib,
    'full_208_tests_or_native_run_executed_locally': False,
    'no_parameters_ALI_or_production_code_changed': True,
}
output = Path(__file__).with_name('local_checks.json')
if output.exists():
    assert json.loads(output.read_text(encoding='utf-8')) == result
else:
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
