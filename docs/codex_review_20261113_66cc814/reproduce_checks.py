"""Bounded independent review of pinned sources and archived data. No ROS/build/run."""
import ast
import argparse
import bisect
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional

import numpy as np

# Publication adapter: materialize only pinned review inputs into a NEW output directory.
# Requires the listed Git objects (fetch the two experiment branches first if needed).
# No native commands, automatic installs, source edits, or scientific threshold changes.
args_parser = argparse.ArgumentParser(description=__doc__)
args_parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
args_parser.add_argument('--output', type=Path, required=True, help='New evidence directory; existing paths are refused')
args = args_parser.parse_args()
REPO = args.repo.resolve()
ROOT = args.output.resolve()
ROOT.mkdir(parents=True, exist_ok=False)
SRC = ROOT / 'source/docs/ali_h_v1_research'
EXP = ROOT / 'experimental/docs/review_20261112_four_host'
OLD = ROOT / 'old_t2'
OUT = ROOT / 'checks.json'
input_manifest = json.loads(Path(__file__).with_name('SOURCES.json').read_text(encoding='utf-8'))
for item in input_manifest['inputs']:
    blob = subprocess.check_output(['git', 'show', item['commit'] + ':' + item['path']], cwd=REPO)
    assert hashlib.sha256(blob).hexdigest() == item['sha256'], item['path']
    target = ROOT / item['destination']
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)

def digest(b):
    return hashlib.sha256(b).hexdigest()

def functions(path, names):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in body} == set(names)
    ns = dict(np=np, math=math, Any=Any, Dict=Dict, List=List, Optional=Optional,
              defaultdict=defaultdict, Counter=Counter, bisect=bisect)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), 'exec'), ns)
    return ns

f = functions(SRC/'t2_run.py', ['so3_exp', 'so3_left_jacobian_inv', 'exact_e',
                                'quat_to_rot', 'parse_trace', 'build_join', 'i_evidence'])
up = functions(SRC/'t2_join_upgrade.py', ['parse_trace'])

def hat(w):
    x,y,z=w
    return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])

def exp_translation(w, rho):
    # Independent Taylor integral V(w) = sum hat(w)^k/(k+1)!.
    K = hat(w)
    term = np.eye(3)
    V = term.copy()
    for k in range(1,40):
        term = term @ K / (k+1)
        V += term
    return V @ rho

numeric=[]
for angle in [0., 1e-5, 8e-5, .0002, .2, .8]:
    axis=np.array([1.,2.,3.]);axis/=np.linalg.norm(axis)
    w=axis*angle
    Rpre=f['so3_exp'](np.array([.1,-.3,.2]))
    Rpost=Rpre@f['so3_exp'](w)
    t_body=np.array([.1,.2,-.05])
    vec=np.r_[-w, -Rpre@t_body]
    e=f['exact_e'](vec,Rpost)
    err=float(np.max(np.abs(exp_translation(e[:3],e[3:])-t_body)))
    world=f['so3_exp'](np.array([-.2,.3,.4]))
    equiv=f['exact_e'](np.r_[vec[:3],world@vec[3:]],world@Rpost)
    inv=float(np.max(np.abs(e-equiv)))
    assert err<1e-10 and inv<1e-10
    numeric.append({'angle':angle,'exp_log_translation_max_error':err,'world_reexpression_max_error':inv})
planar=f['exact_e'](np.array([0.,0.,-.2,-.1,0.,0.]),f['so3_exp'](np.array([0.,0.,.2])))
assert np.allclose(planar,[0.,0.,.2,.09966644423259238,-.01,0.],atol=1e-12)

# Header tokens are taken from the actual v10 source. Float/int rows below are synthetic controls.
cpp=(EXP/'host_change_trace_cov/src_LIVMapper.cpp.v10').read_text()
header_tokens=''.join(re.findall(r'"([^"\n]*)"', '\n'.join(cpp.splitlines()[366:368]))).replace('\\n','').lstrip('# ').split()
assert header_tokens[-1]=='pose7' and header_tokens.index('r_chi2w')+1==15
fixture=ROOT/'synthetic_trace_controls_v2';fixture.mkdir(exist_ok=True)
layout={}
for version, n in [('v8',93),('v10',100)]:
    header=header_tokens[:-1] if version=='v8' else header_tokens
    fields=['0']*n
    fields[header.index('n_scans')]='1';fields[header.index('has_out')]='1'
    if version=='v10':fields[-1]='1'
    path=fixture/(version+'.txt')
    path.write_text('# '+' '.join(header)+'\n'+' '.join(fields)+'\n',encoding='utf-8')
    layout[version]={}
    for name,parser in [('t2_run',f['parse_trace']),('t2_join_upgrade',up['parse_trace'])]:
        r=parser(str(path))
        layout[version][name]={'accepted':len(r['rows']),'malformed':r['malformed']}
        assert len(r['rows'])==(1 if version=='v8' else 0)

