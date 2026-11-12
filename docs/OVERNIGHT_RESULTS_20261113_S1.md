# 15 小时结果（开发侧 S1 汇总，2026-11-13 07:20 UTC+8；08:00 按审阅更正）

窗口：2026-11-12 17:53 → 2026-11-13 08:53（UTC+8）。本文件只汇总**本机已核实原件**的结果；
逐项证据在 `docs/COLLABORATION_STATUS.md` §114–§174 与对应归档分支中。状态口径：
PASS / FAIL / BLOCKED / NOT_APPLICABLE + 原件；未做的明确 NOT_IMPLEMENTED / NOT_EXECUTED / NOT_EVALUABLE。

> **更正记录（2026-11-13 08:00，依据审阅 `330e594`）**：① 纯在线 42 修复那次是 run `121127Z_497953`
> （库 `49f2f941…`、可执行 `0d7e23de…`、driver `62c165d1…`、trace **92 列**），**不是 v11**；v11 同行 trace 是
> run `165438Z_669633`（库 `81b35f92…`、107 列），两者不可互相挂靠。② 地图暴涨的根因记 **UNKNOWN**，只保留
> "匹配退化"候选。③ FAST-LIO2 的 `NATIVE_INDEPENDENT` 限定为"独立工作区构建的**MM-LINS 派生前端**"；同首末戳不等于全轨迹相同，
> 239 s 尾段含 26.9 s 断流/原点重置；config/output hash 与实际脚本仍缺。④ 撤回"MM-LINS 无测量注入点 → 建议换 LIO-SAM"：
> 实际运行拓扑是 **FAST-LIO + PGO 两节点**，点云订阅就是测量输入面；"LIO-SAM 单进程"缺 PID/launch 支持，旧 receipt 为 4 节点。
> ⑤ 协方差项改为"已明确 `NOT_AVAILABLE`、单位权限定"，不是"已修正/已完成转换"。⑥ LIO-SAM 发散与 ORB 失败为**候选因果**，
> 不足以排除图优化；FAST-LIO2 run1 失败根因 **UNKNOWN**，环境只是候选。

## 1. 执行身份与版本

| 项 | 值 |
|---|---|
| 代码主线 | `slam_recovery` main，本文件写入时 HEAD `d17d552`（更正前）/ 更正提交见 `git log` |
| 归档分支 | `exp/trace-cov`、`exp/online-trace`、`exp/online-v2`、`exp/growth-run` |
| S1（本会话） | 分发、集成、共享 driver/manager（`checkpoint_check`/`restore_disposition`/`decision_skipped`/summary 修复） |
| S2（r11070-c3） | 宿主执行：FAST-LIVO2 v6–v12、四宿主分析、FAST-LIO2 独立构建与 run |
| S3（r26534-58） | ALI-H 方法研究（T0/T1/T2、契约、资格分层） |
| 用户新指令（经 Codex 发布） | 四项非 FAST-LIVO2 宿主全部验收前不新开 FAST-LIVO2 工作，已执行 |

## 2. 原生链（FAST-LIVO2，按用户指令已停止）

| 交付 | 结果 | 原件 |
|---|---|---|
| 受控两事件整链（v6 边界修复） | **PASS（受控接口范围）**：两段 checkpoint 均早于 `t_start`（15.9/12.4 ms）；E1 Mode2 接受 23 修复、794 帧重放（244 within + 550 suffix）、无 `set_state`；E2 Mode3 拒绝 + restore + close/rearm/resume；尾段到 320.909；终态 HEALTHY。不认证全部缓存等价或独立净收益 | `docs/review_20261112_four_host/boundary_checkpoint_final_20261112/`（run `092251Z_291996`） |
| 纯在线自动链（`121127Z_497953`，库 `49f2f941…`、trace 92 列） | **部分 PASS**：5 段全部自动触发；1 段 Mode2 接受、**42 条修复 applied 42/dropped 0**、replay 759+615；3 段拒绝、1 段 errored（`No active quarantine segment to validate`，已在 driver 修为 `decision_skipped=SKIPPED`，**旧 run 原件不变**） | `exp/online-trace@e991eaf` |
| 在线回退合法性 | **FAIL（负结果）**：四段中三段 restore 晚隔离起点 **3.77/3.83/4.23 s**；rolling 历史无法提供 ≤ qstart 的合法 checkpoint；`rollback_support=UNSUPPORTED_AT_OR_BEFORE_QSTART` | `ONLINE_ROLLBACK_NEGATIVE_20261112.md` |
| C′ 历史 checkpoint（K=3，灰发） | **局部**：环形保留生效、存在早于边界 **36.97 ms** 的候选；历史条目缺 IMU 延续量与 replay capture，**不能用于恢复**；restore 选择语义未改 | `exp/online-v2@99bfe1e`；`cphist_*` |
| 运行期地图增长 | **负结果（根因 UNKNOWN）**：`eff` 在 rel 25–35 s 塌陷、地图增速峰值 rel≈40.5 s，与隔离窗口不同步；"匹配退化"是候选解释，**不排除越界写**；精确峰与最终量只作 DEVELOPER_REPORTED | `exp/growth-run@ab2fd2a`（文字判据，无新运行） |

结论：受控链已跑通一次；纯在线链首次出现"自动检测→接受→42 修复→replay"实际生效；**在线合法回退、拒绝后历史追赶、
完整缓存等价、独立净收益仍未闭合**。v11 同行 trace（`165438Z_669633`）是另一 run，不能用于 42 修复结论。

## 3. 四宿主（用户新指令后的主线）

