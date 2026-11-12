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

## 8. v3 更新（2026-11-12）：终止戳与声明戳 hold/snapshot

本节把本文件绑定到当前部署，不改前 1–7 节的历史内容；v1/v2 的原件与 sha 保留。

### 8.1 版本链

| 版本 | 完整 patch | 行数 / sha256 | 运行时库 sha256 | 可执行文件 sha256 |
|---|---|---|---:|---|
| v1（2026-11-10） | `deployed_host.diff` | 1501 行 / 见文件 | `0eacffe1017b…65659` | `0d7e23de…af6c1` |
| v2（终止戳） | `../review_20261112_four_host/host_change_terminal_stamp/deployed_host_v2.diff` | 1528 行 / `2ffc5f6e…59a0` | `f27d1730927e…79d0c` | `0d7e23de…af6c1` |
| v3（声明戳 hold/snapshot） | `../review_20261112_four_host/host_change_deferred_stamp/deployed_host_v3.diff` | 1627 行 / `46648b4c…ab28` | `9c0330be…00db` | `0d7e23de…af6c1` |
| v4（后缀重推） | `../review_20261112_four_host/host_change_suffix_replay/deployed_host_v4.diff` | 1625 行 / `f025329c…bc22` | `c0833d9f…dfe0` | `0d7e23de…af6c1` |
| **v5（当前，ack 暴露 replay_suffix）** | `../review_20261112_four_host/host_change_replay_suffix_ack/deployed_host_v5.diff` | **1632 行 / `e444adac…eab9`** | **`9e7d8cdf…3b0a`** | `0d7e23de…af6c1` |

增量 patch（都在上一版树上 `git apply --check` 通过）：

| 增量 | 相对 | 行数 / sha256 |
|---|---|---:|
| `host_change_terminal_stamp/terminal_stamp_increment.diff` | v1 | 87 行 / `4419d401…2530` |
| `host_change_deferred_stamp/deferred_increment.diff` | v2 | 203 行 / `adc61753…4be8` |
| `host_change_suffix_replay/suffix_increment.diff` | v3 | 67 行 / `e234a12c…88d2` |
| `host_change_replay_suffix_ack/ack_increment.diff` | v4 | 49 行 / `4c8aedf2…d824` |

**可执行文件未变、库变了**：`fastlivo_mapping` 一直动态链接 `liblaser_mapping.so`，宿主的行为在库
里。每次运行的 receipt 以 `/proc/<pid>/maps` 解析实际加载的库并哈希，所以 run 身份应看
`runtime_library_sha256`，不能只看可执行文件 sha。053647Z/053917Z 绑定 `f27d1730…`，
055727Z/055931Z 绑定 `9c0330be…`。

### 8.2 v2/v3 的能力增量

- **v2（终止戳）**：`reprocess` payload 可带终止戳（ns），重放只处理组结束 ≤ 该戳的条目；
  日志新增 `replayed=… truncated=… end_stamp=…`；空 payload 保持旧行为。
- **v3（声明戳 hold/snapshot）**：`hold`/`snapshot` payload 可带应用戳；控制线程只入队并回
  `OK <cmd> deferred stamp=…`，主循环在第一个带 lidar 测量的组的 `lio_time ≥ 戳` 时、处理该组
  之前执行（先 hold 后 snapshot）；不带戳保持立即语义。执行分支重构为
  `executeControlCommand`，主循环每帧调用 `applyDeferredControlCommands`；`late_ms` 以毫秒记录。
  控制线程仍不碰地图、状态或 LIO。

### 8.2b v4（后缀重推）

`reprocessCheckpoint` 不再用终止戳截断重放本身；终止戳只限制修复云匹配，决策后捕获的后缀组
用原始测量按顺序重推。日志分列 `replayed_within_end / replayed_suffix`。见
`../review_20261112_four_host/host_change_suffix_replay/BUILD.md`（新库 `c0833d9f…`）。

### 8.2c v5（ack 暴露 replay_suffix）

`checkpointStatus()` 新增 `replay_within_end/replay_suffix`（取自上一次重放，不新算）；驱动在
`suffix>0` 时跳过 `set_state`，避免把状态回拨到候选末端。见
`../review_20261112_four_host/host_change_replay_suffix_ack/BUILD.md`（新库 `9e7d8cdf…`）。

