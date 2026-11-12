"""Check only the reviewed qualification expression and unchanged saved evidence."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = '18297d1d4e8bf4518e7329359a56f29beb5130f9'
OLD = 'cdd3bf70eb78287b102301bb5c6529185cea231d'
P = 'docs/ali_h_v1_research/'
HASHES = {}


def blob(ref, name):
    b = subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + P + name])
    HASHES[ref + ':' + name] = hashlib.sha256(b).hexdigest()
    return b


raw = blob(MAIN, 't2_run.py')
tree = ast.parse(raw)
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
out = next(n.value for n in fn.body if isinstance(n, ast.Assign) and
           any(isinstance(t, ast.Name) and t.id == 'out' for t in n.targets))
meta = next(v for k, v in zip(out.keys, out.values) if ast.literal_eval(k) == '_meta')
layers = next(v for k, v in zip(meta.keys, meta.values) if ast.literal_eval(k) == 'i_qualification_layers')
expression = next(v for k, v in zip(layers.keys, layers.values)
                  if ast.literal_eval(k) == 'RAW_HEADER_CONTAINMENT')
code = compile(ast.Expression(expression), MAIN + ':reviewed_header_qualification', 'eval')
results = []
for mode, expected in [('true_span_512', 'PASS'), ('mechanical_prev_last', 'HEURISTIC_UNPROVEN')]:
    value = eval(code, {'__builtins__': {}, 'join': {'mode': mode}})
    assert value == expected
    results.append({'mode': mode, 'qualification': value, 'status': 'PASS_LOCAL'})
legacy_old = json.loads(blob(OLD, 't2_summary.json'))
legacy_new = json.loads(blob(MAIN, 't2_summary.json'))
assert legacy_old['_meta']['i_qualification_layers']['RAW_HEADER_CONTAINMENT'] == 'PASS'
assert legacy_new['_meta']['i_qualification_layers']['RAW_HEADER_CONTAINMENT'] == 'HEURISTIC_UNPROVEN'
legacy_old['_meta']['i_qualification_layers']['RAW_HEADER_CONTAINMENT'] = 'HEURISTIC_UNPROVEN'
assert legacy_old == legacy_new
unchanged = []
for name in ('t2_join.jsonl', 't2_v11_join.jsonl', 't2_v11_summary.json'):
    assert blob(OLD, name) == blob(MAIN, name)
    unchanged.append(name)
result = {'main': MAIN, 'comparison': OLD,
          'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_18297d1/run_checks.py <new-output>',
          'scope': 'two ordinary reviewed-expression controls and byte/JSON comparisons only; no CLI/native/math rerun',
          'controls': results, 'legacy_only_changed_field': '_meta.i_qualification_layers.RAW_HEADER_CONTAINMENT',
          'unchanged_files': unchanged, 'existing_defect': 'CLOSED_AT_18297d1', 'hashes': HASHES}
output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
