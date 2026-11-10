# 2a7d447：旁路接线已落地，原生写回与第二事件仍未接通

2026-11-10。目标`2a7d447667cd185ad141f5e43082a9a3f8bac5e4`；基线6631da8。新增ROS驱动/runner/测试、stage1/1b报告及receipt/wiring/candidate原件，六笔开发增量；跳过已验收和Auto-Review。已读AGENTS、主线标准、REVIEW10并核本会话三任务及旧owner不运行，忽略stop.md。保护私人handoff，不改算法、不运行ROS或宿主、不调门。

## 1. 实际进展与证据

**部分主线实施进展：真实宿主输出→ROS旁路节点→检测/隔离→一次候选准入/拒绝的接线已交代码和小型运行产物。不是只有提交说明；但尚未交用户要求的原生恢复→接回→第二事件。**

本机从固定Git blobs核验：

- recovery_node.py SHA256 `e3f9c414…`与native_loop_receipt.json源码SHA完全一致；candidate/receipt同run `fl_native_20261110T032515Z_2954170`。
- wiring归档接收800 pose/599 scan，584配对，584/599=97.4958%；实际最大dt39.824962ms。它是有限窗口时间配对，不由成功率单独证明同一原生处理事件/精确同步。沿现限定使用，不因每次统计差强求同值。
- host PID2955402、recovery PID2955403，同PGID2955400：**不同进程共同管理**，不是相同宿主进程内状态恢复。跨进程也能通过有效接口构成恢复闭环，但当前没有此接口。
- receipt headline：1 episode、1 decision、accepted0、final WAITING_FOR_EVIDENCE。候选实际MODE3拒绝，边界跳变0.666m，holdout NIS3.99448，信息40.23159→34.47305；未有接纳/原生恢复/E2。
- 原run_summary、消息/状态序列及宿主输出bag仍未本机取得。以上是Git原件身份/内部关联与源码核验，不是重新播放宿主、独立复算全逐帧分布。

接受可复用的ROS订阅/配对、消息→step_frame连接、候选参数/准入调用、拒绝记录、后续接收计数、runner进程管理。不得重新造同一驱动/runner或再次完成旧A5/A9修复。

## 2. 当前两个实际工程缺口：不是继续调NIS能解决

### 2.1 没有原生恢复/重处理/状态地图写回接口

源码`slam_recovery/ros/recovery_node.py:918–988`只订阅odom和cloud，唯一发布gate_status字符串；`:645–662`从episode缓存宿主pose构造repaired_poses。runner`:178–186`分别启动宿主和Python节点。

**缺的不是日志，而是实际动作：**没有调用宿主checkpoint恢复、修复测量重处理、状态重估/内部地图重建或修复状态写回。代码docstring也声明host_poses不是repair。Python manager改变自己的对象/sidecar不改变正在运行的FAST-LIVO2。

最低解除：S1/S2在现宿主上接实际恢复/重处理/提交接口，明确文件/函数；支持范围有限即可，不建通用框架。若当前接口不存在，实现这个最小接口才是主线；若决定暂用离线重跑/宿主重启，要标实际能力，不能改名冒称同次原生恢复。CLI虽允许icp_reregistration，当前候选仍来自缓存pose；不能仅改来源字符串声称执行了ICP。

### 2.2 首次Mode3后没有继续处理等待段/重武装/E2路径

`recovery_node.py:641–645`首decide即`ep.decided=True`；真实manager`:457–459`保留active_quarantine并WAITING。后续驱动`:543–549`跳过候选追加/再次决定，finish也跳过已decided段；隔离未结束不能创建下一episode。node隔离来帧只登记，不能把消息消费计数当新故障处理。

**具体运行就是1episode/拒绝/WAITING，报告stage1:120–122已承认后续帧只登记。**因此仅把首告警NIS变低，仍不能完成首拒绝→接回→E2。这是确定性功能缺口，不是随机实验波动。

最低解除：实现当前等待段后续有效证据/候选处理、支持的终态/返回与重武装；保留拒绝，不强制接受、不假造健康。用真实manager的一条首拒绝→后续输入→第二事件正常场景验，然后交限定原生运行。新adapter测试fake拒绝时清空active quarantine（test_recovery_node.py:315），不等真实Mode3，所以不能靠其计数宣布该路径通过。不扩异常/并发测试框架。

## 3. 旁支收口：参考年龄/NIS与字段解释

