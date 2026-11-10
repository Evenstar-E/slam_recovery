# A10/B11 阶段一：原生同进程闭环（2026-11-10，第二次口径修正后）

本文件替代 `A10_B11_native_loop_stage1.md` 中 §1.2、§3、§4 的数字；接线部分结论不变。
上一版存档保留，两版的差别就是这一轮改口径的效果。

## 0. 这一轮改了什么

按裁决改了两处**测量口径**，没有动任何门限、没有动 σ、没有动 `step_frame`/`core`/`manager`/`fim_and_holdout`：

1. NIS 参考从 `get_trusted_map_points(max_pts=2000)`（点数上限）改为
   `support_reference()`（每 0.30 m 占据体素一点），并按 `trusted_version` 缓存；
2. "假定健康"取消：帧是否交给检测器，由节点既有的
   `_frame_has_reference_support(...)`（`radius_m=1.0`、`min_supported_fraction=0.60`）决定。
   不满足就只经 manager 的健康路径进图、**不让检测器判定**，记 `detection_status="UNAVAILABLE"`。

顺带修掉上一版一个真 bug：隔离期内的帧走 `step_healthy` 会抛 `RuntimeError`，
上一版被吞成 207 次 callback error；现在隔离期内改走 `register_quarantined_frame`（本趟 callback error 0）。

## 1. 结果：参考口径改了，NIS 没变

| 口径 | node_map NIS 中位数 | p10 | p90 | max |
|---|---|---|---|---|
| 点数上限 2000（上一版） | 21.57 | 5.11 | 857 | 2658 |
| 空间抽样 0.30 m（本版） | **24.05** | 6.54 | 1095 | 2699 |

检测器判据 `nis_q90 = nis×1.35 > 2.8`，即 **NIS > 2.07 报警**。中位数仍是阈值的 11 倍。

**所以"点数上限导致 NIS 偏高"这个假设不成立**——至少它不是主因。空间抽样下参考点反而更少
（931 点 vs 1500 点），NIS 略有上升。

## 2. 真正的主因：检测开始时，参考只有 2 个关键帧

本趟逐帧记录（`run_summary.json:frame_diagnostics`）：

```
kf=18  t=2.132  UNAVAILABLE  prev_scan  nis=6.62   kfs=2  pts=931  state=HEALTHY
kf=19  t=2.199  AVAILABLE    node_map   nis=54.40  kfs=2  pts=931  state=SUSPECT
kf=20  t=2.332  AVAILABLE    node_map   nis=53.75  kfs=2  pts=931  state=QUARANTINED
```

`confirmation_margin = 2 s` 意味着可信图里只有"2 秒以前"的帧。t=2.13 s 时，越过边距的帧
正好是**最开始那 2 帧**。而 `_frame_has_reference_support` 在只有 2 帧时就返回 True，
于是检测器在**第一个可以判定的瞬间**就被交给了 931 点的参考，并立刻报警。

之后隔离段不解除，可信图冻结在 2 帧 / 931 点，剩下的 361 帧全部对着这同一个 931 点参考打分，
NIS 一直在 15–55 之间（p90 被少数远离地图的帧拉到 1094）。

结论（按裁决 §5 的口径）：**改完口径仍然在检测开始后 1 帧内隔离，这是真结论，不是口径残留。**
记录器与检测器在实时下不匹配的形态是：**"参考可用"的判据（覆盖 60%）远比"参考足以支撑标定过的 NIS"
宽松**，两者之间没有任何缓冲。

## 3. 一次决策的内容（与上一版最大的不同：证据通过了，边界没过）

```
t_trigger_ns  = 1627643742844584942      （首帧 + 2.27 s，注入窗口起点前 16.71 s）
t_decision_ns = 1627643744910121918
mode          = MODE3_SOFT_BRIDGE_WAIT
accepted      = false
wilson_lb     = 0.886   (21/21 帧改善，approved=true)
reentry_pos_jump_m = 0.666 m  > 0.5 m 界
refusal_reason= 段边界跳变超限
```

配对证据这一趟**通过了**：宿主的真实位姿在 21/21 帧上优于匀速外推（残差 4.13 vs 13.45）。
唯一的拒绝理由是 0.666 m 的边界跳变，而那个跳变是拿一个 2 帧地图的锚点量的。

## 4. 接线（不变，仍全 PASS）

| # | 项 | 结果 |
|---|---|---|
| 1 | 两话题在收 | PASS（800 位姿 / 599 扫描） |
| 2 | 配对成功率 | PASS **97.5%**（584/599） |
| 3 | gate 有输出、四参取齐 | PASS（`incumbent_basis=CONSTANT_VELOCITY`） |
| 4 | pid 与宿主同组 | PASS（pgid 2955400 = 2955400） |
| 5 | NIS 有来源、不伪造 | PASS（node_map 365 / prev_scan 218 / unavailable 1，无 carried_forward） |

候选记录 18 键零 null。`detection_status`：AVAILABLE 361 / UNAVAILABLE 223
（后者绝大多数是隔离开始后、地图冻结导致覆盖不上的帧，不是启动帧）。

## 5. 配对窗口 20 → 40 ms：同一次运行的对数重算

用同一趟记录的 800 位姿 / 599 扫描戳跑同一个匹配器：

| 窗口 | 配对 | 扫描占比 | 位姿占比 |
|---|---|---|---|
| 20 ms | 333 | 55.6% | 41.6% |
| 40 ms | 584 | **97.5%** | 73.0% |

dt 分布（扫描到最近位姿）：p10 −28.26 ms、中位 +0.09 ms、p90 +29.53 ms；位姿间隔 66.6 ms。
`pairing_rule = "nearest pose within 40 ms, no pose reused"` 已写进 receipt。
**与离线四臂的 20 ms 结果不可同表**，summary 里已标注。

## 6. 状态

- `gate_decision_validity = "GAUGE_DEPENDENT_UNTIL_A7_FIX"`（不变）；
- 阶段一仍**未产出与注入 onset 相关的候选**：每次都是启动后 2.3 s 的误触发；
- 是否让检测在"参考足以支撑 NIS"之前不启动（例如要求参考的最小帧数或最小地图年龄），
  属于新判据，不在我这条线里定；
- 阶段二 (d) 未开始。
