# 实际修复测量缺口与最小接线方案

读者：S1 / 用户 / 审阅。本文只做代码对点与方案，**不开宿主运行、不实现、不调参**。
行号以当前工作树为准：驱动 `slam_recovery` = wt-sim `6f85e20`；宿主 =
`/home/R26534/fast_livo2_ws/src/FAST-LIVO2`（上游 `0d2c034` + `deployed_host.diff`）。

## 0. 结论摘要

1. 受控接纳 run 里 `repair_received=0 / repair_applied=0` 的直接原因是**驱动从不发布修复扫描**：
   本仓库只有独立的 `slam_recovery/ros/inject_repaired_scan.py`，而 run 的启动配方里没有它。
2. `reprocess` 重放的是**宿主自己捕获的原始扫描组**；修复队列为空时 `applyRepairedScan`
   直接返回，宿主日志因此是 `repairs applied=0 queued=0`。
3. `candidate_source=host_poses` 的候选是**位姿**；换成 `icp_reregistration` 也只是单个刚体
   修正 `ΔT`（`reregister_segment` 只返回一个 pose）。两者都不是测量修复——而且纯位姿修正
   **不可能**产生一个不同的 body-frame 点云（见 §2），所以只把 ICP 点云"发布一下"不会改变估计。

## 1. 三条原因，逐条对到文件/函数/行

### 1.1 驱动没有 `/native_recovery/repaired_scan` 的 publisher

- `slam_recovery/ros/recovery_node.py:1754-1770`（`RosDriver.__init__`）：只有
  `_pub`（gate status）以及 `_sub_pose` / `_sub_scan`；全文件没有对修复话题的 `Publisher`。
- 唯一的 publisher 是 `slam_recovery/ros/inject_repaired_scan.py:60`（`rospy.Publisher`）与
  `:76`（`pub.publish(out)`）；它是一个**独立进程**，订阅 `/velodyne_points` 后把同一帧
  做刚性平移再发出去，`--out-topic` 默认 `/native_recovery/repaired_scan`。
- 受控整链的 `launch_pair.sh`（归档里有原件）只启动宿主与 recovery node，没有启动它。
- 宿主侧订阅在 `LIVMapper.cpp:320-321`；计数只在 `repaired_scan_cbk`（`:696-720`）和
  `applyRepairedScan`（`:756/795/862`）里增加。没有人发布 → 三个计数全为 0。

### 1.2 `reprocess` 重放的是宿主原始扫描

- `LIVMapper.cpp:918` `reprocessCheckpoint(bool apply_repairs, bool keep_buffer)`：
  先 `restoreCheckpoint()`（`:921`），再遍历 `replay_buffer_`（`:943` `LidarMeasures = replay_buffer_[i]`）。
- 缓冲区来自运行循环的捕获：`LIVMapper.cpp:1307-1318`
  （`replay_capture_` 为真时把 `LidarMeasures` 深拷贝后 `push_back`）。
- 重放循环里 `:956` `if (apply_repairs) applyRepairedScan(LidarMeasures);`。
- `applyRepairedScan` 的第一行就是 `if (repaired_clouds_.empty()) return false;`（`:728`）。
  队列空 → 返回 false → 该组按原始扫描重放。
- 所以 `reprocess #N ... repairs applied=0 queued=0`（受控 run 的 host.log 原行）是**代码路径的
  必然结果**，不是匹配规则失败。

### 1.3 `host_poses` 是位姿重放；ICP 路径也只产出位姿

- `recovery_node.py:1277`：`repaired = {kf: pose for kf, _ts, pose in ep.frames}`——候选就是
  宿主在隔离期自己发布的位姿。
- `:1283-1292`：只有 `candidate_source == "icp_reregistration"` 时才调用 `_icp_candidate`；
  否则 `repaired` 不变。
- `_icp_candidate`（`:1206-1252`）调用 `reregister_segment`（`repair/pose_reregistration.py:296`），
  后者对整段点云做**一次刚体拟合**，返回 `IcpResult.pose`（一个 4×4 的 `ΔT`），
  候选是 `poses = {k: delta @ inits[k]}`（`recovery_node.py:1225`）。**没有生成任何修复点云。**
- manager 侧 `CandidateMap` 只携带 `repaired_poses`（`core.py:304-320`）；
  `evaluate_and_commit_candidate`（`sim/transaction_manager_node.py:574`）用
  `T_k = repaired_poses[k]` 和**原始** `scan_buffer_body[k]` 计算留出 NIS（`:742-745`）。
  整条评分/提交链里没有"替换测量"这个动作。

