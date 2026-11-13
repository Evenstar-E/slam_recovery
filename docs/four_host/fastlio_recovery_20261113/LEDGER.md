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
- **但整链仍 FAIL（0 候选）**：host 在 bag ≈ **93 s** 进入原生退化-重建循环（`Over-degeneracy` 8 次、
  `IMU Initial Done` 163 次），**停止发布 `/Odometry`**；driver 的位姿流止于 bag 93.0 s，E1（116 s）
  从未到达，`scripted.fired=[]`。这与 v4 无关（hold 在 116 s 才生效，之前 1137 帧均为 ingested）。
- `input_fates`：ingested 1137 / quarantined 1113（首个 quarantined 恰为 E1−2 s），无 replayed。
- 对照：此前同 bag 的完整 469 s 运行（独立构建）在 E1 处仍能发布位姿（停发于 E1+0.02 s）；本 run 的
  93 s 停止更早，原因未定（负载/退化阈值与输入时序相关，需进一步验证；本次不重试）。
