# FAST-LIO增量审阅：受控原生接口局部推进，整链未发生，v3边界与执行回执须先修正

面向：开发S1/S2/S3、用户与独立复核者。2026-11-13 11:03:07（UTC+8）fetch后固定main `119f5d7b4561039f3de91e6e709d76dcae021615`、F1分支 `ce3aaacdf9e31a13e00ba293829ee0eeae50c21d`；前段F2/F3固定main `a355343711cf8e8daf71eadbd68677ab4bf7bddb`。已读AGENTS、A/B评分表、REVIEW§10及今日FAST-LIO任务；20min/2h/日报和18:00一次性任务仍由repair-f3持有，无双写。私人未跟踪文件未读未动。

本机只读源码和归档、运行独立有限控制；**没有改生产算法、构建或运行ROS/宿主、安装依赖、调整阈值或恢复已暂停工作**。交接记录称用户要求先暂停并提交全部尝试，本审阅不自行放行构建/run，也不从Git推断远端进程已经停止。

## 1. 总结：部分推进，不是二事件或自动检测通过

**任务接收疑问已关闭。** main `c80f50b`明确接收 `1b28fe3`，S1记录10:15分发F1/F2；S2/S3随后均有实质交付，不能再报“未收到/未开工”。S2交FAST-LIO派生前端原生v1/v2与真实受控run，S3交本host通道契约/reader，S1交共享能力门与归宿统计。

**主线有受控原生接口进展，但完整目标未推进到通过。** ctrl2有真实hold/snapshot/restore/reprocess、地图点数27513→71690和声明83组重放，接受为 **PARTIAL_CONTROLLED_INTERFACE**。快照不含p_imu预积分/去畸变缓存，`reprocess=PARTIAL`；没有独立净收益，也没有自动检测。

**两事件整链尚未发生。** 第5次完整260.027s调用的host从启动即hold，2248组全部quarantined；driver 1004 paired/ingested、0 episode、scripted E1/E2未触发，run_mode=`CONTROLLED_TRIGGERS_NOT_FIRED`。这是控制接口失败，不是FAST-LIO算法不能恢复的证据；`final_state=HEALTHY`不作健康证明。前四次启动/驱动门控失败保留，均不包装成有效整链实验。

v3只有延期diff及开发声明的语法检查，**未构建、未运行**；下列源码问题说明它尚不能直接作为已修复版本验收。

## 2. 接受的原生证据及其严格边界

| 证据 | 独立判定 | 不能外溢为 |
|---|---|---|
| v2 `laserMapping.v2.cpp`、v1/v2 diff、build日志 | PASS源码/归档局部；有真实ESKF状态/P、ikdtree点集、时间游标、hold和buffer replay实现 | 本机独立构建或binary实体hash复核；完整IMU/deskew checkpoint |
| ctrl2 `commands.log` | PASS受控命令序列；restore回同一stamp/frame，声明`replay_within_end=83/repaired_fed=1` | 自动触发、E1→接回→E2、拒绝/超时/追赶通过 |
| ctrl2 snapshot A/B 27513/71690 | PASS原生replay后地图增长的有限证据 | 修复云已进入成功update、地图净收益或几何正确性 |
| 第5次host/driver原件 | FAIL控制面、有效负结果；启动hold导致无图、停发和触发未达 | 0候选=方法漏检，或最终HEALTHY=正常 |
| F2通道文档、reader及8个合成用例 | PASS数学/合成组件；本host真实run导出仍未到 | FAST-LIO真实I/M/support资格、NORMAL/SUSPECT或检测性能 |

开发实测输入bag只有IMU+LiDAR、无GT/参考topic，本机未重跑rosbag；结合既有归档，**独立正常前缀与故障标签仍未取得**。召回、误报/小时、延迟、onset误差、错误NORMAL及净收益保持NOT_EVALUABLE，不能填0。

## 3. 下一次有效复验前的原生最小修正

### 3.1 v3延期hold/snapshot仍可能晚于声明边界，且“armed”被ACK成已执行

