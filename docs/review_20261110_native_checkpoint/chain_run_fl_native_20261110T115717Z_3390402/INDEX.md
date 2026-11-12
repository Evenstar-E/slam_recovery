# 受控整链归档：`fl_native_20261110T115717Z_3390402`

本目录只把**原 run 目录的已有文件**集中起来并给索引；不新增解释。原目录仍在
`/tmp/fl_native_20261110T115717Z_3390402`（`/tmp` 不保证长期存在，本目录是副本）。

## 1. 运行身份

| 项 | 值 |
|---|---|
| run_id | `fl_native_20261110T115717Z_3390402` |
| 模式 | `CONTROLLED_INTERFACE_TEST`（`--detection off`，声明触发 `14.6,42.0`） |
| pgid / host pid / driver pid | `3391481` / `3391483` / `3391484` |
| 输入 bag | `/tmp/fastlivo/hall01_two_event_v1.bag`，sha `c3e905da…` |
| 宿主二进制 sha | `0d7e23de…`（见 `receipt.json`；与当前 devel 产物一致） |
| 运行时长 | wall 103.053 s |
| 机器负载（启动时） | 见 `machine_load.txt`；`nproc=128` |
| 终态 | `HEALTHY`，`quarantine_open_at_exit=false` |

命令行原文见 `command.txt` 与 `launch_pair.sh`。

## 2. 文件清单

| 文件 | 内容 |
|---|---|
| `receipt.json` | 运行收据：status/reason/termination、输入 sha、launch 参数、exit codes、headline |
| `wiring.json` | 5 项接线检查（同一进程组、双 topic、配对、NIS 来源、门可达）+ `all_ok` |
| `run_summary.json` | 驱动侧完整汇总（544 帧诊断、NIS、门、生命周期、原生动作 44 条） |
| `candidates.jsonl` | 两条候选的 18-key 冻结流（每行一条） |
| `candidates_detail.jsonl` | 每次决策的**输入全集**（帧 id、时间戳、位姿）；语义见 `../SIDECAR_SEMANTICS.md` |
| `lifecycle_events.json` | 从 `run_summary.json` 原样抽出的 `lifecycle.events`（4 条） |
| `native_checkpoint_events.json` | 从 `run_summary.json` 原样抽出的 `native_checkpoint.events`（44 条，逐命令） |
| `received_applied.tsv` | 由上面 44 条按 `wall / received_wall / ack_wall` 列出的视图（派生视图，原值可回查 json） |
| `host_control/{ack,ack_received,cmd.done}` | 命令目录的**残留文件**：最后一条 snapshot 的 applied ack、received 收据、已消费命令 |
| `host.log` | 宿主 stdout/stderr 全文（2.5 MB；含 36 条 `[NATIVE_CHECKPOINT] snapshot`、2 条 `restore`、1 条控制线程 `control`） |
| `recovery_node.log` / `recovery_node_source.sha256` | 驱动进程日志与源码 sha |
| `ros_home_log/` | ROS 侧 `rosout.log`、`master.log`、`roslaunch-*.log` 副本 |
| `launch_pair.sh` / `command.txt` | 启动配方 |
| `machine_load.txt` / `python_version.txt` / `runtime_lib.txt` / `runtime_pid.txt` / `runtime_pgid.txt` | 环境事实 |
| `LIO_TIMING_STATUS.md` | 逐帧 LIO 耗时这一项的归档状态（见第 6 节） |

`SHA256SUMS` 给出本目录所有文件的 sha256。

**未收录**（原目录里有、均为输入回放/框架噪声，且可由上面配方重放）：
`play.log`（870 KB）、`roscore.log`（空）、`supervisor.log`（空）、`ros_home/roscope-*.pid` 等。

## 3. 时间线（bag 时间，t0 = 第一帧 `1627785261.000000000`）

