# T2 v11 结果：同行 pre/post、I 资格 PASS_SAME_ROW（2026-11-13）

> 输入：既有 run `fl_native_20261112T165438Z_669633`（库 `81b35f92…`、driver `c5efdd73…`、
> detection on、K=1、无 scripted）。**只读既有原件**；按用户 2026-11-13 指令，不新开
> FAST-LIVO2 运行/构建/适配、不要求新导出。**单独记账，不与 v7/v8 合并。**
> `ALI-B2` 仍等用户；分类/误报/漏检/延迟/错误 NORMAL 全部 `NOT_EVALUABLE`。
> **本文件为最终版**；不再为补数据做任何新宿主工作。

## 0. 一页表（最终版）

**人口**

| 项 | 值 |
|---|---|
| run | `fl_native_20261112T165438Z_669633`（ONLINE_DETECTION，HEALTHY） |
| paired / availability | **482 / 482**；129 AVAILABLE / 353 UNAVAILABLE |
| trace | **792 × 107**；0 malformed/0 truncated；`has_out=1` **725**；phase 全 0 |
| 同帧 pre/post | **725**（`same_row_pre_post_rows = same_row_post_pose_rows = 725`） |
| join | **TRUE_SPAN_CONTAINMENT_WITH_512NS_QUANTIZATION**；481/482 映射、1 `NO_TRACE_ROW`、246 行多对一 |
| 块 | **106 块 / 53.0 s，全部 UNKNOWN**；普通 42 块/21.0 s，E2 后 **64 块/32.0 s**（21.0–53.0 s） |
| 事件 | 第 2 段 trigger **rel 17.0029 s**、deadline **21.0029 s**（从本 run `episode_detail` 读取，非旧 54 s）；deadline 前 **179 行**、后 **303 行** |
| 段/接纳 | 2 段均 `LATE_AFTER_BOUNDARY`，**0 accepted**；E2 后输出不是合法 catch-up |

**通道与 I 分位**

| 项 | 值 |
|---|---|
| M / T / neither | **175（36.3%） / 306（63.5%） / 1** |
| I | **462**（Ppre 秩 6：462）；其中 **18 条 `eff=0` 且 Log 全零**（无有效点面约束），保留在分母；全 725 行中 `eff=0` **37** 条 |
| I（有效点面约束） | **444**（462 − 18；仅作分母说明，不剔除） |
| `|e_I|`（真 SE(3) Log） | p10 **0.00645** / p50 **0.03424** / p90 **0.11370** / max **0.59071** |
| 单位权 `|e_I|²`（I 主量） | p10 **4.161e-5** / p50 **1.1726e-3** / p90 **1.2931e-2** / max **0.34893** |
| `s_I`（诊断，不作卡方） | p10 1.461 / p50 **57.68** / p90 497.4 / max 25799.7 |

**资格**

| 项 | 状态 |
|---|---|
| `RAW_HEADER_CONTAINMENT` | **PASS**（真实 header 跨度 + 512 ns 量化，数值成立） |
| `SAME_UPDATE_PRE_POST` | **PASS**（725 行同行 pre/post；抽 3 行） |
| `COMPLETE_POINT_MEMBERSHIP` | **`ASSERTED_NOT_VERIFIED`**（cur 接上次 next carryover；`n_scans` 只计新 pop raw；同一 header 可出现在两个更新组） |
| `COVARIANCE_6D` | **`NOT_AVAILABLE`** |
| `vec6` | **`NOT_VERIFIED`**（仅对照，不是 e_I 来源） |
| 协方差 | **`NOT_AVAILABLE`**（混合约定；无已验证 6D 切空间） |
| 总体 I | **`PASS_SAME_ROW_UNIT_WEIGHTED`**（限定：不是 462 个合格独立 I 观测；18 条零约束单列） |

**三条限定**

1. `vec6` 仍 `NOT_VERIFIED`、协方差 `NOT_AVAILABLE`；`s_I` 只是诊断，**不作卡方/概率**。
2. 两段均 `LATE_AFTER_BOUNDARY`、0 accepted；**不用于修复/接纳/连续接回**任何结论；E2 后 64 块/
   32 s 只是"宿主继续在回滚地图上输出"，不是 catch-up。
3. 分类/误报/漏检/延迟/错误 NORMAL 全部 **`NOT_EVALUABLE`**（`ALI-B2` 缺独立正常参照与事件标签）；
   **"全 UNKNOWN"不是零风险**。
4. **18 条 `eff=0` 且 Log 全零**（全 725 行中 37 条）：零修正不证明 IMU 与 LiDAR 物理一致，
   **不能作为 NORMAL 的 I 支持**；保留在分母，不悄悄剔除。

## 1. 运行与人口

