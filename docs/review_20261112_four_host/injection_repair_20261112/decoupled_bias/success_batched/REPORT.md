# 分批 + 累计回执：修复云 32/32 送达并进入重放

同 bag、同绝对戳 `1627785276215170145`、同 relay 窗口、margin 4.0、`candidate_source=icp_reregistration`。
发布改为每批 ≤10 条 + 累计回执（声明见上一层 `PLAN_batched.md`）。

## 1. 运行

| 项 | 值 |
|---|---|
| run | `fl_native_20261112T045944Z_96435` |
| 驱动 | 提交 `8790452`（sha 见 `recovery_node_source.sha256`） |
| 宿主 | `0d7e23de…`，0 行改动 |
| 终态 | `HEALTHY` |

## 2. 结果

| 项 | 值 |
|---|---|
| 门 | **accepted**，Mode 2：before 3.1341 / after 6.8326（阈值 6.2682）/ Wilson 0.9220 / holdout 0.3700 |
| committed / deferred | 32 / —（episode 32 帧） |
| 偏差 | **median +0.45 m**，MAD 0.05，逐帧 0.25–0.65（32 帧），容差内 |
| 修复发布 | **32 条，4 批（10/10/10/2）**，每批回执 `received_ok=true`，`final_received=32 = baseline+published`，**synced=true** |
| 宿主接收/应用 | `repair_received=32 repair_applied=32 repair_dropped=0` |
| 重放 | `reprocess #1: 676 frames replayed … repairs applied=32 queued=0`，地图 **22334 voxels/417461 points** |
| `[NATIVE_REPAIR] applied` | **32 行** |
| 顺序 | hold → 发布 32（4 批）→ receipt 32 → reprocess → set_state → rearm 后 resume |

时间（wall）：hold 625.30；reprocess 638.74→647.74（9.0 s，含 676 帧重放）；set_state
647.74→648.24；resume 648.24→648.79（`trigger=rearm`）。

## 3. 与无修复对照（`../control_dryrun/`）

| 项 | 修复 | 对照（dry-run，不发布） |
|---|---|---|
| 偏差估计 | +0.45 | +0.40（同样估计，不发布） |
| 门 | accepted 3.1341→6.8326/Wilson 0.9220 | accepted 3.1341→7.3487/Wilson 0.8949 |
| episode 帧 | 32 | 23 |
| 修复 received/applied | 32 / 32 | 0 / 0 |
| 重放帧 | 676（[274.881 .. 297.426]） | 529（[275.147 .. 292.759]） |
| 重放后地图 | 22334 voxels/417461 | 20427 voxels/373515 |
| set_state 时 state_pos | 8.540, 6.411, −0.340 | 7.725, 5.606, −0.369 |
| resume 时 state_pos | 8.593, 5.590, −0.560 | 5.154, 6.602, 0.229 |

**能干净比较的只有修复计数**：32/32 vs 0/0，且 `[NATIVE_REPAIR] applied` 32 行。地图、状态和
重放帧数的差异**不能全部归因于修复**：两次的 episode 帧数（32 vs 23）和重放跨度（676 vs 529）
都不同——配对流的帧数随负载变化，决策入口落在不同帧上。修复 run 的 set_state 与对照相差
约 1.15 m（8.540,6.411,−0.340 vs 7.725,5.606,−0.369），方向与"修复后轨迹回到可信地图"一致，
但两边的最后一帧不同，不能当作干净的轨迹效应。

要真正隔离效应，需要固定决策帧集（例如决策绑定到固定的 kf 而不是墙钟 service tick），这是一项
驱动改动，本轮没有做。

## 4. 边界

- 损坏是自己注入的（+0.5 body-z，60 帧），不能声称真实修复收益或恢复成功率。
- 修复云确实进入了宿主重放（`repairs applied=32`），这是本轮成立的事实；它是否让估计更接近
  真值，只有上面的受混杂对照，不下结论。
- 门/阈值/σ/宿主未动。

## 5. 文件

`receipt.json`、`run_summary.json`、`candidates.jsonl`、`candidates_detail.jsonl`、
`icp_detail.jsonl`、`relay_frames.jsonl`、`host.log`、`lifecycle_events.json`、
`native_checkpoint_events.json`、`host_control/`、`launch_pair.sh`、`recovery_node.log`、
`machine_load.txt`、`recovery_node_source.sha256`。
