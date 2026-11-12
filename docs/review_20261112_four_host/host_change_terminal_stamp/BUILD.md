# 宿主改动：`reprocess` 终止戳（本轮唯一允许的宿主改动）

## 1. 改动

- `include/LIVMapper.h` / `src/LIVMapper.cpp`：
  `reprocessCheckpoint(bool apply_repairs, bool keep_buffer, int64_t end_stamp_ns = 0)`。
- `applyPendingControlCommand` 的 `reprocess` 分支解析 payload（ns）；空 payload 保持原行为。
- 重放循环跳过"组结束时间 > end_stamp"的条目，统计 `replayed/truncated`；
  `[NATIVE_CHECKPOINT] reprocess` 行新增 `replayed=… truncated=… end_stamp=…`。
- 无通用 RPC、无其他接口变化。

## 2. 差异文件

| 文件 | 内容 |
|---|---|
| `terminal_stamp_increment.diff` | 相对上一版已部署宿主源码（`deployed_host.diff` 应用后的树）的**增量**，87 行；`git apply --check` 通过 |
| `deployed_host_v2.diff` | 当前完整宿主源码（上游 `0d2c034` + 全部改动），1528 行；在干净 `0d2c034` 树上 `git apply --check` 通过 |

## 3. 构建

命令：`cd /home/R26534/fast_livo2_ws && catkin_make -j8`（日志 `host_build_v2.log`）。

| 产物 | sha256 | 说明 |
|---|---|---|
| `devel/lib/liblaser_mapping.so` | `f27d1730…79d0c` | **已重建**，包含 `truncated=` 字符串（`strings` 验证） |
| `devel/lib/fast_livo/fastlivo_mapping` | `0d7e23de…af6c1` | **未变**（动态链接共享库；行为在 .so 里） |

**构建退出码为 1，但不是宿主目标失败**：91% 时 `Built target laser_mapping` 已完成并链接；
失败发生在无关的 `rpg_vikit` 测试可执行文件 `test_vk_common_patch_score`，
`/usr/bin/ld: /home/R26534/mm/ros/lib/libIlmThread.so.32: undefined reference to
__cxa_call_terminate@CXXABI_1.3.15`。这是该测试目标与 mm ROS 库的 ABI 不匹配，宿主的
`fastlivo_mapping`/`liblaser_mapping.so` 不受影响。runner 的 receipt 以 `/proc/<pid>/maps`
解析实际加载的库并哈希，因此本次 run 的 `runtime_library_sha256` 应绑定 `f27d1730…`。

## 4. 复现检查（已做）

- `git -C /tmp/host_pristine apply --check terminal_stamp_increment.diff` → 通过（上一版树）。
- 干净 `0d2c034` 树 + `git apply --check deployed_host_v2.diff` → 通过。
