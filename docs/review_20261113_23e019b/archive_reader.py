"""Read-only fixed Git blob auditor. Standard library; run python -I. Never imports archive code."""
import argparse, collections, gzip, hashlib, io, json, math, re, statistics, subprocess, sys
from pathlib import Path
SHA = 'a812302e3a9acd17b1e6f318d332b88563910069'
MAIN = '23e019bf7f9ac4bab71db9e50a009db704ffb952'
RUN = 'docs/review_20261112_four_host/growth_fl_native_20261112T165438Z_669633/'
SRC = 'docs/review_20261112_four_host/host_change_trace_cov/'
P = argparse.ArgumentParser(); P.add_argument('--repo', required=True); P.add_argument('--mode', default='survey'); P.add_argument('--out'); P.add_argument('--pattern'); P.add_argument('--path'); A=P.parse_args()
def git(*args):
    return subprocess.check_output(['git', '-C', A.repo, *args])
def blob(path, sha=SHA):
    if path == 'docs/review_20261110_2d36c6a/handoff.md': raise ValueError('excluded private path')
    return git('show', sha+':'+path)
def text(path, sha=SHA): return blob(path,sha).decode('utf-8', errors='replace')
def digest(b): return hashlib.sha256(b).hexdigest()
def numeric(path):
    s=text(path); heads=[l for l in s.splitlines() if l.startswith('#')]; rows=[]; bad=[]
    for i,l in enumerate(s.splitlines(),1):
        if not l.strip() or l.startswith('#'): continue
        try: rows.append([float(x) for x in l.split()])
        except ValueError: bad.append({'line':i,'prefix':l[:100]})
    return heads,rows,bad
if A.mode=='survey':
    report={'sha':SHA,'main':MAIN,'run':RUN}
    for p in ['receipt.json','wiring.json','launch_pair.sh','SHA256SUMS']:
        b=blob(RUN+p);report[p]={'sha256':digest(b),'value':json.loads(b) if p.endswith('.json') else b.decode()}
    summary=json.loads(blob(RUN+'run_summary.json'))
    report['summary']={k: (v if not isinstance(v,list) or len(v)<5 else {'len':len(v),'first':v[:1],'last':v[-1:]}) for k,v in summary.items()}
    for p in ['trace_cov.txt','mat_lio_pre.txt','mat_lio_out.txt','mat_pre.txt','mat_out.txt','M2DGR_room_02.txt']:
        h,r,bad=numeric(RUN+'host_logs/'+p)
        report[p]={'sha256':digest(blob(RUN+'host_logs/'+p)),'headers':h,'rows':len(r),'widths':dict(collections.Counter(map(len,r))),'first':r[:2],'last':r[-1:],'bad':bad}
    b=blob(RUN+'availability_frames.jsonl.gz')
    with gzip.GzipFile(fileobj=io.BytesIO(b)) as f:
        line=f.readline(); obj=json.loads(line)
    report['availability_first']={'sha256':digest(b),'keys':list(obj),'first':obj}
    out=json.dumps(report,ensure_ascii=False,indent=2)
    if A.out: Path(A.out).write_text(out,encoding='utf-8')
    print(out)
