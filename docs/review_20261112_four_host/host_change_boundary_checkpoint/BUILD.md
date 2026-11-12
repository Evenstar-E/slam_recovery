# 宿主改动：checkpoint 时间戳取"最后一个已处理组"

- `snapshotCheckpoint()` 的 `cp_stamp_` 从 `LidarMeasures.last_lio_update_time`（即将处理的组）
  改为 `cp_last_processed_lio_`（已折入状态/地图的最后一个组的 lio_time）；主循环在
  `stateEstimationAndMapping()` 之后更新该值。
- 这样武装快照在"第一个 lio_time ≥ 应用戳 的组"之前执行时，checkpoint 戳反映的是它真正复制
  的状态时间，可以满足"checkpoint ≤ 隔离起点"。
- 增量 33 行（v5→v6，`git apply --check` 通过）；完整 `deployed_host_v6.diff` 1638 行。
- 构建：宿主目标 Built；新库 sha `ca9126c4…44ef`；可执行文件仍 `0d7e23de…`；退出码 1 仍只来自
  无关的 vikit 测试 ABI。
