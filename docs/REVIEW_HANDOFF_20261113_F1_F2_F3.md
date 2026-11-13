# 审阅交接：FAST-LIO 18:00 任务的全部尝试与当前状态

日期：2026-11-13（UTC+8）。面向独立审阅侧（S4/Codex）与用户。本文只记录**本机可核原件**的事实，
不把计划写成执行、不把受控接口写成自动检测、不把 0 候选写成恢复失败或成功。

状态一句话：**受控接口 PASS；两事件整链尚未发生（5 次调用，前 4 次为启动/门控缺陷，第 5 次因 host
忽略 apply stamp 而地图从未写入、0 候选）；用户已要求暂停，修复代码只做语法检查，未构建、未运行。**

## 0. 任务与授权

- 任务原件：`review/repair-f3-handoff-20261110@1b28fe3`，
  [FASTLIO_ALI_AUTODETECTION_E2_TASK_20261113.md](FASTLIO_ALI_AUTODETECTION_E2_TASK_20261113.md)。
  目标 2026-11-13 18:00 前在 FAST-LIO 上贯通"真实测量修复→合法完整原生状态/地图起点→历史重估与地图重建→
  后继接回→重武装→第二事件及尾段"，ALI-H 资格/校准并行；保持 1 研究（S3）+ 2 原生集成/宿主（S1/S2）。
- 用户中途授权：追加 **1 次**整链 run（同二进制、同 bag、约 250 s、不新增构建/安装/扫描）。
- 用户最新指令（本文件写入原因）：**先暂停，把当前所有尝试与状况提交 GitHub 给审阅侧**。
  因此 v3 修复**未构建、未运行**；部署二进制仍是 `df27a24c…`。

## 1. F1：宿主原生恢复（S2，`fastlio2_ws`，仅前端无 PGO）

### 1.1 代码版本

| 版本 | 内容 | 二进制/状态 |
|---|---|---|
| v1 | 命令通道、hold、snapshot/restore、reprocess、relay、input_fates | 构建成功；ctrl1 暴露 reprocess 自锁（同一 `std::mutex` 递归加锁） |
| v2 | 修自锁（调用方持锁）、把"已收到/已应用"分开、快照存/恢复 IMU+LiDAR 时间游标、`flg_EKF_inited` | `df27a24c…`，**ctrl2 通过**；整链第 5 次使用此二进制 |
| v3 | armed hold/snapshot：带 stamp 入队，`lidar_end >= stamp` 帧边界执行；无时间基返回 `valid=0 reason=no_timebase` | **仅 `g++ -fsyntax-only` 通过，未构建、未运行**（`native_recovery_v3_deferred.diff`） |

能力声明（v2 `capabilities.json`）：`snapshot/restore/hold=YES`、`reprocess=PARTIAL`、`set_state=NO`、
`measurement_relay=YES`；`checkpoint_contents=[eskf_state, eskf_cov, ikdtree_points, time_cursor]`；
`checkpoint_excludes=[imu_preintegration_cache, deskew_cache, external_poses_graph]`。
**不称"完整检查点"**：`p_imu` 的预积分/去畸变内部状态不在 cp 内。

### 1.2 受控接口 ctrl2：PASS（CONTROLLED_INTERFACE_TEST，120 s）

原件 `docs/four_host/fastlio_recovery_20261113/ctrl2/`（S1 已核 `commands.log`、`capabilities.json`、v2 diff）：

```
hold      → OK hold valid=1 stamp_ns=1711547901476817920 frame=179 map_writes=held
snapshot A→ OK snapshot valid=1 stamp_ns=1711547902576681472 frame=190 map_points=27513
resume    → OK resume valid=1 ... map_writes=released
restore   → OK restore valid=1 stamp_ns=1711547902576681472 frame=190
reprocess → OK reprocess replay_suffix=0 replay_within_end=83 repaired_fed=1 source=buffer
snapshot B→ OK snapshot valid=1 stamp_ns=1711547918976743168 frame=354 map_points=71690
status    → OK status valid=1 repair_received=1 repair_applied=1 frame=355
```

