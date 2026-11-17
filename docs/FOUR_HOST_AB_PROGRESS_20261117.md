# 四宿主 A/B 进度表（2026-11-17，按宿主绑定）

**用途**：满足 `docs/HOST_VALIDATION_ORDER_20261113.md` §4.1 的第 1 项——按宿主、A/B 行绑定记录
「实际 source/run、已验证组件、未实现接口、失败、未知、最小下一任务及负责人」。

**口径**：本表**不是新评分**。评分基线仍是 `7fc67cf` 的 **A 16/36、B 11/36**（单宿主原型），
未重评、未升档。下表用证据状态而非阶段分；只有已核原件才写 V/P，否则写 U。审阅 `423fee0` 明确：
本轮修复属工程保障，`A4/A6/A9/B2/B11` 未因此闭合，不做全表新评分。

**状态码**：`V`=本宿主原生证据满足该行冻结条件；`P`=有原生 run 或局部实现，未闭合；
`F`=原生运行失败/不可用；`N`=slam_recovery 未接线/未实现；`U`=未取证（未知）。

## 1. 宿主总表

| 宿主 | 实际拓扑 | 原生两事件 | 恢复层接线 | 当前硬阻断 |
|---|---|---|---|---|
| MM-LINS / SC-PGO | FAST-LIO 前端 + `alaserPGO` 两节点（`run_mmlins.sh:49-56`） | **P**：一次整段 run，双事件与尾段（`review_20261112_four_host/mmlins_campus12_20261112/REPORT.md`） | **N** | 两进程无单一状态所有者；无 replay buffer；无测量级修复入口 |
| FAST-LIO2 | 单节点 | **P**：前端单独 run，两次 `Issleeping/Isbuilding`，尾段 239.3 s | **P**：命令/检查点/回滚已验证（本线 11 次 run） | accepted 修复未达成；检测未在线 |
| LIO-SAM | 单节点（5 模块同进程） | **F**：130.3 s 起发散（点云 26k→203），E2/尾段失效 | **N** | 前端在输入退化下发散；恢复接线未做 |
| ORB-SLAM3 | 离线 runner + System | **F**：80 次初始化、末图 0 KF、exit 139 | **N** | 低视差初始化不成立；无话题注入面 |

## 2. A 轴（工程闭合）

| 行 | MM-LINS | FAST-LIO2 | LIO-SAM | ORB-SLAM3 | 说明与原件 |
|---|---|---|---|---|---|
| A1 输入与身份 | P | P | P | P | 四宿主均有 bag/config/binary sha；MM-LINS 的构建溯源缺口（二进制 mtime 早于 HEAD）见其 REPORT；ORB 为离线帧序列 |
| A2 原生执行与运行身份 | P | P | P | P | FAST-LIO2 receipts 最全（每 run 的 binary/lib sha、ack）；LIO/ORB 有 run_receipt |
| A3 在线检测与起点估计 | N | N | N | N | 本线 run 均 `--detection off` 或脚本触发；ALI-H 检测指标 `NOT_EVALUABLE` |
| A4 完整可信检查点 | N | P | N | N（有 Atlas API） | FAST-LIO2：hold/snapshot/restore 实测，范围为 `STATE_AND_MAP_ROLLBACK_ONLY`，`p_imu` 预积分未入检查点（replay `PARTIAL`） |
| A5 隔离与帧归宿 | N | P | N | N | FAST-LIO2 有段/延迟键计数；v9i 存在 `unresolved=2` |
| A6 历史重处理与重建 | N | P | N | N | FAST-LIO2 reprocess/replay 路径存在（smoke `replay_suffix=0`；run 中 `PARTIAL`）；四宿主均无完整重建证据 |
| A7 独立证据准入 | N | P | N | N | 门与 paired evidence 有实现；accepted 未达成 |
| A8 原子提交 | N | P | N | N | 回滚/restore 已验证；原子提交分支未跑通 |
| A9 多事件撤销与重武装 | P（宿主原生双休眠重建） | P（两事件生命周期、rearm） | N | N | 均为宿主/驱动行为，不是修复提交的可撤销历史 |
| A10 接回后持续运行 | P | P | F | F | MM-LINS/FAST-LIO2 接回后继续消费到尾段；LIO-SAM/ORB 原生失效 |
| A11 共同集合与同步评测 | U | P | U | U | FAST-LIO2 有 paired/holdout 与运行摘要；未见四宿主统一共同集合评价 |
| A12 复现封装与预算 | P | P | P | P | 均有脚本/receipt；依赖本机私有路径，未做干净环境复现 |

