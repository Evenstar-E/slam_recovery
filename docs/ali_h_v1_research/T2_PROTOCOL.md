# T2 评价协议（预注册，2026-11-12，见新 trace 结果之前写死）

> 本文件在**任何新 trace 结果产生之前**写定。T2/T3 只按此协议执行；任何偏离必须另开
> `T2_PROTOCOL_DEVIATION_<date>.md` 记录，不改本文件。冻结配置沿
> `ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md` §4.2：**0.5 s 块、alarm u≥0.95、
> normal-compatible u≤0.80、每条件 ≥20 块、两个相邻有证据块**；**不扫参数**。
> 旧 402/544 只保留资格结论，不与新 trace 拼接（见 REPORT §0/§4）。

## 0. 预注册状态

| 项 | 值 |
|---|---|
| 写定时间 | 2026-11-12（UTC+8），trace 未交付 |
| 已知结果 | 无；本文件写定时未看过任何新 trace 的 ALI-H 输出 |
| 适用 | 新 trace 上的 T2（同人口旧方法 ↔ ALI-H 对照）与 T3（错误/成本） |
| 旧档 | 402/544 的资格结论已完成，不重算、不拼接 |

## 1. 人口与分母

### 1.1 输入与 join

- 新 trace 必须带同一次运行的 **availability 日志**（S1 的 `availability_frames.jsonl`）与
  **旧检测/manager 决定**；三者同 run id、同一 build、同一输入/配置/library sha256；
  **detection=on**（旧 402/544 也是 on），availability 的 `status` 不能全是 DISABLED，
  `support`/`support_pass` 必须非空。
- **按列名读取，不按位置**。导出身份：`grp_idx` 是物理扫描身份（已知 322 个值各出现两次、
  两次 `abs_ns` 相同）；`scan_first_ns`/`scan_last_ns` 是该合并组的 header 跨度（原 ns）；
  `phase` 是 native 阶段（`phase=1` = replay 窗口，已知第 489–810 行）；`has_out` 只对
  “有更新后状态”的行有效。绝对原 ns 与 double 量化/打印分开记录。
- **join 用跨度包含，不用精确相等/容差**：availability 的 `scan_stamp_ns` 是**单扫描 header 戳**，
  trace 的 `scan_last_ns` 是**合并组末时刻**，二者物理量不同；本 run 精确相等只有 1/531。
  判定为 `scan_first_ns ≤ S ≤ scan_last_ns`（合并组包含该扫描）；若 `scan_first_ns` 为 `-1`
  （本 trace 的哨兵），有效跨度取 `(previous distinct scan_last, scan_last]`。这是**包含关系**，
  不是 ±1 ms 近似。
- **多对一**：一个组可包含多条扫描；每个 availability 行必须显式写出映射到的 `grp_idx`（以及
  phase/has_out），不得只保留一个而丢掉其余。身份用 `grp_idx`，时间用 `abs_ns`。
- **I 端选行**：同一组有 live/replay 两行时，对 availability 行默认取 `phase=0` 行；若该组只有
  `phase=1`，取 replay 行并标注。`has_out=0` 的行无更新后状态，只记存在、不算 I。
- 未落入任何组跨度的 availability 行记 `NO_TRACE_ROW`（进分母）；trace 行无对应 availability 记
  `NO_AVAILABILITY_ROW`。不静默删除、不 nearest。
- 若 trace 与 availability 的 run id/build/输入 sha256 不一致：**STOP**，不作跨 run 贴接。
- **不要用时间差自证关联**：header 戳与末时刻不等、或 offset 非恒定，本身**不证明**原始扫描
  无法关联；反过来，**恒定 offset 也不证明**关联到的是同一扫描。只有身份对应不存在时才记
  `join_key_unresolved`。
- 不得用“把变 offset 的数据全删”制造好看人口；不得用 double 末时刻反推原始 header 整数。
- join 不上的 trace 行记 `NO_AVAILABILITY_ROW`；availability 有而 trace 无的行记 `NO_TRACE_ROW`。
  两者都进分母，明确列出。
