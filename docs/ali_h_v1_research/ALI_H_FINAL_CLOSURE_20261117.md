# ALI-H（F2）资格-only 收口（2026-11-17）

**用户决定**：2026-11-17 在三选项中选定 **① 接受资格-only 收口**。本文件为最终口径；
此后 ALI-H 不再以「检测指标未评」为开放项挂起，而是明确：**能报什么、不能报什么、缺什么才能越过这一上限**。

**证据范围**：仓库内既有归档（`docs/ali_h_v1_research/`、`docs/milestone_m0_keys.json`、
`docs/DAILY_20261109.md`、`docs/review_20261110_*`）。本收口**没有**新增运行、注入、数据或外部参考。

## 1. 结论

- **C2（独立正常前缀）`BLOCKED`**：归档中不存在经独立确认的正常参照。
  `docs/ali_h_v1_research/manifest.json` 的 `normal_reference` 为空/`BLOCKED`；
  M0 的 132 帧 `healthy_prefix` 只是机械定义（`ts < onset`），且属另一 run/bag，不能当正常真值。
- **C3（声明式注入标签）`BLOCKED`**：存在版本化注入窗口（M0 `INJECTION_ORACLE` 19.939 s / 200 帧；
  E1/E2 文字声明），但**没有与 ALI-H run 同 run、逐帧、已登记的标签**；`labels.jsonl` 为空。
- **C4（检测指标：召回/延迟/误报/错误 NORMAL）`NOT_EVALUABLE`**，依赖 C2/C3。

## 2. 可以报（有原件、可复算，均为离线资格层）

| 项 | 数值/状态 | 原件 |
|---|---|---|
| v7 join | `HEURISTIC_UNPROVEN`；531 availability/60 s | `T2_RESULTS.md` |
| v8 join | `TRUE_SPAN_CONTAINMENT_WITH_512NS_QUANTIZATION`；444/444；仅覆盖 rel 49.11 s | `T2_JOIN_UPGRADE.md:11,23-26,38` |
| v11 join | `TRUE_SPAN_CONTAINMENT_WITH_512NS_QUANTIZATION`；paired/availability **482/482**，481/482 映射、1 `NO_TRACE_ROW` | `T2_V11_RESULTS.md:16,19` |
| v11 块 | **106 块 / 53.0 s 全部 UNKNOWN**（普通 42 块/21.0 s，E2 后 64 块/32.0 s） | `T2_V11_RESULTS.md:20` |
| v11 单位权 `|e_I|²` | p10 4.161e-5 / p50 1.1726e-3 / p90 1.2931e-2 / max 0.34893 | `T2_V11_RESULTS.md:32` |
| v11 协方差 | `NOT_AVAILABLE`（混合约定、无已验证 6D 切空间） | `T2_V11_RESULTS.md:42,44` |
| 402/544 | 946 帧；A 307/402 UNAVAILABLE、B 412/544 等结构统计 | `REPORT.md` |
| 成本 | T0 3.03 s / 28.4 MB；T2 1.97 s / 218 MB | `REPORT.md`、`T2_RESULTS.md` |

## 3. 不得报（写成 0 或 N/A 都算错误）

- `NORMAL_CONSISTENT` / `SUSPECT` 分类、正常段误报率、漏检、检测延迟、错误 NORMAL；
- 「全 UNKNOWN 即零风险」或把 UNKNOWN 当正常负例；
- 任何卡方/概率/健康风险分（协方差 `NOT_AVAILABLE`，`s_I` 只是诊断）；
- 修复收益、连续接回、净收益；
- FAST-LIO 同 update 的 M/T/I/support 或检测指标（导出未交付）。

## 4. 越过这一上限所需（保留，不自行启动）

1. 一个**经独立确认的正常参照**（来源、时间区间、确认方法、输入 hash；每 `(channel, map_support)`
   至少 20 个有效 0.5 s 块）——用户曾可选的「hall_01 Leica 3-DoF GT 代理参照」属于此类，需单独授权；
2. 与该参照**同 run、逐帧**的事件标签（现有注入窗需做身份 join；注入 onset ≠ 故障 onset）；
3. 新运行/新注入/新数据的预算与用户授权。

以上任一启动前，本收口维持；不把「未评价」写成「已解决」，也不把「资格-only」写成方法有效或无效。
