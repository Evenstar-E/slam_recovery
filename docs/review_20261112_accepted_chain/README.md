# 受控但被接纳的整链：`fl_native_20261112T020634Z_4148249`

任务（S1 2026-11-12）：用现有机制跑一次受控、但**被接纳**的整链，验证
`接纳 → commit_closed → resume → 宿主恢复写图`。仍标 `CONTROLLED_INTERFACE_TEST`、`--detection off`、
不改门/阈值/σ。

## 0. 三次 run 的输入身份对照

字段均取各 run 的 `receipt.json` → `inputs`。

| run | `host_binary_sha256` | `runtime_library_sha256` | `recovery_node_source` |
|---|---|---|---|
| `fl_native_20261112T020634Z_4148249`（事件 1，reprocess 丢失） | `0d7e23de537fcaa9ae0a4feb86afd8f9bc867c064f30bbfc9d0fa6bc9a2af6c1` | `0eacffe1017b9ccf4331ad4752cb0d336aaac4457d9f66ff056d66965cd35659` | `fb746dddc1a0f4e4041e27dddd75ab4f85559c88b18694510f25a582e8b36e18` |
| `fl_native_20261112T022158Z_4156288`（串行化后，事件 1） | `0d7e23de537fcaa9ae0a4feb86afd8f9bc867c064f30bbfc9d0fa6bc9a2af6c1` | `0eacffe1017b9ccf4331ad4752cb0d336aaac4457d9f66ff056d66965cd35659` | `18d92a032835dbfaff8593987bca9c6d5928882d33da876cb1549970646ea225` |
| `fl_native_20261112T024337Z_4166038`（两事件） | `0d7e23de537fcaa9ae0a4feb86afd8f9bc867c064f30bbfc9d0fa6bc9a2af6c1` | `0eacffe1017b9ccf4331ad4752cb0d336aaac4457d9f66ff056d66965cd35659` | `18d92a032835dbfaff8593987bca9c6d5928882d33da876cb1549970646ea225` |

- `host_binary_sha256`：三次**逐位相同**。
- `runtime_library_sha256`：三次**逐位相同**。
- `recovery_node_source`：run 1 与 run 2/3 不同；run 2 与 run 3 相同。变化点是合入命令串行化
  （`bbe916f`）之后。该字段记录的是驱动源码文件的 sha256，不是宿主产物。

**结论先说**：候选**真的过了 Mode 2**（不是凑出来的），宿主也**真的被 resume 并恢复了写图**；
但 `commit_closed` **没有出现**，因为这次提交是 **partial commit**，隔离段由等待超时关闭 + `rearm`
结束。并且，接纳后的 `reprocess` 命令在宿主侧**从未执行**——被同一毫秒内下一条命令覆盖了。
这三件事分别归档在下面。

原始文件在 `run_fl_native_20261112T020634Z_4148249/`，索引与复算脚本也在里面。

---

## 1. 运行身份

| 项 | 值 |
|---|---|
| run_id | `fl_native_20261112T020634Z_4148249` |
| 输入 | `/tmp/fastlivo/hall01_two_event_v1.bag`，sha `c3e905da…`，60.0 s |
| 宿主二进制 | sha `0d7e23de…`（= `deployed_host.diff` 构建出的那份） |
| 驱动源码 | sha `fb746dd…`（含本轮新增的绝对时间戳触发 + S1 的 `commit_closed`） |
| 触发 | **绝对位姿时间戳** `1627785276215170145`（bag 内第 132 个 kf），不是"第一帧后 N 秒" |
| confirmation margin | 4.0 s（复现 11:34 那次被接纳候选的 4 s 候选窗） |
| wait limit | 2.0 s |
| 机器负载（启动） | `51.77 69.58 99.39` |
| 终态 | `HEALTHY`，`quarantine_open_at_exit=false` |

为什么用绝对时间戳：上一轮的时间触发在"第一帧后 14.6 s"落到 kf 131，而 kf 132 才是被接纳的那一帧；
相邻两帧的 `weak_dir_info_before` 是 **21.14 vs 3.14**。时间触发会随启动/负载漂 1–2 帧，无法复现。
新增的 `--scripted-trigger-stamps` 让声明直接指向帧；本轮它精确落在 `1627785276215170145`
（`scripted_triggers.fired[0].ts_ns` 与之逐位相等）。

