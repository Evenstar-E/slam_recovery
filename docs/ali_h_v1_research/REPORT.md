# ALI-H v1 真实数据验证：T0 证据盘点与 T1 构造控制（S3，2026-11-12）

> 任务：`docs/ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md` §10（契约 §2–§7）。
> 状态：**T0 EXECUTED / T1 EXECUTED / T2–T3 BLOCKED**。0 次宿主运行、0 个新参数矩阵；
> shadow 观察器只读归档，不写 manager/recovery 共享代码，不改旧归档文件。
> 实现：`ali_h_v1.py`（观察器）、`selftest.py`（T1）；配置/身份：`manifest.json`。
> T2 输入契约：`T2_INPUT_CONTRACT.md`；T2 评价协议（预注册）：`T2_PROTOCOL.md`
> （trace 结果前写死，不扫参数；S2 导出未到，T2/T3 仍 `BLOCKED`）。
> T2 开跑前三处修正：`T2_FIX_NOTES.md`。重大阻塞：`重大阻塞记录.md` 的
> **`ALI-B2-NORMAL-LABELS-20261112-01`**（无独立正常前缀/事件标签，等待用户确认）。
> 15 小时任务：`docs/OVERNIGHT_ALI_AUTODETECTION_TASK_20261112.md`；本文件是其中 S3 的研究交付。

## 0. 一句话结果

**现有两份归档都无法验证 ALI-H 的 NORMAL 分支**：设计要求 NORMAL 必须由"真实 I normal-compatible
+ M 或 T normal-compatible"共同支持，而两份归档的 I 通道均为 **NOT_AVAILABLE**；同时归档没有
独立确认的 normal 参照，所以连 SUSPECT 的报警也无法校准。T0 的全部 946 帧（402+544，分账）输出
**UNKNOWN**，并逐项给出缺的是哪一项。这不是"全 UNKNOWN 零风险"，而是**该数据无法回答该问题**。

## 1. 输入与身份（两 run 分账，不合并）

| 项 | Run A | Run B |
|---|---|---|
| run id | `fl_native_20261112T065500Z_187992` | `fl_native_20261112T070801Z_197026` |
| paired 帧 / 0.5 s 块 | **402 / 90** | **544 / 120**（含 1 个 NO_DATA 块） |
| `availability_frames.jsonl.gz` sha256 | `7a201845…36f82b` | `7492097a…79fa6b1` |
| receipt / run_summary sha256 | 见 `t0_A.json` | 见 `t0_B.json` |
| recovery_node 源 hash | `93f69356…` | `43c65a9d…` |
| 输入 bag | `hall01_two_event_v1.bag` `c3e905da…` | 同左 |
| 宿主库/可执行 | `9c0330be…` / `0d7e23de…` | 同左 |
| 检测 | on，非 scripted、非 oracle、无注入 | 同左 |

manifest 逐项记录代码 sha256、配置（块 0.5 s、alarm u≥.95、normal u≤.80、≥20 块、两相邻块）、
两份输入的 sha256，以及 `artifacts` 中 `t0_A/B`、`shadow_A/B`、`t1_selftest` 的 bytes 与 sha256。T0 两份归档合计 **3.03 s / 28.4 MB RSS**；shadow 输出 **shadow_A.jsonl 652,502 B / shadow_B.jsonl 891,001 B**（生成后未再追加，`wc -c` 测量）。**两 run 分别记账**，未把 946 帧当作同源独立样本。

## 2. T0：每帧/每块的通道资格与旧 UNAVAILABLE 人口

### 2.1 旧 UNAVAILABLE 原因（分母 = 各自 UNAVAILABLE 帧；允许多因）

| 原因码 | Run A | Run B |
|---|---:|---:|
| `insufficient_support`（1 m/60% 评估完成但 <0.60） | **285** / 307 | **351** / 412 |
| `empty_reference`（参考为空） | **22** / 307 | **61** / 412 |
| `nis_unavailable`（NIS 无值，重叠计数） | **1** / 307 | **1** / 412 |
| 全部 UNAVAILABLE | 307 / 402 | 412 / 544 |
| 旧 AVAILABLE | 95 | 132 |

