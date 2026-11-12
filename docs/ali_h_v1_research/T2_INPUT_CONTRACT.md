# T2 输入契约：新 trace 到达后先核什么（S3，2026-11-12）

状态：**WAITING**。S2 的导出尚未执行（`fl_native_20261112T101116Z_329791` 因
`image_transport` 插件缺失在宿主启动时 terminate，`pose_messages: 0`、`paired: 0`）。
本文件只固定接收口径；没有新 trace 前不跑 T2/T3，不把旧 402/544 行与新 trace 拼接。

## 1. 必须来自同一次新运行

| 项 | 要求 |
|---|---|
| run 身份 | **新的 run id**，不能复用 402/544；off/on 两次为**同一 build**、同一输入/config/library |
| 输入 | bag/scan/imu 的 sha256；host library/executable sha256；config sha256 |
| 时间 | **绝对传感器戳**（IMU 与 LiDAR 各自）**且同时给 `scan_header_stamp` 与 `last_lio_update_time`**；不用 wall time 代替；offset 非常数或只有 header 戳 → `INCOMPLETE:join_key_unresolved` |
| 帧配对 | 每个 LiDAR 更新一行；`has_out` 标明该行是否有更新后状态 |
| 行为对照 | trace off/on 两次运行，旧检测决定/manager/native 命令逐条相同（最小不变性） |

## 2. 允许的导出量（S2 已确认）

每个 LiDAR 更新：

| 字段 | 形状/含义 | 用途 |
|---|---|---|
| `P_minus` | 6×6，**更新前**位姿块 | 仅当声明为 **pre_body 的 right perturbation** 时才是 `e_I` 的协方差 |
| `P_plus` | 6×6，**更新后**位姿块 | 同上 |
| `vec` | 6，状态修正/扰动向量 | 与 `P` 同一状态顺序/参数化才可组合 |
| `effct_feat_num` | 有效特征数 | 资格/可观测性上下文，不作概率 |
| `pose_pre` | 更新前 IMU 传播位姿（SE(3)） | `e_I` 的一端 |
| `pose_post` | 更新后 LiDAR 位姿（SE(3)） | `e_I` 的另一端 |
| `stamp_pre` / `stamp_post` | 对应实际传感器时刻（ns） | 同一区间/同基检查 |
| `scan_header_stamp` | LiDAR 消息 header 戳（ns） | 与 availability 的 `scan_stamp_ns` 对照 |
| `last_lio_update_time` | LiDAR 帧**末时刻**（宿主首列，ns） | **精确 join** availability 的 `scan_stamp_ns` |

**明确不接收**：
- `S`（m×m 测量空间量，`S = H P⁻ Hᵀ + R`）——不是 6 维切空间协方差；
- `H_T_H`（信息阵）——不能当 `e_I` 的协方差；
- 零 bias、默认速度、占位创新、carried NIS、另一 run 的内部状态。

## 3. 必须随数据声明的元信息（缺一项即 `INCOMPLETE`）

1. 状态顺序：`rot_trans` 或 `trans_rot`；
2. 旋转参数化：quaternion / rotvec / 其它（写清）；
3. 扰动方向：left 或 right（`T ⊞ δ` 的定义）；
4. `P`、`vec`、位姿各自的 frame：body 或 world，及外参；
5. bias 来源（真实估计值/常量及来源），不得用零 bias 假冒；
6. `P_minus/P_plus` 是否可直接作 6D 协方差；若可用，必须声明 `covariance.frame = pre_body`
   且 `covariance.perturbation = right`（`e_I` 的切空间）；left 或其它 frame 不转换，直接
   `INCOMPLETE`；不可用则写 `NOT_AVAILABLE`。

缺声明时：不猜、不转置、不混合左右扰动；该帧记 `INCOMPLETE` 并列出缺项。

## 4. 残差与分数（沿 ALI-H §3）

\[
e_I = \mathrm{Log}\left(\Delta T_{\text{IMU,preupdate}}^{-1}\,\Delta T_{\text{host,observed}}\right)
\]

SE(3) Log 的平移是 `rho = V(w)^-1 * t`（`V` 为左 Jacobian），**不是直接取 `t`**；
`s_i` 只能使用与 `e_I` 同一切空间（pre_body、right）的 6×6 协方差。

- 两端必须对应**相同实际起止传感器时刻**、同一基、同一外参；
- 平移与旋转**分开保留**，不把米与弧度无声明相加；
- 有真实协方差时：
  \[
  s_I = e_I^{\top}\,\Sigma_I^{+}\,e_I
  \]
  只在实际可观测子空间计算，记录有效 rank；
- 协方差不可用时：只保留**带单位权**的 `e_I`，标 `NOT_AVAILABLE`，**不补单位阵、不宣称卡方概率**。

`I` 只是跨模态冲突证据，不是独立真值；`I` normal-compatible 也不能单独给出
`NORMAL_CONSISTENT`（仍需 M 或 T 的另一条 normal-compatible，见 §5 判决表）。

## 5. 同人口对照与标签

- T2/T3 只在**新 trace** 上同时计算旧方法与 ALI-H；旧 402/544 的资格结论另列，不拼接。
- 正常参照仍缺：若新 trace 只给 I、不给独立确认的正常前缀，校准照实报 `INCOMPLETE`；
  不用 `HEALTHY`、trusted、无注入或预测支持通过充当正常真值。
- 事件标签只用于离线评价；自注入标签只能评价，不能生成训练/在线分类真值。
- 误报/漏检/延迟/错误 NORMAL/UNKNOWN 区间与曝光一起报；缺标签写 `NOT_EVALUABLE`，不填 0。

## 6. 到达后的最小验收顺序

1. 校验 run 身份、输入/库/config sha256、off/on 同 build；
2. 校验 §3 的六项声明，缺项 → `INCOMPLETE`（列出）；
3. 抽 1–2 帧做 `e_I` 手算复核对（同区间、同基、同外参）；
4. 在全部新 trace 上跑 ALI-H shadow 与旧方法同人口对照；
5. 若 trace 仍不可得至 2026-11-13 08:53（UTC+8），按 15 小时任务提交
   `docs/ali_h_v1_research/重大阻塞记录.md`（中文、含选项 A/B），不静默停止。

## 7. 阻塞记录模板字段（预置，不提前提交）

`阻塞ID / 首次时间 / 最新时间 / 状态 / 负责人与 branch/HEAD/run/input/library/config /
具体失败或缺项（文件、函数、命令、输出原件）/ 影响 / 已尝试的最小措施与负结果 /
最低解除 / 需要用户确认的问题 / 选项A/B（改变什么、代价、风险、授权边界、推荐理由）/
等待期间继续做什么 / 用户确认原文/来源 / 恢复动作与后继结果`。
