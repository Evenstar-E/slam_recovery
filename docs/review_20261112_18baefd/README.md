# 18baefd审阅：测量替换已实跑，偏差修复失败，第二事件未执行

- 面向用户、开发主会话S1、宿主执行S2及独立复核者。
- 目标 `18baefd89e70a65b1a493b0c1e532558b6bff6e0`；比较 `f48b23f66707e9491350c1c62972fbf542f94fa3`。12:45:50 SSH fetch成功，审阅工作树4201dbd，未merge目标。
- AGENTS、A/B标准及REVIEW§10已读；实际Cron三项均属repair-f3，无旧owner。20min用户配置及忽略stop.md的直接指令优先；旧参数继续暂停。私人未提交handoff不stage、不公开。

## 1. 主线有实证的部分推进，不是首次有效修复整链完成

新driver保留原scan stamp/完整消息，新增relay、修复publisher、接收屏障并执行了一次原生运行。旧“在线没有测量生产/应用、repair=0”不再适用于这次运行。

| 检查项 | 状态 | 证据与边界 |
|---|---|---|
| 声明损坏实际产生 | PASS（归档） | `fl_native_20261112T043602Z_79001`，relay598帧=60移位+538原样；body-z +0.5m，25发布stamp全部在移位集合 |
| 完整记录移位工具 | PASS_LOCAL（声明布局） | 8项目标cloud tests，0.147s，header/非z字节/半开窗口及逆移位；不是原bag逐点复核或全部PointCloud2布局兼容 |
| 修复测量进入宿主 | PASS（归档） | 发布25，status received25/queued25；host逐帧接收/应用，重放382group、applied25/queued0/leftover0 |
| 实际原生重放及内部地图 | PASS（执行事实） | host.log:13483内部restore；:19326重放，14782→18032voxels、279892→331847点；地图数不是准确度或净收益 |
| 注入偏差实际被修复 | FAIL（本次） | producer `bias_z_m=+0.0029`，向损坏云加2.9mm而非扣除0.5m；ICP平移0.026932m/旋转0.216409°，20迭代ITERATION_LIMIT、未收敛 |
| 接回后继续输入 | PASS（有限执行） | resume OK、首决定后328配对帧；终态HEALTHY经过wait_limit_closed/ABORTED重武装，不能据此证明可靠修复 |
| 第二事件 | NOT_EXECUTED | 仅一绝对触发、一episode、一decision，detection off；bag名two_event不是E2证据 |
| 独立质量/公平对照 | UNAVAILABLE | 未有同候选源、同窗口关修复对照，旧022158Z条件不同；不能把地图/轨迹差异归因于修复 |

已实际替换的是60损坏帧中的25条，未发布的35条不能自动计为已修复；382重放group也不等382条修复云。门MODE2接纳25、deferred81，不能把两人口合成已修复全集。`restores=0`是显式restore命令计数，reprocess内部restore原log确实发生，不作矛盾或未回滚。

本轮不能发送“首次实际修复→原生完整链→E2已完成”通知。四非LIVO命名项上一批真实尝试及共享实现/独立原版FAST-LIO2未构建的边界仍保留，不重开矩阵追成功。

## 2. 版本身份与本机实际命令

归档driver SHA `90acfca99d8a21504b4960fc5fb21f8a5b40ad9c0553709f4011ce8d493ed29f`同时匹配目标18baefd及报告run版本cd90e127的driver Git字节。不是只根据提交标题把旧source绑定新运行；其余新接线文件/实际加载环境仍按receipt/配方报告，未独立重建宿主binary。

- [源码控制](run_checks.py)、[结果](local_checks.json)：`C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_18baefd/run_checks.py`，exit0；目标Git blob内存加载，其他package依赖与目标无源码差异。8项cloud tests及有限正负控制，不是全suite/ROS/native实跑。
- 首次同脚本加`-I`失败exit1，隔离sys.path无numpy；未安装依赖，改用既有依赖环境运行自写source-control。`test_repair_sync.py`未运行，因其导入pytest依赖辅助module；不装/shim，使用actual target client/driver小控制替代，不冒充原单测通过。
- [隔离原件reader](check_archive.py)、[原件核验结果](archive_checks.json)：`C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_18baefd/check_archive.py`，exit0。只读Git bytes，不执行归档脚本。
- 17/17清单哈希一致：16个新注入原件+更新README；未重新核整旧矩阵，更未读远端bag/binary字节。原输入、binary及library完整hash保留于目标receipt，属于开发运行收据而非本机独立重算。
- 只读代理原件核验与本机reader结果一致；代理先前`./`路径reader失败不当作hash坏，本机规范化后已解除。