## 2. 为什么"位姿修复"不能当"测量修复"

设第 k 帧原始 body 点云为 `p`，原位姿 `T_k`，修复后的位姿 `T'_k = ΔT · T_k`。
世界点从 `T_k p` 变成 `ΔT T_k p`。如果把修复后的世界点重新表达回**修复后位姿的 body 系**：

```
(T'_k)^{-1} · ΔT · T_k · p = (T_k^{-1} ΔT^{-1}) ΔT T_k p = p
```

也就是**原来的 body 点云**。宿主 `applyRepairedScan` 替换的 `meas.lidar` 正是这个 body 系的
原始测量（`LIVMapper.cpp:752-760`，随后由 `UndistortPcl` 用 IMU 位姿去畸变）。所以：

- 纯位姿修正 `ΔT` 没有可注入的"不同的 body 点云"；把原点云当修复发出去只会让
  `repair_received/applied` 变成非零，估计不变。
- 真正的测量修复必须**改变几何**：去动态点、纠正去畸变、修复已知损坏/外参错误、替换坏帧等。
  3d 冒烟里的注入是 z 平移（改变了几何），所以 `repair_applied=20/20` 有意义。
- 因此，`icp_reregistration` 即使把点云发布出来，也不是测量修复；这一点必须在任何
  `repair_applied>0` 的声明前说清楚。

## 3. 最小接线方案（前提：存在一个真正改变几何的修复生产者）

### 3.1 需要的产物

每个被接纳候选帧 k 需要两样东西：
1. 修复后的 **body-frame** `sensor_msgs/PointCloud2`（与原始 `/velodyne_points` 同布局：
   `x,y,z,intensity,time,ring`，见 `include/preprocess.h:68-80` 与
   `src/preprocess.cpp:345-352` 的 `pcl::fromROSMsg`）；
2. 该帧**原始扫描的 header stamp**（scan begin），不是位姿戳。

### 3.2 驱动侧改动（唯一必须改的一侧）

1. **保留扫描戳与原始消息**：`_on_scan`（`recovery_node.py:1792-1805`）现在只留
   `cloud_to_xyz` 后的 xyz；`_dispatch`/`on_pair`（`:1807-1810`、`:905`）丢掉了 `scan_ns`。
   需要把 `(scan_ns, msg)` 沿配对传递并按 kf 存入 episode。**必须是 scan stamp**：
   宿主的匹配规则是"组结束时间 `lio_time` 之前 0.2 s 内最大戳"（`LIVMapper.cpp:741-760`），
   用位姿戳（≈扫描结束）会落在 `t <= end` 之外。
2. **新增 publisher**：在 `RosDriver` 里加 `/native_recovery/repaired_scan`
   （`sensor_msgs/PointCloud2`），逐帧发布修复云，`header` 用原始 scan 的 header，
   `stamp` 不改。
3. **在 `reprocess` 之前完成发送并确认入队**：
   - 先发布 N 条；再用现有 `status` 命令轮询 ack 里的 `repair_received`
     （`LIVMapper.cpp:1040-1058` 的 `checkpointStatus()` 已包含它），直到
     `repair_received >= N` 或超时；
   - 只有确认后，才调用 `self.cp.reprocess()`。
   - 不确认直接发 `reprocess` 会有竞态：`reprocess` 由宿主在下一帧边界应用，而修复是 ROS
     topic，回调线程可能还没把云放进队列。
   - 这一步**不需要改宿主**：`status` 与 `repair_received` 都是已有的。
4. **顺序**：`hold`（已在段打开时发）→ 发布修复 + `status` 确认 → `reprocess`
   （重放时 `apply_repairs=true`）→ `set_state(ep.frames[-1][2])` → 在 `rearm` /
   `commit_closed` 时 `resume`。不要把 `set_state` 放到 `reprocess` 之前：`reprocess` 会先
   `restoreCheckpoint()` 再重估，之前写入的状态会被覆盖。
5. **记录**：把发布的 stamp 列表、`repair_received/applied/dropped/queued`、以及宿主
   `reprocess #N ... repairs applied=M` 行一起归档。

### 3.3 宿主侧：最小路径不需要改

- 话题、订阅（`:320`）、`repaired_scan_cbk`（`:696`）、匹配规则（`:741-800`）、
  重放钩子（`:956`）都已存在，3d 冒烟验证过 20/20（`docs/review_20261110_native_checkpoint/README.md` §3d）。
