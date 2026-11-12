# Sham 对照：同发布、同回执、零修正 —— 重放跨度仍未对齐

运行前声明见上一层 `../PLAN_sham.md`。与 `../repair/` 同 bag/戳/窗/margin/冻结/候选源；
同样分批（23 条 → 10/10/3）、同样累计回执、同样时序；发布的是**未修正**的损坏云（shift 0）。

## 1. 结果

| 项 | sham |
|---|---|
| run | `fl_native_20261112T052437Z_114016` |
| 冻结 | 同一戳 `1627785280281185627`，**23 帧**（`frames_after_freeze=353`） |
| 门 | accepted，Mode 2：3.1341 → **7.3321**，Wilson 0.8947，holdout 0.4114，committed 23 |
| 偏差估计 | +0.40（MAD 0.05） |
| 发布 | 3 批 **10/10/3**，每批 `received_ok=true`，`final=23`，**synced=true** |
| 宿主 | `repair_received=23 repair_applied=23` |
| 重放 | **686 帧 / 22.81 s** [275.147 .. 297.959]，map 21744 voxels/408356 |
| set_state / resume `state_pos` | 7.702, 5.648, −0.365 / 7.229, 5.373, −0.375 |

## 2. 与 repair 臂对照

| 项 | repair（051523Z） | sham（052437Z） |
|---|---|---|
| 冻结 / 候选帧 | 同戳 / 23 | 同戳 / 23 |
| 门 after / Wilson / committed | 7.3427 / 0.8947 / 23 | 7.3321 / 0.8947 / 23 |
| 发布 shift | **−0.40** | **0.00**（差 0.40 m，符合预期） |
| received/applied | 23/23 | 23/23 |
| 重放帧 / 跨度 | **815 / 27.14 s** [276.349..303.492] | **686 / 22.81 s** [275.147..297.959] |
| 重放后地图 | 24503 voxels/473187 | 21744 voxels/408356 |
| set_state `state_pos` | 7.706, 5.651, −0.366 | 7.702, 5.648, −0.365 |

**对齐的部分**：冻结戳、候选人口（23）、门结果（Wilson 相同，after 差 0.01）、修复计数
（23/23 vs 23/23）、以及 set_state 位姿（差约 **3 mm**）。修复云与 sham 云的逐帧 z 差就是
估计的 bias：0.40 m（repair shift −0.40，sham 0），与声明一致。

**仍未对齐**：重放跨度 **27.14 s vs 22.81 s（差 4.33 s）**。上一轮 dry-run 与 repair 差
5.3 s，本轮 sham 与 repair 差 4.33 s——**5.3 s 没有作为"分批+回执"的固定代价复现**。
原因是决策之后、`reprocess` 发出之前的**墙钟计算时间**（门评估 + 逐帧偏差搜索 + 发布/回执）
随负载变化，而 bag 是实时回放的：驱动多花几秒，宿主就多捕获几秒的帧进入重放缓冲。sham 与
repair 的这段计算量相近，但仍受负载影响。

因此地图 24503 vs 21744 **仍不能干净归因**；能干净比较的是人口、门、修复计数、set_state
位姿（3 mm）和逐帧 z 差（0.40 m）。

## 3. 断点与下一步（未追加运行）

要让重放缓冲在两次之间逐帧一致，需要把缓冲的终点绑定到**冻结决策帧**而不是"命令被应用
时刻"：

1. 宿主侧改动（需批准）：`reprocess` 携带一个终止 stamp，重放只到该 stamp；或快照/捕获在
   驱动发出 `reprocess` 时停止。
2. 驱动侧（不改宿主）：在冻结帧之后立即记录目标帧，然后无论发布/回执花多久，都用一个固定
   bag 时间的命令触发重放——但命令仍会晚到，宿主仍会多捕获，除非宿主支持终止 stamp。

按"不对齐就停、不追加运行"的要求，本轮停在这里。门/阈值/σ/宿主未动；损坏为自注入，不声称
修复收益。

## 4. 文件

同 `../repair/` 结构：`receipt.json`、`run_summary.json`（含 `frame_freeze` 与
`repair_publish.sham=true`）、`candidates.jsonl`、`candidates_detail.jsonl`、
`icp_detail.jsonl`、`relay_frames.jsonl`、`host.log`、`lifecycle_events.json`、
`native_checkpoint_events.json`、`host_control/`、`launch_pair.sh`、`recovery_node.log`、
`machine_load.txt`、`recovery_node_source.sha256`。
