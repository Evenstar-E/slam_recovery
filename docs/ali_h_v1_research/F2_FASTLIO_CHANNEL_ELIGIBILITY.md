# F2：FAST-LIO 真实通道与校准资格（2026-11-13，10:00/12:00 节点）

> 任务：`docs/FASTLIO_ALI_AUTODETECTION_E2_TASK_20261113.md` §2 F2（S3）。
> 本文件是 **10:00 校准资格与具体缺项** 与 **12:00 本 host 通道/校准可用性** 的合并交付。
> 只读既有源码/归档；**未跑宿主、未改生产代码、未新开 FAST-LIVO2**。标签/校准不足部分
> 直接记 `BLOCKED` 并给最低获取方式，不反复泛问 A/B/C，不把 HEALTHY/无注入/全 UNKNOWN 当正常。

## 0. 一句话

FAST-LIO 的 **I 可以直接从同一次 update 调用拿到**（`x_propagated` → `x_`），但**当前没有任何
FAST-LIO run 导出过它**；**M** 需要在 `h_share_model`/`update_iterated_dyn_share_modified` 处
导出最终迭代的残差与 S；**T 在 FAST-LIO 结构上不存在**（只有 ikdtree 地图更新，没有 prev-scan
更新），必须声明 `NOT_APPLICABLE`，不得用 M 重命名冒充。现有 FAST-LIO 归档（campus_12 共享版/
独立版）只有 `/Odometry` 与休眠事件，**不能独立确认正常开发前缀，也没有故障事件标签**：校准与
检测指标 `BLOCKED/NOT_EVALUABLE`。可继续的是导出契约、资格分层、时间/身份绑定、UNKNOWN 记账、
单位权 shadow 与同人口观测对比。

## 1. 认领与边界

| 项 | 值 |
|---|---|
| 实际会话 | S3 / `r26534-58` |
| owner | 用户 R26534（本会话不代其授权） |
| branch / HEAD | `exp/ali-h-v1`；本文件提交前 `4796f97` |
| 工作树 | `/tmp/wt-ali`，开工时干净；本线只新增 `docs/ali_h_v1_research/` 文档/分析脚本 |
| 正在改的接口 | **无生产接口**。只定义 FAST-LIO 导出契约与读取/资格分析；不写 S1 的 driver/manager/relay，不写宿主 C++ |
| run/source/config/input | 源码 `/home/R26534/MM-LINS/FAST-LIO`（只读，source_identity `c6d9e326…`）；既有 run 只读（campus_12 共享/独立版）；F1 当日新 run 的导出由 S2 提供 |
| 预定窗口 | 2026-11-13 10:15–17:30（UTC+8）；10:00 节点因分发 10:15 到达，锁资格在 10:30 前回报 |
| 停止预算 | S3 不跑宿主、不构建、不安装、不扫参数、不新开 FAST-LIVO2；遇独立标签缺失即停该类指标，不无限重跑 |
| 复用 | `ali_h_v1.py`（冻结规则）、T2 的 SE(3) Log/`V⁻¹` 与混合约定工具；**不重写 reader/旧数学** |

## 2. 为什么不能贴 FAST-LIVO2 v11 的同行资格

FAST-LIVO2 v11 的 `SAME_UPDATE_PRE_POST=PASS` 来自 `LIVMapper`/`voxel_map` 的 trace 行（同行
`pre_pose7`/`pose7`、`vec6` 在最终 solution 前保存）。FAST-LIO 是 `laserMapping` + IKFoM/ikdtree，
状态、更新入口、协方差基都不同。**v11 的 462 行、18 条 eff=0、join 数值、单位权分位一律不作为
本 host 的证据**；v11 只作数学/来源参考（SE(3) Log、单位权、块规则）。本 host 必须有自己的
run/source/config/input 身份与同 update 绑定。

## 3. 同一次 update 的量在哪里（源码绑定）

FAST-LIO 每个 LiDAR 帧的主循环（`FAST-LIO/src/laserMapping.cpp`）：

