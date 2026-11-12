# 四宿主第二事件矩阵：LIO-SAM（本机实际运行）

- 任务：`docs/NON_FASTLIVO2_SECOND_EVENT_TASK_20261112.md`（S1 2026-11-12 接收，先跑非 FAST-LIVO2 四宿主）
- 执行：S1 本机，2026-11-12 11:44–11:49
- 结论先说：**宿主自身双事件运行完成；LIO-SAM 在 E1 后约 60 s 发散，E2 窗口与尾段都处于失效状态，未恢复。**

## 1. 身份

| 项 | 值 |
|---|---|
| 宿主二进制 | `~/catkin_ws/devel/lib/lio_sam/lio_sam_imageProjection`（catkin_ws 既有构建；本轮未重编译） |
| 参数 | `~/LIO-SAM/config/params_mmlins.yaml`（`velodyne_points` / `imu_raw`） |
| 输入 | `/home/R26534/datasets/mmlins/campus_1(2)-003.bag` sha256 `1fb5d827696b193471de9d5bc636230705fec8514e749f7a82e4fef7ebdddea3`（405 s） |
| 播放 | `--clock -r 1.0 --duration 260`，bag 起点起；私有 ROS master（roslaunch 自己持有） |
| 运行记录 | `run_receipt.json`（play_wall 266 s，4 个 lio_sam 节点） |
| 输出 | 1120 条 `/lio_sam/mapping/odometry`、227 条回环标记；轨迹见 `trajectory.csv` |

## 2. E1/E2 声明（运行前落盘，全文见 `declaration.txt`）

E1 = [50,70] s，E2 = [190,210] s，尾段 210–260 s；判据：相邻位姿步长 >1 m 或断流 >0.5 s。

## 3. 实际结果（`window_stats.json` 可直接复算）

| 窗口 | n | 最大步长 | >1 m 步数 | 最大断流 | >0.5 s 断流 |
|---|---:|---:|---:|---:|---:|
| pre [0,50) | 250 | 0.304 m | 0 | 0.300 s | 0 |
| **E1 [50,70)** | 96 | 0.571 m | 0 | 0.400 s | 0 |
| middle [70,190) | 478 | 498.632 m | 85 | 3.201 s | 21 |
| **E2 [190,210)** | 55 | 535.019 m | 26 | 2.000 s | 9 |
| tail [210,260) | 240 | 526.630 m | 86 | 0.601 s | 1 |

- 首次 >1 m 单步：**130.1 s**；首次 >0.5 s 断流：**146.8 s**（bag 相对时刻）。
- 全程路径长度 44.6 km，终点 `(-661.75, -148.72, 625.95)` —— 轨迹已发散，尾段未回到可用的局部轨迹。
- 与既有离线结论一致：该序列约 120–140 s 点云骤降后 LIO-SAM 失效（旧 README 记 143.6 s 跳变）；本轮在连续双事件输入下复现，且 E2 与其后 50 s 均未恢复。

## 4. 分层状态

| 层 | 状态 | 依据 |
|---|---|---|
| 宿主原生多事件（E1→继续输入→E2→尾段） | **FAIL**（运行完成，宿主未存活） | 上表；E1 正常，130.1 s 起发散，E2/尾段持续跳跃 |
| slam_recovery 实际修复链 | **NOT_IMPLEMENTED** | 本仓库没有 LIO-SAM 的 checkpoint/restore/控制通道/修复注入接线；本轮未造 |

## 5. 复现

```bash
# 运行（本机）
/tmp/s1_lio_sam_run/run.sh <out_dir> "/home/R26534/datasets/mmlins/campus_1(2)-003.bag" 260 1.0
# 分析（需 ROS python）
source ~/mm/ros/setup.bash
~/mm/ros/bin/python windows.py <out_dir>/result.bag
```

注意：`run.sh` 让 roslaunch 自己持有 master。先单独起 roscore 会在本机触发
`RLException: run_id on parameter server does not match declared run_id`，节点起不来、
`result.bag` 为空；2026-11-12 前两次尝试即因此失败（记录在状态 §64 的更新里）。
