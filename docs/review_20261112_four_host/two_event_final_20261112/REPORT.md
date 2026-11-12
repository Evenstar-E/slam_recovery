# 同一实例：修复接回 → 第二事件（留足尾部）→ 尾段，全部完成

同 bag、宿主 v5（`9e7d8cdf…`）、驱动含"每戳武装 checkpoint + 开段作废 snapshot + scripted 关
滚动快照"、检测 off、`candidate_source=icp_reregistration`、margin 4、wait 2。损坏只在第一
窗口（触发 1 起 6 s）。第二戳按尾部预算取 **kf 405 / `1627785306371636152`（306.372 s）**，
之后还有 139 帧；实测关闭在 316.258，尾段 **39 帧 / 4.65 s**。

## 1. 两事件

| | 事件 1 | 事件 2 |
|---|---|---|
| 触发 | `1627785276215170145`（kf 146） | **`1627785306371636152`（kf 405）** |
| 决策 | 280.481 | 310.69（+4.32 s） |
| 候选帧 | 23 | 40 |
| 门 | **accepted Mode 2**：after 7.3001，Wilson 0.8947，committed 23 | **refused Mode 3**：after 19.6156（信息量增益不过 2×22.06；Wilson 自身过线） |
| 原生 | hold → **reprocess**（repairs applied=23；within=124 / **suffix=379**；**无 set_state**）→ resume | hold → **restore**（武装 checkpoint）→ resume |
| 关闭 / rearm | 289.149 / v102 | **316.258 / v232** |
| 重放 | 503 帧 [276.281966925 .. 293.025721073]，地图 21578/403642 | — |

## 2. 目标核对

- **第二段 restore `stamp_ns=1627785306303834368`（306.3038），早于触发 `1627785306371636152`
  约 67.8 ms**；滚动快照关闭，`snapshots=2`（只有两次武装快照）、`superseded=0`。
- **第二段 close → rearm → resume 实际执行**：`lifecycle.events` 4 条（两次 close + 两次
  rearm），第二次 resume 的 `trigger=rearm`；`quarantine_open_at_exit=false`，终态 **HEALTHY**。
- **尾段 39 帧 / 4.65 s**（关闭 316.258 → bag 末 320.909）。
- 第一段仍 **accepted + `repairs applied=23` + `replayed_suffix=379` + 无 set_state**；地图
  21578 voxels/403642 points。
- `candidates.jsonl` **2 行**；两个触发戳逐位命中；holds=4 / resumes=2 / restores=1 /
  reprocesses=1。

## 3. 与上一 run 的尾部对比

| run | 第二戳 | wait_offset | 关闭 | 结果 |
|---|---|---:|---|---|
| `080204Z_228057` | 308.048 | 7.335 | 321.383（>320.909） | 未关闭，open=true |
| **`080914Z_233068`** | **306.372** | **1.284** | **316.258** | **完成，HEALTHY，尾段 39 帧** |

`wait_offset` 本 run 更小（1.284 s），提前的戳也留出了余量；两项（restore 戳早于触发 + 第二段
完整关闭）现在在同一 run 同时成立。

## 4. 边界

- 门/阈值/σ 未动；可用性诊断暂停；损坏只第一窗口（+0.5 z，60 帧）；不声称修复收益。
- 第二段用武装 checkpoint（每戳预排）；滚动快照在 scripted run 关闭是已实现的机制。

## 5. 文件

`receipt.json`、`run_summary.json`、`candidates.jsonl`（2 行）、`candidates_detail.jsonl`、
`icp_detail.jsonl`、`relay_frames.jsonl`、`host.log`（两次武装 snapshot、restore stamp、
reprocess within/suffix、close/rearm）、`lifecycle_events.json`、`native_checkpoint_events.json`、
`host_control/`、`launch_pair.sh`、`recovery_node.log`、`machine_load.txt`、
`recovery_node_source.sha256`。
