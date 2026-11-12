# 后缀重放时跳过 set_state：状态与地图都停在边界

同声明受控 run（kf 132、margin 4.0、损坏窗口从触发戳起、声明戳 hold/snapshot、检测 off、
`candidate_source=icp_reregistration`）。宿主 v5 在 reprocess ack 暴露 `replay_suffix`，驱动在
后缀 >0 时跳过 `set_state`。

## 1. 结果

| 项 | 值 |
|---|---|
| run | `fl_native_20261112T074154Z_215075` |
| `reprocess` | 454 帧 [276.281966925 .. 291.358868361]，**replayed_within_end=124，replayed_suffix=330**，repairs applied=23、leftover 0 |
| 重放后地图 | **20625 voxels / 380221 points** |
| reprocess ack `state_pos` | **5.796264, 7.677180, 0.181549**（边界 291.36 处） |
| `set_state` | **未发送** |
| record | `replay_suffix=330`；`native_writeback_skipped={reason:"replay_suffix"}`；`native_writeback` 为空 |
| resume ack `state_pos` | **5.761748, 7.652826, 0.182390**（与边界差约 3.6 cm） |
| 终态 | HEALTHY |

修复 23/23、leftover 0 不变；后缀组用原始测量重推；reprocess 与 resume 的 `state_pos` 几乎相同，
**没有上一次的 3.9 m / 15 s 回拨**；状态与地图都停在捕获边界。

## 2. 命令顺序

`hold`（开段幂等）→ 声明戳 `hold/snapshot`（触发帧执行）→ 发布修复 10/10/3 + 累计回执 →
`reprocess <frozen+100ms>`（ack 带 replay_suffix）→ **跳过 set_state** → `rearm` 后 `resume`。
`native_checkpoint_events` 里没有 set_state 条目，只有 reprocess 与 resume。

## 3. 边界

- 不声称修复收益；损坏为自注入。门/阈值/σ 未动；可用性诊断继续暂停，未改检测。
- 后缀数随负载变化（本 run 330，上一 run 448），within_end 仍是 124、修复仍 23。
- 若跳过 set_state 后出现别的不同步，本 run 未出现：resume 与 reprocess 的状态差 3.6 cm。

## 4. 文件

`receipt.json`、`run_summary.json`（episode meta 的 `replay_suffix` /
`native_writeback_skipped`）、`candidates.jsonl`、`candidates_detail.jsonl`、
`icp_detail.jsonl`、`relay_frames.jsonl`、`host.log`（`replayed_within_end/replayed_suffix`、
ack 的 `state_pos`）、`lifecycle_events.json`、`native_checkpoint_events.json`、
`host_control/`、`launch_pair.sh`、`recovery_node.log`、`machine_load.txt`、
`recovery_node_source.sha256`。
