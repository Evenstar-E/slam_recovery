# 复核 · db77123（street_08 / room_dark_02 留出扩展）

**复核对象**：`db7712315e6bdb34e1a024f99923be518efeac89`，新增 1240 行：`evaluate_room_dark_02.py`（409 行）、`merge_unseen_heldout_results.py`（60 行）、7 份 manifest、论文与研究报告各 2 处改动。
**方法**：源码阅读 + manifest 与 commit message 逐项对照。本机未播 bag、未重跑宿主。`python -B -m unittest discover -s slam_recovery/tests` → 18/18 PASS。

---

## 结论

**street_08 是全仓库最强的一条证据，建议保留并升级为安全主证据。**
**room_dark_02 的正文陈述与它自己的 manifest 冲突：四条臂的恢复比全部为负，却被写成"证明零调参泛化"。这一句必须改写。**

---

## 一、值得肯定：street_08

manifest `test_street_08_heldout_benchmark.json` 与 commit message 逐项一致，无修饰：

| 宿主 | clean | degraded | B6 | G |
|---|---|---|---|---|
| FAST-LIO2 | 0.1316 | 1.2996 | 0.1346 | +0.9974 |
| MM-LINS | 0.3458 | 5.2635（`Issleeping=0`） | 0.3294 | +1.0033 |
| LIO-SAM | 0.1156 | 333.2876（Max 1248.15） | 337.0601 | **−0.0113** |

关键在 LIO-SAM 这一行：B6 候选比退化态还差 3.8 m，而门控**拒绝**了它——
`cross_scan_nis_mean_b6 = 4.4145 > 2.5`、`wilson_lower_bound = 0.4626 < 0.55`、`reentry_pos_jump_m = 0.4042 ≤ 0.500`、`approved = false`。

三个原始值都写进了 manifest，且**显式传入**了 Wilson 与重入跳变，绕开了 P1-1 那条"缺测即通过"的默认路径。这说明开发侧知道正确调用方式，也知道该怎么证明安全。

这是第一次在真实未见序列上把"门控拒绝一个更差的自修复"测出来，而不是声明。建议：
- 论文把这条从 E3 段落里单独拎出来，作为 Mode 2 门控的安全主证据；
- 表里给出被拒候选的三个原始值 + 最终落到 `MODE3_SOFT_BRIDGE_WAIT`，并说明可信地图未被改动。

---

## 二、必须修：room_dark_02

### 2.1 四条臂的 G 全为负，正文却称"证明泛化"

manifest `R4_R5_DualModal_LiDAR_PlasticBag_15_35s`：

| 宿主 | clean | degraded | B6 | G |
|---|---|---|---|---|
| FAST-LIO2 | 0.1659 | 0.8958 | 0.9432 | **−0.0649** |
| MM-LINS | 0.1164 | 0.0723 | 0.0497 | **−0.5130** |
| LIO-SAM | 0.9523 | 1.1310 | 1.2753 | **−0.8081** |
| ORB-SLAM3 | 见 2.2 | 0.7614 | 0.5598 | **−1.0613** |

三个 LiDAR 宿主修复后全部变差。commit message 只引 ORB-SLAM3 的绝对 ATE（0.5598 < 0.7614），未提任何负 G——这是对同一份数据的选择性陈述。

另有一处指标失效：MM-LINS 的 degraded（0.0723）比 clean（0.1164）还好，"退化"反而让分数变好。在 sub-0.1 m 量级上该指标已不敏感，不能承担恢复证据。

### 2.2 G 的分母用错了基线，负号是算出来的

`evaluate_room_dark_02.py:336`：

```python
"clean_ate_m": round(m_orb_b2.ate_rmse_m, 4),      # 0.9513，这是 B2 退化 Atlas 的 ATE
```

把 **B2 退化运行**当成 ORB 的 clean 基线，于是：

- `G_vs_B0 = (0.7614 − 0.5598) / (0.7614 − 0.9513) = +0.2016 / (−0.1899) = −1.0613` —— 分母为负，符号翻转。这不是"恢复失败"，是算错。
- `G_vs_B2 = (0.9513 − 0.5598) / (0.9513 − 0.9513)` —— 分母 0。`compute_recovery_ratio_G`（`trajectory_eval.py:172-173`）在 `abs(denom) < 1e-9` 时**返回 0.0**。manifest 里那个 `recovery_ratio_G_vs_B2: 0.0` 是除零哨兵，读起来却像"无改善"。
- `window_G_vs_B2 = 3.7399` —— G > 1 来自极小分母：clean 窗口 RMSE 0.8863 本身就接近退化水平（B0 0.8474），分母只剩 0.1858。G > 1 在文献里不可解释，不能直接写进论文。

