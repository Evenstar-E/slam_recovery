"""Exact archived detection-on episode ACKs; no archive code or native execution."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'ffd4b13ce86d03556e389e42236e913d4701cf8d'
PREFIX = 'docs/review_20261112_four_host/trace_fl_native_20261112T'
results = []
for suffix in ('115203Z_476840', '115734Z_483777'):
    path = PREFIX + suffix + '/run_summary.json'
    raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', TARGET + ':' + path])
    summary = json.loads(raw)
    episodes = []
    for ep in summary['quarantine']['episode_detail']:
        cp = ep.get('native_checkpoint') or {}
        fields = {k: int(v) for k, v in re.findall(r'\b(stamp_ns|frame|repair_applied|repair_dropped|replay_within_end|replay_suffix)=(-?\d+)', cp.get('ack', ''))}
        start = ep.get('quarantine_start_ns')
        episodes.append({'index': ep['index'], 'trigger_ts_ns': ep.get('trigger_ts_ns'),
                         'quarantine_start_ns': start, 'native_checkpoint': cp,
                         'ack_fields': fields,
                         'cp_minus_quarantine_start_ns': fields.get('stamp_ns') - start if fields.get('stamp_ns', -1) > 0 and start else None,
                         'repair_published': ep.get('repair_publish', {}).get('published'),
                         'scope': 'Actual ACK fields in archived driver summary; no inference all state/cache restored'})
    results.append({'run_id': summary['run_id'], 'summary_sha256': hashlib.sha256(raw).hexdigest(),
                    'detection_enabled': summary['detection_enabled'], 'paired': summary['pairing']['paired'],
                    'episode_count': summary['quarantine']['episodes'], 'episodes': episodes})
assert results[0]['episodes'][0]['native_checkpoint']['ok'] is False
assert results[1]['episodes'][0]['native_checkpoint']['ok'] is False
accepted = results[1]['episodes'][3]
assert accepted['ack_fields']['repair_applied'] == 0 and accepted['ack_fields']['repair_dropped'] == 42
assert accepted['cp_minus_quarantine_start_ns'] == 19914598827
payload = {'archive_target': TARGET, 'runs': results,
           'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4732a88/episode_reader.py',
           'first_automatic_refusal_has_no_native_cp_in_both_runs': True,
           'accepted_run_has_cp_19_914598827_seconds_after_quarantine_start': True,
           'scripted_and_automatic_mixed_not_pure_autonomous_chain': True,
           'no_ROS_host_parameter_or_archived_code_execution': True}
output = Path(__file__).with_name('episode_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in payload.items() if k != 'runs'}, ensure_ascii=False, indent=2))
