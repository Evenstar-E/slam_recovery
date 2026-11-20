# 项目状态总结（2026-11-20）

**主线目标（未变）**：一次整链运行——原生恢复写回 → 接回输入 → 第二事件。
**一句话结论**：**三个宿主的恢复生命周期已经能跑通，但没有任何一次出现 accepted 写回；**
断点已从「接口/PGO 存活」推进到「没有能过门的真实测量候选」。ORB-SLAM3 卡在数据。

本文件只汇总**有原件可核**的结论；每条细节的出处见文末索引。评分基线仍是 `7fc67cf` 的
A 16/36、B 11/36，但按 2026-11-17 审阅日报的口径，**当前状态不引用旧总分作为成绩**，它只是冻结基线。

## 1. 四宿主现状

| 宿主 | 恢复接线 | 两事件生命周期 | 写回（accepted） | 当前硬断点 |
|---|---|---|---|---|
| **MM-LINS**（FAST-LIO + SC-PGO） | 已接线并实测 | **PASS 两次**（v1–v4 迭代后：v4 两事件均处理，PGO 全程存活） | **0** | 候选过不了门（详见 §3） |
| **FAST-LIO2** | 已接线并实测（11 次 run） | PASS（v9f/v9g/v9i/v9j） | **0** | 门的信息增益与 holdout NIS；option ③ 已收口 |
| **LIO-SAM** | 已接线（单进程通道 + iSAM2 快照/重建） | **PASS 两次**（2026-11-17 首次 run） | **0** | 候选过不了门；检查点 stamp 修正未复验 |
| **ORB-SLAM3** | 未接线 | FAIL（80 次重建、0 关键帧、exit 139） | — | **缺带相机且视差足够的序列** |

## 2. 已经真正做到的事（有原件）

### MM-LINS（最完整的一条）
- 前端换成 FAST-LIO2 v9 原生恢复通道（补丁后与原 v9 文件 sha 一致），新增跨进程 `pgo_hold` 标记：
  前端 hold 时写、PGO 见标记即冻结关键帧插入；**门阈值、ICP、估计器、关键帧间距均未改**。
- v4（0.5×、监护参数按 bag 等价换算）：两事件 `hold→snapshot→restore→resume` 全部 `valid=1`；
  **E1 检查点首次 `AT_OR_BEFORE_BOUNDARY`（早 1.17 ms）**；E2 晚 0.200 s；
  PGO 全程存活（`/aft_pgo_odom` 7921 条到录制终点），空休眠图守卫**实际触发 819 次**；
  driver `terminal_reason=None`，尾段存在。
- 修复了一个真实崩溃：v2 的 `alaserPGO` SIGABRT（ScanContext 空描述子断言）→ 定位到
  `act_change()` 不检查空地图 + `performSimilarClosure()` 不检查休眠图 → 修法 A 跳过空图并打印告警。

### LIO-SAM
- 单文件接线（+254/−3，补丁存档）：hold 只停关键帧与图写入、继续跟踪发布；
  snapshot 复制位姿/关键帧云/iSAM2 因子与估计；restore 用全图 `update()` 重建。
- 首次 run（bag 118 s @0.5×，事件放 40/80 s，**刻意避开 120–140 s 已知输入退化窗**）：
  两事件全部 ack `valid=1`，`/lio_sam/mapping/odometry` 589 条覆盖 0–117.6 s、无断流。
- 诚实声明：`reprocess=NO`、`measurement_relay=NO`、`native_reset_under_hold=not_applicable`，
  因此该 run **未启用 `--require-contract`**（契约不通过这一事实写进了 `pre_run.txt`）。

### FAST-LIO2
- 11 次 run 覆盖自然事件、注入事件、逐帧候选、运动先验候选；收口包写明「当前实现/协议下未获得 accepted」，
  不写「宿主不可达」。

## 3. 为什么都过不了门（已归因，不是接线问题）

门的判定是**有序**的：① 配对收益（每帧改善 ≥5%，Wilson ≥0.55）→ ② 重入跳跃 → ③ 弱方向信息
（≥max(3, 2J_before)）→ ④ holdout NIS ≤2.5 → ⑤ 后验协方差。**①不过直接返回，④不成为判定腿。**

