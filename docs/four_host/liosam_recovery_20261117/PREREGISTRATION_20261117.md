# LIO-SAM 恢复层接线与首次两事件 run：预登记（2026-11-17，run 前写定）

**用户决定**：2026-11-17 选定「① 转 LIO-SAM/ORB」。本文件记录 LIO-SAM 的接线内容与首次 run 判据。

## 1. 宿主改动（源码级）

`LIO-SAM/src/mapOptmization.cpp` 新增原生恢复通道（约 230 行，单文件、单进程）：

| 命令 | 行为 |
|---|---|
| `status` / `capabilities` | 写 `ack` / `capabilities.json` |
| `hold` | 置 `nr_hold`；扫描回调仍跟踪与发布，但**跳过 `saveKeyFramesAndFactor()` 与 `correctPoses()`**（不写关键帧、不加因子） |
| `snapshot` | 复制 `cloudKeyPoses3D/6D`、`cornerCloudKeyFrames`/`surfCloudKeyFrames`、`isam->getFactorsUnsafe()`、`isam->calculateEstimate()`、当前 `transformTobeMapped` |
| `restore` | 恢复上述容器，并用 `new ISAM2(params)` + 一次 `update(graph, values)` 重建图 |
| `resume/release` | 清 `nr_hold` |

带 stamp 的 `hold`/`snapshot` 会**延迟到扫描回调**在「第一个到达该 stamp 的帧」之前执行——与 FAST-LIO v9 的边界语义一致。

**声明（`capabilities.json`）**：`snapshot/restore/hold = YES`；`reprocess = NO`（本接线没有输入缓冲，
不假装能重放）；`measurement_relay = NO`（尚未接 `/native_recovery/repaired_scan`）；
`native_reset_under_hold = not_applicable`（LIO-SAM 无原生 reset 路径）。
**未改**：LIO 数学、iSAM2 噪声模型、关键帧策略、门阈值、ICP。

## 2. run 声明

| 项 | 值 |
|---|---|
| 命令 | `tools/run_two_event_liosam.sh OUT campus_1\(2\)-003.bag 118` |
| 事件 | E1 `1711547493390621184`（bag **40 s**）、E2 `1711547533390621184`（bag **80 s**）——**都早于已知输入退化窗 120–140 s** |
| 回放 | `PLAY_RATE=0.5`（非实时证据），`--duration 118` s bag，E2 后有 38 s bag 尾段 |
| 监护参数 | 与 v4 相同、按 0.5× 做 bag 等价：pose-stale 30、signal-window 60、hib-max 180、wait-limit 40、repair-sync 10、first-grace 120 |
| 契约 | **不传 `--require-contract`**：`reprocess=NO`、`native_reset_under_hold=not_applicable` 会使契约检查不通过。该事实写入 `pre_run.txt` 与报告，不隐藏 |
| 二进制 | `lio_sam_mapOptmization` sha `f7733000…`（含通道） |

## 3. 判据

| 观察 | 含义 |
|---|---|
| `ctl/capabilities.json` 存在且 `hold/snapshot/restore=YES` | 通道在线且声明一致 |
| E1/E2 各有 `hold → snapshot → restore → resume` ack，`valid=1` | 两事件生命周期在单进程宿主上可执行 |
| `checkpoint_check.status` | 记录是否 `AT_OR_BEFORE_BOUNDARY`；本宿主首次，不预设 |
| 尾段：E2 之后 `/lio_sam/mapping/odometry` 持续到 118 s | 接回后持续运行 |
| `gate.accepted` / `repair.clouds_published` | 若 0，则仍无写回；原因按 `candidates.jsonl` 记录，不解释为接线失败 |

## 4. 已知限制（run 前声明）

- LIO-SAM 无 `Issleeping/Isbuilding` 话题，driver 的宿主状态推断不适用；静默只会来自真故障或持有的副作用；
- restore 用「全图重建」实现，重建耗时与图规模成正比，会体现在 ack 延迟里；
- 无输入缓冲：`reprocess` 未实现，接回输入若发生也只能走未来版本的 relay；
- 0.5× 非实时证据。

## 5. 结果

（run 后填写。）
