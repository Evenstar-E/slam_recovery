# F1 FAST-LIO 原生恢复：调用台账与状态

日期：2026-11-13。宿主机 `fastlio2_ws`（MM-LINS 派生前端），scope 仅前端（无 PGO）。

| # | 配置 / 分支 | 结果 | 原因 | 原件 |
|---|---|---|---|---|
| ① | wait-limit 0（无限等待），driver 正常 | 已播放 **102 s**，无恢复动作，主动停 | 无限等待会让被拒段永不关闭、E2 永不触发 | `two_event_invalid_driver/` |
| ② | wait-limit 20，`python -I -m` + `--` | pre-bag 失败 | `-I` 忽略 PYTHONPATH；`--` 被 argparse 当位置参数 | `two_event2/` |
| ③ | wait-limit 20，runpy，`setsid ... &` | pre-bag 失败 | `$!` 是 setsid 包装 PID，liveness 门控误判并 SIGINT 健康 driver | `two_event3_gate_misfire/` |
| ④ | wait-limit 20，runpy，无 setsid | pre-bag 失败 | driver stdout 块缓冲，日志 3 s 内为空导致门控误判 | `two_event4_gate_logbuf/` |
| ⑤ | wait-limit 20，`-u` + ROS 图门控 | 完整 260 s，**0 候选** | **host 忽略 hold/snapshot 的 apply stamp**：启动即 hold、空图快照（`map_points=0`、`stamp_ns=-1000000000`），地图自第一帧起就不写，FAST-LIO 约 100 s 退化后停发 `/Odometry`，E1/E2 永远到不了 | `two_event5_hold_ignored_stamp/` |

## 受控接口（独立于整链）

`ctrl2/`：hold → snapshot A（map_points=27513）→ resume → restore → reprocess（`replay_within_end=83`、
`repaired_fed=1`）→ snapshot B（71690）；`repair_received=1 repair_applied=1`。标签 CONTROLLED_INTERFACE_TEST。

## 修复（已写代码，未构建、未运行，等授权）

v3 diff（`native_recovery_v3_deferred.diff`）：
1. **armed hold/snapshot**：带 apply stamp 的命令入 `g_nr_deferred`，在 `g_nr_lidar_end >= stamp` 的帧边界执行；
   ack 为 `OK <cmd> deferred stamp=<ns>`；无 stamp 的命令仍立即执行。
2. **no_timebase**：未初始化时间基时不再输出 `stamp_ns=-1000000000`——`hold/snapshot` 返回
   `valid=0 reason=no_timebase`，`status` 返回 `stamp_ns=NA no_timebase=1`。
3. 语法检查（`g++ -fsyntax-only`，同一组 include/defines）通过；**未构建**，二进制仍为 `df27a24c…`。

## v4（2026-11-13，只写代码，未构建/未运行）

按审阅 §3.1–3.3 修正（`native_recovery_v4.diff`，441 行）：

1. **§3.1 延期边界与 ACK**：`nr_apply_deferred(this_group_end)` 现在在 `sync_packages` 之后、
   **该组被捕获/估计之前**执行——目标戳落在两帧之间时，hold/snapshot 在跨界组进入估计前生效，
   快照用**前一完成帧**的状态（`g_nr_lidar_end` < target）。ACK 分两级：入队 `OK <cmd> deferred
   stamp=<ns>`；执行后 `OK <cmd> applied valid=1 stamp_ns=<ns> frame=<n> [map_points=...]`。
2. **§3.2 replay 期间的写图与输入顺序**：`reprocess` 时显式释放 hold（`map_writes` 随之为 released），
   重放组按时间顺序回到缓冲区前方、先于后继实时输入被消费；新增与 update 关联的回执
   `repaired_in_update` / `last_repaired_update_ns`（`repaired_fed` 只证明入队）。
3. **§3.3 replay 标志复位**：改为**按组身份**——重放入队时写 `g_nr_replay_marks[group_end]`，
   消费时取走并决定该组的 replay/live 身份（`input_fates` 随之精确）；最后一条重放组处理完时
   复位全局标志，不再按命令发出复位。
