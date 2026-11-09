# FAST-LIVO2 的非确定性来源与最小可控清单（源码阅读，未重编译/未重跑）

目的：把 room_02 上"同一 bag 一次收敛、一次发散"的方差先压住，再谈因子对比。
以下全部来自 `~/fast_livo2_ws/src/FAST-LIVO2`（revision `0d2c0346`）与随包 config 的实读，
每条都给文件:行，便于核对与打补丁。

## 1. 找到的来源（按可疑度排序）

**S1 — OpenMP 归约的顺序不确定（最可疑）**
`src/vio.cpp:1554`：`#pragma omp parallel for reduction(+:error, n_meas)`（在 `#ifdef MP_EN` 内）。
浮点求和顺序随线程调度变化，即使线程数固定。EKF 每帧的误差/测量数因此逐次差在最后几位，
在退化窗口里会被放大。这是唯一一处"同一输入、同一线程数、结果仍可能不同"的确定性缺口。

**S2 — 并行是编译期写死的，环境变量无效**
`CMakeLists.txt:46-58` 自动在核数 >1 时 `add_definitions(-DMP_EN -DMP_PROC_NUM=4)`；
两处并行循环前都调用 `omp_set_num_threads(MP_PROC_NUM)`（`src/vio.cpp:1553`、`src/voxel_map.cpp`）。
所以 **`OMP_NUM_THREADS=1` 不会生效**，必须改编译选项或改这几行代码。

**S3 — 主循环是墙钟轮询，帧的分组取决于到达时机**
`src/LIVMapper.cpp:537` `ros::Rate rate(5000);`，循环里 `if (!sync_packages(...)) { rate.sleep(); continue; }`
（`:541-545`）。哪几帧被一起处理、第一帧何时进入处理，取决于回调与 5 kHz 轮询的相位差——
这会直接改变 `sync_packages` 的分组，也解释了我们测到的 66.7 ms / 133 ms 发布节奏变化。

**S4 — IMU 初始化窗口由 S3 决定**
`config/m2dgr.yaml:46` `imu_int_frame: 30` → `Max_INI_COUNT=30`（`include/IMU_Processing.h:82`），
初始化取第一组 `meas.imu.front()` 起若干个 IMU 样本求平均（`src/IMU_Processing.cpp:104-120`）。
分组随 S3 变，**初始重力/零偏就逐次不同**——与"首条输出位姿已差 0.16–1.6 m、且早于 onset"完全吻合。

**S5 — 墙钟定时器**
`src/LIVMapper.cpp:216` `createTimer(ros::Duration(0.004), imu_prop_callback)`：250 Hz 的 IMU 传播
（发布 `/LIVO2/imu_propagate`，不是我们记录的 `/aft_mapped_to_init`），但它驱动视觉侧状态，
在高负载下会改变每帧进入 EKF 时的状态。

**S6 — 已排除的**
- 没有随机数：`rand/random_device/mt19937/shuffle` 在 `src/`、`include/` 里均无命中；
- 订阅队列 `200000`（`src/LIVMapper.cpp:196-199`），不会丢消息；
- `/aft_mapped_to_init` 的时间戳取 `last_lio_update_time`（`:1341`），不是墙钟，所以记录的位姿时间不受 S5 影响。

## 2. 最小可控清单（按代价从低到高）

**T1（编译，一次）——去掉 S1/S2**
以 `-DMP_EN` 关闭的方式重编译：最省事的是把 `CMakeLists.txt:46-58` 加一个 `option(NO_MP)`，
或把两处 `#pragma omp parallel for` 用 `#ifdef` 关掉。重编译后二进制 sha 会变，
**run receipt 必须记录新 binary sha**；同时确认 `omp_get_max_threads()==1` 或该循环串行。
> 这是唯一能消除"同输入同配置仍不同结果"的改动。

**T2（运行，每次）——压住 S3/S5 的相位噪声**
- `taskset -c <固定 8 核>` + 同一 `nice`，并且**机器空闲时跑**（上次 128 核上 load≈250，任何相位分析都被污染）；
- 每次运行独立 `ROS_HOME`（runner 已做）；
- `rosbag play` 固定 `-r 1.0`，不加 `--clock` 之外的额外参数；
- 记录 load、`procs_running`、节点 `/proc/<pid>/schedstat`（runner 已在 rate 诊断里做过，可复用）。

**T3（改代码，仅在 T1+T2 后仍分叉时）——消除 S3/S4**
- 把 5 kHz 轮询改成"每帧到达即按序处理"（去掉 `rate.sleep()` 的空转），或至少在 `sync_packages` 里
  记录每帧的分组大小；
- 或固定 IMU 初始化窗口为**绝对时间戳区间**而不是"前 30 个分组"。

## 3. 每次运行应当记录的新增字段（receipt）

| 字段 | 为什么 |
|---|---|
| 首条 `/aft_mapped_to_init` 的 stamp + 位置/姿态 | 分歧的最早可观测点（对方已用 1 cm / 1e-3 rad 规则标为 POST_HOC） |
| 前 5 条位姿 | 看初始化阶段是否已经开始分叉 |
| IMU 初始化结束时刻、用到的 IMU 样本数 | 直接对应 S4 |
| `sync_packages` 每组帧数（若改为记录） | 直接对应 S3 |
| binary sha、`omp_get_max_threads()`、编译宏 `MP_EN/MP_PROC_NUM` | 证明 T1 是否真的生效 |

## 4. 建议顺序

1. 只做 T1 重编译，**其余不变**，用同一格（O）跑 2 次，看是否仍跨模式；
2. 若仍跨模式，再做 T2（固定核、空闲时段）跑 2 次；
3. 若仍跨模式，问题就在 S3/S4，需要 T3 的代码改动——此时应停止因子对比，先修时钟/分组的确定性。

在 T1 完成前，任何单次因子对比都不可信（这也解释了为什么 2×2 与 8 次重复都被方差吞掉）。
