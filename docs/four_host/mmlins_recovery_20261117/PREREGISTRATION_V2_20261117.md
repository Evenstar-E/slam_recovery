# MM-LINS 两事件 run v2：预登记补充（2026-11-17，run 前写定）

**用户授权**：2026-11-17「推送，授权」——授权在 v1 之后**再跑一次有界 run**，用于修正
`PREREGISTRATION_20261117.md` §4 暴露的时机缺陷（检查点 `LATE_AFTER_BOUNDARY`）。

## 1. 与 v1 的差异（只有一项）

| 项 | v1 | v2 |
|---|---|---|
| `PLAY_RATE` | 1.0 | **0.5** |

其余全部不变：同一 bag（sha `a924b5f9…`）、同一 E1/E2 声明戳、`host_poses` 候选、`--detection off`、
`arm_lead=3`、`margin=2.0`、`wait_limit=20`、同一前端/后端二进制（`2066f025…`/`e3766eb3…`）、
同一 driver（`00691c6b…`）。门阈值不变。

## 2. 依据（v1 实测，不是估计）

driver 单帧成本 mean：pose 43.8 ms、scan 68.7 ms；v1 实收 4212+3553 帧 → 约 428 s 处理量对 468 s
回放，利用率逼近 1；`max_backlog_messages=429`，E2 触发晚 26.41 s。速率减半后利用率约 0.46。

## 3. 必须声明的语义变化

- **不是实时证据**：0.5× 回放下，宿主处理的输入节奏与真实采集不同，所有时间量（延迟、吞吐）都不能
  当实时性能报告；
- **wall/bag 换算**：`wait_limit=20 s`、`pose_stale=15 s`、`arm_lead=3 s` 都是**墙钟**量；
  0.5× 时它们等于 40 s / 30 s / 6 s 的 bag 时间。这是本 run 与 v1 的可比性限制，先记下，
  **不因此改这些参数**（改了才是真的换协议）；
- 报告的判据仍是 v1 预登记 §3 那张表：hold/snapshot/restore/resume 的 ack、`checkpoint_check.status`、
  `repair.clouds_published` 与 `repaired_in_update`、PGO 冻结/解冻、E2 与尾段。

## 4. 结果

run 已结束，见 `REPORT_V2_20261117.md` 与 `two_event_mmlins_v2_20261117/`。本节只作索引，不改判据。
