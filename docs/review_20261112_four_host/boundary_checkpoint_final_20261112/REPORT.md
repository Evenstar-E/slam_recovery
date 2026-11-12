# checkpoint 不晚于隔离边界：两段都成立（宿主 v6）

同声明两事件 run：第一戳 `1627785276215170145`、第二戳 `1627785306371636152`（306.3716），
margin 4.0、wait 2、检测 off、ICP 候选源、损坏只第一窗口。武装 hold/snapshot 的应用戳改为
**声明戳 − margin**（即 manager 的 `t_q_start`），宿主 `cp_stamp_` 改为"最后一个已处理组"的
lio_time。宿主库 `ca9126c4…`，驱动见 receipt。

## 1. 边界核对

| 项 | 值 | 判定 |
|---|---|---|
| 第一段 `t_start`（lifecycle） | `1627785272215170145` | — |
| 第一段 reprocess ack `stamp_ns` | **`1627785272199251712`** | **早 15.9 ms ≤ t_start** ✔ |
| 第二段 `t_start` | `1627785302371636152` | — |
| 第二段 restore ack `stamp_ns` | **`1627785302359221248`** | **早 12.4 ms ≤ t_start，且早于第二触发 306.3716** ✔ |

两段的 checkpoint 都在各自隔离起点之前，不再有"滚动/开段快照晚于触发"的回退不全。

## 2. 两事件

| | 事件 1 | 事件 2 |
|---|---|---|
| 触发 | `1627785276215170145` | `1627785306371636152` |
| 结果 | **accepted Mode 2** | **Mode 3 拒绝** |
| 原生 | hold（自 t_start）→ **reprocess** → resume | hold（自 t_start）→ **restore** → resume |
| 重放 | **794 帧 [272.265811205 .. 298.692232847]**，`within_end=244 / suffix=550`，repairs applied=**23**、leftover 0，地图 27805/564227 | — |
| 写回 | **无 set_state**（suffix>0 跳过） | — |
| 关闭 / rearm | 291.826 → rearm | **319.184 → rearm** |

终态 **HEALTHY / open=false**；`candidates.jsonl` 2 行；lifecycle 4 条；两段都完整关闭并 resume；
尾段到 320.909（关闭后约 1.7 s）。

`within_end=244` 比之前的 124 大，是因为 checkpoint 提前到 t_start（隔离起点），重放从隔离起点
开始覆盖确认窗口；修复云仍只匹配候选窗口的 23 帧。

## 3. 边界

- 门/阈值/σ/检测未动；损坏自注入（+0.5 z，第一窗口）；不声称修复收益。
- 武装戳 = 声明戳 − margin 是声明常量；不改 manager 的 `t_q_start` 语义。
- checkpoint 戳由"最后一个已处理组"决定，仍依赖宿主应用延迟（本 run 15.9/12.4 ms 早于边界）；
  若负载更大导致晚于 t_start，按约定停、报差值。

## 4. 文件

`receipt.json`、`run_summary.json`、`candidates.jsonl`、`candidates_detail.jsonl`、
`icp_detail.jsonl`、`relay_frames.jsonl`、`host.log`、`lifecycle_events.json`、
`native_checkpoint_events.json`、`host_control/`、`launch_pair.sh`、`recovery_node.log`、
`machine_load.txt`、`recovery_node_source.sha256`。
