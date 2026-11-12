"""Reviewed legacy pose-index arithmetic and v11 named-parser control; no native/CLI run."""
import ast
from collections import Counter, defaultdict
import bisect
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
MAIN = '23e019bf7f9ac4bab71db9e50a009db704ffb952'
ARCHIVE = '290aae8441fedc24dfbf316b8150880b63fae0b1'
P = 'docs/ali_h_v1_research/'
RUN = 'docs/review_20261112_four_host/trace_fl_native_20261112T115734Z_483777/'


def blob(ref, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])


raw = blob(MAIN, P + 't2_run.py')
tree = ast.parse(raw)
names = ('so3_exp', 'so3_left_jacobian_inv', 'quat_to_rot', 'exact_e', 'so3_log',
         'e_i_from_poses', '_tail_value', 'pose_from_tail', 'parse_trace', 'build_join', 'i_evidence')
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert len(functions) == len(names)
ns = {'np': np, 'math': math, 'Any': Any, 'Dict': Dict, 'List': List, 'Optional': Optional,
      'defaultdict': defaultdict, 'Counter': Counter, 'bisect': bisect}
exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), MAIN + ':reviewed_functions', 'exec'), ns)
trace_raw = blob(ARCHIVE, RUN + 'host_logs/trace_cov.txt')
ns['open'] = lambda *args, **kwargs: io.StringIO(trace_raw.decode())
trace = ns['parse_trace']('fixed_git_trace')
av_raw = gzip.decompress(blob(ARCHIVE, RUN + 'availability_frames.jsonl.gz'))
av = [json.loads(row) for row in av_raw.splitlines() if row.strip()]
pose_raw = blob(ARCHIVE, RUN + 'host_logs/M2DGR_room_02.txt')
m2 = np.array([[float(x) for x in row.split()] for row in pose_raw.decode().splitlines() if row.strip()])
ho_rows = [r for r in trace['rows'] if r['has_out'] == 1]
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
start = next(i for i, n in enumerate(fn.body) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'pose_rows' for t in n.targets))
end = next(i for i, n in enumerate(fn.body[start:], start) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'join' for t in n.targets))
join_ns = dict(ns, m2=m2.copy(), ho_rows=ho_rows)
exec(compile(ast.fix_missing_locations(ast.Module(body=fn.body[start:end], type_ignores=[])), MAIN + ':reviewed_existing_pose_join', 'exec'), join_ns)
buggy = join_ns['exact_by_idx']
# Independent lookup keeps original rows within each timestamp, never treats a sorted index as original.
pose_groups = defaultdict(list)
for original_index, row in enumerate(m2):
    pose_groups[int(round(float(row[0]) * 1e9))].append(original_index)
keys = sorted(pose_groups)
used = Counter()
correct = {}
for row in ho_rows:
    i = bisect.bisect_left(keys, row['abs_ns'])
    candidates = [k for k in keys[max(0, i - 1):i + 2] if abs(k - row['abs_ns']) <= 2000]
    assert len(candidates) == 1
    key = candidates[0]
    k = used[key]
    assert k < len(pose_groups[key])
    index = pose_groups[key][k]
    used[key] += 1
    correct[row['idx']] = ns['exact_e'](row['vec6'], ns['quat_to_rot'](m2[index, 4:8]))
summary = json.loads(blob(MAIN, P + 't2_summary.json'))
saved_rows = [json.loads(row) for row in blob(MAIN, P + 't2_join.jsonl').splitlines() if row.strip()]
assert summary['_meta']['trace_sha256'] == hashlib.sha256(trace_raw).hexdigest()
assert summary['_meta']['availability_sha256'] == hashlib.sha256(av_raw).hexdigest()
values_buggy, values_correct, differences = [], [], []
for mapping, saved in zip(ns['build_join'](av, trace)['mapped'], saved_rows):
    before = ns['i_evidence'](mapping['rows'], buggy)
    after = ns['i_evidence'](mapping['rows'], correct)
    assert before['present'] == after['present'] == saved['i']['present']
    if before['present']:
        assert abs(before['s_i'] - saved['i']['s_i']) < 1e-7
        values_buggy.append(before['s_i'])
        values_correct.append(after['s_i'])
        if abs(after['s_i'] - before['s_i']) > 1e-7:
            differences.append({'kf_id': saved['kf_id'], 'trace_idx': before['trace_idx'],
                                'saved_s': before['s_i'], 'original_row_s': after['s_i']})
