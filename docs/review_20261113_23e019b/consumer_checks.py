"""Current readers against the archived run's reported block header; no native/CLI run."""
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional

sys.path.append('C:/Users/R26534/AppData/Roaming/Python/Python315/site-packages')
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MAIN = '23e019bf7f9ac4bab71db9e50a009db704ffb952'
PREFIX = 'docs/ali_h_v1_research/'
HEADER = '# idx rel_s abs_ns grp_idx scan_first_ns scan_last_ns n_scans has_out phase eff r_mean r_med r_abs_mean r_chi2 r_chi2w vec6 Ppre6x6 Ppost6x6 pose7 pre_pose7'


def blob(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', MAIN + ':' + path])


row = ['0'] * 107
row[6] = row[7] = '1'
row[99] = row[106] = '1'
text = HEADER + '\n' + ' '.join(row) + '\n'
results = []
for file in ('t2_run.py', 't2_join_upgrade.py'):
    raw = blob(PREFIX + file)
    tree = ast.parse(raw)
    names = ('parse_trace', 'pose_from_tail', '_tail_value') if file == 't2_run.py' else ('parse_trace',)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = {'np': np, 'Any': Any, 'Dict': Dict, 'List': List, 'Optional': Optional,
          'open': lambda *a, **k: io.StringIO(text)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), MAIN + ':reviewed_header_consumer', 'exec'), ns)
    parsed = ns['parse_trace']('in_memory_107_control')
    assert parsed['rows'] == [] and parsed['malformed'] == [{'line': 2, 'ncols': 107}]
    results.append({'parser': file, 'sha256': hashlib.sha256(raw).hexdigest(), 'parsed_rows': 0,
                    'malformed': parsed['malformed'], 'status': 'FAIL_REPRODUCED_BLOCK_HEADER_107'})
result = {'main': MAIN, 'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_23e019b/consumer_checks.py',
          'header': HEADER, 'header_origin': 'Fixed a812302 run header reported by independent archive reader; archive_checks.json retains header and trace SHA',
          'field_layout': '15+6+36+36+7+7=107; Ppost6x6 followed by two block names, not 14 scalar field names',
          'current_reader_expected_width_for_header': [93, 95], 'actual_declared_width': 107,
          'controls': results, 'no_archived_CLI_or_host_execution': True}
output = Path(__file__).with_name('consumer_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
