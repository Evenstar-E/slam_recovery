# T2 结果：新 trace 的资格、UNKNOWN 区间与 I 证据（2026-11-12）

> 输入 run `fl_native_20261112T115734Z_483777`（detection on、TRACE_COV=1、AVAILABILITY=1）。
> 按预注册 `T2_PROTOCOL.md` 执行；**无独立正常参照/事件标签**，所以
> `NORMAL_CONSISTENT` / `SUSPECT` / 误报 / 漏检 / 延迟 / 错误 NORMAL 全部 **`NOT_EVALUABLE`**
> （`ALI-B2-NORMAL-LABELS-20261112-01`）。本文件只交资格、UNKNOWN 区间、M/T/I 证据分布。
> 未跑宿主、未改共享代码、未改旧归档。

## 0. 一句话

新 trace 的 I 通道**存在**（用 `vec6` + `M2DGR_room_02.txt` 的 post 位姿精确算 `e_I`，
`has_out=1` 504 个配对帧可算），M/T 也齐全；
**但校准/标签仍缺**，所以 120 个 0.5 s 块全部 UNKNOWN，分类效果不可评价。这是一次
"证据资格"结果，不是"ALI-H 有效/无效"的结论。

## 1. 运行与输入身份

| 项 | 值 |
|---|---|
| run id | `fl_native_20261112T115734Z_483777` |
| receipt status | `OK`；`detection=on`；`injection=INJECTION_DECLARED_Z_BIAS`；`candidate_source=icp_reregistration` |
| run mode | receipt `CONTROLLED_INTERFACE_TEST`；**run_summary 记 `CONTROLLED_TRIGGERS_NOT_FIRED`（两者不一致，按 receipt 的受控接口测试理解，不作自然检测成绩）** |
| 终态 | `WAITING_FOR_EVIDENCE`；paired **532**；availability **531** |
| inputs | bag `c3e905da…`；host binary `0d7e23de…`；runtime lib `49f2f941…`；recovery node `a4aaa58b…` |
| trace / availability / receipt / summary sha256 | `t2_summary.json._meta`（`t2_run.py` 运行时计算） |

**修复用途限制**：host ack `repair_received=42 / repair_applied=0 / repair_dropped=42`（负载导致命令迟到）。
因此本 run **不用于**"修复收益"结论；per-frame P/M/T 证据不受影响。

## 2. trace 形状

| 项 | 值 |
|---|---|
| 文件 | `host_logs/trace_cov.txt`：5 行表头 + **1042 数据行** |
| 可解析 | **1041 行**（92 列） |
| 格式异常 | **1 行**（第 1048 行只有 53 列，末尾截断；该行是第 975 个 `has_out=1`；记 `TRUNCATED_ROW=1` 进分母，不删除） |
| `phase=1` | **156 行**（replay 窗口；每组的副本） |
| `has_out=1` | 可解析 **974 行** + 1 条截断行 = **975** 个 `has_out=1` |
| `grp_idx` | 885 个组；156 个组出现两次（live/replay） |
| `scan_first_ns` | 全为 **-1 哨兵**；有效跨度用 `(previous distinct scan_last, scan_last]` |

`vec6 = state_propagat - state_ [0..5]`（has_out=1 且在 StateEstimation 之后）；按 host 的
`StatesGroup::operator-`，`vec6 = [Log(R_post^T R_pre), pos_pre - pos_post]`。因此
`R_pre = R_post · Exp(vec6_rot)`，`e_I = [-vec6_rot, -R_pre^T vec6_pos]`；
`R_post` 取 `M2DGR_room_02.txt` 的 P⁺ 位姿（S2/审阅已确认：`pose_output_en` 在 StateEstimation
之后写 `_state.pos_end/rot_end`，body→world；与 trace 的 `abs_ns` 同源同帧）。join **按时间**、
只用 `has_out=1`；replay 时间重复，同一时间组内按 trace 顺序（phase0 先、phase1 后）取 pose 行。
975 行对 974 个可解析 has_out + 1 截断，时间差 ≤512 ns（double 秒量化/ulp，不是漂移）；
重复时间组 156 个，已按 phase 分开统计。`Ppre/Ppost` 为 rot+pos 6×6 块；状态顺序/右扰动/body 由 trace 头声明。
`S` 不导出，`r_*` 不是位姿协方差；`mat_pre/mat_out` 因 VIO/LIO 双写、handler 不可区分，未用于 e_I。

## 3. join（跨度包含，多对一）

规则：`previous distinct scan_last < scan_stamp_ns ≤ scan_last`（等价于 `scan_first..scan_last`
包含，`scan_first=-1` 哨兵已按有效跨度解释）；不用精确相等/±1 ms/nearest。

