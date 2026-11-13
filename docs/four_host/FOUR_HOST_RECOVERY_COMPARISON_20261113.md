# 四宿主恢复层接口对比（A1–A12 接线依据）

日期：2026-11-13。只读结论，基于四份接口/失败分析：
`MMLINS_RECOVERY_INTERFACE_20261113.md`、`LIOSAM_DIVERGENCE_20261113.md`、
`ORBSLAM3_FAILURE_20261113.md`、`fastlio2_independent_20261113/REPORT.md`。
凡标"待测"的项需要构建或运行确认，本次均未做。

## 1. 总表

| 维度 | MM-LINS / SC-PGO | FAST-LIO2 | LIO-SAM | ORB-SLAM3 |
|---|---|---|---|---|
| 实际拓扑 | **FAST-LIO 前端 + `alaserPGO` 两节点**（`run_mmlins.sh:49-56`；PGO 经 remap 消费 `/Odometry`、`/cloud_registered_body`、`/cloud_registered_lidar`，`SC-PGO/launch/fastlio_ouster64.launch:28-30,36`） | 单节点 | 单节点（5 模块同进程） | 离线 runner + System 库 |
| 输入 | `/velodyne_points` + IMU（FAST-LIO 前端直接订阅，`FAST-LIO/src/laserMapping.cpp:758-759`） | `/livox/lidar`+`/livox/imu`（参数可改，`:758-759`） | `/velodyne_points`+`/imu_raw` | 磁盘图像序列 + EuRoC IMU |
| 最终位姿输出 | `/aft_pgo_odom`（PGO） | `/Odometry` | `/lio_sam/mapping/odometry` | `TrackMonocular` 返回值 / 轨迹文件 |
| 状态所有者 | 两进程（FAST-LIO 的 ESKF+ikdtree；PGO 的关键帧+iSAM2） | 单进程（`_state`+ikdtree，`laserMapping.cpp:91`） | 单进程（关键帧+iSAM2） | 单进程（Atlas） |
| **测量注入点** | **有**（FAST-LIO 前端的点云/IMU 订阅面；按实际拓扑判断，不是按进程数） | **有**（话题级 relay，已验证） | **有**（话题级 relay） | **无**（离线读盘，需改 runner） |
| 回滚对象 | PGO 关键帧+iSAM2（`Mapmanager.ActiveMap`）+ 前端 `re_slam` 重建 | `re_slam()` 重置 ESKF 并清 `ikdtree`（`laserMapping.cpp:673-693`） | `cloudKeyPoses3D/6D` + iSAM2 | **`SaveAtlas/LoadAtlas`（官方 API）** |
| 输入缓冲/重放 | 无（需新增；前端 `re_slam` 只是重置） | **无 replay/reprocess**（那套是 FAST-LIVO2 的，本树没有） | 无（需新增） | 无（文件重读可模拟） |
| 输入退化风险 | 中（前端 FAST-LIO，退化表现为休眠重建；实际 run 中 E1/E2 各一次） | 高（曾出现运行期地图暴涨） | **极高**（120–140 s 点云 26k→200，130.3 s 起发散） | **高**（低视差，80 次初始化失败） |
| 既有闭环证据 | 原生双事件 PASS；恢复层 NOT_IMPLEMENTED | **独立构建 NATIVE_INDEPENDENT + PASS**（与共享版在 REPORT 表列的 8 个对比项上一致）；恢复层未接 | 原生 FAIL（输入退化）；恢复层未接 | 原生 FAIL（未稳定跟踪）；恢复层未接 |

## 2. 按 A1–A12 的接线含义

| 需求 | 结论 |
|---|---|
| A1 输入与身份 | LIO-SAM/FAST-LIO2 可直接在话题层取证；ORB-SLAM3 需 runner 级身份；MM-LINS 为 FAST-LIO + PGO **两节点**，需两节点联合身份 |
| A4 完整可信检查点 | ORB-SLAM3 有官方 Atlas 存取；LIO-SAM/FAST-LIO2 单进程可快照；MM-LINS 为两进程（FAST-LIO 状态 + PGO 图），需联合快照 |
| A5 隔离与帧归宿 | 四者都需要"停止写入地图"的钩子；LIO-SAM/FAST-LIO2 单点停写，MM-LINS 需在 FAST-LIO 与 PGO **两处**同步 |
| A6 历史重处理 | 四个宿主**都没有** replay/reprocess（FAST-LIVO2 的那套不能平移）；LIO-SAM/FAST-LIO2/MM-LINS 需输入缓冲，ORB-SLAM3 可重读文件 |
| A8 原子提交 | 单进程宿主风险低；MM-LINS 必须定义"联合提交点" |
| 论文轴测量修复 | **FAST-LIO2、LIO-SAM、MM-LINS 都具备话题级测量输入面**（按实际订阅判断）；ORB-SLAM3 离线读盘不具备 |

## 3. 结论

1. **能承载"测量修复"闭环的宿主：FAST-LIO2、LIO-SAM、MM-LINS**（都有话题级测量输入面）。
2. **能承载"状态/地图回滚"的宿主：四者都可以，但成本排序 ORB-SLAM3（官方 API）< FAST-LIO2
   （`re_slam` 重置 + 需补快照）< LIO-SAM（需写快照）< MM-LINS（两进程联合快照）**。
3. **输入退化是四宿主的共同前提**：LIO-SAM 的 130 s 发散、ORB-SLAM3 的低视差初始化失败、
   FAST-LIO2 的地图暴涨都先于任何恢复逻辑发生；恢复策略必须先区分"输入故障 vs 算法故障"。
4. **不建议把 FAST-LIVO2 的实现默认平移到其它宿主**：FAST-LIVO2 的 `replay_buffer_`/`reprocess`/八叉树
   检查点在这四个宿主里都不存在（FAST-LIO 是 ikdtree、`re_slam` 只能重置），需要按宿主重写。

## 4. 更正记录（2026-11-13，Codex 审阅 `6b6263b`）

- 本表初版把 MM-LINS 写成"4 节点松耦合、无测量注入点"，**错误**：`run_mmlins.sh:49-56` 实际启动
  `fast_lio mapping_velodyne_m2dgr.launch`（`/laserMapping`）与 `aloam_velodyne fastlio_ouster64.launch`
  （`/alaserPGO`）两个节点；PGO 通过 remap 消费前端输出（`SC-PGO/launch/fastlio_ouster64.launch:28-30,36`）。
  初版的 4 节点描述来自 SC-PGO 自带的 A-LOAM 流水线源码，不是本 run 的实际拓扑。
- 初版把"已有 `replay_buffer_`/`reprocess`"写成 FAST-LIO2 的能力，**错误**：那是 FAST-LIVO2 的实现；
  FAST-LIO 树里没有（`laserMapping.cpp` 只有 `re_slam` 重置 + `ikdtree`）。
- "能否做测量修复"改为**按实际拓扑与订阅面判断**，不按进程数推断。
- 同日 S1 集成时再加两条限定（来源 `docs/OVERNIGHT_RESULTS_20261113_S1.md` §3 与审阅 `330e594`）：
  ① 上表 FAST-LIO2 的"一致"仅指独立报告表格里**逐条列出的 8 个项**（条数、首末戳、两次断流、max_step、
  E1/E2 后停发、尾段、sleep/build 计数），**不覆盖全轨迹逐条相同**；共享版与独立版的轨迹步长和 485.08/353.43 m
  差异由重建跳变是否计入解释，但 config/output hash 仍缺。② FAST-LIO2 的独立构建是**MM-LINS 派生前端**，
  "独立工作区构建"成立，不等于"宿主源码级独立实现"。
