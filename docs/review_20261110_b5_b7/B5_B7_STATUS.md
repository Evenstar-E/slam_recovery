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

## 下一个原生运行要补的记录

格式不在本文定义：r11070-c3 已冻结在
`docs/review_20261110_b10/candidate_stream_schema.md`（`f20a546`），
`candidate_id` / `mode` / `accepted` / `refusal_reason` 等都是那里的键，取那里的名字。
该 schema 的三条纪律（门自己的 `weak_dir_info_*` / `holdout_nis` / `paired_benefit_status`
不是标签；缺字段写 `null` 并计数；不为它新增计算）就是本文的口径，本文不再复述。

对照该 schema，B5/B7 还差两处，且都不是"再加一套遥测"：

1. **标签没有落地字段**。schema 里没有 `independent_label`，也没有指明标签文件的路径/来源。
   纪律 1 说标签来自 GT 或独立 clean-run proxy，但这份记录本身不带它。可行做法是按
   `(run_id, candidate_id)` 与一个独立标签产物做 join，并把该产物的 provenance 写进结果；
   否则"标签从哪来"又会变成一条口头约定。
2. **没有段标签**。B7 要按 正常 / 退化 / 恢复尾 分区，schema 里没有任何键表示一个候选属于哪一段。
   B5 不受影响，B7 不能分区。

## 复现

```bash
python -I docs/review_20261110_b5_b7/b5_b7_analysis.py .
# B5 BLOCKED / decision_and_label_records=0 / decision_only_records=1 / B7 BLOCKED
```

脚本是只读的：不写归档、不改阈值、不生成任何替代标签；重跑逐字节一致。

## 计数分母

本项目里"计数"与"帧数"不是一回事：LIVO 每帧切两次（一次带 IMU、一次只带图像），
`GROUP` 数不等于帧数。B5 的分母是**独立标签判为有害/有益的候选数**，B7 的分母是**某段的候选数**，
两者的分母都由记录本身给出并写进结果，不从其它计数换算。样本不足时只报 `k/n`，不报比例。
