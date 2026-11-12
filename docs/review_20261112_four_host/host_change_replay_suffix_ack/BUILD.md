# 宿主改动：reprocess ack 暴露 replay_suffix

- `checkpointStatus()` 新增 `replay_within_end=%zu replay_suffix=%zu`（取自上一次重放的计数，
  不新算）；字符串缓冲从 512 加到 768 以容纳新字段。
- 驱动侧由本仓库实现：接收 reprocess ack 后若 `replay_suffix > 0` 则跳过 `set_state`，并记录
  `native_writeback_skipped.reason="replay_suffix"`；suffix=0 保持现行为。
- 增量 `ack_increment.diff` 49 行（v4→v5，`git apply --check` 通过）；完整
  `deployed_host_v5.diff` 1632 行（干净 `0d2c034` 上通过）。
- 构建 `catkin_make -j8`（`host_build_v6.log`）：宿主目标 Built；新库 sha
  `9e7d8cdf…3b0a`；可执行文件仍 `0d7e23de…`。退出码 1 仍来自无关的 vikit 测试 ABI。
