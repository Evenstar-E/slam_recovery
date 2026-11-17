# FAST-LIO2 恢复线 option ③ 收口包（2026-11-17）

**性质**：把 2026-11-14 至 2026-11-17 在 FAST-LIO2 宿主上完成的工作整理成一份**可核的收口材料**。
不是验收通过，不是 accepted 修复，不重开 run。审阅 `423fee0` 指定这是下一单一主线的交付形态。

**证据基线**：`origin/main@8c1defb`（收口包提交前的 main）；运行原件在各 `two_event_*_authorized/`
目录；逐条判定见 `LEDGER.md` 与 `docs/COLLABORATION_STATUS.md` §231–§240。

## 1. 已验证（有原件、可复算）

| 项 | 证据 | 原件 |
|---|---|---|
| 原生检查点在真实退化事件上存活 | hold→snapshot（最多 221901 点）→ 退化期间宿主继续发布（v9）→ `restore valid=1` | v9/v9b 起每次 run 的 `run_summary.json`、`host.log` |
| 两事件生命周期闭合 | 两事件触发、段关闭（`wait_limit_closed`）、`rearm`、`resume`、第二事件、尾段；终态 `HEALTHY` | `two_event_v9f/v9g/v9j_*` 的 `lifecycle.events` |
| 等待不再依赖新帧 | `_close_stalled_wait` 墙钟关闭 + ABORTED 自动 rearm（v8 的 HIBERNATION_TIMEOUT 修复） | `slam_recovery/ros/recovery_node.py`；`test_hold_ownership.py` |
| JIT 武装 | `arming_mode=JIT_BOUNDARY_MINUS_3s`，E1 快照 `AT_OR_BEFORE_BOUNDARY` | `scripted_triggers.armed_boundaries` |
| host-only 七步接口 | status/capabilities/hold/snapshot/restore/reprocess/resume 七条宿主 ack 原文 | `host_smoke7_v9_authorized/smoke7.jsonl`（限制：reprocess `replay_suffix=0`） |
| 失败候选不再克隆为 incumbent | `_icp_candidate` 只在 `CONVERGED/ITERATION_LIMIT` 产出候选，`candidate_suppressed=true` | `test_recovery_node.py`；测试 292 全绿 |
| 冻结门/ICP/宿主未改 | 门阈值、`IcpConfig`、宿主二进制 `aa04c5ff…`（v9）在全部 run 中一致 | 各 run 的 `pre_run.txt` |

## 2. 未达成（保留负结果）

**accepted 测量修复提交：未获得。** 11 次 run 的全部读数：

| run | 场景 | E1 | E2 | 判定 |
|---|---|---|---|---|
| v8 | 自然事件 | — | — | 等待死锁 → HIBERNATION_TIMEOUT（已修） |
| v9 | 自然事件 | 9/13 | 未触发 | Mode 4 拒绝 |
| v9b | 自然事件 | 3/12 | 1/11 | 拒绝 |
| v9c | 自然事件（逐帧） | 1/13 | 5/11 | 拒绝 |
| v9d | 注入 196–202 s | 7/40 | 14/40 | 拒绝 |
| v9e | 注入转弯窗 | 0/40 | 0/41 | 拒绝 |
| v9f | 自然事件（运动先验） | 2/21 | 1/19 | 拒绝 |
| v9g | 注入（运动先验） | 9/40 | 0/41（无候选） | 拒绝 |
| v9h | campus_2 转弯窗 | 4/38 | 未触发（宿主自入睡） | 拒绝 |
| v9i | campus_1_2 移动窗（host_poses） | **36/41，Wilson 0.770** | **41/41，Wilson 0.938** | 收益通过；仍拒绝（见下） |
| v9j | 静止窗注入 | 0/8（候选≡incumbent） | 0/22 | 拒绝；E1 为候选生成器缺陷，已修 |

- v9i 的拒绝原因（`core.py` 判据）：E1 信息增益比 **1.012 < κ=2.0**、holdout NIS **2293 > 2.5**；
  E2 另有重入跳跃 74.66 m > 时间包络 31.30 m，且信息比 1.13、holdout 38.59。
- 更正：2026-11-14 曾把「0.5 m 连续性与真实运动互斥」写成结构性结论，**已撤回**——实际判据是
  `jump ≤ 0.5 + 2.0·Δt`（`core.py:535-542`），v9i E1/v9j 两事件的重入包络均通过。

## 3. 定义边界（收口口径）

> 在当前 FAST-LIO 派生宿主、已试候选生成器（整段刚体 / 逐帧 / 运动先验多尺度）、已试窗口与冻结协议下，
> 未获得 accepted 测量修复提交。现有证据不支持对宿主+序列作一般「不可达」判断，也不支持
> 「修复收益为零」的推断（v9j E1 是候选生成器失效，不是改进量不存在）。

- 恢复层在本宿主上的可交付价值是**回滚 + 重启生命周期**与**两事件整链闭合**；
- 检测未在线（全部 run `detection off`），检测指标由 ALI-H 资格-only 收口，`NOT_EVALUABLE`；
- 无 native update/map 的净收益证据；无独立复现。

## 4. 产物索引

- 运行目录：`two_event_v8_holdown_authorized/`、`two_event_v9_icp_authorized/`、
  `two_event_v9b_rearm_authorized/`、`two_event_v9c_perframe_authorized/`、
  `two_event_v9d_injected_authorized/`、`two_event_v9e_turn_authorized/`、
  `two_event_v9f_prior_natural_authorized/`、`two_event_v9g_prior_injected_authorized/`、
  `two_event_v9h_seq2_turn_authorized/`、`two_event_v9i_seq2_hostposes_authorized/`、
  `two_event_v9j_static_injected_authorized/`、`host_smoke7_v9_authorized/`。
- 方法声明：`MOTION_PRIOR_METHOD_20261114.md`。
- 判定记录：`LEDGER.md`；跨宿主对照：`docs/FOUR_HOST_AB_PROGRESS_20261117.md`。

## 5. 重开条件

若将来重新追求 accepted：需要用户新的有界 run 授权；使用已修的失败语义；先声明候选方法与其冻结常数；
不得通过降门、改阈值或改宿主二进制制造 accepted。四项宿主全部验收前不返回 FAST-LIVO2。
