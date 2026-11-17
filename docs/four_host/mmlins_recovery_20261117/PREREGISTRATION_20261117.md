# MM-LINS 恢复层接线与两事件 run：预登记（2026-11-17）

**状态**：run 开始前写定。本文件声明本次接线改了什么、跑什么、什么算证据、什么不算。
run 之后不得改动本节判据；新增内容只能作为「实际结果」另起小节。

## 1. 宿主改动（源码级，可复核）

1. **前端**：`FAST-LIO/src/laserMapping.cpp` 由 FAST-LIO2 v9 原生恢复通道源文件整文件替换。
   复核方式：对替换前文件套 `diff -u` 后与
   `/home/R26534/fastlio2_ws/src/FAST-LIO/src/laserMapping.cpp`（sha `4bd859a9…`）
   **逐字节相同**（sha 一致），即端口不是手抄而是已验证的同一份代码。
2. **新增 `pgo_hold` 标记**（仅 MM-LINS 版）：前端在 `hold` 应用时写
   `<native_recovery_dir>/pgo_hold`，在 `resume/release` 时删除。该标记由前端这一唯一写者维护。
3. **后端**：`SC-PGO/src/laserPosegraphOptimization.cpp::process_pg()` 在累积位移后检查标记；
   存在则消费该帧但**不插关键帧、不加因子、不跑 iSAM2**，并把 `translationAccumulated` /
   `rotaionAccumulated` 归零（使 resume 后第一个关键帧只度量自恢复点起的位移）。
   标记路径取自 ROS 参数 `native_recovery_dir`。

**未改动**：门阈值（`tau_abs_min=3.0` 等）、`IcpConfig`、前端 LIO 数学、PGO 噪声模型、
关键帧间距、bag、E1/E2 戳。改动仅限「跨进程 hold 通道」。

## 2. run 声明

| 项 | 值 |
|---|---|
| 命令 | `docs/four_host/mmlins_recovery_20261117/tools/run_two_event_mmlins.sh OUT BAG 470` |
| 输入 | `datasets/mmlins/campus_12_fl.bag`（sha 记入 `pre_run.txt`），rate 1.0，`--clock` |
| 事件 | **DECLARED_OBSERVATION**（自然休眠窗，非注入）：E1 `1711547999352267771`、E2 `1711548113452267771` |
| 恢复层 | 前端 v9 通道（hold/snapshot/restore/reprocess/resume）+ slam_recovery driver |
| 检测 | `--detection off`（诊断记录，不产生检测指标） |
| 候选 | `host_poses` |
| 私有 master | 每次随机端口，`ROS_HOSTNAME=127.0.0.1` |

## 3. 什么算证据（逐项）

| 项 | 判据（原件） |
|---|---|
| 前端通道在线 | `ctl/capabilities.json` 存在且前端 ack 原文可读（`recovery_node.log` 与 `ctl/ack`） |
| hold 生效 | 前端 ack `OK hold applied` + `ctl/pgo_hold` 出现（时间戳可寻） |
| 检查点 | 前端 ack `OK snapshot valid=1`，且 `status` 中 frame/stamp 非空 |
| 回滚 | ack `OK restore valid=1` |
| 接回输入 | 前端 `input_fates.jsonl` / ack 中 `repaired_fed>0`，且 `repaired_in_update>0` 才能称为「原生更新消费了修复帧」 |
| PGO 冻结 | `pgo.log` 出现 `pgo_hold present: keyframe insertion frozen` 与 `released`，且 `ctl/pgo_hold` 生命周期与 hold 对齐 |
| 第二事件 | `lifecycle.events` 有 E2 及其段关闭；E2 后宿主继续产出（尾段） |
| 整链 | 上述在同一 run 目录内串成一条时间线 |

## 4. 什么不算证据

- 只有 `result.txt=done` 或进程正常退出；
- 只有 PGO 轨迹连续（PGO 本来在事件处就连续，`REPORT_20261112` 已记录）；
- 把「repaired_fed>0」当成「修复被地图采用」——采用需 `repaired_in_update>0`；
- 用 `Issleeping/Isbuilding` 条数替换恢复层自身的生命周期记录；
- 任何把 `--detection off` 的 run 报成检测能力的说法。

## 5. 已知限制（run 前声明）

- 前端无 replay buffer 的完整重建；`reprocess` 能力为 `PARTIAL`（v9 声明），本 run 不声称完整重建。
- PGO 冻结是**标记轮询**不是事务；前端崩溃留下的标记会让 PGO 一直冻结（本次 run 结束时检查残留）。
- 前端与 PGO 共享 `native_recovery_dir`，但只有前端写 cmd 的 ack；PGO 只读标记、不写。
- 事件为自然休眠窗声明点，不是注入；注射版证据不在本次范围。

## 6. 结果

（run 结束后填写，只写原件可核的内容。）
