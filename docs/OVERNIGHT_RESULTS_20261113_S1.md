# 15 小时结果（开发侧 S1 汇总，2026-11-13 07:20 UTC+8）

窗口：2026-11-12 17:53 → 2026-11-13 08:53（UTC+8）。本文件只汇总**本机已核实原件**的结果；
逐项证据在 `docs/COLLABORATION_STATUS.md` §114–§174 与对应归档分支中。状态口径：
PASS / FAIL / BLOCKED / NOT_APPLICABLE + 原件；未做的明确 NOT_IMPLEMENTED / NOT_EXECUTED / NOT_EVALUABLE。

## 1. 执行身份与版本

| 项 | 值 |
|---|---|
| 代码主线 | `slam_recovery` main，本文件写入时 HEAD `f795643`（含 §114–§174 记录） |
| 归档分支 | `exp/trace-cov`（FAST-LIVO2 v6–v12 源码/diff/probe）、`exp/online-trace`、`exp/online-v2`、`exp/growth-run`（四宿主分析、FAST-LIO2 独立构建与 run） |
| S1（本会话） | 分发、集成、共享 driver/manager 代码（`checkpoint_check`/`restore_disposition`/`decision_skipped`/summary 修复） |
| S2（r11070-c3） | 宿主执行：FAST-LIVO2 v6–v12、四宿主分析、FAST-LIO2 独立构建与 run |
| S3（r26534-58） | ALI-H 方法研究（T0/T1/T2、契约、资格分层） |
| 用户新指令（经 Codex 发布） | 四项非 FAST-LIVO2 宿主全部验收前，不新开 FAST-LIVO2 工作（`docs/HOST_VALIDATION_ORDER_20261113.md`），已执行 |

## 2. 原生链（FAST-LIVO2，按用户指令已停止）

| 交付 | 结果 | 原件 |
|---|---|---|
| 受控两事件整链（v6 边界修复） | **PASS**：两段 checkpoint 均早于 `t_start`（15.9 ms / 12.4 ms）；E1 Mode2 接受 23 修复、794 帧重放（244 within + 550 suffix）、无 `set_state`；E2 Mode3 拒绝 + restore + close/rearm/resume；尾段到 320.909；终态 HEALTHY | `docs/review_20261112_four_host/boundary_checkpoint_final_20261112/`（run `092251Z_291996`） |
| 纯在线自动链（v11） | **部分 PASS**：5 段全部自动触发；1 段 Mode2 接受、**42 条修复 applied 42/dropped 0**、replay 759+615；3 段拒绝、**1 段 errored**（`No active quarantine segment to validate`，已在 driver 修复为 `SKIPPED`） | `exp/online-trace@e991eaf`（run `121127Z_497953`） |
| 在线回退合法性 | **FAIL（负结果）**：四段中三段 restore 晚隔离起点 **3.77 / 3.83 / 4.23 s**；当前 rolling 历史无法提供 ≤ qstart 的合法 checkpoint；已加 `rollback_support=UNSUPPORTED_AT_OR_BEFORE_QSTART` | `ONLINE_ROLLBACK_NEGATIVE_20261112.md` |
| C′ 保留历史 checkpoint（K=3，灰发） | **局部**：环形保留生效、存在早于边界 **36.97 ms** 的合法候选；但历史条目缺 IMU 延续量与 replay capture，**不能用于恢复**；未改 restore 选择语义 | `exp/online-v2@99bfe1e`；`cphist_*` |
| 运行期地图失控 | **负结果**：`eff` 在 rel 25–35 s 塌陷、地图增速峰值 rel≈40.5 s，与隔离窗口不同步 → 指向 LIO 匹配退化后的持续写入，非隔离触发越界写；K=3/K=1 对照与 ASan 一并暂停 | `exp/growth-run@ab2fd2a` |

结论：**"测量修复→原生状态/地图重处理→接回→第二事件"的受控链已跑通一次**；纯在线链首次出现"自动检测→接受→42 修复→replay"全链路实际生效；
但**在线合法回退、拒绝后历史追赶、完整缓存等价、独立净收益仍未闭合**。

## 3. 四宿主（用户新指令后的主线）

