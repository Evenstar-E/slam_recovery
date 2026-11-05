"""Editable vector architecture, visually informed by FAST-LIVO2's Framework.png.

All geometry is drawn from scratch. This is a code-level overview, not a claim
that the Python recovery layer is connected to the native estimator online.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon, Rectangle
from matplotlib.path import Path

INK = '#171717'
IMU = '#F8D8BB'
LIDAR = '#67C5E4'
AUX = '#F49A8D'
REPAIR = '#B4D9BE'
GATE = '#EBD496'
PURPLE = '#B8A6CF'
BLUE_LINE = '#009DC4'
CORAL_LINE = '#E77868'
PENDING = '#9D5422'


def draw():
    # Serif titles, compact rounded modules, neutral dashed groups and modality
    # colours follow the reference's visual grammar; no reference pixels reused.
    fig = plt.figure(figsize=(20, 7.7), facecolor='white')
    ax = fig.add_axes([.012, .092, .976, .83])
    ax.set(xlim=(0, 100), ylim=(0, 100))
    ax.axis('off')
    font = {'fontfamily': 'DejaVu Serif', 'color': INK}

    def text(x, y, s, size=13, bold=False, ha='center', color=INK, **kw):
        kw.setdefault('va', 'center')
        return ax.text(x, y, s, fontsize=size, fontweight='bold' if bold else 'normal',
                       ha=ha, fontfamily=font['fontfamily'], color=color,
                       linespacing=1.18, zorder=6, **kw)

    def group(x, y, w, h, label, subtitle=''):
        ax.add_patch(Rectangle((x, y), w, h, fc='#EEEEEE', ec=INK,
                               lw=1.35, ls=(0, (5, 4)), zorder=0))
        text(x+.8, y+h-2.5, label, 15.5, True, 'left', va='top')
        if subtitle:
            text(x+w-.7, y+h-2.5, subtitle, 9.3, False, 'right', va='top', color='#555555')

    def node(x, y, w, h, label, fill, sub='', size=14.5, dashed=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
            boxstyle='round,pad=0.03,rounding_size=1.2', fc=fill, ec=INK,
            lw=1.8, ls=(0, (4, 3)) if dashed else '-', zorder=3))
        text(x+w/2, y+h*(.66 if sub else .5), label, size, True)
        if sub:
            text(x+w/2, y+h*.23, sub, 10.0)

    def path(points, color=INK, dashed=False, width=2.0, end=True):
        codes=[Path.MOVETO]+[Path.LINETO]*(len(points)-1)
        p=Path(points,codes)
        ax.add_patch(FancyArrowPatch(path=p, arrowstyle='-|>' if end else '-',
            mutation_scale=15, lw=width, color=color,
            linestyle=(0,(4,3)) if dashed else '-', zorder=2,
            capstyle='round', joinstyle='round'))

    def label(x,y,s,color='#444444',size=10):
        text(x,y,s,size,color=color,bbox=dict(fc='white',ec='none',pad=.8))

    fig.text(.5,.972,'SLAM Recovery — System Overview',ha='center',va='top',
             fontsize=25,fontweight='bold',fontfamily=font['fontfamily'],color=INK)
    group(15.5,59,59.5,38,'Native LiDAR–Inertial Host','inherited MM-LINS')
    group(15.5,4,59.5,47,'Recovery Research Layer','Python / offline studies')
    group(79,4,20,93,'Maps & State')

    # Sensor streams and the actual native estimator, distinct from recovery.
    node(.7,79,11.3,13,'IMU',IMU, 'accel. / gyro',18)
    node(.7,62.8,11.3,13,'LiDAR',LIDAR,'raw scans',18)
    node(.7,22,11.3,16,'Auxiliary',AUX,'pose / image cues',14)
    text(6.35,18.1,'when available',9.7,color='#555555')
    node(18,79,16,11.8,'Forward\npropagation',IMU,size=14.2)
    node(18,63.3,16,12,'Deskew &\npreprocessing',LIDAR,size=14.2)
    node(39,63.3,16,12,'Point-to-plane\nresiduals',LIDAR,size=14.2)
    node(60,63.3,12,12,'Iterated\nstate update',LIDAR,size=14.0)
    path([(12,85.5),(18,85.5)],'#EAB589',width=2.8)
    path([(12,69.3),(18,69.3)],BLUE_LINE,width=2.8)
    path([(26,79),(26,75.3)],'#EAB589',width=2.8)
    path([(34,85),(66,85),(66,75.3)],'#EAB589',width=2.5)
    label(48,85,'predicted state & covariance','#946031',10.4)
    path([(34,69.3),(39,69.3)],BLUE_LINE,width=2.8)
    path([(55,69.3),(60,69.3)],BLUE_LINE,width=2.8)
    path([(72,69.3),(73.5,69.3),(73.5,89.7),(97,89.7),(97,82),(95.8,82)],BLUE_LINE,width=2.3)
    label(76,83,'append',BLUE_LINE,9.8)

    # Original vector drawing of structured point surfaces. It represents map
    # geometry, NOT a voxel-map implementation or an experimental point cloud.
    text(89,86.5,'Local point map',14.5,True)
    plane1=np.array([[81.8,76],[87.5,73.8],[87.5,82],[81.8,84.2]])
    plane2=np.array([[87.5,73.8],[95.8,78],[95.8,86.2],[87.5,82]])
    floor=np.array([[81.8,76],[87.5,73.8],[95.8,78],[90.1,80.2]])
    for plane,fc in [(plane2,'#EFAFA8'),(plane1,'#80CBE0'),(floor,'#ECD88E')]:
        ax.add_patch(Polygon(plane,fc=fc,ec='#484848',lw=1.1,alpha=.8,zorder=1))
        for t in [.25,.5,.75]:
            a=(1-t)*plane[0]+t*plane[1]; b=(1-t)*plane[3]+t*plane[2]
            ax.plot([a[0],b[0]],[a[1],b[1]],color='#777777',lw=.45,alpha=.6,zorder=1)
        for u,v in [(.15,.24),(.28,.66),(.53,.38),(.73,.77),(.86,.3)]:
            p=plane[0]*(1-u)*(1-v)+plane[1]*u*(1-v)+plane[2]*u*v+plane[3]*(1-u)*v
            ax.plot(p[0],p[1],'.',ms=3.8,color='#333333',zorder=2)
    text(89,88.8,'',10)
    path([(81.8,76),(77,76),(77,55),(47,55),(47,63.3)],BLUE_LINE,width=2.0)
    label(62,55,'retrieve local planes',BLUE_LINE,10.3)
    node(82,58.3,14,10.5,'SC-PGO',PURPLE,'loops / submaps',14.5)
    path([(89,73),(89,68.8)],'#725888',width=2)
    # A small node-and-loop graph replaces a vague "output" rectangle.
    pts=[(82.5,51.8),(85.2,49.9),(88,52.0),(90.4,50.5),(93.8,53.1),(96,50.3)]
    for a,b in zip(pts[:-1],pts[1:]):
        ax.plot([a[0],b[0]],[a[1],b[1]],color='#725888',lw=1.25,zorder=1)
    ax.plot([82.5,88,93.8],[51.8,55,53.1],color='#725888',lw=1,ls=':',zorder=1)
    for x,y in pts: ax.plot(x,y,'o',ms=5.3,mfc='white',mec='#725888',mew=1.1,zorder=2)
    path([(89,58.3),(89,54.5)],'#725888',width=1.4)

    # Every arrow in this region denotes a component-level dependency, not a
    # claim that one real-time native event loop already orchestrates them.
    node(18,28,12,12.8,'Health\ndetection',LIDAR,size=14.5)
    node(32.7,28,12,12.8,'Cause\ndiagnosis',GATE,size=14.5)
    node(47.4,28,12,12.8,'Candidate\nrepair',REPAIR,size=14.5)
    node(62.1,28,10.7,12.8,'Four-mode\ngate',GATE,size=13.5)
    path([(30,34.4),(32.7,34.4)])
    path([(44.7,34.4),(47.4,34.4)])
    path([(59.4,34.4),(62.1,34.4)])
    text(24,24.5,'NIS / CUSUM / spectra',9.0)
    text(38.7,24.5,'mechanism signatures',9.0)
    text(53.4,24.5,'filter / bridge / offset',9.0)
    text(67.5,24.5,'info / NIS / cov.',9.0)
    # Logs/adapters intentionally remain dashed at the native/research boundary.
    path([(60,63.3),(57.6,60.8),(14.2,60.8),(14.2,44.2),(24,44.2),(24,40.8)],
         '#626262',dashed=True,width=1.45)
    label(35,59.7,'state / residual / factor records',size=9.7)
    # Optional auxiliary observations connect to the research layer only.
    path([(12,30),(13.4,30),(13.4,52.3),(53.4,52.3),(53.4,40.8)],
         CORAL_LINE,dashed=True,width=2.0)
    label(32.5,52.3,'auxiliary observations (experiment dependent)',CORAL_LINE,9.6)

    node(18,8.2,26.7,11.2,'Quarantine & checkpoint',PURPLE,
         'provisional queue / pose snapshots',13.8)
    path([(18.3,28),(18.3,19.4)],'#725888',width=1.7)
    # Checkpoint + suspect segment is consumed by repair, separate from live map.
    path([(44.7,13.8),(59.1,13.8),(59.1,28)],'#725888',width=1.7)
    label(51.5,13.8,'segment', '#725888',9.2)
    node(62.1,8.2,10.7,10.8,'Wait /\narchive', '#DADADA',size=12.6)
    path([(72.6,28),(72.6,19)],'#666666',width=1.6)

    node(81,28,16,12.8,'Trusted poses',REPAIR,'Python dictionary',14.5)
    path([(72.8,34.4),(81,34.4)],'#4F8463',width=2.3)
    label(76.8,36.7,'accept', '#4F8463',10)
    # Do not silently draw an implemented feedback into native state/map.
    path([(89,40.8),(89,47.2)],PENDING,dashed=True,width=1.8)
    label(89,44.7,'native handoff: pending',PENDING,9.4)
    ax.add_patch(FancyBboxPatch((81,8.2),16,12.3,
        boxstyle='round,pad=.03,rounding_size=.8',fc='#FCF3E9',ec=PENDING,
        lw=1.1,ls=(0,(4,3)),zorder=3))
    text(89,16.4,'Not a full native transaction',10.1,True,color=PENDING)
    text(89,11.8,'state / covariance / map / factors',8.8,color=PENDING)

    fig.text(.021,.042,'Solid: module dependencies    Dashed grey/coral: logs or optional adapters    Dashed amber: unimplemented native handoff',
             fontsize=10.2,fontfamily=font['fontfamily'],color='#444444')
    fig.text(.021,.014,'Code-level overview of 4b140b9; geometric illustrations are schematic. Visual layout inspired by FAST-LIVO2, redrawn with original vectors.',
             fontsize=9.7,fontfamily=font['fontfamily'],color='#666666')
    return fig
