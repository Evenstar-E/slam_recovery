"""Bounded fixed-blob controls and saved-number audit; no archived CLI/native run."""
import ast
import bisect
from collections import Counter, defaultdict
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional

sys.path.append('C:/Users/R26534/AppData/Roaming/Python/Python315/site-packages')
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MAIN = '1f7a6dc35e720b807502acdc258b2f0891c53f47'
OLD = '23e019bf7f9ac4bab71db9e50a009db704ffb952'
GROWTH = 'a812302e3a9acd17b1e6f318d332b88563910069'
LEGACY = '290aae8441fedc24dfbf316b8150880b63fae0b1'
P = 'docs/ali_h_v1_research/'
RUN = 'docs/review_20261112_four_host/'
BINDINGS = {}


def blob(ref, path):
    raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])
    BINDINGS[ref + ':' + path] = hashlib.sha256(raw).hexdigest()
    return raw


def reviewed_namespace(raw, full=True):
    tree = ast.parse(raw)
    names = {'expand_tail_names', 'parse_trace'}
    if full:
        names |= {'so3_exp', 'so3_left_jacobian_inv', 'quat_to_rot', 'exact_e',
                  'so3_log', 'e_i_from_poses', '_tail_value', 'pose_from_tail',
                  'build_join', 'i_evidence'}
    fs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(fs) == len(names)
    ns = dict(np=np, math=math, Any=Any, Dict=Dict, List=List, Optional=Optional,
              Counter=Counter, defaultdict=defaultdict, bisect=bisect,
              POSE_LEAVES=('x', 'y', 'z', 'qx', 'qy', 'qz', 'qw'))
    exec(compile(ast.fix_missing_locations(ast.Module(body=fs, type_ignores=[])),
                 MAIN + ':reviewed_functions', 'exec'), ns)
    return tree, ns


raw = blob(MAIN, P + 't2_run.py')
tree, ns = reviewed_namespace(raw)
growth_path = RUN + 'growth_fl_native_20261112T165438Z_669633/'
traw = blob(GROWTH, growth_path + 'host_logs/trace_cov.txt')
parser_checks = []
for file in ('t2_run.py', 't2_join_upgrade.py'):
    _, pn = reviewed_namespace(blob(MAIN, P + file), full=(file == 't2_run.py'))
    pn['open'] = lambda *a, **k: io.StringIO(traw.decode())
    parsed = pn['parse_trace']('fixed_actual_block_header')
    assert len(parsed['rows']) == 792 and parsed['malformed'] == []
    for original, r in zip((l.split() for l in traw.decode().splitlines()
                            if l.strip() and not l.startswith('#')), parsed['rows']):
        tail = r['pose_tail']
        for prefix, start in [('pose', 93), ('pre_pose', 100)]:
            assert [tail[prefix + '_' + leaf] for leaf in pn['POSE_LEAVES']] == [
                float(x) for x in original[start:start + 7]]
    parser_checks.append(dict(parser=file, status='PASS_ACTUAL_ARCHIVED_107',
                              rows=792, malformed=0, all_fourteen_pose_values_equal=True))
ns['open'] = lambda *a, **k: io.StringIO(traw.decode())
trace = ns['parse_trace']('fixed_actual_trace')
avraw = gzip.decompress(blob(GROWTH, growth_path + 'availability_frames.jsonl.gz'))
av = [json.loads(l) for l in avraw.splitlines() if l.strip()]
saved_summary = json.loads(blob(MAIN, P + 't2_v11_summary.json'))
saved = [json.loads(l) for l in blob(MAIN, P + 't2_v11_join.jsonl').splitlines() if l.strip()]
for key, value in [('trace_sha256', traw), ('availability_sha256', avraw),
                   ('receipt_sha256', blob(GROWTH, growth_path + 'receipt.json')),
                   ('summary_sha256', blob(GROWTH, growth_path + 'run_summary.json'))]:
    assert saved_summary['_meta'][key] == hashlib.sha256(value).hexdigest()