固定[v3 diff:282–325](https://github.com/Evenstar-E/slam_recovery/blob/ce3aaacdf9e31a13e00ba293829ee0eeae50c21d/docs/four_host/fastlio_recovery_20261113/native_recovery_v3_deferred.diff#L282-L325)及[调用位置:375–399](https://github.com/Evenstar-E/slam_recovery/blob/ce3aaacdf9e31a13e00ba293829ee0eeae50c21d/docs/four_host/fastlio_recovery_20261113/native_recovery_v3_deferred.diff#L375-L399)：

- `nr_apply_deferred()`以下一循环前的上一完成帧 `g_nr_lidar_end>=target` 为条件。若相邻帧末为 `t0<target<t1`，它会在t1帧已经完成估计/地图更新后才hold/snapshot；所得快照戳为t1，而契约要求“第一组达到target之前”及checkpoint不晚于边界。
- 入队即写 `OK <cmd> deferred ...`。现有CheckpointClient以OK为完成并计数/释放下一命令，故armed不等于applied；之后真正执行的同名ACK还可能覆盖或误配其它命令。

**最低修正**：在第一个 `lidar_end>=target` 的组进入估计/地图写之前执行hold，并保存前一个完成组的可信状态；armed只作接收回执，applied ACK必须带实际stamp/frame并保持客户端pending至该回执。用一个target落在两帧之间的确定性控制验收：快照=前一帧、跨界帧不进入可信地图、实际ACK可唯一关联。不是再扩异常矩阵。

### 3.2 自动accepted路径的hold/replay顺序未被ctrl2覆盖；`repaired_fed`不是已进入估计器

- ctrl2脚本在reprocess前手工resume；但自动路径在 `_open_episode` hold，`evaluate_and_commit_candidate`后才进入reprocess，lifecycle resume要等下一次service。v2原生reprocess本身不清hold，[v2:344–374](https://github.com/Evenstar-E/slam_recovery/blob/119f5d7b4561039f3de91e6e709d76dcae021615/docs/four_host/fastlio_recovery_20261113/laserMapping.v2.cpp#L344-L374)。因此当前受控脚本没有证明自动accepted replay期间地图写会释放。此项是**源码确认的未覆盖序列**，不是冒称已观察到E1失败。
- 同一函数内，`nr_take_repair`/`++g_nr_repaired_fed`发生在 `lidar_buffer.push_front`，随后立即ACK；没有native update/map调用。它证明的是“修复云被选择并排入buffer”，不能直接映射为driver的 `repair_entered_estimator=True`。地图后来增长证明replay运行，但不唯一证明修复云进入成功update或带来收益。

**最低修正**：S1/S2明确accepted replay期间的map-write释放与新实时输入控制顺序；把“替换并入队”“实际消费到原生update”“地图贡献完成”分为同一update可关联的回执。下一次accepted E1必须交实际update/地图证据，不能仅引用repaired_fed。

### 3.3 replay标志永不复位，899条后继实时输入已被原件证实错标

v2/v3均只有 `g_nr_replay.store(true)`，没有false复位；[v2帧尾:1284–1287](https://github.com/Evenstar-E/slam_recovery/blob/119f5d7b4561039f3de91e6e709d76dcae021615/docs/four_host/fastlio_recovery_20261113/laserMapping.v2.cpp#L1284-L1287)据此决定fate。

独立复算ctrl2全部1255行：261 ingested、12 quarantined、982 replayed。以重放前最大输入戳 `1711547910876055808` 分界，**83条是声明区间重放，899条是其后新实时输入却全标replayed**。这直接破坏A5/A10的接回与后继身份。

**最低修正**：按实际重放队列耗尽和最后重放帧结束复位，而非按命令发出；保留重复frame号的replay/live身份及精确时间，复用ctrl2原件增加一个回归断言即可。

## 4. F3“全消息归宿”仍有实际与合成反例

[message_disposition:2199–2264](https://github.com/Evenstar-E/slam_recovery/blob/119f5d7b4561039f3de91e6e709d76dcae021615/slam_recovery/ros/recovery_node.py#L2199-L2264)只从driver自身事件推算，没有执行其文字声明的“每帧恰属一类，否则unresolved”。

1. **真实第5次**：host 2248组全quarantined，driver却1004 `never_quarantined`、0 episode、`unresolved=[]`；至少有2个精确同戳帧可直接对账为host quarantined。不同层的完整人口不要求行数机械相等，但同身份归宿矛盾必须进unresolved。
2. **闭段跳过控制**：1个ingested、`SEGMENT_CLOSED_BEFORE_DECISION`、无committed/deferred/pending，四类合计0，仍 `unresolved=[]`。
3. **重叠事件控制**：同一key在一个已committed事件及另一个未决事件中，ingested=1而四类合计2，仍 `unresolved=[]`。

**最低修正**：按distinct key建立互斥归宿，skipped单列但不假装已归宿，重叠/缺失进unresolved；按精确update/声明时间量化关联host fate与driver keyframe，保留多对一，不能最近邻贴接。该项只阻“全输入已完整记账”的主张，不阻S2继续修原生接口。

## 5. F2 reader的资格PASS/support守卫需最小收紧

固定reader在main 119f5d7与a355343逐字相同。本机实际运行其8个合成selftest均PASS，再交三个普通反例：

| 反例 | a355/119f5d7实际结果 | 应有边界 |
|---|---|---|
| 两行有效pose，其中一行缺必需run_id | 两行OK、I_rows=2、mixed=false、`SAME_UPDATE_ID_PAIRING=PASS` | 缺身份行INVALID，整体身份/配对不得PASS |
| 同一run一行OK、一行缺post | row_status含NO_PAIR，同时pairing PASS | “完整pair”资格不能PASS；NO_PAIR保留人口 |
| support仅 `{pass_fraction:1.0}`，无样本数n | `SUPPORTED` | 未证明200样本，必须UNKNOWN_CONTEXT |

对应[run_ids:135](https://github.com/Evenstar-E/slam_recovery/blob/119f5d7b4561039f3de91e6e709d76dcae021615/docs/ali_h_v1_research/f2_fastlio_read.py#L135)、[support:95–107](https://github.com/Evenstar-E/slam_recovery/blob/119f5d7b4561039f3de91e6e709d76dcae021615/docs/ali_h_v1_research/f2_fastlio_read.py#L95-L107)及[pairing:300–303](https://github.com/Evenstar-E/slam_recovery/blob/119f5d7b4561039f3de91e6e709d76dcae021615/docs/ali_h_v1_research/f2_fastlio_read.py#L300-L303)。S3只需补这三个回归，不重写reader、不重开已验SE(3)数学或扫阈值。

## 6. 对开发交接三个问题的审阅答复

1. **apply stamp必须成为接口契约。** 当前v3实现尚不满足“目标组前hold、checkpoint不晚于边界、applied ACK真实唯一”的语义，先修再构建/run。
2. **PARTIAL replay可以称有限原生缓冲重放/部分重估，但不能称完整恢复。** 名称不替代实际update证据；p_imu缓存缺失不必阻止一切原生实验，却使完整历史状态等价/完整checkpoint保持未通过。当前queue ACK连“修复已进入update”也尚未证明。
3. **无GT/独立正常标签时接受shadow/UNKNOWN作为有限交付，但不接受“自动检测问题已解决”。** 无需用用户选择豁免科学门；性能NOT_EVALUABLE。若需要新外部参考或新增注入run，再单独取得对应预算/数据授权，未阻原生修正继续。

## 7. 主线、并行和下一单一交付

- **主线（S1共享集成＋S2宿主）**：先交修正后的确定性控制与源码，再在用户实际恢复授权后，以同一有限输入完成 **合法边界快照→accepted E1 replay地图实际重建→修复云真实update回执→实时输入恢复ingested→E2/尾段及host-driver归宿一致**。一次失败保负结果，不为凑PASS重跑。
- **必须先做的最小保障**：§3.1–3.3及跨层归宿对账；它们已破坏或会直接误证本次输入、地图和接回，不是生产级防御扩展。
- **可并行（S3）**：F2三个资格回归、真实导出到达后的UNKNOWN/单位权shadow；标签缺失只限性能，不阻原生修正。
- **延期**：新模型/视觉/通用多宿主框架、参数扫描、FAST-LIVO2新工作、净收益/检测率的强行数值化。四宿主最终需求和冻结科学门不变。

A2/A6有真实受控原生局部推进；A4/A5/A9/A10/B2/B11仍未闭合，A3/B3没有本host自动检测成绩，B4净收益未评价。**不全表重评分，不沿用旧总分为当前分数。**

## 8. 独立命令、状态与复现

- [F2/F3控制](run_checks.py)及[结果](local_checks.json)：`C:/Python315/python.exe -I -B .../run_checks.py` exit0；实际8个selftest PASS＋5个反例CONFIRMED。首次因 `-I` 未带现有NumPy而ModuleNotFoundError，显式加入本机已有user-site后成功；未安装。
- [原生原件控制](native_checks.py)及[结果](native_checks.json)：标准库Python `-I` exit0；真实人口/时间戳复算和固定源码顺序检查。首次断言定位到reprocess前段失败ACK而exit1，改为定位入队后的最终ACK后通过；这是本机检查脚本定位修正，不是宿主测试。
- PASS仅指上述组件/归档或控制实际执行；FAIL为第5次控制面与已确认缺陷；BLOCKED为真实导出/独立校准标签及用户暂停后的构建运行；NOT_APPLICABLE仅F2声明的T结构缺项，不用于豁免其它需求。

全部旧失败保留。本报告只提交审阅脚本、JSON、历史索引，现review分支SSH推送；不合main、不改历史、不覆盖开发日报/私人文件、不修改生产算法或科学门。
