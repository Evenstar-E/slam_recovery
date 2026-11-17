# b5f1dc9增量审阅：MM-LINS原生生命周期推进，accepted仍为零；LIO-SAM仅补丁预登记

面向用户与S1/S2/S3开发侧。2026-11-18 00:35（UTC+8）fetch固定 `origin/main=b5f1dc938029a467a88c0420fda29fdd75192a06`。本机只读归档run、日志、patch和源码，未代跑ROS/宿主、重建或修改算法。

## 1. 总结判定

**MM-LINS有实证推进：跨进程hold、checkpoint、PGO守卫和两事件生命周期取得真实原件；accepted测量修复仍未发生。LIO-SAM当前只有补丁与预登记，无构建或run证据。**

v4是当前最重要结果：前端与PGO均存活到录制终点，E1 checkpoint首次合法落在边界内，第二事件被处理，driver没有提前以`INPUT_STALE`结束。它关闭了v1/v2的部分接口断点，但没有产生accepted候选、repair cloud或reprocess内容。

## 2. MM-LINS v4接受什么

固定`two_event_mmlins_v4_20261117`：

| 项 | 原件结果 | 独立判定 |
|---|---|---|
| bag/binary/source | bag SHA `a924b5f9…`；前端`2066f025…`、PGO`cc99d2ea…`，pre_run有完整路径与SHA | 身份比此前run完整，仍是开发归档，非本机复建 |
| 两事件 | E1/E2均scripted触发，`detection_enabled=false` | 只接受受控生命周期，非自动检测 |
| E1 checkpoint | `AT_OR_BEFORE_BOUNDARY`，restore `valid=1` | 合法边界局部通过 |
| E2 checkpoint | `LATE_AFTER_BOUNDARY`，晚0.200143352s，restore `valid=1` | valid不等于合法覆盖隔离段 |
| PGO | `/aft_pgo_odom` 7921条，`skipping sleeping map` 819次，退出`pgo_hold=absent` | 空休眠图守卫实际生效，PGO未崩 |
| 最终生命周期 | `HEALTHY`、无open quarantine、`terminal_reason=None` | 有尾段，但仍有1个unresolved segment |
| E1候选 | 5/13，Wilson 0.201580，holdout 493.601，Mode 4 | 拒绝，host_poses不是实际测量修复器 |
| E2候选 | 0/11，Wilson 0，holdout 387.828，Mode 3 | 拒绝 |
| 修复写回 | accepted=0、repair clouds=0、reprocess=0 | **未发生native accepted update/map** |

E1/E2的信息增益数值通过并不抵消Wilson与holdout失败。不能把`HEALTHY`、PGO存活或restore valid=1外溢为accepted恢复成功。

## 3. v1–v4负结果与归因边界

- v1虽有两事件生命周期，但checkpoint晚边界，E2晚9.71秒且driver落后；
- v2检查点时机改善，但PGO以SIGABRT退出、driver提前STALE，仍无写回；
- v3无hold、无driver时PGO不崩且守卫零触发，既没有证明守卫有效，也没有证明该路径原生可达；
- v4守卫在带hold的运行中触发819次并阻止空图进入回环候选，是直接行为证据，但**不能单独证明v2崩溃的唯一根因**。开发侧也保持UNKNOWN，本审阅不改成确定因果。

v1/v2配对收益变化同时受速率、检查点和incumbent质量影响，不能把v1高Wilson直接当科学收益，也不能把v2下降归因单一参数。

## 4. LIO-SAM当前状态

`dff8d519`与`b5f1dc9`只交付预登记、runner和`mapOptmization_native_recovery.patch`：

- 声明hold/snapshot/restore=YES；
- 明确`reprocess=NO`、`measurement_relay=NO`，没有输入缓冲或修复消息relay；
- 事件计划放在bag 40/80秒，避开120–140秒已知输入退化窗，0.5×非实时；
- 预登记结果节仍为“run后填写”，提交中没有构建日志、二进制回执、run_summary或两事件原件。

因此LIO-SAM只能记 **PATCH_AND_PREREGISTRATION_ONLY；build/run NOT_EXECUTED**。补丁设计不冒充真实快照恢复、图重建或接回证据。

## 5. 主线、旁支与下一动作

**主线**：MM-LINS跨进程checkpoint/PGO/两事件是实质推进，当前最近断点已从“接口与PGO存活”转为**没有能过门的真实测量候选**。

**旁支**：修法A、配对翻转分析、四宿主表更新、LIO-SAM补丁与预登记是保障或准备，不计accepted。A/B不做全表新评分，局部MM-LINS A4/A9/A10可记生命周期证据，B4/B11仍无accepted净收益。

**下一单一主线**：在现授权边界内由S1把候选从`host_poses`换成真实的**隔离段scan→pre-quarantine trusted map配准/测量修复**，再由S2在用户实际授权后做一次有界run，目标为accepted候选→真实native update/map→接回→E2与完整输入归宿。不得用近静止窗口的host_poses或降门制造通过。

LIO-SAM若要继续，先完成补丁构建和预登记run，保留`reprocess=NO`与`measurement_relay=NO`；它是后续独立任务，不替代MM-LINS accepted缺口，也不启动FAST-LIVO2。

## 6. 本机复核

```text
C:/Python315/python.exe -I -B docs/review_20261117_b5f1dc9/review_checks.py
```

[review_checks.json](review_checks.json)固定v4两事件、E1合法cp、E2晚边界、PGO 7921条输出/819次守卫、accepted/repair/reprocess为0及LIO-SAM仅补丁预登记，最终exit 0；未执行宿主或补丁。
