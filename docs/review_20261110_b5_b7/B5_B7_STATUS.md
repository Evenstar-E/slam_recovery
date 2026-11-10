# B5 / B7 — 现在能闭合到哪一步

日期 2026-11-10。数据仅来自 `docs/**` 下已归档 JSON；**无宿主运行，未改任何阈值，未改任何标签口径**。
脚本 `b5_b7_analysis.py`，结果 `b5_b7_results.json`。

## 结论

| 任务 | 状态 | 原因 |
|---|---|---|
| B5 门的增量价值 | **BLOCKED** | 归档里没有"逐候选的独立标签 + 门决定"配对记录 |
| B7 正常数据代价与修复风险 | **BLOCKED** | 同上，且没有任何"有门控 / 无门控"的同输入对照 |

这不是"没找到"，而是"找到了决定、找不到标签"。机器扫描 `docs/**/*.json` 的全部记录型列表：

- 同时带 **身份 + 决定 + 独立标签** 的记录：**0 条**
- 带 **身份 + 决定但没有标签** 的记录：**1 条**
  （`docs/review_20261105/audit_results.json` 的 R3 观测：`id` + `gate_accepted`，无任何独立标签字段）
- 带 **身份 + 标签但没有决定** 的记录：**0 条**

因此 B5 的混淆矩阵**没有计算**。用 run 级/arm 级的最终 ATE、coverage、fail 反推候选级
"有害被拒/有益被拒"会把宿主失败算成门的功劳或过错，这正是这次要避免的。

## 为什么 B7 也不能用归档数字顶替

`room02_2x2_results.json` 确实有分区的几何量（`healthy_unsupported_fraction`、
`in_window_unsupported_fraction`），但它是**不同退化输入下的宿主结果**，不是"跑门的代价"：

- 没有同一输入的 with-gate / without-gate 对照，差值无从得出；
- 8 个格子里 6 个 `healthy_unsupported_fraction = 1.0`，那是整张地图丢光的失败 run；
  把它称作"误干预造成的健康几何损失"是把宿主故障归给门；
- 没有任何归档把"恢复尾段"从退化窗里分出来，恢复尾段的量在数据里不存在。

这些数字保留在结果 JSON 的 `B7.descriptive_only` 下，并明确标注它们**不是** B7 的量。
`hall01_b4_cost_and_gap.json` 的 C3 侧 `wall_s = null`（provenance error：被引用的
`/tmp/fl_run_...2414230` 其实是 room_02 的 filtered run），所以"中断"的耗时侧也不能引用。

## 下一个原生运行必须补的记录（B5：就这四项，一项也不要多）

每条候选一行：

| 字段 | 说明 |
|---|---|
| `candidate_id` | 候选标识 |
| `gate_accept` | 门的决定，布尔 |
| `gate_reject_reason` | 拒绝原因（门自己给出的字符串） |
| `independent_label` | 独立标签（来自 GT 或独立 clean-run proxy，**不得**由门自己的 `info_after` / `holdout_nis` 生成） |

B5 到此即可闭合：有害被拒 = `label=harmful & gate_accept=false`，有益被拒 = `label=beneficial & gate_accept=false`，
两者都能给计数 + Wilson 区间（脚本里已有 `wilson(k, n, z=1.645)`，样本不足时只报 `k/n`）。

B7 需要的是同一批记录，**外加这一行属于哪个段**（正常 / 退化 / 恢复尾）。没有段标签，
即使四项齐全，B7 的分区仍然做不出来——这是 B7 与 B5 唯一的数据差别，不是第二套遥测。

## 复现

```bash
python -I docs/review_20261110_b5_b7/b5_b7_analysis.py .
# B5 BLOCKED / decision_and_label_records=0 / decision_only_records=1 / B7 BLOCKED
```

脚本是只读的：不写归档、不改阈值、不生成任何替代标签。