- 若 trace 与 availability 的 run id/build/输入 sha256 不一致：**STOP**，不作跨 run 贴接。

### 1.2 帧级分母

| 人口 | 定义 |
|---|---|
| `all_trace_rows` | trace 的全部行（含 `has_out=0`、各 `phase`） |
| `has_out=1` | 有更新后状态的行；只有这些行能算 I |
| `paired` | join 上 availability 的行 |
| `unpaired` | `NO_AVAILABILITY_ROW` + `NO_TRACE_ROW`（分开报） |
| 每通道分母 | `M_present` / `T_present` / `I_present`；再分 `fresh` 与 `carried`；`missing` 单列 |
| 旧 UNAVAILABLE 子人口 | 仅在 paired 内，按旧 status 与原因码分层 |

所有率的分母都写清是 `all_trace_rows`、`paired` 还是某通道 `present`；未配对帧不进"检测率"，
但进"输入缺项/成本"。

### 1.3 块级分母

- 0.5 s 块按**传感器时间**（`scan_stamp_ns`，非 wall）；块边界 `floor(ts/0.5e9)`。
- 从首个到最后一个 trace 戳的每个块都进分母，包括**零行块**（`NO_DATA`）。
- 块内上下文：只有一个 `map_support` 类 → 该类；混合 → `MIXED`（该块所有通道 `OUT_OF_SUPPORT`，
  不向相邻块借分布）。
- 块内每通道取**fresh 样本分数的中位数**；`carried` 不算 fresh；无 fresh → 该通道该块 `MISSING`。
- 尾段、隔离/恢复段、`has_out=false` 段**全部包含**在主分母；另按段（正常前缀 / 声明退化窗 /
  尾段 / 恢复段）分层报告，但不从主分母删除。

### 1.4 分段与尾段（本次已知限制）

- 块在**单个 phase 内**形成，不跨 phase；跨界块按 phase 边界拆开或记 `MIXED_PHASE → OUT_OF_SUPPORT`。
- 本次 trace-on 在 **E2 之后（rel≈54 s 起）宿主位姿发散到 520 m**，原因是 restore 后没有
  catch-up（`catch_up=NOT_IMPLEMENTED`，属既有机制，不是宿主新缺陷）。
- 因此分类结论只在 **replay 窗口（`phase=1`，已知第 489–810 行）与其之前/声明的有效段**；
  E2 之后尾段**不进入** NORMAL/SUSPECT/错误率的分母，单列 `POST_E2_NO_CATCHUP`：
  报行数/时长，注明“宿主继续在回滚地图上运行、无追赶”，**不得**当作连续接回正常证据。
- 若 trace 的 phase/时间边界与上述已知值不同，以 manifest 声明为准并记录差异；差异无法解释 → `INCOMPLETE`。

## 2. 三状态的最小证据条件与 scope

### 2.1 通道 verdict（逐块）

| verdict | 条件 |
|---|---|
| `ALARM` | 该块分数在对应 `(channel, map_support)` 正常参照下 `u ≥ 0.95`，且**前一相邻证据块**也 `ALARM` |
| `NORMAL` | `u ≤ 0.80`，且前一相邻证据块也 `NORMAL` |
| `GREY` | `0.80 < u < 0.95` |
| `UNQUALIFIED` | 校准 `BLOCKED` / `INCOMPLETE(<20 块)` / `OUT_OF_SUPPORT`（混合上下文或无该条件参照） |
| `MISSING` | 本块无 fresh 样本；`STALE` 表示只有 carried |
| `NOT_AVAILABLE` | I 无导出（本 trace 若不满足契约即整列此值） |

`u = (1 + #{b ∈ B_c : b ≤ s}) / (len(B_c)+1)`；`B_c` 只来自**校准段**，永不来自评价段。

**相邻**指块号连续；中间缺一个块（`NO_DATA`/无 fresh）即打断持续性，不跨缺测累计 dwell。

### 2.2 状态判定（按优先级，先判 SUSPECT）