- **唯一的硬限制**：`repaired_clouds_` 上限 64 条（`LIVMapper.cpp:716-720`，超出时丢最旧并
  `repaired_dropped_++`）。候选帧 >64 时，若在 `reprocess` 前一次性发布，会被截断。
  受控 run 的候选是 23–41 帧，够用；更大的候选要么分批（重放开始前不能消费，做不到），
  要么把上限调大（宿主一行改动，**属接口改动，按任务规则不在本轮实现**）。

### 3.4 manager 侧：最小路径不需要改

- 门与提交只看位姿（`CandidateMap.repaired_poses`）；修复云是驱动/宿主的执行细节。
- 若要在提交记录里写明"哪些帧的测量被替换"，给 `CandidateMap` 加一个
  `repaired_scan_keys` 并写进 `candidates.jsonl` 的 sidecar 即可（可选，非必需）。

## 4. 现在哪一步会失败、需要谁改

| 步骤 | 现在 | 失败点 | 归属 |
|---|---|---|---|
| 产生修复云 | 不存在 | `reregister_segment` 只给 `ΔT`；没有几何修复生产者 | **算法/产品决定**（不是驱动 bug） |
| 保留 scan stamp + 原始云 | 不存在 | `_dispatch`/`on_pair` 丢 `scan_ns`；`_on_scan` 丢消息布局 | 驱动 |
| 发布修复 | 不存在 | 没有 publisher | 驱动 |
| 确认入队 | 不存在 | 直接发 `reprocess` 有竞态 | 驱动（用现有 `status`） |
| 重放应用 | 已存在 | 队列为空 → `applyRepairedScan` 返回 false | 不需要改 |
| 顺序 | `reprocess → set_state → resume` 已对 | 若把 `set_state` 提前会覆盖 | 驱动（保持现序） |
| 队列上限 | 64 条 | 大于 64 帧的候选会丢 | 宿主（可选，需批准） |

## 5. 预算与缺口（不实现）

- **驱动**：约 80–120 行 + 单测（pairer 元组、episode 存 scan stamp/消息、publisher、
  status 同步、顺序、归档字段）。
- **宿主**：0 行（最小路径）；队列上限从 64 调大属可选接口改动（约 1 行 + 重新构建/验证）。
- **manager**：0 行（可选记录字段约 10 行）。
- **新消息类型**：不需要，复用 `sensor_msgs/PointCloud2`。
- **新安装/调参/新 bag 运行**：本轮都不需要。
- **必须由用户/S1 先定的语义**：这次要验证的"测量修复"到底是什么（去动态点 / 去畸变纠错 /
  已知损坏修复）。没有这个决定，接线只能把原点云发一遍，`repair_applied>0` 会是计数而非效应。

## 6. 引用索引

| 位置 | 内容 |
|---|---|
| `recovery_node.py:1754-1770` | `RosDriver.__init__`：只有 status publisher、pose/scan subscriber |
| `recovery_node.py:1792-1805` / `:1807-1810` | `_on_scan` / `_dispatch`：scan stamp 被丢弃 |
| `recovery_node.py:1277` / `:1283-1292` | 候选 = episode 位姿；ICP 仅在指定 source 时调用 |
| `recovery_node.py:1206-1252` | `_icp_candidate`：返回位姿映射与 detail，无点云 |
| `repair/pose_reregistration.py:296-326` | `reregister_segment`：一个刚体 `ΔT` |
| `core.py:304-320` | `CandidateMap.repaired_poses`（只有位姿） |
| `sim/transaction_manager_node.py:574` / `:742-745` | 门用候选位姿 + 原始 `scan_buffer_body` 算留出 |
| `inject_repaired_scan.py:60,76` | 唯一修复发布者（独立进程，本轮未启动） |
| `LIVMapper.cpp:320-321` | 宿主订阅 `/native_recovery/repaired_scan` |
| `LIVMapper.cpp:696-720` | `repaired_scan_cbk`：预处理、入队、64 条上限 |
| `LIVMapper.cpp:726-800` | `applyRepairedScan`：组结束匹配 / span 匹配 |
| `LIVMapper.cpp:918` / `:943` / `:956` | `reprocessCheckpoint`：restore → 重放原始组 → 可选应用修复 |
| `LIVMapper.cpp:1040-1058` | `checkpointStatus()`：ack 暴露 `repair_received/applied/dropped/queued` |
| `LIVMapper.cpp:1307-1318` | 原始组的深拷贝捕获 |
| `include/preprocess.h:68-80`、`src/preprocess.cpp:345-352` | 修复云必须满足的 velodyne 点布局 |
