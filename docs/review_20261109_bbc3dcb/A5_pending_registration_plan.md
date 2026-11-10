# A5：pending 全集由系统登记（最小修复方案，先评审再动代码）

反例（审阅给定）：`margin=0`、healthy keys 1/2/3、隔离段 `raw_frame_refs=[]` 时，
candidate 只提交 key1 且不声明任何 deferred → 计算结果 `pending = {}` → 系统回到 **HEALTHY**，
key2/key3 从未被提交、也从未被声明，却被静默丢弃。

## 1. 根因（代码定位）

`TrustedMapTransactionManager`：

- `trigger_quarantine()`（`manager.py:132-200`）把 `timestamp_ns >= t_q_start` 的 delta 放进
  `self.provisional_queue`，并创建 `QuarantineSegment`，但**没有把这些 delta 的 `keyframe_id` 写进
  `raw_frame_refs`**，于是段登记的人口从空集开始；
- `step_healthy()`（`:106`）在非 HEALTHY 状态直接抛错，所以隔离期间到达的帧**没有登记通道**；
- `validate_and_resolve()`（`:269-279`）用
  `pending = (old_pending | candidate.deferred) - committed`，其中 `old_pending` **只来自**
  `segment.raw_frame_refs`。段为空 → 待定全集为空 → `pending == {}` → `state = HEALTHY`。

即：**隔离段的人口由 candidate 的声明决定，而不是系统登记**。candidate 只需不提那两帧，系统就认为没有待定帧。

## 2. 最小修复（只改 Python，两处赋值 + 一个登记入口）

1. **触发时登记**：`trigger_quarantine()` 构造段时把已入队的帧写进段：

   ```python
   raw_frame_refs=[str(d.keyframe_id) for d in quarantined_deltas
                   if getattr(d, "keyframe_id", None) is not None],
   ```

2. **隔离期间登记**：新增 `register_quarantined_frame(keyframe_id, timestamp_ns)`，
   在 `state == QUARANTINED` 时把 key 加入 `self.active_quarantine.raw_frame_refs`（幂等 set 语义），
   供节点在把新帧放进 quarantine 时调用；`step_healthy` 的语义与报错**保持不变**。

3. **判定不变**：`pending = (registered | deferred) - committed`；只有 `pending` 为空才回 HEALTHY。
   已提交的帧从 pending 中移除的逻辑保持原样（`committed` 已在公式里）。

不做的事：不改 `repaired_*` 的语义、不改 mode 判定、不改 report 字段名；`raw_frame_refs` 仍是字符串列表。

## 3. 失败反例测试（先写测试，再改代码）

`tests/test_a5_pending_registration.py`：

```python
def test_margin_zero_commit_one_does_not_finish_the_quarantine():
    mgr = TrustedMapTransactionManager(confirmation_margin_ns=0)
    # healthy 1/2/3 are promoted; 2 and 3 are still provisional when the quarantine opens
    for k in (1, 2, 3):
        mgr.step_healthy(delta(k, ts_ns=k * 10**8))
    seg = mgr.trigger_quarantine(estimated_onset_ns=2 * 10**8, current_ns=3 * 10**8, ...)
    assert sorted(int(r) for r in seg.raw_frame_refs) == [2, 3]      # 系统登记，不靠 candidate
    rep = mgr.validate_and_resolve(candidate(repaired={1: pose}, deferred={}), ...)
    assert rep.remaining_pending_pose_keys == [2, 3]
    assert mgr.state != RecoveryState.HEALTHY
    # committing the rest ends it
    rep2 = mgr.validate_and_resolve(candidate(repaired={2: pose, 3: pose}, deferred={}), ...)
    assert rep2.remaining_pending_pose_keys == []
    assert mgr.state == RecoveryState.HEALTHY
```

第二项测试覆盖隔离期间到达的帧：

```python
def test_frames_arriving_during_quarantine_are_registered():
    ...
    mgr.trigger_quarantine(...)                  # 段开启，raw_frame_refs = 已入队帧
    mgr.register_quarantined_frame(4, ts_ns=4 * 10**8)
    rep = mgr.validate_and_resolve(candidate(repaired={2, 3}, deferred={}), ...)
    assert rep.remaining_pending_pose_keys == [4]
```

断言全部针对**可观察输出**（`report.remaining_pending_pose_keys` 与 `state`），不依赖内部字段，
所以即使实现方式调整也不会假通过。

## 4. 影响面与回归

- 现有测试里所有"提交即 HEALTHY"的用例都在 `raw_frame_refs` 由 candidate 显式给出时成立，
  修复后它们在语义上等价（登记集合 ⊇ candidate 声明集合）；
- 唯一行为变化：**段里已登记但既未提交也未声明的帧，现在会使隔离继续**（这正是要修的）；
- 不在本次修复范围：A8（factor 泄漏）、A9（第二 onset 未入 undo），由他人接手。

## 5. 待确认

1. 节点侧把新帧放进 quarantine 的位置在哪、是否已有统一入口可以挂 `register_quarantined_frame`；
   如果有多处，我在方案里加一个薄封装而不是逐个调用点加。
2. `raw_frame_refs` 的顺序是否需要稳定排序（我按 sorted 写）。

## 6. 覆盖范围（实现后的实测确认）

登记条件写的是 `active_quarantine is not None`，不是 `state == QUARANTINED`，这是有意的：
Mode 3 / Mode 1 会进入 `WAITING_FOR_EVIDENCE` 但**保留段**。

- `validate_and_resolve` 的 Mode 3 / Mode 1 分支只改 `self.state`，不动 `active_quarantine`
  （`manager.py:371-373`）；
- 全仓只有两处把 `active_quarantine` 置 None：Mode 4 hard-sleep（转 ABORTED）与"pending 为空"的完整提交；
- 因此 **Mode 3 期间到达的帧仍会被登记**，不存在"WAITING 但无段"的变体漏洞。

唯一没有登记通道的是 **ABORTED（Mode 4）之后**：段被显式清空并归档 sleeping submap，这是有意的重置，
之后的帧属于新的一段。这一条作为已知边界记录，没有额外改动。