**字段来源（必读）**：Run A 的 285 个比例失败帧在旧 `support.reason` 里仍写作 **`ok`**（旧字段未更新）；
本报告的 `insufficient_support` 是**派生值**（`pass == false` 且 `reference_points > 0`），不是旧档原因字段的原值。
Run B 的 351 个失败帧旧字段是 `fraction_below_threshold`，与本报告类别一致。`empty_reference` 在
两 run 都是旧字段原值（22 / 61）。复核时请按派生规则复算，不要以为 Run A 的旧字段与状态自洽。

### 2.2 通道实际证据（逐帧，`shadow_{A,B}.jsonl`）

| 通道 | Run A（UNAVAILABLE 中） | Run A（全部） | Run B（UNAVAILABLE 中） | Run B（全部） |
|---|---:|---:|---:|---:|
| **M**（node_map NIS，computed、有限） | **28** | 123 | **137** | 239 |
| **T**（prev_scan NIS，computed、有限） | **278** | 278 | **274** | 304 |
| **I**（IMU preupdate ↔ LiDAR update） | **0** | **0** | **0** | **0** |
| M 或 I | **28** | 123 | **137** | 239 |

M/T 互斥（一帧的 NIS 参考只能是一个来源）。旧 UNAVAILABLE 中：
- Run A 的 28 帧有 M、278 帧只有 T、1 帧两者都没有；
- Run B 的 137 帧有 M、274 帧只有 T、1 帧两者都没有。

**这就是结构上限**：即使有大样本 normal 参照，旧 UNAVAILABLE 里能进入 M 分支的只有
**28/307（9.1%，A）** 与 **137/412（33.3%，B）**；其余只有 T。而按 §5 判决表，T 单独正常
只能 UNKNOWN，**NORMAL_CONSISTENT 必须同时有真实 I**——所以两份归档的 NORMAL 上限是 **0**。

### 2.3 描述性分数（不分类，不给概率）

| run | 旧状态 | M 帧数 | M min/median/max | T 帧数 | T min/median/max |
|---|---|---:|---|---:|---|
| A | UNAVAILABLE | 28 | 0.78 / 76.41 / 795.7 | 278 | 0.11 / 5.58 / 799.3 |
| A | 全部 | 123 | 0.69 / 70.18 / 795.7 | 278 | 0.11 / 5.58 / 799.3 |
| B | UNAVAILABLE | 137 | 0.81 / 99.33 / 900.1 | 274 | 0.03 / 0.20 / 286.4 |
| B | 全部 | 239 | 0.67 / 69.07 / 900.1 | 304 | 0.03 / 0.19 / 286.4 |

这些是原始 NIS 量级，**不是异常概率**；M 与 T 的参考不同，数值不可直接比较。

### 2.4 校准资格（块级；OUT_OF_SUPPORT 与 BLOCKED 分开）

| 通道 | Run A | Run B |
|---|---|---|
| M | 35 块有证据：**29 BLOCKED（无 normal 参照）**、6 OUT_OF_SUPPORT（块内上下文混合）；55 块无 M | 57 块有证据：**42 BLOCKED**、15 OUT_OF_SUPPORT；62 块无 M + 1 块 NO_DATA |
| T | 58 块有证据：**56 BLOCKED**、2 OUT_OF_SUPPORT；32 块无 T | 71 块有证据：**63 BLOCKED**、8 OUT_OF_SUPPORT；48 块无 T + 1 块 NO_DATA |
| I | 90 块全部 NOT_AVAILABLE | 119 块 NOT_AVAILABLE + 1 块 NO_DATA |

normal 参照状态：**`BLOCKED:no_independently_confirmed_normal_reference`**。
两份归档都没有"由独立离线证据确认的正常前缀"；`HEALTHY`、trusted、无注入、预测支持通过
都没有被当作正常真值。块内同时含 EMPTY/LOW/SUPPORTED 的上下文按 `MIXED → OUT_OF_SUPPORT`
处理，不向最近的高支持格子借分布。

### 2.5 shadow 状态

