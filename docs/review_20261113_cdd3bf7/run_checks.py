"""Bounded qualification/label audit of fixed blobs; no archive code or native execution."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = 'cdd3bf70eb78287b102301bb5c6529185cea231d'
OLD = 'b2f3983801e6113f3c3626df0d95783666e1c24f'
P = 'docs/ali_h_v1_research/'
HASHES = {}


def blob(ref, path):
    b = subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])
    HASHES[ref + ':' + path] = hashlib.sha256(b).hexdigest()
    return b


def data(ref, name):
    return json.loads(blob(ref, P + name))


def rows(ref, name):
    return [json.loads(l) for l in blob(ref, P + name).splitlines() if l.strip()]


raw = blob(MAIN, P + 't2_run.py')
tree = ast.parse(raw)
main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
out = next(n.value for n in main.body if isinstance(n, ast.Assign) and
           any(isinstance(t, ast.Name) and t.id == 'out' for t in n.targets))
meta = next(v for k, v in zip(out.keys, out.values) if ast.literal_eval(k) == '_meta')
layers = next(v for k, v in zip(meta.keys, meta.values)
              if ast.literal_eval(k) == 'i_qualification_layers')
raw_header_status_expression = next(v for k, v in zip(layers.keys, layers.values)
                                   if ast.literal_eval(k) == 'RAW_HEADER_CONTAINMENT')
assert ast.literal_eval(raw_header_status_expression) == 'PASS'
reports = []
for tag, archive, run in [('', '290aae8441fedc24dfbf316b8150880b63fae0b1',
                         'trace_fl_native_20261112T115734Z_483777'),
                        ('v11_', 'a812302e3a9acd17b1e6f318d332b88563910069',
                         'growth_fl_native_20261112T165438Z_669633')]:
    old, new = rows(OLD, 't2_' + tag + 'join.jsonl'), rows(MAIN, 't2_' + tag + 'join.jsonl')
    before, after = data(OLD, 't2_' + tag + 'summary.json'), data(MAIN, 't2_' + tag + 'summary.json')
    assert len(old) == len(new)
    trace_bytes = blob(archive, 'docs/review_20261112_four_host/' + run + '/host_logs/trace_cov.txt')
    trace_rows = [l.split() for l in trace_bytes.decode().splitlines()
                  if l.strip() and not l.startswith('#')]
    header = next(l[1:].split() for l in trace_bytes.decode().splitlines() if l.startswith('# idx '))
    idx, eff, first = header.index('idx'), header.index('eff'), header.index('scan_first_ns')
    width = 107 if tag else 92
    valid = [r for r in trace_rows if len(r) == width]
    byidx = {int(r[idx]): int(float(r[eff])) for r in valid}
    numeric_unchanged = True
    zeros, changed_tail = [], 0
    for a, b in zip(old, new):
        assert {k: v for k, v in a.items() if k not in ('i', 'tail', 'reason_codes')} == {
            k: v for k, v in b.items() if k not in ('i', 'tail', 'reason_codes')}
        assert a['i'].keys() <= b['i'].keys()
        assert {k: v for k, v in a['i'].items() if k != 'mode'} == {
            k: v for k, v in b['i'].items() if k in a['i'] and k != 'mode'}
        if b['i']['present']:
            recorded = b['i']['eff']
            assert recorded == byidx[b['i']['trace_idx']]
            assert b['i']['zero_constraint'] == (recorded == 0)
            assert b['i']['mode'] == ('same_row_pre_post' if tag else 'exact_from_vec6_and_m2dgr_post')
            if recorded == 0:
                assert b['i']['e_norm'] <= 1e-12
                zeros.append(b['kf_id'])
        changed_tail += a['tail'] != b['tail']
        assert b['shadow_state'] == 'UNKNOWN'
    assert len(zeros) == after['channels']['I_zero_eff_rows'] == after['channels']['I_zero_eff_zero_log_rows']
    assert before['_meta']['trace_sha256'] == after['_meta']['trace_sha256'] == hashlib.sha256(trace_bytes).hexdigest()
    for field in ('availability_sha256', 'receipt_sha256', 'summary_sha256'):
        assert before['_meta'][field] == after['_meta'][field]
    assert before['channels']['I_present'] == after['channels']['I_present']
    first_pose = min(r['pose_stamp_ns'] for r in new)
    trace_start = min(int(r[header.index('abs_ns')]) for r in valid)
    if tag:
        sr = json.loads(blob(archive, 'docs/review_20261112_four_host/' + run + '/run_summary.json'))
        ep = sr['quarantine']['episode_detail'][1]
        deadline = ep['deadline_ns']
        assert abs((deadline - trace_start) / 1e9 - after['_meta']['e2_deadline_rel_s']) < 1e-12
        assert abs((ep['trigger_ts_ns'] - trace_start) / 1e9 - after['_meta']['e2_trigger_rel_s']) < 1e-12
        assert after['_meta']['e2_basis'] == 'second_episode_deadline'
    else:
        deadline = first_pose + 54_000_000_000
        assert after['_meta']['e2_basis'] == 'legacy_54s_not_run_bound'
    assert all(r['tail'] == (r['pose_stamp_ns'] >= deadline) for r in new)
    tail_n = sum(r['tail'] for r in new)
    assert tail_n == after['states']['tail_rows']
    blocks = after['blocks']
    assert len(blocks) == before['states']['blocks'] == after['states']['blocks']
    assert all(b['state'] == 'UNKNOWN' for b in blocks)
    tail_blocks = [b for b in blocks if b['tail']]
    assert len(tail_blocks) == after['states']['tail_blocks']
    membership = sum(r['pose_stamp_ns'] // 500_000_000 in {b['block_id'] for b in tail_blocks} for r in new)
    assert membership == after['states']['tail_rows_by_block']
    reports.append(dict(run=run, population=len(new), numeric_i_unchanged=numeric_unchanged,
                        present=after['channels']['I_present'], zero_constraint_rows=len(zeros),
                        unchanged_input_hashes=True, changed_tail_rows=changed_tail,
                        tail_rows=tail_n, tail_blocks=len(tail_blocks), tail_block_members=membership,
                        all_unknown=True, first_scan_sentinel_all=all(int(r[first]) == -1 for r in valid),
                        raw_header_qualification=after['_meta']['i_qualification_layers']['RAW_HEADER_CONTAINMENT'],
                        join_status=after['_meta']['join_status'], basis=after['_meta']['e2_basis'],
                        zero_constraint_kf_ids=zeros,
                        exact_deadline_ns=deadline,
                        quantized_tail_start_ns=tail_blocks[0]['block_id'] * 500_000_000,
                        zero_constraint_fails_normal_support='source/qualification says no normal support; all states remain UNKNOWN'))
assert reports[0]['raw_header_qualification'] == 'PASS' and reports[0]['first_scan_sentinel_all']
result = dict(main=MAIN, comparison=OLD,
              command='C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_cdd3bf7/run_checks.py',
              scope='fixed data arithmetic and AST constant inspection only; no full CLI/host/math rerun',
              checks=reports,
              finding=dict(status='FAIL_REPRODUCED_SAVED_METADATA',
                           defect='RAW_HEADER_CONTAINMENT emitted as unconditional PASS for legacy sentinel trace',
                           minimum='derive this one qualification from existing join mode; preserve legacy heuristic rows'),
              hashes=HASHES)
output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'hashes'}, ensure_ascii=False, indent=2))
