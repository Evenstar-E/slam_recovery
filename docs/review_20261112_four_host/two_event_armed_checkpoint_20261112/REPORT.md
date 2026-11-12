# 每戳武装 checkpoint + 开段作废 snapshot：restore 戳早于触发，但第二段尾部差 0.47 s

驱动改动（本分支）：开段先 `expire_pending(0.0)` 再发幂等 `hold`；每个 scripted 戳各预排一次
`hold <stamp>` + `snapshot <stamp>`；scripted run **关闭滚动快照**（滚动快照会在触发后应用并
覆盖武装 checkpoint）。同 bag、宿主 v5（`9e7d8cdf…`）、检测 off、两戳同前、损坏只第一窗口。

## 1. 目标项：restore 戳早于第二触发（成立）

| 项 | 值 |
|---|---|
| 第二触发 | `1627785308048271418` |
| 武装 snapshot 应用戳 | **`1627785308048271360`**（早 58 ns） |
| 第二段 restore ack `stamp_ns` | **`1627785308048271360`**，frame 814 |
| 滚动快照 | **关闭**（本 run `snapshots=2`，只有两次武装快照；`superseded=1`） |

开段时 pending snapshot 被作废、hold 仍发出；第二个戳也有自己的武装 hold/snapshot。restore 不再
用触发后才应用的滚动 checkpoint。

## 2. 第一段：完整

触发 `1627785276215170145`，accepted Mode 2（after 7.3024，Wilson 0.8947）；`reprocess`
437 帧 [276.281966925 .. 290.824749470]，**within_end=124 / suffix=313**，`repairs applied=23`、
leftover 0，地图 20154 voxels/375577 points；**无 set_state**；关闭 → rearm → resume。

## 3. 第二段：决策完成，但关闭落在 bag 之外（尾部差 0.47 s）

- 触发 `1627785308048271418`，决策 312.25，**Mode 3 拒绝**（after 18.199；Wilson 自身过线，
  信息量增益不过 2×22.06）；
- 原生 `restore` 使用武装 checkpoint（308.048271360），resume 未发出——**段在退出时仍
  `WAITING_FOR_EVIDENCE`，`open=true`**。
- 原因：该段的 `wait_offset=7.335 s`（决策入口/评估期间继续登记的帧把 `t_end` 推到 319.383），
  关闭应为 `t_end+2 s = 321.383`，而 bag 最后帧是 320.909——**差 474 ms**，关闭从未执行。
  这不是 restore 或 checkpoint 的问题，是**尾部不够**。

**可用最晚戳**（按本 run 的 wait_offset）：关闭 = 触发 + margin 4 + wait_offset 7.335 + wait 2
= 触发 + 13.335 s；要 ≤ 320.909，触发须 ≤ **307.574**。bag 里可用的最后一个 ≤ 该值的帧是
**kf 416，`1627785307441937447`（307.442）**，之后还有 **127 帧**（关闭约 320.78，尾段约 6 帧）。
建议的第二戳 `308.048` 在本 run 的负载下晚了 0.47 s；上一 run（`075652`）同戳能关闭，是
wait_offset 更小（~5 s）。**没有重制 bag。**

## 4. 两 run 的状态

| run | 第二段 restore 戳 | 第二段关闭 | 终态 |
|---|---|---|---|
| `075652Z_224499`（仅 min 戳武装、滚动快照在） | 308.590（晚 0.54 s） | 319.184，完成 | HEALTHY |
| **`080204Z_228057`（每戳武装、滚动快照关）** | **308.048271360（早 58 ns）** | **未发生（321.383 > 320.909）** | **WAITING_FOR_EVIDENCE，open=true** |

两项目标分别成立于两 run：restore 戳的修复在后者；第二段完整关闭在前者。要在**同一 run**
里同时成立，需要一个更早的第二戳（≤307.574，建议 kf 416 的 307.442，留 127 帧）。是否按该戳
再跑一次，等决定。

## 5. 边界

- 门/阈值/σ 未动；可用性诊断暂停；损坏只第一窗口；不声称修复收益。
- `wait_offset` 随负载变化（本 run 7.335，上一 run ~5），第二戳的尾部余量是负载相关的。

## 6. 文件

`receipt.json`、`run_summary.json`（两段 episode 的 wait_offset/state）、`candidates.jsonl`
（2 行）、`candidates_detail.jsonl`、`icp_detail.jsonl`、`relay_frames.jsonl`、`host.log`
（两次武装 snapshot、restore 的 stamp、reprocess 的 within/suffix）、`lifecycle_events.json`
（只有第一段的 close+rearm）、`native_checkpoint_events.json`、`host_control/`、
`launch_pair.sh`、`recovery_node.log`、`machine_load.txt`、`recovery_node_source.sha256`。