| 项 | 值 |
|---|---|
| availability 行 | **531**；映射 **530**；`NO_TRACE_ROW` **1** |
| 精确相等 | **1 / 531**（其余靠跨度包含） |
| 使用的组 | **413** 组：296 组各 1 个 availability 行、117 组各 2 个（多对一） |
| availability 行映射到的组行数 | 217 组 1 行、276 组 2 行、37 组 4 行（live+replay/合并） |
| 多 `grp_idx` 行 | **257 / 530**：同一 `scan_last` 下有 2 个 `grp_idx`；`t2_join.jsonl` 显式列出全部，I 取 phase0 行 |
| phase 覆盖 | 437 行只对应 live 组；93 行对应含 replay 的组（仍取 phase0） |
| 未映射的 1 行 | 最后一个 availability 扫描超出最后一个**可解析**组的 `scan_last`；截断行无法提供跨度 → 记 `NO_TRACE_ROW` 进分母，不删除 |

**多对一的真实结构**：`scan_last` 共 **590** 个不同值，其中 **295 个值由 2 个 `grp_idx` 共享**
（另 295 个只有 1 个），这就是 257 行 availability 出现两个 `grp_idx` 的原因——**合并组/同末时刻的
capture 组**；每个 availability 行映射到的全部 `grp_idx`、`trace idx`、phase、has_out 都写在
`t2_join.jsonl`。每组扫描数分布：trace 行/组 1:217、2:276、4:37；availability 行/组 1:296、2:117。

## 4. 通道证据（531 个 availability 行）

| 通道 | 值 |
|---|---|
| M（node_map NIS） | **444** 行 present |
| T（prev_scan NIS） | **86** 行 present |
| I（`vec6`+`Ppre`，`has_out=1`） | **504** 行 present；26 行 `HAS_OUT_0`；1 行 `NO_TRACE_ROW` |
| I 的 `Ppre` 秩 | 504/504 秩 **6** |
| pose join | **CONFIRMED_POST_POSE_TIME_JOIN**；重复时间组 156 个，phase 分开 |
| I 的 `|e_I|`（与符号无关） | min 0 / median **0.0183** / max **1.545** |
| I 的 `s_I`（精确 e_I，Ppre 可观测子空间） | min 0 / median **70.39** / max **5953** |

旧 status × M/T：

| 旧 status | M only | T only | 都无 |
|---|---:|---:|---:|
| AVAILABLE（351） | 351 | 0 | 0 |
| UNAVAILABLE（180） | 93 | 86 | 1 |

**M/T 分母与覆盖**（531 个 availability 行）：

| 通道 | present | 占比 | both | neither |
|---|---:|---:|---:|---:|
| M（node_map） | **444** | 83.6% | 0 | — |
| T（prev_scan） | **86** | 16.2% | 0 | 1 |

**I 的分位表**（精确 e_I，n=504；`−vec6` 近似作对照）：

| 量 | min | p10 | p50 | p90 | max |
|---|---:|---:|---:|---:|---:|
| `|e_I|` 精确 | 0 | 0.00602 | **0.01827** | 0.06075 | 1.54496 |
| `|e_I|` 近似 | 0 | 0.00602 | 0.01827 | 0.06075 | 1.54496 |
| `s_I` 精确 | 0 | 4.047 | **70.39** | 413.8 | 5953.3 |
| `s_I` 近似 | 0 | 3.914 | 66.87 | 411.6 | 5937.9 |
| 平移 `|e_t|` 精确 | 0 | 0.00508 | 0.01662 | 0.05365 | 1.54424 |

**按 phase 的 I 描述统计**（不分类）：

| phase | has_out=1 行 | `|e|` median/max | `s` median/max |
|---|---:|---|---|
| 0（live） | 818 | 0.0185 / 1.545 | 67.0 / 5953 |
| 1（replay） | 156 | 0.0425 / 0.145 | **869.1** / 9714 |

replay 的 `s` 明显更大，说明 replay 的 `Ppre` 尺度与 live 不同；**不能**据此判异常，只作上下文。

**精确 vs 小角近似**（504 行）：`|e_I|` 的范数相同（旋转不改变范数），但平移**方向**不同——
`‖e_trans_exact − e_trans_approx‖` 中位 **0.0096 m**、最大 **2.64 m**，**475/504 行**差异超过 1%；
`s_I` 中位 70.39（精确） vs 66.87（近似）。所以**精确值为主结果**，`−vec6` 只作对照；大旋转
（最大 |e| 1.545 由平移主导）时近似会明显失真。

