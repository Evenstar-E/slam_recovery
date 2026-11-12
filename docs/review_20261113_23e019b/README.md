# 23e019b增量审阅：同行位姿准备、实际块header缺口与四宿主限制性交接

面向：开发S1/S2/S3与独立复核者。固定2026-11-13 01:09:27 UTC+8 fetch主线 `23e019bf7f9ac4bab71db9e50a009db704ffb952`，比较22d7933；宿主v11归档online-v2@c5bc057，新增长run归档growth-run@a812302。最初fetch超120s转后台，同一命令完成exit0后读取，不重复启动或以缓存冒最新。跳过Auto-Review/已验/纯合入，AGENTS新限制条目与HOST_VALIDATION_ORDER_20261113已读、A/B标准/REVIEW§10及当前历史已核。四Cron仍repair-f3单owner，其他本机session waiting/idle，不重建/双写；忽略stop.md、直接用户暂停优先。只读原件和有限源码控制，不算法修改、ROS/bag/构建/新安装/调参，不合main/改历史门、保私人handoff。

## 1. 已完成的消费者与旧原件复核

| 检查项 | 状态、证据种类 | 接受范围与影响 |
|---|---|---|
| v11同行pre/post数学路径 | PASS_LOCAL／PASS_SOURCE | 具名107列普通控制可解析pre/post；e_i_from_poses复用Rz(.2)/t(.1)得到rho(.0996664442,−.01,0)，不依赖vec反推的源码分支已存在。真实producer解析与物理资格另列，不把helper通过当整链 |
| 真实pose7/pre_pose7块header消费 | FAIL_REPRODUCED_LOCAL | 主会话两个已读reader控制仍0rows/malformed107；把两块名按token计宽会接受93/95，实际107。具名自测通过不能解除已声明producer接口不一致 |
| 旧v7排序索引错配 | FAIL_REPRODUCED_EXISTING_ARCHIVE | 原115734档504诊断行中92分数变化；现main排序索引读m2原数组，中位70.313396→正确原行查找72.293876，主会话actual源码执行复算与Codex参考相容 |
| 历史数学缺陷与资格 | 已解SE3数学、总体I仍INCOMPLETE/UNKNOWN | 不重开已验Jinv工具；旧机械scan成员/vec阶段/真实校准标签缺项未补，不把重算诊断当检测成绩 |

[主会话有限reader](run_checks.py)/[结果](local_checks.json)，[两消费者块表头控制](consumer_checks.py)/[结果](consumer_checks.json)均实际exit0，NumPy只用已存在的明确site-packages；不执行归档CLI/自测临时文件或宿主。exit0是有限检查及反例成立，不目标PASS。原v7输入trace/解压availability SHA绑定旧档，lookup仍保持旧2µs候选/人口，仅校正行索引，不由此宣全物理关联已证。

## 2. 最小旧数值解除，不需要新FAST-LIVO2运行

`23e019b:t2_run.py` 中pose_rows排序后group_idx是排序索引，随后仍用 `m2[j,4:8]` 原数组读旋转。重放让时间不是全局单调，排序index不等原数组index；原件复核504行中92受影响，与新Codex参考结果一致。S1已登记该缺陷，但本目标没有修正源码或重算原件。

**最低S3/S1**沿现pose_rows保存的原行读取对应四元数（或保原行索引），用已有归档重算并保修前/后；只复用此正常原件反例，不新增宿主run/改门/扩大pose矩阵。数值改善/变差不影响缺陷成立，修后仍属HEURISTIC和诊断，不升级成合格I。旧504/全UNKNOWN完整人口保留。

当前107块header问题也是已有产物的只读消费口径：pose7、pre_pose7各7标量，而parser用tail_names两个token计为2。最低对这份明确块布局一致解释并读十四值，不能只改测试header或硬放宽长度后丢pre/post。不新发FAST-LIVO2导出/构建/适配任务，既有数据的读取问题与新宿主验证分开。

## 3. 新增长归档核验：真实pre/post已到，晚回退与零修复负结果保留

固定 `a812302e3a9acd17b1e6f318d332b88563910069` 的run `fl_native_20261112T165438Z_669633`；v11生产源码固定 `c5bc05763b553ebc7d5adc585ba8e84013e9fb6c`，growth树带v12，不能把v12作为实际v11源码。独立只读核验已完成，主会话已读全部自写脚本与JSON，收录[archive_reader.py](archive_reader.py)/[archive_checks.json](archive_checks.json)。实际执行为Python -I标准库fixed Git blobs，不运行归档CLI/宿主；原结果保留，不为日报或审阅重跑同run。

可复核命令（输出到新路径，不覆盖原结果）：

