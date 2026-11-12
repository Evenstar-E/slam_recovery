"""Check summary claims against fixed existing artifacts; no archived executable imports."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = 'd17d5526157b97b374f79cf70b5bcb8465f8a096'
ONLINE = 'e991eaf'
P = 'docs/review_20261112_four_host/trace_online_fl_native_20261112T121127Z_497953/'
HASHES = {}


def blob(ref, path):
    raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + path])
    HASHES[ref + ':' + path] = hashlib.sha256(raw).hexdigest()
    return raw


report_raw = blob(MAIN, 'docs/OVERNIGHT_RESULTS_20261113_S1.md')
report_text = report_raw.decode()
receipt = json.loads(blob(ONLINE, P + 'receipt.json'))
trace = blob(ONLINE, P + 'host_logs/trace_cov.txt').decode()
lines = [l.split() for l in trace.splitlines() if l.strip() and not l.startswith('#')]
widths = {width: sum(len(row) == width for row in lines) for width in sorted({len(row) for row in lines})}
header = next(l for l in trace.splitlines() if l.startswith('# idx '))
assert 'pose7' not in header and set(widths) == {92}
assert '纯在线自动链（v11）' in report_text
assert receipt['inputs']['runtime_library_sha256'].startswith('49f2f941')
old_host = json.loads(blob('0df6ea83020af92424c463ebb236ad35581de2f1',
                           'docs/review_20261113_b2f3983/extended_checks.json'))
assert old_host['run2']['recovery_wiring'] == 'NOT_IMPLEMENTED'
assert old_host['run2']['runner_records_clouds']
assert old_host['independent_workspace_evidence']['original_upstream_implementation_identity'] == 'NOT_VERIFIED'
assert old_host['run2']['saved_metrics_shared_compatible']
qualification = json.loads(blob(MAIN, 'docs/ali_h_v1_research/t2_v11_summary.json'))
assert qualification['_meta']['i_qualification_layers']['COVARIANCE_6D'] == 'NOT_AVAILABLE'
assert qualification['_meta']['covariance_status'].startswith('NOT_AVAILABLE_FOR_E_I')
assert qualification['channels']['I_zero_eff_rows'] == 18
changed = subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only',
                                  'f795643b774bfe0ecb6b39d7aaa17f2d4ba700a2', MAIN]).decode().splitlines()
assert changed == ['docs/OVERNIGHT_RESULTS_20261113_S1.md']
result = {
    'main': MAIN, 'comparison': 'f795643b774bfe0ecb6b39d7aaa17f2d4ba700a2',
    'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_d17d552/run_checks.py <new-output>',
    'scope': 'fixed summary/receipt/schema plus previously accepted review and saved meta; no new host or repeated numeric audit',
    'new_files': changed,
    'online_run_label': {'status': 'FAIL_VERSION_LABEL', 'claimed_version': 'v11',
                         'actual_run': receipt['run_id'], 'actual_trace_width_counts': widths,
                         'actual_header': header,
                         'library': receipt['inputs']['runtime_library_sha256'],
                         'binary': receipt['inputs']['host_binary_sha256'],
                         'driver': receipt['inputs']['recovery_node_source'],
                         'scope': 'old 92-column trace lacks v11 same-row pose pair; actual 42 applications not invalidated'},
    'covariance_claim': {'summary_says_fixed': '协方差切空间未绑定' in report_text,
                         'actual_COVARIANCE_6D': 'NOT_AVAILABLE',
                         'meaning': 'limitation declared, not residual covariance implemented/qualified'},
    'host_scope_reused': {'source_upstream_verified': False, 'records_clouds': True,
                          'restored_wiring': 'NOT_IMPLEMENTED',
                          'output_metrics_compatible_in_saved_scope': True,
                          'e2_outage_s': old_host['run2']['actual_saved_outages'][1]['dt_s']},
    'no_new_execution_evidence': True, 'hashes': HASHES}
output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
