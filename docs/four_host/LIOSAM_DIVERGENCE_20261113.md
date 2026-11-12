# LIO-SAM 130 s 发散分析（只读）

日期：2026-11-13。范围：只读既有 run 原件（`/tmp/s1_lio_sam_run/r1_20261112T120500Z/`）与
`/home/R26534/LIO-SAM` 源码，不构建、不运行。证据引用 `文件:行` 或原件路径。

## 1. 结论

- **是前端（LIO 扫描-地图匹配）发散，不是回环/图优化把图拉坏。**
- 直接诱因是**输入点云骤降**：bag 相对 120–140 s，`/velodyne_points` 每帧点数中位从约
  **26,000 → 797（120–130 s）→ 203（130–140 s）**，140–150 s 恢复到 26,531。
- 轨迹在 **130.3 s** 出现首个 >1 m 的相邻步长，随后**连续爬升**（1.1→1.6→1.9→2.1 m…），
  不是单次跳变；这正是"约束不足→位姿漂移"的形态，而不是一条错误回环边造成的整体跳转。
- 同期节点日志出现 **110 次** `Large velocity, reset IMU-preintegration!`（bag 时间
  1711547577.8–1711547599.9，约 rel 124–146 s），说明预积分被反复重置——与输入退化窗口吻合。
- 断流（>0.5 s）从 **148.2 s** 开始，比位姿发散晚约 18 s。

## 2. 证据

### 2.1 轨迹（`lio_sam/trajectory.csv`，1120 条 `/lio_sam/mapping/odometry`）

| 窗口 | 最大步长 | >1 m 步数 | >0.5 s 断流 |
|---|---:|---:|---:|
| 0–50 s | 0.30 m | 0 | 0 |
| 50–70 s | 0.57 m | 0 | 0 |
| 70–120 s | 0.50 m | 0 | 0 |
| **120–140 s** | **490 m**（p95 19.0 m） | 起于 **130.3 s** | 0 |
| 140–160 s | 499 m（p95 492 m） | — | 6 |
| 190–210 s | 535 m | — | 9 |
| 210–260 s | 527 m | — | 1 |

首个 >1 m 步长序列：`130.3 s 1.1 m → 130.5 1.6 → 130.7 1.9 → 130.9 2.1 → 131.1 2.0 → …`。

### 2.2 输入点云（`/home/R26534/datasets/mmlins/campus_1(2)-003.bag`，4055 帧）

| 窗口 | 每帧点数中位 | 最小 |
|---|---:|---:|
| 100–110 s | 26,612 | 26,485 |
| **120–130 s** | **797** | 165 |
| **130–140 s** | **203** | 139 |
| 140–150 s | 26,531 | 17,355 |
| 190–200 s | 27,227 | 26,782 |

### 2.3 节点日志（`r1_20261112T120500Z/lio_sam.log`）

- `Large velocity, reset IMU-preintegration!` 共 **110** 条（`:100` 起），bag 时间窗
  1711547577.8–1711547599.9。
- 日志中**没有任何"loop found / 回环约束"输出**（`grep loop` 仅命中参数行 `:263-264`），
  录到的 227 条 `/lio_sam/mapping/loop_closure_constraints` 是 **1 Hz 的搜索标记**（首个在
  rel 30.9 s、此后约每秒一条），不能当作 227 次回环；首个 >1 m 步长之前已有 100 条标记，
  但无实际回环边生效的证据。
- 结论：发散期间没有可归因于回环的图改写下发生。

## 3. 接口与 MM-LINS 的差异（决定它能不能当恢复对象）

| 维度 | LIO-SAM | MM-LINS / SC-PGO |
|---|---|---|
| 进程结构 | **单节点** `lio_sam_imageProjection` 内含 imageProjection / featureExtraction / mapOptimization / imuPreintegration / transformFusion | **4 节点松耦合**（特征、里程计、建图、PGO 各自进程） |
| 状态所有者 | 单一进程：`cloudKeyPoses3D/6D`、`isam`、`laserCloudCornerLastDSArray` 等（`src/mapOptmization.cpp:59,90-92,159-162`） | 分散在 3–4 个进程，无单一所有者 |
| 图优化 | GTSAM iSAM2（单节点内） | GTSAM iSAM2（PGO 进程内，`Mapmanager.ActiveMap`） |
| IMU | 有（`imuPreintegration.cpp`，预积分可被重置） | FAST-LIO 前端有；SC-PGO 的里程计为纯激光 |
| 输入 | `/velodyne_points`、`/imu_raw`（`src/imageProjection.cpp:94-96`） | `/velodyne_points` → 特征 → 里程计 → 建图 → PGO |
| **测量注入点** | **有**：单节点直接消费 `/velodyne_points`，可用与 FAST-LIVO2 相同的 relay 方式替换单帧测量 | **无**：替换测量要重跑 `scanRegistration`/`laserOdometry`，已在前一份接口分析中定为结构性结论 |
| 回滚对象 | `cloudKeyPoses3D/6D` + iSAM2 图（单进程内可快照） | 跨进程；另有 `SleepMapList` 分段地图 |

## 4. 最小接线点（三列）

| 能做什么 | 不能做什么 | 需要宿主改什么 |
|---|---|---|
| 测量级修复**可行**：relay 替换 `/velodyne_points`（与本项目 FAST-LIVO2 的 relay 同构） | 没有 checkpoint/restore 机制；进程退出即丢全部状态 | 命令通道（`cmd`/`ack` 目录轮询，~40 行） |
| 单进程状态可整体快照：`cloudKeyPoses3D/6D`、`isam` 图、当前帧点云与降采样器 | 输入无缓冲，无法"回放已消费的帧" | 状态快照/恢复（关键帧 + 图 + 当前帧，~100 行） |
| 独立准入：`/lio_sam/mapping/odometry` 即最终位姿 | iSAM2 增量状态需重建（GTSAM 可序列化，行为需实测） | 输入缓冲 + `reprocess` 驱动（~60 行 + 内存） |
| 回环/图作为软回滚对象 | 输入退化时的"保护"没有现成钩子（`Large velocity` 只是警告，不是停写） | 退化检测钩子（可复用 `imuPreintegration` 的速度判据） |

## 5. 风险

1. **输入退化是该 bag 的固有现象**（120–140 s 点云从 26k 掉到 200）：任何恢复策略都必须先定义
   "这是输入故障还是算法故障"；把降采样后的帧当正常输入重放会重演发散。
2. **单进程**降低了跨进程原子性风险，但把一切压在同一线程组里，命令处理会与 LIO 竞争 CPU。
3. **回环证据不足**：日志无 `loop found` 输出，若要断言"回环没问题"需要打开 LIO-SAM 的回环日志再跑
   （本次未做，属未确认项）。
4. **IMU 重置**（110 次）意味着恢复后的预积分状态与崩溃前不可比；恢复点必须带上 IMU 初始化条件。

## 6. 未确认项（需构建/运行）

- 打开回环日志后是否出现真实回环边；
- iSAM2 序列化/恢复的实际行为；
- 输入缓冲与重放对 CPU 的影响（单进程内）。

## 7. 文件

`/tmp/s1_lio_sam_run/r1_20261112T120500Z/{lio_sam.log,result.bag,receipt.json}`、
`docs/review_20261112_four_host/lio_sam/{trajectory.csv,windows.py,analysis.json,README.md}`、
`/home/R26534/LIO-SAM/src/{imageProjection,mapOptmization,imuPreintegration,featureExtraction}.cpp`。
