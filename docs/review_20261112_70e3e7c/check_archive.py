"""Pinned v5 two-run archive readback; stdlib isolated, no archived scripts or host execution."""
import collections
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = '70e3e7cab942839e88727579787c7210012ef5f9'
BASE = 'c416a68d736c3fb9eee3bc0cfecdb23d586aba34'
PREFIX = 'docs/review_20261112_four_host/'


def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args])


def blob(path):
    return git('show',TARGET+':'+path)


def fields(ack):
    return {k:v.rstrip(',') for k,v in re.findall(r'([A-Za-z_]+)=([^\s\x1b]+)',ack)}


def ns(text):
    sec, frac = text.split('.')
    return int(sec)*10**9+int(frac.ljust(9,'0'))


changed = set(git('diff','--name-only',BASE,TARGET,'--',PREFIX).decode().splitlines())
checks = []
for line in blob(PREFIX+'SHA256SUMS').decode().splitlines():
    expected, name = line.split(maxsplit=1)
    name = str(PurePosixPath(name.removeprefix('./').lstrip('*')))
    assert '..' not in PurePosixPath(name).parts
    if PREFIX+name in changed:
        checks.append({'path':name,'ok':hashlib.sha256(blob(PREFIX+name)).hexdigest()==expected})
assert checks and all(c['ok'] for c in checks)
newsha = blob(PREFIX+'host_change_replay_suffix_ack/new_binary_sha.txt').decode().split()[0]
runs = []
for directory in ('replay_suffix_skip_20261112','two_event_v5_20261112'):
    p = PREFIX+directory+'/'
    obj = lambda f: json.loads(blob(p+f))
    summary, receipt = obj('run_summary.json'), obj('receipt.json')
    events = obj('native_checkpoint_events.json')
    details = [json.loads(line) for line in blob(p+'candidates_detail.jsonl').splitlines()]
    candidates = [json.loads(line) for line in blob(p+'candidates.jsonl').splitlines()]
    ep = summary['quarantine']['episode_detail']
    logs = blob(p+'host.log').decode(errors='replace').splitlines()
    driver = blob(p+'recovery_node_source.sha256').decode().split()[0]
    run_version = 'e39b2b8'
    run_source = git('show',run_version+':slam_recovery/ros/recovery_node.py')
    assert driver == receipt['inputs']['recovery_node_source'] == hashlib.sha256(run_source).hexdigest()
    assert receipt['inputs']['runtime_library_sha256'] == newsha
    line = next(s for s in logs if 'reprocess #1:' in s)
    m = re.search(r'(\d+) frames replayed over \[(\d+\.\d+) \.\. (\d+\.\d+)\]',line)
    attrs = fields(line)
    assert int(m[1]) == int(attrs['replayed_within_end']) + int(attrs['replayed_suffix'])
    critical = [e for e in events if e['command'] in ('reprocess','set_state','restore','resume')]
    reprocess = next(e for e in critical if e['command']=='reprocess')
    resume = next(e for e in critical if e['command']=='resume')
    assert all(e['command']!='set_state' for e in events)
    assert fields(reprocess['ack'])['replay_suffix'] == str(ep[0]['replay_suffix']) == attrs['replayed_suffix']
    pa, pb = ([float(v) for v in fields(e['ack'])['state_pos'].split(',')] for e in (reprocess,resume))
    state_difference = math.sqrt(sum((a-b)**2 for a,b in zip(pa,pb)))
    diag = summary['frame_diagnostics']
    closes = [e for e in summary['lifecycle']['events'] if e['event']=='wait_limit_closed']
    relay = [json.loads(line) for line in blob(p+'relay_frames.jsonl').splitlines()]
    frames = [r for r in relay if r.get('event')=='frame']
    shifted = {r['stamp_ns'] for r in frames if r['shifted']}
    pub = ep[0]['repair_publish']
    assert len(pub['frames'])==23 and set(pub['frames'])<=shifted
    accepted_stage = {'candidate_accepted':candidates[0]['accepted'],'committed':len(candidates[0]['committed_pose_keys']),
                      'frozen_at_ns':ep[0]['frame_freeze']['frozen_at_ns'],'published':pub['published'],
                      'bias_z_m':pub['bias_z_m'],'applied_lines':sum('[NATIVE_REPAIR] applied' in s for s in logs),
                      'received_lines':sum('[NATIVE_REPAIR] received' in s for s in logs),
                      'relay_shifted':len(shifted),'unpublished_shifted':len(shifted-set(pub['frames'])),
                      'native_writeback_skipped':ep[0].get('native_writeback_skipped'),
                      'no_set_state_events':True,'reprocess_resume_ack_xyz': [pa,pb],
                      'command_boundary_position_difference_m':state_difference}
    assert accepted_stage['applied_lines']==23 and accepted_stage['received_lines']==23
    e2 = None
    if len(ep)==2:
        restore = next(e for e in critical if e['command']=='restore')
        cpstamp = int(fields(restore['ack'])['stamp_ns'])
        e2 = {'trigger_ns':ep[1]['trigger_ts_ns'],'quarantine_start_ns':ep[1]['quarantine_start_ns'],
              'decision_ns':candidates[1]['t_decision_ns'],'candidate_frames':len(details[1]['candidate_frame_ids']),
              'accepted':candidates[1]['accepted'],'mode':candidates[1]['mode'],
              'checkpoint_stamp_ns':cpstamp,'late_after_trigger_s':(cpstamp-ep[1]['trigger_ts_ns'])*1e-9,
              'late_after_quarantine_start_s':(cpstamp-ep[1]['quarantine_start_ns'])*1e-9,
              'restore_event':restore,'paired_strictly_after_close2':sum(d['ts_ns']>closes[1]['closed_ns'] for d in diag),
              'tail_after_close2_s':(diag[-1]['ts_ns']-closes[1]['closed_ns'])*1e-9,
              'paired_between_close1_and_trigger2_strict':sum(closes[0]['closed_ns']<d['ts_ns']<ep[1]['trigger_ts_ns'] for d in diag),
              'paired_trigger2_through_last_inclusive':sum(d['ts_ns']>=ep[1]['trigger_ts_ns'] for d in diag),
              'fault_injected_at_E2':False,'complete_rollback_to_quarantine_start':False}
    runs.append({'directory':directory,'run_id':summary['run_id'],'driver_sha':driver,'driver_run_version':run_version,
                 'target_driver_sha':hashlib.sha256(blob('slam_recovery/ros/recovery_node.py')).hexdigest(),
                 'target_adds_diagnostic_identity_basis_fields_not_run_driver':True,'inputs':receipt['inputs'],
                 'launch':receipt['launch'],'runtime':summary['runtime'],'pairing':summary['pairing'],
                 'replay':{'log':line,'groups':int(m[1]),'within':int(attrs['replayed_within_end']),
                           'suffix':int(attrs['replayed_suffix']),'start_ns':ns(m[2]),'end_ns':ns(m[3]),
                           'point_accounting':next(s for s in logs if 'replay points:' in s)},
                 'E1':accepted_stage,'E2':e2,'critical_events':critical,
                 'real_deferred_application':[s for s in logs if 'deferred apply cmd=snapshot' in s],
                 'leftover_lines':[s for s in logs if '[NATIVE_REPAIR] leftover' in s],
                 'gate':summary['gate'],'frames':summary['frames'],
                 'detection_enabled':summary['detection_enabled'],'quarantine':{k:v for k,v in summary['quarantine'].items() if k!='episode_detail'},
                 'lifecycle':{'state':summary['lifecycle']['state'], 'events':[{k:v for k,v in e.items() if k!='frames_unresolved'} | ({'unresolved_count':len(e['frames_unresolved'])} if 'frames_unresolved' in e else {}) for e in summary['lifecycle']['events']]},
                 'native':{k:v for k,v in summary['native_checkpoint'].items() if k not in ('events','note','snapshot_ack_s')},
                 'native_event_counts':dict(collections.Counter(e['command']+'/'+str(e['ok']) for e in events)),
                 'termination':receipt['termination'],'last_paired_stamp_ns':diag[-1]['ts_ns']})
build = blob(PREFIX+'host_change_replay_suffix_ack/host_build_v6.log').decode().splitlines()
result = {'target':TARGET,'base':BASE,'exit':0,
          'command':'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_70e3e7c/check_archive.py',
          'scope':'Git archive/hash and execution readback; no host/bag/archived scripts or binary execution',
          'integrity':{'matched':len(checks),'total':len(checks),'checks':checks},'runs':runs,
          'v5_patch_sha':hashlib.sha256(blob(PREFIX+'host_change_replay_suffix_ack/deployed_host_v5.diff')).hexdigest(),
          'build_signals':[s for s in build if 'Built target laser_mapping' in s or 'CXXABI_' in s or 'Error ' in s or 'failed' in s]}
output=Path(__file__).with_name('archive_checks.json')
assert not output.exists()
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'target':TARGET,'integrity':{'matched':len(checks),'bad':[]},'runs':[{k:r[k] for k in ('run_id','replay','E1','E2','quarantine','native_event_counts')} for r in runs]},ensure_ascii=False))