| 量 | 源码位置 | 说明 |
|---|---|---|
| IMU 传播后的 **pre** 状态 | `p_imu->Process(...)` 后 `state_point = kf.get_x()`（:803–804） | 扫描时刻的 IMU 先验；即 update 前的先验状态 |
| update 前的 **Ppre** | `P_pre_ = kf.get_P()`（:849） | 23×23；同时 `update_iterated_dyn_share_modified` 入口另有 `P_propagated`（`esekfom.hpp:1621–1622`） |
| LiDAR 更新 | `kf.update_iterated_dyn_share_modified(LASER_POINT_COV, ...)`（:869） | 迭代 ESKF，点面残差；`R = LASER_POINT_COV` |
| **post** 状态 | update 后 `state_point = kf.get_x()`（:872） | 同一调用、同一帧的 LiDAR 后验 |
| **Ppost** | update 后 `P_out_ = kf.get_P()`（:884–885） | 23×23 |
| 扫描身份 | `Measures.lidar_beg_time`（`sync_packages`，:349），`lidar_end_time`（:350） | `lidar_beg_time` 来自 LiDAR header（double 秒）；量化与 v11 的 512 ns 同级，join 需声明保护 |
| **有效约束数 eff** | `effct_feat_num`（:64，:629 清零，:638 递增，:641 取残差均值） | 最终迭代有效点面约束数；`eff=0` 表示无有效约束 |
| **M 的原料** | `dyn_share.h`（残差）、`h_x_`（H）、`P_`、`R`（`esekfom.hpp:1631–1648`） | 最终迭代的 `h` 与 `S = H P Hᵀ + R·I` 可算 NIS；当前**未导出** |
| **support 的原料** | `ikdtree.Nearest_Search`（:601）与 `h_share_model` 的点面对应 | 每点最近邻距离/是否有效；当前**未导出** |
| 状态基/约定 | `use-ikfom.hpp:12–20`；`SOn.hpp:233–236` | 23 DoF：pos(0–2) 世界加性、rot(3–5) **右乘 body** `R←R·Exp(δ)`、extrinsic(6–11)、vel(12–14)、bg(15–17)、ba(18–20)、grav(21–22) |

**关键事实**：`x_propagated` 与最终 `x_` 在**同一个 update 函数调用内**，比 v11 的“同一 trace 行”
更强，可作为 FAST-LIO 自己的 `SAME_UPDATE_CALL_BINDING`；但必须由 F1 导出，不能从 `/Odometry`
或时间近邻反推。

## 4. F1 需要导出的最小字段（契约）

一行 = 一次实际 update（或一次被跳过的 LiDAR 帧，`has_out=0`）。**只导出本 run 实际产生的量，
不补造**：

| 组 | 字段 | 说明 |
|---|---|---|
| 身份 | `run_id`, `update_id`（单调），`grp_idx`（若适用），`abs_ns`/`lidar_beg_ns`/`lidar_end_ns`，`rel_s`，`phase`，`has_out` | `update_id` 必须与 pre/post 同一调用；`has_out=0` 覆盖 `re_slam()`/`continue`/无有效点帧 |
| I | pre `pos7`（x,y,z,qx,qy,qz,qw），post `pos7` | 同一 `update_id`；四元数归一、状态顺序按 §3 |
| 协方差 | `Ppre_6x6`（pos 块 + rot 块）、`Ppost_6x6`；或完整 23×23 + 基声明 | **不得**把 Ppre/Ppost 当 Log 差协方差；只登记，默认 `NOT_AVAILABLE_FOR_E_I` |
| M | `nis`（最终迭代 `hᵀS⁻¹h`）、`dof_M`（=eff）、`R`（LASER_POINT_COV）、可选 `sum_r2` | 导出公式与迭代序号必须写清；无合法 Sigma 时只走已声明单位权 |
| eff/support | `eff`, `feats_down_size`, `feats_in`；200 个确定性样本的最近邻平方距离/有效标志（或每点残差分布） | support 谓词（1 m/60%）只能由这些样本算；未导出则 `support=UNKNOWN`，不是 0 |
| 事件/状态 | `re_slam`/`Issleeping`/`Isbuilding` 触发标志、`isPublish` | 用于解释 `has_out=0` 与事件边界，不作健康真值 |
| 身份 | binary sha、library sha、config sha、bag sha、clock 模式、实际命令 | 与 run 目录 receipt 一致；跨 run/跨 build 不贴接 |

