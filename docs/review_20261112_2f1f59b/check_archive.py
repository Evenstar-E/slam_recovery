"""Isolated readback of two new runs; do not execute runners or read remote bags."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = '2f1f59bfdab1203a7ef6eb3eb2e72eb345a7b8cb'
PREFIX = 'docs/review_20261112_four_host/'
INJECTION = PREFIX + 'injection_repair_20261112/'

def blob(path, version=TARGET):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', version + ':' + path])

checks = []
for line in blob(PREFIX + 'SHA256SUMS').decode().splitlines():
    expected, path = line.split(maxsplit=1)
    path = str(PurePosixPath(path.lstrip('*')))
    assert not path.startswith('/') and '..' not in PurePosixPath(path).parts
    if '/decoupled_bias/' in path or '/incumbent_init_refused/' in path or path in ('README.md', 'injection_repair_20261112/REPORT.md'):
        checks.append({'path': path, 'ok': hashlib.sha256(blob(PREFIX + path)).hexdigest() == expected})
assert checks and all(row['ok'] for row in checks)
runs = []
for name, version in [('incumbent_init_refused', 'e472410'), ('decoupled_bias', 'bfe2939')]:
    prefix = INJECTION + name + '/'
    summary = json.loads(blob(prefix + 'run_summary.json'))
    receipt = json.loads(blob(prefix + 'receipt.json'))
    relay = [json.loads(line) for line in blob(prefix + 'relay_frames.jsonl').splitlines()]
    frames = [row for row in relay if row.get('event') == 'frame']
    shifted = {row['stamp_ns'] for row in frames if row['shifted']}
    candidate = json.loads(blob(prefix + 'candidates.jsonl').splitlines()[0])
    icp = json.loads(blob(prefix + 'icp_detail.jsonl').splitlines()[0])
    episode = summary['quarantine']['episode_detail'][0]
    repair = episode.get('repair_publish')
    events = json.loads(blob(prefix + 'native_checkpoint_events.json'))
    lifecycle = json.loads(blob(prefix + 'lifecycle_events.json'))
    host = blob(prefix + 'host.log').decode(errors='replace').splitlines()
    received = [{'line': i, 'text': line} for i, line in enumerate(host, 1) if '[NATIVE_REPAIR] received' in line]
    applications = [{'line': i, 'text': line} for i, line in enumerate(host, 1) if '[NATIVE_REPAIR] applied' in line]
    replay = [{'line': i, 'text': line} for i, line in enumerate(host, 1) if 'reprocess #' in line]
    selected_actions = [{k: e.get(k) for k in ('command', 'wall', 'ack_wall', 'ok', 'error', 'ack')}
                        for e in events
                        if e.get('command') not in ('snapshot', 'status')]
    statuses = [e for e in events if e.get('command') == 'status']
    snapshots = [e for e in events if e.get('command') == 'snapshot']
    recorded = blob(prefix + 'recovery_node_source.sha256').decode().split()[0]
    version_sha = hashlib.sha256(blob('slam_recovery/ros/recovery_node.py', version)).hexdigest()
    target_sha = hashlib.sha256(blob('slam_recovery/ros/recovery_node.py')).hexdigest()
    repair_result = repair
    if repair:
        per_frame = repair.get('per_frame', [])
        biases = [f['bias_z_m'] for f in per_frame]
        repair_result = {k: v for k, v in repair.items() if k not in ('frames', 'per_frame')}
        repair_result.update({'per_frame_count': len(per_frame),
                              'min_valid_points': min(f['valid_points'] for f in per_frame),
                              'bias_median_recomputed': statistics.median(biases),
                              'bias_range': [min(biases), max(biases)],
                              'all_published_stamps_in_shifted_set': set(repair['frames']) <= shifted})
    runs.append({'name': name, 'run_id': summary['run_id'], 'run_source_version': version,
                 'recorded_driver_sha': recorded, 'driver_matches_reported_version': recorded == version_sha,
                 'driver_matches_target': recorded == target_sha,
                 'relay': {'record_lines': len(relay), 'frames': len(frames), 'shifted': len(shifted), 'unshifted': len(frames) - len(shifted)},
                 'candidate': candidate, 'icp': icp, 'repair': repair_result,
                 'frames': summary['frames'],
                 'quarantine': {k: v for k, v in summary['quarantine'].items() if k != 'episode_detail'},
                 'episode_native_skipped': episode.get('native_checkpoint_skipped'),
                 'native_counts': {k: summary.get('native_checkpoint', {}).get(k) for k in ('restores', 'reprocesses', 'resumes', 'failures')},
                 'native_actions': selected_actions,
                 'status_ack_last': statuses[-1].get('ack') if statuses else None,
                 'snapshot_ack_last': snapshots[-1].get('ack') if snapshots else None,
                 'host_received_count': len(received), 'host_received_first_last': received[:1] + received[-1:] if received else [],
                 'host_applied_count': len(applications), 'host_reprocess_lines': replay,
                 'lifecycle': lifecycle, 'receipt': receipt})
    assert recorded == version_sha
patch = blob('docs/review_20261110_native_checkpoint/deployed_host.diff').decode().splitlines()
queue = [{'line': i, 'text': line} for i, line in enumerate(patch, 1)
         if 'nh.subscribe' in line and 'repaired_scan' in line]
payload = {'target': TARGET, 'base': '18baefd89e70a65b1a493b0c1e532558b6bff6e0',
           'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_2f1f59b/check_archive.py',
           'exit': 0, 'scope': 'Read-only Git archives/source hashes; no native/bag execution or causal queue diagnosis',
           'integrity': {'matched': sum(c['ok'] for c in checks), 'total': len(checks), 'bad': []},
           'runs': runs, 'archived_host_subscription': queue}
output = Path(__file__).with_name('archive_checks.json')
if output.exists():
    assert json.loads(output.read_text(encoding='utf-8'))['target'] == TARGET
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in payload.items() if k != 'runs'}, ensure_ascii=False))
for r in runs:
    print(json.dumps({k: v for k, v in r.items() if k not in ('lifecycle', 'receipt')}, ensure_ascii=False, indent=2))
