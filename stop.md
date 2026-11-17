stop automation to both session

## S1（MM-LINS 改进会话）停止记录 2026-11-17 18:05

用户指示「自动化先停」。已停止：不再启动 run、不再做定时巡检、不再提交/推送。
当前无任何宿主/驱动/回放进程在跑（`pgrep` 计数 0）；本会话无定时任务。

**停止时的实际状态（可核）**：
- 本机 `main@5207ae2`；远端 `slam_recovery/main@b5f1dc9`；**1 条提交未推送**（`5207ae2`）。
  内联 PAT 推送被自动模式分类器按凭据外泄规则拒绝，未绕过。
- LIO-SAM 恢复通道已接线并编译（补丁存档于 `docs/four_host/liosam_recovery_20261117/patches/`）；
  首次两事件 run 的检查点 stamp 缺陷已修（`nr_last_proc_time`），**未复验**，新二进制 `e9373b30…`。
- MM-LINS v4 结果、LIO-SAM v1 结果、PGO 崩溃分析、gate 归因等均已在本地提交与文档中。
- ORB-SLAM3 需带相机且视差足够的序列；`M2DGR/raw/` 中 hall_01/hall_02/room_02/room_dark_01 有相机，
  但视差未验证，未启动任何导出或 run。

**恢复自动化前需要用户重新授权**（run、导出、推送方式）。
