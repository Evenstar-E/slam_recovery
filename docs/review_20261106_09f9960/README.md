# 复核 · 09f9960（四条收尾 + 一条记账）

**范围**：`09f9960` "Close the five follow-up review items on the P1 fixes"，8 文件 / +69 −19。
**方法**：逐行读 diff；对全部 27 份 manifest 做了 reentry / Wilson / paired 字段的程序化扫描；`py_compile` 六个改动模块；`python -B -m unittest discover -s slam_recovery/tests` → **22/22 PASS**。

## 结论

**五项收口全部按承诺落地，代码改对了。** 但这次改动在**文档里留下了两处互相矛盾的说法**，其中一处落在论文最关键的那句安全证据上；另外两项行为变更（重入门限、样本量自适应）**没有新增任何测试**。

| # | 项 | 验收 |
|---|---|---|
| P2-1 | None 格式化崩溃 | ✅ 已修，全库已无残留 |
| P2-2 | 同一物理量两个阈值 | ✅ 已统一到 0.50，无历史判决翻转 |
| P3-1 | 样本量下限过薄 | ✅ 已改为随候选规模自适应 |
| P3-2 | B0 硬编码 `G: 0.0` | ✅ 已改名为 `recovery_ratio_G_by_definition` |
| P3-3 | `21/21` 记账 | ✅ 不改历史提交是对的 |

---

## 一、逐项核验

### P2-1 已修，且修干净了

`run_hard_negative_and_rot_ate_benchmark.py:388` 与 `hall_02/evaluate_hall_02.py:98` 各加了一个模块级 `_fmt_g()`。我扫描了全仓库所有 `.py` 里对 `recovery_ratio_G*` 的格式化用法，**没有剩余会抛 `TypeError` 的 `:+.4f`**。hall_02 那三行现在走 `_fmt_g(...)`，C 段 B6 那行长 print 也一并改了。这一条可以关闭。

### P2-2 统一到 0.50，历史判决确实不变

- `wilson_validator.py:57`：`max_reentry_position_jump_m: float = 0.50`，与 `core.py:220` 的 `GateThresholds.max_reentry_jump_m = 0.50` 同值。
- 我独立做了全量核对：仓库里所有 manifest 中记录的 reentry 数值共 18 条，分布在 9 份文件，落在 `(0.35, 0.50]` 区间的**只有 street_08 的 0.4042**，与提交信息一致。
- 所有调用点的实参也核过：`evaluate_e3_orbslam3.py:416/422`、`room_dark_01:313/319`、`hall_02:292`、`room_dark_02:291` 传的都是 ≤0.0898 或 ≥3.6932 的量；`transaction_manager_node.py:302` 显式传 0.0（重入由门控单独判）。**没有任何一条已记录判决会因此翻转。**
- 提交信息里"论文写的是 0.50，代码才是离群值"这个判断是对的：`paper_main.tex:393` 原文就是 `re-entry jump 0.4042 m ≤ 0.50 m`。改代码而不是改论文，方向正确。

### P3-1 自适应样本量，数学核过

`transaction_manager_node.py:266-270`：`len(keys) >= 8 → required_paired = 8`，否则 4。这个值同时进了预检查（`:271`）和 `min_observations`（`:303`），两处一致，没有"预检查过了但报告按旧门槛算"的缝隙。

Wilson 下界我按 `L = n/(n+z²)`（全数改善、z=1.645）手算复核：n=3 → 0.5258、n=4 → 0.5965、**n=8 → 0.7472**，与注释和文档一致。

### P3-2 改名正确，无内部消费者

`evaluate_e3_orbslam3.py:469`、`room_dark_01.py:362` 已改为 `recovery_ratio_G_by_definition`。我搜了所有对 manifest 该键的读取，**没有代码读 B0 的 `recovery_ratio_G`**，改名不会打断任何下游。"磁盘上 manifest 仍旧键、待脚本重跑才更新"这一点提交信息已主动披露，不算隐瞒。

