# 实际部署的宿主代码（受控整链 `fl_native_20261110T115717Z_3390402`）

本文件把"跑出受控整链的那份宿主二进制"绑定到源码、库、配置和输入。归档的 patch 是
`deployed_host.diff`，**不是** 本目录里更早的 `fastlivo2_worktree.diff`。

## 1. 为什么替换旧 patch

`fastlivo2_worktree.diff` 是 17:09 的快照（控制线程改造之前）。在它里面检索：

| 符号 | 旧 `fastlivo2_worktree.diff` | 新 `deployed_host.diff` |
|---|---:|---:|
| `controlThreadLoop` | 0 | 3 |
| `map_hold_`（hold / 停写图） | 0 | 10 |
| `resume` | 0 | 2 |
| `set_state` | 0 | 3 |
| `cloneTree`（深拷贝） | 0 | 4 |

旧 patch 里识别不到 hold/resume/控制线程/set_state，与真正跑过的代码不一致；已由新 patch 取代。
旧文件保留原样，仅作历史，不要再当部署原件使用。

## 2. patch 的生成方式

基准：上游 `0d2c034`（`[Docs] update FAST-LIVO2-Dataset download link.`）。宿主工作树在该提交上带未提交改动。

```
cd /home/R26534/fast_livo2_ws/src/FAST-LIVO2
git diff > tracked.diff                       # 10 个已跟踪文件
git diff --no-index /dev/null include/native_checkpoint.h  >> new.diff
git diff --no-index /dev/null src/native_checkpoint.cpp    >> new.diff
cat tracked.diff new.diff > deployed_host.diff
```

`deployed_host.diff` 共 1501 行，覆盖 10 个已跟踪文件 + 2 个新文件。

## 3. 可复现性验证（已做）

1. `git archive 0d2c034 | tar -x` 到干净的 `/tmp/host_pristine`，在空仓库里提交基线；
2. `git apply --check deployed_host.diff` 通过，`git apply` 成功，生成
   `include/native_checkpoint.h` 与 `src/native_checkpoint.cpp`；
3. `diff -r` 对比打了 patch 的树与宿主工作树：**所有已跟踪源码逐字节一致**。差异只有未跟踪的
   部署/运行文件（`config/*.yaml`、`launch/mapping_m2dgr.launch`、`Log/*` 输出），它们的 sha 在第 4 节。

## 4. 产物绑定（sha256）

### 4.1 源码与构建文件（patch 的输入）

| 文件 | sha256 |
|---|---|
| `CMakeLists.txt` | `54794236bffe41df615f6bb13aed1f88a5ef5b51b2ee7ebd6187caa26462cc69` |
| `include/IMU_Processing.h` | `07c0d3dae1a5ad3b9a5f2e96e3f34f35f53a9a18c04898633a74e082ac294823` |
| `include/LIVMapper.h` | `56d23a75645ba7c6e4de869ad5342355a78ab8bbe104e3161d9f973ef2d5ac0c` |
| `include/common_lib.h` | `353ce2a4005e3e782ba2b8629ebd202ee8eeb43b2f6d392280c334dbfb0fb18f` |
| `include/preprocess.h` | `b30eb70f5df05396e5b384d3b8bf693aa21481cf5c7ec6939ea988e8a3af72a2` |
| `src/IMU_Processing.cpp` | `65a7d4b951b054f6999b5c8f555a1681bf1f92178e6ad61b0f1138069bfe86e0` |
| `src/LIVMapper.cpp` | `1742c00deccc7d142e33f718391efa4db1d7ac235d45a31a78edb257728e2a2a` |
| `src/preprocess.cpp` | `13bcb72ddfb505fc6d861fe862d0d05736a121c7ea0984330d320ce360c061a8` |
| `src/vio.cpp` | `8e3e1b90ed3744a20cadc74b19ea88d3f51328da2eecbd7d3570fd87aa466083` |
| `src/voxel_map.cpp` | `6fa83d0bba6b78d9010032d22172fb0566189eab78a3560548dfff32d26d2040` |
| `include/native_checkpoint.h`（新） | `5c43aab26d891bcd0377dbcd1ce01662e04ab35893c2bca2eda8d665fd7c6d22` |
| `src/native_checkpoint.cpp`（新） | `5a11acd72040f7367d6a7e32f2fe4db19a4256562b46e36b15cf55ddb9bb47f7` |

### 4.2 部署产物与输入

