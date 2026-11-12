"""Bounded producer/consumer header checks; no archived CLI, native execution or new data."""
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

# Explicit existing numerical dependency, not imports from an archived script directory.
sys.path.append('C:/Users/R26534/AppData/Roaming/Python/Python315/site-packages')
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = '22d79337ba80c01ae05988d7dec3bb87db0f0e60'
HOST = 'eb2630ef10f827626ee1eaad87fa7ddc39cc825c'
PREFIX = 'docs/ali_h_v1_research/'
HP = 'docs/review_20261112_four_host/host_change_trace_cov/'


def blob(ref, path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])


host_raw = blob(HOST, HP + 'src_LIVMapper.cpp.v10')
host = host_raw.decode()
start = host.index('<< "# idx ')
end = host.index('<< "#   abs_ns', start)
# Decode only the actual C++ header string literals, preserving the writer's pose7 block token.
header = ''.join(json.loads(literal) for literal in re.findall(r'"(?:[^"\\]|\\.)*"', host[start:end]))
assert header.startswith('# idx ') and header.endswith('Ppost6x6 pose7\n')
source = blob(TARGET, PREFIX + 't2_run.py')
tree = ast.parse(source)
selftest = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'selftest_100col')
selftest_names = ast.literal_eval(next(node.value for node in selftest.body
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'names' for t in node.targets)))
expanded_header = '# ' + ' '.join(selftest_names) + '\n'
pose = [1.5, -2.0, .25, .1, .2, .3, .92736185]
scalars = [7, 12.5, 1627785261379575296, 42, 1627785261379575000, 1627785261379575296,
           1, 1, 0, 99, .1, .2, .3, 4., 5.]
fields = scalars + [.01, -.02, .03, -.04, .05, -.06] + (np.eye(6) * .01).reshape(-1).tolist() + (np.eye(6) * .02).reshape(-1).tolist() + pose
assert len(fields) == 100
cases = [('actual_v10_header_100', header, fields),
         ('selftest_named_header_100', expanded_header, fields),
         ('legacy_v8_header_93', header.replace(' pose7', ''), fields[:-7])]
checks = []
for file in ('t2_run.py', 't2_join_upgrade.py'):
    raw = blob(TARGET, PREFIX + file)
    tree = ast.parse(raw)
    names = ('parse_trace', '_tail_value', 'pose_from_tail') if file == 't2_run.py' else ('parse_trace',)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(functions) == len(names)
    for name, h, row in cases:
        text = h + ' '.join(str(x) for x in row) + '\n'
        ns = {'np': np, 'Any': Any, 'Dict': Dict, 'List': List, 'Optional': Optional,
              'open': lambda *args, **kwargs: io.StringIO(text)}
        module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
        exec(compile(module, TARGET + ':reviewed_parser_functions_only', 'exec'), ns)
        result = ns['parse_trace']('in_memory_source_bound_control')
        p = ns['pose_from_tail'](result['rows'][0]['pose_tail']) if file == 't2_run.py' and result['rows'] else None
        if name == 'actual_v10_header_100':
            assert result['rows'] == [] and result['malformed'] == [{'line': 2, 'ncols': 100}]
            status = 'FAIL_REPRODUCED_actual_writer_header_not_supported'
        else:
            assert len(result['rows']) == 1 and result['malformed'] == []
            status = 'PASS_LOCAL_parser_scope'
            if name == 'selftest_named_header_100':
                assert len(result['rows'][0]['pose_tail']) == 7
                if file == 't2_run.py':
                    assert p is not None and np.allclose(p, pose)
            else:
                assert result['rows'][0]['pose_tail'] is None
        checks.append({'parser': file, 'case': name, 'rows': len(result['rows']),
                       'malformed': result['malformed'], 'pose_tail_values': None if p is None else p.tolist(),
                       'status': status})
assert 'if r["idx"] in exact_by_idx or len(m2) == 0:' in source.decode()
# No new numerical population was published in this parser-only delta.
unchanged = {}
for file in ('t2_join.jsonl', 't2_summary.json'):
    raw = blob(TARGET, PREFIX + file)
    assert raw == blob('66cc814', PREFIX + file)
    unchanged[file] = hashlib.sha256(raw).hexdigest()
qualification = blob(TARGET, PREFIX + 'T2_I_ELIGIBILITY.md').decode()
assert 'PASS（单扫描）' not in qualification and 'PASS（v8 时间 join）' not in qualification
report = {
    'target': TARGET, 'host_archive': HOST,
    'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_22d7933/run_checks.py',
    'reader_sha256': hashlib.sha256(source).hexdigest(), 'host_source_sha256': hashlib.sha256(host_raw).hexdigest(),
    'actual_writer_header': header.rstrip(), 'selftest_header': expanded_header.rstrip(),
    'actual_tail_names_count': 1, 'actual_tail_block_width': 7,
    'parser_expected_columns_for_actual_header': [93, 94], 'writer_columns': 100,
    'controls': checks,
    'inline_pose_branch': 'SOURCE_PRESENT: uses parsed same-row quaternion and skips external fallback when idx is present; actual v10 header produces no parsed rows',
    'qualification_subclaims_narrowed': True, 'saved_results_unchanged_sha256': unchanged,
    'new_bag_trace_or_native_recovery': 'NONE_IN_DELTA', 'real_I_qualification': 'INCOMPLETE/UNKNOWN',
    'full_selftest_or_archived_CLI_execution': False, 'no_ROS_build_parameters_or_production_code_changed': True,
}
output = Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
