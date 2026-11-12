# FAST-LIO2 独立构建与原生验证：BLOCKED_LOAD（构建成立，运行被环境阻塞）

日期：2026-11-13。任务来自四宿主主线（用户指令 `HOST_VALIDATION_ORDER_20261113.md`）。

## 1. 独立构建（成立）

| 项 | 值 |
|---|---|
| 源码 | `/home/R26534/MM-LINS/FAST-LIO`，git HEAD `c6d9e3264bccc8e8762bb072ec0b3b741358d9bd`；内容 sha `da889ce0…` |
| 新工作区 | `/home/R26534/fastlio2_ws`（源码复制；未修改原树、未复用 `mmlins_ws` 的 devel/install） |
| 构建 | `catkin_make -j8`，首次因 CMake 策略报错，加 `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` 后成功；日志 `build.log` / `build2.log` |
| 二进制 | `/home/R26534/fastlio2_ws/devel/lib/fast_lio/fastlio_mapping`，sha **`4c31fada…`**（共享版 `59674a8f…`，不同） |
| 证明 | 启动后 `/proc/<pid>/exe` = `fastlio2_ws/...`（`run1/process_identity.txt`） |

## 2. 运行：FAIL / INCOMPLETE

- 同 bag（`campus_12_fl.bag`，`a924b5f9…`）、`--clock`、rate 1.0、同录制话题、E1/E2 同戳。
- 播放远慢于实时：900 s 外层 timeout 到期时 bag 只到 **376.0 / 469.4 s**（无 `Done`）；随后
  `rosbag record` 被连带终止，录制未索引；`rosbag reindex` 后 **0 条可读消息**。
- 原因：机器负载。运行时 load1 从 ~100 升到 **360**（128 核），来自其它会话 6 天前启动、仍在运行的
  `mmlins_ws` 进程（非本任务，未触碰）。
- 无可用 `/Odometry`/事件数据；节点日志仅作旁证：覆盖的 376 s 内 **4 次** `Over-degeneracy →
  construct a new map`、**323 次** `IMU Initial Done`（共享版整段 2 次）。此负载下**不可归因于代码**。

## 3. 重跑：未执行（load 门控拦截）

- 门控：开跑前 `load1 > 200` 不开跑、不消耗授权。采样 `310 / 283 / 265` → **BLOCKED_LOAD**。
- 脚本 `run_fastlio2_independent.sh` 已具备：load 门控、60 s 一次 `loadavg.log`、播放 120 s 后
  <0.8× 早停（`EARLY_STOP_RATE`）、`SIGINT record → wait → rosbag info → 退出`、1800 s 兜底。

## 4. 结论与标签

- **NATIVE_INDEPENDENT 的构建成立**（二进制独立、身份可证）；
- **原生双事件与尾段未验证**：`BLOCKED_LOAD`，不是代码结论；
- slam_recovery 恢复接线：**NOT_IMPLEMENTED**（与本次阻塞无关）。

## 5. 文件

`run_fastlio2_independent.sh`、`analyze_bag.py`、`source_identity.txt`、`build.log`、`build2.log`、
`run1/`（`binary_identity.txt`、`process_identity.txt`、`fastlio_node.log`、`play.log`、`record.log`、
`roscore.log`、`runner.log`）。`frontend*.bag` 未入库（1.6 GB，且不可读）。

## 6. 录制文件未入库的说明

`frontend.orig.bag`（未索引原件）与 `frontend.bag`（reindex 后）各 1.6 GB，且 reindex 后 **0 条可读
消息**，不具备证据价值；按"大文件不入库"的既有约定，仅在此记录路径与 sha256：

```
<sha>  run1/frontend.orig.bag
<sha>  run1/frontend.bag
```

（实际值见提交时写入的 `run1/bag_sha256.txt`。）
