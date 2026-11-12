"""Minimal new independent-reference controls, all package imports target-bound; no ROS/bag."""
import hashlib
import importlib.abc
import importlib.util
import importlib.util as util
import json
from pathlib import Path
import subprocess
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
TARGET='26ba3a3f907c4ff6f29a32feb8e3540a7bd31de8'


def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args])


class GitModules(importlib.abc.MetaPathFinder,importlib.abc.Loader):
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
from slam_recovery.tests import test_independent_reference as tests
from slam_recovery.validation.independent_reference import score_rows,summarise
suite=unittest.TestSuite()
for cls in (tests.TestReadPcd,tests.TestScore,tests.TestLoadRows):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
has_scipy=util.find_spec('scipy') is not None
if has_scipy:
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(tests.TestAlignment))
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
# The exact same placed scan passes after only the reference changes. No pose change is involved.
body=[[0.,0.,0.],[.1,0.,0.],[.2,0.,0.]]
row={'kf_id':1,'T_wb':np.eye(4).reshape(-1).tolist(),'status':'UNAVAILABLE',
     'support':{'points':[{'body':b} for b in body],'supported_fraction':0.,'pass':False}}
far=score_rows([row],np.array([[100.,100.,100.]]))[0]
near=score_rows([row],np.asarray(body))[0]
assert not far['independent_pass'] and near['independent_pass']
reading=summarise([near])['reading']
# Realistic shape: available samples retain the first 20 of 200, not a full population.
full_body=np.zeros((200,3)); full_body[20:,0]=10
trimmed={'kf_id':2,'T_wb':np.eye(4).reshape(-1).tolist(),'status':'AVAILABLE',
         'support':{'points':[{'body':b.tolist()} for b in full_body[:20]],
                    'points_total':200,'supported_fraction':.8,'pass':True}}
scored=score_rows([trimmed],np.zeros((1,3)))[0]
full_fraction=float(np.mean(np.linalg.norm(full_body,axis=1)<=1))
assert scored['samples_trimmed'] and scored['independent_fraction']==1 and full_fraction==.1
population=summarise([scored])
assert population['both_pass']==1 and population['trimmed_frames']==1
payload={'target':TARGET,'exit':0,
         'command':'C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_26ba3a3/run_checks.py',
         'source_loading':'All slam_recovery modules from exact Git bytes',
         'loaded_sources_sha256':finder.loaded,'selected_tests':result.testsRun,
         'scipy_alignment_test':'PASS_LOCAL' if has_scipy else 'NOT_RUN_scipy_missing_no_install',
         'same_pose_reference_only_control':{'status':'PASS_FACT_REJECT_CAUSAL_READING',
              'pose_changed':False,'old_reference_fraction':far['independent_fraction'],
              'new_reference_fraction':near['independent_fraction'],'producer_reading':reading,
              'conclusion':'Reference replacement alone explains the flip; this is not evidence that the pose is wrong.'},
         'trimmed_population_control':{'status':'FAIL_REPRODUCED_IF_USED_AS_FULL_POPULATION',
              'saved_sample_fraction':scored['independent_fraction'],'actual_full_200_fraction':full_fraction,
              'summary':population,'conclusion':'Trimming is flagged, but the main joint count still includes it as a full frame pass.'},
         'independent_map_runtime_or_geometry_result':'NOT_EXECUTED_no_new_run_or_PCD_in_target',
         'no_native_host_bag_or_parameter_execution':True}
output=Path(__file__).with_name('local_checks.json')
assert not output.exists()
output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in payload.items() if k!='loaded_sources_sha256'},ensure_ascii=False))
