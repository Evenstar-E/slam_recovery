# 独立复核 · 1846b00 时点

**复核对象**：`c9fd250`（新增 `repair_plan.md`，47 行文档，无代码改动）、`43119ed`（两份 review 文档）、`8a2a541`（F1–F8 修复）。
`1846b00` 是本会话提交的 Isaac Sim 导出，不属于开发侧改动，不在此评审范围。

**基线**：`python -B -m unittest discover -s slam_recovery/tests` → **18/18 PASS**（本机实测，0.708 s）。
F1–F8 中可静态核验的部分确实落进了代码：`core.py:270-290` 已有偏置三向量/有限性/SE(3) 形状校验，`GateThresholds` 也新增了 `min_wilson_lower_bound`、`max_reentry_jump_m`。

**结论**：测试通过不等于门控成立。下列 4 条 P1 我用代码逐行复核，**当前仍然成立**；其中两条使"缺少安全证据"被当作"证据通过"。在它们修复前，论文中 "holdout-screened atomic commit" 与"有界内存延迟提交队列"两处表述都不能按字面理解。

---

## 一、我独立核实成立的 4 条

### P1-1 「缺测 = 通过」：三项安全证据默认放行

- **证据链**：`core.py:183-185` 三个字段默认 `paired_benefit_approved=True` / `wilson_lower_bound=1.0` / `reentry_pos_jump_m=0.0`；`core.py:308-312` 用这三者算 `wilson_ok`；而唯一的生产入口 `transaction_manager_node.py:247-254` 构造 `CandidateMap` 时**三项一个都没传**。
- **后果**：`wilson_lower_bound ≥ 0.55`、`reentry_pos_jump_m ≤ 0.50`、`paired_benefit_approved` 这三条"验证通过才允许提交"的条件，在有候选的真实路径上恒为真。上一轮"把 Wilson 检验前置到提交之前"的修复，在在线节点上被默认值架空了。显式传入坏值才被拒——这只证明校验器能拒坏值，不证明它能识别缺测。
- **修法**：三字段改为 `Optional[...] = None`；`None` 归入"证据不足"，不得进入 Mode 2，返回 Mode 3 等待。只有实测通过才允许提交；显式失败则拒绝。使"缺测／通过／失败"三态可区分，并把这一条写成断言。

### P1-2 撤销最后一帧后，验证仍读到旧点

- **证据**：`transaction_manager_node.py:121-122`

  ```python
  if self._kf_map_points:
      self.committed_map_points = [self._kf_map_points[k] for k in sorted(self._kf_map_points.keys())]
  ```

- **后果**：全部关键帧被撤销后 `_kf_map_points` 变空，`committed_map_points` **不被刷新**，`get_trusted_map_points()` 继续返回已撤销帧的世界点。下一次候选评分会把它们并入 `train_world`，于是"空地图"仍能完成一次看起来正常的验证。
- **修法**：去掉 `if`，空集也写回 `[]`；补一条断言：撤销最后一帧后 `get_trusted_map_points()` 必须为空。

### P1-3 `room_dark_01` 的旋转改善归因错位

- **证据**：`run_hard_negative_and_rot_ate_benchmark.py:280-293`

  ```python
  ts_fl_rd, xyz_fl_rd, q_fl_rd = read_bag_odom_se3(".../result_room_dark_01_light.bag", "/Odometry")
  q_gt_zero = np.zeros_like(q_gt_rd)
  rot_fl_rd_b6 = evaluate_rotation_ate_rpe_deg(ts_fl_rd, xyz_fl_rd, q_fl_rd, ts_gt_rd, xyz_gt_rd, q_gt_zero)
  ```

- **后果**：结果字典里键名是 `Ours_B6_LiDAR_Anchored_Orientation`，实际喂进去的是 **FAST-LIO2 自身 `/Odometry` 的四元数**，不是 ORB-SLAM3 B6 的输出姿态；且 GT 四元数置零后走的是切向代理。论文"Atlas 19.268° → B6 5.211°"因此不能归因于 B6 修复。
- **修法**：要么改名为"辅助 LiDAR 姿态上界"并在正文同步措辞，要么从 B6 实际发布的逐帧位姿算；若 B6 只输出平移，旋转一项标为缺测。

### P1-4 撤销日志 O(N²) 内存

- **证据**：`manager.py:60` 每次晋升都做 `prev_factors = list(self.trusted_factors)` 全量拷贝，并追加到 `_promoted_before_images`。
- **后果**：N 帧后累计 `N(N+1)/2` 个因子引用（250 帧 = 31,125，500 帧 = 124,750，与复审文档给的数字一致）。这与论文"延迟提交队列为有界内存"的表述冲突，长序列有 OOM 风险。
- **修法**：只存 `(start_index, added_factor_ids)` 增量，回滚时把列表截断到 `start_index`；保持重复关键帧与偏置的精确回滚语义不变。

---

## 二、我未能复现、需要开发侧指明的 2 条

| 复审文档的说法 | 我的核对结果 | 请补充 |
|---|---|---|
| S1 用各帧扫描估计候选横向位置，之后又从中每五帧取一帧打分 | `run_s1_s2_simulation_experiments.py:261-281` 中 R5/B6 直接用 `quar_poses_gt`（GT 位姿），B5 用合成横向漂移 `quar_poses_drifted_b5`，**都不是从这些扫描拟合出来的** | 请指明"用扫描估计候选"的具体行号；否则该条应降级 |
| Campus 以首尾距离选快照，又用同一距离评分 | `run_campus_and_overhead_benchmark.py` 未逐行复核 | 请给出选快照与评分的具体函数，我按同一口径复核 |

这两条若成立仍是 P1，但在定位之前不应写进给开发侧的任务单——否则会照着错误的行号改。

---

## 三、关于 `c9fd250` 本身

纯文档，方向正确：把 A/B/C/D 四组对照分开，要求地图、轨迹、决策代价三套分母齐全，并明确"用已有 FAST-LIVO2 前提是能导出宿主实际持久地图与提交记录"。这几点比之前的计划更严谨，我没有异议。

但它在第 1 节把 P1-1 描述为"候选省略证据时关键帧 42 被写入"——这正是我上面核实的那条。**开发侧已知情而未修**，文档不构成修复。

---

## 四、建议顺序

1. **先修 P1-1、P1-2**。两者都是行级改动，但决定论文里"验证后提交"这句话是否成立；修完把两条断言并入 `test_atomic_commit.py`。
2. **再修 P1-4**（内存线性化）。
3. **P1-3 改标签或补真实姿态**，并同步 `paper_main.tex` 对应句。
4. 跑 `docs/review_20261106_a14bc1c/probe_boundaries.py` 与全套测试，确认 4 个探针由 reproduce 变为 not reproduced。
5. **这之后**再做 FAST-LIVO2 第五宿主与组件消融（原 Action Item 8.1 / 8.2）。否则新实验都建在一个会默认放行的门控上，结论不可用。

## 五、复现入口

```sh
python -B -m unittest discover -s slam_recovery/tests -v     # 18/18 PASS
python -B docs/review_20261106_a14bc1c/probe_boundaries.py   # 打印四条观测值
```

本机未播放 bag、未重跑宿主、未重算 ATE；以上结论全部来自源码阅读与单元测试。