**时间/身份规则**：同 update 用 `update_id` 绑定；不同 update 之间不允许按“最近时间”补 pre/post。
`lidar_beg_time` 是 double 秒，若跨源比较用 ns，必须声明 512 ns 量化保护并保留多对一，不 nearest。

## 5. 资格分层（FAST-LIO 版）

| 层 | 判据 | 当前状态 |
|---|---|---|
| `SAME_UPDATE_CALL_BINDING` | pre/post 来自同一 `update_iterated_dyn_share_modified` 调用（导出 `update_id`） | **待 F1 导出**；未导出前 `NOT_AVAILABLE` |
| `PRE_POST_POSE_IDENTITY` | 状态顺序/四元数/坐标系按 §3；pre≠post 合理 | **待导出** |
| `COMPLETE_POINT_MEMBERSHIP` | 更新实际使用的点/对应列表（`eff` 对应点）可列；仅导出计数则 `ASSERTED_NOT_VERIFIED` | 默认 `ASSERTED_NOT_VERIFIED` |
| `COVARIANCE_6D` | 有明确切空间与 pos/rot 同 frame 的 6D 块；Ppre/Ppost 的混合约定不自动满足 | 默认 `NOT_AVAILABLE_FOR_E_I` |
| `EFF_ZERO` | `eff=0` 行单列、保留分母；零 Log 不证明 IMU/LiDAR 一致 | 待导出 |

`e_I = Log(T_pre⁻¹ T_post)`，按混合约定取 `[rot, V(rot)⁻¹ t_body]`（复用 T2 已验证实现）。
主量为**已声明单位权** `|e_I|²`；无合法 Sigma 不作卡方/健康概率。

## 6. 现有材料能否独立确认正常前缀与事件标签

| 材料 | 有什么 | 能否作本 host 正常前缀/事件标签 |
|---|---|---|
| FAST-LIO2 campus_12 共享版（`59674a8f…`） | `/Odometry` 4186 条、`Issleeping`/`Isbuilding` 各 2 次、E1/E2 声明戳 | **不能**：无估计器内部量（无 pre/post、无 M/T/eff/support）；无 GT；`DECLARED_OBSERVATION` 是历史 manifest 的休眠 onset，不是故障标签 |
| FAST-LIO2 独立版（`4c31fada…`） | 同 bag/同戳，与共享版逐项一致 | 同上；独立构建≠独立真值 |
| `events.json` 静止窗 109–143 / 224–261 s | `/imu_raw` 低运动（gyro/acc 方差）独立佐证 | **只能**佐证“低运动窗”，且两窗正是声明事件窗；**低信息**，不能当 MAP_AND_MOTION 的正常参照 |
| FAST-LIVO2 v7/v8/v11 | 462 行同行 pre/post、M/T/I | **不是本 host**；只作数学/来源参考，禁止贴成 FAST-LIO 证据 |
| FAST-LIO 自注入 run | **不存在**：`injection_repair_20261112` 等是 FAST-LIVO2（hall01、`0d7e23de…`） | 不能给 FAST-LIO 故障类评价 |

**结论**：
- **正常开发前缀：没有独立依据。** “无注入/终态 HEALTHY/低运动窗”都不等于正常；campus_12 的
  事件本身是休眠，不是故障。
- **事件标签：只有 `DECLARED_OBSERVATION` 的休眠 onset，没有本 host 的故障标签。** 可用于
  “声明观察类”边界说明，不能支撑召回/延迟/误报的故障检测主张。
- 因此 `误报/小时、召回、检测延迟 p50/p95、onset 误差、错误 NORMAL` 全部 `NOT_EVALUABLE`；
  **不得填 0**。

## 7. 校准/评价边界（冻结）

沿 `ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md` §4.2 与 `T2_PROTOCOL.md`，**不再改数值**：

- 块：0.5 s 非重叠、传感器时间；每块每通道取 fresh 分数中位数；`carried` 不算 fresh；
  `NO_DATA` 进分母并打断 dwell。
- 经验序：`u=(1+#{b≤s})/(N+1)`；报警 `u≥0.95`、正常兼容 `u≤0.80`，均要求**两个相邻有证据块**。
- 正常参照：按 `(channel, context)`，**≥20 个有效块**，且只来自**校准段**；不足即 `INCOMPLETE`，
  评价段不得回流校准。
