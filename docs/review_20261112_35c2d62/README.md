# 35c2d62增量核验：研究修正、拒绝范围声明与正常标签重大阻塞

面向：开发S1/S2/S3与独立复核者。固定目标 `35c2d62b6412d5b651ef6d211a5c8d16a77cc5f1`，比较已验 `e0d403b8d8ee621e8af95422debedf267aa24b84`；2026-11-12 19:05:52 UTC+8 fetch成功，前轮DNS失败不当远端停工。必读AGENTS/A-B标准/REVIEW§10未变复用；四Cron含08:53截止仍repair-f3单owner，无旧owner双写，不重建自动化。忽略stop.md，用户15小时/无Codex要求继续；私人handoff保护、不合main不算法/ROS/调参/改历史冻结门。

## 1. 实际增加与仍未闭合

本轮新增研究三项修正及更新原件、driver拒绝范围记录、中文正常参照/标签重大阻塞。**研究组件与证据边界有推进；没有新增可获取的真实I trace、自动检测效果或原生恢复运行。** 跳过febf68旧审阅/纯merge，不再执行旧全UNKNOWN分析或旧失败ACK控制。

[隔离reader](check_archive.py)/[结果](archive_checks.json)只读固定Git字节，不执行归档研究/host：

| 检查 | 独立结果与界限 |
|---|---|
| 五项manifest产物/ali源码SHA | PASS，5/5 bytes/SHA与code一致；更新B T0为40826B、T1为4797B，其他旧原件不变 |
| 旧输入/逐帧身份/I缺项 | PASS，原availability归档未变；A402/B544与shadow身份一致、I缺失、全UNKNOWN |
| 完整块人口 | PASS，A90；B120=119有行+1空块3255570637，NO_DATA/UNKNOWN/n_frames0；旧119不是最新完整块分母 |
| T1七/T2 prep十四保存自测 | 归档读数，不冒本机执行；研究修正的独立控制另列 |
| host trace v7 patch/启动probe原件 | 当前目标路径不存在，DEVELOPER_REPORTED，非可独立复现诊断 |
| 新真实I/自动链/效果风险 | NOT_EXECUTED/NOT_EVALUABLE，不以202 tests、三修正或阻塞登记当检测成功 |

## 2. 三处研究缺陷已在组件范围解除，不继续机械阻断

独立只读控制在固定Git目标读取已审函数/常量后内存编译，`python -I -B D:/REPAIR/.claude/ali_verify_35c2d62_20261112.py` exit0；使用已安装NumPy，未安装/改环境，不执行归档CLI/自测、ROS/host。脚本已读后保存本目录为[独立控制](ali_controls.py)，结果见[原始输出](ali_controls.json)。代理完成这一独立范围，主会话读完整控制脚本/输出；无再委派、不把保存自测当实际运行。其轻量T0重算已完成，不另重复。

| 已验问题 | 实际控制与关闭范围 |
|---|---|
| D1 SE3 Log平移，t2_input_check.py:127–140/160–163 | Rz(.2)+t(.1,0,0)实际rho(.09966644423259238,-.01,0)，匹配右切空间cov分数100.0499334，旧错误.05。有限普通角度/两种顺序/共同world重表达控制通过；是构造数值，不真实误分类 |
| D2 gap dwell，ali_h_v1.py:219–226/264–286 | 10/12无11的ALARM和I+T NORMAL现在均UNKNOWN；8/9疑似后NO_DATA10断dwell且11保last_suspect9，后12才重新持续SUSPECT。非空frame→补块→classify人口一致，A90/B120各字段及shadow重算同保存 |
| D3 READY切空间，t2_input_check.py:82–108 | 原left/world manifest现在INCOMPLETE，只有协方差与declarations匹配right/pre_body才READY，无cov保READY_UNIT_ONLY。低层s_i仍须caller给实际匹配P；真实validator→trace→评分caller未交，故只关闭准备资格漏洞，不宣真实P来源/实际转换已验证 |