## 3. B 轴（论文证据）

| 行 | MM-LINS | FAST-LIO2 | LIO-SAM | ORB-SLAM3 | 说明 |
|---|---|---|---|---|---|
| B1 失效问题与保护必要性 | P | P | P | P | 四宿主都实际出现了失效/退化；事件定义与污染时序未冻结 |
| B2 保护正确性 | N | P | N | N | 仅 FAST-LIO2 有 rollback/restore 与负结果；事务缺陷已有局部修复 |
| B3 检测能力 | U | U | U | U | ALI-H 资格-only 收口，检测指标 `NOT_EVALUABLE` |
| B4 修复净收益 | N | F | F | F | FAST-LIO2：11 次 run 未获 accepted，无净收益；LIO/ORB 原生失效 |
| B5 门增量价值 | N | P | N | N | 有拒绝与仿真对照；无同候选流的无条件 vs 门控真实比较 |
| B6 机制因果 | N | P | N | N | 注入 run 提供了部分机制证据，但未分离各因素 |
| B7 正常代价/有害风险 | N | P | N | N | 自然事件的安全拒绝已多次复现；误干预统计未做 |
| B8 重复与不确定性 | U | P | U | U | FAST-LIO2 有多次同事件 run 的波动记录；无冻结重复方案 |
| B9 未参与环境泛化 | N | P（限定） | N | N | v9i 是另一序列的限定 paired-benefit，未 accepted |
| B10 公平完整基线 | U | U | U | U | 未建立同条件四臂比较 |
| B11 同一原生在线链与成本 | N | P | N | N | FAST-LIO2 链闭合但无 accepted；端到端成本已测（FIM 热点） |
| B12 独立复现 | U | U | U | U | 无可移植发布包与干净环境复现 |

## 4. 每宿主最小下一任务

| 宿主 | 最小下一任务 | 前置/阻断 | 负责人 |
|---|---|---|---|
| FAST-LIO2 | 整理 option ③ 收口包（见 `docs/four_host/fastlio_recovery_20261113/FASTLIO2_OPTION3_CLOSURE_PACKAGE_20261117.md`）；不再开 run | 无 | S1 |
| MM-LINS | 重新写接口计划：两节点命令通道 + 联合 hold/snapshot/restore + 输入缓冲；先做 hold/snapshot/restore/resume 单项冒烟，再做两事件 | 跨进程原子性；前端无 replay；测量级修复需改宿主算法（需用户批准） | S1（无 S2/S3 会话） |
| LIO-SAM | 先把事件窗口移到 130 s 之前（0–120 s 无发散段），或在同一 bag 上确认前端发散的可复现边界；恢复接线随后 | 输入退化（120–140 s 点数 26k→203）非恢复层可修 | S1 |
| ORB-SLAM3 | 换一条视差足够的序列验证“能稳定跟踪”，否则两事件无从谈起 | 低视差初始化失败、exit 139；离线读盘无话题注入面 | S1 |

## 5. 本表不声称

- 不声称四宿主任一整体验收完成；不声称 FAST-LIVO2 可启动（四宿主未全过）。
- 不把 `P` 当通过、不把测试数量或一次 HEALTHY 当验收；`U` 项不能由本表推断为已具备。
- 不新增阶段分：A/B 总分仍是 `7fc67cf` 的 16/36 与 11/36，直到全部行按新证据重评。
