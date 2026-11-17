# MM-LINS 两事件 run v4：0.5× + hold + 监护参数 bag 等价化（2026-11-17，run 前写定）

**用户决定**：2026-11-17「① 0.5×+hold+监护参数 bag 等价化 授权run」。

**目的**：用修法 A 之后的后端，在同速率下重跑带 hold 的两事件链，回答两件事——
(1) `alaserPGO` 是否还崩；(2) 干扰项去掉后，链路能否跑到 E2 之后。

## 1. 改动（只有监护参数，全部 ×2）

0.5× 回放时，一个「墙钟 W 秒」等于 `W×rate = W/2` 秒 bag 时间。为了让判据的 **bag 时间含义**
与 v1（1.0×）一致，所有墙钟监护参数乘 2：

| 参数 | v1/v2 | v4 | bag 等价 |
|---|---|---|---|
| `--pose-stale-sec` | 15 | **30** | 15 s |
| `--host-signal-window-sec` | 30 | **60** | 30 s |
| `--host-hibernation-max-sec` | 90 | **180** | 90 s |
| `--wait-limit-sec` | 20 | **40** | 20 s |
| `--repair-sync-timeout-sec` | 5 | **10** | 5 s |
| `--first-pose-grace-sec` | 60 | **120** | 60 s |

**未改**：门阈值、`IcpConfig`、候选源（`host_poses`）、`arm_lead=3`、`confirmation_margin=2.0`
（后两者按位姿戳比较，本来就是 bag 时间）、bag、E1/E2、前端二进制、后端二进制（`cc99d2ea…`，含修法 A）。

## 2. run 声明

| 项 | 值 |
|---|---|
| 命令 | `POSE_STALE=30 SIGNAL_WINDOW=60 HIB_MAX=180 WAIT_LIMIT=40 REPAIR_SYNC=10 FIRST_GRACE=120 PLAY_RATE=0.5 DRIVER_DUR=1120 tools/run_two_event_mmlins.sh OUT campus_12_fl.bag 470` |
| 时长 | 回放约 940 s 墙钟 + 20 s 排空 |
| 判据表 | 同 `PREREGISTRATION_20261117.md` §3 |

## 3. 判据

| 观察 | 含义 |
|---|---|
| `alaserPGO` 全程存活且有 `/aft_pgo_odom` | 修法 A 之后崩溃未再出现（仍不能证明 A 是原因，但两次同条件对照有意义） |
| `pgo.log` 出现 `skipping sleeping map N` | 空休眠图路径被走到，且守卫拦住了它——**这才是修法 A 的直接证据** |
| E1/E2 两个 `hold → snapshot → restore → resume` 都有 ack | 事件 2 也在后端在线时完成 |
| E2 之后宿主仍发布且 driver 未提前退出 | 监护参数换算生效 |
| `repair.clouds_published` | 若 >0 则首次出现写回；若 0 则仍无写回 |

## 4. 不声称（预登记时写死）

- 本 run 仍是 **非实时证据**：0.5× 回放不等于在线性能；
- 监护参数换算不等于门放宽：门阈值一字未改，候选被拒仍是证据；
- 若 PGO 仍崩且守卫未触发，说明根因不在 `performSimilarClosure`，需要栈回溯/core dump 另定位；
- 若配对收益仍为 0，不据此宣称「修复无价值」——只能说明在当前候选与门下达不到 accepted。

## 5. 结果

见 `REPORT_V4_20261117.md` 与 `two_event_mmlins_v4_20261117/`。要点：PGO 全程存活、守卫触发 819 次、
E1 检查点首次 `AT_OR_BEFORE_BOUNDARY`、E2 尾段存在；门仍 0 accepted、`clouds_published=0`。