### P3-3 不改历史提交，同意

`79dae02` 当时确实是 21 条测试，第 22 条在 `20047a2` 才加。为一个纯记账问题 force-push 改写已发布历史，代价大于收益。

---

## 二、必须修（P1）：论文那句"三项同时被拒"自相矛盾

`paper_submission_package/paper_main.tex:393`：

> our B6 pose-graph bridge is *refused* by the gate **on all three measured criteria at once** (cross-scan NIS = 4.4145 > 2.5, Wilson LB = 0.4626 < 0.55, **re-entry jump 0.4042 m ≤ 0.50 m**)

三项里第三项的不等号是 **≤**，即**通过**。两个不满足、一个满足，却写成"三项同时被拒"。这是全文最强的一句安全证据，而读者只要看一眼括号就会发现问题。

**这一处和本次改动直接相关**：改动之前，`wilson_validator` 用 0.35，会先以 `reentry_position_discontinuity_exceeded` 拒掉它——也就是说旧代码下是"重入拒、Wilson 也拒"；改动之后两边都认 0.4042 ≤ 0.50 通过，只剩 NIS 与 Wilson 两项在拒。**这次统一让这句话变得更不成立**，提交信息引用了这半句作为依据，却没有发现整句是矛盾的。

建议改写为：

> ...refused by the gate on **two of the three** measured criteria (cross-scan NIS = 4.4145 > 2.5, Wilson LB = 0.4626 < 0.55), with the re-entry jump 0.4042 m **within** its 0.50 m bound...

而且这样写反而更有说服力：它证明门控不是靠某一个指标一刀切，而是在连续性已满足的情况下仍被独立证据否决。

---

## 三、应修（P2）

### 3.1 同一份研究文档里，样本量规则前后矛盾

`SLAM_RECOVERY_RESEARCH.md:540` 新加了自适应规则（n≥4 只是下限，≥8 关键帧时要求 n≥8），但同一份文件 **`:1857`** 仍写着：

> ...`min_paired_observations=4`（n=3 时全票改善的 Wilson 下界为 0.526 < 0.55，n=4 时为 0.596，取最小可判别样本数，非人工放宽）。

`paper_submission_package/SLAM_RECOVERY_RESEARCH.md:1857` 是同一句的镜像，同样没改。读者从 §实现细节 进来会得到与 §4.9 相反的结论。请把 1857 那行改成"下限 4，候选触及关键帧 ≥8 时抬到 8"，或直接指向 540 行。

### 3.2 两项行为变更都没有测试

`git show --stat 09f9960` 显示 **没有任何 tests/ 文件被改动**。这是本仓库唯一一次"改了门控判定逻辑却不加断言"的提交，而前一轮 P1 修复每条都配了测试。

具体缺口：

- `test_atomic_commit.py:151` 用 0.85、`:158` 用 0.04，**两个值在 0.35 和 0.50 下行为相同**，所以把新常量改回 0.35 测试也不会红。建议补一条 `reentry_position_jump_m=0.40` 的用例，断言 `approved=True` 且 `reason` 不是 `reentry_position_discontinuity_exceeded`。
- 自适应样本量：没有任何测试构造 ≥8 关键帧的候选。建议用 `confirmation_margin_sec=0.0` 的节点构造 8 个 keyframe + 6 个 paired frame，断言 `last_paired_evidence["required_paired_frames"] == 8`、判决为 MISSING——这正是新规则要挡的场景。

没有这两条，下一次有人"顺手调一下常量"，CI 不会拦。

---

## 四、建议顺手清（P3）

### 4.1 大候选规则应当是 `max(...)`，不是直接取值

`transaction_manager_node.py:266-270`：

```python
required_paired = (
    self.min_paired_observations_large_candidate
    if len(keys) >= self.large_candidate_keyframe_threshold
    else self.min_paired_observations
)
```

