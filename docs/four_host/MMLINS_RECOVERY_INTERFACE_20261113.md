# MM-LINS / SC-PGO 的恢复层接线前置分析（只读）

日期：2026-11-13。范围：只读源码与既有 run 报告，不构建、不运行、不改代码。
证据引用格式 `文件:行`。凡需要构建或运行才能确认的点，明确标注"未确认"。

## 0. 更正（2026-11-13，Codex 审阅 `6b6263b`）

本文 §2 描述的 **4 节点 SC-PGO 流水线不是 `run_mmlins.sh` 实际启动的拓扑**。实际情况：

- `run_mmlins.sh:49-56` 启动两个 roslaunch：
  `fast_lio mapping_velodyne_m2dgr.launch`（节点 `/laserMapping`）与
  `aloam_velodyne fastlio_ouster64.launch`（节点 `/alaserPGO`），就绪判定同时等待这两个节点。
- PGO 通过 remap 消费前端：`/aft_mapped_to_init → /Odometry`、`/velodyne_cloud_registered_local →
  /cloud_registered_body`、`/cloud_for_scancontext → /cloud_registered_lidar`
  （`SC-PGO/launch/fastlio_ouster64.launch:28-30,36`）。
- 因此 **MM-LINS 的测量输入面就是 FAST-LIO 前端的 `/velodyne_points` + IMU 订阅**
  （`FAST-LIO/src/laserMapping.cpp:758-759`）；**话题级测量注入点是存在的**，与 FAST-LIO2 同构。
- 相应地：前端地图是 `KD_TREE ikdtree`（`:91`），"重建"是 `re_slam()` 重置 ESKF 并清树（`:673-693`），
  **没有 `replay_buffer_`/`reprocess`**（那套属于 FAST-LIVO2）。
- 本文 §2/§5 中把 SC-PGO 的 4 节点链当作 MM-LINS 的主拓扑、以及"无测量注入点"的结论，**按此更正作废**；
  4 节点链只适用于 SC-PGO 独立运行（A-LOAM 特征→里程计→建图）的模式。

## 1. 结论摘要

- MM-LINS 是 **4 节点松耦合流水线**：`scanRegistration → laserOdometry → laserMapping →
  laserPosegraphOptimization`，另有一个**可选的 FAST-LIO 前端**（作为激光里程计替代）。
  状态分散在 3–4 个进程里，**没有单一状态所有者**，这是接线的首要约束。
- `slam_recovery` 的文件命令通道（`cmd`/`ack`）与隔离/段语义可以**原样复用**，但宿主侧需要新增：
  命令通道、hold/snapshot/restore 的具体实现、输入缓冲（用于 replay）、以及按节点拆分/合并的
  checkpoint 序列化。
- **测量级修复（repair）在 SC-PGO 上没有注入点**：特征在 `scanRegistration` 产生、里程计在
  `laserOdometry` 消费，替换测量意味着重跑整条链，不存在 FAST-LIVO2 那种"重放时替换扫描"的等价路径。
- 天然可用的两处：PGO 的**关键帧图与 iSAM2 状态**（`Mapmanager.ActiveMap`）是天然的"软回滚"对象；
  前端的 `Issleeping`/`Isbuilding` 是现成的"停写/重建"信号（MM-LINS 自己的休眠-重建机制）。

## 2. 数据流与话题（证据）

