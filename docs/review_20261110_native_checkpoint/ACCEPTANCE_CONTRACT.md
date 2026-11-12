# 验收契约（审阅点名的三项）

本文只描述**现在代码里的实际契约**，并标出其中的缺口。行号对应当前分支
`exp/m0-updated` / HEAD `c2b193c`。

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

## 2. 完整接纳 → HEALTHY：谁发 `resume`（当前契约 + 缺口）

### 2.1 现在的契约

`resume` 只有一个发送点：`NativeClosedLoop._apply_lifecycle()`（:1336-1345），
它遍历 `tx_mgr.lifecycle_events`，**只对 `"rearm"` 事件**调用 `cp.resume()`。

而 `rearm` 只有一个产生点：`QuarantineManager.rearm()`（`slam_recovery/quarantine/manager.py:567`），
调用者为：
- `maybe_close_waiting_segment()` 返回非空之后（`transaction_manager_node.py:306`、
  `recovery_node.py:1075`）——即 **Mode 3 等待超时关闭**路径；
- 状态为 `ABORTED` 且没有 active quarantine 时的恢复（`transaction_manager_node.py:312`）。

### 2.2 缺口：接纳路径没有事件

Mode 2 提交分支（`manager.py:324-475`）在 `pending` 为空时直接：

```python
new_state = RecoveryState.HEALTHY     # pending 为空
...
self.active_quarantine = new_segment  # None
self.state = new_state
```

**它不 append 任何 `lifecycle_events`。** 因此：

- 完整接纳 → `HEALTHY` → Python 侧**不会发 `resume`**；
- 宿主的 `map_hold_` 仍为 true（`LIVMapper.cpp:1145-1155`，只有 `resume` 会清零），
  之后的地图写入继续被停掉。

也就是说，**"接纳后放写"目前没有契约**，`resume` 只覆盖"拒绝 → 等待超时 → 关闭 → rearm"这条路径。
本趟受控整链没有暴露这一点，因为两段都是拒绝（`accepted=0`，见归档 `candidates.jsonl`）。

### 2.3 需要补的（未做，等决定）

二选一，都是小改动，但属于设计决定，不在本轮文档任务里动：

1. 接纳成功时也 append 一个 lifecycle 事件（例如 `"commit_closed"`），驱动侧把它等同于 rearm；
2. 驱动侧不再只看 `rearm`，而在观察到 `tx_mgr.state` 从隔离态回到 `HEALTHY` 且
   `active_quarantine is None` 时发 `resume`。

第 2 种不依赖 manager 改动，但依赖状态轮询；第 1 种把"为什么放写"写进事件流，更可核对。

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
- 只有 pending 真正清空（后续候选把剩余帧全部验证并提交）才转 `HEALTHY`；转 `HEALTHY` 后
  仍会遇到第 2 节的缺口。

### 3.1 可核对的字段

- 冻结的 18-key 流（`candidates.jsonl`）里有 `committed_pose_keys` 与 `deferred_pose_keys`：
  本趟两行都是 `[]`（两段都没进 Mode 2）。
- `report.partial_commit` 与 `report.remaining_pending_pose_keys` 在 `core.py:380-384`
  定义、由 manager 赋值，但**当前驱动不把它们写进任何归档文件**（不在 18-key 流里，
  `candidate_record` 也不取）。需要的话要单独加字段，而不是从 `deferred_pose_keys` 猜。
- 拒绝路径的"没提交的帧"另有记录：`run_summary.lifecycle.events` 的
  `frames_unresolved`（本趟 58 / 86 帧），以及 `lifecycle.unresolved_segments=2`。