若有人用 `min_paired_observations=10` 构造节点，一个 ≥8 关键帧的大候选反而只需要 **8** 帧——"抬高要求"的规则把要求**降低了**。默认值 4 < 8 掩盖了这一点，但这是安全门控里的一处反直觉逻辑。建议写成：

```python
required_paired = max(self.min_paired_observations,
                      self.min_paired_observations_large_candidate
                      if len(keys) >= self.large_candidate_keyframe_threshold
                      else 0)
```

### 4.2 失败分支与成功分支的键名不一致

`last_paired_evidence` 在证据不足时记 `"min_paired_observations": required_paired`（`:275`），在通过时记 `"required_paired_frames": required_paired`（`:307`）。**恰恰是"MISSING 判决"这个最需要解释的场景，用的是旧键名。** 建议两处统一为 `required_paired_frames`。

### 4.3 本次编辑的那一格，数字与 manifest 对不上

`SLAM_RECOVERY_RESEARCH.md:1636`（B5 / hall_01 重度低光）本次从 `0.92m > 0.35m` 改成 `0.92m > 0.50m`。但仓库里对应的 `e3_orbslam3_second_host_benchmark.json` 记的是：

| 字段 | 文档写的 | manifest 实际 |
|---|---|---|
| `reentry_position_jump_m` | 0.92 | **4.519** |
| `wilson_lower_bound` | 0.0 | **0.8061** |
| `recovery_ratio_G_vs_B0` | −6.0531 | **−6.0539** |
| `rejection_reason` | — | `reentry_position_discontinuity_exceeded` |

结论不变（4.519 > 0.50，仍被拒），但**这一格的两个核心数字（0.92、Wilson 0.0）在仓库里找不到来源**。既然本次专门编辑了这一格，就应该顺手对着 manifest 校一遍。建议改成 `4.519m > 0.50m`，Wilson 写 0.8061 并说明拒绝原因是重入而非 Wilson。

### 4.4 S1/S2 manifest 已经过期

`sim_s1_s2_counterfactual_and_3d_voxel_benchmark.json` 里的 `paired_evidence_diagnostics` 只有旧字段，重跑后会多出 `required_paired_frames`、`candidate_keyframes`，**不会再 byte-identical**。提交信息里的 byte-identical 只针对 p10（我核过 p10 manifest，G = 0.0032 / 0.9975，与提交信息一致），这一条不算错，只是别把结论推广到 S1/S2。

另外，"所有实际运行记录的 `num_paired_frames` 为 20"这句，严格说是"**唯一记录了该字段的 manifest** 里是 20"——其余 manifest 根本没有 paired 诊断字段。措辞收一下更稳。

---

## 五、复现

```sh
python -m py_compile slam_recovery/sim/transaction_manager_node.py \
  slam_recovery/validation/wilson_validator.py \
  slam_recovery/experiments/run_hard_negative_and_rot_ate_benchmark.py \
  slam_recovery/experiments/e3_orbslam3/hall_02/evaluate_hall_02.py \
  slam_recovery/experiments/e3_orbslam3/evaluate_e3_orbslam3.py \
  slam_recovery/experiments/e3_orbslam3/room_dark_01/evaluate_room_dark_01.py
python -B -m unittest discover -s slam_recovery/tests -v     # 22/22 PASS
```

manifest 全量扫描（本文第一、四节的数据来源）可直接对 `slam_recovery/experiments/manifests/*.json` 递归取 `reentry*` 字段，无需重跑宿主。

---

## 六、建议顺序

1. **P1**：改掉 `paper_main.tex:393` 的"all three ... at once"，并同步重编 PDF。
2. **P2**：改掉 `SLAM_RECOVERY_RESEARCH.md:1857`（两份）与 540 行的矛盾。
3. **P2**：补两条测试（0.40 重入、8 关键帧自适应）。
4. **P3**：`max()`、键名统一、1636 行的数字校正。
5. 以上清完，门控的样本量逻辑就既有实现又有回归保护，可以放心推进 8.1（FAST-LIVO2 第五宿主）与 8.2（组件消融）。
