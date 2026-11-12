# ORB-SLAM3 原生 FAIL 的同口径只读分析

日期：2026-11-13。范围：只读既有 run 原件（`docs/review_20261112_four_host/orb_slam3/` 与
`/tmp/s1_orb_run/`）与 `/home/R26534/ORB_SLAM3` 源码，不构建、不运行。

## 1. 结论

- ORB-SLAM3 这次 FAIL 的性质是**单目惯性初始化无法稳定**，不是"跟踪途中被事件打断"：
  351.65 s 内 **80 次** `New Map created`、**385 次** `Not enough motion for initializing. Reseting...`、
  **43 次** `Reset map because local mapper set the bad imu flag`；最后一次初始化在 t=346.98 s。
- 结束时自报 `There are 1 maps in the atlas / Map 0 has 0 KFs`，随后 `exit=139`（SIGSEGV，收尾崩溃）。
- 因此 E1（190–220 s）/E2（300–330 s）窗口内都不是"稳定跟踪中遇到第二事件"，而是**还在反复重建**；
  这个 run 不构成"宿主原生双事件"的证据，只能作为"宿主在该输入下不可用"的基线。

## 2. 证据

### 2.1 运行身份（README §1）

| 项 | 值 |
|---|---|
| 二进制 | `~/ORB_SLAM3/Examples/Monocular-Inertial/mono_inertial_euroc`，sha `5efa7ff1…` |
| 配置 | `Examples/Monocular-Inertial/Hall01_color_imu.yaml`，sha `26cde907…` |
| 输入 | `/tmp/orb_hall01`（TUM 彩色 + EuRoC IMU，5229 帧，351.65 s） |
| 模式 | 单目惯性、无头 |

### 2.2 初始化时间线（`init_events.json`）

| 窗口 | 新地图次数 |
|---|---:|
| 0–190 s | 43 |
| E1 [190,220) | 4 |
| 220–300 s | 24 |
| E2 [300,330) | 6 |
| 尾段 [330,351] | 3 |

- 首次初始化 t=11.35 s，此后平均约每 4.4 s 重建一次；最后三次在 t=315.69 / 329.51 / 338.58 s。
- 日志原文（`orb.log:56-62`）：`New Map created with 239 points` → `Not enough motion for initializing.
  Reseting...` → `LM: Reseting current map ...` 循环。

### 2.3 失败机制

- `Not enough motion`（385 次）是 ORB-SLAM3 单目初始化的**视差不足判据**：该序列（走廊、
  近乎平动/低视差）反复不满足两视图几何初始化条件。
- `bad imu flag`（43 次）说明初始化后 IMU 一致性检查也经常失败，本地建图被重置。
- 两项叠加 → 永远不会形成稳定关键帧，最终 Atlas 只剩 1 张空图。

## 3. 与恢复层的关系（重要差异）

- **它不是一个 ROS 话题节点**：`mono_inertial_euroc.cc` 用 `LoadImages` 从磁盘逐帧读、
  调 `System::TrackMonocular(im, t, vImuMeas)`（`Examples/Monocular-Inertial/mono_inertial_euroc.cc:35,89,198`）。
  因此**没有话题级测量注入点**（与 LIO-SAM/FAST-LIO2 不同）。
- 但它**有官方 Atlas 存取接口**：`System::SaveAtlas(int type)` / `LoadAtlas(int type)`
  （`include/System.h:203-204`，配置项 `System.SaveAtlasToFile`/`LoadAtlasFromFile`，
  `src/System.cc:83-98`），以及 `ActivateLocalizationMode/DeactivateLocalizationMode`
  （`include/System.h:125,127`）。这是四宿主里**唯一现成的"快照/恢复/纯定位"API**。
- 状态对象：`Atlas::GetAllMaps()`（`include/Atlas.h:108`）返回全部 Map（含 KeyFrames/MapPoints）。

## 4. 三列结论

| 能做什么 | 不能做什么 | 需要宿主改什么 |
|---|---|---|
| 用 `SaveAtlas/LoadAtlas` 做**整图快照与恢复**（官方 API，四宿主中最省力） | 无话题注入点：输入是磁盘图像序列，无法像 LIO-SAM 那样用 relay 替换单帧 | 一个"读取帧序列 + 在指定帧暂停/快照/恢复"的 runner（改造 `mono_inertial_euroc.cc`，~80 行） |
| `ActivateLocalizationMode` 可做"只定位不建图"的保护态 | 初始化不稳定：低视差输入下 80 次重建，任何恢复策略都会被"重建"覆盖 | 初始化门控（在未稳定前不进入恢复判定），需与主线门定义对齐 |
| Atlas 多地图结构天然对应"多事件/多段" | 退出路径 SIGSEGV（exit 139），收尾不可靠 | 修复/绕开收尾崩溃（需定位，本次未做） |

## 5. 风险

1. **输入不适用**：该序列低视差导致单目惯性初始化失败；若主线要求 ORB-SLAM3 的恢复证据，
   需要换有足够视差的序列，否则任何结论都是"输入不适合"，不是恢复层结论。
2. **无话题级注入**：测量修复只能通过改 runner/System 调用层实现，成本高于 LIO-SAM。
3. **收尾崩溃**：`exit=139` 会污染"保存轨迹/Atlas"的证据链，需单独处理。

## 6. 未确认项（需构建/运行）

- `SaveAtlas/LoadAtlas` 在本版本的实际可用性（`type=1` 文本格式的兼容性）；
- `exit 139` 的调用栈位置；
- 换高视差序列后初始化是否稳定。

## 7. 文件

`docs/review_20261112_four_host/orb_slam3/{README.md,orb.log,init_events.json,declaration.txt}`、
`/home/R26534/ORB_SLAM3/{include/System.h,include/Atlas.h,Examples/Monocular-Inertial/mono_inertial_euroc.cc}`。
