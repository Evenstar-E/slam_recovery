# room_02 2×2 host 结果审计

对象：`room02_2x2_results.json`、8 份 `room02_2x2_receipt_fl_run_*.json`、独立复算
`evaluate_2x2_runs.json`（main acfc820）。只读。
脚本 `two_by_two_audit.py`，结果 `two_by_two_audit.json`。

## 结论

| # | 项 | 结论 |
|---|---|---|
| 1 | 判据与预声明一致 | **符合** |
| 2 | 8 份回执绑定输入与 runner，四包 sha 与 manifest 一致 | **符合** |
| 3 | 独立复算与宿主无结论冲突 | **符合**（数值差异大，但在阈值同侧） |
| 4 | **判定用的 ATE 是诊断量，不是协议量** | **发现（不推翻结论，但改变解读）** |

`NOT_A_CLEAN_INTERACTION` 在两种 ATE 口径下都成立——交互规则的前提（O+F 与 O−B 均不失败）
从未满足。但「**运行方差主导**」这个解读只在诊断口径下成立；换成协议口径，四格**全部两次失败**。

## 1. 判据未被事后改动

`room02_2x2_results.json:protocol` 与 `single_factor_preregistration.json` 对齐：

| 项 | 预声明 | 结果 protocol |
|---|---|---|
| 阈值 | `failure_threshold_ate_m: 1.0` | `fail_rule: "full-alignment ATE > 1.0 m fails"` |
| 重复次数 | `repetitions_per_cell: 2` | `"both repeats must land on the same side"` |
| 交互规则 | O+F−B 两次失败且 O+F/O−B 均不失败 | 同 |
| 声明时点 | `declared_before_results: true` | — |

措辞不同但规则相同，未见放宽或收紧。**但 `fail_rule` 指名的是 full-alignment ATE**——这是第 4 项的问题。

## 2. 回执与包的绑定

- 8 份回执，每格 2 份，全部 `status: OK`；
- 每份 `pre_run.sha256.input_bag` 与 `single_factor_bags.json` 对应格的 sha256 一致；
- 四个 bag 在磁盘上的现算 sha 与 manifest **全部一致**（O `f8b26ddf…` 等）；
- 每份记录宿主 binary 路径 `fastlivo_mapping`、`host_revision: 0d2c034…`、两份配置的 hash。

## 3. 独立复算 vs 宿主

8 次运行全部落在阈值**同一侧**，无结论冲突。绝对差最大约 `71 m`（O+F#1），来源是对断掉
的轨迹做整体 SE(3) 拟合时，对齐方式不同会放大差异——这不是小数级的口径差，但两侧都只是
诊断量，且从未用于判定协议口径。

## 4. 发现：判定变量用的是诊断 ATE

`room02_2x2_results.json` 每条记录同时给两个 ATE：

```
ate_full_alignment_diagnostic_m   整条轨迹拟合一次 SE(3)      ← fail 用它
ate_frozen_prefix_protocol_m      冻结 healthy-prefix 协议量
```

同一条记录里还写着：

> `ate_full_alignment_diagnostic_m is a FULL_ALIGNMENT_DIAGNOSTIC and must not be merged into
> the frozen-prefix protocol table; ate_frozen_prefix_protocol_m is the protocol number`

而 `fail_rule` 明确写的是 "full-alignment ATE > 1.0 m fails"。

两种口径下的失败模式：

| 格 | full-alignment | frozen-prefix |
|---|---|---|
| O | 0.072 / 14.439 → **不过 / 过** | 3.81 / 24.42 → **过 / 过** |
| O+F | 593.0 / 14.9 → 过 / 过 | 过 / 过 |
| O−B | 48.8 / 19.7 → 过 / 过 | 过 / 过 |
| O+F−B | 554.6 / 0.301 → **过 / 不过** | 过 / 过 |

- **full-alignment**：O 与 O+F−B 都不稳定 → 「运行方差主导」；
- **frozen-prefix**：四格**全部两次失败**，没有一格是好的 → 不是方差，是**协议口径下全盘失败**。

交互规则在两种口径下都不满足（O+F 与 O−B 都稳定失败），所以 `NOT_A_CLEAN_INTERACTION`
本身不受影响。受影响的是**为什么**：说「运行方差主导」等于说「同一个格时好时坏」，
而在协议口径下没有任何一次是好。

**建议**：2×2 的失败判据改用 `ate_frozen_prefix_protocol_m`（即协议量的定义），
或把两种口径的判定都列出来并明确最终采用哪一个。诊断量可以作为补充列，但不应是判定变量。

## 5. P2 修正后的复核（main 067b8ba）

| 验收项 | 结果 | 证据 |
|---|---|---|
| 冻结 clean→GT 每个 run 共用 | **PASS** | `clean_to_gt` 只出现一次（177 匹配、RMSE 0.0907 m），没有任何 cell 自带变换 |
| 复合顺序 | **PASS** | 代码为 `(me @ R_p.T + t_p) @ R_cg.T + t_cg`，先 run→clean 再 clean→GT |
| hash 链 | **PASS** | 4 个 map 包记录值 = manifest = 磁盘现算；8 个 run 包 sha 逐个与磁盘一致 |
| 诊断量逐位不变 | **PASS** | 8 个 cell 的 `ate_full_alignment_diagnostic_m`、coverage、unsupported（含窗内/健康）、`frames_scored`、`poses_matched_gt` **全部逐位相同**，只有 `ate_frozen_prefix_protocol_m` 改变 |

修正后的协议读数：O 0.0926/26.373、O+F 743.311/26.148、O−B 76.070/33.682、O+F−B 687.520/0.314。
**只有 O#1 与 O+F−B#2 通过**，与诊断口径的通过集合相同。

因此先前「协议口径下八次全失败」是**漏掉 clean→GT 的假象**，我的第 4 项发现随之失效：
两种口径现在给出一致的通过/失败集合与一致的 `NOT_A_CLEAN_INTERACTION`。
「运行方差主导」不再依赖口径选择——两口径都显示同一格两次运行相差三个数量级。

本文件第 4 节保留为**历史记录**（针对 9bd2ff7 的旧数值），但不作为当前结论。

## 5b. R2 / R3 处置（同意你的提议）

- **R2**：旧 `room02_hybrid_bag_report.json` 属已废弃的 X/Y 设计，2×2 已取代它。
  同意按 **`SUPERSEDED, 不再用于结论`** 关闭，而不是等新报告。规则保留，供将来的 hybrid
  报告使用；测试改为断言「该归档文件缺少绑定字段」这一既成事实，不再标 expectedFailure。
- **R3**：`build_oracle_bag.py` 已改为读声明窗口，但归档 oracle report 未重建，
  `window_mismatch` 无从判断 → **保持 expectedFailure**。
