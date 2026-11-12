"""Verify new executed-driver provenance; do not execute archived scripts or native host."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MAIN = 'f890ad8064cb42bfbc708732e98735206e2b09ee'
ARCHIVE = '1fde521'
BASE = '8d9cd0d'
PREFIX = 'docs/review_20261112_four_host/'
PROV = PREFIX + 'run_provenance_131213/'
RUN = PREFIX + 'cphist_fl_native_20261112T131213Z_563253/'


def blob(ref, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])


executed = blob(ARCHIVE, PROV + 'recovery_node.executed.py')
base = blob(BASE, 'slam_recovery/ros/recovery_node.py')
main = blob(MAIN, 'slam_recovery/ros/recovery_node.py')
receipt = json.loads(blob(ARCHIVE, RUN + 'receipt.json'))
assert hashlib.sha256(executed).hexdigest() == receipt['inputs']['recovery_node_source']
manifest = blob(ARCHIVE, PROV + 'SHA256SUMS').decode().splitlines()
verified = {}
for line in manifest:
    digest, path = line.split(maxsplit=1)
    actual = hashlib.sha256(blob(ARCHIVE, path)).hexdigest()
    assert actual == digest
    verified[path] = actual
old_tree, new_tree = ast.parse(base), ast.parse(executed)
old_fn = next(n for n in old_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_summary')
new_fn = next(n for n in new_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_summary')


def checkpoint_expr(fn):
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == 'checkpoint_checks':
                    assert isinstance(v, ast.ListComp)
                    return v
    raise AssertionError('missing reviewed summary expression')


old_expression, new_expression = checkpoint_expr(old_fn), checkpoint_expr(new_fn)
assert ast.dump(old_expression, include_attributes=False) != ast.dump(new_expression, include_attributes=False)
# Remove exactly the changed, reviewed checkpoint-summary expression, then compare complete ASTs.
class MaskExpression(ast.NodeTransformer):
    def visit_Dict(self, node):
        self.generic_visit(node)
        for i, key in enumerate(node.keys):
            if isinstance(key, ast.Constant) and key.value == 'checkpoint_checks':
                node.values[i] = ast.Constant(value='REVIEWED_SUMMARY_EXPRESSION')
        return node


assert ast.dump(MaskExpression().visit(old_tree), include_attributes=False) == ast.dump(MaskExpression().visit(new_tree), include_attributes=False)
assert base == blob('de4360b', 'slam_recovery/ros/recovery_node.py')
assert hashlib.sha256(main).hexdigest() != hashlib.sha256(executed).hexdigest()
patch = blob(ARCHIVE, PROV + 'driver_patch.diff').decode()
actual_diff = ''.join(difflib.unified_diff(base.decode().splitlines(True), executed.decode().splitlines(True), fromfile='base_driver', tofile='executed_driver'))
# Compare hunk contents, leaving declared source paths and file-generation timestamps untouched.
def hunks(text):
    lines = text.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith('@@ '))
    return lines[first:]
assert hunks(actual_diff) == hunks(patch)
summary = json.loads(blob(ARCHIVE, RUN + 'run_summary.json'))
ep = summary['quarantine']['episode_detail'][0]
rows = blob(ARCHIVE, RUN + 'cp_candidates.txt').decode().splitlines()
values = rows[1].split()
assert len(rows) == 2
assert int(values[1]) == ep['quarantine_start_ns']
assert int(values[2]) == ep['checkpoint_check']['actual_stamp_ns']
assert values[3] == 'LATE_AFTER_BOUNDARY' and values[4] == '1'
assert int(values[5]) == 1627785261470954240
assert float(values[6]) == 0.037 and int(values[7]) == 2036096 and int(values[8]) == 51
shell_diff = blob(ARCHIVE, PROV + 'run_native_loop.diff').decode()
assert '+CP_HISTORY_K="${CP_HISTORY_K:-}"' in shell_diff
assert '_cp_history_k:=3' in blob(ARCHIVE, RUN + 'launch_pair.sh').decode()
result = {
    'main': MAIN,
    'archive': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', ARCHIVE]).decode().strip(),
    'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_f890ad8/run_checks.py',
    'executed_driver_sha256': hashlib.sha256(executed).hexdigest(),
    'base_driver_sha256': hashlib.sha256(base).hexdigest(),
    'main_driver_sha256': hashlib.sha256(main).hexdigest(),
    'executed_matches_receipt': True,
    'only_AST_change_is_reviewed_checkpoint_checks_expression': True,
    'base_matches_de4360b': True,
    'declared_driver_patch_matches_actual_source_diff': True,
    'provenance_manifest_verified': verified,
    'actual_driver_source_diff': actual_diff,
    'candidate_saved_row_verified': values,
    'candidate_minus_boundary_ns': int(values[5]) - int(values[1]),
    'actual_minus_boundary_ns': int(values[2]) - int(values[1]),
    'candidate_bytes_scope': 'same points*32+voxels*96 estimate; not RSS/full checkpoint cost',
    'frame_gap_scope': 'active checkpoint frame minus candidate frame, not actual replay count or required suffix total',
    'archive_receipt_old_host_binary_sha256': receipt['inputs']['host_binary_sha256'],
    'relinked_binary_6dd71953': 'DEVELOPER_REPORTED: no new run receipt or full hash/ldd/link log in this eight-file delta',
    'new_native_or_ALI_results': 'NONE_IN_REVIEWED_DELTA',
    'archived_CLI_native_or_tests_executed': False,
}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