elif A.mode=='audit':
    V11='c5bc05763b553ebc7d5adc585ba8e84013e9fb6c'
    import difflib
    report={'sha':SHA,'v11_source_sha':V11,'main_claim_sha':MAIN,'run':RUN,'scope':'only original blobs; no archive code executed'}
    hashes={}
    def bind(path,sha=SHA):
        b=blob(path,sha); hashes[sha+':'+path]={'sha256':digest(b),'git_blob':git('rev-parse',sha+':'+path).decode().strip(),'bytes':len(b)};return b
    receipt=json.loads(bind(RUN+'receipt.json')); summary=json.loads(bind(RUN+'run_summary.json')); wiring=json.loads(bind(RUN+'wiring.json'))
    report['receipt_inputs']=receipt['inputs'];report['receipt_launch']=receipt['launch'];report['termination']=receipt['termination'];report['exit_codes']=receipt['exit_codes']
    bind(RUN+'launch_pair.sh'); manifest=bind(RUN+'SHA256SUMS').decode()
    report['manifest_checks']=[]
    for l in manifest.splitlines():
        expected,path=l.split(None,1); b=bind(RUN+path.removeprefix('./'));report['manifest_checks'].append({'path':path,'matches':digest(b)==expected,'expected':expected,'actual':digest(b)})
    report['recovery_source_matches_receipt']=digest(bind('slam_recovery/ros/recovery_node.py'))==receipt['inputs']['recovery_node_source']
    sources={}
    for name in ['src_LIVMapper.cpp','src_voxel_map.cpp','include_LIVMapper.h','include_voxel_map.h','include_common_lib.h']:
        b11=bind(SRC+name+'.v11',V11);b12=bind(SRC+name+'.v12');sources[name]={'same':b11==b12}
        if b11!=b12: sources[name]['diff']=''.join(difflib.unified_diff(b11.decode().splitlines(True),b12.decode().splitlines(True),fromfile='v11',tofile='v12',n=3))
    report['sources']=sources
    trace_bytes=bind(RUN+'host_logs/trace_cov.txt'); trace_s=trace_bytes.decode(); headers=[l for l in trace_s.splitlines() if l.startswith('#')]
    header=next(l for l in headers if l.startswith('# idx '));report['actual_idx_header']=header
    widths={'vec6':6,'Ppre6x6':36,'Ppost6x6':36,'pose7':7,'pre_pose7':7}; names=header.split()[1:]; offset=0;blocks={}
    for name in names: blocks[name]=[offset,offset+widths.get(name,1)];offset+=widths.get(name,1)
    report['header_width']={'tokens':len(names),'expanded':offset,'blocks':blocks}
    rows=[]
    for l in trace_s.splitlines():
        if not l.strip() or l.startswith('#'):continue
        ss=l.split();row=[float(x) for x in ss]
        for j in [0,2,3,4,5,6,7,8,9]: row[j]=int(ss[j])
        rows.append(row)
    byidx={r[0]:r for r in rows};valid=[r for r in rows if r[7]==1];early=[r for r in rows if r[7]==0]
    def sample(r):return {'idx':r[0],'rel_s':r[1],'abs_ns':r[2],'grp_idx':r[3],'scan_first_ns':r[4],'scan_last_ns':r[5],'n_scans':r[6],'has_out':r[7],'eff':r[9],'pose7':r[93:100],'pre_pose7':r[100:107]}
    report['trace']={'rows':len(rows),'widths':dict(collections.Counter(map(len,rows))),'idx_contiguous':list(byidx)==list(range(len(rows))),'has_out':dict(collections.Counter(r[7] for r in rows)),'phase':dict(collections.Counter(r[8] for r in rows)),'grp_unique':len(set(r[3] for r in rows)),'finite':all(math.isfinite(x) for r in rows for x in r),'first':sample(rows[0]),'last':sample(rows[-1]),'early_pre_position_nonzero':sum(any(x!=0 for x in r[100:103]) for r in early),'early_pre_quat_norm_min':min(math.sqrt(sum(x*x for x in r[103:107])) for r in early),'early_post_cov_all_zero':all(all(x==0 for x in r[57:93]) for r in early),'updates_prepost_position_changed':sum(any(a!=b for a,b in zip(r[93:96],r[100:103])) for r in valid),'abs_ns_strict_increase':all(b[2]>a[2] for a,b in zip(rows,rows[1:])),'rel_s_span':rows[-1][1]-rows[0][1]}
    report['span']={'first_missing':sum(r[4]<=0 for r in rows),'last_missing':sum(r[5]<=0 for r in rows),'first_gt_last':sum(r[4]>r[5] for r in rows),'scan_count_distribution':dict(collections.Counter(r[6] for r in rows)),'first_equals_last':sum(r[4]==r[5] for r in rows),'distinct_scan_headers':len(set(r[5] for r in rows)),'scan_last_monotone':all(b[5]>=a[5] for a,b in zip(rows,rows[1:])),'note':'span endpoints represent raw scan header timestamps, not point-time coverage'}
    for fn,delta,pose_start in [('mat_lio_pre.txt',0,100),('mat_lio_out.txt',1,93)]:
        bind(RUN+'host_logs/'+fn);h,m,bad=numeric(RUN+'host_logs/'+fn); matched=[];wrong=[]
        for r in m:
            t=byidx.get(int(r[0])+delta)
            if t is None:wrong.append({'idx':int(r[0]),'grp':int(r[1]),'rel_s':r[3]});continue
            matched.append({'grp_equal':int(r[1])==t[3],'phase_equal':int(r[2])==t[8],'time_round6_ok':abs(r[3]-t[1])<=0.000051,'pos_round6_ok':all(abs(x-y)<=max(0.00000051,abs(y)*0.0000051) for x,y in zip(r[7:10],t[pose_start:pose_start+3])),'pos_abs_max':max(abs(x-y) for x,y in zip(r[7:10],t[pose_start:pose_start+3]))})
        report[fn]={'rows':len(m),'widths':dict(collections.Counter(map(len,m))),'join_delta':delta,'joined':len(matched),'unjoined':wrong,'grp_equal':sum(x['grp_equal'] for x in matched),'phase_equal':sum(x['phase_equal'] for x in matched),'time_round6_ok':sum(x['time_round6_ok'] for x in matched),'pos_round6_ok':sum(x['pos_round6_ok'] for x in matched),'max_pos_rounding_abs':max(x['pos_abs_max'] for x in matched),'last':m[-1]}
    for fn in ['mat_pre.txt','mat_out.txt','M2DGR_room_02.txt']:
        bind(RUN+'host_logs/'+fn);h,m,bad=numeric(RUN+'host_logs/'+fn);report[fn]={'rows':len(m),'widths':dict(collections.Counter(map(len,m))),'last':m[-1]}
    side=bind(RUN+'availability_frames.jsonl.gz');statuses=collections.Counter();ids=[];poses=[];scans=[];dts=[];first=None;last=None
    with gzip.GzipFile(fileobj=io.BytesIO(side)) as f:
        for l in f:
            x=json.loads(l);first=x if first is None else first;last=x;statuses[x['status']]+=1;ids.append(x['kf_id']);poses.append(x['pose_stamp_ns']);scans.append(x['scan_stamp_ns']);dts.append(x['pose_scan_dt_ns'])
    report['paired_sidecar']={'rows':len(ids),'kf_ids_unique':len(set(ids)),'pose_stamps_unique':len(set(poses)),'scan_stamps_unique':len(set(scans)),'max_abs_dt_ns':max(map(abs,dts)),'dt_arithmetic_consistent':all(p-s==d for p,s,d in zip(poses,scans,dts)),'status_counts':dict(statuses),'first_pose_stamp_ns':first['pose_stamp_ns'],'last_pose_stamp_ns':last['pose_stamp_ns'],'last_scan_stamp_ns':last['scan_stamp_ns'],'last_manager':last['manager'],'stamp_span_s':(last['pose_stamp_ns']-first['pose_stamp_ns'])/1e9}
    def fields(e):return dict(re.findall(r'(\w+)=([^ ]*)',e.get('ack','')))
    events=summary['native_checkpoint']['events']; snaps=[]
    for e in events:
        f=fields(e)
        if e['command']=='snapshot' and e.get('ok'):
            snaps.append({'stamp_ns':int(f['stamp_ns']),'rel_s':(int(f['stamp_ns'])-rows[0][2])/1e9,'wall':e['wall'],'ack_wall':e['ack_wall'],'frame':int(f['frame']),'voxels':int(f['live_voxels']),'points':int(f['live_points'])})
    rates=[]
    for a,b in zip(snaps,snaps[1:]):
        dt=(b['stamp_ns']-a['stamp_ns'])/1e9; dw=b['wall']-a['wall'];rates.append({'a_rel_s':a['rel_s'],'b_rel_s':b['rel_s'],'dt_stamp_s':dt,'dt_wall_s':dw,'d_voxels':b['voxels']-a['voxels'],'d_points':b['points']-a['points'],'voxels_per_stamp_s':(b['voxels']-a['voxels'])/dt if dt>0 else None,'points_per_stamp_s':(b['points']-a['points'])/dt if dt>0 else None,'voxels_per_wall_s':(b['voxels']-a['voxels'])/dw if dw>0 else None})
    q=summary['quarantine'];episode=[]
    for e in q['episode_detail']:
        cc=e['checkpoint_check'];episode.append({'index':e['index'],'trigger_ns':e['trigger_ts_ns'],'trigger_rel_s':(e['trigger_ts_ns']-rows[0][2])/1e9,'decision_basis':e['decision_basis'],'checkpoint_check':cc,'late_s':(cc['actual_stamp_ns']-cc['boundary_stamp_ns'])/1e9,'restore_ack':fields(e['native_checkpoint']),'restore_disposition':e['restore_disposition']})
    report['episodes']=episode; report['gate']=summary['gate'];lc=summary['lifecycle'];report['lifecycle']={'state':lc['state'],'unresolved_segments':lc['unresolved_segments'],'events':[{k:(len(v) if k=='frames_unresolved' else v) for k,v in e.items()} for e in lc['events']]}; report['checkpoint']={k:v for k,v in summary['native_checkpoint'].items() if k not in ['events','snapshot_ack_s']}
    report['checkpoint']['events_by_command_result']=dict(collections.Counter(e['command']+':'+str(e.get('ok')) for e in events));report['checkpoint']['last_successful_ack']=next(e for e in reversed(events) if e.get('ok'));report['checkpoint']['last_event']=events[-1]
    report['growth_from_snapshot_acks']={'snapshots':snaps,'rates':rates,'first_to_third':{'dt_stamp_s':(snaps[2]['stamp_ns']-snaps[0]['stamp_ns'])/1e9,'voxels':snaps[2]['voxels'],'points':snaps[2]['points']},'observed_max_rate':max((r for r in rates if r['voxels_per_stamp_s'] is not None),key=lambda r:r['voxels_per_stamp_s']),'note':'sparse observations, restores/holds and timeouts; no per-frame host map inventory archived; cannot establish reported true peak/final 593925'}
    def stats(rs):
        return {'rows':len(rs),'has_out':sum(r[7]==1 for r in rs),'eff':{'min':min(r[9] for r in rs),'median':statistics.median(r[9] for r in rs),'max':max(r[9] for r in rs)},'r_abs_mean_m_median':statistics.median(r[12] for r in rs),'r_med_abs_m_median':statistics.median(r[11] for r in rs),'r_chi2_per_eff_median':statistics.median(r[13]/r[9] for r in rs if r[9]>0),'r_chi2w_per_eff_median':statistics.median(r[14]/r[9] for r in rs if r[9]>0),'post_translation_norm_max_m':max(math.sqrt(sum(x*x for x in r[93:96])) for r in rs)}
    report['trace_update_diagnostics']={'all_valid':stats(valid),'first_30_stamp_s':stats([r for r in valid if r[1]<30]),'last_after_30_stamp_s':stats([r for r in valid if r[1]>=30]),'note':'eff count and final-iteration measurement summaries; no correspondence denominator/GT; not proof of cause or stability'}
    report['final_summary']={k:summary[k] for k in ['final_state','quarantine_open_at_exit','trusted_keyframes_at_exit','pairing','runtime']}
    def producer_header(sha,version):
        s=text(SRC+'src_LIVMapper.cpp.'+version,sha);start=s.index('<< "# idx rel_s');end=s.index('pre_pose7\\n"',start)+len('pre_pose7\\n"')
        return ''.join(json.loads(t) for t in re.findall(r'"(?:[^"\\]|\\.)*"',s[start:end])).rstrip('\n')
    report['producer_headers']={'v11':producer_header(V11,'v11'),'v12':producer_header(SHA,'v12'),'all_match_actual':producer_header(V11,'v11')==header==producer_header(SHA,'v12')}
    report['trace']['abs_ns_distinct']=len(set(r[2] for r in rows));report['trace']['zero_eff_has_out']=sum(r[9]==0 for r in valid)
    report['conclusions']={'prepost':'Readable same-row same handleLIO update for has_out=1, confirmed source capture/write placement plus rounded mat_lio joins. Ppre/Ppost are not covariance of their difference; no cross-covariance or S exported. Early has_out=0 has no valid posterior even though pose7 is written.', 'covariance_tangent':'Source right-multiplies rotation, but position increment is additive world-frame, not full body-frame SE3 tangent as prose suggests. StatesGroup operator+= lines 192-193 / operator- lines 205-207. Avoid whole-6D body adjoint without establishing mixed coordinates.', 'v12':'Only LIVMapper cpp changed: lio stream precision6 to10 and out idx rows-1 to rows; other four blobs identical. No v12 run measured here.', 'actual_closure':'0 accepted / 2 rejected / 0 commit. ACK holds/restores/resumes2 each; no replay or repair observed. lifecycle.unresolved_segments=2 even though final HEALTHY and quarantine closed.', 'trace_terminal_gap':'793 mat_lio_pre / 726 mat_lio_out and absolute pose output, but792 trace /725 has_out: one last completed output has no archived trace posterior. Buffered tail loss possible; cause UNKNOWN.', 'growth':'Developer-reported 593925 voxels/4.15M points, peak42.9k/s at301.6s,722frames,first30s andeff13227 are not reproducible from sparse ACK inventory and missing growth script/host.log; no per-frame host map inventory in trace. ACK arithmetic supports large later net map growth, not exact peak/timing/causal mechanism.', 'minimal_unblock':'Read-only fix block header expansion and join v11 out idx+1; exclude unjoined final posterior/has_out=0. Obtain already-existing archived map-count series, original time origin/script and terminal host status if available, no new host run/build/ASan authorization. Missing evidence remains UNKNOWN/DEVELOPER_REPORTED.', 'scope':'No fetch, production modifications, archived CLI/ROS/build/algorithm, dependency install or delegation. Did not read excluded private handoff.'}
    report['hashes']=hashes
    out=json.dumps(report,ensure_ascii=False,indent=2)
    if A.out:Path(A.out).write_text(out,encoding='utf-8')
    print(out)
elif A.mode=='source':
    lines=text(A.path).splitlines(); hits=set()
    for i,l in enumerate(lines):
        if re.search(A.pattern,l): hits.update(range(max(0,i-8),min(len(lines),i+16)))
    for i in sorted(hits): print(f'{i+1}: {lines[i]}')
elif A.mode=='find':
    paths=git('ls-tree','-r','--name-only',SHA).decode().splitlines()
    print('\n'.join(p for p in paths if re.search(A.pattern,p)))