4. 语法检查（同一 include/defines，`-fsyntax-only`）rc=0、0 errors；**未构建**，二进制仍 `df27a24c…`。
5. 回归断言 `tools/check_replay_regression.py`（只读 ctrl2 原件）：`rows=1255 replayed_label=982
   declared_replay=83 corrected_split: replay=83 live=899` → **PASS**。

## 离线确定性检查（v4，未构建/未运行）

- `tools/check_source_contract.py`：14 条源码级断言（延期调用点在 `sync_packages` 之后、`nr_capture_group`
  之前；无旧的前置调用；两级 ack 文本；`reprocess` 释放 hold；按组 replay 标记与消费；`repaired_in_update`
  暴露；排空后复位；快照戳取上一完成帧）→ **RESULT PASS**。
- `tools/check_replay_regression.py`（只读 ctrl2 原件）→ **PASS**（replay=83 / live=899）。

## §2 同边界双命令（v4 复核，2026-11-13）

- `nr_apply_deferred` 对同一 stamp 的 hold + snapshot：入队 `push_back`、应用时 `while (front.stamp_ns <= now)`
  逐项 `pop_front` 到 `due`，再按队列顺序 `nr_execute`——**FIFO、全部 due 项、都在 `nr_capture_group`/估计之前**。
  同一组内 hold 先执行、snapshot 后执行（快照取上一完成帧，与 hold 无关）。
- `check_source_contract.py` 增加 5 条断言（deque 类型、push_back、pop_front、`<= now` 全量排空、按序执行），
  现共 **19 项，全部 PASS**；`check_replay_regression.py` 仍 PASS（83/899）。

## ⑦ 授权复验（2026-11-13，v4 构建 `86f85025…`）

- 构建 1 次：`df27a24c…` → **`86f85025…`**，退出码 0（`build_v4.log`）。
- 运行 1 次（`two_event_authorized_20261113/`）：bag 播完（Done，259.99 s），driver 存活 260.6 s。
- **v4 延期语义生效**：ack 依次为 `OK hold deferred stamp=1711547997352267771`（= E1−2 s）→
  `OK hold applied valid=1 stamp_ns=1711547997274449664 frame=1137 map_writes=held` →
  `OK snapshot applied valid=1 stamp_ns=1711547997774402048 frame=1142 map_points=221815`；第二组
  E2−2 s 同样 applied（frame 2111/2117）。不再是 frame=0 / 空图。
- **但整链仍 FAIL（0 候选）**：host 在 bag ≈ **95–96 s** 进入原生退化-重建循环（口径：`frame_diagnostics` 末条相对首帧 94.70 s；`pairing` 记录的最后配对准位姿相对同一首帧 96.41 s。此前文中"93.0 s"是误用了首个**配对**帧而非首帧作基准，作废）（`Over-degeneracy` 8 次、
  `IMU Initial Done` 163 次），**停止发布 `/Odometry`**；driver 的位姿流止于 bag 93.0 s，E1（116 s）
  从未到达，`scripted.fired=[]`。这与 v4 无关（hold 在 116 s 才生效，之前 1137 帧均为 ingested）。
- `input_fates`：ingested 1137 / quarantined 1113（首个 quarantined 恰为 E1−2 s），无 replayed。
- 对照：此前同 bag 的完整 469 s 运行（独立构建）在 E1 处仍能发布位姿（停发于 E1+0.02 s）；本 run 的
  93 s 停止更早，原因未定（负载/退化阈值与输入时序相关，需进一步验证；本次不重试）。

## ⑧ A/B 诊断（2026-11-13，v4 `86f85025…`，均无 driver）

| run | 通道 | `/Odometry` | 首停发（>1 s 缺口起点） | 缺口 | `Issleeping`/`Isbuilding` | Over-degeneracy / IMU Initial |
|---|---|---:|---:|---|---|---|
| **A** | 关 | 2095 | **115.8 s** | 23.8 s；230.1 s / 26.5 s | 2 / 2（间隔 114.3 / 117.0 s） | 4 / 163 |
| **B** | 开 | 2091 | **115.7 s** | 23.8 s；229.7 s / 26.8 s | 2 / 2（间隔 114.0 / 117.0 s） | 4 / 164 |
| C（授权整链，有 driver） | 开 | 949（driver 侧） | **94.7–96.4 s** | — | — | 8 / 163 |
| 旧独立 run（`4c31fada…`，469 s） | 关 | 4186 | 115.80 s | 23.8 s；229.70 s / 26.9 s | — | — |

