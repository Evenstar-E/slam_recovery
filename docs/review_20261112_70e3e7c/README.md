# 70e3e7c审阅：受控实际修复接回后E2已执行，可信回退与成功依赖仍未闭合

- 读者：用户、开发S1/S2/S3与独立复核者。
- 目标 `70e3e7cab942839e88727579787c7210012ef5f9`，比较已验 `c416a68d736c3fb9eee3bc0cfecdb23d586aba34`；跳过已核Auto-Review和旧merge。AGENTS/评分表/REVIEW§10未变内容复用；三Cron实际repair-f3持有、无旧owner双写，按用户忽略stop.md。私人handoff保护，不merge main/改算法/代ROS或宿主/调参。
- 首次该受控链实际执行已在本轮核到原件后**立即单独向用户汇报**，未等两小时/日报。以下同时保留未通过项，不把“执行过一遍”写成“有效恢复全部验收成功”。

## 1. 主线已真实推进：同一实例实际修复重放→接回→E2拒绝→尾段

[reader](check_archive.py)/[原件核验](archive_checks.json)：本轮changed清单40/40 SHA一致。两run实际driver都为 **e39b2b8/0a38e952…**；目标main driver c33c0094不同，差异为随后合入的诊断reference/prediction/boundary字段，不能把旧运行冒称全部最新代码实测。host实际库receipt `9e7d8cdf…` 与v5构建声明一致；host.log/完整部署patch/运行命令绑定接受，本机未读bag/binary实体或重新构建宿主。

| 项 | 单事件验证074154Z_215075 | 两事件运行074744Z_219478 |
|---|---|---|
| 实际重放 | 454group=124窗口+330suffix，末1627785291358868361 | 497group=124窗口+373suffix，末1627785292825729847 |
| 修复应用 | 23received/applied、leftover0；bias+.45/施加−.45 | 23received/applied、leftover0；bias+.40/施加−.40 |
| 内部地图 | 20625vox/380221点 | 20838vox/379892点 |
| set_state | 真正未发送，meta suffix330/skip | 真正未发送，meta suffix373/skip |
| reprocess→resume ACK位置 | 差 **0.0422514m（4.225cm）**，报告3.6cm不准确 | XYZ均5.167277/6.898875/.217473，记录值相同 |
| E2 | NOT_EXECUTED（只一事件） | 两候选，E1部分接纳23，E2拒绝40候选；restore/resume真实执行 |
| 终态及尾段 | HEALTHY/waitclose/rearm | HEALTHY/open=false；E2关闭后17paired，末1627785320909073830，尾1.725149155s |

此前“后缀重放完仍灌旧候选尾pose”的已证正常断点在两次**成功非零suffix ACK范围**解除，不继续把旧3.904m回拨当本run发生。v5 ACK携带suffix、driver不再发set_state，host重放/内部地图与接回原件可核。ACK XYZ相同/接近不是GT质量或全部velocity/bias/cache等价证明；不用逐位checkpoint要求挡探索，也不靠小位置差升完整state/map验收。

两事件运行：E1 trigger1627785276215170145，decision1627785280481083632；E1原生重放及后缀追赶→resume后同一host继续输入。E2 trigger1627785308048271418，decision1627785312254862785，Mode3拒绝信息增益（before22.064/after18.216未过旧2×门）；Wilson通过不改变最终拒绝。E2 hold→restore→waitclose/rearm→resume，并有尾17paired。close1与trigger2**严格之间185帧**，报告186含边界需注明；trigger2含端点到末122。固定输入/原件可复核，不混消息/group/paired分母。

这是首次本会话核到**实际测量修复应用后的同实例受控E2流程执行**，不是旧raw-replay024337Z双事件替代品。报告执行事实必须保留，不再说测量修复后E2完全未跑。

## 2. 当前首个真实不通过项：E2检查点晚于可信隔离边界

E2 quarantine_start=1627785304048271418；trigger=1627785308048271418。实际restore ACK用cp1627785309656085248/frame863，map31773vox/680433点：

- 晚于触发 **1.607813830s**；
- 晚于隔离起点 **5.607813830s**。

host.log restore #2：live32084/690927→checkpoint31773/680433。确实执行了回退，但不是回退到隔离起点之前的可信状态。报告“滚动checkpoint是声明边界不是失败/未观察异常”不能解除这个A4/A9/B2缺口；S1§99随后主动承认晚检查点，接受其如实负结果，须同步限定S2报告。

E2本次**未再注入损坏**，而是第二脚本触发下的拒绝分支。它支持后继流程/接回能力，不能证明第二个真实故障被检测或跨E1修复撤销完整。E2不是跨越首次修复的迟到onset，A9跨修复贡献撤销尚未实跑。迟snapshot的发出/应用时间差是开发解释；已核的是实际cp戳晚，不能仅以发送时点在trigger前证明可信。

最低S1/S2复用现checkpoint，选择实际应用时刻不晚于目标可信隔离边界的合法历史状态，并保该点之后的输入归宿/按序重处理；若历史不可得，显式拒绝不支持回溯，不用段内cp给OK restore背书。不是要求预知在线异常，也不是简单为每个未来脚本戳预置snapshot就能证明更早quarantine_start安全；受控首trigger预置保证与在线/后继历史保证分开。

## 3. 新collect分支仍会在未知/失败时发送旧set_state（本机正常控制确认）