# Independently form relative rotations/translations, then solve V*rho=t.
# This does not use the reviewed helper's inverse-Jacobian formula.
def independent_log(pre, post):
    Rp, Rq = ns['quat_to_rot'](pre[3:]), ns['quat_to_rot'](post[3:])
    R = Rp.T @ Rq
    t = Rp.T @ (post[:3] - pre[:3])
    theta = math.acos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    if theta < 1e-10:
        w = np.zeros(3)
    else:
        w = theta / (2 * math.sin(theta)) * np.array(
            [R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    V = (np.eye(3) + .5 * K + K @ K / 6 if theta < 1e-5 else
         np.eye(3) + (1 - math.cos(theta)) / theta**2 * K +
         (theta - math.sin(theta)) / theta**3 * K @ K)
    return np.r_[w, np.linalg.solve(V, t)]

exact = {}
for r in trace['rows']:
    if r['has_out'] == 1:
        post = ns['pose_from_tail'](r['pose_tail'])
        e = ns['e_i_from_poses'](r['pre_pose'], post)
        assert np.allclose(e, independent_log(r['pre_pose'], post), atol=1e-8, rtol=1e-8)
        exact[r['idx']] = e
assert len(exact) == 725
join = ns['build_join'](av, trace)
assert len(join['mapped']) == len(saved) == 482
norms, energies, scores, selected, missing = [], [], [], [], Counter()
for m, s in zip(join['mapped'], saved):
    independent_rows = [r for r in trace['rows'] if
                        abs(r['scan_first_ns'] - int(m['av']['scan_stamp_ns'])) <= 512 and
                        r['scan_first_ns'] == r['scan_last_ns']]
    assert [r['idx'] for r in m['rows']] == [r['idx'] for r in independent_rows]
    assert s['kf_id'] == m['av']['kf_id'] and s['grp_rows'] == [r['idx'] for r in m['rows']]
    actual = ns['i_evidence'](m['rows'], exact)
    assert actual.keys() == s['i'].keys()
    for key, value in actual.items():
        recorded = s['i'][key]
        assert (math.isclose(value, recorded, rel_tol=1e-10, abs_tol=1e-10)
                if isinstance(value, float) and isinstance(recorded, (int, float))
                else value == recorded), (s['kf_id'], key, value, recorded)
    if actual['present']:
        r = next(r for r in m['rows'] if r['idx'] == actual['trace_idx'])
        selected.append(r)
        norms.append(actual['e_norm']); energies.append(actual['e_norm']**2); scores.append(actual['s_i'])
    else:
        missing[actual['reason']] += 1
assert len(norms) == saved_summary['channels']['I_present'] == 462
assert sum(not m['rows'] for m in join['mapped']) == 1
assert sum(len(m['rows']) == 2 for m in join['mapped']) == 246
assert np.isclose(np.median(norms), saved_summary['channels']['I_e_norm']['median'])
assert len(saved_summary['blocks']) == 106
assert all(b['state'] == 'UNKNOWN' for b in saved_summary['blocks'])
assert all(s['shadow_state'] == 'UNKNOWN' for s in saved)

# Only the existing 504-row normal-path defect is rechecked; no new host execution.
legacy_path = RUN + 'trace_fl_native_20261112T115734Z_483777/'
lraw = blob(LEGACY, legacy_path + 'host_logs/trace_cov.txt')
ns['open'] = lambda *a, **k: io.StringIO(lraw.decode())
lt = ns['parse_trace']('fixed_legacy_trace')
lavraw = gzip.decompress(blob(LEGACY, legacy_path + 'availability_frames.jsonl.gz'))
lav = [json.loads(l) for l in lavraw.splitlines() if l.strip()]
mraw = blob(LEGACY, legacy_path + 'host_logs/M2DGR_room_02.txt')
m2 = np.array([[float(x) for x in l.split()] for l in mraw.decode().splitlines() if l.strip()])
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
start = next(i for i, n in enumerate(fn.body) if isinstance(n, ast.Assign) and
             any(isinstance(t, ast.Name) and t.id == 'pose_rows' for t in n.targets))
end = next(i for i, n in enumerate(fn.body[start:], start) if isinstance(n, ast.Assign) and
           any(isinstance(t, ast.Name) and t.id == 'join' for t in n.targets))
lookup = dict(ns, m2=m2, ho_rows=[r for r in lt['rows'] if r['has_out'] == 1])
exec(compile(ast.fix_missing_locations(ast.Module(body=fn.body[start:end], type_ignores=[])),
             MAIN + ':reviewed_pose_lookup', 'exec'), lookup)
old_saved = [json.loads(l) for l in blob(OLD, P + 't2_join.jsonl').splitlines() if l.strip()]
new_saved = [json.loads(l) for l in blob(MAIN, P + 't2_join.jsonl').splitlines() if l.strip()]
assert len(old_saved) == len(new_saved) == 531
changes, legacy_scores = [], []
for m, before, after in zip(ns['build_join'](lav, lt)['mapped'], old_saved, new_saved):
    assert {k: v for k, v in before.items() if k != 'i'} == {k: v for k, v in after.items() if k != 'i'}
    actual = ns['i_evidence'](m['rows'], lookup['exact_by_idx'])
    assert actual.keys() == after['i'].keys()
    for key, value in actual.items():
        recorded = after['i'][key]
        assert (math.isclose(value, recorded, rel_tol=1e-10, abs_tol=1e-10)
                if isinstance(value, float) and isinstance(recorded, (int, float))
                else value == recorded), (after['kf_id'], key, value, recorded)
    if actual['present']:
        legacy_scores.append(actual['s_i'])
        if abs(actual['s_i'] - before['i']['s_i']) > 1e-7:
            changes.append(after['kf_id'])
assert len(legacy_scores) == 504 and len(changes) == 92


def quantiles(values):
    return {key: float(v) for key, v in zip(('p10', 'p50', 'p90', 'max'),
            [*np.percentile(values, [10, 50, 90]), max(values)])}

zero_eff = [r for r in selected if r['eff'] == 0]
window_counts = []
for lo in range(5, 55, 5):
    rows = [r for r in trace['rows'] if lo <= r['rel_s'] < lo + 5]
    valid = [r for r in rows if r['has_out'] == 1]
    window_counts.append(dict(rel_window=[lo, lo + 5], all_rows=len(rows), has_out_rows=len(valid),
                              eff_median_all=float(np.median([r['eff'] for r in rows])),
                              eff_median_hasout=float(np.median([r['eff'] for r in valid])) if valid else None))
source_summary = json.loads(blob(GROWTH, growth_path + 'run_summary.json'))
origin_ns = trace['rows'][0]['abs_ns']
timeline = [{key: (episode[key] - origin_ns) / 1e9
             for key in ('quarantine_start_ns', 'trigger_ts_ns', 'deadline_ns')}
            for episode in source_summary['quarantine']['episode_detail']]
report = dict(main=MAIN, comparison=OLD,
              command='C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_1f7a6dc/run_checks.py',
              scope='reviewed AST functions/statements plus data blobs only; not full T2 CLI, native or build',
              parser_checks=parser_checks,
              legacy_closure=dict(status='PASS_EXISTING_DEFECT_CLOSED', population=531,
                                  diagnostics=504, changed_scores=92,
                                  median_s=float(np.median(legacy_scores)), unchanged_non_i_fields=True),
              v11=dict(source_pre_post_rows=725, independently_checked_logs=725,
                       paired=482, mapped=481, missing=dict(missing), multi_to_one=246,
                       selected_I=462, saved_i_fields_equal=True,
                       norm=quantiles(norms), unit_energy=quantiles(energies), diagnostic_s=quantiles(scores),
                       blocks=106, unknown_blocks=106, all_482_states_unknown=True,
                       selected_zero_eff=len(zero_eff),
                       selected_zero_eff_idx=[r['idx'] for r in zero_eff],
                       selected_zero_eff_nonzero_log=int(sum(np.linalg.norm(exact[r['idx']]) > 1e-9 for r in zero_eff)),
                       all_hasout_zero_eff=sum(r['has_out'] == 1 and r['eff'] == 0 for r in trace['rows']),
                       scope_limits=['raw-header containment is not full point/carryover membership',
                                     'eff=0 is not positive measurement information',
                                     'same-row log arithmetic is not calibrated detection or recovery performance',
                                     'legacy vec/mixed-cov qualification remains unchanged']),
              growth_report_checks=dict(origin_ns=origin_ns, episode_timeline=timeline,
                                        five_second_windows=window_counts,
                                        map_peak_series_available=False),
              bindings=BINDINGS)
output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