### 8.3 构建记录

`host_change_terminal_stamp/BUILD.md`、`host_change_deferred_stamp/BUILD.md` 记录命令
（`catkin_make -j8`）、日志与复现检查。两次构建的退出码都是 1，但**宿主目标已成功**：
`Built target laser_mapping`（91%）；失败在无关的 `rpg_vikit` 测试可执行文件
`test_vk_common_patch_score`——`/usr/bin/ld: /home/R26534/mm/ros/lib/libIlmThread.so.32:
undefined reference to __cxa_call_terminate@CXXABI_1.3.15`（mm ROS 库的 ABI 不匹配），
`fastlivo_mapping`/`liblaser_mapping.so` 不受影响。

### 8.4 复现验证（已做）

- v3 完整 patch 在干净 `0d2c034` 树上 `git apply --check` 通过；
- 两份增量在各自上一版树上 `git apply --check` 通过；
- `strings liblaser_mapping.so | grep 'deferred apply'` 命中，v3 库确含新代码。

## 9. 版本链 v1 → v5（每版解决什么、仍缺什么）

同一上游 `0d2c034`，五版宿主 patch 依次叠加；可执行文件始终 `0d7e23de…`，行为在
`liblaser_mapping.so`，run 身份看 receipt 的 `runtime_library_sha256`。

| 版本 | 完整 patch（行数 / sha256） | 库 sha256 | 解决的断点 | 当时仍缺 |
|---|---|---|---|---|
| **v1** | `deployed_host.diff`（1501 / `b12ae153…`） | `0eacffe1…` | 宿主原生 checkpoint/restore/replay、停写图、修复扫描通道、`set_state`、地图深拷贝 | 控制轮询与 LIO 共槽（ack 饿死）；`reprocess`/`set_state` 连发被覆盖；重放无终止边界 |
| **v2** | `../review_20261112_four_host/host_change_terminal_stamp/deployed_host_v2.diff`（1528 / `2ffc5f6e…`） | `f27d1730…` | `reprocess <end_stamp>`：重放只处理组结束 ≤ 戳的条目 | 被截断的已消费后缀不再重推；开段快照/滚动快照的时刻受宿主积压影响 |
| **v3** | `../review_20261112_four_host/host_change_deferred_stamp/deployed_host_v3.diff`（1627 / `46648b4c…`） | `9c0330be…` | `hold`/`snapshot` 带应用戳，控制线程入队、主循环在第一个带 lio 的组处理前执行 | 后缀仍未重推；`set_state` 会把状态写回候选末端 |
| **v4** | `../review_20261112_four_host/host_change_suffix_replay/deployed_host_v4.diff`（1625 / `f025329c…`） | `c0833d9f…` | 重放覆盖全部捕获组：终止戳只限制修复云匹配，后缀用原始测量按序重推，日志分列 `replayed_within_end / replayed_suffix` | `set_state` 在重放到达边界后仍回拨状态（实测 3.9 m / 15 s） |
| **v5** | `../review_20261112_four_host/host_change_replay_suffix_ack/deployed_host_v5.diff`（1632 / `e444adac…`） | `9e7d8cdf…` | `checkpointStatus()` 暴露 `replay_within_end / replay_suffix`；驱动据此在后缀 >0 时跳过 `set_state` | 驱动侧另有：每戳武装 checkpoint、开段作废 pending snapshot、scripted run 关滚动快照（不在宿主 diff 里） |

**驱动侧的收尾（不在这五个 patch 内）**：`_open_episode` 先 `expire_pending(0.0)` 再发 hold；
`main()` 为每个 scripted 戳预排 `hold/snapshot`；scripted run 关闭滚动快照；`reprocess` 的终止
戳 = `frozen_at_ns + REPLAY_END_GRACE_NS`（100 ms，声明常量）；收到 `replay_suffix>0` 时跳过
`set_state` 并记 `native_writeback_skipped`。

各版构建记录在对应的 `BUILD.md`；宿主目标每次都在 91% 处 `Built target laser_mapping`，构建
退出码 1 只来自无关的 `test_vk_common_patch_score`（`libIlmThread` 的 `__cxa_call_terminate@
CXXABI_1.3.15`）。
