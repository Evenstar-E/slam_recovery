# 宿主改动：重放覆盖全部捕获组（后缀不再丢弃）

## 1. 改动

- `reprocessCheckpoint` 不再用 `end_stamp` 截断重放本身。终止戳只作为**修复云匹配的边界**：
  `within_end` 组照常匹配并替换修复云，`suffix` 组（决策后捕获、live 已消费但被 restore 回滚
  的后缀）用**原始测量**按顺序重推。
- 日志：`replayed_within_end=… replayed_suffix=… end_stamp=…`，总帧数仍写 `replayed`。
- 修复计数不变：后缀组不消费修复云，候选窗口的修复仍 23/23。

## 2. 差异

| 文件 | 内容 |
|---|---|
| `suffix_increment.diff` | 相对 v3 的增量，67 行；在 v3 树上 `git apply --check` 通过 |
| `deployed_host_v4.diff` | 当前完整源码，1625 行；干净 `0d2c034` 树上通过 |

## 3. 构建

`catkin_make -j8`（`host_build_v5.log`）：宿主目标已 Built；新库 sha
`c0833d9f…dfe0`；`fastlivo_mapping` 仍 `0d7e23de…`（动态链接）。构建退出码 1 仍来自无关的
`test_vk_common_patch_score`（`libIlmThread` 的 `__cxa_call_terminate@CXXABI_1.3.15`）。
