# 宿主改动：hold/snapshot 声明戳（延迟到帧循环执行）

## 1. 改动

- `hold` / `snapshot` 的 payload 可带**应用戳(ns)**。带戳时控制线程只入队并立刻回
  `OK <cmd> deferred stamp=<ns>`；主循环在**第一个 `lio_time ≥ 戳` 的组被处理之前**执行它
  （`applyDeferredControlCommands`，在 `sync_packages` 之后、处理之前调用）。不带戳保持原有
  立即语义。过期/迟到在 `[NATIVE_CHECKPOINT] deferred apply ... late_ms=` 里记录。
- 执行分支重构为 `executeControlCommand(cmd, payload, detail)`；`applyPendingControlCommand`
  与延迟队列共用它。约 203 行增量（含重构），无通用 RPC。延迟触发只认"带 lidar 测量的组"的 `lio_time`：image-only 组没有时间可比，若用上一组的时间会晚一组执行，checkpoint 会漏掉触发组。
- 控制线程从不碰地图、状态或 LIO；只做入队与 receipt。

## 2. 差异

| 文件 | 内容 |
|---|---|
| `deferred_increment.diff` | 相对上一版（含终止戳）的增量，203 行；在 v2 树上 `git apply --check` 通过 |
| `deployed_host_v3.diff` | 当前完整宿主源码（`0d2c034` + 全部改动），1627 行；干净树上 `apply --check` 通过 |

## 3. 构建

`cd /home/R26534/fast_livo2_ws && catkin_make -j8`（日志 `host_build_v4.log`）。

| 产物 | sha256 | 说明 |
|---|---|---|
| `liblaser_mapping.so` | `9c0330be…00db` | 已重建；`strings` 含 `deferred apply` |
| `fastlivo_mapping` | `0d7e23de…af6c1` | 未变（动态链接） |

构建退出码 1，失败仍在无关的 `rpg_vikit` 测试可执行文件
`test_vk_common_patch_score`（`libIlmThread.so.32` 的 `__cxa_call_terminate@CXXABI_1.3.15`
未定义），宿主目标已 `Built target laser_mapping`。receipt 以 `/proc/<pid>/maps` 绑定新库 sha。

## 4. 复现检查

- `git -C /tmp/host_v2 apply --check deferred_increment.diff` → 通过。
- 干净 `0d2c034` + `git apply --check deployed_host_v3.diff` → 通过。
