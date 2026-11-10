# `tau_info` 量级证据（2026-11-10，只整理既有记录，未改代码、未改阈值）

> **`OLD_CRITERION`（2026-11-10）**：本文的判定使用 `weak_dir_info_after >= tau_info = 25`。该判据已被 `1917e16` 取代为 `after >= tau_abs_min=3.0 且 after >= tau_info_kappa=2.0 * before 且 gain > 0`。本文的**数值**是归档测量，仍然有效；基于旧判据的**结论**必须单独标注，新旧不得进同一张表。


目的：B10 的 `G` 臂与 `Q` 臂是否再次重合，取决于门下"弱方向信息"这一腿。这里把**已经记录在案**
的数值整理出来，说明 `tau_info = 25` 与当前评价基下的实际量级是否同尺度。
**本文不改任何阈值**，只作为预注册改动的输入。

## 1. 这个判据在做什么

- 定义：`GateThresholds.tau_info = 25.0`，判据是 `weak_dir_info_after >= tau_info`；
- `weak_dir_info_before` 由触发帧自己的扫描算：`compute_6dof_point_to_plane_fim(scan_body,
  sigma_meas_m=0.075)`，再 `transport_information(fim, pose)` 搬到触发帧 body 基
  （`transaction_manager_node.py:211`、`:247`）；
- `weak_dir_info_after` 由候选各帧的世界点 FIM 取平均再投影（`:637` 起，同样 `sigma=0.075`）；
- 两者都**不受** NIS 的 `sigma_meas_m` 影响——这条很关键，见 §3。

## 2. 既有记录里的全部取值（16 次决策，全部来自 `/tmp/fl_native_*`）

| 运行 | σ | 候选来源 | `info_before` | `info_after` | after/before |
|---|---:|---|---:|---:|---:|
| `025831Z` | 0.12 | host_poses | 39.05 | 0.00 | 0.00 |
| `030300Z` | 0.12 | host_poses | 39.05 | 0.00 | 0.00 |
| `030656Z` | 0.12 | host_poses | 40.23 | 34.47 | 0.86 |
| `030931Z` | 0.12 | host_poses | 40.23 | 34.47 | 0.86 |
| `031851Z` | 0.12 | host_poses | 40.23 | 34.47 | 0.86 |
| `032515Z` | 0.12 | host_poses | 40.23 | 34.47 | 0.86 |
| `035239Z` | 0.884 | host_poses | 1.1019 | 4.6458 | 4.22 |
| `035544Z` | 0.884 | host_poses | 1.1019 | 4.6199 | 4.19 |
| `035825Z` | 0.884 | host_poses | 1.1019 | 4.6281 | 4.20 |
| `042426Z` | 0.884 | host_poses | 1.1019 | 4.6342 | 4.21 |
| `043148Z` | 0.884 | host_poses | 1.1019 | 4.6472 | 4.22 |
| `044250Z` | 0.884 | host_poses | 1.1019 | 4.6990 | 4.26 |
| `044830Z` | 0.884 | host_poses | 1.1019 | 4.6612 | 4.23 |
| `050737Z` | 0.884 | icp_reregistration | 1.1019 | 0.9746 | 0.88 |
| `051542Z` | 0.884 | icp_reregistration | 1.1019 | 4.0293 | 3.66 |
| `051744Z` | 0.884 | icp_reregistration | 1.1019 | 4.4701 | 4.06 |

## 3. 结论一：`tau_info = 25` 落在"同一 bag、同一配置"的自然变动范围内

`info_before` 只由**触发帧**决定（扫描点 FIM，`sigma=0.075`，与 NIS 的 σ 无关）。
在这一个 bag 上它取了两个值：**40.23**（σ=0.12 那几趟，触发在启动早期）和 **1.1019**
（σ=0.884 那几趟，触发在注入 onset）。**跨度 36.5 倍。**

`tau_info = 25` 正落在这两端之间：启动早触发那一帧的 `info_before` 就有 40，本身就高于阈值；
而 onset 触发那一帧只有 1.10，无论候选多好都只能到 4.6。

**所以拒绝与否首先由"哪一帧触发"决定，而不是由候选决定。** 这与 σ 那条是同一类结构问题：
一个常数阈值跨不过自然范围。

## 4. 结论二：两种候选来源落在同一条腿

| 候选来源 | `info_after` 范围 | 证据腿 | 最终拒绝 |
|---|---:|---|---|
| `host_poses` | 4.62 – 4.70 | PASSED（Wilson 0.759） | 信息腿 |
| `icp_reregistration` | 4.03 – 4.47 | PASSED（Wilson 0.902） | 信息腿 |

两个来源、证据腿都过、都停在 `tau_info`。**这是"B10 的 `G` 会等于 `Q`"的直接原因**——
不是候选拿不到，是信息阈值与当前量级不同尺度。

## 5. 结论三：`min_eig_rot` / `min_eig_trans` — **UNAVAILABLE**

这两个量只存在于 `HealthWindow`（`transaction_manager_node.py:228-229`），**没有任何一趟把它写进
summary 或 receipt**。我核过全部 16 个运行目录：`min_eig_rot`、`min_eig_trans`、
`weak_dir_info_gain`、`posterior_cov_norm`、`propagated_cov_norm` 一个都没有落盘。

所以本文给不出它们。要拿到只有两条路，都需要额外计算：

1. 在 `_record_diag` 里逐帧记录（每帧多一次 FIM，是新增计算，未做）；
2. 离线按 `frame_diagnostics` 里的触发帧时间戳回到 bag 里取那一帧扫描重算 FIM（不做宿主运行，
   但是新计算）。

## 6. 单一阈值能否同时满足两头：算术上不能

- 要让 `icp_reregistration` 的候选通过（`after ≈ 4.5`），阈值必须 **≤ 4.5**；
- 要让启动早触发那几趟不通过（`after ≈ 34.5`），阈值必须 **> 34.5**。

两个要求不相容。**这与 σ 那条结论同型：不是标定精度问题，是判据没有对评价基归一。**

## 7. 边界（防止这份文件被当成改动）

- **没有改 `tau_info`，没有改任何阈值**，也没有改 `weak_dir_info_*` 的计算方式；
- 全部数值来自既有 `candidates.jsonl`，逐条可核；
- 这张表能支持的是"提出预注册改动"，不是"现在动手"。