| run | E1 | E2 |
|---|---|---|
| MM-LINS v1 (1.0×) | ①通过 12/13；卡 ③ 1.012、④ 1393 | ①通过 21/21；卡 ③ 1.74、④ 53.1 |
| MM-LINS v2/v4 (0.5×) | 卡 ① **0/12**、**5/13** | 卡 ① **0/15**、**0/11** |
| LIO-SAM v1 | 卡 ① 1/11；info 20.20→**19.80**（负增益） | 卡 ① 0/11；info 18.92→**17.59** |

**根因**：候选源是 `host_poses`（宿主自己的位姿），而 MM-LINS 的两次事件落在近静止窗
（0.02–0.03 m/s），常速度外推与宿主位姿几乎重合（v4 E1 残差 499.5 vs 502.2），没有可赚的几何信息。
另一层：holdout NIS 493.6 换算残差约 2.7 m，说明隔离段扫描对不上事件前的 trusted map
（宿主在事件处自建了局部图）。

**结构性前提**：候选必须来自「隔离段扫描 → trusted map」的配准，而不是复用宿主位姿。这是下一步的
方法选择（AGENTS §2.3：需用户批准）。

## 4. 负结果与已撤回的结论（保留，不重写历史）

- 撤回「0.5 m 重入是唯一绑定约束」与「与真实运动结构互斥」——实际规则是 `jump ≤ 0.5 + 2.0·Δt`。
- 撤回把 v1 的配对通过（12/13、21/21）当作科学收益——它与「检查点晚 0.223 s/9.71 s、污染进入 incumbent」同现。
- v2 的 PGO 崩溃**仍未定位根因**（无栈回溯、单次未复现）；修法 A 只是让同类路径不再断言。
- 仿真侧：五案例全部 `MODE3_SOFT_BRIDGE_WAIT`、`simulator_validity=FAILED`，旧 R5 Mode2 数值已撤回。
- ALI-H：C2/C3 BLOCKED、C4 `NOT_EVALUABLE`；不得报检测指标或净收益。

## 5. 未闭合项与下一步（均需用户授权）

1. **候选方法**：用「隔离段扫描 → trusted map」的配准候选替代 `host_poses`（MM-LINS）。需要先声明冻结常数。
2. **LIO-SAM 检查点 stamp 修正未复验**：新二进制 `e9373b30…`，需一次 run 确认 `AT_OR_BEFORE_BOUNDARY`。
3. **ORB-SLAM3**：`datasets/mmlins/*` 的 8 个 bag **无相机话题**；`M2DGR/raw/` 中
   hall_01(351 s)、hall_02(128 s)、room_02(75 s)、room_dark_01(106 s) 有相机，但视差未验证。
   需先导出 TUM 序列并做一次「能否稳定初始化」短测。
4. **推送**：见 §7。

## 6. 证据索引

- MM-LINS：`docs/four_host/mmlins_recovery_20261117/`（`REPORT_20261117.md`、`REPORT_V2_*`、
  `REPORT_HOSTONLY_V3_*`、`REPORT_V4_*`、`PGO_CRASH_ANALYSIS_*`、各 `two_event_*` 原件）
- LIO-SAM：`docs/four_host/liosam_recovery_20261117/`（`REPORT_V1_*`、`patches/`、`two_event_liosam_v1_*`）
- FAST-LIO2：`docs/four_host/fastlio_recovery_20261113/`（`FASTLIO2_OPTION3_CLOSURE_PACKAGE_20261117.md` 等）
- 跨宿主：`docs/FOUR_HOST_AB_PROGRESS_20261117.md`；过程记录：`docs/COLLABORATION_STATUS.md` §232–§254
- 审阅：`review/repair-f3-handoff-20261110`（最新 `7815391`，2026-11-18 日报）

## 7. 版本状态（实际）

- 本机 `main`：见本次提交；远端 `slam_recovery/main`：`b5f1dc9`（2026-11-17 推送）。
- **本地有 2 条提交未推送**（`5207ae2` LIO-SAM 首跑、`354929a` 停止记录），本文提交后为 3 条。
- 原因：内联 PAT 推送与凭据文件写入均被自动模式分类器按凭据外泄规则拒绝，未绕过。
