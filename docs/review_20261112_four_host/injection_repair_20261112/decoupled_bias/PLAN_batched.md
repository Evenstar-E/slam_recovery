# 分批 + 累计回执：运行前声明

- 发布：每批 ≤10 条；每批后用 `status` ack 的累计 `repair_received` 确认到"已发布总数"，
  再发下一批；最后一批后再做一次 status，要求 `repair_received == baseline + published`。
- 任一批超时或最终计数不符：不发 `reprocess`，记录批次与丢帧数，走原有拒绝/等待路径，
  不重试发布、不跳过校验。
- 超时：沿用 `--repair-sync-timeout-sec 5.0`。
- 判定：`repair_received == repair_applied == 26`、`reprocess #` 出现、`[NATIVE_REPAIR] applied`
  逐帧、命令顺序 hold→发布→receipt→reprocess→set_state→resume。
- 若仍有丢帧：停、报断点（每批回执与丢帧数），不跑对照。
- 门/阈值/σ/宿主不动。
