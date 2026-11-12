# INJECTION 测量修复：一次受控运行

任务：声明式损坏 + 测量级修复 + 受控接纳整链（kf 132 绝对戳、margin 4.0、`--detection off`）。
本轮**只跑一次**；结论是"传输链成立，测量修复本身不成立"，原因在 §3，不掩饰。

## 1. 装配与身份

| 项 | 值 |
|---|---|
| 运行 | `fl_native_20261112T043602Z_79001` |
| bag | `/tmp/fastlivo/hall01_two_event_v1.bag`，sha `c3e905da…` |
| 宿主二进制 | `0d7e23de…`（未变）；宿主 0 行改动 |
| 驱动源码 sha | `90acfca9…`（`recovery_node_source.sha256` 原件在目录；对应提交 `cd90e12`） |
| 触发 | 绝对位姿戳 `1627785276215170145`，margin 4.0 s |
| 标签 | `CONTROLLED_INTERFACE_TEST` + `INJECTION_DECLARED_Z_BIAS` |
| 终态 | `HEALTHY`，wall 106.6 s |

**损坏端（relay）**：`corrupt_relay` 订阅 `/velodyne_points_raw`、发布 `/velodyne_points`；
窗口 `[1627785276208000000, 1627785282215170145)`（触发前 0.7 s 到触发后 6 s），窗口内每帧
body 点 `z += 0.5`，窗口外原样透传。`relay_frames.jsonl` 记录：**60 帧被移位、538 帧原样**；
候选的 25 帧全部在移位集合内（逐帧核对）。

## 2. 门与修复链（都走通了）

| 项 | 值 |
|---|---|
| 候选源 | `icp_reregistration`（否则修复后的位姿无法过门） |
| Mode 2 | accepted：before 3.134 / after 7.299 / Wilson 0.9023 / holdout 0.4285 |
| committed / deferred | 25 / 81 |
| 修复发布 | **published 25，`synced=true`** |
| 宿主接收/应用 | ack `repair_received=25 repair_applied=25 repair_dropped=0` |
| 重放 | `reprocess #1: 382 frames replayed … repairs applied=25 queued=0`，`leftover 0` |
| 顺序 | hold → 发布 25 条 → status 收到 25 → reprocess → set_state → rearm 后 resume |

时间（wall）：hold 212.25；reprocess 216.37→220.87（4.5 s 重放）；set_state 220.87→221.37；
resume 221.37→221.87。命令串行化与 receipt 屏障都按设计工作。

## 3. 关键结果：估计出的偏差是 0.003 m，不是注入的 0.5 m

`repair_publish.bias_z_m = 0.0029`。也就是说，25 条"修复云"只被平移了 3 mm，基本等于损坏云；
`repair_applied=25` 是**计数**，不是测量效应。

原因（实测 + 机理）：

- 本次 ICP 的修正量是 **0.027 m 平移 / 0.216° 旋转**（`icp_detail.jsonl`：`ITERATION_LIMIT`，
  20 次迭代，残差 0.050 m，未收敛），不是 0.5 m。
- 机理是**量测与位姿的规范自由度**：统一的身体系 z 偏置会被 LIO 吸收成位姿偏移。宿主在损坏
  窗口内用它自己的状态补偿了这 0.5 m，于是"损坏点云 + 偏移位姿"落在世界里的位置和干净点云
  一致；再拿**宿主位姿**把点云投到可信地图上做点面配准，就没有 0.5 m 的信号可看，只剩 0.03 m。
- 旁证：同一 bag 戳上，注入 run 的触发位姿与无注入 run（`022158Z`）相差
  `[0.72, 0.48, -0.03] m`（世界系；身体 z 在该姿态下并不等于世界 z），而 ICP 修正仍只有 0.03 m。
  位姿吸收了偏差，地图配准看不见它。

这与 `REPAIR_GAP.md` §2 的推导是同一件事的另一面：位姿修正与测量修正在地图配准下不可区分；
**用宿主位姿做初值**时，估计器只能看到残余（3 mm）。

## 4. 与上一 run（`repairs applied=0`）逐项对照

