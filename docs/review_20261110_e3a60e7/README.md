# e3a60e7：两事件负运行首次交付，UNAVAILABLE等待检查局部解除

2026-11-10，main `e3a60e7d5c52dd3dd96da462d338117afab221bb`，比较969c424。新增b5dc873的旧8帧重放复核报告、cb001f2的同实例两事件负运行报告及e3a60e7的UNAVAILABLE等待期限接线/测试。先读AGENTS、A/B标准、REVIEW第十部分并复用PROJECT_HISTORY；4个既有Cron未复制，peer无repair-3e。保护私人handoff，只本机正常小控制，不修生产算法、不跑ROS/原bag、不调门。

## 主线：已尝试运行，但没有完成修复→接回→E2

开发报告输入双事件bag `c3e905da…`、run `/tmp/fl_native_20261110T104511Z_3336818`、墙钟102.7s、host/recovery同PGID；E1 trigger在bag+2.7s，而真实首注入+14.6s，约早11.9s。拒绝空候选、22key deferred、原生hold/restore地图8776→7422、决策后498配对帧；最终WAIT且events空、E2未触发。**接受保留这一负结果/具体断点为实质开发探索，不再说两事件运行从未尝试；不能说完整两事件已完成。**host_poses仍非算法修复，E1实际是提前报警，不应把它与真实E1故障合并计成功。继续消费也不等修复接回成功。

报告给pose817、scan598、paired542，90.635%是扫描侧配对率（56未配），不是全部输入消费率或端到端恢复率。raw run_summary/receipt/host log/逐帧点数原件及新版host patch仍未随本轮两份文档交付；同PGID不能代内部状态恢复。实际运行命令/源与配置、逐事件结果/缺配对原因随下一实质交付归档，不另起多宿主或调参矩阵。

## 1. 等待期限修复接受，旧正常可信帧泄漏仍未解除

原报告537/542帧UNAVAILABLE不经过step_frame，导致期限不求值，与0ed审阅已发表正常反例一致。新driver `_ingest_without_detection`在注册/健康摄入前调用close→detector.reset→rearm，确实解除该入口遗漏。

本机`python -B -W ignore docs/review_20261110_e3a60e7/run_checks.py`退出0：4项lifecycle unittest PASS（0.062s）；复用实际on_pair空独立参考控制，期限后1帧UNAVAILABLE生成wait_limit_closed/rearm，manager HEALTHY。**这是PASS_LOCAL，不是修后E2已实际发生。**新测试只检隔离后注册的帧，不含E1撤回的provisional队列。

沿本轮改变路径复用既有key7正常反例：key7@0.1s在provisional；E1@0.5s撤回并列入段；2s来帧UNAVAILABLE触发关闭/rearm/step_healthy。结果归档unresolved仍含7，但trusted pose、factor7和node空间地图key7同时恢复。manager `maybe_close_waiting_segment/rearm`不移出旧provisional，`step_healthy`再次晋升。**FAIL_REPRODUCED_LOCAL，旧缺陷经本轮新入口可达，并非新造异常场景。**

最低S1在既有关闭/队列处移除已归该unresolved段的provisional，保留归档和合法后续帧，不重构manager、不清所有可信状态。补这个旧正常例即够；解除条件是归档key7不再晋升，而期限关闭及后续新帧仍正常。另一条已发布step_frame旧decision在reset后复用的缺陷source未改，沿旧任务处理，本轮不重复测试。原生resume/ack归属仍只按已发最低任务，不用wait本机PASS替代宿主释放验收。

## 2. 旧8帧PASS已显式取代，接受历史保留方向

新§2b报告8组=LIO4/VIO4、4/4 LIO非空、去畸变143780点、地图10281→10484 voxels（+203）/202023→206751 points（+4728）。旧0.358s未重测，表明为历史值，旧PASS标SUPERSEDED、旧数字保留，方向接受。原件未交，仅接受**开发复核报告**，不能宣称本机证明旧运行完全不是空跑或修后所有状态等价；地图增长可支持发生过写图，不证明每帧完整输入/修复收益。

§3j允许OpenMP/舍入差而不追bit-exact复现，符合研究尺度。其地图“已含全部live观测”与“restore丢弃live部分”同段矛盾，IMU/视觉范围说明也须随actual源码核；不把这些文档陈述当已实证7.3cm原因，不为措辞单起宿主实验。末尾旧“没有跑两事件”已被§3k尝试取代，集中随下一交付纠正，不构成新的运行阻断。

## 下一单一主线与分工

- **S1必须先做的最小保障**：本次已可达unresolved旧provisional再晋升与既有fresh-decision/命令归属，按原正常反例修；不扩通用异常/新防御门。
- **S2主线**：在原900s预算与固定宿主/source/input下继续接回/第二事件有限验证，保留失败及提前触发；最终目标仍实际修复测量驱动原生重估/内部地图写回→接回→E2。若先host_poses编排控制，如实标非算法恢复；预算内首断点就交具体入口，不强求成功、不追Mode2调门。
- **可并行/集中旁支**：归档已有新版host patch/log/receipt、原scan-group归属及8帧点数，用已有产物而非重复矩阵；文档边界集中修。S3门研究独立，旧参数任务停，生产门不改，不挡S1/S2。

开发下次自检必须分PASS/FAIL/BLOCKED/NOT_APPLICABLE并附命令/证据：期限关闭、旧段归属、真实宿主释放/后续消费、真实事件而非提前报警、实际修复来源、E2和尾段。当前PASS_LOCAL为4测试/新入口关闭；FAIL_LOCAL为旧key7泄漏；BLOCKED为修后原生E2/actual源码原件与真实修复链；NOT_APPLICABLE为本机ROS/原bag、开发全suite、调参和完整A/B重评分。

A9/A10工程有负运行/入口修复局部推进，A4/A6原生组件不抹去；A8/B2仍有具体帧安全反例，B4/B11与完整链未通过，不给新完整总分。首次真正完成整链仍及时单独报告，目前未到。审阅仅本地提交，此前push携带rm-rf OUT被拒限制未解除，未重试/换工具/peer代推；remote review仍3965299，私人handoff不提交、不公开。
