# 串行化之后的受控接纳 run：`fl_native_20261112T022158Z_4156288`

同一份声明（kf 132 的绝对位姿戳）、同一 bag、同一 margin 4.0、`--detection off`；只换了驱动
（合入 `bbe916f` 的命令串行化）。本目录是原 run 目录的原件副本。

## 1. 身份

| 项 | 值 |
|---|---|
| run_id | `fl_native_20261112T022158Z_4156288` |
| bag | `/tmp/fastlivo/hall01_two_event_v1.bag`，sha `c3e905da…` |
| 宿主二进制 | `0d7e23de…`（未变；宿主源码未改） |
| 驱动源码 sha | `18d92a03…`（含 `bbe916f` 的 `_outbox`） |
| 触发 | `1627785276215170145`（kf 132），`fired.ts_ns` 与之逐位相等 |
| margin / wait limit | 4.0 s / 2.0 s |
| 启动负载 | `352.99 298.35 209.15`（高） |
| 终态 | `HEALTHY`，wall 107.8 s |

## 2. 门（仍是同一个候选总体，未改协议）

| 量 | 值 |
|---|---:|
| before / after | 3.1388 / 6.6761（阈值 ≥ 6.2776） |
| 比值 | 2.127 |
| Wilson / holdout | 0.9197 / 0.4412 |
| 模式 | `MODE2_ATOMIC_COMMIT`，`accepted=true` |
| committed / deferred | **31 / 81**（仍是 partial） |
| 生命周期 | `wait_limit_closed` → `rearm`；**无 `commit_closed`**（预期，见上一 run 的断点 1） |

## 3. 命令串行化的效果（本轮要核对的就是这些）

`native_checkpoint.events` 里 hold 之后依次是 `reprocess → set_state → resume`，**各一条**：

| 命令 | 写出 | received | applied | received−sent | applied−received |
|---|---:|---:|---:|---:|---:|
| hold | 1794450174.384 | 1794450174.389 | 1794450174.630 | 0.005 | 0.241 |
| reprocess | 1794450177.670 | 1794450177.671 | 1794450183.170 | 0.001 | **5.500** |
| set_state | 1794450183.170 | 1794450183.172 | 1794450183.670 | 0.002 | 0.498 |
| resume | 1794450183.670 | 1794450183.673 | 1794450184.170 | 0.003 | 0.497 |

- 驱动侧计数：`reprocesses=1`、`resumes=1`、`restores=0`、`failures=9`（全部是 snapshot 超时）。
- 三条 ack 自身的累计计数也证明顺序（不依赖驱动记账）：
  reprocess `hold=1 set_state=0 restores=1 live_voxels=19194`；
  set_state `hold=1 set_state=1 restores=1 live_voxels=19194`；
  resume `hold=0 hold_commands=2 set_state=1 live_voxels=19194`。
- **`reprocess` 真的执行了**：`host.log` 有
  `[NATIVE_CHECKPOINT] reprocess #1: 416 frames replayed over [1627785274.681 .. 1627785288.545],
  repairs applied=0 queued=0, map now 19194 voxels/362286 points`。
- 宿主 ack 的 `restores=1` 是 `reprocessCheckpoint` 内部先 restore 再重放造成的，
  **不是** 驱动发了 `restore` 命令（驱动 `restores=0`）；这一点看 `cmd.done` 与 events 即可区分。
- 重放构成：`LIO frames=208 with_points=164 empty=44 | VIO frames=208`，
  `total_undistorted=1193687`。VIO 帧没有 lidar 点，属于预期，不是丢点。
- resume ack：`hold=0 held_frames=171 held_points=495589 hold_commands=2 set_state=1`。
- 重放后地图从 checkpoint 的 `15161 voxels/298650 points` 变为 `19194/362286`；
  resume 之后滚动快照继续增长：`21330 → 29486 → … → 60425 voxels`，共 26 次快照。

## 4. LIO / 地图在重放后是否异常

- 无新的 `[ERROR]`/`[ WARN ]`（日志里两条都在启动阶段：`Data Cut`、`Reset ImuProcess`）。
- `average residual`：重放前最后 1000 条中位 **0.0512**、最大 0.167；重放后 2274 条中位
  **0.0529**、最大 0.251。没有台阶式变化。
- 本轮 `host.log` 末尾**没有** `double free`（上一 run 有，已单独记录，未推测原因）。
- 说明：上一 run 用 "hold 窗口内 `Update Voxel Map` = 0" 作为停写证据；本轮这个指标**不再适用**，
  因为 `reprocess` 在重放期间会临时清掉 `map_hold_` 以便写图（`LIVMapper.cpp:931-977`）。
  本窗口内的 164 次 `Update Voxel Map` 全部来自重放本身，这是设计行为，不是停写失效。
  停写仍然把**普通帧**挡在 `UpdateVoxelMap` 之外：resume ack 的 `held_frames=171`。

## 5. 文件

| 文件 | 内容 |
|---|---|
| `receipt.json` / `wiring.json` / `run_summary.json` | 收据、接线、完整汇总 |
| `candidates.jsonl` / `candidates_detail.jsonl` | 门结果（18-key）与输入全集 |
| `lifecycle_events.json` / `native_checkpoint_events.json` / `.tsv` | 生命周期与 40 条命令账本 |
| `host.log` | 宿主全文（含 `reprocess #1`、重放 points 行） |
| `host_control/{ack_received,cmd.done}` | 末条 receipt 与已消费命令；本轮最后一条快照超时，`ack` 不存在 |
| `map_write_evidence.json` | 由 `../map_write_evidence.py` 生成；resume 边界取驱动账本 |
| `ros_home_log/`、`launch_pair.sh`、环境文件 | 配方与 ROS 日志 |
| `SHA256SUMS` | 完整性 |