B空块n_frames0不伪造新帧；I119 NOT_AVAILABLE+1 NO_DATA，不改旧逐帧544。UNKNOWN总时长/最长区间评价器仍未交，补块表不等时长指标完成。旧T0观察器I仍固定NOT_AVAILABLE，不能把合成I控制当宿主I已接入。

附带低优先级正常边界回归：`ali_h_v1.py:274`现在对`block_summary([])`调用min空集合抛ValueError，基线返回[]，独立控制已复现。仅当既有caller允许空批次/筛选段才需恢复原行为或明确非空前置；本次A/B非空不受影响、无真实trace空输入失败证据，不扩异常矩阵、不提升成主线阻断。

## 3. 拒绝范围声明接受；真实时间归宿仍不等字段记录

新增 `recovery_node.py:1870–1890` 只写meta，不改变restore/replay/resume控制。`STATE_AND_MAP_ROLLBACK_ONLY`、`NOT_REPLAYED`、`catch_up=NOT_IMPLEMENTED`诚实收窄主张，接受这个记录进展；不继续把没有明确说明当现状态。**A5/A10的完整历史追赶未实现，不因文字关闭。**

新增字段还有一个正常记录错配：`checkpoint_stamp_ns=trigger-margin`不是原生cp实际时刻。已验v6就在请求前最近已处理组取cp，E2实际restore ACK `stamp_ns=1627785302359221248`，请求隔离起点 `1627785302371636152`，相差12,414,904ns；自动rolling时两者也没有等值保证。无需新run就能核这个区别。

[最小源码控制](run_checks.py)/[结果](local_checks.json)：只编译已读目标拒绝else分支，构造正常trigger1000/margin20/有效restore ACK cp975，记录却cp980、interval[980,1500]。exit0是**FAIL_REPRODUCED_METADATA**，不是目标通过或实测宿主新丢输入。初执行目标新增测试导入pytest缺失exit1，测试NOT_EXECUTED_LOCAL；未安装/伪造依赖，改有限AST控制而非全库测试。

另 `CheckpointClient._send():881–888`明确先发送不等待应用，`restore()`返回该event；meta即时写`CONTINUES_FROM_RESTORED_STATE`不能独自证明restore/resume已成功。最低S1沿现event/ACK在汇总绑定实际`stamp_ns`与应用结果，请求/隔离起点另名保留，未回执或失败写UNKNOWN/未应用；实际消费末边界没有记录也UNKNOWN，不拿decision pose时间冒完整host消费边界。此为现字段来源收口可并行，不阻工程启动、不新增遥测框架、不为记录重跑；真正合法拒绝后input连续性沿旧最小主线实现/显式不支持，不无条件重放已拒污染。

## 4. 宿主诊断目前仍为开发报告，不能从首帧前崩溃排除新增代码

COLLAB§122/125报告v7库0308c216、v6 ca9126c4，启动probe v7四失败/v6偶发及teardown stack smash，S1另安排有限二分/ASan/探针。这些命令、patch、probe日志/receipt没有入本目标：`git ls-tree ... host_change_trace_cov`为空。不是把开发报告当虚假，而是**本机无法独立验收其率、诊断及成本**，root UNKNOWN。

“第一LIO前崩，所以与trace代码无关”不成立为源码排除：成员布局/构造/配置读取/依赖也在首帧前生效。v6也报失败说明可能非v7独有，不证明必定内存竞态、也不证明配置/插件路径已排除。最低S2上传已有v6/v7实际patch、库/环境/命令/启动与teardown原件及有限诊断结果；不先为审阅重复探针/重跑bag或扩大宿主矩阵。S1的approved记开发安排，不冒用户新预算/安装授权；本机不额外授权clean删除/安装/改宿主输出。现预算诊断继续，若实际必需超授权或已证不能继续，立即中文重大阻塞，不以22:00/08:53为已知重大阻塞延迟告知的理由。

## 5. 中文重大阻塞已在GitHub，待真实用户确认；两类缺项分开解除

