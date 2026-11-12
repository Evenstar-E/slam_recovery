"""Read exact Git archive bytes using isolated Python; never execute archive code."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = '18baefd89e70a65b1a493b0c1e532558b6bff6e0'
PREFIX = 'docs/review_20261112_four_host/'
RUN = PREFIX + 'injection_repair_20261112/'

def blob(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', TARGET + ':' + path])

checks = []
for line in blob(PREFIX + 'SHA256SUMS').decode().splitlines():
    expected, path = line.split(maxsplit=1)
    path = str(PurePosixPath(path.lstrip('*')))
    assert not path.startswith('/') and '..' not in PurePosixPath(path).parts
    if path == 'README.md' or path.startswith('injection_repair_20261112/'):
        checks.append({'path': path, 'ok': hashlib.sha256(blob(PREFIX + path)).hexdigest() == expected})
assert len(checks) == 17 and all(row['ok'] for row in checks)
relay = [json.loads(line) for line in blob(RUN + 'relay_frames.jsonl').splitlines()]
frames = [row for row in relay if row.get('event') == 'frame']
shifted = {row['stamp_ns'] for row in frames if row['shifted']}
summary = json.loads(blob(RUN + 'run_summary.json'))
episode = summary['quarantine']['episode_detail'][0]
repair = episode['repair_publish']
assert len(frames) == 598 and len(shifted) == 60
assert len(repair['frames']) == 25 and set(repair['frames']) <= shifted
window = next(row for row in relay if row.get('event') != 'frame')
trigger = episode['trigger_ts_ns']
icp = json.loads(blob(RUN + 'icp_detail.jsonl').splitlines()[0])
candidate = json.loads(blob(RUN + 'candidates.jsonl').splitlines()[0])
host = blob(RUN + 'host.log').decode(errors='replace').splitlines()
selected = [{'line': i, 'text': line} for i, line in enumerate(host, 1)
            if 'reprocess #1:' in line or 'leftover' in line or 'restore #1:' in line]
receipt = json.loads(blob(RUN + 'receipt.json'))
recorded = blob(RUN + 'recovery_node_source.sha256').decode().split()[0]
source_match = recorded == hashlib.sha256(blob('slam_recovery/ros/recovery_node.py')).hexdigest()
assert source_match
payload = {'target': TARGET, 'run_id': summary['run_id'],
           'scope': 'Isolated read-only Git archive parsing; no bag, binary, ROS or archived script execution',
           'command': 'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_18baefd/check_archive.py',
           'exit': 0, 'integrity': {'matched': 17, 'total': 17, 'bad': []},
           'relay': {'record_lines': len(relay), 'frames': len(frames), 'shifted': len(shifted),
                     'unshifted': len(frames) - len(shifted), 'window': window,
                     'actual_trigger_minus_start_s': (trigger - window['start_ns']) / 1e9,
                     'all_repair_stamps_in_shifted_set': True},
           'gate': {'accepted': candidate['accepted'], 'mode': candidate['mode'],
                    'committed': len(candidate['committed_pose_keys']),
                    'deferred': len(candidate['deferred_pose_keys'])},
           'repair': repair, 'icp': icp, 'native_selected_log': selected,
           'frames': summary['frames'],
           'quarantine': {k: v for k, v in summary['quarantine'].items() if k != 'episode_detail'},
           'scripted_triggers': summary.get('scripted_triggers'),
           'native_checkpoint': summary.get('native_checkpoint'),
           'receipt_status': receipt.get('status'), 'termination': receipt.get('termination'),
           'driver_recorded_sha_matches_target': source_match}
output = Path(__file__).with_name('archive_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(payload, ensure_ascii=False, indent=2))
