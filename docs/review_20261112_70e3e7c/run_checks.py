"""Minimal actual-target orchestration controls; simulate gate/ACK, never native execution."""
import hashlib
import importlib.abc
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = '70e3e7cab942839e88727579787c7210012ef5f9'


def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args])


class GitModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self):
        self.paths=set(git('ls-tree','-r','--name-only',TARGET,'--','slam_recovery').decode().splitlines())
        self.loaded={}
    def find_spec(self,fullname,path=None,target=None):
        if not (fullname=='slam_recovery' or fullname.startswith('slam_recovery.')):
            return None
        stem=fullname.replace('.','/')
        source=stem+'/__init__.py' if stem+'/__init__.py' in self.paths else stem+'.py'
        if source not in self.paths:
            return None
        spec=importlib.util.spec_from_loader(fullname,self,is_package=source.endswith('/__init__.py'))
        spec.loader_state=source
        return spec
    def create_module(self,spec):
        return None
    def exec_module(self,module):
        source=module.__spec__.loader_state
        raw=git('show',TARGET+':'+source)
        self.loaded[source]=hashlib.sha256(raw).hexdigest()
        module.__file__=str(ROOT/source)
        exec(compile(raw,TARGET+':'+source,'exec'),module.__dict__)


assert not git('diff','HEAD','--','slam_recovery').strip()
finder=GitModules()
sys.meta_path.insert(0,finder)
from slam_recovery.core import RecoveryState
from slam_recovery.ros.recovery_node import NativeClosedLoop, Episode, LiveNis
from slam_recovery.ros.availability_log import AvailabilityRecorder
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode


class CP:
    def __init__(self,ack):
        self.ack=ack
        self.calls=[]
        self._last_snapshot_wall=0
    def reprocess(self,end_stamp_ns=None):
        self.calls.append('reprocess')
        return {'command':'reprocess'}
    def collect(self,timeout_s=None):
        self.calls.append('collect')
        return self.ack
    def set_state(self,pose):
        self.calls.append('set_state')
        return {'command':'set_state'}


def scenario(ack):
    mgr=SimpleNamespace(trusted_poses={},trusted_version=0,
                        active_quarantine=SimpleNamespace(t_end_ns=12_000_000_000),
                        confirmation_margin_ns=2_000_000_000,state=RecoveryState.QUARANTINED)
    report=SimpleNamespace(accepted=True,mode='MODE2',reason='synthetic full acceptance',
                           committed_pose_keys=[1,2],deferred_pose_keys=[],partial_commit=False,
                           evidence_status='PASSED')
    node=SimpleNamespace(tx_mgr=mgr,sigma_meas_m=.12,_kf_timestamps={},last_paired_evidence={},
                         evaluate_and_commit_candidate=lambda *a,**k: report)
    loop=NativeClosedLoop(node,'target-control')
    loop.cp=CP(ack)
    loop._repair_gate=lambda *a,**k:(True,None)
    ep=Episode(0,10_000_000_000,np.eye(4),12_000_000_000)
    ep.frames=[(1,10_000_000_000,np.eye(4)),(2,11_000_000_000,np.eye(4))]
    loop._open=ep
    loop.episodes=[ep]
    row=loop.decide(12_000_000_000,'review')
    return {'accepted_record':row['accepted'],'calls':loop.cp.calls,
            'parsed_suffix':ep.meta['replay_suffix'],
            'skipped':ep.meta.get('native_writeback_skipped'),
            'writeback_present':'native_writeback' in ep.meta}


positive=scenario({'command':'reprocess','ok':True,'ack':'OK reprocess replay_suffix=373'})
assert positive['calls']==['reprocess','collect'] and positive['skipped']
missing=scenario(None)
assert missing['parsed_suffix'] is None and missing['calls']==['reprocess','collect','set_state']
failed=scenario({'command':'reprocess','ok':False,'error':'ack_timeout'})
assert failed['parsed_suffix'] is None and failed['writeback_present']
zero=scenario({'command':'reprocess','ok':True,'ack':'OK reprocess replay_suffix=0'})
assert zero['writeback_present']
node=OnlineRecoveryTransactionNode()
nis=LiveNis(node)
nis.support_reference(123)
identity=nis.reference_identity()
assert identity['cache_key']==[0,0] and identity['refresh_ns']==123 and identity['points']==0
assert identity['sha256']==hashlib.sha256(b'').hexdigest()
T=np.eye(4)
fake=SimpleNamespace(node=SimpleNamespace(tx_mgr=SimpleNamespace(trusted_poses={1:T}),_kf_timestamps={1:100}))
pose,basis=NativeClosedLoop._predicted_pose(fake,500)
assert basis['mode']=='last_pose' and basis['base_stamps_ns']==[100]
assert basis['predicted_T']==pose.reshape(-1).tolist()
with tempfile.TemporaryDirectory(prefix='boundary-detail-review-') as directory:
    path=Path(directory,'boundary.jsonl')
    recorder=AvailabilityRecorder(str(path))
    recorder.record({'status':'AVAILABLE','boundary':True,'support':{'points':[{'row':i} for i in range(200)]}})
    recorder.close()
    boundary=json.loads(path.read_text())
    assert len(boundary['support']['points'])==200
payload={'target':TARGET,'exit':0,
         'command':'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_70e3e7c/run_checks.py',
         'source_loading':'All slam_recovery modules from target Git bytes in memory',
         'loaded_sources_sha256':finder.loaded,
         'positive_nonzero_suffix':{'status':'PASS_LOCAL',**positive},
         'missing_ack_writeback':{'status':'FAIL_REPRODUCED_LOCAL',**missing},
         'failed_ack_writeback':{'status':'FAIL_REPRODUCED_LOCAL',**failed},
         'explicit_zero_suffix':{'status':'DECLARED_LEGACY_BRANCH',**zero},
         'diagnostic_metadata':{'status':'PASS_LOCAL','reference_identity_empty':identity,
                                'last_pose_prediction_basis':basis,'boundary_support_points_saved':200,
                                'scope':'Source control only; no new diagnostic runtime archive'},
         'new_repair_sync_tests':'NOT_RUN_pytest_helper_dependency_no_install_or_shim',
         'no_ros_host_bag_or_parameter_execution':True}
output=Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in payload.items() if k!='loaded_sources_sha256'},ensure_ascii=False))
