# UNAVAILABLE 逐帧取证：一次检测 on 的有限诊断

任务：`docs/UNAVAILABLE_DIAGNOSTIC_TASK_20261112.md`。本轮只做一次检测 on 的有限诊断，不改检测/
阈值/门/模型，不新开参数矩阵。日志实现由 S1 完成（main `8bbef74`，`--availability-log`），本
run 只使用它并做离线核对。

## 1. 运行与身份

| 项 | 值 |
|---|---|
| run | `fl_native_20261112T065500Z_187992` |
| 命令 | `AVAILABILITY=1 WAIT_LIMIT=2.0 bash slam_recovery/ros/run_native_loop.sh /tmp/fastlivo/hall01_two_event_v1.bag --detection on --candidate-source host_poses --sigma-meas-m 0.884 --drain 20` |
| 模式 | `ONLINE_DETECTION`（检测 **on**，非 scripted 触发、非 oracle） |
| 驱动源码 sha | `93f693566111…`（含 S1 的 availability log） |
| 宿主库 sha | `9c0330beffa2…`（v3）；可执行文件 `0d7e23de…` |
| 输入 | `hall01_two_event_v1.bag`，sha `c3e905da…` |
| 配置 | `m2dgr.yaml` / `camera_m2dgr.yaml`，sha 见 `receipt.json` |
| 负载 | `77.05 143.72 198.72`，nproc 128 |
| 终态 | `HEALTHY`（wiring all_ok） |

## 2. 逐帧原件

`availability_frames.jsonl`：**402 行 = 本次 paired 人口 402**（`run_summary.frames.paired=402`）。
无 2000 条上限截断。原件 gzip 在 `availability_frames.jsonl.gz`，sha 见
`availability_sha256.txt`（原文件 `50170392…`，gz `7a201845…`）。

每行含：kf、pose/scan stamp 与 dt、`T_wb`、scan 点数、manager 状态/版本、support
（reason/radius/threshold/参考点数/抽样数/within 数/比例/抽样点）、NIS（current、trusted_total、
near_radius、prev_scan、selected source/点数、raw_kind/raw_reason、source、effective_nis、
holdout 的 k/残差/coverage/branch/分位/抽样点）、`support_pass`/`nis_present`/
`status_from_conditions`/`status`。

## 3. 按原因计数（分母 = 402，允许多因重叠）

**支持的失败原因**（`support.reason` + `pass`/`supported_fraction`；日志里"评估完成但不达标"
写作 `reason=ok, pass=false`，本节按 `pass` 归为 `insufficient_support`）：

| 类别 | 帧数 | 占比 | 说明 |
|---|---:|---:|---|
| `empty_reference` | 22 | 5.47% | trusted 参考为空（开局） |
| `insufficient_support` | 285 | 70.90% | 评估完成，within 比例 < 0.60 |
| `ok`（support_pass） | 95 | 23.63% | 支持通过 |

**NIS 的失败原因**：

| 类别 | 帧数 | 占比 |
|---|---:|---:|
| `computed_finite`（raw finite，source computed） | 401 | 99.75% |
| `not_computed:no_reference`（source unavailable） | 1 | 0.25% |
| `carried_forward` | **0** | 0% |
| `inf`/`nan`（非有限） | **0** | 0% |

**两项联合**：`support_pass=False & nis_present=True` **306 帧**；`False & False` **1 帧**；
`True & True` **95 帧**；`True & False` 0。可见本段 UNAVAILABLE 的主导原因**不是 NIS 缺失**，
而是**地图支持比例不足**；NIS 在 401/402 帧都算出了有限值（包括从 `prev_scan` 算的）。

`status` 可由两布尔逐帧重算：402 行 `status_from_conditions` 与 `status` **0 处不一致**。

## 4. 连续段

| 状态 | 行范围 | 帧数 | 起始 pose_stamp_ns | 结束 pose_stamp_ns |
|---|---|---:|---:|---:|
| UNAVAILABLE | 0–21 | 22 | 1627785262008174419 | 1627785264073572397 |
| AVAILABLE | 22–52 | 31 | 1627785264206571102 | 1627785267205767155 |
| **UNAVAILABLE** | **53–117** | **65** | **1627785267272356749** | **1627785273678019524** |
| AVAILABLE | 118–156 | 39 | 1627785273812009573 | 1627785279081910849 |
| UNAVAILABLE | 157–170 | 14 | 1627785279281777620 | 1627785281680577278 |
| AVAILABLE | 171–179 | 9 | 1627785281880469561 | 1627785283346364737 |
| UNAVAILABLE | 180–182 | 3 | 1627785283546281815 | 1627785283946079731 |
| AVAILABLE | 183–198 | 16 | 1627785284145961285 | 1627785286211474180 |
| **UNAVAILABLE** | **199–401** | **203** | **1627785286344705820** | **1627785306575157404** |

早期两段 UNAVAILABLE（22 + 65 = **87 帧**）与既往"87 帧窗口"的规模一致；中间夹着 31 帧
AVAILABLE。`segment_53_117.tsv` 给出该段逐帧的 support fraction / raw_kind / effective_nis /
source；203 帧段的逐帧原值在 JSONL 里（行 199–401）。