# Recalculate archived v7 diagnostic values, preserving its declared unresolved semantics.
summary=json.loads((SRC/'t2_summary.json').read_text())
joined=[json.loads(x) for x in (SRC/'t2_join.jsonl').read_text().splitlines() if x.strip()]
trace_bytes=(OLD/'host_logs/trace_cov.txt').read_bytes()
av_bytes=gzip.decompress((OLD/'availability_frames.jsonl.gz').read_bytes())
assert digest(trace_bytes)==summary['_meta']['trace_sha256']
assert digest(av_bytes)==summary['_meta']['availability_sha256']
trace=f['parse_trace'](str(OLD/'host_logs/trace_cov.txt'))
av=[json.loads(x) for x in av_bytes.splitlines() if x.strip()]
pose_path=EXP/'trace_fl_native_20261112T115734Z_483777/host_logs/M2DGR_room_02.txt'
pose=np.loadtxt(pose_path)
# The host streams preserve duplicate timestamp order. Here verify actual ordering before joining.
pose_ns=[int(round(x*1e9)) for x in pose[:,0]]
pose_groups=defaultdict(list)
for i,ns in enumerate(pose_ns):pose_groups[ns].append(i)
keys=sorted(pose_groups);used=Counter();exact={};errors=[]
for row in trace['rows']:
    if row['has_out']!=1:continue
    i=bisect.bisect_left(keys,row['abs_ns'])
    candidates=[x for x in keys[max(0,i-1):i+2] if abs(x-row['abs_ns'])<=2000]
    assert len(candidates)==1, candidates
    key=candidates[0];k=used[key];assert k<len(pose_groups[key])
    idx=pose_groups[key][k];used[key]+=1
    exact[row['idx']]=f['exact_e'](row['vec6'],f['quat_to_rot'](pose[idx,4:8]))
    errors.append(abs(key-row['abs_ns']))
mapped=f['build_join'](av,trace)['mapped'];values=[];max_diff=0.;row_differences=[]
for j,m in enumerate(mapped):
    val=f['i_evidence'](m['rows'],exact)
    assert val['present']==joined[j]['i']['present']
    if val['present']:
        values.append(val)
        for key in ['e_norm','s_i']:
            max_diff=max(max_diff,abs(val[key]-joined[j]['i'][key]))
        if abs(val['s_i']-joined[j]['i']['s_i'])>1e-7:
            row_differences.append({'kf_id':joined[j]['kf_id'],'trace_idx':val['trace_idx'],
                                    'saved_s':joined[j]['i']['s_i'],'correct_pose_s':val['s_i'],
                                    'saved_e_norm':joined[j]['i']['e_norm'],'correct_pose_e_norm':val['e_norm']})