| 顺序 | 条件 | 状态 | scope | 原因码 |
|---|---|---|---|---|
| 1 | 任一合格 `M ALARM`；或真实 host hard-failure/reset 事件（声明、非 placeholder） | `SUSPECT` | M：`MAP_AND_MOTION`；host failure：`NONE`（事件自身声明范围） | `CONFLICT:M` / `HOST_FAILURE` |
| 2 | 任一合格 `I ALARM` | `SUSPECT` | `RELATIVE_MOTION_ONLY` | `CONFLICT:I` |
| 3 | 仅 `T ALARM` | `SUSPECT` | `RELATIVE_MOTION_ONLY` | `MEASUREMENT_INCONSISTENT:T` |
| 4 | `I NORMAL` 且（`M NORMAL` 或 `T NORMAL`） | `NORMAL_CONSISTENT` | `MAP_AND_MOTION`（有 M）/ `RELATIVE_MOTION_ONLY`（仅 T） | `NORMAL_PAIR` |
| 5 | `M NORMAL` 但无 `I NORMAL` | `UNKNOWN` | `NONE` | `M_NORMAL_WITHOUT_I` |
| 6 | 仅 `T NORMAL` | `UNKNOWN` | `NONE` | `T_ONLY_RELATIVE` |
| 7 | 全部 `GREY`/`UNQUALIFIED`/`MISSING`/`STALE`/`NOT_AVAILABLE` | `UNKNOWN` | `NONE` | 逐项列出 |

- **NORMAL 必须同时有 I**；没有 I 时 `NORMAL_CONSISTENT` 恒为 0（这是设计约束，不是实现选择）。
- `scope` 只授予实际支撑证据的通道：M → `MAP_AND_MOTION`；T/I → `RELATIVE_MOTION_ONLY`；
  `NORMAL_CONSISTENT` 的 `RELATIVE_MOTION_ONLY` 不等绝对地图可信。
- `MIXED` 上下文、低支持 M 无合格参照 → M 失格，不得升级成 SUSPECT 或 NORMAL。
- 旧 `HEALTHY`/trusted/预测支持通过不进入任何 verdict。

## 3. 校准与评价分离

1. **正常参照来源**：必须是**独立确认的正常前缀**（S1/S2 在 trace 交付时声明，附独立离线证据，
   并在看到 ALI-H 结果之前写进 trace manifest）；或单独指定的正常开发输入。
   `HEALTHY`、trusted、无注入、预测支持通过**都不算**独立确认。
2. **分段**：校准段与评价段时间**不重叠**；校准段先于评价段。若正常前缀不足 20 个有证据块，
   该条件 `INCOMPLETE`；缺 LOW 条件参照 → `OUT_OF_SUPPORT`，不借 SUPPORTED 分布。
3. **在线不更新**：V1 确认阶段不在故障/隔离/UNKNOWN 期更新正常参照；正常参照只来自校准时一次
   固定的 `B_c`。
4. **注入标签**：只用于离线评价；不进入在线分类、不进入 `B_c`。若正常前缀与注入窗重叠，
   该段不能作校准。
5. **评价段**：新 trace 的其余全部块（含尾部/恢复段），按 §1.3 的完整分母；不按结果挑选子集。

## 4. 错误、延迟与缺项

| 指标 | 定义 | 分母/边界 |
|---|---|---|
| 漏检 | 独立已标事件区间内没有任何 `SUSPECT` 块 | 事件级；未标段不当负例 |
| 检测延迟 | 事件区间内首个 `SUSPECT` 块起点 − 事件 onset；无 SUSPECT 则记 MISS | 事件级；标签无 onset 时 `NOT_EVALUABLE` |
| 误报 | 评价段内**独立确认为正常**的子段中 `SUSPECT` 块数 / 实际暴露小时 | 曝光 <1 h 只报 count，不宣稳定率；未标段不当正常负例 |
| 错误 NORMAL | 已标异常事件区间内 `NORMAL_CONSISTENT` 的块数/时长 | 按 scope 分列；无标签不填 0 |
| UNKNOWN | 全部块中 UNKNOWN 的数量、总时长、最长连续区间、原因分布 | 主分母；不因 UNKNOWN 删除前先报 |
| 分类覆盖 | 非 UNKNOWN 的块数/占比，按状态与 scope | 与风险同报，不用覆盖率代替风险 |
| 缺项 | `NO_TRACE_ROW`、`NO_AVAILABILITY_ROW`、通道 missing/carried、`has_out=false` | 单列；不补零 |