## 5. 离线复算（用保存的抽样点与残差）

| 帧 | 状态 | support 保存/分母 | support within 复算 | NIS 保存/分母 | NIS 复算 | 结论 |
|---|---|---|---|---|---|---|
| 22（正常边界） | AVAILABLE | 20 / 200 | 15/20 = **0.75**（报告全样本 0.88） | 20 / 300 | mean χ² = **0.889**（报告 18.281） | support 子样本不能复现全样本比例；NIS 的 20/300 子样本**不能复算报告均值**（保存的是确定性子样本，非代表抽样） |
| 53（不可用反例） | UNAVAILABLE | **200 / 200** | 39/200 = **0.195** = 报告值 | **300 / 300** | mean χ² = **10.156722** = 报告 NIS | **精确复算**；support_pass=False → status 重算 UNAVAILABLE |
| 157（不可用反例） | UNAVAILABLE | **200 / 200** | 63/200 = **0.315** = 报告值 | **300 / 300** | mean χ² = **403.642606** = 报告 403.642606 | **精确复算**；valid 23/300、coverage 0.077 |

结论：**不可用帧的点级证据是完整的**（support 200 点、NIS 300 残差全部保存），可精确复算
within 比例、NIS 均值和最终 status；**正常帧只保存 20/200 与 20/300 子样本**，不足以复算
全样本指标（任务 §3 允许"固定预算不足时明确缺项"，这里就是该缺项）。

## 6. 结论与边界

- **未进检测器的代码分支**：307 帧 UNAVAILABLE 中，306 帧是 `_frame_has_reference_support`
  的 within 比例 < 0.60（support_pass=False），1 帧是参考为空且 NIS 无参考
  （`empty_reference` + `not_computed:no_reference`）。没有一帧是"有新 NIS 证据但被支持条件
  排除"以外的原因——NIS 在 401/402 帧都算出了有限值，支持条件是唯一的普遍前置门槛。
- **旧值沿用**：本 run `carried_forward=0`；`source` 只有 `computed` 与 `unavailable`。
- **非有限**：`inf/nan` 0 帧。
- **UNKNOWN**：support 比例为何在 53–117 与 199–401 持续低于 0.60（几何退化、参考覆盖变化、
  还是地图与当前位姿的偏移），本诊断**不能给出因果**；日志只给当时参考与样本，不给真值。
  不从"unsupported"直接推"必然漂移"。
- **NOT_EXECUTED**：支持索引的"精确最近距离"诊断未做——日志的支持索引找到即短路，只记录
  within_1m；精确最近距离需要对保存的 200 点与同一参考离线重算，本轮没有另建参考快照。
  记为 NOT_EXECUTED，不用首个命中距离冒充全局最近距离。
- **NOT_EXERCISED**：`carried_forward` 字段实现但本 run 未触发；缺 pose/scan 的输入缺项也
  未出现（402 帧都有有效 pose 与 scan）。两者标 NOT_EXERCISED，不是 NOT_IMPLEMENTED。
- 诊断前后计算不变：本 run 只加日志开关，`available` 判据、NIS 计算、检测决定未改；S1 的
  开/关一致性测试在两半会话都通过。
- 不能声称：自动检测通过、恢复成功、或未支持帧必然漂移。诊断文件条数不是检测结果。

## 7. 文件

| 文件 | 内容 |
|---|---|
| `availability_frames.jsonl.gz` | 402 行逐帧原件（gzip；原文件 sha 在 `availability_sha256.txt`） |
| `analysis.json` | 计数、9 个连续段、3 帧复算结果（由 `analyze_availability.py` 生成） |
| `analyze_availability.py` | 复算脚本 |
| `segment_53_117.tsv` | 65 帧段的逐帧 support fraction / raw / effective NIS |
| `receipt.json` / `wiring.json` / `run_summary.json` / `candidates.jsonl` | 运行原件 |
| `recovery_node.log` / `machine_load.txt` / `recovery_node_source.sha256` | 运行环境与版本 |

## 8. 后续：位姿-地图分解（第二次诊断）

`predicted_pose/REPORT.md`：同输入、检测 on 的第二次诊断，S1 新增
`support_under_predicted_pose`。本 run 544 行（paired 544；上一轮 402，人口随 run 变化）、
预测支持非空 480、null 64。联合计数：both_low 301、both_pass 82、only_host_low 50、
only_pred_low 47。分段落判读：**位姿漂移段 147 帧**（147–173、228–280、396–462，预测中位
0.48–0.515 vs 宿主 0.0–0.025，50 帧预测位姿过阈值）、**覆盖不足段 191 帧**（两套都低）、
预测更低 54 帧（UNKNOWN）、null 64 帧。上一轮同戳窗口在本 run 已有 37/65 帧 AVAILABLE——
UNAVAILABLE 依赖该 run 的地图/位姿状态，不是输入的固定属性。检测/阈值/门/模型未改。
