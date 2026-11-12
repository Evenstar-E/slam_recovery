# 对照：同管线、同损坏、只关掉修复发布（dry-run）

`--repair-dry-run`：偏差估计照常执行（决策成本与修复 run 相同），但不发布任何修复云、不做
receipt 校验；重放使用原始（损坏）扫描。其余与 `../success_batched/` 完全相同。

## 1. 运行

| 项 | 值 |
|---|---|
| run | `fl_native_20261112T050645Z_102106` |
| 驱动 | 提交 `8790452`（含 dry-run） |
| 宿主 | `0d7e23de…`，0 行改动 |
| 终态 | `HEALTHY` |

## 2. 结果

| 项 | 值 |
|---|---|
| 门 | accepted，Mode 2：before 3.1341 / after 7.3487 / Wilson 0.8949 / holdout 0.4080 |
| episode 帧 | 23 |
| 偏差估计 | median **+0.40**，MAD 0.05（估计了，未发布） |
| 修复 | `published=0`，宿主 `repair_received=0 repair_applied=0` |
| 重放 | `reprocess #1: 529 frames replayed over [275.147 .. 292.759] … repairs applied=0` |
| 重放后地图 | **20427 voxels / 373515 points** |
| set_state / resume 时 `state_pos` | 7.725, 5.606, −0.369 / 5.154, 6.602, 0.229 |

## 3. 与修复 run 的对照限制（必须读）

| 项 | 修复（045944Z） | 本对照（050645Z） |
|---|---|---|
| episode 帧 | 32 | **23** |
| 重放帧 / 跨度 | 676 / 274.881–297.426 | **529 / 275.147–292.759** |
| 重放后地图 | 22334 voxels | **20427 voxels** |
| 修复 received/applied | 32 / 32 | 0 / 0 |

两次的决策入口落在不同的帧集上（配对流帧数随负载变化），重放跨度相差 147 帧。因此地图与
`state_pos` 的差异**不能全部归因于修复**；能干净比较的只有修复计数（32/32 vs 0/0）与
`repairs applied=32 vs 0`。要隔离修复效应，需要把决策绑定到固定帧而不是墙钟 service tick，
这是一项驱动改动，未在本轮实施。

## 4. 边界

- 损坏为自注入；不声称真实修复收益或恢复成功率。
- 本对照只证明"关掉发布后同一管线仍能 accepted 且重放使用原始扫描（applied=0）"。
- 门/阈值/σ/宿主未动。

## 5. 文件

同 `../success_batched/` 的结构：`receipt.json`、`run_summary.json`、`candidates.jsonl`、
`candidates_detail.jsonl`、`icp_detail.jsonl`、`relay_frames.jsonl`、`host.log`、
`lifecycle_events.json`、`native_checkpoint_events.json`、`host_control/`、`launch_pair.sh`、
`recovery_node.log`、`machine_load.txt`、`recovery_node_source.sha256`。
