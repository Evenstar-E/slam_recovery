"""Fixed v10 source/preparation checks; no bag, build, archived CLI or native execution."""
import ast
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
MAIN = '66cc8146909329ef4bc712cd0728dc4cb4dfd0f4'
HOST = 'eb2630ef10f827626ee1eaad87fa7ddc39cc825c'
OLD_HOST = '1fde5219e0aad403a5b3895d1067c12b6edb6f65'
PREFIX = 'docs/ali_h_v1_research/'
HP = 'docs/review_20261112_four_host/host_change_trace_cov/'


def blob(ref, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])


summary = json.loads(blob(MAIN, PREFIX + 't2_summary.json'))
rows = [json.loads(row) for row in blob(MAIN, PREFIX + 't2_join.jsonl').splitlines() if row.strip()]
assert summary['_meta']['i_qualification'] == 'INCOMPLETE/UNKNOWN'
assert 'so3_left_jacobian_inv' in summary['_meta']['e_i_convention']
assert blob(MAIN, PREFIX + 't2_join.jsonl') == blob('e351a0b', PREFIX + 't2_join.jsonl')
start = min(row['pose_stamp_ns'] for row in rows)
by_pose = [row for row in rows if (row['pose_stamp_ns'] - start) / 1e9 >= 54]
tail_ids = {block['block_id'] for block in summary['blocks'] if block['tail']}
by_block = [row for row in rows if row['pose_stamp_ns'] // 500_000_000 in tail_ids]
assert len(by_pose) == summary['states']['tail_rows_by_pose_rel_54'] == 47
assert len(by_block) == summary['states']['tail_rows_by_block'] == 51
assert sum((row['pose_stamp_ns'] - start) / 1e9 < 54 for row in by_block) == 4
assert summary['states']['unknown_blocks'] == 120
v10 = {name: blob(HOST, HP + name + '.v10') for name in ('src_LIVMapper.cpp', 'src_voxel_map.cpp', 'include_LIVMapper.h', 'include_common_lib.h', 'include_voxel_map.h')}
for name in v10:
    if name != 'src_LIVMapper.cpp':
        assert v10[name] == blob(OLD_HOST, HP + name + '.v9')
cpp = v10['src_LIVMapper.cpp'].decode()
handler_start = cpp.index('void LIVMapper::handleLIO()')
handler_end = cpp.index('void LIVMapper::savePCD()', handler_start)
handler = cpp[handler_start:handler_end]
assert handler.index('g_lio_pre <<') < handler.index('voxelmap_manager->StateEstimation(state_propagat)')
assert handler.index('_state = voxelmap_manager->state_;') < handler.index('g_lio_out <<') < handler.rindex('writeTraceCovRow(')
assert cpp.count('g_lio_pre <<') == cpp.count('g_lio_out <<') == 1
pre_output = handler[handler.index('g_lio_pre <<'):handler.index('// The propagated covariance')]
post_output = handler[handler.index('g_lio_out <<'):handler.rindex('writeTraceCovRow(')]
assert not any(key in pre_output + post_output for key in ('native_group_index', 'trace_cov_rows', 'replay_mode_'))
assert 'state_propagat = _state;' in cpp
assert 'const Eigen::Quaterniond q_end(_state.rot_end)' in cpp
assert 'P_post = _state.cov.block<6, 6>(0, 0)' in cpp
common = v10['include_common_lib.h'].decode()
assert 'this->pos_end += state_add.block<3, 1>(3, 0);' in common
assert 'BODY (IMU) tangent space' in cpp
probe = []
for i in range(1, 6):
    result = blob(HOST, HP + f'probe_v10_pre_{i}/result.txt').decode().strip()
    sha = blob(HOST, HP + f'probe_v10_pre_{i}/env_and_sha.txt').decode().split()[0]
    assert result == 'PASS alive 25s'
    assert sha == '69dc8ac5fcfe53a8abdf618b7418f0055f5c5baf3d60382d65950b9271f02e4d'
    probe.append({'number': i, 'result': result, 'library_sha256': sha})
build = blob(HOST, HP + 'host_build_v10.log')
assert 'Built target laser_mapping' in build.decode() and 'Built target fastlivo_mapping' in build.decode()
assert 'build/FAST-LIVO2' in build.decode()
# One ordinary row in the new declared v10 width; execute only each reviewed parser.
header = '# idx rel_s abs_ns grp_idx scan_first_ns scan_last_ns n_scans has_out phase eff r_mean r_med r_abs_mean r_chi2 r_chi2w vec6 Ppre6x6 Ppost6x6 pose7\n'
text = header + ' '.join(['0'] * 100) + '\n'
controls = []
for file in ('t2_run.py', 't2_join_upgrade.py'):
    tree = ast.parse(blob(MAIN, PREFIX + file))
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'parse_trace')
    namespace = {'Any': Any, 'Dict': Dict, 'List': List, 'Optional': Optional,
                 'open': lambda *args, **kwargs: io.StringIO(text)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), MAIN + ':reviewed_parser_only', 'exec'), namespace)
    result = namespace['parse_trace']('synthetic-reviewed-v10-row')
    assert result['rows'] == [] and result['malformed'] == [{'line': 2, 'ncols': 100}]
    controls.append({'parser': file, 'normal_v10_width': 100, 'parsed_rows': 0,
                     'malformed': result['malformed'], 'status': 'FAIL_REPRODUCED_v10_consumer_not_supported',
                     'scope': 'synthetic expected-width row, no actual v10 bag or trace delivered'})
report = {
    'main': MAIN, 'host_archive': HOST,
    'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_66cc814/run_checks.py',
    'saved_meta': summary['_meta'], 'saved_numeric_rows_unchanged': True,
    'tail_counts_verified': {'pose_at_least_54_s': len(by_pose), 'tail_block_members': len(by_block), 'extra_boundary_members': 4},
    'saved_states': dict(Counter(row['shadow_state'] for row in rows)),
    'v10_source_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in v10.items()},
    'only_LIVMapper_changed_from_v9': True,
    'pre_post_source_order': 'LIO-only pre before StateEstimation; post and trace after updated _state',
    'pre_post_identity_fields': 'NO idx/group/phase in added separate files; rel_s only, unique pairing not demonstrated',
    'pose7_inline_source': 'same writeTraceCovRow _state; qualify as post only for has_out/valid update rows',
    'covariance_declaration': 'NOT_VERIFIED: unchanged mixed body rotation/world additive translation, no residual covariance conversion',
    'probe_archives': probe, 'build_sha256': hashlib.sha256(build).hexdigest(),
    'build_scope': 'FAST-LIVO2 laser_mapping/fastlivo_mapping targets built; not full workspace build or independent rebuild',
    'v10_reader_controls': controls,
    'v10_new_bag_trace_I_performance_and_recovery': 'NOT_EXECUTED in delivered delta',
    'full_host_binary_sha256': 'UNAVAILABLE in probe hashes (library only); reported prefix 6dd71953',
    'no_native_build_ROS_archived_CLI_or_parameter_execution': True,
}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
