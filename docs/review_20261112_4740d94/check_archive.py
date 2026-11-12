"""Pinned compressed archive readback, isolated stdlib only; never execute archived scripts."""
import collections
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = '4740d94a583886afc04b361aee3c6403d5072ecf'
PREFIX = 'docs/review_20261112_availability/predicted_pose/'


def blob(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', TARGET + ':' + path])


def read(name):
    return blob(PREFIX + name)


checks = []
for line in read('SHA256SUMS').decode().splitlines():
    expected, name = line.split()
    name = name.removeprefix('./')
    assert '..' not in Path(name).parts
    checks.append({'path': name, 'ok': hashlib.sha256(read(name)).hexdigest() == expected})
assert len(checks) == 14 and all(c['ok'] for c in checks)
compressed = read('availability_frames.jsonl.gz')
raw = gzip.decompress(compressed)
sidecar = {line.split()[0] for line in read('availability_sha256.txt').decode().splitlines()}
assert hashlib.sha256(compressed).hexdigest() in sidecar
assert hashlib.sha256(raw).hexdigest() in sidecar
rows = [json.loads(line) for line in raw.splitlines()]
summary = json.loads(read('run_summary.json'))
receipt = json.loads(read('receipt.json'))
analysis = json.loads(read('analysis.json'))
candidates = [json.loads(line) for line in read('candidates.jsonl').splitlines()]
assert len(rows) == summary['frames']['paired'] == len(summary['frame_diagnostics']) == 544
recorded = read('recovery_node_source.sha256').decode().split()[0]
assert recorded == receipt['inputs']['recovery_node_source'] == hashlib.sha256(blob('slam_recovery/ros/recovery_node.py')).hexdigest()
counts = collections.Counter()
null_trusted = collections.Counter()
combos = collections.Counter()
pred_saved = collections.Counter()
example = {}
for i, (r, d) in enumerate(zip(rows, summary['frame_diagnostics'])):
    assert r['kf_id'] == i == d['kf_id'] and r['pose_stamp_ns'] == d['ts_ns']
    assert r['pose_stamp_ns'] - r['scan_stamp_ns'] == r['pose_scan_dt_ns']
    assert r['nis']['effective_nis'] == d['nis']
    assert r['status'] == d['detection_status'] == r['status_from_conditions']
    assert r['status'] == ('AVAILABLE' if r['support_pass'] and r['nis_present'] else 'UNAVAILABLE')
    counts['status/' + r['status']] += 1
    counts['support_reason/' + r['support']['reason']] += 1
    p = r.get('support_under_predicted_pose')
    if p is None:
        counts['joint/no_prediction'] += 1
        null_trusted[r['manager']['trusted_keyframes']] += 1
        if r['support_pass']:
            counts['host_pass/null_prediction'] += 1
    else:
        h, pp = bool(r['support_pass']), bool(p.get('pass'))
        category = 'both_pass' if h and pp else 'only_pred_low' if h else 'only_host_low' if pp else 'both_low'
        counts['joint/' + category] += 1
        combos[str(h) + '/' + str(pp) + '/nis=' + str(r['nis_present'])] += 1
        points = p.get('points', [])
        pred_saved[len(points)] += 1
        if points:
            assert len(points) == p['sampled_query_count']
            assert sum(pt['within_1m'] for pt in points) == p['within_radius_count']
            assert p['within_radius_count'] / p['sampled_query_count'] == p['supported_fraction']
            assert pp == (p['supported_fraction'] >= p['threshold_fraction'])
        if r['manager']['trusted_keyframes'] == 1 and 'one_trusted_pose' not in example:
            example['one_trusted_pose'] = {'kf': i, 'status': r['status'], 'manager': r['manager'], 'pred_reason': p['reason'], 'pred_fraction': p.get('supported_fraction')}
    for name in ('both_pass', 'only_pred_low', 'only_host_low'):
        if p and category == name and name not in example:
            example[name] = {'kf': i, 'stamp_ns': r['pose_stamp_ns'], 'host_fraction': r['support'].get('supported_fraction'), 'pred_fraction': p.get('supported_fraction'), 'nis': r['nis']['effective_nis'], 'status': r['status']}
joint = {k.split('/')[1]: v for k,v in counts.items() if k.startswith('joint/')}
assert joint == analysis['joint']
windows = {}
for name, lo, hi in [('prev_53_117', 1627785267272356749, 1627785273678019524), ('prev_199_401', 1627785286344705820, 1627785306575157404)]:
    selected = [r for r in rows if lo <= r['pose_stamp_ns'] <= hi]
    windows[name] = {'frames': len(selected), 'host_pass': sum(r['support_pass'] for r in selected), 'available': sum(r['status']=='AVAILABLE' for r in selected), 'pred_pass': sum(bool((r.get('support_under_predicted_pose') or {}).get('pass')) for r in selected)}
    assert len(selected) == analysis['stamp_windows_from_previous_run'][name]['frames']
    assert windows[name]['host_pass'] == analysis['stamp_windows_from_previous_run'][name]['host']['pass']
    assert windows[name]['pred_pass'] == analysis['stamp_windows_from_previous_run'][name]['predicted']['pass']
events = summary['native_checkpoint'].get('events', [])
episode_details = summary['quarantine']['episode_detail']
segment_label_totals = collections.Counter()
for segment in analysis['unavailable_runs']:
    segment_label_totals[segment['reading']] += segment['frames']
result = {'target': TARGET, 'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4740d94/check_archive.py', 'exit': 0,
          'scope': 'Git bytes and compressed rows; no archived scripts, host or bag execution',
          'integrity': {'matched': len(checks), 'total': len(checks), 'compressed_sha': hashlib.sha256(compressed).hexdigest(), 'raw_sha': hashlib.sha256(raw).hexdigest(), 'compressed_bytes': len(compressed), 'raw_bytes': len(raw)},
          'identity': {'run_id': receipt['run_id'], 'driver_sha_matches_target': True, 'driver_sha': recorded, 'inputs': receipt['inputs'], 'launch': receipt['launch'], 'actual_node_launch_args': summary['launch_args'], 'runtime': summary['runtime']},
          'population': {'rows': len(rows), 'pairing': summary['pairing'], 'counts': dict(counts), 'condition_combinations_with_prediction': dict(combos), 'null_prediction_trusted_key_counts': dict(null_trusted), 'pred_points_saved_counts': dict(pred_saved), 'examples': example, 'stamp_windows': windows, 'archived_segment_label_totals': dict(segment_label_totals), 'segment_label_rule': 'exploratory median difference >=0.25 improved; <host-0.10 lower; not causal labels'},
          'actual_execution': {'detection_on': summary['detection_enabled'], 'scripted': summary['scripted_triggers'], 'gate': summary['gate'], 'summary_final_state': summary['final_state'], 'receipt_final_state': receipt['recovery_summary_headline']['final_state'], 'lifecycle_state': summary['lifecycle']['state'], 'open_at_exit': summary['quarantine_open_at_exit'], 'native_headline': {k:v for k,v in summary['native_checkpoint'].items() if k not in ('events','note','snapshot_ack_s')}, 'native_event_counts': dict(collections.Counter(e['command']+'/'+str(e['ok']) for e in events)), 'candidate_count': len(candidates), 'all_candidates_refused': all(not c['accepted'] for c in candidates), 'episode_trigger_stamps': [e['trigger_ts_ns'] for e in episode_details]},
          'limits': ['Same-frame support sensitivity to an alternative internally-derived pose is not an independent causal label of pose drift or map coverage.', 'Predicted pose basis keys/timestamps/horizon/matrix and actual reference coordinates/hash are not recorded in this diagnostic block.', 'Only predicted support pass is observed; no native correction is applied.', '544 vs 402 paired frames is a different run population; load is not independently established as its sole cause.', 'Both_pass82 vs AVAILABLE132 differs by only_pred_low47 plus null-prediction host-pass3, not by a missing NIS gate.']}
output = Path(__file__).with_name('archive_checks.json')
if output.exists():
    assert json.loads(output.read_text(encoding='utf-8'))['target'] == TARGET
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'target': TARGET, 'integrity': result['integrity'], 'counts': dict(counts), 'combos': dict(combos), 'null_trusted': dict(null_trusted), 'windows': windows, 'execution': result['actual_execution']}, ensure_ascii=False))