## 2. 门的结果（真过 Mode 2）

| 量 | 值 | 门槛 |
|---|---:|---|
| `weak_dir_info_before` | 3.138785 | — |
| `weak_dir_info_after` | 6.693675 | ≥ 3.0 且 ≥ 2.0 × before = 6.2776 |
| 比值 | 2.133 | ≥ 2.0 |
| `holdout_nis` | 0.442094 | ≤ τ_val |
| `wilson_lower_bound` | 0.922030 | ≥ 0.55 |
| `reentry_pos_jump_m` | 1.9526 | 包络内 |
| `paired_benefit_status` | PASSED | 必须 PASSED |
| 模式 | `MODE2_ATOMIC_COMMIT`，`accepted=true` | — |
| 提交帧 / 推迟帧 | **32 / 53** | — |

`before/after` 与 11:34 那次被接纳运行（3.1388 / 7.2187）一致；本轮 4 s 窗口给出 6.6937，
过线但是薄（2.133 vs 2.0）。

## 3. 宿主侧证据：resume 生效、停写解除、后续帧确实写图

驱动侧的 `native_checkpoint_actions` 在 `hold` 处就断了（见第 5 节），所以这里用宿主自己的文件：

- `host_control/ack` 最后一条是
  `OK resume ... hold=0 held_frames=104 held_points=346199 hold_commands=2 set_state=1`：
  **resume 被应用**，`map_hold_` 已清零；`set_state` 也已应用（`set_state=1`）。
- `host_control/ack_received` = `RECEIVED resume wall=1794449256.117040`。
- 写图是否真的恢复（`map_write_evidence.json`，脚本 `map_write_evidence.py`）：
  `[ LIO ] Update Voxel Map` 是 `UpdateVoxelMap` 内部的打印，停写时根本不会执行。

| 区间 | LIO 帧（`Raw feature num`） | 写图（`Update Voxel Map`） |
|---|---:|---:|
| hold 应用前 | 1365 | 219 |
| **hold → resume** | **547** | **0** |
| resume 之后 | 2399 | **448** |

  也就是说：停写期间 547 条 LIO 帧照常处理但**一次都没写图**；resume 之后马上恢复写图（448 次）。
  这是"接纳后恢复写图"最直接的宿主证据。

## 4. `commit_closed` 为什么没有出现（断点 1：partial commit 是结构性的）

`lifecycle.events` 只有两条：`wait_limit_closed`（`:deferred` 段）和 `rearm`；没有 `commit_closed`。
原因不是门，而是**候选集和待提交集不是同一个集合**：

- 触发时，manager 把 `t_q_start = trigger − margin = 触发前 4 s` 到触发时刻之间已经 provisional
  的帧全部算进隔离段。本轮这些帧是 **kf 95–132**（38 帧，含触发帧 132）。
- 驱动侧 episode 的候选帧从触发后的下一帧开始：**kf 133–164**（32 帧），全部提交成功。
- 于是 `pending = (old_pending ∪ deferred) − committed` 里必然留下 95–132；
  `new_segment` 非空 → 状态是 `WAITING_FOR_EVIDENCE`，不是 `HEALTHY` → **不会 append `commit_closed`**。
  随后 2 s 等待超时 → 段关闭 → `rearm` → driver 发 resume。

也就是说：**在这条受控路径上，无论门怎么判，`commit_closed` 都不可能到达**，除非候选覆盖
manager 自己认定的隔离总体（margin 窗口内的 provisional 帧 + 触发帧）。11:34 那次被接纳运行
同样是 partial（committed 23 / deferred 192），只是旧驱动不看事件、直接发了 resume，所以没暴露。

最小修法（**未实施，等决定**）：触发时把 driver 已缓存的 `[t_q_start, trigger]` 帧（含触发帧）
一并放进 episode，让候选总体 = manager 的待提交总体。这会改变门看到的帧数，属于协议决定，不擅自改。

## 5. `reprocess` 从未执行（断点 2：命令被覆盖）

