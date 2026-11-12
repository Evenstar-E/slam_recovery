# 四宿主第二事件（第一批）：MM-LINS / SC-PGO 与 FAST-LIO2

任务来源：`docs/NON_FASTLIVO2_SECOND_EVENT_TASK_20261112.md`（用户纠正：先各跑一次 MM-LINS、
FAST-LIO2、LIO-SAM、ORB-SLAM3 的第二事件，再回 FAST-LIVO2）。分工：S2 负责 MM-LINS 与
FAST-LIO2，S1 负责 LIO-SAM 与 ORB-SLAM3。本目录只收 S2 的两项。

## 0. 证据链（按运行）

库 sha 是宿主实际加载的 `liblaser_mapping.so`（receipt 的 `runtime_library_sha256`）；
可执行文件始终 `0d7e23de…`。"损坏声明"一列写该 run 是否注入、窗口与幅度。

| run | 驱动 sha | 库 sha | 损坏声明 | 关键证据 | 能 / 不能声称 |
|---|---|---|---|---|---|
| `020634Z_4148249` | `fb746ddd` | `0eacffe1` | 无 | Mode 2 accepted（3.1388→6.6937，Wilson .9220）；`reprocess` 命令被覆盖、无 `reprocess #`，set_state/resume 生效 | 能：接纳与 hold/resume；不能：地图重建、`commit_closed` |
| `022158Z_4156288` | `18d92a03` | `0eacffe1` | 无 | accepted（6.6761）；串行化后 `reprocess` 416 帧、`repairs applied=0`；rearm 放写 | 能：命令串行化；不能：测量修复 |
| `024337Z_4166038` | `18d92a03` | `0eacffe1` | 无 | 同实例两事件：接受 + 拒绝各一；两次 close/rearm/resume；2 行候选，终态 HEALTHY | 能：两事件整链；不能：第二次接纳、`commit_closed` |
| `044445Z_85628` | `f62dbd55` | `0eacffe1` | INJECTION +0.5 z，[276.208, 282.215) | incumbent 初值：ICP 修正 0.815 m，`ITERATION_LIMIT`，Wilson 0.2855 拒绝；无修复 | 能：偏差在独立位姿下可见；不能：接纳或修复 |
| `045238Z_92133` | `c144deb3` | `0eacffe1` | 同上 | 解耦 bias +0.40（容差内），accepted；发布 26、宿主收到 20、synced=false → 无 reprocess | 能：偏差估计；不能：传输完整性 |
| `045944Z_96435` | `1acb0b4d` | `0eacffe1` | 同上 | 分批 10/10/10/2，32/32 收到并应用；`repairs applied=32`，地图 22334/417461 | 能：测量修复进入重放；不能：干净 A/B（跨度不同） |
| `050645Z_102106` | `721b9f15` | `0eacffe1` | 同上 | dry-run 对照：0 条修复、529 帧、地图 20427；帧集/跨度与修复臂不同 | 能：对照管线可跑；不能：效应归因 |
| `051523Z_107073` / `051728Z_109595` | `6f90ad9e` | `0eacffe1` | 同上 | 冻结人口 23/23；重放 815 vs 692 帧；地图 24503 vs 21870 | 能：人口冻结；不能：跨度一致、地图归因 |
| `052437Z_114016` | `231b0ed2` | `0eacffe1` | 同上 | sham：23/23、shift 0；重放 686 vs 815；set_state 差 3 mm；地图 21744 vs 24503 | 能：修正唯一差别（set_state）；不能：跨度一致 |
| `053647Z_122935` / `053917Z_128272` | `cae046ec` | `f27d1730` | 同上 | 终止戳：end_stamp 逐位相同（280.281185627）；开段快照落于触发后 2.9/1.9 s，重放 34 vs 64 帧、应用 7 vs 12 | 能：终止戳正确；不能：起点一致 |
| `055727Z_148998` / `055931Z_151459` | `5877388c` | `9c0330be` | 同上（窗口从触发戳起） | 声明戳 hold/snapshot + 终止戳：snapshot stamp/frame 相同、重放区间逐位相同、124 帧、23/23、leftover 0；地图 17811/335054 vs 17316/328516；仅 shift −0.40 vs 0 | 能：测量是否修正改变重放结果；不能：真实修复收益（注入损坏） |
| `072902Z_207524` | `43c65a9d` | `c0833d9f` | 同上（窗口从触发戳起） | 后缀重推：`replayed_within_end=124 replayed_suffix=448`，重放 [276.282..295.292]，修复 23/23、地图 21257/379069；随后 `set_state` 把状态从边界 3.168 拉回候选末端 7.051（差 3.9 m），状态与地图不同步 | 能：后缀被重推、state/map 到达边界；不能：set_state 之后仍停在边界、持续接回完成 |

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
| `injection_repair_20261112/decoupled_bias/success_batched/REPORT.md` | 分批回执后修复云 32/32 送达并进入重放；`repairs applied=32`，地图 22334 voxels |
| `injection_repair_20261112/decoupled_bias/control_dryrun/REPORT.md` | dry-run 对照（同损坏、不发布）：0 条修复、重放 529 帧、地图 20427；帧集不同，效应未隔离 |
| `injection_repair_20261112/freeze_ab/REPORT.md` | 候选帧集冻结后的 A/B：人口 23/23、门一致、修复 23/23 vs 0/0；重放跨度仍差 5.3 s（发布+回执推迟 reprocess），停并报因 |
| `injection_repair_20261112/freeze_ab/sham/REPORT.md` | sham 对照（同发布、零修正）：23/23 synced、set_state 差 3 mm、逐帧 z 差 0.40 m；重放跨度仍差 4.33 s，非分批固定代价 |
| `host_change_terminal_stamp/BUILD.md` | 已批准的宿主改动：`reprocess` 终止戳；增量/完整 diff、构建日志、新库 sha `f27d1730…`（无关 vikit 测试链接失败已记录） |
| `injection_repair_20261112/freeze_ab/terminal_stamp/REPORT.md` | 终止戳 + 开段快照的一对：终止戳逐位一致生效；开段快照在积压下落于触发后 1.9–2.9 s，起点仍差 1 s，停并报因 |
| `host_change_deferred_stamp/BUILD.md` | 已批准宿主改动：hold/snapshot 声明戳（延迟到帧循环执行）+ 终止戳重放；增量/完整 diff、构建日志、新库 sha `9c0330be…` |
| `injection_repair_20261112/freeze_ab/deferred_pair/REPORT.md` | 干净 A/B：snapshot/重放区间逐位一致、124 帧、23/23 applied、leftover 0；仅 shift −0.40 vs 0，地图 17811 vs 17316 |
| `run_fastlio2_shared.sh` | 本项使用的运行脚本（可复算；内含共享执行注释） |
| `analyze_run_bag.py` | 从输出 bag 计算 E1/E2 位姿、间隔、步长、尾段的分析脚本 |

大型产物不入库，路径与 sha 写在各报告里；`analysis.json` 是可直接复核的结构化结果。