判读：**A ≈ B ≈ 基线**（115.7–115.8 s），**通道开销可忽略**；C 的 19–21 s 提前来自 **driver 竞争**，
不是恢复通道本身。性能口径（2026-11-13 更正）：NIS 走 `compute_disjoint_holdout_point_to_plane_nis`
（300×600 向量化），**不是** `ReferenceGrid` 最近邻；`ReferenceGrid` 只在修复偏置搜索里。逐帧成本应表述为
"扫描回调的 `cloud_to_xyz` + `subsample` 与 NIS holdout 计算"；driver 已加逐回调耗时统计
（`runtime.pose_callback/scan_callback` 的 p50/p95/max），供下一定量诊断。原件：`diag_A/`、`diag_B/`（各含 `pre_run.txt`、`host.log`、`play.log`、
`frontend.bag`、`bag_info.txt`、`analysis.json`；B 另有 `ctl/capabilities.json` 与 `ctl/input_fates.jsonl`）。

## v5（2026-11-13，只写代码，未构建/未运行）：`re_slam` 使 checkpoint 失效

共存规则第三层：即使 driver 的 sleep/build 信号丢失或未订阅，host 也拒绝用过期的 checkpoint 恢复。

- `re_slam()` 内（持 `g_nr_mtx`）置 `g_nr_cp.valid = false; g_nr_cp_invalidated_by_reslam = true;`；
- `nr_restore_locked()` 在无效时区分原因：`checkpoint_invalidated_by_re_slam`（否则 `no_checkpoint`），
  不执行 `change_x/change_P/Build`；
- 新的 `snapshot` 成功后清除该原因标志；
- `capabilities.json` 增加 `"checkpoint_invalidated_by": "re_slam (host-native reset); a new snapshot is required afterwards"`；
- `check_source_contract.py` 增加 3 条断言（re_slam 体内失效、restore 原因字符串、capabilities 声明），现共 **22 项 PASS**；
- 语法检查 `-fsyntax-only` rc=0、0 errors；**未构建**，二进制仍 `86f85025…`（v5 随下次授权构建一起生效）。

## ⑨ v5 授权复验（2026-11-13）：FAIL（driver 启动期看门狗误杀）

- 构建 1 次：`86f85025…` → **`785c0f20…`**（v5，`re_slam` 使 cp 失效），退出码 0（`build_v5.log`）。
- 运行 1 次：**driver 在启动后 15.0 s 判 `INPUT_STALE` 并退出**（`pose_messages=0, last_pose_wall=null`），
  此时 host 的首个 `IMU Initial Done` 在 driver 启动后 **18.4 s**（host 启动后 22.2 s，bag 打开后 14.0 s）。
  即 `--pose-stale-sec 15` 从**进程启动**计时，比 host 首次发布 `/Odometry` 早 3.4 s。
- 主机侧正常：通道 `channel on`、首条 ack `OK hold deferred stamp=1711547997352267771`、`input_fates` 2250 组
  （ingested 1137 / quarantined 1113）、bag 播到 `Done`；只是 driver 已退出，未收到任何位姿/扫描。
- 判读：**driver 启动期看门狗口径问题**（应在首个位姿后再计时，或加启动宽限 ≥30 s），不是 host 或恢复通道缺陷。
- 未重试、未再构建；原件 `two_event_v5_authorized/`。

## ⑩ v5b 授权复验（2026-11-13）：FAIL（driver 共存下宿主提前休眠），但拿到定量成本

- 不构建，v5 `785c0f20…`；driver 首次位姿宽限 60 s、`/Odometry` 已录制（`frontend.bag` 800 KB、259 s）。
- `input_health = OK`（silence 0.063 s，不再误报 STALE）；`message_disposition` 输入 1019 位姿 / 2510 扫描，零回调错误。
- **host_native 事件（相对 bag 首帧）**：休眠 66.2 s → 73.8 s 重建 → 81.3 s 休眠 → 94.3 s → 98.3 s；位姿流止于 **103.4 s**；
  E1 在 **117.4 s**，仍未到达 → `scripted.fired=[]`、0 候选。对照 A/B（无 driver）首次休眠 115.8 s：
  **driver 共存把宿主首次休眠提前约 50 s**。