| 项 | 值 |
|---|---|
| run id | `fl_native_20261112T165438Z_669633` |
| run mode / 终态 | `ONLINE_DETECTION`；`HEALTHY`（kf 295） |
| paired / availability | **482 / 482**；129 AVAILABLE + 353 UNAVAILABLE；support 482/482 非空 |
| trace | **792 行 × 107 列**，0 malformed / 0 truncated；`has_out=1` **725**、`has_out=0` 67；phase 全 0 |
| 同帧 pre/post | `same_row_pre_post_rows = 725`；同行 `pose7`+`pre_pose7` |
| 两个段 | `checkpoint_checks` 均 `LATE_AFTER_BOUNDARY`；**0 accepted** |
| E2（第 2 段） | trigger rel 17.0029 s、deadline 21.0029 s；输出到约 53 s → E2 后 64 块/32 s |
| eff=0 | 725 行中 37 条；462 条 I 中 18 条 Log 全零（无有效点面约束） |
| 修复/接纳 | **不用于**修复收益或连续接回结论 |

## 2. join（v11 真实跨度 + 512 ns 量化）

| 项 | 值 |
|---|---|
| status | **`TRUE_SPAN_CONTAINMENT_WITH_512NS_QUANTIZATION`** |
| 分母 | 482；mapped **481**；`NO_TRACE_ROW` **1** |
| 每组 | 481 组各 1 个 availability 行；246 行对应 2 条 trace 行（同 scan 戳的重复 LIO 行） |
| 多对一 | **246** 行；保留不拆组 |
| 精确相等 | 1 / 482（其余靠 512 ns 量化包含） |

## 3. 通道与块

| 通道 | 值 |
|---|---|
| M（node_map NIS） | **175 / 482（36.3%）** |
| T（prev_scan NIS） | **306 / 482（63.5%）** |
| M 与 T 都无 | 1 |
| I（同行 pre/post，`has_out=1`） | **462**；`Ppre` 秩 6：462 |
| I `|e_I|`（真 Log） | p10 0.00645 / **p50 0.03424** / p90 0.11370 / max 0.59071 |
| I 单位权 `|e_I|²` | p10 4.16e-5 / **p50 1.1726e-3** / p90 1.2931e-2 / max 0.34893 |
| `s_I`（诊断，不作卡方） | min 0 / median 57.68 / max 25799.7 |
| 块 | **106 块 / 53.0 s，全部 UNKNOWN**；普通 42 块/21.0 s；E2 后 64 块/32.0 s |

## 4. 同帧配对验证（升级依据）

抽 3 行（trace idx 4/5/6）核对：

- `pose7` 的位置与 `M2DGR_room_02.txt` 同时间最近行一致到 **≤1 mm**（时间差 −512/−256/0 ns）；
- `pre_pose7` 与 `pose7` 不同，四元数范数均 **1.0±1.2e-11**；
- `pre→post` 位移与 `vec6` 平移相比同量级（如 0.0032256 vs 0.0032171 m）；
- parser 正常控制 `selftest107` **PASS**（pose/pre_pose 各 7 值逐位一致）。

因此 **pre/post 均为同行、同帧**；`e_I = Log(inv(pre)·post)` 的 SE(3) Log（含 `V⁻¹`）可直接使用。
`mat_lio_*` 有 S2 已确认的 off-by-one（idx N = trace N+1），**未用于 e_I**，最多用 `idx+1` 交叉核对。

## 5. I 资格（v11）

| 项 | 状态 | 依据 |
|---|---|---|
| `RAW_HEADER_CONTAINMENT` | **PASS**（真实跨度 + 512 ns 量化） | `scan_first/last` 真实、481/482 映射 |
| `SAME_UPDATE_PRE_POST` | **PASS**（725 行同行） | pre/post 同帧 |
| `COMPLETE_POINT_MEMBERSHIP` | **`ASSERTED_NOT_VERIFIED`** | carryover、`n_scans` 只计新 pop raw、同 header 可出现在两个更新组 |
| pre 位姿 | **`PASS_SAME_ROW`** | 同行 `pre_pose7`；3 行抽检 + 725 行 |
| post 位姿 | **`PASS_SAME_ROW`** | 同行 `pose7`；与 M2DGR 同时间一致 |
| `vec6` | `NOT_VERIFIED` | 仅作对照，不再作为 e_I 来源 |
| 协方差 | **`NOT_AVAILABLE`** | 混合约定；无已验证 6D 切空间 |
| 总体 I | **`PASS_SAME_ROW_UNIT_WEIGHTED`**（限定：不是 462 个合格独立 I 观测；18 条零约束单列） | e_I 真实；主量为单位权 `|e_I|²`，不作卡方 |

## 6. 能推出 / 不能推出

**能推出**：v11 的 462 个 availability 配对帧有同行 pre/post 的**真实 e_I**（单位权），
`I_present=462`；M/T 分母与旧 run 同口径但**单独记账**；106 块全 UNKNOWN。

**不能推出**：NORMAL/SUSPECT/误报/漏检/延迟/错误 NORMAL（`ALI-B2`）；修复收益或连续接回
（两段 `LATE_AFTER_BOUNDARY`、0 accepted）；协方差归一化的卡方概率（`NOT_AVAILABLE`）。

## 7. 复现

```bash
~/mm/micromamba run -p ~/mm/ros python -I docs/ali_h_v1_research/t2_run.py \
  --run /tmp/fl_native_20261112T165438Z_669633 --tag v11
```

输出 `t2_v11_summary.json`、`t2_v11_join.jsonl`；只读既有原件，不跑宿主。
