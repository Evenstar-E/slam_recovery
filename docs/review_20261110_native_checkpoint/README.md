# 原生 checkpoint：FAST-LIVO2 上的深拷贝、恢复与重放（2026-11-10）

范围按 S1 `5206027` 的转向要求：**收尾在手工作，保存证据，给出宿主接口事实，不跑完整两事件**。
没有为 LIVO 再开检测/参考密度/ICP/门参数循环，也没有在选宿主前跑两事件。

## 1. 实际做了什么

宿主原来没有 restore/checkpoint/snapshot 入口，也没有任何 `advertiseService`（全仓 0 个
`ros::ServiceServer`），所以恢复所需状态全部是私有成员，外部无法读写。本轮加了**一个入口加最小接线**：

| 位置 | 内容 |
|---|---|
| `include/native_checkpoint.h` / `src/native_checkpoint.cpp`（新） | `VoxelOctoTree` 的深拷贝/释放/计数。只有这一件事，不含序列化格式、索引 sidecar 或第二个估计器 |
| `src/LIVMapper.cpp:679` `snapshotCheckpoint()` | 复制 `_state`、`state_propagat`、voxel map、IMU 预处理跨帧四值；同时清空并**开始捕获**后续 `LidarMeasureGroup` |
| `src/LIVMapper.cpp:700` `restoreCheckpoint()` | 释放当前 map，装入快照；写回 `_state`/`state_propagat`/`voxelmap_manager->state_`/IMU 四值；`lidar_map_inited=true` |
| `src/LIVMapper.cpp:728` `reprocessCheckpoint()` | 恢复后把捕获的每个 group 依次 `processImu()` + `stateEstimationAndMapping()`，**走宿主自己的** LIO 更新与 `UpdateVoxelMap` |
| `src/LIVMapper.cpp:776` `pollCheckpointControl()` | 目录文件通道：`<dir>/cmd` 被宿主先改名 `cmd.done` 再执行（保证恰好执行一次），结果写 `<dir>/ack` |
| `include/IMU_Processing.h` | `getCheckpointState/setCheckpointState`：暴露 `last_imu`、`last_prop_end_time`、`acc_s_last`、`angvel_last` |
| `slam_recovery/ros/recovery_node.py` `CheckpointClient` | 驱动侧：健康期每 2 s 滚动快照；决策后拒绝→`restore`，接纳→`reprocess`；每次等待 ack 并记录 |

重放期间 `publish_odometry/publish_path/publish_mavros/publish_effect_world` 全部静默，
否则旧时间戳会被恢复节点当成新输入二次配对。

## 2. 冒烟结果（PASS/FAIL）

命令：`bash slam_recovery/ros/smoke_checkpoint.sh /tmp/fastlivo/hall01_inj43_filtered.bag /tmp/cp_smoke7 1.0 30`
（不判门、不跑检测、不建候选）。宿主 binary `b465409e…`（MP_EN，`MP_PROC_NUM=4`）。

| 项 | 实测 | 判定 |
|---|---|---|
| 深拷贝 | 10734 voxels / 21349 nodes / **210985 points**，ack 0.086 s | **PASS** |
| 恢复回滚 | live 10773 voxels / 212255 points → **10734 / 210985**（与快照逐值相同），状态回到 `2.007873,1.127087,0.097816` | **PASS** |
| 重放 | 8 帧经宿主 `handleLIO` 重新估计并写回 map，0.358 s | **PASS** |
| 修复测量注入 | 未实现：宿主只吃自己预处理出的点云 | **NOT_IMPLEMENTED** |
| 隔离期间地图停写 | 未实现：host 仍在每帧 `UpdateVoxelMap` | **NOT_IMPLEMENTED** |

耗时说明：ack 延迟含宿主 20 ms 轮询间隔，是拷贝本体的**上界**；2 s 滚动周期下开销可忽略。
产物：`/tmp/s2_native_checkpoint/{host_smoke.log,smoke_results.json,fastlivo2_worktree.diff,native_checkpoint.h,native_checkpoint.cpp}`。

## 3. FAST-LIVO2 接口事实表（只给事实）

### 3.1 恢复"完整状态"需要哪些对象

