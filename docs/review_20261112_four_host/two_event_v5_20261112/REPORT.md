# 同一实例：修复接回 → 第二事件 → 尾段（宿主 v5）

同 bag、宿主 v5（库 `9e7d8cdf…`）、`--detection off`、`candidate_source=icp_reregistration`、
margin 4.0、wait limit 2.0。两个绝对戳都用 `--scripted-trigger-stamps`：

- 第一事件 `1627785276215170145`（损坏 relay 窗口从该戳起 6 s，到 `1627785282215170145`）；
- 第二事件 `1627785308048271418`，**不加损坏**。

## 1. 结果

| | 事件 1 | 事件 2 |
|---|---|---|
| 触发（bag ns） | 1627785276215170145（kf 146） | 1627785308048271418（kf 422） |
| 决策 | 1627785280481083632（+4.27 s） | 1627785312254862785（+4.21 s） |
| 候选帧 | 23 | 40 |
| 门 | **accepted Mode 2**：before 3.1388 / after 7.3114，Wilson 0.8947，holdout 0.4137，committed 23 | **refused Mode 3**：before 22.0638 / after 18.2156，Wilson 0.8954，holdout 0.9730（信息量增益不过 Mode 2） |
| 关闭（wait limit） | 1627785289417330980 | 1627785319183924675 |
| rearm（trusted version） | 102 | 246 |
| 原生 | hold → **reprocess**（repairs applied=23；`replayed_within_end=124 replayed_suffix=373`；**无 set_state**）→ resume | hold → **restore** → resume |
| 重放 | 497 帧 [276.281966925 .. 292.825729847]，地图 20838 voxels/379892 points | — |

`candidates.jsonl` **2 行**；`lifecycle.events` **4 条**（两次 close + 两次 rearm）；终态
**HEALTHY**，`quarantine_open_at_exit=false`。原生计数：holds=3、resumes=2、restores=1、
reprocesses=1。

## 2. 时间线与帧数

- 触发 1 → 触发 2：**276 帧**（31.83 s）；
- 第一次 close（289.417）→ 触发 2：**186 帧**（18.63 s）；
- 触发 2 → bag 末帧（320.909）：**122 帧**（12.86 s）；
- `frames.consumed_after_first_decision=326`；第一段重放的后缀到达 292.826，之后宿主继续到
  第二触发；第二段关闭在 319.184，尾段约 1.7 s。

## 3. 第一段：修复 + 后缀重放 + 跳过写回

- 偏差估计 +0.40 m、发布 23 条、`synced=true`、宿主 `repair_received/applied=23`；
- `reprocess #1`：124 within-end + **373 suffix**，终止戳 1627785280381185627；
- `episode.meta.replay_suffix=373`、`native_writeback_skipped={reason:"replay_suffix"}`、
  `native_writeback` 为空——**没有 set_state**；
- resume 在 rearm 后发出（`trigger=rearm`），状态/地图停在重放边界（292.826），没有被拉回
  候选末帧。

## 4. 第二段：滚动 checkpoint（已声明边界）

预排的武装 `hold/snapshot` 只针对 `min(stamps)`（第一事件），第二事件按**滚动 checkpoint** 进入；
本 run 第二段是拒绝路径，原生动作是 `restore`（不是 `reprocess`），宿主回滚到当时的滚动
checkpoint 并 resume，未观察到异常。这条边界按要求照实记录，没有改机制。

第二段候选 40 帧、Mode 3 拒绝（Wilson 0.8954 本身过 0.55，但信息量增益 18.22 < 2×22.06），
关闭 → rearm（v246）→ resume；终态 HEALTHY。

## 5. 边界

- 损坏只注入第一段（+0.5 body-z，60 帧）；第二段无损坏。
- 不声称修复收益；门/阈值/σ 未动；可用性诊断继续暂停，未改检测。
- 第二段使用滚动 checkpoint 是当前机制已声明的边界，不是失败；若以后要让第二段也用武装
  checkpoint，需要在 `min(stamps)` 之外逐个预排，这是新决定。

## 6. 文件

`receipt.json`、`run_summary.json`、`candidates.jsonl`、`candidates_detail.jsonl`、
`icp_detail.jsonl`（2 行）、`relay_frames.jsonl`、`host.log`（`reprocess` 的 within/suffix、
`NATIVE_REPAIR applied`、两次 close/rearm 的日志）、`lifecycle_events.json`、
`native_checkpoint_events.json`、`host_control/`、`launch_pair.sh`、`recovery_node.log`、
`machine_load.txt`、`recovery_node_source.sha256`。
