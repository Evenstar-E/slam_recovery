# 四宿主第二事件（第一批）：MM-LINS / SC-PGO 与 FAST-LIO2

任务来源：`docs/NON_FASTLIVO2_SECOND_EVENT_TASK_20261112.md`（用户纠正：先各跑一次 MM-LINS、
FAST-LIO2、LIO-SAM、ORB-SLAM3 的第二事件，再回 FAST-LIVO2）。分工：S2 负责 MM-LINS 与
FAST-LIO2，S1 负责 LIO-SAM 与 ORB-SLAM3。本目录只收 S2 的两项。

## 状态

| 宿主 | 实际运行 | 宿主原生双事件 | slam_recovery 修复链 | 报告 |
|---|---|---|---|---|
| MM-LINS / SC-PGO | **1 次**（campus_12_fl，469 s 整段） | **PASS**：E1/E2 都发生，前端两次休眠重建、PGO 保持全局图；尾段 227–239 s | **NOT_IMPLEMENTED**（无接线） | `mmlins_campus12_20261112/REPORT.md` |
| FAST-LIO2 | **1 次**（同一 bag、同一时间线，前端单独跑） | **PASS**：E1/E2 都发生，`Issleeping`/`Isbuilding` 各 2 次；尾段 239.3 s | **NOT_IMPLEMENTED**（无接线） | `fastlio2_shared_campus12_20261112/REPORT.md` |

FAST-LIO2 必须标 **SHARED_EXECUTION**：本机只有一个 `fastlio_mapping`
（`mmlins_ws/devel/lib/fast_lio/`，sha `59674a8f…`），它同时是 MM-LINS 的前端；没有独立构建。
这一项验证的是"共享前端单独运行时的原生双事件"，不能算独立 FAST-LIO2 实现验证。独立构建缺口
已写在它的报告第 2 节。

## 共同输入与事件

| 项 | 值 |
|---|---|
| bag | `/home/R26534/datasets/mmlins/campus_12_fl.bag`，sha `a924b5f9…`，469.4 s，首个 IMU 戳 `1711547883362267771` |
| E1 | `1711547999352267771`（+115.99 s） |
| E2 | `1711548113452267771`（+230.09 s） |
| 事件性质 | `DECLARED_OBSERVATION`：campus_12 的两个自然休眠（历史 manifest 的 `sleep_trigger_sec`），不是注入 |
| 独立佐证 | `/imu_raw` 低运动窗 109–143 s、224–261 s，两个声明戳都在窗内 |

两戳按"留够尾段"选：E2 之后 bag 还有 239 s；没有按结果好坏挑宿主或事件。

## 环境事实

- 两个宿主共用 `mmlins_ws`；ROS 使用 `~/mm/ros` 自带的 roscore（每次私有端口）。
- MM-LINS run 的启动阶段（约 60 s）与另一项 MM-LINS 运行重叠（pid 开始于 11:33:11，
  `campus_1(2)-003.bag`，`--duration 260`）。它在 E1（bag +116 s）之前已结束，**两个事件窗口内
  没有其它宿主运行**。runner 的固定 `/tmp/mm_*.log` 会被并发写，所以本归档不使用那些日志，
  只使用唯一的 runner 日志与输出 bag。
- 观测到 loadavg：启动阶段约 140，事件窗口约 80（128 核）。
- FAST-LIO2 项运行期间没有其它宿主运行。

## 限制（按任务第 4 节的自检口径）

- 两项都只有**宿主原生层**证据；`slam_recovery` 修复/事务层没有任何接线，均标 `NOT_IMPLEMENTED`。
- 没有 GT，不给轨迹质量数字；E1/E2 处的位置只是记录值。
- `/path` 话题在两个 bag 里都用墙钟 header（全相同），不能用于事件对齐；分析只使用
  `/Odometry` 与 `/aft_pgo_odom`（MM-LINS）或 `/Odometry`（FAST-LIO2）。
- 事件是自然休眠，不是注入故障；结果不能外推到"任意第二个故障"。

## 文件

| 路径 | 内容 |
|---|---|
| `mmlins_campus12_20261112/REPORT.md` | MM-LINS 的运行、身份、事件、原生表现、尾段、限制 |
| `mmlins_campus12_20261112/{run.log,analysis.json,events.json,run_mmlins.sh}` | 原件副本与事件声明 |
| `fastlio2_shared_campus12_20261112/REPORT.md` | FAST-LIO2（SHARED_EXECUTION）同上 |
| `fastlio2_shared_campus12_20261112/{run.log,fastlio_node.log,record.log,analysis.json,events.json}` | 原件副本 |
| `REPAIR_GAP.md` | `repair_received/applied=0` 的逐条代码对点与最小接线方案（无新运行） |
| `injection_repair_20261112/REPORT.md` | INJECTION 测量修复的一次受控运行：传输链成立（25/25/25），估计偏差 0.003 m 而非注入的 0.5 m，原因与最小修法 |
| `injection_repair_20261112/incumbent_init_refused/REPORT.md` | incumbent 初值第二次尝试：修正放大到 0.815 m（偏差可见），ICP 未收敛、候选被 Wilson 0.2855 拒绝，修复未发布 |
| `injection_repair_20261112/decoupled_bias/REPORT.md` | 解耦偏差估计第三次尝试：bias +0.40 m（容差内）、门 accepted；宿主订阅队列 20 条，26 条发布丢 6 条，屏障拒绝重放 |
| `run_fastlio2_shared.sh` | 本项使用的运行脚本（可复算；内含共享执行注释） |
| `analyze_run_bag.py` | 从输出 bag 计算 E1/E2 位姿、间隔、步长、尾段的分析脚本 |

大型产物不入库，路径与 sha 写在各报告里；`analysis.json` 是可直接复核的结构化结果。
