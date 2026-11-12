# 干净 A/B：声明戳 hold/snapshot + 终止戳重放（两端逐位一致）

同声明的一对：repair（发布修正云，shift −0.40）与 sham（同发布、shift 0）。宿主 `hold`/`snapshot`
带触发戳，由主循环在第一个 `lio_time ≥ 戳` 的组处理之前执行；`reprocess <frozen+100 ms>` 固定
重放终点。损坏窗口从触发戳开始。运行前声明见 `../PLAN_deferred.md`。

## 1. 两端一致（逐项）

| 项 | repair（055727Z） | sham（055931Z） |
|---|---|---|
| 冻结 | `1627785280281185627`，23 帧 | 同一值，23 帧 |
| 开段 snapshot ack（stamp/frame） | **1627785276215170048 / 221** | **同一值 / 221** |
| `reprocess` 重放区间 | **[276.281966925 .. 280.347787857]** | **同一区间** |
| `replayed` / `truncated` | **124 / 399** | **124 / 372** |
| `end_stamp` | 1627785280381185627 | 同一值 |
| `repairs applied` / leftover | **23 / 0** | **23 / 0** |
| 发布批次 | 10 / 10 / 3，synced | 10 / 10 / 3，synced |
| 门 | accepted 3.1388→**7.2960**，Wilson 0.8947，holdout 0.4137，committed 23 | accepted 3.1388→**7.2986**，Wilson 0.8947，holdout 0.4193，committed 23 |
| 偏差估计 | +0.40（MAD 0.05） | +0.40 |
| 修复 shift | **−0.40** | **0.00** |

**两端完全对齐**：snapshot stamp/frame 相同、重放起止戳逐位相同、`replayed=124` 相同、
23/23 应用、无 leftover。唯一的差别是发布云的平移（−0.40 vs 0），即测量是否被修正。

## 2. 同窗口下的差异

| 项 | repair | sham | 差 |
|---|---|---|---|
| 重放后地图 | **17811 voxels / 335054 points** | **17316 / 328516** | +495 voxels，+6538 points |
| `set_state` 时 `state_pos` | 7.696, 5.638, −0.359 | 7.701, 5.627, −0.359 | 约 **1.1 cm** |
| `resume` 时 `state_pos` | 9.506, 4.749, 0.068 | 7.754, −0.175, −0.380 | 后续帧继续后的差异 |
| 发布云逐帧 z 差 | — | — | **0.40 m**（repair −0.40 / sham 0） |

在两端窗口、候选和修复计数都一致的前提下，地图差（+495 voxels/+6538 points）和 resume 后的
状态差可以归因于**测量是否被修正**；`set_state` 位姿几乎相同（1.1 cm），因为两边用的是同一个
ICP 候选。

## 3. 边界

- 损坏是自己注入的（+0.5 body-z，60 帧）；**不声称真实修复收益、恢复成功率或质量提升**。
  这组实验证明的是"测量修复确实进入宿主原生重估，并改变了重放结果"。
- 门/阈值/σ 未动；宿主改动仅限本轮的声明戳 hold/snapshot（控制线程入队、主循环按期执行）与
  终止戳重放；详见 `../../../host_change_deferred_stamp/BUILD.md`。
- 上一轮的 `late_ms` 标注错误（ns 当 ms）已在本轮修正为真正的毫秒；本对运行日志里
  `late_ms=66.797`（约 67 ms），是相对声明戳的迟到量。

## 4. 文件

`repair/`、`sham/` 各含：`receipt.json`、`run_summary.json`（`frame_freeze` +
`repair_publish`）、`candidates.jsonl`、`candidates_detail.jsonl`、`icp_detail.jsonl`、
`relay_frames.jsonl`、`host.log`（`deferred apply`、`reprocess ... replayed/truncated/
end_stamp`、`NATIVE_REPAIR applied`）、`lifecycle_events.json`、`native_checkpoint_events.json`、
`host_control/`、`launch_pair.sh`、`recovery_node.log`、`machine_load.txt`、
`recovery_node_source.sha256`。
