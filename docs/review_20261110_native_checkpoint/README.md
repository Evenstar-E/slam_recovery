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
| 重放 | 8 帧经宿主 `handleLIO` 重新估计并写回 map，0.358 s。**该 PASS 已被 §2b 的重复实验取代**（当时未记录逐帧点数） | **SUPERSEDED** |
| 修复测量注入 | 未实现：宿主只吃自己预处理出的点云 | **NOT_IMPLEMENTED** |
| 隔离期间地图停写 | 未实现：host 仍在每帧 `UpdateVoxelMap` | **NOT_IMPLEMENTED** |

耗时说明：ack 延迟含宿主 20 ms 轮询间隔，是拷贝本体的**上界**；2 s 滚动周期下开销可忽略。
产物：`/tmp/s2_native_checkpoint/{host_smoke.log,smoke_results.json,fastlivo2_worktree.diff,native_checkpoint.h,native_checkpoint.cpp}`。

## 2b. 对上面那条"重放 PASS"的复核（浅拷贝修复之后）

§3g 发现捕获是浅拷贝之前，"8 帧重放 PASS"没有记录**逐帧点数**——而这正是空跑与真跑的分界。
深拷贝修好后用同一条 `smoke_checkpoint.sh` 重跑：

| 项 | 实测 |
|---|---|
| 重放帧数 | 8（**LIO 4 帧 + VIO 4 帧**） |
| LIO 帧中有点云的 | **4 / 4**（empty=0） |
| 去畸变点总数 | 143780 |
| 重放前地图（restore #2 之后） | 10281 voxels / 202023 points |
| 重放后地图 | **10484 voxels / 206751 points**（+203 / +4728） |
| 重放耗时 | §2 记录 0.358 s；本轮未单独计时 |

结论要精确，不能一刀切：

- **旧的 8 帧 PASS 不是空跑**——当时地图确实从 10734 增到 11284 voxels，说明帧里有被处理的点；
- **但它是未经验证的**：当时没有逐帧点数，而浅拷贝 bug 已在同一条路径上被证明存在（§3g 的 control 一个顶点都没写）；
- 因此 §2 那条 **标记为 SUPERSEDED**，由本节的重复实验替代，数字不悄悄改。

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

## 3g. 重放保真度：先修一个真 bug，再谈修复效应

**撤回上一轮 `repair_effect_measured = PASS`。** 照 S1 要求先量保真度，量出来的第一件事是：
control 重放终态 **−12.644**，而同刻 live 是 **6.49** —— 差 19 m，**重放根本不保真**，14 m 不能算注入效应。

根因找到了，而且是个真 bug：捕获进 `replay_buffer_` 的 `LidarMeasureGroup` **共享点云指针**，
而宿主在 live 处理时**原地改这些点云**（`swap`、`clear`、把点搬进下一帧）。于是重放时帧里没有点，
`handleLIO` 直接走 "No point!!!" 早退——**control 那趟一个顶点都没写**（地图停在 checkpoint 的
9400 不变，就是这个症状）。修复超时看不见它，因为那时点云被换成了修复点云。

修法：捕获时**深拷贝** `lidar` / `pcl_proc_cur` / `pcl_proc_next`。

修好后的保真度（同一时间戳 = 重放末帧 `1627785284.679`）：

| 项 | state_pos |
|---|---|
| 宿主 live（restore 之前，同一时刻） | 6.604361, 9.140322, 0.114888 |
| control 重放（无注入） | 6.594110, 9.154173, 0.185198 |
| treatment 重放（20 帧注入） | 6.608602, 9.176204, 0.173547 |

- `|control − live|` = **7.3 cm**（亚分米，重放可信）；
- `|treatment − control|` = **2.9 cm**（20/426 帧被 +1.0 m 平移，效应小是对的——估计器对逐帧做平均）。

**所以：14.23 m 是浅拷贝造成的假象，已撤回；真实修复效应量级是厘米。**

## 3g2. 匹配规则最终版（20/20，0 残留）

之前 9–12/20 的根因也定位了：用"从 `lio_time` 反推的 begin + 20 ms 窗"匹配，误差几毫秒就漏。
换成**按组结束时间匹配**：修复扫描的组结束于 `begin + duration`，取"戳最大且不晚于本组结束、
且相差 ≤0.2 s"的那条。实测 **applied=20，leftover=0**。

残留分类也做了：修复前 `had_group_but_missed=11, no_group_nearby=0` —— **每条残留修复都有对应的组**，
所以不是"没组"，是匹配精度问题；换规则后残留归零。

## 3g_old. 进程内对照（上一轮，读数已被 3g 取代）

