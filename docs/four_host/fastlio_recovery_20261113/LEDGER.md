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
