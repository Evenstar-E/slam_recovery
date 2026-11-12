# MM-LINS / SC-PGO：一次真实双事件运行（campus_12_fl）

## 1. 运行

| 项 | 值 |
|---|---|
| 命令 | `~/run_mmlins.sh /home/R26534/datasets/mmlins/campus_12_fl.bag /home/R26534/mmlins_ws/output/result_campus12_twosleep_20261112` |
| 输入 | `campus_12_fl.bag`，sha `a924b5f9…`，469.4 s，首个 IMU 戳 `1711547883362267771` |
| 方式 | 整段回放到 bag 尾（rate 1.0，`--clock`），PGO 15 s 收尾，postprocess 生成 light/mid |
| 退出 | 正常退出（`[run_mmlins] done`），无 BLOCKED |
| 状态 | **PASS**（宿主原生双事件与尾段）；**slam_recovery 层：NOT_IMPLEMENTED** |

身份：

| 物件 | 值 |
|---|---|
| 前端二进制 | `mmlins_ws/devel/lib/fast_lio/fastlio_mapping`，sha `59674a8f…`，mtime 2026-10-30 20:52 |
| 后端二进制 | `mmlins_ws/devel/lib/aloam_velodyne/alaserPGO`，sha `ec2c5e06…`，mtime 2026-11-05 11:48 |
| runner | `~/run_mmlins.sh`，sha `82ba3679…`（副本 `run_mmlins.sh`） |
| 前端配置 | `FAST-LIO/config/velodyne_m2dgr.yaml`，sha `13086d7d…` |
| 前端 launch | `FAST-LIO/launch/mapping_velodyne_m2dgr.launch`，sha `23a91256…` |
| 后端 launch | `SC-PGO/launch/fastlio_ouster64.launch`，sha `3c4258f6…` |
| 源码树 | `/home/R26534/MM-LINS`，**运行时刻 HEAD `2ef0169`**（11:31:21 提交；该共享 checkout 在 11:51 被另一会话推进到 `129dae2`，在我的 run 之后）。`FAST-LIO/`、`SC-PGO/` 无源码改动 |

**构建溯源的缺口（如实写）**：两个二进制的 mtime 都早于上述 HEAD（10-30 / 11-05），本机没有可复核的构建命令记录把它们绑到 `2ef0169`。这里能保证的是**跑的是这两个 sha 的二进制**，源码 HEAD 只作语境。

## 2. 事件声明

两个 E 都是**声明观察点**，不是注入：MM-LINS 没有触发器接口。

- 来源：`slam_recovery/experiments/manifests/e2_real_world_mmlins_campus_r1_r2_r3_benchmark.json` 的
  `campus_12` 段，`sleep_trigger_sec` = 115.99 / 230.09。
- 换算：绝对戳 = 首个 IMU 戳 + offset →
  **E1 = `1711547999352267771`**，**E2 = `1711548113452267771`**。
- 独立佐证：`/imu_raw` 的 1 s 分箱（陀螺模长 std < 0.002 rad/s 且加速度模长 std < 0.03 m/s²，
  连续 ≥3 s）给出两段低运动窗 **109–143 s** 与 **224–261 s**，两个声明戳都落在窗内。
- 标注：`DECLARED_OBSERVATION (natural hibernation, not injected)`。

## 3. 宿主自身表现（原生层）

### 3.1 事件 1

- `/Odometry`（FAST-LIO 前端）在 **E1+0.32 s** 停止发布，间隔 **23.7 s**；恢复后的第一帧位置是
  **≈原点 `[0.00, 0.00, -0.01]`**，而停止前是 `[34.14, -50.00, 1.26]`（跨间隔位移 60.56 m）。
  这不是位移，是**局部地图重建**：源码在过度退化时发布 `Issleeping` 并 `re_slam()`，恢复时打印
  `construct a new map` 并重新初始化 IMU（`FAST-LIO/src/laserMapping.cpp:915-942`）。
- 宿主自己发布了 `Issleeping=true`（两次，见 3.3）。
- `/aft_pgo_odom`（SC-PGO）在 E1 附近有 **38.5 s** 的发布间隔（E1−9.4 s → E1+29.1 s），
  跨间隔位移 **0.75 m**；PGO 的全局图没有重建，继续在旧地图里。

### 3.2 事件 2

- 前端在 **E2+0.12 s** 停止，间隔 **26.8 s**；恢复后第一帧 **`[0.02, 0.00, 0.10]`**，
  停止前 `[67.03, -23.49, 3.80]`（跨间隔位移 71.11 m，同样是重建到原点）。
- PGO 间隔 **41.4 s**（E2−7.9 s → E2+33.4 s），跨间隔位移 **0.48 m**，全局图保持连续。
- 第二次重建说明：**同一实例用同一原生机制处理了第二个事件**，没有额外的恢复/事务层。

### 3.3 睡眠标志

`Issleeping` 共 **2 条**，均为 `true`；`std_msgs/Bool` 无 header，记录的是录制到达墙钟：
`1794454707308222703`、`1794454821207879049`。两条间隔 **113.90 s**，与声明的 E2−E1
（**114.10 s**）相差 0.20 s——宿主自己标记了两次睡眠，间隔与声明一致。

### 3.4 尾段与两次事件之间的连续输入

| 量 | 值 |
|---|---|
| E1 → E2 之间（bag 时间） | 114.10 s；E1 后前端重建一次、PGO 保持 |
| E2 之后前端仍发布 | **239.0 s**、1051 条 |
| E2 之后 PGO 仍发布 | **227.0 s**、967 条 |
| 两次事件之间的 PGO 位移 | **71.40 m**（E1 前最后一条 → E2 前最后一条，同一全局图） |
| PGO 全程路径长 | **348.35 m** |
| PGO 最大 1 s 内步长 | **2.56 m** @ `1711548321470030069`（E2 之后约 208 s；loop closure 附近，未用 GT 判性质） |

`/path` 话题不能用：282 条消息的 header stamp 全相同（墙钟 `1794454580.778`），不是 bag 时间；
本报告不使用它。

## 4. 输出原件

| 物件 | 路径 | 大小 / sha |
|---|---|---|
| 全量录制 | `/home/R26534/mmlins_ws/output/result_campus12_twosleep_20261112.bag` | 29 GB |
| light（轨迹+回环，分析用） | `..._light.bag` | 76 MB，sha `236d8c17…` |
| mid（稀疏点云） | `..._mid.bag` | 1.5 GB |

大 bag 不入库；路径与 sha（light）在 `analysis.json` 同目录可复核。`run.log` 是 runner 的完整输出。

## 5. 这一项能/不能声称

- 能声称：MM-LINS 在**同一实例、同一输入时间线**上经历了两个声明事件；两次都由宿主自己的
  过度退化/休眠路径处理（前端重建局部地图、PGO 保持全局图），并继续到 bag 尾。
- 能声称：事件时刻与宿主自己的 `Issleeping` 间隔一致，且落在 IMU 静止窗内。
- 不能声称：这是"恢复"或"修复"；没有 slam_recovery 事务接线，**NOT_IMPLEMENTED**。
- 不能声称：PGO 在这些事件上没有漂移——没有 GT，不给质量数字；E1/E2 处的位姿只是记录值。
