# 解耦偏差估计：bias 合理，但修复只到了 20/26，重放被 receipt 屏障正确拦下

运行前的容差声明见同目录 `PLAN.md`（`|bias−0.5| ≤ 0.15 m` 记为合理；超出也照发照跑）。

## 1. 运行

| 项 | 值 |
|---|---|
| run | `fl_native_20261112T045238Z_92133` |
| 声明 | 同 bag、同绝对戳 `1627785276215170145`、同 relay 窗口 `[1627785276208000000, 1627785282215170145)`、margin 4.0、`candidate_source=icp_reregistration` |
| 驱动 | 提交 `bfe2939`（sha 见 `recovery_node_source.sha256`） |
| 宿主 | 二进制 `0d7e23de…`，0 行改动 |
| 终态 | `HEALTHY` |

## 2. 偏差估计（合理）

候选 26 帧，逐帧在 incumbent 位姿下做 body-z 一维搜索（步长 0.05，参考 24336 点）：

| 量 | 值 |
|---|---:|
| 逐帧 median | **+0.40 m** |
| MAD | **0.05 m** |
| 逐帧范围 | 0.25 – 0.55 m |
| 帧数 | 26 |
| 声明容差 | ±0.15 m |
| `within_declared_tolerance` | **true**（|0.40−0.50| = 0.10） |

符号与方向都对：注入 +0.5 body-z，估计 +0.40，修复平移 `-0.40`。

## 3. 门与修复传输

- 门：**accepted**，`MODE2_ATOMIC_COMMIT`；before 3.1341 / after 6.8216（阈值 6.2682）、
  Wilson 0.9057、holdout 0.3882、committed 26 / deferred 96。
- 修复发布：`published=26`。
- 宿主回执：**`repair_received=20`、`repair_queued=20`、`repair_applied=0`、`repair_dropped=0`**。
- `synced=false` → `_repair_gate` 拒绝发 `reprocess`：`host.log` 里 **没有 `reprocess #`**，
  也**没有 `NATIVE_REPAIR applied`**；隔离段照常等待超时 → `rearm` → `resume`，终态 HEALTHY。

## 4. 断点：26 条里 6 条没有到达宿主回调

宿主订阅 `/native_recovery/repaired_scan` 的队列是 **20**（`LIVMapper.cpp:320-321`）。驱动在
一次决策里连续发布 26 条，回调还没处理完，发布端已经把队列灌满——**6 条在进入回调之前就被
丢弃**，所以宿主的 `repair_received` 只到 20（`repair_dropped=0` 是宿主内部队列溢出计数，
不包含传输层丢的这 6 条）。

receipt 屏障按设计工作：它看到 20 < 26，就不发重放；否则 `reprocess` 会用一套缺 6 帧的修复
云重放，和上一轮 `repairs applied=0` 一样不可信。这是"屏障正确、传输不够"。

## 5. 另外记录：损坏窗口内宿主自身发散

最终快照的 `state_pos = (-1822.8, 1488.2, -1387.2)`——0.5 m 的统一 z 偏置在冻结地图上把宿主
LIO 推得很远（`voxels=582146`）。这是宿主在损坏输入下的原生行为，不是修复造成的；修复链没有
重放，所以这段发散没有被纠正。

## 6. 下一步最小修法（未实施）

1. **发布节流**：逐条发布之间 `sleep 10–20 ms`（26 条约 0.3–0.5 s），让宿主回调（每条约
   5–10 ms）跟上；这是驱动侧一处改动，宿主 0 行。
2. 或**分批 + 回执**：每批 ≤20 条，发完一批用 status 等 `repair_received` 累计到本批，
   再发下一批；同样只用现有 ack。

按任务要求，本轮 bias 合理但修复没有真正应用，**没有跑对照**，停在这里报断点。修完需要再跑
一次同声明受控 run，才能验证 `repair_received/applied=26`、`reprocess` 使用修复云以及地图/轨迹
的变化。

## 7. 文件

`PLAN.md`（运行前声明）、`receipt.json`、`run_summary.json`、`candidates.jsonl`、
`candidates_detail.jsonl`、`icp_detail.jsonl`、`relay_frames.jsonl`、`host.log`、
`lifecycle_events.json`、`native_checkpoint_events.json`、`host_control/`、`launch_pair.sh`、
`recovery_node.log`、`machine_load.txt`、`recovery_node_source.sha256`。