`decide()` 在接纳分支里连续调用 `cp.reprocess()` 和 `cp.set_state(...)`，两次 `_write` 相隔
亚毫秒；宿主控制线程每 5 ms 才轮询一次 `cmd`，第二条写到 `cmd` 时第一条还没被读走，于是
**`reprocess` 被 `set_state` 覆盖**。证据：

- `host.log` 里 `[NATIVE_CHECKPOINT] reprocess #` **0 行**；也没有 "nothing was captured" 的告警，
  所以不是"重放为空"，而是命令根本没送到。
- `host_control/cmd.done` = `resume`（最后被消费的一条），`ack` 里 `set_state=1`、`hold_commands=2`。
- 后果：接纳后的地图**没有被从 checkpoint 重放构建**；宿主只是被 `set_state` 跳到接受位姿、
  解除停写，然后从旧地图继续写新帧。`reprocess` 才是把隔离帧写回地图的那一步。

最小修法（**未实施**）：`CheckpointClient` 内部串行化命令（一条 in-flight，ack 后再发下一条），
这与 `ACCEPTANCE_CONTRACT.md` 写的契约一致；现在 `decide()` 自己破坏了这个契约。

## 6. 驱动侧记账卡死（断点 3）

因为 pending 队头是丢掉的 `reprocess`，`poll()` 只匹配队头，后面的 `set_state` / `resume` ack
永远不会被认领：

- `native_checkpoint.events` 只有 11 条，最后是 `hold`；`snapshots=9`、`failures=0`。
- `resume` 在宿主上**已应用**，但 `native_checkpoint_actions` / `events` 里没有它。
- `tick()` 在 `pending()` 非空时直接返回，所以决策之后不再有滚动快照——驱动侧的原生通道
  在接纳瞬间就静默了，直到运行结束。

所以本轮"resume 的 received/applied 时刻"只能从 `ack_received` 拿到 received（256.117），
applied 没有驱动侧时间戳；只有宿主 ack 的 `hold=0` 作为已应用的证据。

## 7. 另一个观察：宿主在收尾时 `double free or corruption (out)`

`host.log` 末行是 `double free or corruption (out)`，出现在最后一条 INFO（bag 末帧 320.9 s）之后。
之前两次原生运行（`115717Z`、`113447Z`）的日志末尾没有这一行。发生在 runner 收尾杀进程附近，
可能是 checkpoint 深拷贝在析构路径上的问题，也可能只是被信号打断的退出路径。**未定位，如实记录**。

## 8. 本轮不能声称的事

- 不能声称 `commit_closed → resume` 走通：`commit_closed` 没有出现（第 4 节）。
- 不能声称接纳后的地图被正确重建：`reprocess` 没有执行（第 5 节）。
- 不能声称驱动侧记录了 resume：它没有（第 6 节）。
- 能声称：**受控触发能产生真过 Mode 2 的候选**；**resume 后宿主确实恢复了写图**；
  **停写期间帧照常处理但不落图**。

## 9. 归档内容

`run_fl_native_20261112T020634Z_4148249/`：

| 文件 | 内容 |
|---|---|
| `receipt.json` / `wiring.json` / `run_summary.json` | 运行收据、接线检查、完整汇总 |
| `candidates.jsonl` / `candidates_detail.jsonl` | 门结果（18-key）与输入全集 |
| `lifecycle_events.json` / `native_checkpoint_events.json` / `.tsv` | 生命周期事件、逐命令账本（11 条） |
| `host.log` | 宿主全文（含停写/恢复写图的直接打印） |
| `host_control/{ack,ack_received,cmd.done}` | 宿主最终 ack（resume 生效）与 receipt |
| `map_write_evidence.json` | 第 3 节的计数结果（脚本在上一层 `../map_write_evidence.py`，可复算） |
| `ros_home_log/`、`launch_pair.sh`、环境文件 | 运行配方与 ROS 侧日志 |
| `SHA256SUMS` | 本目录完整性 |

---

## 10. 第二次运行（命令串行化之后）：`fl_native_20261112T022158Z_4156288`

S1 修好了断点 2/3（`bbe916f`：`CheckpointClient._outbox` 一次只放一条命令，只读快照可被状态
命令抢占）。同一份声明（kf 132 绝对戳）、同一 margin 4.0、`--detection off`、宿主二进制未变
（`0d7e23de…`），只换驱动（sha `18d92a03…`）。原始件在
`run_fl_native_20261112T022158Z_4156288/`，索引在该目录的 `INDEX.md`。