空间抽样后NIS仍高，支持“这次换采样未解决提前告警”，不能直接说所有点数cap影响被排除、唯一真因已证明是地图年龄。少量重复有随机差异，21.57与24.05不要求逐值复现；主要趋势是高残差、提前隔离仍在。地图持续增长的有限诊断可区分启动参考不足与仍存在的残差/位姿/支持问题，但这是**检测关闭诊断，不是恢复运行**。已有两事件接口不能等待无期限的NIS分箱/标定。

detection-off后若NIS随地图扩大降低，属于启动条件的开发依据；从结果选出的新启动规模须明确是开发选择，不能包装为独立确认。不以新K帧门槛或sigma*.55自动修复，不降低冻结门。只有新证据指向真实参数瓶颈才按PROJECT_HISTORY§2.1总结规律/上限后决定调整。

两处表述随实际交付集中解释，不立新日志任务：

- candidate的paired_benefit_status=FAILED与Wilson0.886/真实paired21/21不矛盾：驱动`:233`实际写复合`ValidationReport.evidence_status`，core`:518–528`结合paired/Wilson/重入，跳变超限足以FAILED。不能将它当独立paired或质量标签，也不能称只有边界一项物理指标不合格（NIS3.994>2.5、信息增益负仍可见）。
- sigma脚本按“点数恒定”猜reference_variant并不能识别真实采样算法；空间采样在图冻结时也恒定931。沿实际源码/receipt记参考类型，计数仅描述，不用标签猜根因。这仅限制诊断解释，不挡原生接线。

A7 actual-node world正则反例沿[e72c145核验](../review_20261110_21fa650/README.md)，core/node/manager在21fa650..2a7d447未变；不重复跑旧68test、旧反例或重开已通过的搬运公式。S3只做固定基内现epsilon正则最小修正。

## 4. 本机自检与诚实失败记录

| 项 | 状态 | 实际命令/结果 |
|---|---|---|
| native源码与收据关联 | PASS（归档身份） | git show固定原blob SHA256与receipt一致；candidate run ID同 |
| runner语法 | PASS | `bash -n slam_recovery/ros/run_native_loop.sh`，未启动 |
| 核心unittest discover含新模块 | **FAIL：环境导入ERROR1** | 显式目标sys.path，69 entries，0断言FAIL/1ERROR：test_recovery_node导入pytest缺失；原68执行无失败；2.279s |
| 新adapter27个pytest例本机执行 | BLOCKED | 当前Python3.15无pytest；不安装、不伪造pytest shim，不把环境失败当算法回归，也不宣称27例已独立PASS |
| 原生恢复/E2功能 | 未实现/未验收 | 上述源码与1episode WAITING归档；未本机跑ROS |
| sigma/随机趋势 | 归档方向接受，因果未定 | 不重复运行会覆写结果的校准脚本，不强求同值 |
| 完整A/B升档 | NOT_APPLICABLE | A2/A3接线，A10/B11仍缺恢复与E2，B4/B5/B10无新净收益 |

## 5. 下一单一主线与并行分工

主线按[NATIVE_RECOVERY_RUN_TASK](../NATIVE_RECOVERY_RUN_TASK_20261110.md)不变，但本轮**已经定位具体缺口**：

- S1集成，明确当前宿主恢复接口文件/函数和责任，不以更多检测诊断代替接口；复用已通过A5/A9。
- S2 r11070-c3在现驱动接原生实际修复/写回，并补真实Mode3等待段处理及重武装；交一次限定恢复/接回/E2运行或第一实际接口断点。无需再证明“能收话题”。
- S3 r26534-58并行最小A7固定基正则；现NIS趋势诊断有明确假设/预算可集中准备，不不断交sigma/分箱文字。KITTI/外部基线/独立标签不挡开工。
- Codex沿已有独立包和版本范围做集成验证，不抢写driver/manager；环境缺失照实BLOCKED。

开发交付仍需PASS/FAIL/BLOCKED/NOT_APPLICABLE、实际命令/结果路径和当前接口；不另造仅“收到审阅”的提交。本轮用户追加随机复现尺度已写AGENTS、REVIEW及项目历史：总体趋势相容即可，不要求逐位/逐值同结论；同时不豁免确定性接口缺失、状态停留、身份和坐标不变量。不据随机差异新增防御门/重跑矩阵，冻结科学标准不降低。