```text
C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_23e019b/archive_reader.py --repo D:/REPAIR/slam_recovery_upstream --mode audit --out <新结果路径>
```

| 检查项 | 状态／原件 | 范围、影响及最低下一动作 |
|---|---|---|
| 运行来源 | PASS_SOURCE/ARCHIVE限定范围 | receipt driver SHA c5efdd73与fixed growth节点源码一致；library声明81b35f92、binary声明完整6dd71953、bag声明c3e905da；launch有K1/trace/on/无scripted。没有远端binary/bag实体独立重算，不报独立重建或整个环境绑定 |
| 五普通manifest条目 | PASS，self项FAIL | receipt/summary/wiring/launch/availability SHA一致；清单自hash失配、host_logs未列，但reader另算所有host log SHA。最低随归档集中完善，不使全部真实trace无效、不称全清单PASS |
| 真实trace形状及配对 | PASS_ARCHIVE局部 | 792行全107列，idx0–791连续、792唯一group、phase全0；725 has_out、67无后验，789个不同abs_ns。同行pre/post原件可读，源handleLIO更新前捕pre/后取post；不继续说没有真实pre位姿 |
| 同行post有效性与人口 | 限定PASS，整体I未评价 | 67 has_out0虽有pose字段但Ppost全0，必须保无有效后验；63 pre位置非零、4初始零，不笼统称全部非零。725 has_out中37 eff0；完成函数不等有测量约束，不能直接把725当合格检测人口 |
| mat_lio独立交叉核 | v11 out索引FAIL，v12修正PASS_SOURCE | pre793行中792与trace同key匹配；out726行须按标签idx+1配trace725，不能按文件行号+1。v12改rows−1→rows及6位精度→10位，其他四源码同；未交v12新run，不冒实跑验证 |
| 消费者实际header | FAIL_CURRENT_SOURCE | run/v11/v12均原样pose7 pre_pose7块名；主会话两reader正常107行控制均拒绝，具名selftest不解除actual布局缺口 |
| online实际恢复 | FAIL时间范围，修复/重放NOT_EXECUTED | 两restore cp晚qstart2.632151872/2.500209589s；0 accepted/2 rejected/0 commit，repair/replay/set_state计数均0、reprocess0。21 snapshot timeout不当取消；HEALTHY/openfalse但unresolved_segments2、两wait关闭保120/100未决帧，不计成功恢复 |
| 新运行覆盖/尾行 | PARTIAL | trace支持52.83821177s，sidecar配对482=129A353U、pose首末支持52.579876184s；mat_lio末pre/post及绝对pose已有一帧输出但缺trace行。未来/有输出子集不能冒完整60s人口；末行缺项保UNKNOWN |
| 资源与增长/根因 | 归档有限读数；精确峰/根因UNKNOWN | summary wall111.644s、peak1024664KB为recovery PID670715范围，不host峰/全天预算；增长率详下，不从日志判独立质量或唯一原因 |

本run trace SHA `b14d4f57e4c488f64365e5fa48c72c32d946ef51d00371a4f21456ac87ccd736`；主会话consumer_checks使用的块header与实际档/v11/v12完全相同。因此已有真实取证资产足够解释消费缺口，**不需要为parser或mat_out索引另跑新FAST-LIVO2实验**。若只读既有材料修正消费，直接用同行pre/post计算单位权残差、vec仅对照；state cov仍旋转body右扰动＋平移world加性混合坐标，没有差值相关性模型，继续NOT_AVAILABLE_FOR_E_I。真实同更新来源局部解除不等校准/标签/完整scan成员、ALI性能或恢复净收益解除。

### 增长率：晚段大净增长可核，精确峰时序与唯一机制不可核

可复算的是稀疏成功snapshot ACK：rel33.346623744→50.510500864s，voxels52,747→561,126，净增508,379，分母17.163877120传感器秒，约29,619.1 voxels/s；同区间wall35.482000113s则约14,327.8/s。两种速率不是同分母，稀疏观测含21次timeout，不能据此锁定真实峰值或增长起点。最后成功ACK到frame706/rel51.575036160s，576,707 voxels/3,944,635 points，之后仍timeout，没有终态host状态档，不能拿这条当最终地图。

COLLAB§159“前30s 0→9233/167k≈3k/55k每秒”数值实际匹配0→第三ACK、**3.061057280传感器秒**，不是30秒；13227 eff、722帧、最终593925/4.15M与301.6s峰42.9k/s没有本次可复算逐帧map序列/原增长脚本/共同时间原点，只保DEVELOPER_REPORTED，不能与本reader的统一rel触发4.595475213/17.002940433s硬对齐。最低补既有原run脚本/序列/原点（若确已保存），否则精确峰与对齐UNKNOWN，不为补因果新开run/ASan。

