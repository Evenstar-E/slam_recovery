# 候选流记录格式（B10/B5 的输入，2026-11-10 冻结）

B10 的四策略和 B5 的混淆矩阵都要求**逐候选**记录，而不是最终结果。现在冻结它，是因为下一轮的原生闭环（A10/B11）本来就要产出这些值——只是顺手写下来，不需要新增计算。

一行一个候选，JSONL（`candidates.jsonl`），字段固定，缺字段写 `null`，不要省略键。

```json
{
  "run_id": "fl_run_20261110T023139Z_2912547",
  "candidate_id": "cand_0007",
  "t_trigger_ns": 1627643760123456789,
  "t_decision_ns": 1627643761123456789,
  "mode": "MODE2_ATOMIC_COMMIT",
  "accepted": true,
  "deferred_pose_keys": [41, 42],
  "committed_pose_keys": [38, 39, 40],
  "refusal_reason": null,
  "weak_dir_info_before": 20.0,
  "weak_dir_info_after": 30.0,
  "holdout_nis": 1.2,
  "paired_benefit_status": "PASSED",
  "wilson_lower_bound": 0.9,
  "reentry_pos_jump_m": 0.05,
  "parent_map_version": 3,
  "candidate_source": "recovery_node",
  "pose_se3_first_trigger": [16 floats, row-major]
}
```

## 为什么是这些键

| 键 | B10 用途 | B5 用途 |
|---|---|---|
| `candidate_id` | 四臂共用同一候选集的键 | 逐候选配对 |
| `mode` / `accepted` / `refusal_reason` | 只有 `G` 与 `U` 的差来自这里 | 门的决定 |
| `committed_pose_keys` / `deferred_pose_keys` | `G` 臂的接纳集合；`Q` 臂缺失的帧由这里解释 | 拒绝的后果 |
| `weak_dir_info_*` / `holdout_nis` / `paired_benefit_status` | 诊断，不参与判定 | **不得**当独立标签 |
| `t_trigger_ns` / `t_decision_ns` | 检测→决策延迟 | 迟检分析 |
| `pose_se3_first_trigger` | 事后核对 `T_wb` 约定 | 复算排查 |

## 三条纪律

1. **`weak_dir_info_*`、`holdout_nis`、`paired_benefit_status` 不是标签**。它们由门自己产生，用它评价门就是自证；独立标签必须来自 GT 或独立 clean-run proxy。
2. 缺字段写 `null` 并**在结果里计数**，不要用默认值填充——"没记录"和"记为零"必须可分。
3. 该文件只记录 `step_frame`/gate 已经算出的值；**不得**为它新增任何一次计算或第二个估计器。

## 归属

- 产出：A10/B11 的原生闭环（r11070-c3）；
- 消费：B10 四策略与 B5 混淆矩阵（我 / r26534-58）。
