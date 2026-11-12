# 候选帧集冻结后的 A/B：人口一致，重放跨度仍不一致（停，报原因）

同声明的一对运行：`repair/`（发布修复）与 `control/`（`--repair-dry-run`，不发布）。
冻结在 `_track_episode` 越过 deadline 的帧上完成。

## 1. 冻结生效：人口与门一致

| 项 | repair | control |
|---|---|---|
| run | `fl_native_20261112T051523Z_107073` | `fl_native_20261112T051728Z_109595` |
| freeze | `frozen_at_ns=1627785280281185627`，**23 帧** | 同一时刻，**23 帧** |
| `frames_after_freeze` | 357 | 359 |
| 门 | accepted：3.1341 → **7.3427**，Wilson 0.8947，holdout 0.4185，committed 23 | accepted：3.1341 → **7.3482**，Wilson 0.8947，holdout 0.4091，committed 23 |
| 偏差估计 | +0.40（MAD 0.05） | +0.35（MAD 0.05） |
| 修复 | **23/23 收到并应用**，synced | 0/0 |

冻结前两次的候选是 32 vs 23；冻结后是 **23 vs 23**，冻结戳逐位相同，门结果几乎相同
（after 7.3427 vs 7.3482，Wilson 相同）。这一项达标。

## 2. 仍不一致：重放跨度（按你的要求停下，不再多跑）

| 项 | repair | control |
|---|---|---|
| `reprocess` 重放帧 / 跨度 | **815 帧 / 27.14 s** [276.349 .. 303.492] | **692 帧 / 23.08 s** [275.081 .. 298.159] |
| 重放后地图 | **24503 voxels / 473187 points** | **21870 voxels / 418979 points** |
| set_state 时 `state_pos` | 7.706, 5.651, −0.366 | 7.725, 5.608, −0.370 |
| resume 时 `state_pos` | 7.130, 5.536, −0.435 | 6.933, 5.080, −0.234 |

原因（已定位）：**`reprocess` 命令发出的时刻不同**。repair 方案在决策后要先完成 3 批发布
（23 条，含每批 `status` 回执），control 的 dry-run 估计完就直接发 `reprocess`。宿主从"最后
一个快照"一直捕获到"它应用 `reprocess`"的那一刻，所以 repair 的缓冲区多覆盖了约 **5.3 s / 123
帧**（其中大部分在损坏窗口之外）。起点也差 1.27 s（快照周期决定）。地图差异因此**不能归因于
修复**；能干净比较的是候选人口、门结果、修复计数（23/23 vs 0/0）和 set_state 位姿——后者两边
只差约 **6 cm**，与"同一 ICP 候选、同一最后一帧"一致。

## 3. 下一步（未跑，等你定）

要隔离修复对重放轨迹/地图的效应，需要让两次的 `reprocess` 在同一时刻发出。两个做法：

1. **sham 对照**：同样分批发布、同样回执、同样时序，但发布的是**未加修正的损坏云**（bias=0）。
   两次的重放跨度应一致，唯一差别是云是否被修正。这是最干净的隔离。
2. 或在 control 里加一段与发布+回执等长的等待再发 `reprocess`；时序对齐但语义上更人工。

按"仍不一致就停下报原因"的要求，本轮没有跑 sham，也没有再跑更多。门/阈值/σ/宿主未动。

## 4. 能/不能声称

- 能声称：冻结使候选人口与门结果在两次之间一致（23/23，冻结戳相同）；修复云 23/23 进入重放。
- 不能声称：地图 24503 vs 21870 是修复造成的（重放跨度不同）；任何修复收益。
- 损坏为自注入；宿主 0 行改动。

## 5. 文件

`repair/`、`control/` 各自的结构同前：`receipt.json`、`run_summary.json`（含
`frame_freeze`）、`candidates.jsonl`、`candidates_detail.jsonl`、`icp_detail.jsonl`、
`relay_frames.jsonl`、`host.log`、`lifecycle_events.json`、`native_checkpoint_events.json`、
`host_control/`、`launch_pair.sh`、`recovery_node.log`、`machine_load.txt`、
`recovery_node_source.sha256`。