# Execute exactly the reviewed pose-join statements of main, with immutable arrays as inputs.
main_ast=next(n for n in ast.parse((SRC/'t2_run.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='main')
join_statements=[n for n in main_ast.body if 276<=n.lineno<=306]
ns=dict(f);ns.update(m2=pose.copy(),ho_rows=[r for r in trace['rows'] if r['has_out']==1])
exec(compile(ast.Module(body=join_statements,type_ignores=[]),'reviewed_main_pose_join','exec'),ns)
buggy=ns['exact_by_idx'];buggy_diff=0.
for j,m in enumerate(mapped):
    val=f['i_evidence'](m['rows'],buggy)
    if val['present']:
        buggy_diff=max(buggy_diff,abs(val['s_i']-joined[j]['i']['s_i']))
assert buggy_diff<1e-7
sorted_order=sorted(range(len(pose)),key=lambda i:pose_ns[i])
wrong_rotation_pair_rows=sum(not np.allclose(exact[idx],buggy[idx],rtol=1e-12,atol=1e-12) for idx in exact)
norms=[x['e_norm'] for x in values];scores=[x['s_i'] for x in values]
block_tail={b['block_id'] for b in summary['blocks'] if b['tail']}
stats={'join_rows':len(joined),'numeric_I_rows':len(values),'trace_rows':len(trace['rows']),
       'malformed':trace['malformed'],'pose_rows':len(pose),'post_join_max_err_ns':max(errors),
       'e_norm_median':float(np.median(norms)),'e_norm_max':max(norms),
       's_median':float(np.median(scores)),'s_max':max(scores),'max_saved_row_numeric_diff':max_diff,
       'original_pose_time_decreases':sum(a>b for a,b in zip(pose_ns,pose_ns[1:])),
       'original_pose_indices_moved_by_sort':sum(i!=j for i,j in enumerate(sorted_order)),
       'correct_join_vs_main_e_differing_trace_rows':wrong_rotation_pair_rows,
       'correct_join_vs_saved_s_differing_join_rows':len(row_differences),
       'source_main_join_vs_saved_s_max_difference':buggy_diff,
       'largest_s_differences':sorted(row_differences,key=lambda x:abs(x['saved_s']-x['correct_pose_s']),reverse=True)[:5],
       'unknown_rows':sum(x['shadow_state']=='UNKNOWN' for x in joined),
       'unknown_blocks':sum(b['state']=='UNKNOWN' for b in summary['blocks']),
       'tail_pose':sum(x['tail'] for x in joined),
       'tail_block':sum(x['pose_stamp_ns']//500000000 in block_tail for x in joined),
       'qualification':summary['_meta']['i_qualification'],'physical_I_verified':False}
assert (stats['join_rows'],stats['numeric_I_rows'],stats['tail_pose'],stats['tail_block'])==(531,504,47,51)

prov=EXP/'run_provenance_131213';sha_rows=[]
for line in (prov/'SHA256SUMS').read_text().splitlines():
    expected,rel=line.split(maxsplit=1);p=ROOT/'experimental'/rel
    actual=digest(p.read_bytes());assert actual==expected
    sha_rows.append({'path':rel,'sha256':actual,'matches':True})
k3=EXP/'cphist_fl_native_20261112T131213Z_563253'
receipt=json.loads((k3/'receipt.json').read_text());run=json.loads((k3/'run_summary.json').read_text())
assert digest((prov/'recovery_node.executed.py').read_bytes())==receipt['inputs']['recovery_node_source']
fields=(k3/'cp_candidates.txt').read_text().splitlines()[1].split()
boundary,actual,legal=int(fields[1]),int(fields[2]),int(fields[5])
actions=run['native_checkpoint_actions'];restores=[x for x in actions if x['command']=='restore']
assert len(restores)==1 and f'stamp_ns={actual}' in restores[0]['ack']
history={'boundary_ns':boundary,'actual_restore_ns':actual,'legal_history_candidate_ns':legal,
         'candidate_minus_boundary_ns':legal-boundary,'actual_minus_boundary_ns':actual-boundary,
         'candidate_uses_full_restore':False,'reprocess_count':run['native_checkpoint']['reprocesses'],
         'unresolved_segments':run['lifecycle']['unresolved_segments'],
         'driver_matches_receipt':True,'provenance_files':sha_rows}
driver_now=(ROOT/'source/slam_recovery/ros/recovery_node.py').read_bytes()
driver_base=subprocess.check_output(['git','show','c91519734de99397e97e368d015f17694ffe303f:slam_recovery/ros/recovery_node.py'],cwd=REPO)
assert driver_now==driver_base
payload={'main':'66cc8146909329ef4bc712cd0728dc4cb4dfd0f4','experiment':'eb2630ef10f827626ee1eaad87fa7ddc39cc825c',
         'numpy':np.__version__,'scope':'AST-loaded reviewed pure functions; archive reads; no archived CLI, ROS, build, native run, install or push',
         'se3_controls':numeric,'planar_control':planar.tolist(),'v10_integration_control':layout,
         't2_archive_recalculation':stats,'history_provenance':history,
         'recovery_driver_unchanged_from_c915197':True,
         'v10_probe_results':[(EXP/f'host_change_trace_cov/probe_v10_pre_{i}/result.txt').read_text().strip() for i in range(1,6)]}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(payload,ensure_ascii=False,indent=2))