## 5. 块与 UNKNOWN 区间

| 项 | 值 |
|---|---|
| 0.5 s 块 | **120** 块（覆盖 **60.0 s**），全部 UNKNOWN |
| 原因 | `CALIBRATION_BLOCKED:no_normal_reference`；部分块另带 `I_HAS_OUT_0`/`I_NO_TRACE_ROW` |
| 普通 UNKNOWN | **108 块 / 54.0 s**，最长连续 **54.0 s**（0–54 s，单段） |
| `POST_E2_NO_CATCHUP` | **12 块 / 6.0 s**，最长连续 **6.0 s**（54–60 s，单段） |
| 非尾段 / 尾段行 | 480 / **51** |
| 尾段处理 | E2 后宿主发散到约 520 m、`catch_up=NOT_IMPLEMENTED`；只作分段报告，不作连续接回正常证据 |

**`NORMAL_CONSISTENT` / `SUSPECT` / 误报 / 漏检 / 延迟 / 错误 NORMAL 全部 `NOT_EVALUABLE`**：
原因不是实现，而是 `ALI-B2-NORMAL-LABELS-20261112-01` 缺独立正常参照与事件标签。
**“全 UNKNOWN”不等于零风险**——它表示这些帧的可信状态未知、不能据此判定正常；
不得用 UNKNOWN 数量冒充误报为零。

## 6. 逐项自检

| 项 | 状态 | 证据 | 下一动作 |
|---|---|---|---|
| 输入/run/build/身份 | **PASS** | receipt + sha256（`t2_summary.json._meta`） | — |
| detection on / status / support 非空 | **PASS** | 351 AVAILABLE、180 UNAVAILABLE；support 531/531 非空 | — |
| trace 形状（按名） | **PASS（1 行截断已记录）** | 1041/1042 可解析；第 1048 行 53 列 | 需 S2 补最后一行或声明截断 |
| join 跨度包含、多对一显式 | **PASS（1 行 NO_TRACE_ROW）** | `t2_join.jsonl` 531 行，含 grp/phases/has_out | — |
| M/T 证据 | **PASS** | 444 / 86 | — |
| I 证据存在与可算 | **PASS（504，秩 6）** | 精确 e_I（vec6 + M2DGR P⁺，时间 join、phase 分开）；s/|e| 分位表 | — |
| NORMAL/SUSPECT 分类 | **BLOCKED / NOT_EVALUABLE** | 无独立正常参照/标签（ALI-B2） | 等用户选 A/B/C |
| 误报/漏检/延迟/错误 NORMAL | **NOT_EVALUABLE** | 同上；受控注入标签只可离线评价 | — |
| UNKNOWN 区间 | **PASS** | 120 块/60 s，尾段 12 块 | — |
| 修复收益 | **NOT_EXECUTED** | ack applied=0/dropped=42 | 不用本 run 下结论 |
| 成本 | **PASS（本地）** | T2 脚本 1.97 s、峰值 RSS 218 MB；`t2_join.jsonl` 428 KB、`t2_summary.json` 26 KB | — |
| 生产集成 | **NOT_APPLICABLE** | shadow 不写 manager/native | 用户另行确认 |

## 7. 能推出 / 不能推出

**能推出**：
1. 新 trace 的 I 通道**已存在且可算**：504 个 availability 帧有 `has_out=1` 的 `vec6/Ppre`，`Ppre` 满秩；
   M/T 也齐全（444/86）。这是旧 402/544 没有的能力。
2. 跨度包含 join 可用：530/531 映射；精确相等只有 1 个，证明"精确戳"会把人口判错；多对一 117 组
   与多 `grp_idx` 257 行必须在输出里显式保留。
3. 由于仍缺独立正常参照/标签，**所有状态只能 UNKNOWN**；这不是 ALI-H 的实现失败，是校准/标签缺项。
4. 本 run 的 repair `applied=0/dropped=42`，不能用于修复收益；E2 尾段发散且无 catch-up，只作
   分段报告。

**不能推出**：ALI-H 的 NORMAL/SUSPECT 效果、误报/漏检/延迟、错误 NORMAL 率；SUSPECT 在真实冲突
上的判别力；修复收益或连续接回正常。这些都需要 `ALI-B2` 的用户选择（A/B/C）。

## 8. 复现

```bash
~/mm/micromamba run -p ~/mm/ros python -I docs/ali_h_v1_research/t2_run.py \
  --run /tmp/fl_native_20261112T115734Z_483777
```

只读 trace/availability/receipt；输出 `t2_summary.json`、`t2_join.jsonl`；不跑宿主、不改生产代码。
