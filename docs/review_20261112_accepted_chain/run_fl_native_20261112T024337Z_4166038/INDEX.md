# 同一份受控 run 里的第二事件：`fl_native_20261112T024337Z_4166038`

第一次事件仍是被接纳的那次写回；第二事件在其放写之后、bag 结束之前由第二个脚本触发点打开。
两次触发都只声明、不挑门的结果：第一事件被接受，第二事件被拒绝，按门自己判。

## 1. 身份

| 项 | 值 |
|---|---|
| run_id | `fl_native_20261112T024337Z_4166038` |
| bag | `/tmp/fastlivo/hall01_two_event_v1.bag`，sha `c3e905da…`，60.0 s（未改/未重制） |
| 宿主二进制 | `0d7e23de…`（未变） |
| 驱动源码 sha | `18d92a03…`（含 `_outbox` 串行化） |
| 触发（声明） | `1627785276215170145`（kf 146）、`1627785308048271418`（kf 422） |
| margin / wait limit | 4.0 s / 2.0 s |
| 启动负载 | `34.08 49.75 128.02` |
| 终态 | `HEALTHY`，`quarantine_open_at_exit=false`，wall 102.6 s |

`scripted_triggers.fired` 两条的 `ts_ns` 与声明逐位相等（实际 14.811 s / 46.644 s，均以第一帧为 0）。
第二戳选在**第一次放写之后**：第一段在 bag 287.011 关闭并 rearm；第二戳在 308.048，距离第一段关闭
**210 帧**、距离 bag 末帧 320.909 还有 **122 帧**。

## 2. 两次事件的门结果

| | 事件 1 | 事件 2 |
|---|---|---|
| trigger（bag ns） | 1627785276215170145 | 1627785308048271418 |
| 决策（bag ns） | 1627785280281185627 | 1627785312188321114 |
| 候选帧 | 23 | 41 |
| before / after | 3.1388 / **7.2154** | 22.0638 / 17.6808 |
| 比值 | 2.299 | 0.801 |
| Wilson / holdout | 0.8947 / 0.4369 | 0.8304 / 0.4677 |
| 证据 | PASSED | PASSED |
| 模式 | `MODE2_ATOMIC_COMMIT`，**accepted** | `MODE3_SOFT_BRIDGE_WAIT`，**refused** |
| committed / deferred | 23 / 62 | 0 / 0 |
| 拒绝原因 | — | 信息量增益不达 Mode 2 阈值，维持软桥等待 |

第二事件是**事件**，不是接纳：它开段、决策、关闭、放写都发生了，门拒绝了候选。没有为了让它
"好看"去改帧、改门或挑时间。

## 3. 两次事件的完整时序

### 事件 1（接纳 + 写回）

| 时刻（wall） | 事件 | 备注 |
|---|---:|---|
| 1794451460.967 | `hold` 发出 | 段打开 |
| 1794451461.473 | `hold` applied | |
| 1794451462.862 | `reprocess` 发出 | 决策后 |
| 1794451466.473 | `reprocess` applied | **3.611 s**（重放） |
| 1794451466.473 | `set_state` 发出 | applied 466.973 |
| 1794451466.973 | `resume` 发出 | applied 467.473，`trigger=rearm` |

段在 bag 287.011 关闭（`wait_limit_closed`，`:deferred`）→ `rearm` → 驱动发 `resume`。

### 事件 2（开段 → 决策 → 关闭 → 放写）

| 时刻（bag ns） | 事件 |
|---|---|
| 1627785308048271418 | 第二戳触发，段打开（`quar_270_1627785304048271418`，t_start = 触发 − 4 s） |
| 1627785312188321114 | 决策：Mode 3 拒绝 |
| 1627785315388730764 | `wait_started`（段 t_end） |
| 1627785317389723063 | 段关闭（`wait_limit_closed`） |
| — | `rearm`（from `ABORTED`，trusted_version 270）→ 驱动发 `resume` |

原生命令（wall）：

| 命令 | 发出 | received | applied | applied−received |
|---|---:|---:|---:|---:|
| hold | 1794451493.978 | 1794451493.982 | 1794451494.473 | 0.491 |
| restore | 1794451498.858 | 1794451498.863 | 1794451499.359 | 0.496 |
| resume | 1794451500.860 | 1794451500.863 | 1794451501.598 | 0.735 |

`restore` 是拒绝路径的正确动作；宿主日志有
`restore #2: live map 37335 voxels/838421 points -> 36511 voxels/798215 points`。
resume ack：`hold=0 held_frames=248 restores=2`。

## 4. 两次之间的帧与终态

- 触发 1 → 触发 2：**276 帧**；
- 第一次关闭（287.011）→ 触发 2：**210 帧**；
- 触发 2 → bag 末：**122 帧**；
- `frames.consumed_after_first_decision = 349`；
- 终态 `HEALTHY`，两段都无未决隔离；`candidates.jsonl` **2 行**；
- 原生计数：`holds=2`、`resumes=2`、`restores=1`、`reprocesses=1`、`snapshot_ack_timeouts=0`；
- 数据面：最后一条快照 `live_voxels=44633`，地图在两次事件后仍在增长。

## 5. 边界（照实写）

- 第二事件是 **refused**，不是第二次接纳；`commit_closed` 依旧没有出现（协议未改）。
- 第一事件的提交仍是 partial（23 / 62），放写来自 wait 超时 + `rearm`，与上一 archive 的结论一致。
- 本轮没有 `double free`，也没有 snapshot 超时。
- 本 run 的 hold 窗口不能用 `Update Voxel Map` 计数判断停写：事件 1 有 `reprocess`、事件 2 有
  `restore`，两者都会改地图（宿主设计）。停写对普通帧的约束看 `held_frames`（126 / 248）。

## 6. 文件

| 文件 | 内容 |
|---|---|
| `receipt.json` / `wiring.json` / `run_summary.json` | 收据、接线（两段都可达）、完整汇总 |
| `candidates.jsonl` / `candidates_detail.jsonl` | 两行门结果与两行输入全集 |
| `lifecycle_events.json` | 4 条：两次 `wait_limit_closed` + 两次 `rearm` |
| `native_checkpoint_events.json` / `.tsv` | 42 条命令账本（含 trigger 列） |
| `host.log` | 宿主全文（`reprocess #1`、`restore #2`） |
| `host_control/` | 末条 receipt 与已消费命令 |
| `ros_home_log/`、`launch_pair.sh`、环境文件 | 配方与 ROS 日志 |
| `SHA256SUMS` | 完整性 |