- `NOT_EVALUABLE`：任何需要标签的指标在缺少独立标签/onset/曝光不足时标此值，并写明缺哪一项。
- 不把相关点/块当独立样本；事件级计数与块级计数分开报。
- 生效量/趋势：块级与事件级都报；人口小时不足时只给 count/exposure，不声称稳定率。

## 5. 停止/阻塞条件（不降阈值强凑）

出现以下任一，T2 该部分 `STOP/BLOCKED`，不换参数、不扫 `.95/.80/0.5/20`：

0. trace 不是 detection on，或 availability 的 status 全为 DISABLED / support 为空；
1. trace 缺声明（state order / rotation param / perturbation / frame / extrinsic / bias 来源），
   或声明互相矛盾；
2. `pose_pre`/`pose_post` 不是同一实际区间/同一基，或 `has_out=false` 被当作更新后状态；
3. `P⁻/P⁺` 不是 6×6 位姿块，或把 `S`/`H_T_H` 当 6D 协方差；或协方差声明不是
   `pre_body` + `right`（与 `e_I` 不同切空间且未声明转换）；
4. trace 与 availability 的 run id/build/输入 sha256 不一致，或 join 键不能精确对应
   （含 `last_lio_update_time` 缺失、偏移非常数且未声明映射）；
5. 正常前缀不可得/非独立确认，导致校准 `INCOMPLETE`：可继续报资格/UNKNOWN，但
   **NORMAL/SUSPECT 与错误率 `NOT_EVALUABLE`**，不把全 UNKNOWN 当零风险；
6. 需要新数据/安装/换宿主/改科学门才能继续；或超出既有预算；
7. 只有伪 I（零 bias、默认速度、另一 run 内部状态、carried NIS）可用。

协方差不可用**不**停止：只走单位权 `e_I` + `NOT_AVAILABLE`，不宣称卡方概率。

## 6. 首版冻结配置与“不扫参数”

| 量 | 冻结值 |
|---|---|
| 时间块 | 0.5 s 传感器时间 |
| alarm | `u ≥ 0.95`，两个相邻有证据块 |
| normal-compatible | `u ≤ 0.80`，两个相邻有证据块 |
| 灰区 | `0.80 < u < 0.95` |
| 每条件最少块 | 20 |
| 上下文键 | `(channel ∈ {M,T,I}, map_support ∈ {EMPTY,LOW,SUPPORTED})` |
| 混合上下文 | `MIXED → OUT_OF_SUPPORT` |
| 正常参照 | 独立确认的正常前缀；不在线更新 |
| I 协方差 | P⁻/P⁺ 6×6；缺则单位权、无卡方 |

**不扫参数**：同一条 trace 只报告这一版；不因结果改 `.95/.80/0.5/20`、不缩正常段、不改
`1 m/60%` 或 sigma/κ/floor。若本版效果差，保留负结果并交下一步科学选择，不重跑追好成绩。

## 7. 交付格式（T2/T3）

每项 `PASS / FAIL / BLOCKED / NOT_APPLICABLE` + 实际命令/输出或原件 + 受影响结果 + 下一动作；
未实现/未执行写 `NOT_IMPLEMENTED` / `NOT_EXECUTED`。
最小表：全 paired 与未配对的旧 UNAVAILABLE 三类分布（数量/时间/scope/通道资格）、漏检/延迟、
正常段误报与曝光、错误 NORMAL、UNKNOWN 数量/总时长/最长区间/原因、成本（耗时/峰值内存/输出量）。
