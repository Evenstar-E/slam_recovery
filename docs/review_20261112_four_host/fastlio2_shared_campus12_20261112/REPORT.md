# FAST-LIO2 前端：一次真实双事件运行（campus_12_fl，SHARED_EXECUTION）

## 1. 运行

| 项 | 值 |
|---|---|
| 命令 | `bash docs/review_20261112_four_host/run_fastlio2_shared.sh /home/R26534/datasets/mmlins/campus_12_fl.bag /home/R26534/mmlins_ws/output/fastlio2_shared_campus12_20261112` |
| 内部 | `roslaunch fast_lio mapping_velodyne_m2dgr.launch rviz:=false` + `rosbag play --clock`（rate 1.0，整段到 bag 尾），录制 `/Odometry /path /cloud_registered /cloud_registered_body /Issleeping /Isbuilding` |
| 输入 | 同一 `campus_12_fl.bag`，sha `a924b5f9…`，469.4 s |
| 退出 | 正常退出（`recorded …/frontend.bag`），无 BLOCKED |
| 状态 | **PASS**（宿主原生双事件与尾段）；**slam_recovery 层：NOT_IMPLEMENTED**；**SHARED_EXECUTION** |

## 2. SHARED_EXECUTION 与独立构建缺口

- 本机只有一个 `fastlio_mapping`：`/home/R26534/mmlins_ws/devel/lib/fast_lio/fastlio_mapping`，
  sha `59674a8f…`（`find /home/R26534 -maxdepth 6 -name fastlio_mapping -type f` 只返回这一条；
  没有第二个 fast_lio 源码目录）。
- 因此本项跑的**就是 MM-LINS 的前端**：同一 workspace、同一二进制、同一 `velodyne_m2dgr.yaml`、
  同一 launch。**不是独立构建的 FAST-LIO2**，不能算作"独立宿主"的一次独立实现验证。
- 本项没有启动 SC-PGO（后端），所以它是干净的前端单独行为。
- 缺口：要得到独立 FAST-LIO2 结论，需要一份独立构建（独立源码树 + 独立二进制）。本机没有；
  本轮没有新装/新编，按任务要求只记录缺口，不做安装。

身份：

| 物件 | 值 |
|---|---|
| 二进制 | `mmlins_ws/devel/lib/fast_lio/fastlio_mapping`，sha `59674a8f…` |
| 配置 | `MM-LINS/FAST-LIO/config/velodyne_m2dgr.yaml`，sha `13086d7d…` |
| launch | `MM-LINS/FAST-LIO/launch/mapping_velodyne_m2dgr.launch`，sha `23a91256…` |
| 源码树 | `/home/R26534/MM-LINS`，运行时刻 HEAD `129dae2`（前端源码无改动；该 checkout 同时被另一会话使用） |

## 3. 事件声明

与 MM-LINS 完全相同（同一 bag、同一时间线、同一换算）：

- **E1 = `1711547999352267771`**，**E2 = `1711548113452267771`**
  （首个 IMU 戳 + 115.99 / 230.09，来源与 IMU 静止窗佐证见 `events.json` 与 MM-LINS 报告）。
- 标注：`DECLARED_OBSERVATION (natural hibernation, not injected)`。

## 4. 宿主自身表现（原生层）

### 4.1 事件 1

- `/Odometry` 在 **E1+0.22 s** 停止发布，间隔 **23.8 s**；停止前 `[34.15, -50.00, 1.34]`，
  恢复后第一帧 **`[0.00, 0.00, -0.01]`**（跨间隔 60.56 m，是局部地图重建，不是位移）。
- 前端日志：`Over-degeneracy has happened` → 发布 `Issleeping=true` → `re_slam()`
  → 退化消失时 `construct a new map` 并重新初始化 IMU。
- 宿主自己的 `Issleeping` 与 `Isbuilding` 各记录到 2 条 `true`（后者是本项与 MM-LINS 项的差别：
  MM-LINS 的 light bag 没保留 `Isbuilding`，本项的前端 bag 有）。

### 4.2 事件 2

- 前端在 **E2+0.02 s** 停止，间隔 **26.9 s**；停止前 `[67.19, -23.07, 4.02]`，
  恢复后 **`[0.02, 0.00, 0.10]`**（71.13 m，重建到原点）。
- 日志同样两次 `Over-degeneracy has happened`、两次 `construct a new map`（各计数 2）。
- 尾段：E2 之后前端仍发布 **239.3 s**、2126 条。
- `Issleeping` 两条墙钟间隔 **113.90 s**，与声明 E2−E1（114.10 s）相差 0.20 s；
  `Isbuilding` 间隔 116.99 s。

### 4.3 与 MM-LINS 前端的对照

同一二进制、同一输入，E1/E2 处的位姿几乎相同：

| | MM-LINS 前端 | FAST-LIO2 单独前端 |
|---|---|---|
| E1 最近位姿 | `[34.20, -50.08, 1.28]` | `[34.16, -50.08, 1.35]` |
| E2 最近位姿（重建后坐标系） | `[67.03, -23.52, 3.79]` | `[67.19, -23.07, 4.02]` |
| E1 后间隔 / 重建位移 | 23.7 s / 60.56 m | 23.8 s / 60.56 m |
| E2 后间隔 / 重建位移 | 26.8 s / 71.11 m | 26.9 s / 71.13 m |

差异在厘米/亚秒级，是同一前端在两次运行里的重复散布；这也说明 MM-LINS 项里的前端重建不是
SC-PGO 触发的，而是前端自己的过度退化路径。

`/path` 同样不可用于事件对齐：418 条消息的 header stamp 全相同（墙钟），本报告不使用。

## 5. 输出原件

| 物件 | 路径 | 大小 / sha |
|---|---|---|
| 前端录制 bag | `/home/R26534/mmlins_ws/output/fastlio2_shared_campus12_20261112/frontend.bag` | 869 MB，sha `dda2aafe…` |
| 节点日志 | 同目录 `fastlio_node.log`（副本在归档里） | 27 KB |
| 回放日志 | 同目录 `play.log` | 8.6 MB（不入库） |

## 6. 这一项能/不能声称

- 能声称：共享前端在同一实例、同一时间线上经历两个声明事件；两次都由其原生过度退化/休眠路径
  处理（`Issleeping`/`Isbuilding`、局部图重建），并继续到 bag 尾。
- 能声称：单独前端与 MM-LINS 项里的前端行为一致（同二进制、厘米级重复散布）。
- 不能声称：这是独立 FAST-LIO2 实现的验证（SHARED_EXECUTION；本机无独立构建）。
- 不能声称：有恢复/修复；slam_recovery 层 NOT_IMPLEMENTED。