assert len(values_buggy) == len(values_correct) == 504 and len(differences) == 92
# Use the existing ordinary SE3 example, now through actual same-row pose helper, not vec6 reconstruction.
pre = np.array([0, 0, 0, 0, 0, 0, 1], dtype=float)
post = np.array([.1, 0, 0, 0, 0, math.sin(.1), math.cos(.1)])
actual = ns['e_i_from_poses'](pre, post)
expected = np.array([0, 0, .2, .1 * .1 / math.tan(.1), -.01, 0])
assert np.allclose(actual, expected)
scalars = [7, 12.5, 1627785261379575296, 42, 1627785261379575000, 1627785261379575296,
           1, 1, 0, 99, .1, .2, .3, 4., 5.]
base_names = 'idx rel_s abs_ns grp_idx scan_first_ns scan_last_ns n_scans has_out phase eff r_mean r_med r_abs_mean r_chi2 r_chi2w vec6 Ppre6x6 Ppost6x6'
fields = scalars + [0] * 6 + np.eye(6).reshape(-1).tolist() + np.eye(6).reshape(-1).tolist() + post.tolist() + pre.tolist()
assert len(fields) == 107
named = base_names + ' ' + ' '.join(prefix + '_' + leaf for prefix in ('pose', 'pre_pose') for leaf in ('x', 'y', 'z', 'qx', 'qy', 'qz', 'qw'))
controls = []
for kind, header in [('named107', named), ('declared_block107', base_names + ' pose7 pre_pose7')]:
    ns['open'] = lambda *args, h=header, **kwargs: io.StringIO('# ' + h + '\n' + ' '.join(str(x) for x in fields) + '\n')
    parsed = ns['parse_trace']('in_memory_header_control')
    if kind == 'named107':
        assert len(parsed['rows']) == 1 and not parsed['malformed']
        r = parsed['rows'][0]
        assert np.allclose(r['pre_pose'], pre) and np.allclose(ns['pose_from_tail'](r['pose_tail']), post)
    else:
        assert not parsed['rows'] and parsed['malformed'] == [{'line': 2, 'ncols': 107}]
    controls.append({'case': kind, 'rows': len(parsed['rows']), 'malformed': parsed['malformed'],
                     'scope': 'block header to be checked against separately reviewed actual archived producer/run'})
report = {'main': MAIN, 'legacy_archive': ARCHIVE,
          'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_23e019b/run_checks.py',
          'source_sha256': hashlib.sha256(raw).hexdigest(), 'legacy_pose_sha256': hashlib.sha256(pose_raw).hexdigest(),
          'legacy_source_bound_sorted_index_defect': {'status': 'FAIL_REPRODUCED_existing_archive',
              'diagnostic_present_rows': 504, 'different_rows': len(differences),
              'saved_median_s': float(np.median(values_buggy)), 'original_row_lookup_median_s': float(np.median(values_correct)),
              'differences': differences, 'scientific_scope': 'same old heuristic join only, not qualified I or performance'},
          'same_row_pose_SE3_control': {'status': 'PASS_LOCAL', 'actual': actual.tolist(), 'expected': expected.tolist()},
          'v11_parser_controls': controls,
          'saved_population_state': summary['states'],
          'repo_host_order': 'read-only restrictive handoff observed; no new FAST-LIVO2 actions commissioned; repo user quote not independently authenticated here',
          'no_archived_CLI_native_build_parameter_or_full_test_execution': True}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({**report, 'legacy_source_bound_sorted_index_defect': {k: v for k, v in report['legacy_source_bound_sorted_index_defect'].items() if k != 'differences'}}, ensure_ascii=False, indent=2))
