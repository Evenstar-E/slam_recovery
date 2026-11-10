# σ=0.884 的原生闭环运行：事件级指标（2026-11-10）

这一趟执行已经写死的规则：**σ 使"检测开始时那个参考"上的健康 NIS 中位数为 1**。
检测从 2 个关键帧 / 932 点开始，该箱 σ\*=0.884（`detection_start_criterion.md` §3.1）。

运行：

```
bash slam_recovery/ros/run_native_loop.sh /tmp/fastlivo/room02_2x2_O.bag \
     --rate 1.0 --drain 3 --sigma-meas-m 0.884
```

receipt：`/tmp/fl_native_20261110T035825Z_3008585/receipt.json`
（已归档 `native_loop_sigma0884_receipt.json` / `_summary.json` / `_candidates.jsonl` / `_wiring.json`）

## 1. 事件级三件（B3 的口径）

真实 onset = `room02_2x2_audit.json:window.onset_ns` = 1627643759554082870。

| 事件 | 戳 | 相对真实 onset |
|---|---|---|
| 首次报警（detector 离开 HEALTHY） | 1627643759526658773 | **−0.027 s** |
| 隔离段开启 | 1627643759659727812 | **+0.106 s** |
| detector 的 onset 估计 | 1627643759426658773 | **−0.127 s** |
| 隔离段起点（估计 − 2 s 边距） | 1627643757426658773 | −2.127 s |
| 决策 | 1627643761790611506 | +2.237 s |

1. **检测延迟 = +0.027 s**（|误差| 27 ms），隔离 +0.106 s；
2. **起点估计误差 = −0.127 s**（早报 127 ms，回溯逻辑没有系统性晚报）；
3. **窗内隔离事件数 = 1**（`episodes = 1`）。隔离开启后状态不再回到 HEALTHY，
   所以"窗内只报一次"在本配置下是结构性的，不是统计结果。

## 2. 帧级覆盖率：100%，但这个数字要按它自己的含义读

窗内（onset 到 onset+19.84 s）197 帧，**197 帧都处于非 HEALTHY**（=100%）。
这不是"检出率"，而是"隔离段开启后不关闭"的必然结果：一旦进入 QUARANTINE，
后续每一帧都带着非 HEALTHY 状态。**真正的召回是事件级的 1/1，不是这个 100%。**

## 3. 与 S3 重放的差异（重要）

S3 重放同一份诊断数据得到 σ=0.884 时首次报警 +6.386 s、覆盖 70/197 帧 = 35.53%。
本趟实测是 **−0.027 s、197/197**。差异不是随机性，是参考不同：

- 重放用的是诊断跑里**早期冻结的小参考**；
- 活循环里，检测启动后平台继续跑、可信图继续长（2 s 确认边距持续放行新帧），
  到真实 onset 时参考已经是数百帧的大图；
- 于是健康基线 NIS 落到 19.72×(0.12/0.884)² ≈ 0.36，注入把 NIS 推过 2.07 的阈值，
  报警发生在污染出现的那一刻，而不是"等参考变大"。

**结论：σ=0.884 不是在两端妥协，它在活循环里把基线和污染分开了。**

## 4. 决策内容

```
mode = MODE3_SOFT_BRIDGE_WAIT，accepted = false
refusal_reason = 段边界跳变超限
reentry_pos_jump_m = 1.2506 m  > 0.5 m 界
wilson_lower_bound = 0.601（17/22 帧改善；`paired_evidence.approved = true`）
holdout_nis = 0.0948
weak_dir_info_before/after = 1.102 / 4.628
candidate_frames = 22（隔离期缓存的宿主位姿）
```

配对证据这一趟**通过了**（Wilson 0.601 > 0.55，17/22 帧改善，残差 0.253 → 0.091）。

**更正：1.25 m 边界跳变不是唯一的拒绝原因。** refusal 文案只会报先失败的那一腿，而
`weak_dir_info_after = 4.628` 对 `tau_info = 25`——**弱方向信息这一腿本来就不够**。
所以即使边界判据修好，Mode 仍然是 3，拒绝理由会变成"弱方向信息不足"。

另外，这个 1.25 m 本身也不是候选的问题：锚点比触发帧早 2.329 s，1.2506/2.329 ≈ 0.54 m/s，
是行走速度。已由 S1 在 `bcadd9f` 修成"锚点时间戳起算的时距包络"，阈值 0.5 m 未动。

## 4b. 边界判据修完重跑（`bcadd9f` 之后）

同一 bag、同一 σ，重跑一次（receipt `/tmp/fl_native_20261110T042426Z_3020861`）：