命令 `reprocess_control` = restore + 重放**但不注入修复**，且**保留缓冲帧**；随后 `reprocess`
对**同一批帧**再放一遍。两条轨迹的起点（同一 checkpoint）、帧数（426）、区间
（`1627785267.006 .. 1627785281.214`）都相同，control 侧 `applied=0` 是构造保证。

| 项 | control（无修复） | treatment（12 帧注入） | 差 |
|---|---:|---:|---:|
| state_pos | −12.644, −1.496, −1.116 | 1.587, 0.667, 0.002 | **14.23 m (x)** |
| voxels | 9400 | 15965 | +6565 |
| points | 189173 | 235542 | +46369 |

**这条读数说明替换路径确实到达估计器并可测**；但注入的是**故意错误的 +1.0 m 刚体平移**，
所以 14 m 是**破坏效应，不是修复收益**。不能把它当修复效果报。

## 3h. dropped 分类（回应"先分类再猜"）

20 条发布的修复里 **全部落在重放区间内部**：早于 checkpoint 0 条、晚于重放末帧 0 条、
区间内 20 条。所以"S1 预期大部分落在 checkpoint 之前"这条**不成立**——窗口是对齐的。

现在的未确定项只剩一句话：**重放区间内、有 8 条修复没有找到可替换的帧**。
（control 那趟不清队列，treatment 因此拿到全部 20 条，命中 12 条，比上一轮的 10 条多 2。）

## 3i. 两个计数器到底是什么（回应语义质疑）

- `native_merged_scans_ += merged_scans`，`merged_scans` 是 `sync_packages` 的 LIVO 分支里
  `while (!lid_raw_data_buffer.empty())` 循环的**迭代次数**，即"本次组装进这一组的扫描条数"；
- `native_multi_scan_groups_++` 仅当 `merged_scans > 1`。

所以 217–230 = **整趟被并进各组的扫描总数**，`multi_scan_groups = 0` = **没有任何一组合并 ≥2 条**——
两者并不矛盾：217 条扫描分散在 217 个各自只并 1 条的组里。但这两个计数是**整趟累计**，不是
按重放窗口统计；用它们排除"合并假设"只在本窗口有效。

## 3j. 重放路径与 live 路径**不完全一致**（必须写明的差异）

"7.3 cm"是**保真**，不是**复现**。已知差异：

1. **累积舍入与线程**：宿主是 `MP_EN`（OpenMP 4 线程）构建，同一输入不保证 bit-exact 归约顺序；
2. **重放时的地图已含 live 期间的全部观测**（restore 只回到 checkpoint，之后 live 又处理的部分在回滚时被丢弃，重放走的是同一条确定性路径，但地图的插入顺序与 live 不完全相同）；
3. **IMU 预处理只恢复四个跨帧量**（`last_imu`、`last_prop_end_time`、`acc_s_last`、`angvel_last`），`IMUpose` 只用于输出、不参与传播；若将来把 `IMUpose` 接入估计，这项差异会变化；
4. **VIO 组不重放点云**：重放里的 VIO 帧没有 lidar（构造如此），视觉后续只在 live 上发生——本报告不声称重放了视觉。

因此本文件一律写"保真 7.3 cm"，不写"完全复现"。

## 3k. 同实例两事件运行：E1 走到终态，**E2 未触发**（状态机断点）

输入 `hall01_two_event_v1.bag`（`c3e905da…`，E1 在 +14.6 s、E2 在 +42…52 s），
rate 1.0、drain 30、σ=0.884、`--candidate-source host_poses`、`--wait-limit-sec 10`，墙钟 102.7 s。
run `/tmp/fl_native_20261110T104511Z_3336818`，host 与 recovery node 同 pgid `3337883`。

| 项 | 实测 |
|---|---|
| host binary / runtime lib | `26a9f2e6…` / 见 receipt |
| pose / scan | 817 / 598 |
| 配对 | 542（扫描侧 90.6%） |
| **E1 trigger** | 1627785263.808（bag **+2.7 s**，远早于真实注入 +14.6 s） |
| **E1 决策** | 1627785265.874（trigger +2.07 s） |
| Mode / 结果 | `MODE3_SOFT_BRIDGE_WAIT`，拒绝（候选为空，22 个 key 进 deferred） |
| 原生动作 | `snapshot×3`（frame 19：7422 voxels/140114 points）→ `hold` → **`restore #1`：live 8776 → 7422 voxels** |
| 决策后继续消费 | 498 帧 |
| **E2** | **未触发** |
| 最终状态 | `WAITING_FOR_EVIDENCE`，quarantine 仍开，`lifecycle.events = []` |

### 断点（不在我这边，报给 S1）

`maybe_close_waiting_segment()` 的**唯一调用点在 `step_frame`**（`transaction_manager_node.py:250`）。
隔离期间帧走的是 `_ingest_without_detection()`，它在 `state != HEALTHY` 时**直接**
`register_quarantined_frame` 并 `return`，**不经过 `step_frame`**。于是：

