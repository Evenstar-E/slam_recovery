"""Read exact Git archive bytes with isolated stdlib; no native or archived-code execution."""
import collections
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = 'c416a68d736c3fb9eee3bc0cfecdb23d586aba34'
BASE = '4740d94a583886afc04b361aee3c6403d5072ecf'
PREFIX = 'docs/review_20261112_four_host/'
RUN = PREFIX + 'suffix_replay_20261112/'
HOST = PREFIX + 'host_change_suffix_replay/'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def blob(path):
    return git('show', TARGET + ':' + path)


def obj(name):
    return json.loads(blob(RUN + name))


def fields(text):
    return {k:v.rstrip(',') for k,v in re.findall(r'([A-Za-z_]+)=([^\s\x1b]+)', text)}


changed = set(git('diff', '--name-only', BASE, TARGET, '--', PREFIX).decode().splitlines())
checks = []
for line in blob(PREFIX + 'SHA256SUMS').decode().splitlines():
    expected, name = line.split(maxsplit=1)
    name = str(PurePosixPath(name.removeprefix('./').lstrip('*')))
    assert '..' not in PurePosixPath(name).parts
    if PREFIX + name in changed:
        checks.append({'path': name, 'ok': hashlib.sha256(blob(PREFIX + name)).hexdigest() == expected})