- **定量根因**：`runtime.pose_callback` n=1018、p50 **102 ms**、p95 **1255 ms**、max **1957 ms**、mean **244 ms**
  （≈ 一个整核的持续占用）；`scan_callback` n=2510、p50 0.9 ms、p95 3.3 ms。即竞争来自 driver 的**逐位姿处理**，
  不是扫描回调或恢复通道（A/B 已排除通道）。
- 同一 run 也验证了共存策略：driver 收到宿主 sleep/build 后释放 hold（`input_fates` ingested 1274 / quarantined 978），
  `host_native.state=PUBLISHING` 收尾，未发生 restore/reprocess（无 episode），v5 的 cp 失效路径未被触发。

## ⑪ v5c 优化后授权 run（2026-11-13）：E1 首次到达；takeover 路径执行；仍非完整整链

- 不构建，v5 `785c0f20…`；driver main `16c4f71`（FIM 恒等式 + packed-unique）。
- **硬指标**：宿主首次休眠 **105.4 s**（v5b 66.2 s；无 driver 基线 115.8 s）→ 改善 39 s，仍早 10 s；
  位姿流 **1.8–232.3 s**，**首次越过 E1（117.4 s）** ✔。
- **E1 触发**：`fired=[(1711547999352267771, actual 115.6 s, kf 1092)]`，episode 1 个。
  - `hold_skipped_host_state=HIBERNATING`（宿主 105.4→141.4 s 休眠中）；
  - `host_reset_during_quarantine={signal: build, ts 1711548094.37}` → 按设计走 takeover，**不 restore/reprocess**；
  - **armed snapshot 为空图**：`hold applied frame=1136 map_writes=held`、`snapshot applied frame=1140 map_points=2`
    （E2 组 `map_points=1`）——因为宿主在休眠中已 `re_slam()` 清树。这证明"休眠期不应 snapshot"仍应补一层
    host 侧判断（v5 只让 restore 拒绝，未阻止 snapshot 拍空图）。
  - 收尾：`final_state=QUARANTINED`、`quarantine_open_at_exit=true`（takeover 后 segment 未被关闭）；E2 未触发。
- **回调成本（新旧对比）**：

| 回调 | v5b（旧） | v5c（新） |
|---|---|---|
| pose p50 / p95 / max / mean | 102 / 1255 / 1957 / 244 ms | **20 / 92 / 393 / 28 ms** |
| scan p50 / p95 / max / mean | 0.9 / 3.3 / 1493 / 4.8 ms | 1.6 / **224** / 607 / 36.8 ms |

  pose 路径改善 ~8.7×；scan 路径的 p95 反而升高（与录制/调度相关，需下次单独观察）。
- `input_fates`：ingested 1277 / quarantined 982；首个 quarantined **115.4 s**（= E1−2 s，armed hold 正确）。
- `input_health` OK（silence 0.06 s）；`message_disposition` 2063 位姿 / 2245 扫描、64 未配对位姿、246 未配对扫描。

## v6（2026-11-13，只写代码，未构建/未运行）：休眠期拒绝空图快照

针对 v5c 观察到的 `snapshot ... map_points=2`（宿主休眠/`re_slam` 后拍空图）：

- `re_slam()` 置 `g_nr_host_reset = true`；`publish_odometry()` 首次正常发布时清除；
- 该标志为真期间，`snapshot` 回 `OK snapshot valid=0 reason=host_reset_no_map`，不覆盖已有 checkpoint；
- `capabilities.json` 增加 `"snapshot_refused_after_host_reset": "until the host publishes odometry again"`；
- 契约断言增至 **26 项 PASS**（re_slam 置位、snapshot 拒绝、publish 清除、capabilities 声明）；
- 语法检查 rc=0；**未构建**，二进制仍 v5 `785c0f20…`（v6 需随下次授权构建生效）。

## ⑫ v6 授权 A/B（2026-11-13）：takeover 关段修复成立；E2 仍不可达