## 3. 主要算法问题：负结果成立，唯一原因与新初值收益尚未成立

目标REPORT/COLLAB称“规范自由度/宿主吸收偏差，所以独立incumbent初值可见0.5m”。本次结果只证明当前估计失败，不能由一次未收敛ICP和不同条件run的位姿差，独立证明唯一因果、一般不可辨性或常速外推一定正确。

现有incumbent是最后5个trusted帧的常速外推，**不是独立姿态GT**；它能作为冻结候选初值，但不能仅改名字叫独立可靠位姿。是否改善信息、减少宿主初始化偏差或只引入外推误差，仍UNKNOWN。新初值方案在本次原件未执行；COLLAB“已派”是开发派工报告，实际owner接收/运行待新证据，不由本机再授新参数或模型权限。

还有一个必须先一致化的确定性几何问题（source `recovery_node.py:1275–1276,1351–1363`、`cloud_repair.py:67–79`）：门候选用 `T'=delta*T` 配**原始损坏扫描**，publisher又将同一个delta平移投到body-z去改扫描，未用真正发布的扫描重新核该候选。这是不同物理候选，不能把旧gate PASS直接搬给新测量。

[本机精确控制](local_checks.json)取identity姿态、干净点z=1、损坏点z=1.5、正确配准delta_z=-0.5：

- 原坏点 + 候选pose：世界z=1（门所见）。
- target producer把坏点减0.5后，body z=1。
- **同一候选pose + 发布修复点：世界z=0.5**，重复补偿。

这是target producer及当前candidate定义的算术反例，不是声称本次2.9mm run已造成0.5m轨迹错误。只有平移就足以暴露一致性，不需扩大旋转/异常矩阵。新方案文中“预期bias≈+0.5，然后按bias平移”也不是正向成功判据：本次注入+0.5，实际测量去偏的identity控制需**施加-0.5**；有误初值/旋转时须明确估计偏置与施加修正的符号及参考pose，不硬套正值。

**最低解除（S2与S1集成）**：复用已有云记录和配准，明确唯一的修复测量/对应重估pose定义，实际发布什么就用什么构成/评估候选；不要对旧坏云通过的pose再重复扣偏。用一个干净/损坏/修复点与世界落点正控制先确定符号，不读注入真值生产反演；若做known-shift直接反演只能标oracle接口控制。原生重放保留真实完整状态，不用旧/deferred尾位姿替代它。无需新增修复框架/阈值层。

## 4. 新接线的正常释放/第二事件反例与最低工程解除

控制全部actual target driver/client，gate/receipt状态按说明模拟，**不谎称发生于本次归档成功传输run**。正控制：有两云+成功receipt，先发reprocess，set_state排队；有限支持新成功入口。

1. **E2累计receipt误放行** — `recovery_node.py:791–812`：E1累计received25/applied25，E2本次收到0/期待25，actual file-client读`OK status ... repair_received=25 ... repair_queued=0`仍返回synced=true。首run从0到25的实际屏障通过不豁免E2。最低使用本次开始计数增量及既有scan stamp/queued/applied记录，确认本episode人口，不新RPC。
2. **同步失败后manager已成功、生命周期仍resume** — `:1416,1473–1479,1526–1539`：合法full接纳已trusted_version+1/HEALTHY/commit_closed；发表两云但receipt false，decide不发reprocess，然后正常消费commit_closed却物理发resume。只测试“没有reprocess”不足以保护接回。最低对native未成功的该段保持失败/未公开状态、阻止依赖resume；复用现生命周期/成功依赖，不能保留成功记录但宿主未应用。
3. **零云也允许原始重放** — `:1326`：accepted但两缓存云缺失，published0/missing2/syncedfalse，仍物理发送reprocess。正常缓存裁剪或修复源不存在不能默默冒充修复。最低实际修复入口要求声明人口产物完整/非零且同步；不满足则明确未修复/不走成功接回，不靠加缓存或通用防御矩阵掩盖。