| 对象 | 位置 | 持有者 | 可否复制 |
|---|---|---|---|
| 体素地图 | `include/voxel_map.h:194` `VoxelMapManager::voxel_map_` | `voxelmap_manager`（`LIVMapper.h`） | 结构是裸指针 octo 树（`voxel_map.h:129`，`leaves_[8]` + `VoxelPlane*`），**必须深拷贝**，无序列化 |
| 估计状态 | `include/LIVMapper.h:168` `_state`（`StatesGroup`） | `LIVMapper` | 纯值类型，直接拷贝 |
| 传播起点 | `include/LIVMapper.h:169` `state_propagat` | `LIVMapper` | 同上 |
| 消息缓冲 | `LIVMapper.h:140/142/143` `lid_raw_data_buffer`、`imu_buffer`、`img_buffer` | `LIVMapper` | `shared_ptr` 队列，拷贝即共享 |
| 当前待处理组 | `LIVMapper.h:167` `LidarMeasureGroup LidarMeasures` | `LIVMapper` | 同上（`Pcl::Ptr` + `Imu::ConstPtr` 队列） |
| IMU 预处理跨帧量 | `include/IMU_Processing.h` `last_imu`、`last_prop_end_time`、`acc_s_last`、`angvel_last` | `p_imu`（`ImuProcess`） | 值类型；**不恢复则重放起点错误** |
| IMU 初始化量 | 同上 `imu_need_init`、`imu_time_init`、`init_iter_num`、`mean_acc/gyr`、`cov_*` | `p_imu` | 初始化后不再变；跨初始化重放才需要 |
| 视觉地图 | `include/vio.h:111/126/127/128` `visual_submap`、`feat_map`、`sub_feat_map`、`warp_map` | `vio_manager`（`VIOManager`） | 裸指针 `VisualPoint*`/`Warp*`，**无拷贝、无序列化**。仅 LIVO 模式需要；本仓 m2dgr 配置下 LIO 主路径不读它 |
| 光度标定 | `VIOManager` 内 `inv_expo_time` 等 | `_state.inv_expo_time` + `vio_manager` | 值类型 |

### 3.2 测量重处理的实际调用点

```
LIVMapper::run()                                    src/LIVMapper.cpp:831
  └ sync_packages(LidarMeasures)                    src/LIVMapper.cpp:1311
  └ processImu()                                    src/LIVMapper.cpp:373
      └ ImuProcess::Process2                        src/IMU_Processing.cpp:558
          └ ImuProcess::UndistortPcl                src/IMU_Processing.cpp:252
  └ stateEstimationAndMapping()                     src/LIVMapper.cpp:392
      └ handleLIO()                                 src/LIVMapper.cpp:461
          ├ VoxelMapManager::StateEstimation        src/voxel_map.cpp:338
          └ VoxelMapManager::UpdateVoxelMap         src/LIVMapper.cpp:549 → voxel_map.cpp:609
```

**能否从缓存重放：能，已验证。** `UndistortPcl` 的输入全部来自 `LidarMeasureGroup`
（`measures.back().imu` 的 `ImuConstPtr` 队列 + `pcl_proc_cur` 的 `PointCloudXYZI::Ptr`），
加上 3.1 的四个跨帧量；本轮 8 帧重放已走通同一条调用链。

### 3.3 内部地图按扫描的所有权/撤销能力

- **没有按扫描的归属标记**：`VoxelOctoTree::temp_points_` 只累加点，`pointWithVar` 不带
  scan id/time；`UpdateVoxelMap`（`voxel_map.cpp:609`）直接插入。
- **没有删除单条扫描的 API**。唯一的清理是 `clearMemOutOfMap`（`voxel_map.cpp:950`），按空间
  箱体整块清（用于 `mapSliding`），不能按扫描撤销。
- 结论：**撤销粒度只能到"整张地图快照"**，这也是本轮做成深拷贝的原因；按扫描撤销需要新加
  标记 + 重建能力，属新增工作，不是接线。

### 3.4 接回与重武装的调用点

- **接回**：宿主没有"隔离"概念，隔离期间它**继续消费并继续写图**（`run()` 循环不暂停）。
  本轮 `restore` 能把地图整体回滚，但在下一次 `UpdateVoxelMap` 之后污染帧又被合并回去——
  所以"接回"目前只有**回滚那一刻**成立。
- **重武装**：只在 Python 侧（`QuarantineManager.rearm`，S1 `a1a371d`）；宿主侧没有对应钩子。
- 明确缺口：宿主需要一个"暂停写图/暂停消费"的标志位（最小实现：`handleLIO` 里绕开
  `UpdateVoxelMap`，并在 `sync_packages` 前按标志决定是否丢弃组）。

### 3.5 现有环境与产物

| 项 | 值 |
|---|---|
| 工作区 | `/home/R26534/fast_livo2_ws`（ROS 在 `/home/R26534/mm/ros`） |
| 源码 | `/home/R26534/fast_livo2_ws/src/FAST-LIVO2`，上游 `0d2c034` + 未提交 patch（`fastlivo2_worktree.diff`，sha `f5efce71…`） |
| binary | `fastlivo_mapping` sha `b465409e…`；`liblaser_mapping.so` 见 `smoke_results.json` |
| 配置 | `config/m2dgr.yaml`、`config/camera_m2dgr.yaml`（sha 见收据） |
| 输入 | `hall01_inj43_filtered.bag` `c90300cb…`（单事件）；双事件包 `hall01_two_event_v1.bag` `c3e905da…`（E2 在 +42…52 s，99 帧，宿主无关） |
| 构建 | `catkin_make -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -j8`，约 12–14 min 全量、增量 <2 min |