| run | NORMAL_CONSISTENT | SUSPECT | UNKNOWN |
|---|---:|---:|---:|
| A | 0 | 0 | **402** |
| B | 0 | 0 | **544** |

原因逐条约在 `shadow_{A,B}.jsonl` 的 `shadow.reason_codes`：`NO_QUALIFIED_EVIDENCE` 为主，
`M/T` 的 `UNQUALIFIED/BLOCKED` 为次，I 恒为 `MISSING/NOT_AVAILABLE`。

## 3. T1：六条最小构造控制（全部 SYNTHETIC/UNIT）

| 测试 | 内容 | 结果 |
|---|---|---|
| T1.1 | 低支持 + 真实 I 正常 + T 正常 → NORMAL（RELATIVE_MOTION_ONLY）；只有 T 正常 → UNKNOWN | **PASS** |
| T1.2 | 低支持 + 合格 I 冲突 → SUSPECT；M 冲突 → SUSPECT（MAP_AND_MOTION），不被支持门屏蔽 | **PASS** |
| T1.3 | 无参考/无 I/carried → UNKNOWN；missing 不喂 0；缺证据不清除 last_suspect | **PASS** |
| T1.4 | 同一分数在 M/T 各自参照下结论不同；没有 LOW 参照 → OUT_OF_SUPPORT，不借 SUPPORTED | **PASS** |
| T1.5 | 同一物理标量在 SE(3) 重表达下不变（rel 1.7e-16）；块时间取自 pose_stamp，不发明 dt | **PASS** |
| T1.6 | **同一 trace（Run A 402 行）** shadow 开关前后：旧 status/NIS source/参考/分数/fraction 逐条相同；旧字段与输入一致 | **PASS** |
| T1.7 | 缺块/NO_DATA 打断 dwell：块 10、12 两个 ALARM 不跨空窗变 SUSPECT；last_suspect 保留；block_summary 补齐 NO_DATA 块 | **PASS** |

T1 全部标记 `marker: SYNTHETIC_UNIT`，不称真实恢复，不产生真实 NORMAL/SUSPECT。

## 4. T2/T3：BLOCKED（未执行）

| 项 | 状态 | 缺什么 / 下一动作 |
|---|---|---|
| 真实 I 通道 | **BLOCKED** | 两份归档无 IMU preupdate/update、区间、外参、协方差；输入 bag 只有 raw IMU/LiDAR，无 `imu_prop_odom`。需 S1/S2 在 LiDAR 更新点做**一次最小导出**（正常前缀 + 已声明退化窗 + 尾段），并先给 wall/message 预算 |
| normal 参照 | **BLOCKED** | 无独立确认的健康前缀；不能用 HEALTHY/trusted/无注入替代。已登记 `ALI-B2-NORMAL-LABELS-20261112-01`，等用户选择 A/B/C |
| 独立事件标签 | **NOT_EVALUABLE（归档）** | 两份归档没有事件标签；自注入标签只能离线评价，不能生成训练/评价真值 |
| T2 最小 trace | **NOT_EXECUTED** | S2 的 `fl_native_20261112T101116Z_329791` 宿主启动即 `image_transport` 插件缺失 terminate（`pose_messages: 0`、`paired: 0`），trace 未导出；不自行造 trace、不拼旧档。已知列序按名读取：`grp_idx`（322 值各两次、同 `abs_ns`）为物理扫描身份，`phase=1` 为 replay 窗口（第 489–810 行）；E2 后 rel≈54 s 尾段因 `catch_up=NOT_IMPLEMENTED` 发散到 520 m，只单列 `POST_E2_NO_CATCHUP`，不参与分类 |
| T3 同人口对照 | **NOT_EXECUTED** | 依赖 T2；当前只能交 T0 的证据资格与边界 |

## 5. 逐项自检（§8/§10.3 格式）