- relay 修复云 `stamp=1711547908.776 points=25155`；`input_fates` 982 replayed / 261 ingested / 12 quarantined；
- 地图 27513 → 71690（restore 后由重放重建，不是旧轨迹复制）；
- 标签：**CONTROLLED_INTERFACE_TEST**；不证明自动检测、不证明整链、不证明净收益。

### 1.3 整链调用台账（全部保留原件）

| # | 配置/目录 | 结果 | 根因（S1 复核） |
|---|---|---|---|
| ① | wait-limit 0，`two_event_invalid_driver/` | 播放 102/260 s 主动停 | driver 未启动（`-I` 忽略 PYTHONPATH，`ModuleNotFoundError`），无任何恢复动作 |
| ② | `$PY -I -m` + `--`，`two_event2/` | pre-bag 退出 | argparse 把 `--` 当位置参数 |
| ③ | runpy + `setsid`，`two_event3_gate_misfire/` | pre-bag | `$!` 是 setsid 包装 PID，liveness 门控误判并 SIGINT 健康 driver |
| ④ | runpy 无 setsid，`two_event4_gate_logbuf/` | pre-bag | driver stdout 重定向到文件为**块缓冲**：门控 3 s 时日志 0 字节（本机实测复现），误杀健康 driver |
| ⑤ | `-u` + ROS 图门控，`two_event5_hold_ignored_stamp/` | 完整 260 s，**0 候选** | **host 忽略 `hold`/`snapshot` 的 apply stamp**：启动即 hold、空图快照，地图自第一帧起不写 |

第 5 次关键原件：

- `ctl/ack`：`OK snapshot valid=1 stamp_ns=-1000000000 frame=0 map_points=0`；
- `native_checkpoint_actions`：两次 `hold`/`snapshot` 均在启动后 0.5–1 s 被 ack（不是 E1/E2 时刻）；
- host `input_fates.jsonl`：**2248 条全部 `fate=quarantined`**（第一帧起，hold 已生效）；
- driver `run_summary.json`：`paired=1004, ingested=1004, fed_to_step_frame=0`、`quarantine.episodes=0`、
  `scripted_triggers.fired=[]`、`run_mode=CONTROLLED_TRIGGERS_NOT_FIRED`、`final_state=HEALTHY`、
  `wall_sec=260.027`、`peak_rss_kb=2185368`；
- driver 帧诊断止于 `ts=1711547984175518990`（bag ≈100.5 s），bag 实际播到 259.99 s；
- host 日志出现 `Over-degeneracy ... construct a new map`、`Rebuild thread terminated normally`。

因果链（有原件支持，但**不是**对 FAST-LIO 算法质量的结论）：host 在启动时立即 hold → 地图不写 → 前端约 100 s
后退化/重建并停发 `/Odometry` → E1（`1711547999352267771`）与 E2（`1711548113452267771`）从未到达 →
0 候选、0 episode。

### 1.4 未证事项（明确 NOT）

- 未证明 E1→接回→E2→尾段的整链；未证明拒绝/超时/追赶分支在 FAST-LIO 上实际工作；
- 未证明完整历史重估（`p_imu` 缓存不在 cp，`reprocess=PARTIAL`）；
- 未证明自动检测（所有触发为 scripted；`--detection off`）；
- 未证明测量修复的净收益（无独立参考、无 GT）。

## 2. F2：ALI-H 资格与校准（S3，`exp/ali-h-v1@f85de73`）

- 交付 `F2_FASTLIO_CHANNEL_ELIGIBILITY.md`：同 update 绑定源码位置（`laserMapping.cpp:803-804/849/869/872/884-885`、
  `esekfom.hpp:1621-1622`、`use-ikfom.hpp:12-20` 23 DoF、`SOn.hpp:233-236` 右乘）已由 S1 逐条核对；
- **T 在 FAST-LIO 结构上不存在**（只有 ikdtree 地图更新，无 prev-scan 更新）→ `NOT_APPLICABLE`，不得用 M 冒充；
- 读取器 `f2_fastlio_read.py` + 合成自检 **8 用例全 PASS**（S1 本机复跑）；
- `rosbag info campus_12_fl.bag`：469 s / 98580 条，**只有 `/imu_raw` 93885 + `/velodyne_points` 4695，无 GT/参考**；
- 资格：`SAME_UPDATE_CALL_BINDING`/`PRE_POST_POSE_IDENTITY` 待 F1 导出；`COMPLETE_POINT_MEMBERSHIP=ASSERTED_NOT_VERIFIED`；
  `COVARIANCE_6D=NOT_AVAILABLE_FOR_E_I`；