旧`set_state(ep.frames[-1][2])`和FAIL reprocess仍继续依赖的来源问题新source未修，本轮不重测旧台账。此次原件也不能关闭来源问题：reprocess ACK pos `[5.773410,9.470632,0.038568]`，随后set_state ACK `[6.589887,6.527721,-0.382681]`、map保持18032vox；这只是动作观察、期间帧仍继续，不直接量化同stamp误差，却证明不能把最后resume或set_state位姿称未经覆盖的原生重估输出。最低保native state/map同逻辑时刻及applied成功依赖，不灌旧尾。

这些影响声明修复的真实人口/成功状态/第二事件，是有限研究路径的正确性，不是生产级容错要求。与本次主要估计失败分开记账，不从代码反例猜本次负run根因。

## 5. 原件口径集中更正，不为此重跑

- relay599是JSONL总行数，含1条window；实际598frame=60shift+538原样，非599frame/539原样。
- 触发stamp减注入start为**0.007170145s**，不是REPORT的“前0.7s”；end确为+6s。以原stamp为准，不能按文字补造更早暴露。
- 实际同stamp触发kf134，非历史kf132；summary泛化protocol的host_poses/不是repairer措辞过时，实际candidate_source=icp_reregistration、已发布应用。
- 2个snapshot timeout/failure、wait_limit_closed/unresolved与PLANNED_KILL_AFTER_DRAIN保留。终态HEALTHY与receipt OK不表示正常完整修复或普通退出。
- ACK时间是driver观察时刻，非host精确CPU应用时刻；一次成功屏障与顺序不支持所有分支“都走通”。

## 6. 下一单一主线交付、分工与停止

**下一交付不是再做日志循环或重跑全宿主：在已声明有限损坏范围内，交一次候选测量/pose一致、实际去偏→原生完整状态/内部地图→接回→第二事件/尾段的版本绑定结果，或交首个真实算法/接口断点。** 保留本次估计失败，不能只追bias接近某个正值、gate通过、应用计数或地图点数。

- S1：共享生命周期/发布成功依赖与E2增量receipt最低集成，实际认领回执；不和S2双写manager。
- S2：修复物理定义/符号/候选一致、复用完整记录和host runner；现有有限预算内执行，未知信息不可恢复明说。第二事件不能被单次运行文件名替代。若只做到接口替换，结果限定，不无限追成功。
- S3：仍门A/B/C研究，不恢复旧sigma/κ/floor调参，不部署未选门；研究不挡native主线。
- 窗口/kf/计数/protocol更正可并行；未声明格式、big-endian/padded row、防御框架与全异常单测延期，不为归档文字重跑宿主。

开发随下一实际交付提供**检查项/PASS、FAIL、BLOCKED、NOT_APPLICABLE/实际命令与原件/下一动作**：input/source/config/binary/scan身份，完整记录/符号/实际修复人口，修复后合法候选及独立质量，当前事件queued/applied与丢弃，native同stamp完整状态/map，接回/E2/尾段/成本，失败/缺测/oracle边界。未做写NOT_IMPLEMENTED或NOT_EXECUTED，未知UNKNOWN，不拿测试总数替代。

A1/A2/A6测量传输/替换与原生重放局部实证推进，B7失败范围增加；A7新测量候选一致、A8/A9成功依赖/E2、A10有效修复后持续运行与B4/B11整链仍未闭合。**仅局部复核，不产生新A/B总分**。

## 7. 发布范围

本轮只新增审阅脚本/结果/意见并追加历史/协作，沿 `review/repair-f3-handoff-20261110` 正常SSH提交推送，不合main、不修改算法/冻结门/旧记录、不发布私人handoff。旧push限制已解除，收到此次意见及后继执行仍待开发真实回执。