| 宿主 | 原生证据（限定） | 恢复层 | 关键结论 |
|---|---|---|---|
| FAST-LIO2 | **NATIVE_INDEPENDENT（限定）**：独立工作区构建的 **MM-LINS 派生前端**（`4c31fada…`）；`/Odometry` 4186 条、首末戳与共享版相同；E2 后 239.318 s / 2126 条（含 26.899 s 断流/原点重置）；`Issleeping`/`Isbuilding` 各 2 次。**同首末戳≠全轨迹相同**；config/output hash 与实际脚本仍缺 | NOT_IMPLEMENTED | 独立构建与执行成立；完整宿主独立验收、恢复与净收益未证 |
| MM-LINS / SC-PGO | 既有原生双事件（**实际运行拓扑为 FAST-LIO + PGO 两节点**） | NOT_IMPLEMENTED | 点云订阅即为测量输入面；跨进程状态分散是接线难点，但**不能据此豁免测量要求**；可复用 PGO 关键帧+iSAM2 与 `SleepMapList` |
| LIO-SAM | 原生 FAIL | NOT_IMPLEMENTED | 106 帧×… 输入点数在 120–140 s 骤降（26k→797→203）、130.3 s 起轨迹渐坏、110 次 IMU 预积分重置；**"输入退化驱动、非图优化"是候选**，不足以排除；进程拓扑与旧 receipt 为 4 节点，单进程说法缺 PID/launch 支持 |
| ORB-SLAM3 | 原生 FAIL | NOT_IMPLEMENTED | 单目惯性初始化不稳（80 次建图、385 次 `Not enough motion`、末 0 KF、exit 139）；`TrackMonocular(image,time,IMU)` 是 runner 输入面，"无 ROS 话题"≠不能修复输入；`SaveAtlas/LoadAtlas` 存在不等于完整可信 tracker |

共同前提（保留）：恢复前必须区分"输入故障 vs 算法故障"；不能把 FAST-LIVO2 的实现默认平移到其它宿主。

## 4. ALI-H

| 项 | 状态 |
|---|---|
| 设计/契约/预注册协议 | 完成 |
| T0（旧 402/544 资格） | 完成：A 95/307、B 132/412；I 通道 0；shadow 全 UNKNOWN |
| T1 | 7/7 PASS |
| T2（v11 run `165438Z_669633`） | I 462（真 SE(3) Log、单位权 `|e_I|²` p50 1.1726e-3）；M 175 / T 306；106 块全 UNKNOWN；资格三层（v11 `RAW_HEADER_CONTAINMENT=PASS` / v7 `HEURISTIC_UNPROVEN`；`SAME_UPDATE_PRE_POST=PASS`；`COMPLETE_POINT_MEMBERSHIP=ASSERTED_NOT_VERIFIED`）；**协方差 `NOT_AVAILABLE`（仅资格声明，未做转换）**；18 条 `eff=0` 单列 |
| 分类/误报/漏检/延迟/错误 NORMAL | **NOT_EVALUABLE**（缺独立正常参照与事件标签） |

窗口内被审阅指出并经本机复现后修正的实现缺陷：SE(3) Log 平移漏 `V⁻¹`、缺块跨空窗累计 dwell、协方差切空间未绑定、
时间索引错配（92/504 行）。修正均为**资格/数学层**，不构成坐标系转换或误差协方差的实现。

## 5. 阻塞与未完成

1. **缺少独立正常参照与事件标签**：分类与错误率无法评价。已有授权允许"声明自注入标签仅离线评价"，
   因此**不把再次抽象选择 A/B/C 当作已授权步骤或原生接线的默认前置**；若确需新数据/换输入/超预算，再给具体缺项与最低获取。
2. **环境（平台层）**：`/proc/loadavg` 为宿主机全局值（容器约 2.8/128 核）；16 个 2026-11-06 起、属本会话的 `mmlins_ws`
   孤儿进程占约 2.4 核，**终止操作被本机权限拦截**；FAST-LIO2 首次 run 失败根因 **UNKNOWN**（超时/全量录制/负载均为候选），
   重跑在新门控下通过——**不由此反推代码因素已被排除**，也不把杀进程当恢复主线的必要条件。
3. **FAST-LIVO2 在线恢复缺口**：合法 ≤qstart checkpoint、拒绝后历史追赶（`catch_up=NOT_IMPLEMENTED`）、完整缓存等价、独立净收益。
4. **四宿主恢复层**：全部 NOT_IMPLEMENTED。

## 6. 窗口内未执行（如实）

- 未在四宿主上实现/运行任何 slam_recovery 恢复层接线（仅接口分析与原生验证）；
- 未做大规模参数扫描、未改冻结科学阈值；
- ALI-H 未取得分类效果；
- 未按审阅建议额外补矩阵/新宿主。

## 7. 需要用户决定的事项（仅限真实超出当前授权或需新数据的事项）

1. 若要让 ALI-H 的分类与错误率可评价：需要**独立确认的正常前缀与事件标签**（具体缺项见 `T2_I_ELIGIBILITY.md` 与
   `重大阻塞记录.md`）——这是数据来源问题，不是选项字母问题；
2. 是否终止 §5.2 的 16 个本会话遗留进程（影响宿主算力，不影响已完成证据）；
3. 若要把恢复层接入某一宿主并超出既有预算（构建/运行时间、数据），需要明确授权范围；**宿主接线本身属既有 15h 授权内的集成工作**，
   由 S1/S2 按实际拓扑继续，不再以"选型"形式请用户决定。
