# T2 输入契约：新 trace 到达后先核什么（S3，2026-11-12）

状态：**WAITING**。S2 的导出尚未执行（`fl_native_20261112T101116Z_329791` 因
`image_transport` 插件缺失在宿主启动时 terminate，`pose_messages: 0`、`paired: 0`）。
本文件只固定接收口径；没有新 trace 前不跑 T2/T3，不把旧 402/544 行与新 trace 拼接。

## 1. 必须来自同一次新运行

| 项 | 要求 |
|---|---|
| run 身份 | **新的 run id**，不能复用 402/544；off/on 两次为**同一 build**、同一输入/config/library |
| 检测 | 必须是 `--detection on`（旧 402/544 也是 on；off 只有 `DISABLED`，没有 support 可对照） |
| availability | 同 run 产出；`status` **不再全是 DISABLED**，`support` / `support_pass` **非空** |
| 输入 | bag/scan/imu 的 sha256；host library/executable sha256；config sha256 |
| 时间/身份 | 绝对原 ns；`grp_idx` 为身份，`abs_ns` 为时间；join 用 `scan_first_ns ≤ S ≤ scan_last_ns` 的**跨度包含**（`scan_first=-1` 时有效跨度为 `(prev last, last]`），多对一必须显式写映射；不用精确相等/±1 ms/nearest |
| 帧配对 | 每个 LiDAR 更新一行；`has_out` 标明该行是否有更新后状态 |
| 行为对照 | trace off/on 两次运行，旧检测决定/manager/native 命令逐条相同（最小不变性） |

## 2. 允许的导出量（S2 已确认）

每个 LiDAR 更新：

**trace 按列名读取，不按位置**。已知列序（仅供核对，不用于解析）：

`idx(0) rel_s(1) abs_ns(2) grp_idx(3) scan_first_ns(4) scan_last_ns(5) has_out(6)
phase(7) eff(8) r_mean(9) r_med(10) r_abs_mean(11) r_chi2(12) r_chi2w(13)
vec6(14..19) Ppre6x6(20..55) Ppost6x6(56..91)`

| 字段 | 形状/含义 | 用途 |
|---|---|---|
| `idx` / `rel_s` | 行号 / 相对秒 | 追溯，不作时间真值 |
| `abs_ns` | 绝对传感器时刻（原 ns） | 时间对应的一端 |
| `grp_idx` | native 合并组身份；322 个值各出现两次、两次 `abs_ns` 相同 | **物理扫描身份**（join 必需） |
| `scan_first_ns` / `scan_last_ns` | 该合并组的 header 戳跨度（原 ns） | 时间对应/跨度核对 |
| `has_out` | 该行是否有更新后状态 | 只用于 `has_out=1` 的行 |
| `phase` | native 阶段；`phase=1` 为 replay 窗口（已知第 489–810 行） | live/replay 分段，不跨段分块 |
| `eff` | 有效特征数 | 资格/可观测性上下文，不作概率 |
| `vec6` | 6，状态修正/扰动 | 与 `Ppre/Ppost` 同一状态顺序/参数化才可组合 |
| `Ppre` / `Ppost` | 6×6，更新前/后位姿块 | 仅当声明为 **pre_body 的 right perturbation** 时才是 `e_I` 协方差 |
| `r_*` | 更新残差及其统计（mean/median/abs/chi2） | 仅作上下文，不另造新 confidence |
| `mat_pre.txt` / `mat_out.txt` | 更新前 IMU 传播位姿 / 更新后 LiDAR 位姿，SE(3) | `e_I` 的两端；与 trace 同键（`grp_idx`/`abs_ns`） |

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
6. `Ppre/Ppost` 是否可直接作 6D 协方差；若可用，必须声明 `covariance.frame = pre_body`
   且 `covariance.perturbation = right`（`e_I` 的切空间）；left 或其它 frame 不转换，直接
   `INCOMPLETE`；不可用则写 `NOT_AVAILABLE`。

缺声明时：不猜、不转置、不混合左右扰动；该帧记 `INCOMPLETE` 并列出缺项。

## 4. 残差与分数（沿 ALI-H §3）

\[
e_I = \mathrm{Log}\left(\Delta T_{\text{IMU,preupdate}}^{-1}\,\Delta T_{\text{host,observed}}\right)
\]

SE(3) Log 的平移是 `rho = V(w)^-1 * t`（`V` 为左 Jacobian），**不是直接取 `t`**；
`s_i` 只能使用与 `e_I` 同一切空间（pre_body、right）的 6×6 协方差。
本 trace 的 `vec6 = (state_propagat - state_)[0..5]`（`has_out=1` 时在 StateEstimation 之后）。
按 host `StatesGroup::operator-`，`vec6 = [Log(R_post^T R_pre), pos_pre − pos_post]`；精确
`e_I = [-vec6_rot, −R_pre^T vec6_pos]`，其中 `R_pre = R_post·Exp(vec6_rot)`。
`R_post` 必须来自同帧的 post 位姿（`M2DGR_room_02.txt` 或可配对的 `mat_out`），不能只用 `−vec6`
（仅小角近似；本数据平移方向最大差 2.64 m）。`Ppre` 为预测协方差；`s_i`/`|e_I|` 对符号不变，
但平移方向与各向异性 `s_i` 需要精确值。

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

1. 校验 run 身份、detection=on、availability 非全 DISABLED 且 support 非空、输入/库/config sha256、off/on 同 build；
2. 校验 §3 的六项声明与 §1 的按列名导出（`grp_idx`/`abs_ns`/`phase`/`scan_first_ns`/`scan_last_ns`/`Ppre`/`Ppost`/`vec6`/`mat_pre`/`mat_out`），缺项 → `INCOMPLETE`（列出）；
3. 抽 1–2 帧做 `e_I` 手算复核对（同区间、同基、同外参）；
4. 在全部新 trace 上跑 ALI-H shadow 与旧方法同人口对照；
5. 若 trace 仍不可得至 2026-11-13 08:53（UTC+8），按 15 小时任务提交
   `docs/ali_h_v1_research/重大阻塞记录.md`（中文、含选项 A/B），不静默停止。

## 7. 阻塞记录模板字段（预置，不提前提交）

`阻塞ID / 首次时间 / 最新时间 / 状态 / 负责人与 branch/HEAD/run/input/library/config /
具体失败或缺项（文件、函数、命令、输出原件）/ 影响 / 已尝试的最小措施与负结果 /
最低解除 / 需要用户确认的问题 / 选项A/B（改变什么、代价、风险、授权边界、推荐理由）/
等待期间继续做什么 / 用户确认原文/来源 / 恢复动作与后继结果`。
