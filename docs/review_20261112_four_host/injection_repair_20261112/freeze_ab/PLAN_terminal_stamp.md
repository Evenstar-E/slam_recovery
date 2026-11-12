# 终止戳重放 + 开段快照：运行前声明

- 宿主：`reprocess` 带终止戳（`frozen_at_ns`），重放只到该戳；开段时 `hold` 后立即 `snapshot`，
  checkpoint 为触发帧地图、捕获从触发帧开始。
- 损坏窗口：**relay_start_ns = 触发戳 `1627785276215170145`**（不再提前 4 s），
  end_ns = `1627785282215170145`。
- 一对运行：repair（发布修正云）与 sham（同发布、shift 0），其余完全相同。
- 判定：两次 `reprocess` 的起止戳逐位一致、跨度一致；repair/sham 的 `repair_received/applied`
  各 23/23 且 synced；逐帧云 z 差 0.40/0。
- 若起止仍不一致：停、报差异来源，不追加运行。
- 门/阈值/σ 不动；仍不声称真实修复收益。
