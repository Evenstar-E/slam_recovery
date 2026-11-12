"""Read three new archive runs at an exact Git version; no archive code execution."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'd193680aa6f3bb7945e8bf01fdd2d8932819c49c'
BASE = '64bfed115f7d2058bbfe076caf103491036560c1'
PREFIX = 'docs/review_20261112_four_host/'
INJECTION = PREFIX + 'injection_repair_20261112/freeze_ab/'

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])
def blob(path, version=TARGET):
    return git('show', version + ':' + path)

changed = set(git('diff', '--name-only', BASE, TARGET, '--', PREFIX).decode().splitlines())
checks = []
for line in blob(PREFIX + 'SHA256SUMS').decode().splitlines():
    expected, path = line.split(maxsplit=1)
    path = str(PurePosixPath(path.lstrip('*')))
    assert not path.startswith('/') and '..' not in PurePosixPath(path).parts
    if PREFIX + path in changed:
        checks.append({'path': path, 'ok': hashlib.sha256(blob(PREFIX + path)).hexdigest() == expected})
assert checks and all(row['ok'] for row in checks)
runs = []
def ns(text):
    seconds, nano = text.split('.')
    return int(seconds) * 10**9 + int(nano.ljust(9, '0'))
for name, version in [('sham', '7aef6bc'), ('terminal_stamp/repair', 'b3f4f47'), ('terminal_stamp/sham', 'b3f4f47')]:
    prefix = INJECTION + name + '/'
    summary = json.loads(blob(prefix + 'run_summary.json'))
    detail = json.loads(blob(prefix + 'candidates_detail.jsonl').splitlines()[0])
    candidate = json.loads(blob(prefix + 'candidates.jsonl').splitlines()[0])
    episode = summary['quarantine']['episode_detail'][0]
    repair = episode.get('repair_publish', {})
    events = json.loads(blob(prefix + 'native_checkpoint_events.json'))
    actions = [{k: e.get(k) for k in ('command', 'wall', 'ack_wall', 'ok', 'error', 'ack')}
               for e in events if e.get('command') in ('hold', 'reprocess', 'set_state', 'resume')]
    # First snapshot requested after hold is the newly added opening checkpoint.
    hold = next(e for e in events if e.get('command') == 'hold')
    opening = next((e for e in events if e.get('command') == 'snapshot' and e.get('wall', 0) > hold['wall']), None) if name.startswith('terminal_stamp/') else None
    host = blob(prefix + 'host.log').decode(errors='replace').splitlines()
    replay = next(line for line in host if 'reprocess #1:' in line)
    match = re.search(r'(\d+) frames replayed over \[(\d+\.\d+) \.\. (\d+\.\d+)\], repairs applied=(\d+) queued=(\d+)(.*)', replay)
    assert match, replay
    attrs = {key: int(value) for key, value in re.findall(r'(replayed|truncated|end_stamp)=(\d+)', match[6])}
    start, end = ns(match[2]), ns(match[3])
    recorded = blob(prefix + 'recovery_node_source.sha256').decode().split()[0]
    source_sha = hashlib.sha256(blob('slam_recovery/ros/recovery_node.py', version)).hexdigest()
    assert recorded == source_sha
    receipt = json.loads(blob(prefix + 'receipt.json'))
    relay = [json.loads(line) for line in blob(prefix + 'relay_frames.jsonl').splitlines()]
    window = next(row for row in relay if row.get('event') == 'window')
    frames = [row for row in relay if row.get('event') == 'frame']
    shifted = {row['stamp_ns'] for row in frames if row['shifted']}
    selected = [{'line': i, 'text': line} for i, line in enumerate(host, 1)
                if '[NATIVE_REPAIR] leftover' in line or 'reprocess #1:' in line]
    applied_lines = [line for line in host if '[NATIVE_REPAIR] applied' in line]
    diagnostics = summary.get('frame_diagnostics', [])
    runs.append({'name': name, 'run_id': summary['run_id'], 'driver_sha': recorded,
                 'run_source_version': version, 'driver_matches_version': True,
                 'driver_matches_target': recorded == hashlib.sha256(blob('slam_recovery/ros/recovery_node.py')).hexdigest(),
                 'receipt_hashes': {key: receipt.get('inputs', {}).get(key) for key in ('bag_sha256', 'host_binary_sha256', 'runtime_library_sha256')},
                 'relay': {'window': window, 'frames': len(frames), 'shifted': len(shifted), 'unshifted': len(frames) - len(shifted)},
                 'candidate': {'count': len(detail['candidate_frame_ids']), 'pose_stamps_ns': detail['candidate_frame_ts_ns'],
                               'committed': len(candidate['committed_pose_keys']), 'deferred': len(candidate['deferred_pose_keys']),
                               'accepted': candidate['accepted'], 'mode': candidate['mode'], 'after': candidate['weak_dir_info_after'],
                               'wilson': candidate['wilson_lower_bound'], 'holdout': candidate['holdout_nis']},
                 'freeze': episode.get('frame_freeze'),
                 'repair': {k: v for k, v in repair.items() if k not in ('per_frame', 'frames')},
                 'published_scan_stamps_ns': repair.get('frames', []),
                 'published_stamps_all_corrupted': set(repair.get('frames', [])) <= shifted,
                 'received_log_count': sum('[NATIVE_REPAIR] received' in line for line in host),
                 'applied_log_count': len(applied_lines), 'first_last_applied': applied_lines[:1] + applied_lines[-1:],
                 'replay': {'start_ns': start, 'end_ns': end, 'duration_ns': end - start, 'frames': int(match[1]),
                            'applied': int(match[4]), 'queued': int(match[5]), **attrs},
                 'selected_host_lines': selected, 'opening_snapshot': opening, 'actions': actions,
                 'tail': {**summary['frames'], 'last_recorded_pose_ns': diagnostics[-1].get('ts_ns') if diagnostics else None},
                 'episodes': summary['quarantine']['episodes'], 'second_and_later_events': summary['quarantine']['second_and_later_events'],
                 'lifecycle': {k: summary['lifecycle'].get(k) for k in ('state', 'unresolved_segments', 'wait_limit_ns')},
                 'lifecycle_event_names': [e.get('event') for e in summary['lifecycle'].get('events', [])],
                 'native_failures': summary['native_checkpoint'].get('failures'),
                 'detection_enabled': summary['detection_enabled'], 'termination': receipt.get('termination')})
a, b = runs[1:]
comparison = {'same_candidate_pose_stamps': a['candidate']['pose_stamps_ns'] == b['candidate']['pose_stamps_ns'],
              'same_frozen_at_ns': a['freeze']['frozen_at_ns'] == b['freeze']['frozen_at_ns'],
              'same_actual_replay_end_ns': a['replay']['end_ns'] == b['replay']['end_ns'],
              'same_payload_end_ns': a['replay'].get('end_stamp') == b['replay'].get('end_stamp'),
              'actual_end_minus_payload_ns': [r['replay']['end_ns'] - r['replay'].get('end_stamp', r['replay']['end_ns']) for r in (a, b)],
              'start_difference_ns': a['replay']['start_ns'] - b['replay']['start_ns'],
              'applied_population': [a['applied_log_count'], b['applied_log_count']],
              'truncated_counts': [a['replay'].get('truncated'), b['replay'].get('truncated')]}
build = blob(PREFIX + 'host_change_terminal_stamp/host_build_v2.log').decode(errors='replace').splitlines()
build_signals = [line for line in build if 'Built target laser_mapping' in line or 'CXXABI_1.3.15' in line or 'Error ' in line or 'failed' in line]
sha_text = blob(PREFIX + 'host_change_terminal_stamp/new_binary_sha.txt').decode()
new_library_sha = sha_text.split()[0]
comparison['runtime_library_matches_recorded_build_hash'] = [r['receipt_hashes']['runtime_library_sha256'] == new_library_sha for r in (a, b)]
payload = {'target': TARGET, 'base': BASE,
           'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_d193680/check_archive.py',
           'exit': 0, 'scope': 'Git archive hashes and recorded execution arithmetic, no host or bag execution',
           'integrity': {'matched': len(checks), 'total': len(checks), 'bad': []},
           'runs': runs, 'terminal_pair_comparison': comparison, 'new_library_sha': new_library_sha,
           'build_log_signals': build_signals}
output = Path(__file__).with_name('archive_checks.json')
if output.exists():
    assert json.loads(output.read_text(encoding='utf-8'))['target'] == TARGET
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'target': TARGET, 'integrity': payload['integrity'], 'comparison': comparison, 'build': build_signals,
                  'runs': [{k: r[k] for k in ('name', 'run_id', 'driver_matches_target', 'relay', 'replay', 'received_log_count', 'applied_log_count', 'tail', 'episodes', 'second_and_later_events', 'lifecycle_event_names', 'native_failures')} for r in runs]}, ensure_ascii=False, indent=2))