`ALI-B2-NORMAL-LABELS-20261112-01`已随72284f7进入main，原[中文记录](https://github.com/Evenstar-E/slam_recovery/blob/35c2d62b6412d5b651ef6d211a5c8d16a77cc5f1/docs/ali_h_v1_research/重大阻塞记录.md)状态等待，用户确认原文为空；不替用户选A/B/C，不把S1批准当用户决定。

现402/544 receipt无注入、sigma .884可读；redo detection off/sigma .12可读，不能跨run借正常校准；B5/B7旧报告是其归档扫描范围的无逐候选独立标签，不外推成全项目从无注入标签。**当前交付没有独立确认的低支持正常校准及可用完整事件标签，性能不能评价**这一阻塞成立，必须保留。它不是已经证明ALI模型不可辨识/永久失败。

需最低明确两处，追加更正不覆盖历史/用户内容：

1. 记录§最低解除写“正常前缀或事件标签二选一”不足以解除完整评价。正常前缀用于条件校准，事件标签用于评价误报/漏检/延迟/错误NORMAL；**完整效果需要两类证据**，只补一类只解除对应部分，缺另一类仍NOT_EVALUABLE。NORMAL_CALIBRATION与EVALUATION_LABELS分别列状态、来源/时间/hash/独立确认方法及最低缺项。
2. 用户既有15h任务§2步骤4已允许“已有声明自注入可有限测试、标签仅离线”，不能把相同已授权范围重复等待用户授权。原记录B的新数据/新离线正常确认方法/新增预算仍需具体说明与用户确认，不能据此擅选B。真实待决是必要独立正常证据来源、确需增加的输入/成本或接受资格-only范围，不是重复批准现注入。C是待选，不自动把用户15h目标降级成只交UNKNOWN。

S3只暂停受无参照/标签阻塞的分类效果，仍可真实trace资格/完整NO_DATA-UNKNOWN时长；S2合法启动诊断/导出、S1原生归宿最小实现继续。记录“等待期间不新跑宿主”限定S3研究，不扩为停止S2现任务。A/B/C选项给用户，但当前本机未收到实际确认；可靠通道仍GitHub仓库中文确认commit，下轮fetch读，不冒监控Issue/评论。

## 6. 本轮主线/旁支与自检交付

**下一单一交付：有效真实I trace（身份、scan-group-phase与同物理时间/cov来源可核）及其支持范围同人口旧方法/ALI结果；缺正常/标签部分保NOT_EVALUABLE，用户解除后恢复完整效果并有证据再有限自动接线。** 不另造第二份方案或反复旧全UNKNOWN。

- S1共享集成：现拒绝范围诚实记录可复用，收口实际ACK/时间，不冒追赶成功；复用v6/suffix/skip/受控E2，原生必要归宿/成功依赖未关闭。
- S2工程：已有有限诊断/真实导出责任继续，上传现原件最小即可；不把source/插件/内存猜测当根因，不新clean-map/多宿主矩阵。
- S3研究：三普通问题修正核证据后关闭已解范围，正常校准和标签分别状态/等待用户选必要输入，完整人口资格与弃权可继续；不降阈值硬分类。
- S4现自动审阅/2h/日报/截止继续，1研究+2集成/noCodex，旧手调暂停；现场算法/host留开发，本机不代跑。

必须先做旁支仅当前执行启动、实际时间/cov/校准有效性；ACK汇总、保存patch来源可并行；不重审未变大库、扩单测/参数/故障矩阵或先完善生产框架。下一实交逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令/输出原件/影响/下一动作，NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE保留；全部paired/未配对/无行块/UNKNOWN时长、独立正常/事件标签/失败退出/资源与实际动作，不以测试总数替代。

A3/B3研究组件与资格边界增加，检测性能不通过；A5/A10范围声明增加但追赶未实现；A2/A6/A4无本轮新增可获取host运行，A8/A9/B2/B4/B11未闭合。只局部核，不给新全表总分或继承历史分。实质修正/新重大阻塞与实际记录反例按授权中文review白名单SSH推送，不触private/开发日报，不合main不改算法/历史/科学门。