修法：
1. ORB 的 clean 基线改用同 manifest 第 36 行已有的 `ORB_SLAM3_B0_SingleMap.full_seq_hold_ate_rmse_m = 0.7614`，或明确标"No clean baseline, G N/A"。
2. `compute_recovery_ratio_G` 的除零分支改为返回 `None` 并由调用方标记 `N/A`。现在这个 sentinel 会被下游当成真实测量值——`G_vs_B2 = 0.0` 就是活例。

### 2.3 `dropped_frames_in_15_35s: 0` 是定义产物，不是能力

B6 的 provenance 是 `OFFLINE_CONSTRUCT`，轨迹由 LiDAR 相对运动桥接而成，本来就没有"ORB 丢帧"这一概念。写成"zero dropped frames in [15,35] s"会被读成"我们的修复让 ORB 没有丢帧"。
改为：桥接段由健康 LiDAR 相对运动构造，ORB 跟踪器在该窗口的丢帧不计入该分支；B0 228/744、B2 114/744 照旧列出。

### 2.4 旋转数字不可用

`ate_rot_rmse_deg: 93.123`（FAST-LIO2 clean）、`111.707`（Atlas）。clean 的 LiDAR 旋转误差不可能 93°——`evaluate_rotation_ate_rpe_deg` 只对齐位置，GT 与估计的坐标系未做旋转对齐，这个数就是坐标系差。
论文没有引用它们（正确），但 manifest 会被复用。建议标 `UNAVAILABLE`，或先做旋转对齐再算。

---

## 三、`paper_main.tex` 新增的那一句

原文以 "demonstrating zero-tuning generalization to unseen real natural darkness" 收尾。在四条臂全负 G 的同一条序列上，这个结论不成立。

建议改写为两段：

1. **street_08 单独成段**，正面写：真实户外未见序列，FAST-LIO2 与 MM-LINS 恢复到 clean 水平（G = +0.9974 / +1.0033），LIO-SAM 前端发散到 333 m，其 B6 候选经门控以 NIS 4.4145、Wilson LB 0.4626 被拒，系统落入 Mode 3 而未污染可信地图。
2. **room_dark_02 作为负结果如实报告**：ORB-SLAM3 分支把 ATE 从 0.7614 降到 0.5598、窗口 RMSE 从 1.0721 降到 0.3771，但同一序列上三个 LiDAR 宿主的修复均未改善（G 为负），因此该序列不构成泛化证据，而用于说明恢复器在双模态同时退化时的边界——这恰好呼应 Proposition 1（回滚不创造可观测量）与论文 Limitations 一节。

负结果 + 门控拒绝，比一句空泛的"泛化"更能建立可信度，也堵住审稿人自己去翻 manifest 的路径。

---

## 四、`merge_unseen_heldout_results.py`

纯合并：无筛选、无硬编码、把整份 manifest 原样嵌入 summary。因此上面的负结果也在 `unseen_heldout_all_sequences_summary.json` 里。**脚本是对的，问题在 prose，不在工具。**

---

## 五、建议顺序

| 级别 | 事项 |
|---|---|
| 阻断 | room_dark_02 的论文句子按第三节改写，正文或附录明示三条负 G |
| 阻断 | 修 `evaluate_room_dark_02.py:336` 的 clean 基线；`compute_recovery_ratio_G` 除零改返回 `None` 并标 N/A |
| 高 | `dropped_frames` 措辞、`ate_rot_rmse_deg` 标 `UNAVAILABLE` |
| 高 | street_08 升级为 Mode 2 安全主证据，表内给出被拒候选三值 |
| 中 | 给 `merge_unseen_heldout_results.py` 的输出加一张"G 与分母"列，避免 0.0 sentinel 再被误读 |

---

## 复现

```sh
python -B -m unittest discover -s slam_recovery/tests -v     # 18/18 PASS
```

manifest 数字与 commit message 的逐项对照见本文第一、二节；负 G 由 `test_room_dark_02_heldout_benchmark.json` 直接给出，无需重跑。