- 构建 1 次：v5 `785c0f20…` → **v6 `f167bf5e…`**（休眠期拒快照），退出码 0（`build_v6.log`）。

| run | 录制 | 首次休眠 | 位姿覆盖 | E1 触发 | E2 触发 | takeover/关段 | 收尾 |
|---|---|---|---|---|---|---|---|
| **A** `two_event_v6_norec` | 否 | 105.8 s | 1.7–226.5 s | ✔ 115.7 s | ✘（差 3.2 s） | `segment_abandoned=True` | HEALTHY / open=false |
| **B** `two_event_v6_rec` | 是 | 111.2 s | 1.7–199.8 s | ✔ 115.7 s | ✘（差 29.9 s） | `segment_abandoned=True` | HEALTHY / open=false |

- **driver 的 takeover 后关段修复成立**：两 run 都 `host_reset_during_quarantine(build)` → `segment_abandoned=True` → 终态 HEALTHY、`open=false`。
- **v6 的 `host_reset_no_map` 未被触发**：两 run 的 E1 armed snapshot 都拿到 `map_points=221815`（当时尚未 `re_slam`），
  E2 armed snapshot 分别为 1347 点——条件保护未满足即不拒绝，符合设计。
- **callback A/B 对比**（说明录制不是主因）：

| 回调 | A（不录制） | B（录制） |
|---|---|---|
| pose p50 / p95 / mean | 0.07 / 85 / 18 ms | 51 / 393 / 87 ms |
| scan p50 / p95 / mean | 62.7 / 430 / 94 ms | 1.1 / 171 / 26 ms |

  两 run 方向相反、量级都远高于算法本身，**主导因素是宿主休眠/积压下的突发处理与调度**，不是 `rosbag record`。
- E2 不可达的量化原因：E2 在 bag 229.7 s，而 driver 的位姿流在 A 止于 226.5 s、B 止于 199.8 s；宿主在 E1 后继续
  多次 sleep/rebuild，未能在 E2 前恢复稳定发布。
- `input_fates`：A ingested 1268 / quarantined 982；B 1270 / 980。

## v7（2026-11-13，只写代码，未构建/未运行）：契约 semantics 块

- `capabilities.json` 新增 `semantics`：
  `{"apply_stamp":"YES","ack_levels":["deferred","applied"],"checkpoint_validity":"until_re_slam","publish_gating":"isPublish","profile":"native_recovery"}`；
- 离线验证：从 C++ 字符串字面量重建整份 JSON 并用 `json.loads` 解析 → **合法**，顶层键含 `semantics`；
- `check_source_contract.py` 增 5 条断言（五项字段），共 **31 项 PASS**；
- 语法检查 rc=0；**未构建**，二进制仍 v6 `f167bf5e…`（v7 随下次授权构建生效）。

## 预算门槛（driver 侧，供记录）

`bench_frame_cost.py --rate 10 --max-core-fraction 0.25`：FIM≈82 ms + NIS≈12 ms ≈ 94 ms/对 → **0.94 核，FAIL**
（与 v6 A/B 的 ~112 ms/对一致）。降到 0.25 核需声明式降采样（`max_eval_points` 1200→600 或
`scan_cap` 减半），会改变 FIM/NIS 人口，待用户批准与离线等价证据；本项不在 host 侧。

## ⑬ v7 授权 run（2026-11-13）：契约校验通过；宿主在 E1 后停止发布，驱动看门狗终止整链

- 构建 1 次：v6 `f167bf5e…` → **v7 `a40e20d5…`**（semantics 块），退出码 0。
- **契约**：`host_contract=DECLARED`，`semantics` 五项齐全 → `--require-contract` 在放 bag 前通过（bag 正常开始）。
- **预算诊断**（不阻塞）：`bench_frame_cost` total 47.5 ms/对、**0.475 核**、`--max-core-fraction 0.25` 下 status FAIL（exit 1），按用户决定只记录。
- **E1 触发** 115.7 s；armed `hold applied valid=1 stamp_ns=1711547997274449664 frame=1137 map_writes=held`、
  `snapshot applied valid=1 stamp_ns=1711547997575793920 frame=1140 map_points=221815`。
