# 四宿主第二事件矩阵：ORB-SLAM3（本机实际运行）

- 任务：`docs/NON_FASTLIVO2_SECOND_EVENT_TASK_20261112.md`
- 执行：S1 本机，2026-11-12 11:51–11:57（wall 374 s）
- 结论先说：**宿主自身双事件运行完成；ORB-SLAM3 全程未能维持跟踪——351 s 内 80 次地图初始化，
  E2 窗口内仍在重建（6 次），尾段 3 次，最终 Atlas 只剩 1 张 0 关键帧的地图，收尾 exit 139。**

## 1. 身份

| 项 | 值 |
|---|---|
| 二进制 | `~/ORB_SLAM3/Examples/Monocular-Inertial/mono_inertial_euroc` sha256 `5efa7ff1221f9c70770f333e149f9826c2f49138069d11a9c4dff1d7eaf3a0e5` |
| 配置 | `Examples/Monocular-Inertial/Hall01_color_imu.yaml` sha256 `26cde907…` |
| 输入 | `/tmp/orb_hall01`（M2DGR hall_01 全序列彩色 TUM + EuRoC IMU，5229 帧，351.65 s） |
| 模式 | 单目惯性，无头（不设 `ORB_USE_VIEWER`） |
| 记录 | `run_receipt.json`；原始 stdout `orb.log`（2681 行） |

## 2. E1/E2 声明（运行前落盘，全文见 `declaration.txt`）

E1 = [190,220) s，E2 = [300,330) s，尾段 [330,351] s。选择依据是既有 59 s 结果（该序列后段才
初始化成功），属先验，不是本轮结果。判据：窗口内是否处于跟踪、是否 lost/重定位/新建地图。

## 3. 实际结果（`init_events.json`，由 `mnFirstFrameId` 精确映射到 times.txt）

| 窗口 | 地图初始化次数 |
|---|---:|
| 0–190 s（含 E1 前） | 43 |
| **E1 [190,220)** | 4 |
| 220–300 s | 24 |
| **E2 [300,330)** | 6 |
| 尾段 [330,351] | 3 |

- 共 **80** 次 "New Map created"、465 次 Local Mapping reset、385 次 "Not enough motion"、43 次
  "Reset map because local mapper set the bad imu flag"；最后一次初始化在 t=346.98 s。
- 结束时日志自报 `There are 1 maps in the atlas / Map 0 has 0 KFs`，随后 `exit=139`（SIGSEGV，收尾崩溃）。
- 本 run 没有产出可用轨迹文件；E1/E2 处都不是"跟踪中遇到事件"，而是**尚未稳定跟踪**。

## 4. 分层状态

| 层 | 状态 | 依据 |
|---|---|---|
| 宿主原生多事件（E1→继续输入→E2→尾段） | **FAIL**（运行完成，宿主未建立稳定地图） | 上表；80 次重建、最终 0 关键帧、exit 139 |
| slam_recovery 实际修复链 | **NOT_IMPLEMENTED** | 本仓库无 ORB-SLAM3 接线；本轮未造 |

## 5. 与既有结果的关系

既有 `~/orb_slam3_results` 的 59 s 轨迹是**截取后段**得到的局部可用结果；本轮跑完整序列并保留
全部失败，不与之矛盾：那 59 s 只是初始化成功后的短暂区间，前后仍反复重建。

## 6. 复现

```bash
# 运行（本机）
/tmp/s1_orb_run/run.sh <out_dir>
# 解析（把 mnFirstFrameId 映射到 times.txt）
python3 analyze_orb.py <out_dir>/orb.log
```
