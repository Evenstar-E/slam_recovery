"""Code-derived diagrams and provenance-aware charts. Never overwrites source figures.

Usage: python docs/review_20261105/redraw_figures.py
Dependencies: numpy, matplotlib, pillow. No ROS, dataset or GPU required.
"""
from pathlib import Path
import csv
import hashlib
import json
import sys
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DEPS = ROOT.parent / '.viz_dependencies'
if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))
sys.path.insert(0, str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.lines import Line2D
from matplotlib import font_manager
from PIL import Image, ImageDraw
from slam_recovery.experiments.injection.injectors import (
    LiDARInjectionParams, inject_lidar_attenuation_and_dropout,
    inject_plastic_bag_near_field_occlusion, inject_visual_exposure_drop,
)

OUT = Path(__file__).parent / 'figures'
OUT.mkdir(exist_ok=True)
MAN = ROOT / 'slam_recovery/experiments/manifests'
INK='#172D43'; BLUE='#17638C'; TEAL='#176C60'; ORANGE='#A84C16'; PURPLE='#6D4B91'
GRAY='#526476'; BG='#F4F7FA'; RED='#A13F43'
PALE=['#E8F2F8','#E9F3EE','#FFF1E3','#F0EAF6']
font_path=Path('C:/Windows/Fonts/msyh.ttc')
if font_path.exists():
    font_manager.fontManager.addfont(str(font_path))
    FAMILY=font_manager.FontProperties(fname=str(font_path)).get_name()
else:
    FAMILY='DejaVu Sans'
plt.rcParams.update({'font.family':[FAMILY,'DejaVu Sans'],'font.size':11,
    'axes.unicode_minus':False,'text.color':INK,'axes.labelcolor':INK,
    'axes.edgecolor':'#B6C5D0','xtick.color':GRAY,'ytick.color':GRAY,
    'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white',
    'pdf.fonttype':42,'svg.fonttype':'none'})
MANIFEST=[]; TABLE=[]

def title(fig, number, heading, sub):
    fig.text(.035,.954,f'{number}  /  {heading}',size=22,weight='bold',color=INK)
    fig.text(.035,.913,sub,size=10.6,color=GRAY)

def base(number, heading, sub, height=9):
    fig=plt.figure(figsize=(16,height))
    title(fig,number,heading,sub)
    ax=fig.add_axes([.035,.11,.93,.75]); ax.set(xlim=(0,100),ylim=(0,100)); ax.axis('off')
    return fig,ax

def card(ax,x,y,w,h,head,body='',color=BLUE,fill=PALE[0],dash=False,fs=12):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.2,rounding_size=1.1',
        edgecolor=color,facecolor=fill,linewidth=1.3,linestyle='--' if dash else '-'))
    ax.text(x+w/2,y+h*.73,head,ha='center',va='center',size=fs,weight='bold',color=color)
    if body: ax.text(x+w/2,y+h*.32,body,ha='center',va='center',size=10.2,color=INK,linespacing=1.5)

def arrow(ax,a,b,label='',dash=False,color=GRAY,rad=0):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=13,lw=1.5,
        color=color,linestyle='--' if dash else '-',connectionstyle=f'arc3,rad={rad}'))
    if label: ax.text((a[0]+b[0])/2,(a[1]+b[1])/2+2,label,ha='center',size=9,color=color,
                     bbox=dict(fc='white',ec='none',pad=1))

def foot(fig,text): fig.text(.035,.035,text,size=10,color=GRAY,linespacing=1.5)