| 项 | 状态 | 证据 / 命令 | 受影响结果 | 下一动作 |
|---|---|---|---|---|
| 输入身份（两 run 分账） | **PASS** | `manifest.json`、`t0_{A,B}.json.inputs`；sha256 | — | — |
| 逐帧 M/T/I 来源、fresh/carried、资格、缺项 | **PASS** | `shadow_A.jsonl` 402 行、`shadow_B.jsonl` 544 行；I 显式 `present:false` | 全 UNKNOWN | — |
| 0.5 s 块、上下文、校准条件 | **PASS** | `t0_{A,B}.json.blocks`（90/119 块） | 全 UNKNOWN | — |
| 旧 UNAVAILABLE 原因人口 | **PASS** | §2.1；`old_unavailable_reasons` | — | — |
| 校准资格 OUT_OF_SUPPORT / BLOCKED 单列 | **PASS** | §2.4；`block_channel_status` | — | — |
| NORMAL 分支可测性 | **FAIL（设计上限 0）** | §2.2：I=0；§5 要求 I+M/T | 无法验证正常相容 | 需真实 I |
| SUSPECT 分支可测性 | **BLOCKED** | 有 M/T 证据但无 normal 参照 | 无 SUSPECT | 需正常前缀 |
| T1 七条控制 | **PASS 7/7** | `python -I … selftest`；`t1_selftest.json` | — | — |
| shadow 开关不变性 | **PASS（限定控制）** | T1.6，Run A 402 行逐条相同 | — | — |
| 真实 I trace | **BLOCKED/NOT_EXECUTED** | §4 | — | 等 S1/S2 |
| 同人口误报/漏检/延迟 | **NOT_EVALUABLE** | 无标签、无 I、无 normal 参照 | — | 等 T2 |
| T2 输入契约/校验器 | **PASS（准备，SYNTHETIC）** | `T2_INPUT_CONTRACT.md`、`t2_input_check.py`；18/18 合成测试（manifest 缺项/拒绝 S 与 H_T_H/旧 run id/左扰动与异切空间拒绝/恒定 offset 但身份不成立/缺时间对应/detection off/DISABLED availability/V⁻¹ e_I/s_I/单位权） | 真实 T2 仍 `NOT_EXECUTED` | 收到 trace 后按契约 §6 顺序核声明 |
| 计算成本/内存 | **PASS（T0 本地）** | T0 两份归档合计 **3.03 s**、峰值 RSS **28.4 MB**；shadow 输出 **652,502 B + 891,001 B**（`wc -c`，生成后未追加） | — | T2 时补生产侧成本 |
| 旧归档文件改写 | **NOT_APPLICABLE** | 只读；新文件全部在本目录 | — | — |
| 生产集成 | **NOT_APPLICABLE（未授权）** | shadow 不写 manager/native | — | 用户另行确认 |
| 重大阻塞登记 | **PASS（已提交）** | `重大阻塞记录.md`：`ALI-B2-NORMAL-LABELS-20261112-01`；trace 依赖单列 | — | 等用户确认 |

## 6. 能推出 / 不能推出

**能推出**：
1. 两份归档的 I 通道为 0，且输入 bag 不含 `imu_prop_odom`；按 §5，**NORMAL_CONSISTENT 在这两份数据上
   结构上不可产生**，不是"分类器调不好"。
2. 旧 UNAVAILABLE 中只有 28/307（A）、137/412（B）帧有 M 证据；其余只有 T，而 T 单独正常只能 UNKNOWN。
3. 没有独立 normal 参照时，SUSPECT 也无法校准；T0 全 UNKNOWN 是数据缺口的结果。
4. T1 的六条规则在合成输入上按契约工作；shadow 开关不改变旧决定（Run A 402 行逐条）。

**不能推出**：ALI-H 在真实数据上有效或无效；SUSPECT 的真实误报率；NORMAL 的真实覆盖率；
ALI-H 能提升 A/B 分或端到端恢复。这些都需要 T2 的真实 I + 正常参照 + 独立标签。

## 7. 复现

```bash
python -I docs/ali_h_v1_research/ali_h_v1.py t0         # T0: 两份归档，分账
~/mm/micromamba run -p ~/mm/ros python -I docs/ali_h_v1_research/ali_h_v1.py selftest   # T1
```

只读归档；不跑 ROS/宿主；不改旧归档文件。