**结果**：候选仍然真过 Mode 2（before 3.1388 / after 6.6761 / Wilson 0.9197 / holdout 0.4412），
仍是 **partial commit（31 submitted / 81 deferred）**，`commit_closed` 依旧不出现——这是第 4 节
的协议断点，本轮按要求没有动。放写仍由 `wait_limit_closed → rearm` 触发。

**串行化要核对的三件事，全部成立**：

- `host.log` 出现 `[NATIVE_CHECKPOINT] reprocess #1: 416 frames replayed over [1627785274.681 ..
  1627785288.545], repairs applied=0 queued=0, map now 19194 voxels/362286 points`。
- ack 顺序 `hold → reprocess → set_state → resume`，`native_checkpoint.events` 里
  reprocess / set_state / resume **各有且仅各一条**；驱动 `reprocesses=1`、`resumes=1`、`restores=0`。
  宿主 ack 里的 `restores=1` 是 reprocess 内部先 restore 再重放，不是驱动发的 `restore` 命令。
- resume 有驱动侧记录：received `1794450183.672810`（+0.003 s），applied `1794450184.170`（+0.497 s）。
  reprocess 的 applied−received = **5.500 s**，就是重放本身的耗时。

**地图与 LIO**：重放把地图从 checkpoint 的 15161 voxels/298650 points 写成 19194/362286；
resume 后滚动快照继续增长到 60425 voxels。重放前后 `average residual` 中位 0.0512 → 0.0529，
无新 ERROR/WARN，**本轮没有 `double free`**（上一 run 的那一行保留原记录，不推测）。

**一个口径修正**：第 3 节用 "hold 窗口内 `Update Voxel Map` = 0" 证明停写，那只对**没有 reprocess**
的运行成立。`reprocessCheckpoint` 在重放期间会临时清掉 `map_hold_` 才能写图（宿主源码如此设计），
所以本轮同一窗口有 164 次写图，全部来自重放；停写对普通帧的约束仍由 resume ack 的
`held_frames=171` 体现。以后引用这个指标必须写明运行里有没有 reprocess。

---

## 11. 第三次运行：同一份受控 run 里的第二事件：`fl_native_20261112T024337Z_4166038`

同一 bag、同一宿主二进制（`0d7e23de…`）、同一驱动（`18d92a03…`）、同一 margin 4.0、
`--detection off`。新增**第二个绝对戳** `1627785308048271418`（kf 422），选在第一次放写
（bag 287.011）之后、bag 末帧（320.909）之前；只声明，不按门的结果挑帧。原始件在
`run_fl_native_20261112T024337Z_4166038/`，索引见其 `INDEX.md`。

**两次事件都完整走完**：

| | 事件 1 | 事件 2 |
|---|---|---|
| 触发（bag ns） | 1627785276215170145 | 1627785308048271418 |
| 决策 | 1627785280281185627 | 1627785312188321114 |
| 结果 | **Mode 2 接受**（before 3.1388 / after 7.2145 / Wilson 0.8947 / holdout 0.3906） | **Mode 3 拒绝**（22.0641 / 17.6810 / Wilson 0.8304 / holdout 0.5588） |
| 关闭 + rearm | 287.011 → rearm | 317.390 → rearm |
| 原生 | hold → reprocess → set_state → resume（3.61 s 重放） | hold → restore → resume（0.50 s restore） |

- 触发 1 → 触发 2 之间 **276 帧**；第一次关闭 → 触发 2 **210 帧**；触发 2 → bag 末 **122 帧**。
- `candidates.jsonl` **2 行**，`lifecycle.events` 4 条（两次 close + 两次 rearm），终态 `HEALTHY`。
- 原生计数 `holds=2 / resumes=2 / restores=1 / reprocesses=1`；两次 resume 的 `trigger` 都是 `rearm`。
- 地图在两次事件后继续增长（末快照 `live_voxels=44633`）。

第二事件是**事件**（开段、决策、关闭、放写都发生），但不是第二次接纳：门按自己的规则拒绝了它，
没有为了让它好看改帧或改门。`commit_closed` 仍不出现（协议不变）。