| 环节 | 输入 | 输出 | 证据 |
|---|---|---|---|
| 特征提取 | `/velodyne_points` | `/velodyne_cloud_2`、`/laser_cloud_{sharp,less_sharp,flat,less_flat}` | `SC-PGO/src/scanRegistration.cpp:492,494,496-502` |
| 激光里程计 | 上述特征 + `/velodyne_cloud_2` | `/laser_odom_to_init`、`/velodyne_cloud_3` | `SC-PGO/src/laserOdometry.cpp:195-213` |
| 建图 | `/laser_cloud_corner_last`、`/laser_cloud_surf_last`、`/laser_odom_to_init`、`/velodyne_cloud_3` | `/aft_mapped_to_init`、`/velodyne_cloud_registered(_local)`、`/laser_cloud_surround`、`/laser_cloud_map` | `SC-PGO/src/laserMapping.cpp:921-940` |
| 位姿图 | `/velodyne_cloud_registered_local`、`/aft_mapped_to_init`、`Issleeping`、`Isbuilding` | `/aft_pgo_odom`、`/aft_pgo_path`、`/aft_pgo_map`、`/repub_odom`、`/loop_scan_local` | `SC-PGO/src/laserPosegraphOptimization.cpp:1275-1286` |
| 可选前端（FAST-LIO） | `/livox/lidar`、`/livox/imu`（参数可改） | `/Odometry`、`Issleeping`、`Isbuilding` | `FAST-LIO/src/laserMapping.cpp:705-708,767-768` |

## 3. 恢复层需要接触的宿主状态（证据）

| 状态 | 位置 | 规模/性质 | 能否快照 |
|---|---|---|---|
| 里程计位姿/速度 | `q_w_curr`、`t_w_curr`、`systemInited`（`laserOdometry.cpp:69,93-94`） | 十几个标量 + 若干局部地图点云 | 小，易序列化；但里程计自身**无重定位**，一旦漂移只能靠上层重建 |
| 建图立方体 | `laserCloudCornerArray[4851]`、`laserCloudSurfArray[4851]`（`laserMapping.cpp:77-104`） | 固定 21×11×21 立方体，指针数组 + 点云 | 可深拷贝；**大**（数十至数百 MB 量级，需实测） |
| PGO 关键帧与图 | `Mapmanager.ActiveMap->keyframeposesUpdated/keyframeTimes/keyframeClouds`、`isam`（`laserPosegraphOptimization.cpp:106,119,329-381`） | 关键帧序列 + iSAM2 增量图 | 关键帧可序列化；iSAM2 需重新 `update` 重建（GTSAM 支持序列化，但需验证） |
| 休眠地图列表 | `Mapmanager.SleepMapList[...]`（`laserPosegraphOptimization.cpp:477-480`） | 多张历史子图 | 结构上就是"分段地图"，可作为粗粒度回滚点 |
| 前端重建 | `re_slam()`（`FAST-LIO/src/laserMapping.cpp:673-698`） | 重建 ESKF、清空 ikdtree | 是"回到初始态"，不是回滚到某个历史点 |

## 4. `slam_recovery` 现有接口（可复用面）

