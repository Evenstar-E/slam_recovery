# 复核 · 20047a2（P1 修复 + G 迁移 + 负结果改写）

**范围**：`79dae02`（四 P1）、`e15eb02` / `816fab8`（PDF 重建）、`c3e9e7b`（G 的 None 迁移 + room_dark_02 改写）、`20047a2`（迁移收尾 + 测试）。
**方法**：源码逐行 + manifest 对照 + 本地构建。`python -B -m unittest discover -s slam_recovery/tests` → **22/22 PASS**（我本机实测，0.66 s）。

## 结论

**四条 P1 都是真修，不是翻默认值糊过去。** G 的除零哨兵已改为 `None` 并做 None-safe 传播，room_dark_02 已按负结果重写，Fig. 1 已标注为示意图。我先前两条复核里标为"阻断"的事项全部关闭。

---

## 一、逐项验收（含我的独立核算）

### P1-1 「缺测即通过」→ 三态证据，已关闭

- `core.py`：三字段改 `Optional[...] = None`；新增 `ValidationReport.evidence_status ∈ {PASSED, MISSING, FAILED, NOT_APPLICABLE}`；`evidence_status != "PASSED"` 直接拒绝 Mode 2，返回 Mode 3/4。
- **关键改进不是默认值，而是让在线节点真的去测**：`OnlineRecoveryTransactionNode._measure_paired_evidence()` 用候选与 incumbent 在同一份独立的隔离前可信点云上逐帧算 NIS，再喂给 `evaluate_paired_sequential_benefit`；重入跳变单独对冻结锚点测。
- `run_s1_s2_simulation_experiments.py` 五条分支（R4/B5/R5/B6-PM/B6-PG）都传了 `incumbent_poses` 与 `reentry_anchor_pose`，证据是真测出来的，不是占位。
- `min_paired_observations=4` 的理由我手算复核过（单侧 z=1.645，全数改善）：
  - n=3 → L = 0.5258（< 0.55，不通过）
  - n=4 → L = 0.5965（> 0.55，通过）
  与其注释写的 0.526 / 0.596 一致。
- 新增测试覆盖 MISSING / FAILED / NaN→FAILED / PASSED 四态，并断言 `42` 只在 PASSED 时进入 `trusted_poses`。

### P1-2 撤销最后一帧后仍读旧点 → 已关闭

`_sync_spatial_map_with_trusted_poses()` 去掉了 `if self._kf_map_points:` 守卫，空集也写回 `[]`。有对应断言。

### P1-3 room_dark_01 旋转归因错位 → 已关闭

键名改为 `room_dark_01_Aux_FASTLIO2_LidarInertial_Orientation`，并新增 `room_dark_01_Ours_B6_Orientation = UNAVAILABLE` 显式记录"B6 只发布平移，无逐帧四元数"。正文同步改为 auxiliary attitude。这是正确处理——比硬凑一个数字好。

### P1-4 撤销日志 O(N²) → 已关闭

`(prev_pose, prev_factor_len, prev_ba, prev_bg)` + 回滚时 `del self.trusted_factors[prev_factor_len:]`。因子表确为只追加，截断即精确 before-image，每帧 O(1)。新增线性增长测试。

### G 的除零哨兵 → 已关闭

`compute_recovery_ratio_G` 现在返回 `None`，并且在 `E_clean > E_degraded` 时也返回 `None`——这正是 ORB 那个 `-1.0613` 的成因（分母 `0.7614 − 0.9513 < 0`）。新增 `recovery_ratio_G_rounded()` / `round_or_none()`，六个调用点已迁移，manifest 落 `null` 而不是 `0.0`。

### prose

- `room_dark_02`：已改为"three of four hosts 上为负结果，双模态同时退化时受 Proposition 1 限制"，并明确把它当作"仓库保留失败可见性"的证据。原句"zero-tuning generalization"已删。
- manifest 里 `clean_ate_m` 改名 `atlas_on_unmodified_bag_ate_m`，并注明注入只作用于 LiDAR；`dropped_frames_in_15_35s = 0` 增加 `dropped_frames_note` 说明这是 `OFFLINE_CONSTRUCT` 分支的定义产物，并指向 B0 (206/278)、B2 (92/278) 的真实跟踪计数。
- Fig. 1 图注改为 "**Schematic**, drawn from fixed distribution parameters rather than a logged host run"。
- Fig. 0 不再把尚未运行的 FAST-LIVO2 画成已执行路径。

### PDF

`79dae02` 说"本机无 LaTeX，PDF 未重建"，但后续 `816fab8` 的 PDF 元数据为 `Producer: pdfTeX-1.40.29`、`Creator: LaTeX with hyperref`、`CreationDate: D:20261106153920`，与提交时间吻合——**确由 LaTeX 重建，不是旧文件顶替**。此前的矛盾已消解。

---

## 二、残留问题（均不阻断，建议随下次提交清理）

| 级别 | 问题 |
|---|---|
| P2 | **两处 None 格式化会崩**：`run_hard_negative_and_rot_ate_benchmark.py:417-418` 与 `evaluate_hall_02.py:404-406` 仍是 `f"{...:+.4f}"`。刚把 G 改成 None，这两处一旦遇到除零就抛 `TypeError`，而不是打印 `n/a`。`evaluate_room_dark_02.py` 已用 `g_txt` 正确处理，照抄即可。 |
| P2 | **同一物理量有两个阈值**：`_measure_paired_evidence` 给收益检验传 `reentry_position_jump_m=0.0`（刻意不参与），由门控按 `GateThresholds.max_reentry_jump_m = 0.50` 单独判；而 `evaluate_paired_sequential_benefit` 自身默认 `max_reentry_position_jump_m = 0.35`。两个界并存，读者必踩。建议统一到 0.50，或在注释里写清为什么保留 0.35。 |
| P3 | **`min_paired_observations = 4` 偏激进**：n=4 全数改善才刚好 0.596，仅高出门限 0.046。用 4 帧证据授权一次不可逆的地图提交，统计上合法但很薄。建议：候选触及关键帧数超过某阈值时要求 n ≥ 8，或在论文里把这个取舍写出来。 |
| P3 | **`recovery_ratio_G: 0.0` 仍在两处硬编码**（`evaluate_e3_orbslam3.py:469`、`evaluate_room_dark_01.py:362`）。它们是 B0 基线条目，`G(B0 vs B0) = 0` 按定义成立，不算错；但字面值与刚废弃的哨兵完全一样，日后容易被误读为实测。建议改名 `recovery_ratio_G_by_definition` 或加注释。 |
| P3 | `79dae02` 提交信息写"21/21 PASS"，HEAD 实为 22（`20047a2` 又加一条）。纯记账，不影响代码。 |

---

## 三、建议

1. 清掉 P2 的两处 None 格式化，并把重入阈值统一——这两条都是十几行的清理，但会决定别人重跑你的评测脚本时是拿到 `n/a` 还是拿到 crash。
2. `min_paired_observations` 的取舍写进论文或 supplement：4 帧的门槛是有意为之，需要说明。
3. 修完后可以推进 Action Item 8.1（FAST-LIVO2 第五宿主）与 8.2（组件消融）——门控现在是真的在把关，新实验的判决才有意义。

## 复现

```sh
python -B -m unittest discover -s slam_recovery/tests -v    # 22/22 PASS
```

Wilson 下界的两个数我按 `z=1.645` 手算复核：n=3 → 0.5258，n=4 → 0.5965，与源码注释一致。
本机未播 bag、未重跑宿主；PDF 结论来自文件元数据与提交时间比对。