| 项 | `022158Z`（无修复） | 本次（INJECTION + 修复） |
|---|---|---|
| 候选源 | `host_poses` | `icp_reregistration` |
| before / after | 3.1388 / 6.6761 | 3.134 / 7.299 |
| Wilson / holdout | 0.9197 / 0.4412 | 0.9023 / 0.4285 |
| committed | 31 | 25 |
| reprocess 帧 | 416 | 382 |
| `repairs applied` | 0 | **25** |
| 地图（checkpoint → 重放后） | 15161→19194 voxels | 14782→18032 voxels |
| resume 时 `state_pos` | 8.390, 8.518, −1.145 | 4.105, 7.385, −0.016 |

**不能把地图/轨迹差异归因于修复**：两次的候选源与候选窗都不同（31 vs 25 帧），差异是混合的。
要做干净 A/B，需要在同一 `icp_reregistration` + 同一窗口下再跑一次 `--repair-publish` 关闭的对照；
本轮只有一次运行。

## 5. 最小修法（未实施，等批准后再跑）

偏差在"宿主位姿"下不可见，但在**独立位姿**下可见。可信地图已经给出独立位姿：门用的
`extrapolate_incumbent`（最后 5 个 trusted keyframe 的常速外推）。把修复估计的配准初值从宿主
位姿换成 incumbent 位姿：

- `reregister_segment(scans, incumbent_poses, reference)` → `ΔT_inc`；
- `bias = median_k( e_z^T R_inc[k]^T Δt_inc )`，预期 ≈ +0.5；
- 候选位姿用 `ΔT_inc · incumbent`（与修复一致的、被纠正的轨迹），`set_state` 写同一个最终位姿；
- 修复云按 `bias` 平移。

这是 `_icp_candidate` 的初值改动（约 15 行 + 单测），需要再跑一次受控 run 才能验证
`bias≈0.5` 与重放轨迹的变化。本轮按"一次 run"的预算没有实施。

## 6. 能/不能声称

- 能声称：relay 的窗口与字节级移位正确（60/538，候选 25 帧全在窗内）；驱动保留了 scan stamp
  与原始点云；25 条修复云发布、宿主收到并应用、重放替换成功（`leftover 0`）；receipt 屏障与
  顺序正确。
- 不能声称：修复改变了估计；注入的 0.5 m 偏置被扣除；任何修复收益或成功率。计数非零不等于效应。
- 门/阈值/σ 未动；宿主 0 行改动。

## 7. 文件

| 文件 | 内容 |
|---|---|
| `receipt.json` / `run_summary.json` | 运行收据与完整汇总（含 relay/injection 字段） |
| `candidates.jsonl` / `candidates_detail.jsonl` / `icp_detail.jsonl` | 门结果、候选帧集、ICP 修正量 |
| `relay_frames.jsonl` / `relay.log` | 逐帧移位记录（60 帧）与窗口参数 |
| `host.log` | 宿主全文：`[NATIVE_REPAIR] received/applied`、`reprocess #1 ... repairs applied=25` |
| `host_control/`、`launch_pair.sh`、`recovery_node.log`、`machine_load.txt` | 命令链、配方、载荷 |
| `recovery_node_source.sha256` | 驱动源码身份 |

## 8. 后续：incumbent 初值的第二次尝试

`incumbent_init_refused/REPORT.md`：同声明、同窗口，只把 ICP 初值换成 incumbent。结果 ICP 修正
从 0.027 m 放大到 **0.815 m**（偏差可见），但拟合未收敛（706 inliers，0.5 m 对应门限），候选被
Wilson 0.2855 拒绝，**没有发布修复、没有 bias 实测**。按任务规则没有跑对照，断点与下一步写在
该报告里。

## 9. 后续：解耦偏差估计的第三次尝试

`decoupled_bias/REPORT.md`：同声明、同窗口；候选保持宿主位姿 ICP（accepted），偏差改用
incumbent 位姿下的 body-z 一维搜索。结果 **bias median +0.40 m（MAD 0.05，26 帧，容差内）**，
门 accepted；但宿主订阅队列只有 20 条，26 条一次性发布丢了 6 条，`repair_received=20`，
receipt 屏障拒绝重放（无 `reprocess #`、无 applied）。断点与发布节流的修法写在那个报告里。