- 等待上限这一条根本不会被求值 → `wait_limit_closed` / `rearm` 永不发生；
- 而隔离期间 NIS 又因为参考停在冻结的地图上而大面积 `UNAVAILABLE`（本次 `fed_to_step_frame=5`，
  其余 537 帧 UNAVAILABLE），所以 `step_frame` 也不会因为别的路径被调用；
- 结果：段永远开着，**E2 结构上不可能触发**。

这是**状态机断点**，不是本次运行的偶发。按三类归属，本次属于 **"仅接线"**：E1 的原生 hold/restore
真的执行了（地图 8776→7422 回滚），但**第二事件没有发生**，不能算完整流程。

## 3l. 两事件重跑：等待上限与重武装生效，**E2 仍未触发**（下一个断点在检测可用性）

S1 修好调用图后（`e3a60e7`）用同一套参数重跑。run `/tmp/fl_native_20261110T105118Z_3341023`，
pgid `3342097`，wall 104.9 s，peak RSS 721 MB，binary `26a9f2e6…`。

| 项 | 实测 |
|---|---|
| pose / scan；配对 | 471 / 598；312（扫描侧 52.2%） |
| E1 trigger / 决策 | 1627785263.808（bag **+2.7 s**，假警报）/ 1627785265.674（+1.87 s），`MODE3_SOFT_BRIDGE_WAIT` 拒绝 |
| 原生动作 | `hold` → `restore #1` → **`resume`**（全部 ack OK）；滚动快照 38 次 |
| `lifecycle.events` | **`wait_limit_closed`**（closed 1627785275.681，即 bag +14.6 s，正是真实注入起点）+ **`rearm`** |
| 未决帧 | **143** 帧（`unresolved_segments=1`），终态 `HEALTHY` |
| 重武装后帧数 | 169 帧，全部 `UNAVAILABLE` |
| 重武装后地图 | 0 → **108501 points / 169 kfs**（地图确实在长） |
| 重武装后 NIS | 0.43 – **164.01**，中位 16.86（真实注入窗口的 NIS 很大） |
| 重武装后参考来源 | **prev_scan ×169，node_map ×0** |
| E2 | **未触发** |

### 断点在哪一步（不是终态，是路径）

1. 等待上限求值 → **通过**（`wait_limit_closed`）；
2. `rearm` → **通过**（事件出现，native `resume` 已 ack）；
3. 检测重武装 → `detector.reset()`，状态回 `HEALTHY` → **通过**；
4. **之后没有任何一帧进入检测器**：`fed_to_step_frame` 全程停在 **5**。原因不是没 P 值（NIS 一路算到 164），
   而是参考**永远是 `prev_scan`**，`reference_node_map` 全程 **5 次**，于是 `supported=false`，
   帧被记为 UNAVAILABLE 并走 `step_healthy`。

**这是一次回归，不是旧有状态**：同一 bag、同一 σ 的早期 hall 运行 `054559Z` 是
`reference_node_map=397 / AVAILABLE=440`。现在变成 `5 / 5`。变化发生在宿主侧移植（hold/restore/
深拷贝/修复通道）与驱动侧 checkpoint 接线之间；**具体是哪一个尚未定位**，我没有把它写成"已知原因"。

按三类归属：**仍是"仅接线"**——E1 的原生 hold/restore/resume 全执行了、等待上限与重武装也真的发生了，
但第二事件没有开出来。

## 3m. 定位：回归从哪一帧开始（同 kf 对照）

早期 `054559Z` vs 本次 `105118Z`，同 kf 21–40：

| kf | 早期：status / ref / nis / kfs / pts | 本次：status / ref / nis / kfs / pts |
|---|---|---|
| 21 | AVAILABLE / prev_scan / 0.22 / 1 / 923 | AVAILABLE / node_map / 13.41 / 1 / 926 |
| 25 | AVAILABLE / prev_scan / 0.14 / 5 / 923 | AVAILABLE / node_map / 14.40 / 5 / 926 |
| **26** | AVAILABLE / node_map / 0.85 / **5** / **3237** | UNAVAILABLE / prev_scan / 0.19 / **0** / **0** |
| 27–40 | AVAILABLE / node_map / ~1.0 / 7 / 3237→4071 | UNAVAILABLE / prev_scan / ~0.2 / **0** / **0** |

**分叉点就是 kf 26**：本次运行在这一帧 `trusted_poses` 从 5 个变成 **0 个**、`support_reference()`
长度从 926 变成 **0**，此后整趟再没恢复（直到 rearm 后地图重建）。参考长度一旦为 0，
`_frame_has_reference_support` 恒 False，匹配只能退回 `prev_scan`，`fed_to_step_frame` 就此停在 5。

