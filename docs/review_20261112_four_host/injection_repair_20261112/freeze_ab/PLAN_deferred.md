# 声明戳 hold/snapshot：运行前声明

- 宿主：`hold`/`snapshot` 带应用戳时延迟到"第一个 lio_time ≥ 戳的组处理之前"执行；控制线程只
  入队并回 `OK ... deferred`。`reprocess <frozen_at_ns>` 固定重放终点。
- 驱动：启动阶段就把 `hold <trigger>` 与 `snapshot <trigger>` 排进队列；开段只剩幂等 `hold`。
- 损坏窗口仍从触发戳开始（relay_start_ns = 1627785276215170145）。
- 一对 repair / sham。核对：两次 `snapshot stamp` 与 `reprocess` 起止戳逐位一致、`replayed`
  帧数一致、`repairs applied=23/23`、地图 voxels/points、同批 stamps 的重放位姿差。
- 若两端不一致：停、报具体字段差异，不追加运行。
- 门/阈值/σ 不动；损坏自注入，不声称真实修复收益。