| 事件 | 段 0 | 段 1 |
|---|---:|---:|
| 声明触发 / 实际触发 | 14.6 / 15.082 | 42.0 / 42.426 |
| 决策时刻 | 17.282 | 45.236 |
| 结果 | `MODE3_SOFT_BRIDGE_WAIT`，`accepted=false` | `MODE3_SOFT_BRIDGE_WAIT`，`accepted=false` |
| 段关闭（`wait_limit_closed`） | 22.546 | 49.057 |
| `rearm`（from `ABORTED`） | 紧随关闭 | 紧随关闭 |
| 原生动作 | `hold → restore → resume` | `hold → restore → resume` |
| 候选帧数 | 13 | 27 |
| 段内 unresolved 帧 | 58 | 86 |
| trusted_version | 119 | 288 |

两段之间（段 0 决策后到段 1 触发前）消费 **368 帧**（`frames.consumed_after_first_decision`）。

## 4. 原生命令账本

44 条命令的逐条记录在 `native_checkpoint_events.json`，平铺视图在 `received_applied.tsv`：

| 命令 | 次数 | 成功 | 说明 |
|---|---:|---:|---|
| `snapshot` | 37 | 30 | 滚动快照；7 次 ack 超时（见第 5 节） |
| `hold` | 2 | 2 | 段打开时 |
| `restore` | 2 | 2 | 决策后 |
| `resume` | 2 | 2 | `rearm` 之后 |
| `status` | 1 | 1 | 就绪探测 |
| `reprocess` / `reprocess_control` / `set_state` | 0 | 0 | 本趟未用 |

四次 restore/resume 的时间戳（原始值，单位 s）：

| 命令 | sent | received | applied | received−sent | applied−received |
|---|---:|---:|---:|---:|---:|
| restore #1 | 1794311884.164 | 1794311884.169 | 1794311884.360 | 0.005 | 0.191 |
| resume #1 | 1794311884.862 | 1794311884.864 | 1794311885.360 | 0.002 | 0.496 |
| restore #2 | 1794311916.968 | 1794311916.969 | 1794311917.468 | 0.001 | 0.499 |
| resume #2 | 1794311918.974 | 1794311918.978 | 1794311919.566 | 0.004 | 0.588 |

`run_summary.native_checkpoint` 的计数：`snapshots=30`、`snapshots_superseded=0`、
`snapshot_ack_timeouts=7`、`failures=7`、`holds=2`、`restores=2`、`resumes=2`、`reprocesses=0`、
`host_ready=true`。

## 5. 快照超时 7/30 与 superseded 的计数口径

沿用现有写法，单独列：

- **7** = `snapshot_ack_timeouts`：快照命令在 **0.5 s** 预算内没有被宿主应用（`service()` 里
  `expire_pending(0.5)`）；计入 `failures`。
- **30** = `snapshots`：成功应用并收到 `OK snapshot ...` 的条数。
- 37 = 30 + 7，即本趟实际写出的快照命令数。
- **`superseded` = 0**：只有在"新命令写到命令目录前，旧快照仍在 pending 且被 `expire_pending(0.0)`
  顶掉"时才计入；它是**被替换**，不是失败，不进 `failures`。本趟没有发生。
- 两者互斥：超时的快照已经被移出 pending，不会再被后来的命令顶掉，所以同一个快照不会既记超时又记替换。

## 6. 逐帧 LIO 耗时：不在本归档内

见 `LIO_TIMING_STATUS.md`。结论先行：**原始逐帧记录没有落盘**，本目录无法核对该数字；
`../README.md` §3u 的那一行应读作"会话内测量"，不是归档事实。

## 7. 可以离线复核的几个点

1. 二进制/库/配置/bag 的 sha 与 `receipt.json` 逐位一致（`DEPLOYED_CODE.md` §4）。
2. 两段都触发、都决策、都关闭、都 rearm：`lifecycle_events.json` 的 4 条事件 + `candidates.jsonl` 两行。
3. 两段都走了 hold→restore→resume：`native_checkpoint_events.json` 的顺序，
   以及 `host.log` 里 `restore #1` / `restore #2` 两行。
4. 两段之间确实有帧被消费：`frames.consumed_after_first_decision = 368`。
5. `wiring.json.all_ok = true`，且 `same_process_group` 里 host/recovery 的 pgid 都是 `3391481`。
