from pathlib import Path
import argparse
import ast,bisect,gzip,hashlib,json,math,subprocess
from collections import Counter,defaultdict
from typing import Any,Dict,List,Optional
import numpy as np
ap=argparse.ArgumentParser()
ap.add_argument('--work-dir', type=Path, required=True)
R=ap.parse_args().work_dir.resolve()
P=R/'main/docs/ali_h_v1_research'
G=R/'growth/docs/review_20261112_four_host'
FN={'so3_exp','so3_left_jacobian_inv','quat_to_rot','exact_e','_tail_value','pose_from_tail','so3_log','e_i_from_poses','expand_tail_names','parse_trace','build_join','i_evidence'}
def functions(path,names):
    tree=ast.parse(path.read_text(encoding='utf-8'))
    ns=dict(np=np,math=math,bisect=bisect,Counter=Counter,defaultdict=defaultdict,Any=Any,Dict=Dict,List=List,Optional=Optional,POSE_LEAVES=('x','y','z','qx','qy','qz','qw'))
    fs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(fs)==len(names)
    exec(compile(ast.Module(body=fs,type_ignores=[]),str(path),'exec'),ns)
    return tree,ns
T,F=functions(P/'t2_run.py',FN)
_,U=functions(P/'t2_join_upgrade.py',{'expand_tail_names','parse_trace'})
# Close the original real-data index counterexample using exact current main statements.
oldtrace=R/'legacy/trace_cov.txt'
assert hashlib.sha256(oldtrace.read_bytes()).hexdigest()==json.loads((P/'t2_summary.json').read_text())['_meta']['trace_sha256']
pose=R/'legacy/M2DGR_room_02.txt'
old=F['parse_trace'](str(oldtrace)); m2=np.loadtxt(pose)
fn=next(n for n in T.body if isinstance(n,ast.FunctionDef) and n.name=='main')
start=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='pose_rows' for x in n.targets))
end=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='join' for x in n.targets))
ns=dict(F,m2=m2,ho_rows=[r for r in old['rows'] if r['has_out']==1])
exec(compile(ast.Module(body=fn.body[start:end],type_ignores=[]),'current_pose_join','exec'),ns)
saved=[json.loads(x) for x in (P/'t2_join.jsonl').read_text().splitlines()]
previous=[json.loads(x) for x in (R/'previous/t2_join.jsonl').read_text().splitlines()]
byidx={r['idx']:r for r in old['rows']}; vals=[]; dif=[]
for a,b in zip(saved,previous):
    if a['i']['present']:
        val=F['i_evidence']([byidx[a['i']['trace_idx']]],ns['exact_by_idx'])
        assert np.isclose(val['s_i'],a['i']['s_i'],rtol=1e-10,atol=1e-8)
        vals.append(val['s_i']); dif.append(abs(a['i']['s_i']-b['i']['s_i'])>1e-7)
legacy={'rows':len(saved),'numeric_rows':len(vals),'changed_scores':sum(dif),'median':float(np.median(vals))}
# Real producer file, not an expanded synthetic header.
run=G/'growth_fl_native_20261112T165438Z_669633'; tp=run/'host_logs/trace_cov.txt'
trace=F['parse_trace'](str(tp)); alt=U['parse_trace'](str(tp)); rows=trace['rows']; assert len(rows)==len(alt['rows'])==792
assert not trace['malformed'] and not alt['malformed']
assert all(a['pose_tail']==b['pose_tail'] for a,b in zip(rows,alt['rows']))
summary=json.loads((P/'t2_v11_summary.json').read_text()); meta=summary['_meta']
assert hashlib.sha256(tp.read_bytes()).hexdigest()==meta['trace_sha256']
for file,key in [('receipt.json','receipt_sha256'),('run_summary.json','summary_sha256')]:assert hashlib.sha256((run/file).read_bytes()).hexdigest()==meta[key]
# Independently recover rho by V series and solve, instead of the implementation's inverse formula.
def hat(w):
    x,y,z=w;return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
errs=[]; exact={}
for row in rows:
    if row['has_out']!=1:continue
    pre=row['pre_pose'];post=F['pose_from_tail'](row['pose_tail'])
    e=F['e_i_from_poses'](pre,post); w=e[:3];K=hat(w);term=np.eye(3);V=term.copy()
    for k in range(1,40):term=term@K/(k+1);V+=term
    t=F['quat_to_rot'](pre[3:]).T@(post[:3]-pre[:3])
    rho=np.linalg.solve(V,t);errs.append(float(np.max(np.abs(e[3:]-rho))));exact[row['idx']]=e
assert max(errs)<1e-8
joined=[json.loads(x) for x in (P/'t2_v11_join.jsonl').read_text().splitlines()]
idx={x['idx']:x for x in rows};norm=[];zero=0
for a in joined:
    if a['i']['present']:
        e=exact[a['i']['trace_idx']];norm.append(float(np.linalg.norm(e)))
        assert np.isclose(norm[-1],a['i']['e_norm'],rtol=1e-10,atol=1e-8)
        if idx[a['i']['trace_idx']]['eff']==0:zero+=1;assert a['i']['zero_constraint'] and np.linalg.norm(e)<1e-12
origin=min(r['abs_ns'] for r in rows);runsummary=json.loads((run/'run_summary.json').read_text())
ep=runsummary['quarantine']['episode_detail'][1];deadline=(ep['deadline_ns']-origin)/1e9
assert deadline==meta['e2_deadline_rel_s']
tail=sum(a['pose_stamp_ns']>=ep['deadline_ns'] for a in joined);assert tail==303==sum(a['tail'] for a in joined)
v11={'trace_rows':len(rows),'has_out_rows':len(exact),'paired_rows':len(joined),'numeric_rows':len(norm),'zero_effective_rows':zero,'median_e_norm':float(np.median(norm)),'median_unit_energy':float(np.median(np.square(norm))),'independent_translation_max_error':max(errs),'tail_rows':tail,'deadline_rel_s':deadline,'all_unknown':all(a['shadow_state']=='UNKNOWN' for a in joined),'layers':meta['i_qualification_layers']}
# Archive-level independent arithmetic. No claim of full bag reread.
fp=G/'fastlio2_independent_20261113';a=json.loads((fp/'run2/analysis.json').read_text()); od=a['/Odometry'];gaps=[]
for gap in od['gaps_gt_1s']:
    dt=(gap['to_ns']-gap['from_ns'])/1e9;step=float(np.linalg.norm(np.array(gap['pos_after'])-gap['pos_before']))
    assert abs(dt-gap['dt_s'])<1e-9 and abs(step-gap['step_m'])<1e-8
    gaps.append({'seconds':dt,'jump_m':step})
node=(fp/'run2/fastlio_node.log').read_text(); runner=(fp/'run2/runner.log').read_text()
fl={'messages':od['messages'],'topics':a['topics'],'messages_total':sum(a['topics'].values()),'gaps':gaps,'e2_tail_s':(od['last_stamp_ns']-a['events_ns']['E2'])/1e9,'e2_tail_rows':od['messages_after_E2'],'imu_initial_done_log_count':node.count('IMU Initial Done'),'runner_120s_record_present':'bag_duration_after_120s=' in runner,'source_identity':(fp/'source_identity.txt').read_text(),'bag_reread':False}
result={'legacy_index_fix':legacy,'v11_existing_archive':v11,'fastlio2_archive_checks':fl,'native_build_run_replay_performed':False}
(R/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