按本run trace rel<30s与≥30s、has_out人口分层，eff中位4061→1125.5、测量残差r_abs_mean中位0.0422→0.1100m，记录末位置约(−1195.76,727.07,−136.90)m，约1406m位置范数。它们支持观察到晚段匹配支持减少/条件残差升高及大净地图增长，**不独立证明GT漂移、不唯一排除内存问题或判定匹配退化根因**；无相应分母/控制，不能作论文性能或稳定性评分。r_*是最终迭代点面统计，不是pose创新协方差。

仅保原run负结果与来源边界：has_out0、eff0、末trace缺行、未配对输入及全部未决不可静默删去凑效能。reader提取量不使用算法新模型，也不重新授予后续FAST-LIVO2运行/构建许可。

## 4. 四宿主顺序：按限制性交接执行，不伪造用户认证或新增授权

最新main AGENTS/HOST_VALIDATION_ORDER及S1 COLLAB§160已把优先级收紧为MM-LINS、FAST-LIO2、LIO-SAM、ORB-SLAM3工程/论文需求验收在前，FAST-LIVO2新工作后置。本会话**尊重这份更限制性的项目交接，不委派新的FAST-LIVO2运行/构建/适配，也不恢复旧实验**；本次已完成原件只读核验不是新执行许可。

仓库引号中的“用户原话”在本会话仅能作为来源为Codex/S1的归档转述，不能自行认证其确为新直接用户消息、扩算力/安装/全部宿主大矩阵授权或宣称执行端已停止。本轮无新范围批准；S1的安排及停止声明与实际S2/S3回执仍须分开。四项“全需求先验收”不是四项已通过，不因无GT自行把需求删成NOT_APPLICABLE，适用性争议交实际用户决定。

复用本日已验四项边界，不重跑基线填表：MM-LINS/单独改版共享前端有原生休眠重建和尾段，但slam_recovery测量修复接线NOT_IMPLEMENTED；独立原版FAST-LIO2构建/验证不能由共享前端代替。LIO-SAM/ORB有真实失败尝试，不能把观察窗/反复建图当有效二故障恢复，原失败保留。此前FAST-LIVO2局部成果不抹去，但不能给四项A4/A6/A10/B4/B11代验。

**下一单一主线交付：在四项当前范围内，由S1绑定一个既有环境/真实最小接口的非FAST-LIVO2宿主，交实际测量修复→原生状态/地图重处理→接回真实输入及第二事件/尾段，或具体宿主文件/调用点首断点和最低解除。** 其他项必要适配并行，不用全表文字/算法防御设计替代首条实际链；选择先做一项不豁免其余项或放行FAST-LIVO2。公共已验数学/修复/通道组件可版本化复用，真实host执行/输入归宿/净收益及成本须对应宿主。

| 分类 | 责任、顺序与验收 |
|---|---|
| 主线 | S1唯一集成/指定实际host与接口，S2现环境native：输入修复/真实完整状态map→全部归宿/后继；不新开FAST-LIVO2。新非LIVO适配/执行的实际认领回执尚未交 |
| 必须先做 | 所选host当前实际输入、状态时间与恢复接口断点，列文件/函数和最小解除；不是为四项先造通用checkpoint或补全所有防御/单测 |
| 可并行 | S3旧原件索引修正、真实I/正常标签资格与只读shadow；已有增长档负结果与来源收口。只读允许不转成新hostrun许可，不重复抽象A/B/C |
| 集中延期 | FAST-LIVO2新增适配/构建/实验按新项目限制后置；一般根因/ASan/格式兼容/文案不成主线前置，旧sigma/κ/floor仍停门不降 |

后继逐项**PASS/FAIL/BLOCKED/NOT_APPLICABLE＋实际命令/输出原件＋影响/下一动作**，绑定owner/branch/HEAD/host/input/source/library/config、cp/所用状态时间/完整消息/修复对象/实际应用/全部pending与后继、独立评价/正常标签/UNKNOWN/失败和资源。NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE保留，不以平均分/test数/HEALTHY放行。15h08:53仍是如实结果报告，不因仓库转述新顺序冒称目标全通过、用户延期或全部远端停止。

A1/A11真实pre/post取证原件、A2/A12归档与A3/B3研究支持仅局部报范围；A4/A5/A6/A9/A10/B2/B4/B11不据日志/增长/旁支宣整链通过。四宿主全表未重评，不报新总分。本轮新真实档/正常缺陷与限制性交接构成增量，独立归档结果已合并，白名单现review分支中文SSH发布；不算法ROS/main历史/private/开发日报。