| 物件 | 路径 | sha256 |
|---|---|---|
| 宿主二进制 | `/home/R26534/fast_livo2_ws/devel/lib/fast_livo/fastlivo_mapping` | `0d7e23de537fcaa9ae0a4feb86afd8f9bc867c064f30bbfc9d0fa6bc9a2af6c1` |
| 运行时库 | `/home/R26534/fast_livo2_ws/devel/lib/liblaser_mapping.so` | `0eacffe1017b9ccf4331ad4752cb0d336aaac4457d9f66ff056d66965cd35659` |
| 配置 `m2dgr.yaml` | `/home/R26534/FAST-LIVO2/config/m2dgr.yaml` | `47a1bfd9b6f453298a0aafb2bc0651a48647f0ff1cba2c0ddd6dc6459217fe93` |
| 配置 `camera_m2dgr.yaml` | `/home/R26534/FAST-LIVO2/config/camera_m2dgr.yaml` | `96867cf92efc6ebbcaf224de4d3d2a82baf03e5834bc4197dddaf964f7ad75d7` |
| launch（未跟踪） | `src/FAST-LIVO2/launch/mapping_m2dgr.launch` | `5f8735320503d4f1c9618de15b1bf7f1455c22b325d8acb341db86dc77966c5a` |
| 输入 bag | `/tmp/fastlivo/hall01_two_event_v1.bag` | `c3e905da6600d86c1ecc5dde5ff3cfceb33938b18960fe62bf2f06f43c059dec` |

二进制与库的 sha 与 run 目录 `receipt.json` 的 `inputs.host_binary_sha256` /
`inputs.runtime_library_sha256` **逐位一致**；两份配置与 `inputs.config_*_sha256` 一致；
bag 与 `inputs.bag_sha256` 一致。源码文件 mtime 均早于二进制（`LIVMapper.cpp` 19:56:24，
二进制构建 `build_ctrl2.log` 19:56:54），不存在"源码晚于构建"的错配。

## 5. 构建开关（实际生效值）

来自 `build/CMakeCache.txt` 与宿主启动时的 `[DETERMINISM]` 行：

| 开关 | 值 | 说明 |
|---|---|---|
| `NO_MP` | OFF | 保留 OpenMP 并行 |
| `DET_SYNC` | OFF | 轮询接收，阻塞接收关闭 |
| `TRACE_GROUP` | **ON** | 只写分组 trace 行到 `$TRACE_GROUP_FILE`；观测用，不改估计/门/地图语义 |
| 运行期 | `MP_EN with MP_PROC_NUM=4` | 来自 `[ INFO] [DETERMINISM] build: MP_EN with MP_PROC_NUM=4, omp_get_max_threads()=128` |

`TRACE_GROUP=ON` 会编译进 trace 写盘分支；本趟没有设置 `TRACE_GROUP_FILE`，因此没有 trace 文件产出。
它是本 run 的构建事实，写在这里以免"源码对了、开关没记"。

## 6. patch 内含的能力（供核对，不解释结果）

- **深拷贝**：`native_checkpoint.cpp` 的 `cloneTree` / `cloneMap` / `freeTree`；`VoxelOctoTree` 默认构造不给
  `plane_ptr_`、`leaves_[]` 初值，clone 显式写每个字段。
- **快照/恢复/重放**：`LIVMapper::snapshotCheckpoint`、`restoreCheckpoint`、`reprocessCheckpoint`；
  跨帧 IMU 值经 `ImuProcess::get/setCheckpointState` 存取。
- **停写图**：`map_hold_` 在 `handleLIO` 的 `UpdateVoxelMap` 之前分叉；held 时只计数 `held_frames_` / `held_points_`。
- **控制线程**：`startControlThread` / `controlThreadLoop` / `applyPendingControlCommand`；线程只读命令目录、
  立即写 `ack_received`，把命令放进待应用槽；主循环在每帧开始处应用并写 `OK <cmd> ...`。
- **修复通道**：`repaired_scan_cbk` / `applyRepairedScan`，按时间戳把修复扫描并入重放组。
- **状态写回**：`set_state`（7 个数：x y z qx qy qz qw）。
- **重放捕获**：`replay_capture_` 分支在捕获 `LidarMeasureGroup` 时**深拷贝**三朵点云（共享指针会让重放帧没有点）。

## 7. 不在 patch 里的部署文件

`config/m2dgr.yaml`、`config/camera_m2dgr.yaml`、`config/m2dgr_noimg.yaml`、`config/m2dgr_vio10.yaml`、
`launch/mapping_m2dgr.launch` 在宿主仓库里是未跟踪文件，不进入 `deployed_host.diff`；前三个是实际部署物，
按第 4.2 节的 sha 绑定。