清空发生在**隔离开启那一刻**：`trigger_quarantine`（`manager.py:156`）按
`t_q_start = 估计 onset − 裕度` 回滚 `promoted_history`，而本次 `t_q_start` 落在几乎全部已提升帧
之后，于是把它们全部撤销；早期运行的脏触发落在帧序更晚的位置，回滚没扫到已建的地图。
**"恢复哪一个 checkpoint / 回滚窗口是否该覆盖全部已提升帧"是下一步要定的**，我没有改。

### 宿主输出的变化（回答第 1 问）

| 项 | 早期 054559Z | 本次 105118Z |
|---|---:|---:|
| host.log 中 `Update Voxel Map` | 780 | **408** |
| LIO 有效特征数（末帧） | 15027 | **426** |
| 平均残差 | 0.051 | **0.113** |
| 发布位姿数 | 777 | **471** |
| 配对 | 515 | **312** |

408 vs 780 里有 185 帧是 hold 期间被挡下的写入，剩下是真实下降；**有效特征 15027 → 426、残差
0.051 → 0.113** 说明 restore 之后宿主是在一张与当前位姿不再对齐的地图上匹配——这正是"声明过的
轨迹不连续"的代价，不是发布链路本身坏了。

**逐帧扫描点数**：两趟都没有归档这个字段（`frame_diagnostics` 只记
`map_points`/`trusted_keyframes`），所以现在给不出，要么加字段、要么不报——我没有为了补数去跑新实验。

### 配对 312 vs 515（第 2 问）

位姿数 471 vs 777 已经解释了大半（配对上限就是位姿数），剩下的差来自本次 `max_backlog=282`：
主循环每 2 s 要等一次快照 ack，期间配对队列在堆。**快照没有丢弃消息**（`scan_messages` 两趟都是 598），
但它确实降低了主循环的推进速度。

## 3n. 段身份修复后：五段全部走完决策→关闭→rearm，**E2 仍不可达**

`466f1a3` 之后同一套参数（`--wait-limit-sec 2.0`）重跑。run
`/tmp/fl_native_20261110T110616Z_3349738`，pgid `3350818`，wall 154.3 s，
wiring **all_ok**（含修好的 `same_process_group`），receipt status OK。

| episode | trigger(bag s) | decision(bag s) | 关闭+rearm |
|---|---:|---:|---|
| 0 | 2.61 | 4.67 | 6.81 |
| 1 | 8.07 | 10.27 | 13.42 |
| 2 | 13.82 | 16.68 | 22.35 |
| 3 | 23.35 | 25.55 | 30.23 |
| 4 | 30.43 | 32.76 | 38.36 |

- **五段都有 episode、都有决策**（全部 `MODE3_SOFT_BRIDGE_WAIT` 拒绝，共 51 个 key 进 deferred），
  每段都 2 s 后关闭并 `rearm`；原生侧 `hold → restore → resume` ×5 全 ack；
  终态 **HEALTHY**、无遗留隔离段。
- rearm → 第一帧 AVAILABLE：**0.80 / 0.00 / 0.80 / 0.13 s**，第 5 次 **从未恢复**。

### E2 仍不可达，断点在这里

`+42…52 s` 的 E2 窗口共 **87 帧，全部 UNAVAILABLE**（参考 `prev_scan`），检测器状态 HEALTHY——
帧被 `step_healthy` 吞进地图，但**没有一帧被判定**，所以 E2 不可能触发。

同一时刻地图仍在长（kf 69 → 110 → 148，points 40414 → 90809），所以不是"地图没建起来"，
而是**当前位姿与参考云不满足 3 m / 60% 的支持条件**。

宿主侧也还在跟踪但质量下降：有效特征从 16000–20000 掉到 **2719–3011**，残差 0.028 → 0.100–0.117。
五次 restore 每次都把宿主位姿拉回约 2 s，累计约 10 s，宿主在同一个区域反复重走，
它的地图与位姿已经不再是一条一致轨迹。

**这就是 S1 预判的结构性情形**：恢复链需要一个"隔离期不让宿主地图过期"的机制，
或者一个 rearm 后的支持恢复条件；两者都是设计决定。按指令停在这里，不改代码、不改参数。

另记一条小观察：本轮有 **2 次滚动快照 ack 超时**（`snapshot ack_timeout`），都发生在 restore
密集的时段；它不影响任何决策，但说明快照与重放会在主循环上撞车。

## 4. 边界

- 没有跑两事件；没有调门、没有调 σ、没有重跑检测或候选矩阵。
- 宿主 patch 只新增入口与开关，没有改现有估计/门语义；默认（不传
  `_native_checkpoint_dir`）时行为与之前完全一致。
- 双事件包保留在 `/tmp/fastlivo/hall01_two_event_v1.bag`，与宿主无关，换宿主可直接复用。