- **宿主在 117.7 s 后停止发布**：`host_native` 只记录到一次 111.4 s 的瞬断（111.5 s 即"发布"），driver 状态保持
  `PUBLISHING`，因此 15 s 常规 STALE 判据生效：`pose stream stale for 15.2 s ... stopping the run`，
  运行在约 133 s 结束（`terminal_reason=INPUT_STALE`），**未走 90 s 休眠上限分支**。
- 决策：episode 1 个，`decided=True`、`decision_basis=bag_end`、候选 `cand_0000`、mode `MODE4_HARD_SLEEP_SPLIT`、
  `accepted=False`、3 帧；`final_state=ABORTED`、`open=false`。E2 未到达。
- 回调：pose n=1161、p50 58.5 / p95 255 / max 415 / mean 84.8 ms；scan n=1392、p50 1.1 / p95 55 / max 289 / mean 7.0 ms。
- `input_fates`：ingested 1137 / quarantined 1113（首次 quarantined 于 E1−2 s）。
- 判读：契约路径已验证；整链仍因**宿主在 E1 后长时间静默且未发出可用休眠信号**而无法覆盖 E2——属宿主原生行为与
  driver 状态映射（瞬断→PUBLISHING）的组合，不是接口契约问题。

## ⑭ 信号窗授权 run（2026-11-13）：E1 静默期不再误杀；E2 仍因宿主后续停机未达

- 不构建，v7 `a40e20d5…`；新增 `--host-signal-window-sec 30`；契约通过（`host_contract=DECLARED`）。
- **E1 静默期的看门狗修复验证成功**：`host_native` 记录 `sleep 113.6 → build 117.7 → publish 141.4`；
  driver 全程存活 260 s，`input_health` 期末 `status=OK`、`silence_s=0.198`，**没有 STALE 误杀**
  （v7 那次曾在 133 s 被 STALE 终止，只差 1.3 s）。
- **E1 触发** 115.7 s（kf 1157）；armed ack：`hold applied frame=1137 map_writes=held`、
  `snapshot applied frame=1142 map_points=221815`；episode `hold_skipped_host_state=HIBERNATING`、
  `host_reset_during_quarantine(build, ts 1711547999675624847)`、`segment_abandoned=True`；
  **收尾 HEALTHY / open=false**。
- **E2 未触发**：宿主在 E1 之后继续多轮 sleep/build（160.2、192.5、201.0 s），位姿流止于 **211.1 s**，
  E2 在 229.7 s。`scripted.fired` 仍只有 E1。
- 回调：pose n=1856、p50 53 / p95 387 / max 756 / mean 81 ms；scan n=2505、p50 1.1 / p95 153 / max 406 / mean 25 ms。
- `input_fates`：ingested 1274 / quarantined 978；resume 多次（每轮宿主发布后）。

## ⑮ 排空授权 run（2026-11-13）：E1 与 E2 均触发；E2 在排空期决策为 Mode 3 等待

**非实时声明**：本 run 播放 260 s，driver 墙钟上限 360 s，bag 结束后排空 60 s 再 SIGINT。
E2 的帧在排空期被处理；其 `actual_s=229.696` 是 **stamp 时间**，墙钟晚于 bag 结束，因此本 run 是
"逻辑链验证"，不是实时性能证据。

- 不构建，v7 `a40e20d5…`；契约通过；录三轻量话题。
- **`scripted.fired` 两条**：E1 `115.599 s`（kf 1156）、**E2 `229.696 s`（kf 2054）**。
- ep0（E1）：`hold_skipped_host_state=HIBERNATING`、`host_reset_during_quarantine(build)`、`segment_abandoned=True`；
  lifecycle `segment_abandoned` + `rearm`。
- ep1（E2）：触发 `1711548113473230600`，决策于 `1711548141172342539`（rel ≈259.9 s），
  mode **`MODE3_SOFT_BRIDGE_WAIT`**、1 个候选 `cand_0001`、`accepted=false`；无 host 重置。
- 收尾 `WAITING_FOR_EVIDENCE`、`open=true`：Mode 3 的等待段在 run 结束（排空后 STALE）前未关闭。
- `poses_received=2085`（录制 2091）、`max_backlog=501`、`paired=2085`；`input_fates` ingested 1269 / quarantined 982。
- **逐阶段成本**（`frame_cost_breakdown`）与回调：

