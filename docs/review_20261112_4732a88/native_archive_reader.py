"""Bounded earlier off/on/buffered archive summary and ACK reader; no archived code."""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'ffd4b13ce86d03556e389e42236e913d4701cf8d'
PREFIX = 'docs/review_20261112_four_host/trace_fl_native_20261112T'


def blob(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', TARGET + ':' + path])


def ack_fields(ack):
    return {k: int(v) for k, v in re.findall(r'\b(stamp_ns|frame|repair_received|repair_applied|repair_dropped|replay_within_end|replay_suffix|set_state)=(\d+)', ack or '')}


runs = []
for suffix in ('112254Z_445825', '112753Z_454009', '113855Z_464306'):
    prefix = PREFIX + suffix + '/'
    receipt_raw = blob(prefix + 'receipt.json')
    summary_raw = blob(prefix + 'run_summary.json')
    receipt, summary = json.loads(receipt_raw), json.loads(summary_raw)
    episodes = []
    for ep in summary['quarantine']['episode_detail']:
        cp = ep.get('native_checkpoint', {})
        episodes.append({'index': ep['index'], 'quarantine_start_ns': ep['quarantine_start_ns'],
                         'command': cp.get('command'), 'ok': cp.get('ok'), 'ack': cp.get('ack'),
                         'ack_fields': ack_fields(cp.get('ack')), 'replay_suffix': ep.get('replay_suffix'),
                         'published': ep.get('repair_publish', {}).get('published')})
    runs.append({'run_id': summary['run_id'], 'receipt_sha256': hashlib.sha256(receipt_raw).hexdigest(),
                 'summary_sha256': hashlib.sha256(summary_raw).hexdigest(),
                 'library': receipt['inputs']['runtime_library_sha256'], 'source': receipt['inputs']['recovery_node_source'],
                 'status': receipt['status'], 'paired': summary['pairing']['paired'], 'episodes': episodes})
assert runs[0]['library'] == runs[1]['library'] != runs[2]['library']
assert runs[0]['episodes'][0]['ack_fields']['repair_applied'] == 23
assert runs[1]['episodes'][0]['ack_fields']['repair_applied'] == 0
assert runs[1]['episodes'][0]['ack_fields']['repair_dropped'] == 23
assert runs[1]['episodes'][0]['ack_fields']['stamp_ns'] == 1627785302359221248
assert runs[2]['episodes'][0]['ack_fields']['repair_applied'] == 23
assert runs[2]['episodes'][0]['ack_fields']['stamp_ns'] == 1627785272199251712
out_raw = blob(PREFIX + '113855Z_464306/host_logs/mat_out.txt')
out = [[float(v) for v in line.split()] for line in out_raw.decode().splitlines() if line.strip()]
last = out[-1]
result = {'archive_target': TARGET,
          'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4732a88/native_archive_reader.py',
          'runs': runs, 'buffered_mat_out': {'sha256': hashlib.sha256(out_raw).hexdigest(), 'rows': len(out),
                                            'last_relative_seconds': last[0], 'last_xyz': last[4:7],
                                            'last_recorded_position_norm_m': math.sqrt(sum(v*v for v in last[4:7])),
                                            'scope': 'Recorded world-coordinate position norm, not GT error or ATE'},
          'bad_on_reprocess_used_second_event_checkpoint': True,
          'unique_cause_flush_or_slot_overwrite': 'UNKNOWN; actual cp differs, final deployed source binding incomplete',
          'no_host_ROS_parameters_or_archived_code_execution': True}
output = Path(__file__).with_name('native_archive_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'runs'}, ensure_ascii=False, indent=2))
