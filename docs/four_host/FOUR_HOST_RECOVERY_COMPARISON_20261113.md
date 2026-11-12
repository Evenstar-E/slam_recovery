# 四宿主恢复层接口对比（A1–A12 接线依据）

日期：2026-11-13。只读结论，基于四份接口/失败分析：
`MMLINS_RECOVERY_INTERFACE_20261113.md`、`LIOSAM_DIVERGENCE_20261113.md`、
`ORBSLAM3_FAILURE_20261113.md`、`fastlio2_independent_20261113/REPORT.md`。
凡标"待测"的项需要构建或运行确认，本次均未做。

## 1. 总表

| 维度 | MM-LINS / SC-PGO | FAST-LIO2 | LIO-SAM | ORB-SLAM3 |
|---|---|---|---|---|
| 进程结构 | 4 节点松耦合（特征→里程计→建图→PGO） | 单节点 | 单节点（5 模块同进程） | 离线 runner + System 库 |
| 输入 | `/velodyne_points`（经 3 个中间节点） | `/livox/lidar`+`/livox/imu`（参数可改） | `/velodyne_points`+`/imu_raw` | 磁盘图像序列 + EuRoC IMU |
| 最终位姿输出 | `/aft_pgo_odom` | `/Odometry` | `/lio_sam/mapping/odometry` | `TrackMonocular` 返回值 / 轨迹文件 |
| 状态所有者 | 分散（3–4 进程） | 单进程（`_state`+ikdtree） | 单进程（关键帧+iSAM2） | 单进程（Atlas） |
| **测量注入点** | **无**（替换测量需重跑特征+里程计） | **有**（话题级 relay，已验证） | **有**（话题级 relay） | **无**（离线读盘，需改 runner） |
| 回滚对象 | `SleepMapList` 分段图 + PGO 关键帧 | 体素八叉树 + 状态（已有实现） | `cloudKeyPoses3D/6D` + iSAM2 | **`SaveAtlas/LoadAtlas`（官方 API）** |
| 输入缓冲/重放 | 无（需新增） | 已有 `replay_buffer_` + `reprocess` | 无（需新增） | 无（文件重读可模拟） |
| 输入退化风险 | 中（多进程，退化表现为跳变） | 高（曾出现运行期地图暴涨） | **极高**（120–140 s 点云 26k→200，130.3 s 起发散） | **高**（低视差，80 次初始化失败） |
| 既有闭环证据 | 原生双事件 PASS；恢复层 NOT_IMPLEMENTED | 原生双事件 PASS（共享版）；独立版 BLOCKED_LOAD；恢复层未接 | 原生 FAIL（输入退化）；恢复层未接 | 原生 FAIL（未稳定跟踪）；恢复层未接 |

## 2. 按 A1–A12 的接线含义

| 需求 | 结论 |
|---|---|
| A1 输入与身份 | LIO-SAM/FAST-LIO2 可直接在话题层取证；ORB-SLAM3 需 runner 级身份；MM-LINS 需 4 节点联合身份 |
| A4 完整可信检查点 | ORB-SLAM3 有官方 Atlas 存取；LIO-SAM/FAST-LIO2 单进程可快照；MM-LINS 跨进程最难 |
| A5 隔离与帧归宿 | 四者都需要"停止写入地图"的钩子；LIO-SAM/FAST-LIO2 有天然停写点，MM-LINS 需三处同步 |
| A6 历史重处理 | 只有 FAST-LIO2 已有 `reprocess`；LIO-SAM/MM-LINS 需输入缓冲；ORB-SLAM3 可重读文件 |
| A8 原子提交 | 单进程宿主风险低；MM-LINS 必须定义"联合提交点" |
| 论文轴测量修复 | **只有 FAST-LIO2 与 LIO-SAM 能复现"替换单帧测量→重放"**；MM-LINS/ORB-SLAM3 不具备 |

## 3. 结论

1. **能承载"测量修复"闭环的宿主：FAST-LIO2、LIO-SAM**（话题级注入点）。
2. **能承载"状态/地图回滚"的宿主：四者都可以，但成本排序 ORB-SLAM3（官方 API）< FAST-LIO2（已实现）
   < LIO-SAM（需写快照）< MM-LINS（跨进程）**。
3. **输入退化是四宿主的共同前提**：LIO-SAM 的 130 s 发散、ORB-SLAM3 的低视差初始化失败、
   FAST-LIO2 的地图暴涨都先于任何恢复逻辑发生；恢复策略必须先区分"输入故障 vs 算法故障"。
4. **不建议把 FAST-LIVO2 的实现默认平移到其它宿主**：SC-PGO 没有测量注入点这一条已足以推翻平移假设。
