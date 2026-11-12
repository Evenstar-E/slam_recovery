"""Isolated readback of one reference-map archive. No archived scripts or host execution."""
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[2]
TARGET='eeda1224da57fa9d380811f4009cb954615286c7'
PREFIX='docs/review_20261112_availability/reference_map_20261112/'


def blob(path):
    return subprocess.check_output(['git','-C',str(ROOT),'show',TARGET+':'+path])


def read(name):
    return blob(PREFIX+name)


checks=[]
for line in read('SHA256SUMS').decode().splitlines():
    expected,name=line.split(maxsplit=1)
    name=str(PurePosixPath(name.removeprefix('./')))
    assert '..' not in PurePosixPath(name).parts
    checks.append({'path':name,'ok':hashlib.sha256(read(name)).hexdigest()==expected})
assert len(checks)==11 and all(c['ok'] for c in checks)
receipt=json.loads(read('receipt.json'))
summary=json.loads(read('run_summary.json'))
poses=[[float(v) for v in row.split()] for row in read('lidar_poses.txt').decode().splitlines() if row.strip()]
assert all(len(row)==8 for row in poses)
positions=[row[1:4] for row in poses]
norms=[math.sqrt(sum(v*v for v in p)) for p in positions]
maxi=max(range(len(norms)),key=lambda i:norms[i])
pcd=read('all_downsampled_points.pcd')
head,body=pcd.split(b'DATA binary\n',1)
assert b'FIELDS x y z rgb' in head and b'SIZE 4 4 4 4' in head
xyz=[row[:3] for row in struct.iter_unpack('<fffI',body)]
assert len(xyz)==13493 and len(body)==len(xyz)*16
host=read('host.log').decode(errors='replace').splitlines()
pose_stamp_lo,pose_stamp_hi=poses[0][0],poses[-1][0]
diag=summary['frame_diagnostics']
assert len(diag)==summary['frames']['paired']==396
recorded=read('recovery_node_source.sha256').decode().split()[0]
assert recorded==receipt['inputs']['recovery_node_source']==hashlib.sha256(blob('slam_recovery/ros/recovery_node.py')).hexdigest()
assert hashlib.sha256(read('refmap_m2dgr.yaml')).hexdigest()==receipt['inputs']['config_m2dgr_sha256']
previous_last=1627785320909073830
result={'target':TARGET,'exit':0,
        'command':'C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_eeda122/check_archive.py',
        'scope':'Git bytes/hash, scalar trajectory and PCD geometry only; no archived scoring/host/bag execution',
        'integrity':{'matched':len(checks),'total':len(checks),'checks':checks},
        'identity':{'run_id':receipt['run_id'],'inputs':receipt['inputs'],'matches_target_driver':True,
                    'config_copy_hash_matches_receipt':True,'launch':receipt['launch'],
                    'actual_args':summary['launch_args'],'termination':receipt['termination']},
        'pose_log':{'rows':len(poses),'start_s':pose_stamp_lo,'end_s':pose_stamp_hi,
                    'duration_s':pose_stamp_hi-pose_stamp_lo,
                    'xyz_ranges':[[min(p[i] for p in positions),max(p[i] for p in positions)] for i in range(3)],
                    'norm_min_max':[min(norms),max(norms)],'positions_over_1m':sum(n>1 for n in norms),
                    'max_norm_row':{'index':maxi,'values':poses[maxi]},
                    'first_row':poses[0],'last_row':poses[-1],
                    'delta_last_vs_previous_run_last_s':previous_last*1e-9-pose_stamp_hi,
                    'claim_all_positions_under_1m':False,'pose_map_inconsistency_causal_verdict':'UNKNOWN_not_proven_by_extent'},
        'pcd':{'points':len(xyz),'file_bytes':len(pcd),'sha256':hashlib.sha256(pcd).hexdigest(),
               'xyz_ranges':[[min(p[i] for p in xyz),max(p[i] for p in xyz)] for i in range(3)],
               'raw_pcd':'NOT_READ_external_path_hash_only','full_map_quality':'UNKNOWN'},
        'run':{'frames':summary['frames'],'pairing':summary['pairing'],'runtime':summary['runtime'],
               'paired_start_ns':diag[0]['ts_ns'],'paired_end_ns':diag[-1]['ts_ns'],
               'detection_enabled':summary['detection_enabled'],
               'quarantine':{k:v for k,v in summary['quarantine'].items() if k!='episode_detail'},
               'save_lines':[line for line in host if 'point cloud data saved to:' in line],
               'host_exit_footer':host[-1],
               'host_graceful_exit_verified':False},
        'reported_scoring':{'gauge_rms_3_51m_and_302_before_after_zero':'DEVELOPER_REPORTED_no_score_or_gauge_artifact_in_target',
                            'independent_reference_result':'NOT_ACCEPTED_no_coverage_and_gauge_validated_result',
                            'pose_static_claim':'FAIL_conflicts_with_original_xyz',
                            'time_limit':'Pose log does not cover previous diagnostic tail; absolute timestamp ending near315s is not a320s bag duration.'},
        'ali_h_task_present':bool(subprocess.check_output(['git','-C',str(ROOT),'ls-tree','--name-only',TARGET,'--','docs/ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md']).strip()),
        'no_native_or_parameter_execution':True}
output=Path(__file__).with_name('archive_checks.json')
assert not output.exists()
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('identity','integrity')},ensure_ascii=False))
