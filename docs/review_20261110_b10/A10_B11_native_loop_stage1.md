# A10/B11 阶段一：原生同进程闭环的接线验证（2026-11-10）

本文件只记录**接线五项**和它们暴露出来的问题。它不是阶段一的候选流结果：跑到的那个候选
不是注入窗口的候选，原因见 §4。

## 0. 交付物

| 文件 | 作用 |
|---|---|
| `slam_recovery/ros/recovery_node.py` | `rospy` 入口，包 `OnlineRecoveryTransactionNode` |
| `slam_recovery/ros/run_native_loop.sh` | 宿主 + 恢复节点同组启动、receipt、接线自检 |
| `slam_recovery/tests/test_recovery_node.py` | 27 个用例，不需要 ROS master |

`step_frame` / `core.py` / `quarantine/manager.py` / `fim_and_holdout.py` **均未改动**。

运行：

```
bash slam_recovery/ros/run_native_loop.sh /tmp/fastlivo/room02_2x2_O.bag --rate 1.0 --drain 3
```

## 1. 与计划的偏离（两处，都在跑之前不知道，跑出来才看见）

### 1.1 配对窗口 20 ms → 40 ms

实测（`run_summary.json:pairing_diagnosis`，同一趟的 672 个位姿戳 / 599 个扫描戳）：
扫描到最近位姿的偏移是 **p10 −27.1 ms / 中位 +1.5 ms / p90 +29.5 ms**，
而位姿间隔只有 **66.6 ms**。原因不是抖动而是定义：`/aft_mapped_to_init` 的戳是
`last_lio_update_time`（组内最后一个 IMU 时刻），不是雷达 header 戳。

20 ms 窗口实测配对 **55.6%** 的扫描，40 ms（半个位姿周期）配对 **83.3%**。
40 ms 仍会配对到"同一个处理帧"的位姿，不会跨帧，所以这不是放宽判据。

### 1.2 门控前加了一段 warm-up（18 帧）

`step_frame` 的检测器要一个 NIS，而 NIS 要一个参考。节点的可信图**是被 step_frame 自己喂大的**，
所以第 0 帧没有任何参考，形成一个死循环。第一版实现用"上一帧扫描"当参考，结果
NIS ≈ 2.9，检测器（`nis_q90 = nis×1.35 > 2.8`）**在第 0 帧就 SUSPECT、第 1 帧就 QUARANTINED**——
那是参考选错造成的必然触发，不是场景退化。

现在的做法：参考不可用期间，帧只经 `tx_mgr.step_healthy` 进入可信图，**不让检测器判定**
（`_warmup_step`，逐行镜像 `step_frame` 的 HEALTHY 分支，唯一差别是不调 `detector.step`）。
一旦节点自己的图能提供参考（≥30 点在 3 m 内），立刻交还给 `step_frame`。

代价明确写在 `run_summary.json:warmup.assumption`：**这 18 帧被假定为健康，本趟没有证据。**

## 2. 接线五项（PASS/FAIL）

| # | 项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 两个话题都在收 | **PASS** | `/aft_mapped_to_init` 672 条、`/velodyne_points` 599 条 |
| 2 | 配对成功率 | **PASS**（83.3%） | `pairing.paired_fraction_of_scans = 0.833`，`max_abs_dt = 39.8 ms` |
| 3 | gate 有输出且四参取齐 | **PASS** | 1 次决策，`incumbent_basis=ZERO_VELOCITY_SINGLE_KEYFRAME`、`paired_evidence.wilson_lower_bound=0.121` 均非空 |
| 4 | pid 与宿主同组 | **PASS** | 恢复节点 pgid 2942557 = 宿主 pgid 2942557 |
| 5 | NIS 有来源、不伪造 | **PASS** | computed 498（node_map 363 / prev_scan 135）、carried_forward 0、unavailable 1 且该帧未送入 gate |

候选记录 18 个键**零 null**（`null_field_counts` 全 0，`holdout_nis_nonfinite` 0）。

