# `candidates_detail.jsonl` 的语义（写死）

## 1. 一句话

`candidates_detail.jsonl` 是**决策的输入全集**：每次决策时交给 gate 的帧集合与位姿。
它**不是** verified 集、不是 holdout 集、不是 anchor 集，也不是"被评分的点集"。
不要用它当评分分母。

## 2. 它到底装了什么

一行对应一次决策（`recovery_node.py:276` `candidate_detail_record`）：

| 字段 | 含义 |
|---|---|
| `candidate_id` | 与 `candidates.jsonl` 对齐 |
| `t_trigger_ns` / `t_decision_ns` | 触发与决策时刻 |
| `candidate_frame_ids` | 该隔离段在决策时刻已登记的**全部**帧 id（`ep.frames` 的 key） |
| `candidate_frame_ts_ns` | 与上面一一对应的帧时间戳 |
| `repaired_poses` | 与上面一一对应的 4×4 位姿（行主序 16 个数） |

来源就是 `decide()` 里的 `keys` / `repaired` / `ts_by_key`（`recovery_node.py:1199-1201`），
原样交给 `evaluate_and_commit_candidate(..., repaired_poses=...)`。
当 `candidate_source=icp_reregistration` 时，`repaired` 被替换为 ICP 重配准的输出
（`recovery_node.py:1204-1215`），此时它仍是"输入"，只是生产者不同。
`candidate_source=host_poses`（本趟）时，权姿就是宿主在隔离期自己发布的位姿。

本趟两行：`cand_0000` 13 帧、`cand_0001` 27 帧。

## 3. 真正的评分集合（分开列，别混用）

gate 在一次决策里实际使用的集合，全部在 `slam_recovery/sim/transaction_manager_node.py`
的 `evaluate_and_commit_candidate` 内构建：

| 集合 | 构造 | 用途 |
|---|---|---|
| **评分参考点云** `train_world` | `tx_mgr.get_trusted_map_points(max_pts=1500)`：隔离前 trusted map 的点采样 | holdout 的 point-to-plane NIS 参考 |
| **参考排除集** `reference_keys` | `tx_mgr.get_trusted_map_keys()`：构成参考的 kf | 不让帧给自己打分 |
| **覆盖/支持参考** `support_ref` | `support_reference()`：spatially sampled trusted map，`_RadiusIndex(..., 1.0)` | 判断一帧是否"被参考支持" |
| **可提交帧集** `committable` | `kf ⊆ candidate_frame_ids`，且不在 `reference_keys`、且 incumbent 有位姿、且 `_frame_has_reference_support` | 决定哪些帧能进 commit |
| **提交帧集** `commit_keys` | `committable` 的有序列表 | 写入 trusted map 的帧 |
| **留出帧集** `holdout_kfs` | `commit_keys` 里下标 `% holdout_stride == 0`（stride=5） | 计算 `holdout_nis` |
| **锚点** `reentry_anchor_pose` / `reentry_anchor_ts_ns` | 决策前 trusted map 里最大 kf 的位姿及其时间戳 | re-entry 包络检查 |

`candidate_frames_total`（`_last_holdout_support`）等于 sidecar 行里的帧数；其余计数
（`candidate_frames_committable` / `committed` / `deferred` / `holdout_frames_scorable`）
**只在内存里**，本驱动不落盘（`_last_holdout_support` 只被实验脚本读取）。
因此不要把 sidecar 行数当 `committable`，也不要把 `holdout_nis` 的存在理解为"有帧被提交"：
本趟两段都是 Mode 3 拒绝，`committed_pose_keys=[]`，但 `holdout_nis` 仍然被算了
（0.490 / 0.641），因为它测的是 `commit_keys` 上的留出集，而 gate 并未接受。

## 4. 归档里各集合的可见位置

| 集合 | 在归档中 |
|---|---|
| 输入全集（帧 + 位姿） | `candidates_detail.jsonl`（本 sidecar） |
| 提交帧 / 推迟帧 | `candidates.jsonl` 的 `committed_pose_keys` / `deferred_pose_keys`（本趟均为 `[]`） |
| 留出 NIS | `candidates.jsonl` 的 `holdout_nis` |
| 锚点/重入结果 | `candidates.jsonl` 的 `reentry_pos_jump_m`（结果，不是锚点本身） |
| 拒绝时未提交的帧 | `run_summary.lifecycle.events[].frames_unresolved`（58 / 86 帧） |
| 评分参考点云、支持参考点云 | **未落盘**（每次决策重算；点集是 1500 点预算的采样，不是固定集合） |
| `partial_commit` / `remaining_pending_pose_keys` | 在 report 对象里，当前驱动未写出（见 `ACCEPTANCE_CONTRACT.md` §3.1） |

## 5. 使用规则

1. 需要回答"这次决策看了多少帧/哪些位姿" → 用 sidecar。
2. 需要回答"门在哪些帧上打分" → 用 `committed_pose_keys` ∩ 每 5 帧取 1 的留出集；
   只有 `commit_keys` 非空时这个集合才非空。
3. 需要回答"参考用了多少点" → 代码里是 1500 点预算的采样，数量随地图大小变化，
   归档里没有可复现的具体点集。
4. 任何"verified / scorable / anchor"的统计，都不要以 sidecar 的行数为分母。
