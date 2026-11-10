# A9：第二次 onset 早于首次修复时，修复未进 undo 日志（方案，先评审再动代码）

反例（审阅给定）：修复（Mode 2 提交）之后出现第二个 onset，且 `t_q_start` 早于该修复的时间，
`trigger_quarantine` 的回滚循环发现不了这次修复，因为**修复从未写进 undo 日志**。

## 1. 根因

`TrustedMapTransactionManager` 有两份 undo 记录，且只覆盖"晋升"：

- `_apply_promote()` 把 delta 追加到 `promoted_history`，并把
  `(prev_pose, prev_factor_len, prev_ba, prev_bg)` 追加到 `_promoted_before_images`（`manager.py:56-75`）；
- `restore_checkpoint()`（`:92`）与 `trigger_quarantine()`（`:151`）都只从这两份里回滚；
- **Mode 2 的修复走的是另一条路**：`validate_and_resolve` 在 publish 段直接给
  `trusted_poses/trusted_factors/trusted_bias_*` 赋值（`:355-360`），**既不写 `promoted_history`
  也不写 before-image**。

所以"修复"对 undo 日志是不可见的：只要后续 onset 覆盖到修复帧，回滚会保留修复结果，
trusted map 里留下本应被撤销的位姿。

## 2. 最小修复的形态（先说清难点）

直观做法：在 publish 段为每个被提交的关键帧追加一条 undo 记录（delta + before-image），
让 `trigger_quarantine` 的回滚循环自然覆盖修复。

**难点**：`promoted_history` 是一个**按时间单调的栈**，两个回滚循环都靠
"从尾部弹出所有 `timestamp_ns >= t_q_start` 的条目"来工作。修复覆盖的帧可能**比栈顶更早**
（例如修复 8..11，而 12..19 已经晋升），直接 append 会破坏单调性，弹出会提前停止。

三种可选形态，按侵入性从低到高：

1. **插入排序**：按 `timestamp_ns` 把修复条目插到正确位置（O(n) 插入，n 是 undo 日志长度，通常几十条）。
   回滚循环不变。代价小，但要求修复条目与晋升条目有可比的时间戳（用被修帧的时间戳）。
2. **独立日志 + 合并回滚**：新增 `repair_history`，回滚时把两份日志按时间合并再弹。语义最清晰，
   但 `trigger_quarantine`/`restore_checkpoint` 两处都要改，且要保证两者在同一 t_q_start 下的一致性。
3. **只记录被修帧的 before-image**，在 `trigger_quarantine` 里额外遍历一次"修复过的帧集合"回滚。
   最小，但等于在 manager 里维护第二套"哪些键被修复过"的状态。

我倾向 **1（插入排序）**：只改 publish 段的一处追加 + 一个插入辅助函数，回滚逻辑零改动。

## 3. 失败反例测试（先写测试）

`tests/test_a9_repair_undo.py`：

```python
def test_second_onset_before_the_repair_undoes_it():
    mgr = TrustedManager(...)
    # 1) 正常晋升 8..11，随后 M ode2 修复这四帧
    pose_before = mgr.trusted_poses[8].copy()
    mgr.validate_and_resolve(candidate(repaired={8:..., 9:..., 10:..., 11:...}, ...))
    assert mgr.trusted_poses[8] != pose_before            # 修复已生效
    # 2) 第二个 onset 的 t_q_start 早于这次修复
    mgr.step_healthy(delta(12, ts=...)); mgr.step_healthy(delta(13, ts=...))
    mgr.trigger_quarantine(estimated_onset_ns=..., current_ns=...)   # 覆盖 8..13
    # 3) 修复必须被撤销
    assert np.allclose(mgr.trusted_poses[8], pose_before)
    assert 9 not in mgr.trusted_poses or ...              # 按 before-image 语义逐帧断言
```

断言走可观察输出：`mgr.trusted_poses` 与 `mgr.trusted_version`，不看内部日志字段。

## 4. 待确认

1. 修复撤销的语义：被修复的帧应回到**修复前**的位姿（若有）还是**被移除**（若修复前不存在）？
   before-image 机制已能区分这两者，我按它的既有语义实现。
2. `trusted_factors` 的截断语义：现有晋升撤销用 `del trusted_factors[int(prev_factor_len):]` 截断到修复前的长度；
   修复插入在中间时，这个"按长度截断"的做法是否仍成立，需要确认 factor 列表是否严格按时间追加。

这两点确认后我再动代码。
