# 验收契约（审阅点名的三项）

本文只描述**现在代码里的实际契约**，并标出其中的缺口。§1/§3 的行号对应归档 run 的代码
`exp/m0-updated` / HEAD `c2b193c`；§2.2 的修复合入后在 main。

---

## 1. 单 in-flight 命令，ack 恰好消费一次

### 1.1 驱动侧（`slam_recovery/ros/recovery_node.py`，`CheckpointClient`）

- `_pending` 是 FIFO 列表。`_send`（:729）只 append，不等待；`poll`（:667）/`collect`（:608）
  只看 `_pending[0]`，并且 pop 只发生一次——成功 ack、失败、或超时各走一个分支，事件对象只被
  `_count` 一次（:684-688）。这就是"恰好消费一次"的实现点。
- ack 用**命令名**校验：`_read_ack_for`（:635）要求 `ack` 的第二个 token 等于当前命令名，
  否则返回空。迟到的 `hold` ack 不会被当成 `restore` 的 ack——旧问题（迟到 ack 撞上新命令、
  同一条被记两次成功）由这一处关掉。
- 写新命令前先 `expire_pending(0.0)`（:735）：仍有 pending 的旧快照被记为
  `superseded`，从 pending 移除，不阻塞新命令；`superseded` 不计失败。
- 驱动主循环在 `service()` 里 `if self.cp.pending(): return None`（:1323-1325）：
  有命令在飞时不产生新候选，决策不会跑在"宿主还没应用上一条命令"的状态上。

### 1.2 宿主侧（`src/LIVMapper.cpp`）

- `controlThreadLoop`（:1075）收到 `cmd` 后立刻 `rename` 成 `cmd.done`（:1090），再写
  `ack_received`，然后把命令放进待应用槽。rename 保证同一文件不会被消费两次。
- 主循环每帧开始处 `applyPendingControlCommand()`（:1217）应用并写 `OK <cmd> ...`；
  线程本身不碰 `_state`、地图或 LIO。

### 1.3 已知限制（如实写）

ack 的令牌是**命令名，不是序号**。同名命令连续出现时（`snapshot` → `snapshot`），
一个迟到的旧 ack 在理论上会被下一条同名命令认领。本趟 37 条快照里有 7 条超时，
这个歧义只影响**快照的计时/计数归属**，不影响决策：快照是只读命令，不改变宿主状态与地图，
也不参与 hold/restore/resume 链路。`hold/restore/resume/status/set_state` 名称互不相同，
不存在这个歧义。

---

## 2. 隔离结束 → 放写：谁发 `resume`

### 2.1 归档 run 的契约（发现缺口时的状态）

归档 run `fl_native_20261110T115717Z_3390402` 跑在修复合入前的代码上。当时 `resume` 只有一个发送点
`NativeClosedLoop._apply_lifecycle()`，且**只对 `"rearm"` 事件**调用 `cp.resume()`；`rearm` 只在
Mode 3 等待超时关闭后产生。Mode 2 完整提交在 `pending` 为空时直接置 `HEALTHY`、清
`active_quarantine`，不 append 任何 `lifecycle_events`——**接纳路径不会发 `resume`**，宿主的
`map_hold_` 保持 true（`LIVMapper.cpp:1145-1155`，只有 `resume` 清零），修复后的地图不会再被写入。
本趟两段都是拒绝（`accepted=0`），所以没有暴露。

### 2.2 已补的（代码级，未在宿主上跑过接纳路径）

采用方案 1：manager 在"提交后 `pending` 清空、`new_segment is None`、确有旧段"时 append
一条 `commit_closed` 事件（`manager.py`，publish 块内），字段
`segment_id / trusted_version / n_committed / t_end_ns`；驱动侧把 `rearm` 与 `commit_closed`
都视为"宿主可以写图"，发 `resume` 并在 action 里记 `trigger`。

- 部分提交（`pending` 非空 → `WAITING_FOR_EVIDENCE`）不产生该事件，也不放写（见 §3）。
- 测试：`test_lifecycle_rearm.py::TestAcceptedCommitReleasesTheHold`（接纳产生事件、拒绝不产生）、
  `test_checkpoint_client.py::test_an_accepted_commit_writes_resume`（`commit_closed` 也写 `resume`）。
- **边界**：这条路径只有单测覆盖，没有宿主运行证据；下一次受控整链若被接纳，`resume` 的
  实际发出与应用要在 receipt 的 `native_checkpoint_actions` 里核对。

---

## 3. partial 提交仍保持隔离，不无条件放写

Mode 2 提交后若 `pending` 非空（`manager.py:375-430`）：

```python
pending = (old_pending | set(deferred_keys)) - committed_keys
new_segment = QuarantineSegment(segment_id=f"{old}:deferred", ...)
new_state = WAITING_FOR_EVIDENCE if pending else HEALTHY
self.active_quarantine = new_segment
self.state = new_state
```

- 已提交帧写入 trusted map（`trusted_poses`/`trusted_version` 前进），但**只有被独立支持且
  不在 reference 里的帧**能进 commit（`candidate.verified_pose_keys` 覆盖检查，`manager.py:324-338`）。
- 剩余 pending 帧组成 `:deferred` 段继续隔离；状态是 `WAITING_FOR_EVIDENCE`，不是 `HEALTHY`。
- 该分支同样**不产生 lifecycle 事件**，所以宿主保持 hold，不会放写——这在这里是正确行为。
- 只有 pending 真正清空（后续候选把剩余帧全部验证并提交）才转 `HEALTHY`；转 `HEALTHY` 时走
  §2.2 的 `commit_closed`，宿主放写。

### 3.1 可核对的字段

- 冻结的 18-key 流（`candidates.jsonl`）里有 `committed_pose_keys` 与 `deferred_pose_keys`：
  本趟两行都是 `[]`（两段都没进 Mode 2）。
- `report.partial_commit` 与 `report.remaining_pending_pose_keys` 在 `core.py:380-384`
  定义、由 manager 赋值，但**当前驱动不把它们写进任何归档文件**（不在 18-key 流里，
  `candidate_record` 也不取）。需要的话要单独加字段，而不是从 `deferred_pose_keys` 猜。
- 拒绝路径的"没提交的帧"另有记录：`run_summary.lifecycle.events` 的
  `frames_unresolved`（本趟 58 / 86 帧），以及 `lifecycle.unresolved_segments=2`。
