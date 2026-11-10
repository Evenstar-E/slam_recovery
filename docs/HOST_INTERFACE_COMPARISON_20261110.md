# 宿主接口对照与选择（2026-11-10，S1）

依据：审阅侧 `05f7fc5`（[HOST_SELECTION_HANDOFF](HOST_SELECTION_HANDOFF_20261110.md)），按**真实接口事实**在既有宿主中选择，不按历史数值或投入时间。事实来源：S2 在 FAST-LIVO2 的实测（`docs/review_20261110_native_checkpoint/README.md`）与 S1 对 MM-LINS/FAST-LIO 源码的核查。只比较支撑"checkpoint→重处理→内部状态/地图写回→接回→重武装"的接口。

## 1. 事实表

| 宿主 / source | 可恢复的真实状态 / checkpoint | 测量重处理调用点 | 内部地图更新 / 撤销 / 提交 | 接回与重武装 | 现有环境与最小新增工作 |
|---|---|---|---|---|---|
| **FAST-LIVO2** `fast_livo2_ws/src/FAST-LIVO2`（`0d2c034`+patch） | **已有实测**：`snapshotCheckpoint`/`restoreCheckpoint`（`LIVMapper.cpp:679/700`）深拷贝体素 octo 地图（10734 voxels / 21349 nodes / **210 985 points**，ack 0.086 s）+ `_state`/`state_propagat`/IMU 四值；回滚逐值相同 **PASS** | `sync_packages`→`processImu`(`ImuProcess::Process2`/`UndistortPcl`)→`stateEstimationAndMapping`→`handleLIO`；`reprocessCheckpoint` 已用 8 帧走通宿主自身链路（0.358 s）**PASS** | `UpdateVoxelMap`（`voxel_map.cpp:609`）按帧插入；**无按扫描归属/撤销**，只能整图快照；`clearMemOutOfMap` 是空间箱体清理 | 宿主无隔离概念，**隔离期仍写图**；Python 侧 `rearm` 已有（S1 `a1a371d`），宿主侧无钩子 | 环境就绪、有运行 receipts；最小缺口：①隔离期停写图（`handleLIO` 门控，约 5 行）②修复测量注入（`processImu` 前替换 `pcl_proc_cur`，约 40 行）③接纳后状态写回 ④视觉地图 checkpoint（**仅 LIVO 模式需要**；m2dgr 配置的 LIO 主路径不读它） |
| **MM-LINS / FAST-LIO** `MM-LINS/FAST-LIO`（软链进 `mmlins_ws/src`，已构建） | **无现成 checkpoint**，但组件齐全：`esekfom::esekf` 的 `get_x/get_P/change_x/change_P`（状态与协方差直接读写），`imu_buffer`/`lidar_buffer` 原始消息保留 | `sync_packages`→`UndistortPcl`→`h_share_model`；重放需要另行接出，**未验证** | ikd-Tree：`flatten`/`Build`/`Add_Points`/`Delete_Point_Boxes`；同样**无按扫描撤销** | 主循环持续消费；已有退化触发休眠（`Issleeping`）与重建（`Isbuilding`），`re_slam()` 重置 esekf/IMU/ikd-Tree = 原生**硬重武装**；`isPublish=false` 时跳过 `map_incremental` = **原生写图门控** | 环境就绪、M2DGR 配置在；最小新增：实现 checkpoint/restore/重放并验证（组件现成但未跑通）+ 修复测量注入 |
| **FAST-LIO2** | 与 MM-LINS 的 FAST-LIO 同源（ikd-Tree + IKFoM），本机没有独立于 MM-LINS 的 FAST-LIO2 工作区；不单列 | — | — | — | 不新增安装/适配 |

## 2. 选择：**继续在 FAST-LIVO2（LIO 主路径）上做第一个两事件验证**

理由只用上表事实：

1. **它是唯一已有实测 checkpoint/restore/reprocess 的宿主**：整图回滚逐值相同（210 985 点）、重放 8 帧走宿主自身 `handleLIO`。MM-LINS 的三块组件虽然齐全，但**没有一条被跑通**；选择它意味着先把同样的三件事重新实现并验证一遍，新增工作更多，不是更少。
2. **LIVO 的"最大一块"不适用**：视觉地图/光度标定只在 LIVO 模式被读取；m2dgr 配置下主路径是 LIO，缺的不是视觉 checkpoint。
3. **剩余缺口是可枚举的小项**（4 项，其中 3 项与本选择相关），且第一项本身就是正确性前提：隔离期宿主仍在写图，回滚后污染帧会立刻被合并回来——不修，恢复只在回滚瞬间成立。
4. MM-LINS 的原生优势（`flatten/Build`、`re_slam`）不缩短到**已验证两事件**的路径，且其 `re_slam()` 是"清空重建"，不是"回到可信快照"。

**边界**：这是本轮的宿主选择，不是"FAST-LIVO2 全面更好"；若第 1 项（停写图）或第 2 项（修复注入）在本预算内失败，按 `HOST_SELECTION_HANDOFF` §3 重新比较，不延长绑定。

## 3. 第一处断点与责任

| 项 | 内容 | 责任 |
|---|---|---|
| 第一断点 | **隔离期停写图**：`LIVMapper::handleLIO` 中 `UpdateVoxelMap` 需要受一个显式标志控制，且 `sync_packages` 前的消费要按标志决定丢弃/缓存；否则 restore 之后污染帧立即回到地图 | S2 实现（约 5 行 + 标志位），S1 核 |
| 第二断点 | 修复测量注入：`processImu` 之前替换 `pcl_proc_cur` 的 `PointCloudXYZI::Ptr`（按时间戳匹配 repaired-scan 话题） | S2 实现，需与 S1 的候选/修复产物接口对齐 |
| 第三断点 | 接纳后的状态写回：`_state` 与体素地图按修复结果更新，而不仅是"不 restore" | S2 实现；S1 提供写回语义 |
| Python 侧 | 等待上限/rearm 已有（`a1a371d`）；`CheckpointClient` 的拒绝→restore、接纳→reprocess 已接 | S1 已交付 |

## 4. 本轮不做的

- 不跑两事件（等前三项接通）；不调门/σ/参数；不新增宿主安装；不动 FAST-LIVO2 历史数据；不把 MM-LINS 从候选里删除（下次工作区变化时重核）。
