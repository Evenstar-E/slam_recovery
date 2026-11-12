# 解耦偏差估计：运行前声明

- 方法：候选仍用宿主位姿初值的 ICP（上一 run accepted、Wilson 0.90）；偏差对每帧用 incumbent
  位姿做 body-z 一维搜索（步长 0.05 m，范围 [-0.6, 1.4]），代价为到 trusted 参考地图的
  最近点距离中位数；修复用逐帧估计的中位数；修复云 = 损坏云 − bias。
- 预期：注入为 +0.5 m body-z，`bias_z_m` 应 ≈ **+0.5**。
- **容差（运行前写死）**：`|bias_z_m − 0.5| ≤ 0.15 m` 记为“估计合理”。即使超出，也照常发布、
  照常运行、照实报告，不按结果过滤。
- 判定：accepted + `repair_received/applied > 0` + `[NATIVE_REPAIR] applied` +
  `reprocess` 使用修复云；逐帧 bias 与 0.5 的差、地图/轨迹相对无修复 run 的变化、命令顺序
  全部归档。若 bias 或效应不行，停在本轮报断点，不跑对照。
- 门/阈值/σ/宿主不动。