- 上下文：`map_support` 由 200 个确定性样本按 1 m/60% 判；混合上下文块记 `OUT_OF_SUPPORT`。
- 状态：`NORMAL_CONSISTENT` 需 `I NORMAL` 且（`M NORMAL` 或 `T NORMAL`）；本 host **T 不存在**，
  所以只有 `I+M` 可达 `NORMAL`（`MAP_AND_MOTION`）；仅 `I NORMAL` 不构成 NORMAL。
- 标签只离线；同 source/config/input 人口对比旧方法与 ALI-H；**不扫参数、不为过门改阈值**。
- 协方差：Ppre/Ppost 不是 Log 差协方差，不能相加、不能换 frame 标签冒 Sigma；无合法 Sigma
  只用单位权，**禁止卡方/健康概率**。

## 8. BLOCKED 项与最低获取方式（具体缺项）

| # | 缺项 | 影响 | 最低获取方式 |
|---|---|---|---|
| B1 | FAST-LIO 同 update 导出缺失（§4 字段） | I/M/support/eff 全 `NOT_AVAILABLE`，只能做契约与合成自检 | F1/S2 在 `laserMapping.cpp:849–874` 与 `esekfom.hpp:1621–1648` 处按 §4 写 trace；一次 run 即可，不需要新算法 |
| B2 | 无独立正常开发前缀 | 校准 `BLOCKED`，三态只能 `UNKNOWN` | 同一输入上覆盖 ≥10 s（20 块）、有运动与几何的**外部参考**（GT/独立轨迹）；或经用户接受的“独立认证正常段”。静止/事件窗不能替代 |
| B3 | 无本 host 故障事件标签 | 召回/延迟/误报 `NOT_EVALUABLE` | 在 FAST-LIO 输入面（relay 级）做**声明式自注入**并保存逐帧 mask（如 FAST-LIVO2 `corrupt_relay` 的做法）；或只评价 `DECLARED_OBSERVATION` 类，不作故障检测主张 |
| B4 | T 通道结构不存在 | `I+T`/`T` 规则不可用 | 声明 `NOT_APPLICABLE`；若确需 scan-to-scan 残差，那是新方法，不是 ALI-H v1，需另立任务，不能在本线补造 |

**最低可解除顺序**：B1（当天可做）→ B2（需外部参考或用户接受）→ B3（需新注入 run，属 F1 预算）。
B2/B3 未解除前，本 host 只能交“资格/UNKNOWN/单位权 shadow”，不能交检测成绩。

## 9. 未阻塞、可继续的工作

1. 本契约与读取器 `f2_fastlio_read.py`（按 §4 读取 JSONL、复用 T2 的 SE(3) Log/`V⁻¹`，
   逐行 `eff=0`/缺 pair/重复 `update_id` 均保留并标注；带合成自检 `python -I f2_fastlio_read.py selftest`，
   7 个用例通过）。
2. 导出到达后：同 update 绑定核对、`eff=0` 单列、support/context、逐帧/块三态与 scope、
   UNKNOWN 区间（数量/总时长/最长区间）。
3. 同人口旧检测 vs ALI-H 的**观测对比**（不是检测率）：M/T/I present、UNKNOWN 占比、单位权分位。
4. 所有结论带 run/source/config/input 身份；跨 run 不贴接。

## 10. 复现与出处

- 源码：`FAST-LIO/src/laserMapping.cpp:349–350,629–647,803–804,849,869–874`；
  `FAST-LIO/include/IKFoM_toolkit/esekfom/esekfom.hpp:1616–1648`；
  `FAST-LIO/include/use-ikfom.hpp:12–20`；`FAST-LIO/include/IKFoM_toolkit/mtk/types/SOn.hpp:233–236`。
- 既有归档：`docs/review_20261112_four_host/fastlio2_shared_campus12_20261112/`、
  `fastlio2_independent_20261113/`（只读）；事件 `events.json`。
- 规则：`docs/ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md` §4.2；`ali_h_v1_research/T2_PROTOCOL.md`；
  `ali_h_v1_research/T2_INPUT_CONTRACT.md`。
- 本文件未跑宿主、未改阈值、未写生产代码。