code-review low指出[recovery_node.py:1856](../../slam_recovery/ros/recovery_node.py#L1856)附近新路径：collect缺失/ack_timeout/不带suffix时，suffix=None落入`elif ep.frames`，仍写candidate尾。既不检查ack ok，也未要求ack command/本次reprocess身份明确。开发§97“ack缺失/无字段同样不盲写”与源码不符。

实际target `decide`控制只模拟准入及CP回应，复用真实流程：
- 正例OK reprocess suffix373：calls reprocess→collect，skip记录，**没有set_state**；
- collect None：suffix null、accepted记录仍true，calls reprocess→collect→**set_state**；
- ack_timeout/okFalse：同样发**set_state**；
- OK suffix0：保旧写回行为，声明旧范围，不能证明该pose等完整native状态。

这是普通回执超时/信息不足下的具体成功依赖反例，不人为异常矩阵；本次归档两run均正常收到suffix，不声称它们实际出现该失败。最低UNKNOWN/失败/错命令不推进依赖写回与成功公开，只有实际本次reprocess成功和明确边界才推进；复用现事件/字段，不新RPC/阈值/fallback框架。完整candidate与修复测量物理一致准入、manager提前commit/native失败公开、baseline None→0旧范围未变不重测；跳过灌pose解除宿主状态覆盖，不自动使原坏云准入等价新修复测量准入。

## 4. 修复、自动检测、人口与质量边界

两run都detection off、icp_reregistration、margin4s、wait2s、E1+0.5m注入6s；E2无注入。relay598帧中**59shift**（报告60是名义数）、只23修复发布，36shift未发表修复。捕获后缀仍原始测量，可能含剩余注入云；不称全损坏人口已修复。23/.40等估计产物方向及应用接受，收益/正常几何损失/轨迹质量UNKNOWN，不凭地图点数或HEALTHY证明去偏有效。

二事件497group包括249LIO（202有点/47空）和248VIO，非497个有点scan。paired544对819pose/598scan，275/54未配对；node wall102.346s、peakRSS884752KB是记录值不是整宿主预算。两wait_limit_closed都ABORTED rearm，unresolved分别106/143，最终HEALTHY不抹未解决人口。

单事件native1超时保留；二事件0ack_timeout但1snapshot superseded，显式restore1不含E1reprocess内部restore（host累计2）；数量不混。build target laser_mapping Built而整体catkin_make仍vikit CXXABI链接失败，本机不称全构建/宿主独立复现PASS。

## 5. 可并行诊断元数据局部交付，不重开诊断实验

最新main新增reference cache_key/refresh_ns/点数/sha，prediction mode/basis stamps/velocity/horizon/T，availability状态变化边界保全样本；源控制接受字段与边界原样保存。预测算法仍one-pose last/no horizon上限，未新阈值。**无新诊断on归档使用这些新字段**（两native run driver是e39且availability off），实现不冒实跑原因归因。

reference hash由float64计算参考cast到float32后hash，只证明声明表示的缓存身份，不是实际float64字节等价或完整参考几何复算；未保存参考坐标/prev_scan来源/原raw row mapping等缺项保留。不要求为字段重启diagnostic run；开发继续pause，仅DEVELOPER_REPORTED非本机会话新用户命令/新增模型选择授权。S3回既定门A/B/C研究、旧参数停。

## 6. 本机命令、自检与下一唯一主线

- archive：`C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_70e3e7c/check_archive.py` exit0，40/40本轮原件、两实际版本/库声明、host重放/apply/命令与E2晚cp/17尾帧核。[结果](archive_checks.json)。首reader假设两run匹配最新driver而assert失败exit1，核e39实际SHA后更正版本绑定，不报真实source错配。
- source：`C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_70e3e7c/run_checks.py` exit0，全部package从target Git bytes内存加载；正例skip、None/FAIL反例及元数据/200边界样本控制。[结果](local_checks.json)。新repair_sync测试导pytest辅助未跑，不装/shim；非全suite/native。code-review候选经actual方法反例确认，不直接拿技能建议当归档故障。

**主线**：已执行一次受控测量修复→原生接回→E2/尾段；下一只收口可信后继checkpoint/失败或UNKNOWN依赖和物理一致候选，交合法历史恢复→完整input归宿→后继拒绝或修复/尾段，或明确不支持范围。S1共享集成与真实成功公开，S2宿主合法cp/有限同实例交付；不要无限单事件、参数或诊断实验代E2正确性。

**必要保障**：E2晚checkpoint和新失败collect写回是具体正常断点；复用当前已验全后缀/成功skip接口，不重造宿主。质量评测可并行按完整预声明人口，未知标UNKNOWN不调冻结门。**延期**：数字、旧因果措辞/注入59vs60集中随后继更正；不扩大防御模型/阈值/单测矩阵。

开发逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令/原件/下一动作：source/input/library实际版本、可信cp应用边界、完整修复/后缀人口、applied/catch-up与失败UNKNOWN依赖、接回/E2/尾段、独立质量/成本/未测；未实施未运行明确NOT_IMPLEMENTED/NOT_EXECUTED。A5/A6/A10受控修复/后继流程局部推进，A4/A8/A9/B2及A3/B3/B4/B11完整科学链未闭合，不全表升分。已即时报告用户执行里程碑；沿白名单独立review SSH提交推送，补此前DNS失败012899f，不合main/改历史/冻结门/private，发布不等开发实际接收新意见。