assert checks and all(c['ok'] for c in checks)
s = obj('run_summary.json')
receipt = obj('receipt.json')
detail = json.loads(blob(RUN + 'candidates_detail.jsonl').splitlines()[0])
candidate = json.loads(blob(RUN + 'candidates.jsonl').splitlines()[0])
events = obj('native_checkpoint_events.json')
host = blob(RUN + 'host.log').decode(errors='replace').splitlines()
replay = next(line for line in host if 'reprocess #1:' in line)
m = re.search(r'(\d+) frames replayed over \[(\d+\.\d+) \.\. (\d+\.\d+)\]', replay)
assert m
attrs = fields(replay)
assert int(m[1]) == int(attrs['replayed_within_end']) + int(attrs['replayed_suffix']) == 572
assert int(attrs['replayed_within_end']) == 124 and int(attrs['replayed_suffix']) == 448
commands = {name: next(e for e in events if e['command'] == name) for name in ('reprocess','set_state','resume')}
states = {name:fields(e['ack']) for name,e in commands.items()}
position = lambda a:[float(v) for v in a['state_pos'].split(',')]
jump = math.sqrt(sum((a-b)**2 for a,b in zip(position(states['reprocess']), position(states['set_state']))))
tail_key = detail['candidate_frame_ids'][-1]
tail = detail['repaired_poses'][str(tail_key)]
assert all(abs(tail[i]-position(states['set_state'])[j]) < 1e-6 for j,i in enumerate((3,7,11)))
assert states['reprocess']['live_voxels'] == states['set_state']['live_voxels']
assert states['reprocess']['live_points'] == states['set_state']['live_points']
episode = s['quarantine']['episode_detail'][0]
pub = episode['repair_publish']
relay = [json.loads(line) for line in blob(RUN+'relay_frames.jsonl').splitlines()]
frame_rows = [r for r in relay if r.get('event') == 'frame']
shifted = {r['stamp_ns'] for r in frame_rows if r['shifted']}
assert set(pub['frames']) <= shifted and len(pub['frames']) == 23
recorded_driver = blob(RUN+'recovery_node_source.sha256').decode().split()[0]
assert recorded_driver == receipt['inputs']['recovery_node_source'] == hashlib.sha256(blob('slam_recovery/ros/recovery_node.py')).hexdigest()
build_sha = blob(HOST+'new_binary_sha.txt').decode().split()[0]
assert build_sha == receipt['inputs']['runtime_library_sha256']
patch = blob(HOST+'deployed_host_v4.diff')
body = patch.decode().split('+bool LIVMapper::reprocessCheckpoint',1)[1].split('+std::string LIVMapper::checkpointStatus',1)[0]
assert 'if (apply_repairs && within_end) applyRepairedScan' in body
assert '++replayed_within; else ++replayed_suffix;' in body
assert '    stateEstimationAndMapping();' in body and '    processImu();' in body
assert '++truncated;' not in body
build = blob(HOST+'host_build_v5.log').decode().splitlines()
result = {'target':TARGET, 'base':BASE,
          'command':'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_c416a68/check_archive.py',
          'exit':0, 'scope':'Git archive/source-bound arithmetic only; no host, bag, binary or archived script execution',
          'integrity':{'matched':len(checks),'total':len(checks),'checks':checks},
          'identity':{'run_id':s['run_id'],'driver_sha':recorded_driver,'matches_target_driver':True,
                      'runtime_library_sha':build_sha,'matches_declared_build_sha':True,'inputs':receipt['inputs'],
                      'launch':receipt['launch'],'actual_node_args':s['launch_args'],
                      'v4_patch_sha':hashlib.sha256(patch).hexdigest()},
          'replay':{'log':replay,'groups':int(m[1]),'start_s':m[2],'end_s':m[3],
                    'within_end':int(attrs['replayed_within_end']),'suffix':int(attrs['replayed_suffix']),
                    'end_stamp_ns':int(attrs['end_stamp']),
                    'point_accounting_log':next(line for line in host if 'replay points:' in line),
                    'full_group_time_list_or_complete_state_equivalence':'NOT_VERIFIED_not_archived',
                    'source_loops_all_captured_groups_through_native_imu_mapping':True},
          'repair':{'published':pub['published'],'received':states['reprocess']['repair_received'],
                    'applied':states['reprocess']['repair_applied'],'dropped':states['reprocess']['repair_dropped'],
                    'host_received_lines':sum('[NATIVE_REPAIR] received' in line for line in host),
                    'host_applied_lines':sum('[NATIVE_REPAIR] applied' in line for line in host),
                    'leftover_lines':[line for line in host if '[NATIVE_REPAIR] leftover' in line],
                    'bias_z_m':pub['bias_z_m'],'actual_shift_z_m':pub['repair_shift_z_m'],
                    'relay_frames':len(frame_rows),'relay_shifted':len(shifted),'published_stamps_all_shifted':True,
                    'shifted_stamps_not_published':len(shifted-set(pub['frames'])),
                    'shifted_stamps_after_last_published':sum(ts>max(pub['frames']) for ts in shifted),
                    'full_injected_window_repaired':'NOT_VERIFIED_23_clouds_not_all_shifted_frames'},
          'boundary_conflict':{'commands':commands,'ack_fields':states,
                               'candidate_tail_stamp_ns':detail['candidate_frame_ts_ns'][-1],
                               'candidate_tail_key':tail_key,'candidate_tail_xyz':[tail[i] for i in (3,7,11)],
                               'replay_end_minus_candidate_tail_s':float(m[3])-detail['candidate_frame_ts_ns'][-1]*1e-9,
                               'reprocess_to_set_state_displacement_m':jump,
                               'set_state_matches_candidate_tail_not_replay_state':True,'map_counts_unchanged_at_set_state':True,
                               'scope':'ACK states at separate command boundaries; not instantaneous jump/trajectory-quality estimate'},
          'lifecycle':{'frames':s['frames'],'quarantine':{k:v for k,v in s['quarantine'].items() if k!='episode_detail'},
                       'gate':s['gate'],'final_state':s['final_state'],'lifecycle_state':s['lifecycle']['state'],
                       'detection_enabled':s['detection_enabled'],'runtime':s['runtime'],
                       'native':{k:v for k,v in s['native_checkpoint'].items() if k not in ('events','note','snapshot_ack_s')},
                       'native_event_counts':dict(collections.Counter(e['command']+'/'+str(e['ok']) for e in events)),
                       'lifecycle_events':[{k:e.get(k) for k in ('event','from_state','trusted_version')} for e in s['lifecycle']['events']]},
          'build_signals':[line for line in build if 'Built target laser_mapping' in line or 'CXXABI_' in line or 'Error ' in line or 'failed' in line]}
output = Path(__file__).with_name('archive_checks.json')
assert not output.exists()
output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
print(json.dumps({'target':TARGET,'integrity':{'matched':len(checks),'bad':[]},'replay':result['replay'],
                  'repair':result['repair'],'boundary':{k:v for k,v in result['boundary_conflict'].items() if k not in ('commands','ack_fields')},
                  'lifecycle':result['lifecycle']},ensure_ascii=False))