| 阶段 | n | p50 | p95 | max | mean |
|---|---:|---:|---:|---:|---:|
| **ingest** | 2083 | 51.4 | 216.8 | 522.4 | **69.9 ms** |
| nis_measure | 2085 | 15.6 | 372.9 | 636.9 | 54.7 ms |
| pose_callback（含两者+配对/分发） | 2085 | 61.9 | 450.6 | 1028.1 | 98.4 ms |
| scan_callback | 2600 | 1.1 | 158.9 | 393.0 | 24.3 ms |

  最长项：**`ingest`（mean 69.9 ms，占 pose_callback mean 的约 71%）**；`nis_measure` 次之（54.7 ms）。
  仅标注，未做任何修改。

## v8（2026-11-14，A1+A2 run 1）：hold 生效、checkpoint 存活、restore 首次成功；门拒绝健康段

二进制 `1491433f…`（v8：`native_reset_under_hold=deferred`）；driver `d9e4f34`+（JIT 边界武装、
hold 归属、run-end 关闭）；`PLAY_RATE=0.5`（**非实时**，driver ~6 Hz 才追得上宿主 10 Hz）。
E1 声明 113.500 s（宿主自身 `Issleeping` 前 2.3 s），E2 227.000 s。

- 武装：hold 于 108.6 s 写入、apply stamp 111.5，宿主在 frame 1117 **held**；snapshot frame 1119、
  `map_points=221670` → checkpoint 有效。
- **v8 的对称共存规则生效**：宿主在 ~117.0 s 进入退化、发 `Issleeping`，但**没有** `re_slam`；
  `restore valid=1 stamp_ns=…5474589952 frame=1119` —— 这是真实退化事件上**第一次回滚成功**
  （此前 drain/v7 都是 `checkpoint_invalidated_by_re_slam`）。
- 段内 20 帧（此前同事件只有 3 帧）：因为 hold+snapshot 提前 2.3 s 落在宿主停发之前。
- **门拒绝**：`candidate_source=host_poses`，`num_improved_frames=0/20`、`wilson_lower=0`、
  `MODE3_SOFT_BRIDGE_WAIT`。原因可从数字读出：平台近乎静止（vel ≈0.01 m/s），"候选=宿主位姿"
  与"incumbent=常速外推"几乎相同，没有可测的改善；这不是阈值问题，是候选定义问题。
- **死锁**：拒绝后段进入 `WAITING_FOR_EVIDENCE`，而等待只在**帧到达**时计时。宿主被 hold 且已退化
  → 停发 → 等待永不结束 → hold 永不释放 → 90 s 休眠上限终止 run（bag 207 s），E2 未到达。
- 附带证据：snapshot 实际落在 111.698 s，比声明边界 111.5 s 晚 0.2 s（`checkpoint_check=LATE_AFTER_BOUNDARY`）。

修复（run 2 前）：
1. 等待的墙钟出口：`maybe_close_waiting_segment(..., elapsed_s=)` + driver `_close_stalled_wait`
   （2 Hz 主循环里计时，无帧也能关段并 rearm→resume）。
2. accepted 路径改用 `icp_reregistration`（11-12 三次 accepted 的 run 全部是这条路径；
   `host_poses` 在静止平台上原理上无法改善）。
3. v9：hold 期间继续发布 `/Odometry`（`publish_gating=isPublish+held`，capabilities 已声明），
   否则段永远只能覆盖宿主 onset 之前的健康帧。

## v9（2026-11-14，A1+A2 run 2）：段覆盖退化、ICP 候选 9/13 改善；第二事件仍未触发（ABORTED 无人 rearm）

二进制 `aa04c5ff…`（v9：`publish_gating=isPublish+held`）；driver `d9e4f34`+；`PLAY_RATE=0.5`（非实时）；
E1/E2 回到**清单原始声明** 115.599 / 229.696 s；`candidate_source=icp_reregistration`。

- **v9 生效**：hold 期间宿主继续发 `/Odometry`，段内 13 个配对帧（v8 在 onset 只有 ~1–3 帧）。
- **checkpoint 完全合规**：`checkpoint_check=AT_OR_BEFORE_BOUNDARY`（snapshot frame 1138、
  `map_points=221815`，边界 113.6，实际 113.6）——JIT 武装把上一轮的 0.2 s 迟到消掉了。