| 宿主 | 原生证据 | 恢复层 | 关键结论 |
|---|---|---|---|
| FAST-LIO2 | **NATIVE_INDEPENDENT + PASS**：独立构建 `4c31fada…`、`/Odometry` 4186 条、首末戳与共享版逐位相同、E2 后尾段 239.318 s / 2126 条、`Issleeping`/`Isbuilding` 各 2 次 | NOT_IMPLEMENTED | 依赖最少、已可作独立宿主；`docs/four_host/FOUR_HOST_RECOVERY_COMPARISON_20261113.md` |
| MM-LINS / SC-PGO | 原生双事件 PASS（既有） | NOT_IMPLEMENTED | **4 节点、无单一状态所有者、无测量注入点**；可用 PGO 关键帧+iSAM2 软回滚、`SleepMapList` 粗回滚；`docs/four_host/MMLINS_RECOVERY_INTERFACE_20261113.md` |
| LIO-SAM | 原生 FAIL | NOT_IMPLEMENTED | **输入退化驱动的前端发散**（120–140 s 点数 26k→200，130.3 s 起漂移，110 次 IMU 预积分重置，无回环约束）；单节点、**有话题级测量注入点** |
| ORB-SLAM3 | 原生 FAIL | NOT_IMPLEMENTED | **单目惯性初始化无法稳定**（351.65 s 内 80 次建图、385 次 `Not enough motion`，末 0 KF、exit 139）；非话题节点、无注入点，但有官方 `SaveAtlas/LoadAtlas` |

共同前提：**必须先区分"输入故障 vs 算法故障"**；把降采样帧当正常输入重放会重演发散。**不能把 FAST-LIVO2 的实现默认平移到其它宿主。**

## 4. ALI-H（自适应低信息健康）

| 项 | 状态 |
|---|---|
| 设计/契约/预注册协议 | 完成（`ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md` §1–§10；`T2_PROTOCOL.md` 预注册） |
| T0（旧 402/544 资格） | 完成：Run A 95 AVAILABLE/307 UNAVAILABLE、Run B 132/412；I 通道 0；shadow 全 UNKNOWN |
| T1（构造控制） | 7/7 PASS |
| T2（v11 既有 run） | I 462 行（真 SE(3) Log + 单位权 `|e_I|²` p50 1.1726e-3）；M 175 / T 306；106 块全 UNKNOWN；**资格三层**：`RAW_HEADER_CONTAINMENT`（v11 PASS / v7 HEURISTIC_UNPROVEN）、`SAME_UPDATE_PRE_POST` PASS、`COMPLETE_POINT_MEMBERSHIP` ASSERTED_NOT_VERIFIED、`COVARIANCE_6D` NOT_AVAILABLE；18 条 `eff=0` 单列 |
| 分类/误报/漏检/延迟/错误 NORMAL | **NOT_EVALUABLE** —— 缺独立正常参照与事件标签（`ALI-B2` 等待用户选 A/B/C） |

三个实现缺陷在窗口内被审阅指出并由本机复现后修正：SE(3) Log 平移漏 `V⁻¹`、缺块跨空窗累计 dwell、协方差切空间未绑定；另修时间索引错配（92/504 行）。

## 5. 阻塞与未完成

1. **`ALI-B2-NORMAL-LABELS-20261112-01`（等用户）**：缺独立正常前缀与事件标签 → 分类与错误率无法评价。选项 A（用户给独立数据）/ B（自注入标签仅离线 + 独立正常前缀）/ C（只交资格与 UNKNOWN）。
2. **环境（平台层）**：`/proc/loadavg` 为宿主机全局值（容器约 2.8/128 核）；16 个 2026-11-06 起、属本会话的 `mmlins_ws` 孤儿进程占约 2.4 核，**终止操作被本机权限拦截，等用户授权**；FAST-LIO2 首次 run 因此 FAIL，重跑在新门控下 PASS。
3. **FAST-LIVO2 在线恢复缺口**：合法 ≤qstart checkpoint、拒绝后历史追赶（`catch_up=NOT_IMPLEMENTED`）、完整缓存等价、独立净收益。
4. **四宿主恢复层**：全部 NOT_IMPLEMENTED；MM-LINS 无测量注入点的结构性限制已记录。

## 6. 窗口内未执行（如实）

- 未在四宿主上实现/运行任何 slam_recovery 恢复层接线（仅接口分析与原生验证）；
- 未做大规模参数扫描、未改冻结科学阈值；
- ALI-H 未取得分类效果（等用户决定证据来源）。

## 7. 用户需要决定的最小事项

1. `ALI-B2` 选 A / B / C；
2. 是否终止 §5.2 的 16 个本会话遗留进程（影响宿主算力，不影响当前已完成证据）；
3. 四宿主恢复层的下一个优先宿主与验收范围（建议：LIO-SAM，因其单节点且**有话题级测量注入点**，最接近已验 FAST-LIVO2 形态）。