### 3.6 最小还差哪几件事（逐项，不合并）

1. **隔离期停写图**：`handleLIO` 里给 `UpdateVoxelMap` 加门（约 5 行）；否则回滚瞬间之后污染帧会回来。
2. **修复测量注入**：宿主只吃 `pcl_proc_cur`；要有修复点云就必须在 `processImu` 之前替换该
   `Ptr`（需要一条 repaired-scan 话题 + 按时间戳匹配，约 40 行）。
3. **接纳后的状态写回**：现在接纳只决定"不 restore"；要把修复位姿真正写回 `_state` 还缺一步。
4. **视觉地图检查点**：只有用 LIVO 模式才需要；`feat_map/warp_map/visual_submap` 无拷贝入口，
   是这一侧最大的一块新工作。
5. **宿主侧重武装钩子**：与第 1 项同一处标志位，Python 侧已有 `rearm`。

## 3b. 隔离期停写图（第一断点，已做）

宿主新增 `map_hold_` 标志与两条命令 `hold` / `resume`：

- `handleLIO()`（`src/LIVMapper.cpp:553`）里 `UpdateVoxelMap` 被显式门控——hold 期间帧**照常传播、
  照常估计**，但 `held_frames_/held_points_` 只计数不写图；
- `BuildVoxelMap`（`:487`）与 `mapSliding`（`:567`）同样被门控，避免首帧建图或滑窗在 hold 期间改动地图。

实测（hall01 filtered @1.0，快照在 frame 113：12130 voxels / 242541 points）：

| 时点 | live_points | 期间处理但未写图的帧/点 | hold |
|---|---:|---:|---:|
| hold 前 | 265080 | 0 | 0 |
| hold | 265706 | 0 | 1 |
| held +2 s | **265706** | 22 / 345031 | 1 |
| held +4 s | **265706** | 72 / 671526 | 1 |
| held +6 s | **265706** | 128 / 896075 | 1 |
| restore（仍 hold） | **242541** | 129 | 1 |
| restore 后 +2 s | **242541** | 159 / 950823 | 1 |
| resume 后 +4 s | 278125 | — | 0 |
| resume 后 +8 s | 306865 | — | 0 |

四项判定全 PASS：地图停增、帧被处理但不写、restore 不会被 hold 期间的帧撤销、resume 后从
checkpoint 继续增长（不是跳回 265706）。

**必须照实写的副作用**：hold 期间估计器仍在跑，而地图是冻结的，于是状态在 6 s 内从
`3.60 → 6.68` 漂移（同期正常运动约 0.67 m/3 s）。所以 hold 保护的是**地图**，不是**估计**；
restore 会把估计一起回滚，输入恢复时这就是**声明过的轨迹不连续**。

## 3c. 宿主侧重武装钩子（第二断点，已做）

`resume` 与 `hold` 共用同一标志位，由驱动侧在**管理器 re-arm 时**调用：

- `recovery_node.py::CheckpointClient.hold()` 在 `_open_episode()`（订阅回调线程）里**只写命令不等 ack**，
  避免深拷贝/等待阻塞配对；ack 由主线程 `service()` 收取。
- `_apply_lifecycle()` 在每次 `service()` 里检查 `tx_mgr.lifecycle_events` 新增项，遇到 `rearm`
  就发 `resume`，并且每个事件**只处理一次**（`_lifecycle_seen`）。
- 事件落在 `run_summary.json` 的 `lifecycle.native_checkpoint_actions`
  （plus 原有 `lifecycle.events`），所以"宿主没收到 resume"不会被记成"重武装发生过"。

单测（验收命令 `python -B -m unittest discover -s slam_recovery/tests -t .`）：**90 passed**
（原 83 + 本项 7），其中 `test_opening_a_segment_holds_the_host_map`、
`test_a_re_arm_writes_resume`、`test_lifecycle_events_are_only_acted_on_once` 直接覆盖本钩子。

## 3d. 修复测量注入（第三断点，受控接口测试）

**声明**：CONTROLLED_INTERFACE_TEST，不是检测成绩、也不是修复质量结论。触发方式是测试脚本直接调用恢复接口。

接口：宿主订阅 `/native_recovery/repaired_scan`（`sensor_msgs/PointCloud2`），走同一个
`PreProcess`，按**扫描起始时间戳**入队；`reprocessCheckpoint()` 在重放每一帧前
`applyRepairedScan()`，命中就替换 `meas.lidar` / `meas.pcl_proc_cur`，其余字段不动。

两处实测事实（都是先跑出来才知道的）：