| 项 | 修前 | 修后 |
|---|---|---|
| 首次报警 / 隔离 / 起点估计 / 决策 | −0.027 / +0.106 / −0.127 / +2.237 s | **完全相同** |
| Mode | 3 | 3 |
| refusal 文案 | 段边界跳变超限 | **paired-benefit evidence FAILED** |
| `reentry_pos_jump_m` | 1.2506 | **1.2636**（未变，仍超 0.5 界） |
| `boundary_continuity_ok` | False | **True**（边界这一腿通过） |

**修复只覆盖了一半。** `bcadd9f` 把时距包络用在段边界与 first-run 两处判定上，
但 `_measure_paired_evidence`（`transaction_manager_node.py:404`）仍把**原始锚点距离**
写进 `CandidateMap.reentry_pos_jump_m`，而 `evaluate_four_mode_gate`（`core.py:522`）用
`reentry_pos_jump_m > max_reentry_jump_m` 决定 `evidence_status`。
于是同一个陈旧锚点距离换了条腿再失败一次：边界腿过了，证据腿没过，文案随之变成
"paired-benefit evidence FAILED"。

修好之后才会轮到真正的下一个原因：**`weak_dir_info_after = 4.634` 对 `tau_info = 25`**，
Mode 仍是 3。这与 S1 的判断一致（他事先指出边界不是唯一原因）。

## 4c. 门侧包络修完之后（`f9ad688`）

再跑一趟（receipt `/tmp/fl_native_20261110T044250Z_3031393`）。检测三项仍完全不变。

| 项 | 值 |
|---|---|
| Mode | 3 |
| refusal | **paired-benefit evidence FAILED**（不再是边界） |
| `reentry_pos_jump_m` | 1.2518（仍作为物理距离上报） |
| 门是否仍因它拒绝 | **否**——`reentry_elapsed_s` 存在时走同一包络 |
| Wilson 下界 | **0.418 < 0.55** → 证据腿这次是**真的**没过 |
| `weak_dir_info_after` | 4.699 < `tau_info` 25 |

所以 re-entry 这条**修好了**（不再拒绝），拒绝理由落到配对收益本身；而
`weak_dir_info_after` 仍然不足，Mode 3 与 S1 的预判一致。

**但这趟的 Wilson 数值受机器负载影响，不能当结论。** 同一份代码、同一 bag：

| 运行 | 机器 load | 配对 | 改善帧 | Wilson |
|---|---|---|---|---|
| `035825Z`（空载） | ~200 | 584/599 | 17/22 | 0.601 |
| `044250Z` | **338 / 128 核** | 369/599 | 13/22 | 0.418 |

候选人口是"2 s 决策窗内处理到的帧"，节点跟不上时窗内帧数变少、改善比例随之变化。
`runner` 现在把 `/proc/loadavg` 与 `nproc` 写进 receipt（`machine_load_at_launch`），
因为这是同一份代码给出不同 Wilson 的直接原因。

## 5. 三条代价（按裁决必须写进 receipt）

1. **该箱 n=2**，0.884 是两样本估计，不确定性大——不要当精确值；
2. 大图（101+ 帧）健康中位落到 19.72×(0.12/0.884)² ≈ **0.36**，检测在大图上偏保守；
3. 退化尾部重标后仍 ≈1000×0.0184 ≈ **18**，与 0.36 差一个半数量级，**保守不等于看不见**。

## 6. 吞吐（仍未解决）

584 条扫描配对 97.5%，`max_backlog = 116`，峰值 RSS 386 MB。比诊断跑（393/599、积压 207）
好，但仍未验证 1× 实时下的余量。

## 7. 仍未验收

- 边界判据的度量缺陷已由 S1 在 `bcadd9f` 修掉（锚点时间戳起算的时距包络，阈值不变）；
  但它不是这趟被拒的原因，见 §4 的更正；
- **弱方向信息 4.628 对 `tau_info = 25`**：这两个数是否同一尺度、25 来自哪套 FIM 量级，
  需要证据才能说。本趟只有决策时刻的一个样本 `(before, after) = (1.102, 4.628)`
  （这两个量只在判定时计算，node 不逐帧记录），所以给不出分布；要分布需在
  `_record_diag` 里逐帧记 `min_eig_rot/min_eig_trans`，代价是每帧多一次 FIM。**未动阈值。**
- 阶段二 (d) 的 ICP 候选构造已完成（`slam_recovery/repair/pose_reregistration.py` + 13 项单测），
  离线跑分仍在进行；
- A7 的 gauge 问题不变：本趟决策仍标 `GAUGE_DEPENDENT_UNTIL_A7_FIX`，不进 B10 四策略表。