receipt：`/tmp/fl_native_20261110T030931Z_2941380/receipt.json`
（bag sha `f8b26ddf…`、宿主 binary sha `6e0a3e57…`、运行时 `liblaser_mapping.so` sha `6aeef032…`、
config sha、恢复节点源码 sha `c0490471…`）。

## 3. 跑到的那次决策（不是注入窗口的决策）

```
t_trigger_ns  = 1627643742844584942   （首帧 + 2.27 s）
t_decision_ns = 1627643744910121918
mode          = MODE3_SOFT_BRIDGE_WAIT
accepted      = false
refusal_reason= 段边界跳变超限（reentry_pos_jump_m = 0.666 m > 0.5 m）
wilson_lb     = 0.121 < 0.55
holdout_nis   = 29.72
```

**注入窗口从 1627643759554082870 开始，比这次触发晚 16.7 s。**
所以这个候选来自一次启动时的误触发，与注入无关。

## 4. 为什么在启动时就触发：一个真问题

`node_map` 参考下的 NIS 分布（363 帧）：

```
min 1.73   p10 5.11   median 21.57   p90 857   max 2658
```

检测器的判据是 `nis×1.35 > 2.8`，即 **NIS > 2.07 就报警**。中位数 21.57 是阈值的 10 倍。
这不是注入造成的（注入还没开始），是**参考太年轻、太稀**：

- 决策时可信图只有 **1 个关键帧**（`trusted_keyframes_at_exit = 1`），因为
  `confirmation_margin = 2 s` 期间只有最早那一帧越过了 2 s 边距；
- `get_trusted_map_points(max_pts=2000)` 把一个 1500 点/帧的地图**按点数上限抽样**到 2000 点——
  节点自己在 `support_reference()` 里已经指出"点数上限会把点间距变成地图大小的函数"，
  但那个修正只用在覆盖判据上，**NIS 参考仍在用带 cap 的版本**。

于是单帧视角的点云当参考，另一视角的扫描有几成点找不到近邻平面，点到面残差被放大到
σ=0.12 下的 NIS ≈ 21。节点自己的 `_measure_paired_evidence` 也得到同一量级
（`incumbent_mean_residual = 25.6`），说明这是**估计器口径问题，不是我这一层的接线问题**。

这条与"gate NIS 265.81 不可复现"是同一根线。**我没有改 σ、没有改 cap、没有改阈值**——
按规则这属于 r26534-58 手上的 NIS 标定线，我只负责把现象记录成可复现的数字。

## 5. 位姿约定的一次性自检

`run_summary.json:pose_convention.one_frame_check`：

```
nis_forward_T_wb = 49.73      nis_reversed_T_bw = 54.97      -> FORWARD_SELECTED
```

**这个自检只有方向意义，不构成证明**：两个数都很大（同一帧、同一参考），差距只有 10%；
只有等 §4 的参考稀问题修好、NIS 回到 O(1)，这个对比才有判别力。

## 6. 状态与边界

- `gate_decision_validity = GAUGE_DEPENDENT_UNTIL_A7_FIX`：A7 未验收，同场景换世界原点会换 Mode，
  这条流的 accept/refuse **不得**进 B10 四策略表，也不得与离线 A3 臂比较"谁能过门"；
- 闭环**会跑**：检测 → 隔离 → 候选 → 门 → 拒绝 → 继续收帧，全程无异常、无 callback 错误；
- 但因为 §4，它**还没有在注入窗口上产生过候选**。阶段一要产出与 onset 相关的候选流，
  必须先解决 NIS 参考口径（cap / 地图年龄），否则每一趟都会在 warm-up 结束后 0.3 s 内误触发；
- 只跑了一次决策：`step_frame` 在隔离期内不会二次触发（`state != HEALTHY`），
  第一次决策若是 Mode 3 则 `active_quarantine` 保留、状态停在 `WAITING_FOR_EVIDENCE`，
  后续 458 帧只登记不判定。这一点按裁决没有做自动重试。
