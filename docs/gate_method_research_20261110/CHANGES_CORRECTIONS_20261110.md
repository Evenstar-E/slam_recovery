# 审阅修正清单（2026-11-10，对应 `06f543a` / `e2db4b3`）

范围：只改 Part 1 / Part 2 与 C-2 文档的研究产物。**0 次宿主运行、未改生产门、未应用补丁。**
A / B 的旧结论未动。

| # | 审阅点 | 改了什么 | 落在哪里 | 现在的说法 |
|---|---|---|---|---|
| 1 | 旋转控制混杂平移与再单位化 | 新协议：**纯旋转**（t=0），`transport_information(L,G⁻¹)` **搬回同一 anchor**，方向不单位化；另加纯平移与完整 SE3 两个诊断；旧读法整段保留并标注 | `p2_subspace_gate.py` 的 `_anchored_rotation_control` / `_spd_transport_control` / `_mixed_protocol_old`；`p2_subspace_gate.json` 的 `rotation_control`；`P2_GATE_FORMS.md` §0；`C2_SPATIAL_PATCH.md` 顶部警告 | 旧 producer ≤**5.5e-16**；C-2 纯旋转 room02 **0.66% / 0.39% / 20.1%**、hall01 **40.4% / 14.9% / 426%**。旧百分比标为"含平移+再单位化的混合读法"（hall 10° 旧读 103%，纯旋转 40.4%），保留不删 |
| 1b | 审阅给的精确 SPD 控制 | 复算并写进 JSON：原投影 **1** → 搬运不单位化 **1.0（差 0）** → 再单位化 **1/6**，`‖Ad v0‖²=6` | `rotation_control.spd_control`；P2 §0 表 | 再单位化本身改变被比较的量，协议必须声明 |
| 2 | r=1.0 / 24-24 是自比较，结论对象错 | 该段改名为 `tautology_check`，明确是"每个矩阵与自身最小特征向量比较"的代数恒等式；新增**actual gate 控制**直接调用 `evaluate_four_mode_gate` | `p2_subspace_gate.py` 的 `_actual_gate_control`；`p2_subspace_gate.json` 的 `gate_control`；`P2_GATE_FORMS.md` §2.1–2.3、§4、§5 | 固定触发 tx、候选 `diag(300,300,300,100,38.8889,38.8889)` → 门读 **100**、`λ_min=38.8889`、**Mode 2 accepted**：**固定方向 ≠ 最弱特征向量**。可保留的窄结论：`m_after=0 ⟺ λ_min≥2` 是全谱最小值阈值，`P=Λ⁻¹` 时等于**协方差范数腿**，不是固定方向信息腿；Loewner 是另一条件，但**不是唯一非退化形态** |
| 3 | "逐位复现"过强；需绑定 | 容差改为运行前声明的 **5e-4 相对**，每行记录 `abs_diff` / `rel_diff`；每行绑定 `bag_sha256`、`scan_sha256`、扫描戳，并记录 producer 源文件 sha256 与运行时 git HEAD | `p1_before_recompute.py`；`p1_before_recompute.json` 的 `rows` / `validation` / `_meta.producer`；`P1_INFO_LEG_NEW_PRODUCER.md` §1 | **5/5 在 5e-4 内复现；实测最大相对差 1.56e-5、绝对差 3.79e-5**。不是逐位。最近扫描与触发戳相差 **5.39 / 23.19 / 5.50 / 21.00 / 20.90 ms**，逐行记录 |
| 3b | 方向"稳定 PASS / 几乎不变"无依据 | 删除"方向稳定 PASS"与"几度"表述；改为报告夹角 **7.57°–28.46°**（cos 0.9913–0.8792），并声明**无预声明容差、未评分** | P1 §2、§6；JSON `scale_summary` 的 `alignment_angle_deg_min/max` 与 `reading` | 28.46° 不是"几度"；只作测量值 |
| 3c | κ 表述过强 | 收窄为"旧校准**不能无条件移植**"；真实两端（4.26 应通过 / 0.86 应拒绝）在新 producer 下**仍 `BLOCKED`**；不写"κ 必失效" | P1 §3、§6、§7；`C2_SPATIAL_PATCH.md` §3；`SUMMARY_A_B_C.md` §5.1 | 变化跨度 12.1×（固定方向）证明不是全局缩放；是否仍可达需 `after` |
| 3d | JSON reading 与字段矛盾 | 重写 `scale_summary.reading`、`validation.reading`；P2 的 `form2_scalar_floor_frozen.status` 改为"是协方差腿、不是信息腿" | 同上 | 文本与字段一致 |

## 复现

```bash
~/mm/micromamba run -p ~/mm/ros python -I docs/gate_method_research_20261110/p1_before_recompute.py
~/mm/micromamba run -p ~/mm/ros python -I docs/gate_method_research_20261110/p2_subspace_gate.py
```

两个脚本只读 bag 与归档；不改生产代码；C-2 补丁未应用。
