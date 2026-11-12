"""Complete the archive stamp/interval comparison; isolated read-only Git blobs."""
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = '64bfed115f7d2058bbfe076caf103491036560c1'
BASE = '2f1f59bfdab1203a7ef6eb3eb2e72eb345a7b8cb'
PREFIX = 'docs/review_20261112_four_host/'
INJECTION = PREFIX + 'injection_repair_20261112/'
NAMES = ['decoupled_bias/success_batched', 'decoupled_bias/control_dryrun', 'freeze_ab/repair', 'freeze_ab/control']

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
    full = PREFIX + path
    if full in changed:
        checks.append({'path': path, 'ok': hashlib.sha256(blob(full)).hexdigest() == expected})
assert checks and all(row['ok'] for row in checks)
runs = []
populations = []
for name, version in zip(NAMES, ['8790452', 'e6f7430', '7b02fa7', '7b02fa7']):
    prefix = INJECTION + name + '/'
    summary = json.loads(blob(prefix + 'run_summary.json'))
    detail = json.loads(blob(prefix + 'candidates_detail.jsonl').splitlines()[0])
    candidate = json.loads(blob(prefix + 'candidates.jsonl').splitlines()[0])
    episode = summary['quarantine']['episode_detail'][0]
    repair = episode.get('repair_publish', {})
    population = detail['candidate_frame_ts_ns']
    populations.append(population)
    events = json.loads(blob(prefix + 'native_checkpoint_events.json'))
    actions = [{k: event.get(k) for k in ('command', 'wall', 'ack_wall', 'ok', 'ack')}
               for event in events if event.get('command') in ('hold', 'reprocess', 'set_state', 'resume')]
    host = blob(prefix + 'host.log').decode(errors='replace').splitlines()
    replay_line = next(line for line in host if 'reprocess #1:' in line)
    match = re.search(r'(\d+) frames replayed over \[(\d+\.\d+) \.\. (\d+\.\d+)\], repairs applied=(\d+) queued=(\d+), map now (\d+) voxels/(\d+) points', replay_line)
    assert match, replay_line
    def ns(value):
        seconds, nanos = value.split('.')
        return int(seconds) * 10**9 + int(nanos.ljust(9, '0'))
    start, end = ns(match[2]), ns(match[3])
    replay = {'frames': int(match[1]), 'start_ns': start, 'end_ns': end, 'duration_ns': end - start,
              'applied': int(match[4]), 'queued': int(match[5]), 'voxels': int(match[6]), 'points': int(match[7]),
              'log': replay_line, 'host_applied_log_count': sum('[NATIVE_REPAIR] applied' in line for line in host)}
    received = [line for line in host if '[NATIVE_REPAIR] received' in line]
    receipt = json.loads(blob(prefix + 'receipt.json'))
    recorded = blob(prefix + 'recovery_node_source.sha256').decode().split()[0]
    report_sha = hashlib.sha256(blob('slam_recovery/ros/recovery_node.py', version)).hexdigest()
    target_sha = hashlib.sha256(blob('slam_recovery/ros/recovery_node.py')).hexdigest()
    assert recorded == report_sha
    rows = [json.loads(line) for line in blob(prefix + 'relay_frames.jsonl').splitlines()]
    frames = [row for row in rows if row.get('event') == 'frame']
    shifted = {row['stamp_ns'] for row in frames if row['shifted']}
    published = repair.get('frames', [])
    frame_diag = summary['frame_diagnostics']
    tail = {key: summary['frames'].get(key) for key in ('paired', 'consumed_after_first_decision', 'first_decision_ts_ns')}
    tail['last_recorded_pose_stamp_ns'] = frame_diag[-1].get('ts_ns') if frame_diag else None
    runs.append({'name': name, 'run_id': summary['run_id'], 'driver_sha': recorded, 'source_version': version,
                 'driver_matches_version': True, 'driver_matches_target': recorded == target_sha,
                 'input_hashes': {k: receipt.get(k) for k in ('bag_sha256', 'host_binary_sha256', 'runtime_library_sha256')},
                 'candidate': {'accepted': candidate['accepted'], 'mode': candidate['mode'],
                               'count': len(detail['candidate_frame_ids']),
                               'pose_stamps_ns': population,
                               'committed': len(candidate['committed_pose_keys']), 'deferred': len(candidate['deferred_pose_keys']),
                               'weak_before': candidate['weak_dir_info_before'], 'weak_after': candidate['weak_dir_info_after'],
                               'wilson': candidate['wilson_lower_bound'], 'holdout': candidate['holdout_nis']},
                 'freeze': episode.get('frame_freeze'),
                 'repair': {k: v for k, v in repair.items() if k not in ('per_frame', 'frames')},
                 'relay': {'frames': len(frames), 'shifted': len(shifted), 'unshifted': len(frames) - len(shifted)},
                 'published_scan_stamps_ns': published, 'all_published_in_corrupt_set': set(published) <= shifted,
                 'host_received_log_count': len(received), 'replay': replay, 'actions': actions,
                 'tail': tail, 'episodes': summary['quarantine']['episodes'],
                 'second_and_later_events': summary['quarantine']['second_and_later_events'],
                 'lifecycle': summary['lifecycle'], 'native_failures': summary['native_checkpoint'].get('failures'),
                 'detection_enabled': summary['detection_enabled'], 'termination': receipt.get('termination')})
repair_run, control_run = runs[2:]
comparison = {'same_frozen_pose_stamps': populations[2] == populations[3],
              'same_frozen_count': len(populations[2]) == len(populations[3]),
              'same_candidate_freeze_ns': repair_run['freeze']['frozen_at_ns'] == control_run['freeze']['frozen_at_ns'],
              'replay_start_difference_ns': repair_run['replay']['start_ns'] - control_run['replay']['start_ns'],
              'replay_end_difference_ns': repair_run['replay']['end_ns'] - control_run['replay']['end_ns'],
              'replay_duration_difference_ns': repair_run['replay']['duration_ns'] - control_run['replay']['duration_ns'],
              'replay_frame_count_difference': repair_run['replay']['frames'] - control_run['replay']['frames']}
positions = []
for run in (repair_run, control_run):
    ack = next(a['ack'] for a in run['actions'] if a['command'] == 'set_state')
    positions.append([float(x) for x in re.search(r'state_pos=([-\d.,]+)', ack)[1].split(',')])
comparison['set_state_ack_pos_difference_m'] = math.dist(*positions)
comparison['scope'] = 'Same pose stamp population, not identical host poses; map comparison has different native replay support. Set_state ack is commanded candidate state, not independent native re-estimation quality.'
payload = {'target': TARGET, 'base': BASE,
           'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_64bfed1/check_archive.py',
           'exit': 0, 'scope': 'Git byte hashing and structured archive arithmetic only; no remote bag/binary/host execution',
           'integrity': {'matched': len(checks), 'total': len(checks), 'bad': []},
           'runs': runs, 'frozen_pair_comparison': comparison}
output = Path(__file__).with_name('archive_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'target': TARGET, 'integrity': payload['integrity'], 'comparison': comparison,
                  'runs': [{k: r[k] for k in ('name', 'run_id', 'source_version', 'driver_matches_version', 'driver_matches_target', 'tail', 'episodes', 'second_and_later_events', 'native_failures')} for r in runs]}, ensure_ascii=False, indent=2))
