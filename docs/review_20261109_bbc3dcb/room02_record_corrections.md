# room_02 记录口径更正（审阅 0c2e4206）

对应四件事：比较集口径、ATE 标签、FNR 分母、机制结论降级。
凡与本文件冲突的旧表述，以本文件为准；被更正的旧值一律保留在括号里，不静默删除。

## C1 比较集：E_oracle 是 323 帧 / 317 GT 匹配，不是 326

| 用途 | 帧数 | 来源 |
|---|---:|---|
| **E_oracle / E_actual 对照** | **323** | `room02_e_oracle_results.json: frame_set.n_frames` |
| 同上，GT 匹配位姿 | **317** | `mechanism.trajectory_vs_gt.*.matched` |
| 五臂分解 A–E | 326 | `room02_decomposition_results.json: frame_set.n_frames` |

**326 是分解实验的共同集，不是 oracle 对照集，两者不得混用。**
分解要求「过滤扫描 + rerun 位姿」，oracle 对照在此之上还要求 oracle 包可解析，
因此后者少 3 帧。任何「E_oracle 在 326 帧上」的表述都应改为 323 帧 / 317 GT 匹配。

## C2 ATE 315.16 m 的标签：`FULL_ALIGNMENT_DIAGNOSTIC`

| 臂 | ATE RMSE | 标签 |
|---|---:|---|
| E_actual | 315.159 m | `FULL_ALIGNMENT_DIAGNOSTIC` |
| E_oracle | 0.0744 m | `FULL_ALIGNMENT_DIAGNOSTIC` |

含义：在**整条轨迹**上拟合一次 SE(3) 再算残差。它回答「重放整体漂了多远」，
不回答「窗内修复是否有效」，与冻结的 healthy-prefix 协议（只用前置段拟合、
窗内即为外推）**不是同一个量**。

- 两个诊断值**不得**与 hall_01 的冻结协议数字并排放进同一张表；
- 本序列的冻结协议 ATE **尚未计算**，应记为 `UNAVAILABLE`，不得用 315.16 代替；
- 引用 315.16 时必须同时写出 `FULL_ALIGNMENT_DIAGNOSTIC` 与「整条轨迹拟合」。

## C3 FNR：0.01394%，不是 0.1066%

| 量 | 值 | 分母 |
|---|---:|---|
| **FNR（正确）** | **0.00013941** | `kept_injected + dropped_injected = 1,265 + 9,072,678 = 9,073,943` |
| 旧值（误标为 FNR） | 0.00106641 | `background_present = 1,186,220` |

旧值是把「存活注入行」除以「背景行数」，量纲上不是漏检率，它回答的是
「残留行相当于多少比例的背景行」。现重命名为
`kept_injected_over_background_present`，与正确的 `false_negative_rate` **同时保留**
（`room02_filter_row_audit.json: in_window` 两个字段都在）。
引用时须说明取的是哪一个：0.01394% 是漏检率，0.1066% 是背景归一化残留率。

## C4 机制结论降级

原表述：`FILTER_IS_THE_CAUSE (in-window removal)`（`room02_e_oracle_results.json: verdict.value`）。
该 JSON 字段保持不动（生产者产物），但**对外表述改为**：

> 窗内测量选择差异是重要因素；单因素尚未分离。

理由：E_actual 与 E_oracle 同时改变了「哪些行被删」与「删了之后点云的空间分布」，
hybrid（窗外用实际过滤器、窗内用 oracle）只覆盖其中一个方向。
在 X/Y 2×2（X = oracle + 保留的 1,265 注入行；Y = oracle + 误删的 23,607 背景行）
跑出来之前，不能说「1,265 行足以拉走配准」。

X/Y 预注册见 `docs/MILESTONE_fixed_input_repair.md`「Final mechanism split」。

## 附：本次同时落地的工具与规则

- `room02_filter_row_audit.py`：FNR 改为正确分母，旧量改名保留（C3）。
- `oracle_audit_rules.py` + `test_oracle_audit_rules.py`：五条验收规则
  （按索引计数保多重性 / hybrid 报告须带借用包 hash 与 original-index sidecar /
  窗外检验须用独立声明的窗口 / oracle 运行须核 input+output hash / FNR 定义）。
  其中 R2、R3 对当前 hybrid 报告仍是 `expectedFailure`，等实现修好后会变成
  unexpected success，提示移除标记。