- **v8 的 reset 推迟仍然生效**：宿主 115.98 s 退化，`Issleeping` 后**继续发布**（sleep→publish 抖动，
  无 `re_slam`），cp 一直有效。
- **ICP 候选首次有改善**：`num_improved_frames=9/13`（69%），`candidate_mean_residual 1723` <
  `incumbent 1986`，`wilson_lower=0.465` < 门槛 → `MODE4_HARD_SLEEP_SPLIT` 拒绝。
  ICP 自身 `status=ITERATION_LIMIT`（20 次未收敛），`icp_residual=0.033 m`，
  `correction_translation_m` 很大但 `reentry_pos_jump_m=0.217 m`——是绕远点旋转的平移分量，不是漂移 16 m。
- **E2 未触发（fired 1/2）**：Mode 4 把 manager 留在 **ABORTED**；re-arm 依赖“下一帧”走 detector 路径，
  而 `--detection off` 的脚本化 run 永远不走那条路径 → 管理器整轮停在 ABORTED，E2 的 `HEALTHY` 前提不成立。
  `lifecycle.events=[]`、`state_after=ABORTED`、`unresolved=0` 都是这条链的证据。

修复（run 3 前，纯 driver，无需重建）：
- `_close_stalled_wait` 新增终态分支：`ABORTED && active_quarantine is None` → `detector.reset(); rearm()`
  （与 `step_frame` 的既有规则同一条），使脚本化 run 在拒绝后能回到 HEALTHY 并接收第二事件。

## v9b（2026-11-14，A1+A2 run 3）：**两事件全链生命周期闭合**；两次真实事件均被门拒绝

二进制不变 `aa04c5ff…`；driver 只加了终态 rearm。`PLAY_RATE=0.5`（非实时）；E1/E2 = 清单原始声明。

链路（全部有宿主 ack 原件）：
| 步骤 | E1 | E2 |
|---|---|---|
| 触发 | 115.599 s / kf 1156 | 229.696 s / kf 2084 |
| hold | frame 1136 `map_writes=held` | frame 2088 `held` |
| snapshot | frame 1137，`map_points=221370` | frame 2091，`map_points=165950` |
| checkpoint 合规 | `AT_OR_BEFORE_BOUNDARY` | `LATE_AFTER_BOUNDARY`（晚 0.2 s） |
| 段帧数 | 12 | 11 |
| 门 | **拒绝** 改善 3/12，wilson 0.105，MODE4 | **拒绝** 改善 1/11，wilson 0.021，MODE3 |
| 回滚 | `restore valid=1` frame 1137 | `restore valid=1` frame 2091 |
| 释放 | rearm→`resume` frame 1139 | wait 20 s 关闭→rearm→`resume` frame 2145 |

- `run_mode=CONTROLLED_INTERFACE_TEST`，`fired 2/2`；`lifecycle` 事件依次为 rearm / wait_limit_closed / rearm，
  退出时 `state=HEALTHY`、`unresolved=1`、无悬挂段。**A1 达成**：E2 的 Mode 3 等待段按声明关闭。
- **A2 未达成**。拒绝原因可从 ICP 原件读出：段内只有一个刚体变换（`mode=single_rigid_transform_for_the_segment`），
  E1 的 ICP 给出 `correction_rotation_deg=26.6`、`translation=25.1 m`、`status=ITERATION_LIMIT`（20 次未收敛）。
  平台近乎静止而 ICP 接受了 26° 的解（`icp_residual=0.03 m`，低残差但不是真解），说明该段几何对这种单刚体拟合是**病态**的。
  E2 同样 `ITERATION_LIMIT`，修正 2.9°/3.5 m，改善 1/11。
- 与 run 2 对比：同样声明戳、同一二进制，E1 改善率从 9/13 掉到 3/12——候选**不稳定**，因为 20 次迭代未收敛、
  初值附近存在多个低残差极小。这不是阈值问题，是候选生成器的问题。
- 尾部：E2 释放后宿主按原生策略再次退化并停发，driver 在 15 s stale 判定处结束（bag ≈250 s，非排空到尾）。