- **命令通道**：`cmd`/`ack` 文件对 + `cmd.done` 重命名，命令集 `hold/snapshot/restore/reprocess/
  set_state/resume/status`；`ack` 返回宿主侧 `checkpointStatus()` 的文本（可扩展字段）。
  客户端串行化、`expire_pending` 处理在途命令（`recovery_node.py: `_send`/`pending`）。
- **事务/隔离**：`trigger_quarantine`、`register_quarantined_frame`、`validate_and_resolve`、
  `maybe_close_waiting_segment`、`rearm`、`create_checkpoint/restore_checkpoint`
  （`quarantine/manager.py:104-133,159,260,280,522,566`）。
- 宿主适配只要实现：**收到 `hold` 停止写入**、**`snapshot` 生成可恢复对象**、**`restore` 回到该对象**、
  **`reprocess` 从该对象重放到当前**、**`status` 报告计数**。SC-PGO 的难点是这四件事要跨进程。

## 5. 最小接线点（三列）

| 能做什么（现有设施即可） | 不能做什么（现状不具备） | 需要宿主改什么 |
|---|---|---|
| 用 `Isbuilding`/`Issleeping` 作为"停写/重建"的触发信号（PGO 已订阅，`laserPosegraphOptimization.cpp:1278-1279`） | **测量级修复**：SC-PGO 无"替换一帧测量并重估"的入口；特征与里程计在另外两个进程里 | 在 `laserMapping` 与 `laserPosegraphOptimization` 主循环加命令目录轮询（与 FAST-LIVO2 同构，~40 行/节点） |
| PGO 关键帧图为"软回滚"对象：丢弃 checkpoint 后的关键帧并重跑 iSAM2（图优化天然可重算） | **跨进程原子性**：odometry/mapping/PGO 三者任一不同步，回滚后状态不一致 | odometry 状态快照结构（`q_w_curr/t_w_curr/systemInited` + 局部地图），~80 行 |
| 粗粒度回滚点：`SleepMapList` 的分段地图 | **状态序列化不存在**：无 checkpoint 结构、无 restore 路径 | 建图立方体深拷贝/恢复（可参考本仓 `native_checkpoint.cpp` 的 octree 克隆思路，但 SC-PGO 用的是固定立方体数组，需新写） |
| 独立准入：`/aft_pgo_odom` 已是最终位姿输出，可直接喂给候选/门 | **重放**：无输入缓冲；要 replay 必须在宿主侧缓存 `/velodyne_points` + IMU 并在 restore 后重喂 | 输入缓冲（replay 用）与 `reprocess` 驱动，~60 行 + 内存预算 |
| 命令/事务/门：`slam_recovery` 侧**完全复用**，无需改 | **单前端的 FAST-LIO 变体**：前端是另一个进程/另一套重建逻辑，接线目标不同 | 选型：接 SC-PGO 四节点，还是只接 FAST-LIO 前端（后者已有 `re_slam`，但恢复语义是"重置"不是"回滚"） |

## 6. 风险清单

1. **跨进程 checkpoint**：四节点没有共同时钟/共同提交点；`snapshot` 天然非原子。缓解：先把
   "停写"（hold）做成全局（三个节点都暂停消费）再各自快照，代价是停写窗口变长。
2. **iSAM2 状态不可轻量复制**：GTSAM 图可序列化，但 `isam` 的增量状态需要重新 `update` 才能与
   快照一致；恢复后的首批关键帧可能触发重优化，行为与在线不同（需实测）。
3. **大对象开销**：建图立方体与关键帧点云都是 MB 级；2 s 滚动快照的代价需实测（本次未测）。
4. **无测量级修复**：若主线要求"同 FAST-LIVO2 的 repair→replay"，MM-LINS 上不存在等价入口；
   要么接受"只做状态/地图回滚 + 重放"，要么改 `scanRegistration`/`laserOdometry` 增加测量注入
   （属宿主算法改动，需用户/主线批准）。
5. **前端二选一**：SC-PGO 的四节点链与 FAST-LIO 单节点链的恢复语义不同（回滚 vs 重置重建）；
   文档与验收必须写清接的是哪一条。
6. **权限与负载**：本机 `/proc/loadavg` 是宿主全局（容器未挂 lxcfs），不代表容器可用算力；
   运行前必须按运行时可观测判据（play 速率、cgroup `nr_throttled`）而不是 loadavg 决策。

## 7. 未确认项（需要构建/运行才能定，本次未做）

- 建图立方体深拷贝的真实内存与耗时；
- iSAM2 序列化/重放的实际行为；
- `re_slam()` 后再接入 PGO 时关键帧索引是否连续；
- 命令通道插入后对 4 节点时序的影响。

## 8. 证据文件

`SC-PGO/src/{scanRegistration,laserOdometry,laserMapping,laserPosegraphOptimization}.cpp`、
`FAST-LIO/src/laserMapping.cpp`、`/tmp/wt-sim/slam_recovery/ros/recovery_node.py`、
`/tmp/wt-sim/slam_recovery/quarantine/manager.py`、
`docs/review_20261112_four_host/mmlins_campus12_20261112/REPORT.md`（既有运行证据）。
