"""Exact-target manifest declaration controls; no archived CLI or native execution."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'aaf7e284974877c9196ebd68a94e1c075e3cee93'
PREFIX = 'docs/ali_h_v1_research/'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


raw = git('show', TARGET + ':' + PREFIX + 't2_input_check.py')
tree = ast.parse(raw)
names = {'check_manifest', '_manifest'}
constants = {'OLD_RUN_IDS', 'REQUIRED_TOP', 'REQUIRED_INPUTS', 'REQUIRED_EXPORTS',
             'REQUIRED_DECL', 'VALID_STATE_ORDER', 'VALID_PERTURBATION'}
namespace = {}
functions = []
for node in tree.body:
    if isinstance(node, ast.Assign):
        for name in node.targets:
            if isinstance(name, ast.Name) and name.id in constants:
                namespace[name.id] = ast.literal_eval(node.value)
    if isinstance(node, ast.FunctionDef) and node.name in names:
        functions.append(node)
assert len(functions) == 2
exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
             TARGET + ':reviewed_manifest_functions', 'exec'), namespace)
checks = []
for identity, time in [(True, True), (False, True), (True, False), (False, False)]:
    manifest = namespace['_manifest']()
    manifest['join'].update(identity_correspondence=identity, time_correspondence=time)
    result = namespace['check_manifest'](manifest)
    assert result['status'] == ('READY' if identity and time else 'INCOMPLETE')
    checks.append({'identity': identity, 'time': time, 'result': result})
manifest = namespace['_manifest']()
manifest['join']['offset_constant'] = False
variable = namespace['check_manifest'](manifest)
assert variable['status'] == 'READY'
manifest = namespace['_manifest']()
manifest['exports']['scan_source_index'] = False
missing = namespace['check_manifest'](manifest)
assert missing['status'] == 'INCOMPLETE' and 'exports.scan_source_index' in missing['missing']
old = ast.parse(git('show', '35c2d62:' + PREFIX + 't2_input_check.py'))
unchanged = {}
for name in ('e_i', 's_i', 'so3_left_jacobian_inv'):
    before = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == name)
    after = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    unchanged[name] = ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False)
assert all(unchanged.values())
record = json.loads(git('show', TARGET + ':' + PREFIX + 't2_prep_selftest.json'))
paths = git('ls-tree', '-r', '--name-only', TARGET, '--', 'docs').decode().splitlines()
new_run_paths = [p for p in paths if any(s in p for s in ('111325', 'trace_cov', 'probe_v7s'))]
assert not new_run_paths
payload = {'target': TARGET, 'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_aaf7e28/run_checks.py',
           'source_sha256': hashlib.sha256(raw).hexdigest(), 'join_declaration_controls': checks,
           'variable_offset_with_identity_and_time': variable, 'missing_source_identity_export': missing,
           'old_numeric_functions_AST_unchanged_not_retested': unchanged,
           'saved_selftest_count': len(record['tests']), 'saved_selftest_failed': record['failed'],
           'archived_selftest_executed': False, 'uploaded_new_run_or_probe_paths': new_run_paths,
           'trace_off_and_layout_diagnosis': 'DEVELOPER_REPORTED; no raw artifacts in target',
           'actual_row_identity_join_time_and_behavior_control': 'NOT_EXECUTED_NOT_VERIFIED',
           'major_blocker_user_confirmation': 'UNCHANGED_ABSENT',
           'no_ROS_host_bag_parameters_or_archived_CLI': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(payload, ensure_ascii=False, indent=2))