- **BLOCKED**：B1（同 update 导出缺失，待 F1）、B2（无独立正常前缀，参考必须来自本数据集之外）、
  B3（无本 host 故障标签；声明式注入不并入 F1 预算）、B4（T 不存在）；
- 召回/延迟/误报/错误 NORMAL：`NOT_EVALUABLE`，不填 0。

## 3. F3：共享 driver/manager（S1，main）

- 能力声明 `capabilities.json`（只认 `YES`；`PARTIAL` 可用但记限制；缺失/损坏为 `UNDECLARED`）；
- `reprocess != usable` → 不发重放、不发布修复云，记 `reprocess_unsupported`；`restore != YES` → 不发回滚，记 `restore_unsupported`；
- `replay_disposition=PARTIAL` 携带 `partial_notes`；解析 `repaired_fed` 并记 `repair_entered_estimator`；
  `set_state=NO` 时不再发写回，记 `set_state_unsupported`；
- summary 新增 `host_capabilities` 与 `message_disposition`（ingested/quarantine memberships/distinct/
  never_quarantined/committed/deferred/pending + `unresolved`，不默认 healthy）；
- 测试：`test_host_capabilities.py` 14 项，全套 **238 项通过**；
- 这些只在 ctrl2 的真实 host 上走过一部分；第 5 次整链中 driver 行为正确（0 候选、脚本触发未到），
  **未**在真实 E1/E2 上验证。

## 4. 当前暂停与待决

- 用户指令：暂停。**没有构建、没有运行**；v3 代码只在 `exp/growth-run@ce3aaac`，二进制仍 `df27a24c…`。
- 需要用户决定：是否授权 **1 次修复构建 + 1 次最小整链复验**（同 bag、同 E1/E2、`--wait-limit-sec 20`、
  `-u` + ROS 图门控）。若授权，验收观察点：启动后 ack 为 `OK hold deferred stamp=…`（不是 frame=0）、
  E1 前地图持续增长、E1 到达时 hold/决策/restore/reprocess 的 ack 带真实 `stamp_ns/frame` 与 `repaired_fed`。
- 审阅侧可裁决的问题：
  1. `hold/snapshot` 的 apply stamp 语义是否应作为接口契约的一部分（v3 已按 FAST-LIVO2 语义实现）；
  2. `reprocess=PARTIAL`（缓冲重放、p_imu 缓存不入 cp）是否足以称"原生重估"，还是必须补齐缓存才能叫恢复；
  3. 无 GT、无独立正常前缀下，ALI-H 只能交 shadow/UNKNOWN，是否接受这一范围。

## 5. 证据索引

- 任务与接受：`main` 提交 `c80f50b`（任务文档 + 分发记录）、`1b28fe3`；
- F1 受控与代码：`exp/growth-run@326413b`（v1/v2、ctrl1/ctrl2）、`@ce3aaac`（v3 源码、台账、5 次原件）；
- F2：`exp/ali-h-v1@f85de73`（文档、读取器、selftest、bag 证据）；
- F3：`main` 提交 `538e86a`、`eb94249`、`a355343`、`52eda17`、`0b343ae`；
- 协作日志：`docs/COLLABORATION_STATUS.md` §178–§184；
- 宿主台账：`docs/four_host/fastlio_recovery_20261113/LEDGER.md`。

## 6. 不得引用为结论的事项

- 不把 ctrl2 的 PASS 当成整链或自动检测通过；
- 不把第 5 次的 0 候选当成"FAST-LIO 不能恢复"或算法失败——它是本地接口缺陷（hold 忽略 stamp）；
- 不把 `map_points` 增长、`repair_received=1`、`repaired_fed=1` 单独当成净收益；
- 不把 `final_state=HEALTHY` 当成正常/无故障；
- 不把 FAST-LIO 派生前端当成上游原版或独立宿主源码级实现。