1. **live 路径不可能命中**：修复是在帧处理**之后**才决定的，实测表现为 `received` 有、
   `applied` 恒 0。所以注入点必须在重放里，不在主循环里；主循环那次调用已删除并留注释。
2. **组的起始时间要从结束时间反推**：这个模式下 `lidar_frame_beg_time` 只在开扫描组时赋值
   （其余为 0），PCL header 也不随 `pcl_proc_cur` 传递。实测可用的换算是
   `begin = measures.back().lio_time - 末点 curvature/1000`，误差约 9 ms，因此匹配窗口取 20 ms
   （扫描周期 100 ms，不会串帧）。

实测（hall01 filtered，rate 0.5，dz=+1.0 m，bag 20–22 s）：

| 项 | 实测 | 判定 |
|---|---|---|
| 发布修复扫描 | 20 | — |
| 重放并替换测量 | **10** | PASS（`repair_applied`） |
| 未匹配到帧 | **10** | 如实记录（`repair_dropped`） |
| 重放帧数 / 时间跨度 | 426 帧 / bag 13.6–27.7 s | — |
| 重放后宿主地图 | 12733 → **16651** voxels，245751 → 282179 points | PASS（宿主自己重算） |
| 重放后宿主状态 | `7.205,9.046,0.140` → `3.448,2.157,0.044` | — |

**未解决、如实标注**：20 条里有 10 条没找到可替换的帧。原因**未确定**，候选解释是 LIVO 模式下
`pcl_proc_next` 会把连续扫描并进同一个观测组，于是被并掉的那一帧没有独立组可替换。这是测出来的
数字，不是解释掉的数字。

**未证明**：重放后地图/状态的变化里，有多少来自修复、有多少来自"重放本身"。
要分清需要一次**不带修复的重放对照**；但同一输入两次运行的基线差已测得 **>1.6 m**，
大于 1.0 m 修复在此处的效果量级，所以本轮预算内无法据此归因。

## 3e. 精确匹配的尝试：没做到，并量到了为什么

S1 建议"用帧自己的 header 做键、修复保留同一 header，就不用窗口"。照做之后实测**失败**，两次：

1. **给合并组的点云补 header**（`pcl_proc_cur->header.stamp = 最后合并扫描的时间`）→ `applied` 从
   10 掉到 **0**。因为一旦 header 非 0，匹配就切到 1 ms 精确模式，而这个组的起始与扫描自身
   header 相差几毫秒，于是全部落空。该改动**已回退**，代码里留了注释说明原因。
2. **按组的扫描区间匹配**（`native_scan_first/native_scan_last`，区间内命中即替换）→ 实测
   **一次都没命中**：这一模式下大部分组的 `merged_scans == 0`，区间压根没被赋值。

顺带得到一条能排除假设的计数：

| 计数 | 实测 | 含义 |
|---|---:|---|
| `merged_scans` | 217–230（整趟） | 有这么多扫描是被合并进组的 |
| `multi_scan_groups` | **0** | 但没有任何一个组合并了 **>1** 个扫描 |

也就是说**"合并导致不可替换"这条假设在本窗口被排除**：每个合并组恰好一个扫描。20 条修复里
10 条找不到帧的原因**仍未确定**，不作解释。

## 3f. 接纳后的状态写回（第四断点，已做）

命令 `set_state tx ty tz qx qy qz qw`（第二行为 payload）：写 `_state.pos_end/rot_end`、
`state_propagat`、`voxelmap_manager->state_`。驱动侧在**接纳**时先 `reprocess`，再
`set_state(最后一帧修复位姿)`；拒绝时仍是 `restore`。四元数由 `_rotation_to_quaternion` 给出
（无 scipy 依赖，单测覆盖单位旋转与绕 z 90°）。

同一实例实测（hall01 filtered @1.0，`set_state 10 0 0 0 0 0 1`）：

| 时点 | `state_pos` | live_points |
|---|---|---:|
| 写前 | 2.359,1.432,0.045 | 231068 |
| 写后 | **10.000,0.000,0.000** | 231265 |
| +1 s | 10.276,0.026,−0.016 | 337887 |
| +4 s | 11.229,−0.010,−0.011 | 361450 |

除写回本身，这张表还说明一件事：**写回一个跳变位姿会让地图在新位置从零长起**
（231k → 361k points 全是新观测），所以写回是"声明的轨迹不连续"，不是无缝接管。

## 4. 边界

- 没有跑两事件；没有调门、没有调 σ、没有重跑检测或候选矩阵。
- 宿主 patch 只新增入口与开关，没有改现有估计/门语义；默认（不传
  `_native_checkpoint_dir`）时行为与之前完全一致。
- 双事件包保留在 `/tmp/fastlivo/hall01_two_event_v1.bag`，与宿主无关，换宿主可直接复用。
