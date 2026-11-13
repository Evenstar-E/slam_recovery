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