def save(fig,name,kind,sources,caption):
    files=[]
    for ext in ['svg','pdf','png']:
        p=OUT/f'{name}.{ext}'
        fig.savefig(p,dpi=170)
        if ext=='svg':
            p.write_text('\n'.join(line.rstrip() for line in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
        files.append({'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                      'bytes':p.stat().st_size})
    MANIFEST.append(dict(name=name,kind=kind,caption=caption,
        source_sha256={s:hashlib.sha256((ROOT/s).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for s in sources},outputs=files))
    plt.close(fig)

def architecture():
    from architecture_paper import draw
    fig=draw()
    save(fig,'01_architecture','CODE_DERIVED', ['slam_recovery/core.py','slam_recovery/quarantine/manager.py',
         'slam_recovery/health/detector.py','slam_recovery/diagnosis/signature_router.py',
         'docs/review_20261105/architecture_paper.py'],
         'Original vector overview inspired by FAST-LIVO2 visual grammar; separates native LIO, Python research dependencies, pose-only commit and pending native handoff.')


def gate():
    fig,ax=base('02','四种处理模式，到底检查了什么','忠实表达 evaluate_four_mode_gate 的现有顺序；阈值仅是该版本配置')
    card(ax,1,80,31,18,'短暂异常？','持续 < 1 s 且传播协方差范数 < 1.0')
    card(ax,61,80,37,18,'M1  在线降权模式','当前函数返回模式，管理器进入等待',TEAL,PALE[1])
    arrow(ax,(32,89),(61,89),'是')
    card(ax,1,48,31,23,'候选是否同时满足？','弱向信息 ≥ 25，增量 > 0\n留出分数 ≤ 2.5，协方差范数 ≤ 0.5')
    arrow(ax,(16.5,80),(16.5,71),'否')
    card(ax,61,50,37,20,'M2  采用候选','另验父版本；当前仅合并 repaired_poses',TEAL,PALE[1])
    arrow(ax,(32,60),(61,60),'有候选且全通过')
    card(ax,1,18,31,21,'传播协方差范数 < 4？','无候选或候选未通过时')
    arrow(ax,(16.5,48),(16.5,39),'否 / 无候选')
    card(ax,61,24,37,17,'M3  等待新证据','保持可信位姿字典',PURPLE,PALE[3])
    card(ax,61,1,37,17,'M4  归档并中止','保存 sleeping_submaps；状态 ABORTED',ORANGE,PALE[2])
    arrow(ax,(32,32),(61,32),'是'); arrow(ax,(32,22),(61,10),'否')
    foot(fig,'Wilson 配对收益检验是另一函数，由部分评测脚本调用；四模式门本身不强制调用。\n现有门尚未完整检查有限值、SE(3) 合法性、留出覆盖及完整状态提交，不能当作充分安全证明。')
    save(fig,'02_gate_logic','CODE_DERIVED',['slam_recovery/core.py','slam_recovery/quarantine/manager.py',
        'slam_recovery/validation/wilson_validator.py'],'Four-mode gate in actual precedence, with implemented scope and missing checks explicitly labeled.')

def timeline():
    fig=plt.figure(figsize=(16,8)); title(fig,'03','延迟提交能保护多长时间？','替换原 Fig. 1 的随机信号曲线；这里是逻辑示意与可复现反例，不是 hall_01 实测')
    axes=[fig.add_axes([.12,.56,.78,.25]),fig.add_axes([.12,.20,.78,.25])]
    for ax,alarm,head in zip(axes,[11.5,14],['A  及时报警：延迟 1.5 s，小于 2 s 缓冲','B  迟到报警：延迟 4 s，超过 2 s 缓冲']):
        ax.set(xlim=(7,15),ylim=(-.7,1.1),yticks=[],xlabel='时间 / s')
        ax.set_title(head,loc='left',size=13,pad=15)
        ax.axvspan(10,alarm,color=PALE[2],zorder=0)
        ax.plot([7,alarm-2],[0,0],lw=14,color=BLUE,solid_capstyle='butt')
        ax.plot([alarm-2,alarm],[0,0],lw=14,color=TEAL,solid_capstyle='butt')
        ax.axvline(10,color=ORANGE,ls='--',lw=1.5); ax.axvline(alarm,color=INK,ls=':',lw=1.5)
        ax.text(10,.65,'真实起点',ha='center',color=ORANGE,size=11)
        ax.text(alarm,.65,'报警',ha='center',size=11)
        ax.text((7+alarm-2)/2,-.42,'已提交',ha='center',color=BLUE)
        ax.text(alarm-1,-.42,'仍在缓存',ha='center',color=TEAL)
        if alarm==14:
            ax.scatter([10,11,12],[0,0,0],s=160,marker='X',fc=RED,ec='white',zorder=5)
            ax.text(11,.30,'10 / 11 / 12 s 坏位姿仍在 trusted_poses',ha='center',color=RED,size=11)
        else:
            ax.text(7.1,.32,'报警前停止晋升，缓存可覆盖故障尾段',size=11,color=GRAY)
        for sp in ['left','top','right']: ax.spines[sp].set_visible(False)
    foot(fig,'反例 R2：调用当前管理器，真实起点 10 s、14 s 报警、2 s 缓冲；创建的“8 s checkpoint”仍含 9–12 s 状态。\n结论：缓存只在有限检测延迟下防止新污染；更早的污染必须依赖真实历史 checkpoint 与可撤销日志。')
    save(fig,'03_delay_boundary','SCHEMATIC_AND_REPRODUCTION',['docs/review_20261105/audit_results.json',
         'slam_recovery/quarantine/manager.py'],'Timely alarm schematic and reproduced late-alarm failure; no invented measured time series.')

def ablation():
    path='slam_recovery/experiments/manifests/e2_ablation_b0_b7_and_r4_r5.json'
    data=json.loads((ROOT/path).read_text())['e2_b0_to_b6_ablation_hall01_plasticbag']
    keys=list(data); codes=['B0','B2','B4','B5','B6']
    labels=['B0 原宿主','B2 MM-LINS','B4 隔离构造','B5 不验证','B6 完整方案标签']
    source_types=[['常数','复用 MM-LINS','离线构造','复用 B6','注入 manifest'],
                  ['注入 manifest','复用 MM-LINS','离线构造','常数','离线构造']]
    fig=plt.figure(figsize=(16,9)); title(fig,'04','误差数值与证据类型一起看','重画原 Fig. 2；原值保留。此图转录仓库报告，未重新运行宿主或重算 ATE')
    for j,(field,col) in enumerate([('FAST_LIO2_ate_rmse_m',BLUE),('LIO_SAM_ate_rmse_m',TEAL)]):
        ax=fig.add_axes([.15+j*.43,.24,.32,.59])
        vals=[data[k][field] for k in keys]
        for i,(v,typ) in enumerate(zip(vals,source_types[j])):
            marker='s' if typ=='离线构造' else ('X' if typ in ['常数','复用 B6'] else 'o')
            ax.plot([0,v],[i,i],color='#D2DDE5',lw=2)
            ax.scatter(v,i,s=80,marker=marker,fc='white' if typ=='离线构造' else col,ec=col,lw=1.7,zorder=4)
            ax.text(v+.13,i-.10,f'{v:.4f} m',size=10,color=INK)
            ax.text(v+.13,i+.17,typ,size=8.6,color=GRAY)
            TABLE.append(dict(figure='04',group=field,variant=codes[i],metric='repository_reported_ATE_RMSE_m',value=v,source=path,evidence=typ))
        ax.set(xlim=(0,9.7),ylim=(4.65,-.65),yticks=range(5),yticklabels=labels if j==0 else [],xlabel='仓库报告的 ATE RMSE / m')
        ax.set_title('FAST-LIO2 列' if j==0 else 'LIO-SAM 列',loc='left',size=15,weight='bold')
        ax.grid(axis='x',color='#E4EAF0'); ax.set_axisbelow(True)
        for sp in ['top','right','left']:ax.spines[sp].set_visible(False)
    foot(fig,'关键限制：B2 同一个 MM-LINS 数值被填进两个宿主列；B4 区间外使用 B6 增量；B5 部分数字为常数或复用。\n原“地图污染率”实际是关键帧位置误差代理，B4/B6 的 0 只统计报警前已提交部分。三维全图污染与覆盖尚待独立测量。')
    save(fig,'04_ablation_provenance','REPOSITORY_REPORTED',[path,'slam_recovery/experiments/run_e2_ablation_matrix.py'],
         'Original ATE values with explicit provenance; proxy pollution not relabeled as voxel-map quality.')

def evidence():
    fig,ax=base('05','如何避免“用同一份证据修，再用它证明修得好”','审阅启发  /  下排为建议的验证设计，尚未实现')
    ax.text(1,96,'当前 E3 的主要依赖',size=13,weight='bold')
    card(ax,1,64,26,23,'辅助 LiDAR 轨迹','用于构造视觉候选',BLUE,PALE[0])
    card(ax,37,64,26,23,'桥接后的候选','增量接近辅助轨迹',BLUE,PALE[0])
    card(ax,73,64,26,23,'候选 − 辅助增量','再扰动同帧奇偶点求分数',ORANGE,PALE[2])
    arrow(ax,(27,76),(37,76)); arrow(ax,(63,76),(73,76))
    ax.plot([14,14,86],[64,57,57],color=ORANGE,ls='--',lw=1.5)
    arrow(ax,(86,57),(86,64),dash=True,color=ORANGE)
    ax.text(50,59,'同一辅助源再次进入评分',ha='center',size=10,color=ORANGE)
    ax.text(50,46,'点 ID 不重合，并不等于约束来源独立。',ha='center',size=14,color=ORANGE,weight='bold')
    ax.text(1,39,'建议的最小修正',size=13,weight='bold',color=TEAL)
    for x,h,b in [(1,'拟合集 A','求起点 / 修正量 / 候选\n只记录已到达数据'),(37,'验证集 B','独立时段 / 子地图 / 观测\n固定对应与失配分母'),(73,'最终评测 C','全图距离 + 覆盖\n轨迹误差 + clean 干预')]:
        card(ax,x,6,26,24,h,b,TEAL,PALE[1],True)
    arrow(ax,(27,18),(37,18),'冻结候选',True,TEAL)
    arrow(ax,(63,18),(73,18),'只验一次',True,TEAL)
    foot(fig,'验证时保留失配率、方向 / 时间覆盖与尾段坏点。独立验证仍需检查共同地图、共同 IMU 或辅助估计带来的相关性。')
    save(fig,'05_evidence_split','CODE_DERIVED_AND_PROPOSED',[
        'slam_recovery/experiments/e3_orbslam3/evaluate_e3_orbslam3.py',
        'slam_recovery/validation/fim_and_holdout.py'],
        'Current shared auxiliary evidence versus a proposed fit/validation/final-evaluation split.')

def faults():
    rng=np.random.default_rng(42)
    xyz=np.vstack([np.c_[rng.uniform(-6,6,900),np.full(900,4),rng.uniform(-1,3,900)],
                   np.c_[np.full(900,6),rng.uniform(-4,4,900),rng.uniform(-1,3,900)],
                   np.c_[rng.uniform(-6,6,900),rng.uniform(-4,4,900),np.full(900,-1)]])
    pts=np.c_[xyz,np.full(len(xyz),180)]
    occ,mask=inject_plastic_bag_near_field_occlusion(pts,occluded_azimuth_fraction=.75,seed=42)
    params=LiDARInjectionParams(alpha_extinct=.03,sigma_range_m=.03,target_drop_ratio=.30,seed=42)
    atten,kept=inject_lidar_attenuation_and_dropout(pts,params)
    scaled=pts.copy(); scaled[:,:3]*=1.1
    yy,xx=np.mgrid[:200,:300]
    pattern=((xx//25+yy//25)%2*150+40).astype(np.uint8)
    pattern[65:135,110:190]=230
    dark=inject_visual_exposure_drop(pattern,gain_g=.2,seed=42)
    fig=plt.figure(figsize=(16,11)); title(fig,'06','故障改变的是哪些观测？','合成房间与标定图案；新故障直接调用本仓库注入器，尺度变化用作旧项目机制对照')
    clouds=[pts,scaled,occ,atten]
    heads=['A  正常合成点云','B  距离 × 1.10（旧项目）','C  扇区近场替换（新）','D  衰减 + 丢点 + 测距噪声（新）']
    for i,p in enumerate(clouds):
        ax=fig.add_axes([.035+(i%3)*.32,.51 if i<3 else .13,.285,.32],projection='3d')
        ax.scatter(p[:,0],p[:,1],p[:,2],c=p[:,2],vmin=-1.2,vmax=3.4,cmap='viridis',s=1.8,alpha=.8,rasterized=True)
        ax.set(xlim=(-7,7),ylim=(-5,5),zlim=(-1.5,3.5),xlabel='x / m',ylabel='y / m',zlabel='z / m')
        ax.view_init(elev=24,azim=-57); ax.set_box_aspect((14,10,5))
        ax.set_title(heads[i],size=12,loc='left',pad=10)
        ax.tick_params(labelsize=8)
    for i,img in enumerate([pattern,dark]):
        ax=fig.add_axes([.355+i*.32,.13,.285,.30]);ax.imshow(img,cmap='gray',vmin=0,vmax=255,interpolation='nearest')
        ax.set_title('E  正常合成图案' if i==0 else 'F  亮度 × 0.20 + 噪声（新）',size=12,loc='left')
        ax.set_xticks([]);ax.set_yticks([])
    foot(fig,f'点云四图使用相同视角、坐标范围和高度色标（−1.2 至 3.4 m）；近场替换 {mask.sum()}/{len(mask)} 点，衰减后保留 {kept.sum()}/{len(kept)} 点。\n这些是可控扰动模型，尚不等同真实雨雾、半透明塑料袋或相机曝光过程；此图不展示恢复效果。')
    (OUT/'fault_demo_parameters.json').write_text(json.dumps(dict(seed=42,synthetic=True,n_original=len(pts),
        occluded=int(mask.sum()),kept=int(kept.sum()),params=params.__dict__,range_scale=1.1,image_gain=.2),indent=2),encoding='utf-8')
    save(fig,'06_fault_mechanisms','SYNTHETIC_DEMONSTRATION',['slam_recovery/experiments/injection/injectors.py'],
        'Deterministic synthetic inputs show distinct measurement changes; neither real sensor validation nor recovery demonstration.')

def visual_transfer():
    s1='slam_recovery/experiments/manifests/e3_orbslam3_second_host_benchmark.json'
    s2='slam_recovery/experiments/manifests/e3_orbslam3_room_dark_01_benchmark.json'
    hall=json.loads((ROOT/s1).read_text())['metrics']['E3_Degradation_and_Recovery']
    dark=json.loads((ROOT/s2).read_text())['metrics']
    keys=['B0_Controlled_SingleMap','B2_Native_ORBSLAM3_Atlas','B6_Ours_GrayBox_LiDAR_Aux_Repair']
    groups=[(hall['severe_gain_0.05'],['window_118_152s_rmse_m']*3,'hall_01 重暗\n118–152 s 窗口 RMSE',s1),
        (hall['severe_gain_0.05'],['ate_rmse_m']*3,'hall_01 重暗\n全局 ATE',s1),
        (hall['moderate_gain_0.20'],['ate_rmse_m']*3,'hall_01 中暗\n全局 ATE',s1),
        (dark,['full_sequence_hold_ate_rmse_m','all_submaps_ate_rmse_m','ate_rmse_m'],
         'room_dark_01 自然暗光\n各方案原评测口径',s2)]
    fig=plt.figure(figsize=(16,8.5));title(fig,'07','视觉辅助恢复，数值和条件分开读','重画原 Fig. 5 数值部分；转录 manifest，保留 Atlas 劣化及不同比较分母')
    for j,(group,metrics,head,source) in enumerate(groups):
        ax=fig.add_axes([.06+j*.238,.28,.195,.50])
        vals=[group[k][m] for k,m in zip(keys,metrics)]
        bars=ax.bar(range(3),vals,width=.6,color=[BLUE,TEAL,'white'],edgecolor=[BLUE,TEAL,PURPLE],linewidth=1.6)
        bars[2].set_hatch('///')
        for i,(v,k,m) in enumerate(zip(vals,keys,metrics)):
            ax.text(i,v+.02*max(vals),f'{v:.4f}',ha='center',size=10)
            TABLE.append(dict(figure='07',group=head.replace('\n',' / '),variant=k,metric=m,value=v,source=source,
                              evidence='OFFLINE_CONSTRUCT + LiDAR auxiliary' if i==2 else 'repository host run'))
        ax.set(ylim=(0,max(vals)*1.27),xticks=range(3),xticklabels=['B0\n单图','B2\nAtlas','B6\n离线+LiDAR'])
        ax.set_title(head,size=11.5,loc='left',pad=16);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
        if j==0:ax.set_ylabel('仓库报告误差 / m（各面板独立纵轴）')
        for sp in ['top','right']:ax.spines[sp].set_visible(False)
    foot(fig,'B6 使用健康 LiDAR 辅助信息，属于离线构造，不能只与纯视觉比较后声称算法独立收益。\n自然暗光 B0 为全段零阶保持评测，B2 为各子图输出，B6 为补全轨迹；输出存在不等于原视觉成功跟踪。\n本轮未加载原始 GT 重算指标；原轨迹图需要补齐 GT、帧关系和相同评测端点后才能重新生成。')
    save(fig,'07_visual_transfer','REPOSITORY_REPORTED',[s1,s2],
         'Four reported evaluation groups; B6 offline auxiliary construction hatched; coverage/alignment caveats retained.')

def main():
    architecture_only=sys.argv[1:]==['--architecture-only']
    previous=json.loads((OUT/'manifest.json').read_text(encoding='utf-8')) if architecture_only else None
    for fn in ([architecture] if architecture_only else [architecture,gate,timeline,ablation,evidence,faults,visual_transfer]): fn()
    if architecture_only:
        MANIFEST.extend(f for f in previous['figures'] if f['name']!='01_architecture')
        with (OUT/'plotted_values.csv').open(encoding='utf-8-sig',newline='') as f:
            TABLE.extend(csv.DictReader(f))
    with (OUT/'plotted_values.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['figure','group','variant','metric','value','source','evidence']);w.writeheader();w.writerows(TABLE)
    report=dict(reviewed_commit='4b140b949d217de56aaf992f6684e23ad2355a30',
        python=platform.python_version(),numpy=np.__version__,matplotlib=matplotlib.__version__,font=FAMILY,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        source_hash_policy='SHA256 of source text with CRLF normalized to LF; output hashes use exact bytes.',
        transformations='No original metrics changed; figure 04/07 transcribe manifests; 06 deterministic synthetic inputs; others code/schematic.',
        figures=MANIFEST)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    thumbs=[]
    for m in MANIFEST:
        p=OUT/(m['name']+'.png');im=Image.open(p).convert('RGB');im.thumbnail((800,560));thumbs.append(im)
    sheet=Image.new('RGB',(1600,4*600),'#e8edf2')
    draw=ImageDraw.Draw(sheet)
    for i,im in enumerate(thumbs):
        x=(i%2)*800;y=(i//2)*600;sheet.paste(im,(x,y+20));draw.text((x+10,y+2),MANIFEST[i]['name'],fill='black')
    sheet.save(OUT/'contact_sheet.png')
    print(json.dumps({'generated_figures':len(MANIFEST),'formats':['svg','pdf','png'],'table_rows':len(TABLE),'out':str(OUT)},ensure_ascii=False))

if __name__=='__main__':main()
