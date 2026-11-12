# T2 真实 I 资格：source scan → update → pre/post/vec 的采集阶段（2026-11-13）

> 对象：v8 run `124217Z_521833`（真实 `scan_first`）与 v7 run `115734Z_483777`（`scan_first=-1`）。
> 目标：逐项说明 I 通道的每个量来自哪个阶段，缺项直接记 `INCOMPLETE/UNKNOWN`；
> **不按行近邻补来源，不靠改 frame 字符串做转换**。本文件不改变已有数值，只限定其资格。

## 0. 一句话

`I_present=504`（v7）是**数值行数**，不是 504 个合格独立 I 证据。`vec6` 在最终 solution 之前保存，
pre 位姿没有独立的 LIO handler 导出，协方差是混合约定且无已验证 6D 切空间转换；因此
**I 的物理资格 = `INCOMPLETE/UNKNOWN`**，已有 `e_I`/`s_I` 只是带声明依赖的派生量。

## 1. 逐项资格表

| 量 | 源码/文件 | 采集阶段 | 状态 | 缺什么 |
|---|---|---|---|---|
| source scan：`RAW_HEADER_CONTAINMENT` | trace `scan_first/last_ns`；availability `scan_stamp_ns` | 组建立时 | v8/v11 **PASS（含 512 ns 量化）**；v7 **`HEURISTIC_UNPROVEN`** | v7 的 `scan_first` 为 -1 |
| source scan：`SAME_UPDATE_PRE_POST` | 同行 `pre_pose7`/`pose7` | update 前后 | v11 **PASS（725）**；v7/v8 **INCOMPLETE** | v7/v8 无同行 pre |
| source scan：`COMPLETE_POINT_MEMBERSHIP` | `grp_idx`/`n_scans`/carryover | 组建立 | **`ASSERTED_NOT_VERIFIED`** | cur 接上次 next carryover；`n_scans` 只计新 pop raw；同一 header 可出现在两个更新组 |
| update 阶段 | `LIVMapper::handleLIO`：`has_out=0` 在 StateEstimation 前返回；`has_out=1` 在更新后写 trace | 每 LIO 帧 | **PASS（阶段标签）** | — |
| post 位姿 | v11/v10 同行 `pose_x…qw`；v7/v8 用 `M2DGR_room_02.txt`（`pose_output_en`，StateEstimation 之后） | update 后 | v11 **`PASS_SAME_ROW`**（与 M2DGR 同时间 ≤1 mm）；v8 **`ASSERTED_NOT_VERIFIED`/`INCOMPLETE`** | v8 的 `grp_idx`/首末戳**不唯一对应**所用更新 |
| pre 位姿 | v11（107 列）同行 `pre_pose7`；v7/v8 的 `mat_pre.txt` 由 `handleVIO`/`handleLIO` 双写、**无 handler 标签**，`state_propagat` 不单独导出 | update 前 | v11 **`PASS_SAME_ROW`**（真实 run `165438Z`，725 行；3 行抽检）；v7/v8 **INCOMPLETE** | v7/v8 无可唯一归属 LIO 的 pre 位姿 |
| `vec6` | `voxel_map.cpp`：`vec = state_propagat - state_`（L478），`trace_cov_vec_ = vec`（L510），**之后**才 `state_ += solution`（L519） | 最终 solution **之前** | **INCOMPLETE / `NOT_VERIFIED`** | 最终 solution 未导出；v11 起 e_I 改用同行 pre/post，`vec6` **只作对照**，不再作为 e_I 来源 |
| `eff=0` 零约束 | trace `eff`、同行 pre/post | 无有效点面约束 | **单列，保留分母** | v11：462 条 I 中 **18** 条 `eff=0` 且 Log 全零（全 725 行中 37 条）；零修正不证明 IMU/LiDAR 一致，不能作 NORMAL 支持 |
| `Ppre` / `Ppost` | `_state.cov` 6×6 rot+pos 块；Ppre 在 StateEstimation 前取，Ppost 更新后取 | update 前/后 | **`NOT_AVAILABLE`（for e_I）** | 混合约定（rot 右 body、pos 世界加性）；无已验证 6D 切空间转换 |
| carryover / 成员 | trace `n_scans`、`grp_idx`；v8 全为 1 | — | **`ASSERTED_NOT_VERIFIED`**（v8） / **UNKNOWN**（v7） | `n_scans` 计的是新 pop 的 raw，carryover 在 cur/next；**完整点成员未证**；v7 无 `n_scans` |

## 2. 结论与影响

- **总体 I 资格：`INCOMPLETE/UNKNOWN`**。数值 `e_I`（含 V⁻¹ 修正）是**派生量**：
  依赖 `vec6` 是最终 pre−post 的假设（未证）、post 位姿（同行优先，但 `grp_idx`/首末戳唯一对应未证）、
  以及混合约定。
- 504 个数值行**不是** 504 个合格独立 I 证据；`s_I` 只是诊断，不能作卡方/概率。
- 不能把 `P⁻+P⁺`、改 frame 字符串、或按行近邻当作补来源/转换。
- `vec6` 的状态：`NOT_VERIFIED`（最终 solution 前保存；同次 pre/post 与 carryover 成员未证）。

## 2.1 v11（107 列）支持与待验证项

- 两个 parser 已按表头名接受 **92/93/100/107**；107 时 `Ppost6x6` 后的 `pose7` 与 `pre_pose7` 都解析。
- 正常控制：`python -I t2_run.py selftest107` → **PASS**，`pose` 与 `pre_pose` 7 值均与输入逐位一致；
  `selftest100` 仍 PASS。
- 新路径：v11 的 e_I 直接用同行 `pre_pose7`/`pose7` 做 `Log(inv(pre)·post)`（含 V⁻¹），
  **不再依赖 `vec6`**；`vec6` 只作对照。
- 真实 v11 run `165438Z_669633` 已验证：`same_row_pre_post_rows=725`；抽 3 行核对 pre/post
  与 `abs_ns`/`Ppost` 一致（post 与 M2DGR ≤1 mm，quat 范数 1.0±1.2e-11）。因此 v11 的 pre/post
  升为 **`PASS_SAME_ROW`**；总体 I 为 **`PASS_SAME_ROW_UNIT_WEIGHTED`**（协方差仍 `NOT_AVAILABLE`）。
  详见 `T2_V11_RESULTS.md`。v7/v8 仍 `INCOMPLETE/UNKNOWN`。
- **E2 绑定本 run**：v11 第 2 段 trigger rel 17.0029 s、deadline 21.0029 s；输出到约 53 s，
  E2 后 64 块/32 s 只是宿主继续在回滚地图上输出，**不是 catch-up**。
- `mat_lio_pre/out` 已加 `idx/grp_idx/phase`，只作交叉核对，不再是 e_I 的必要来源。

## 3. 解锁条件（交给 S2/S1 的实际导出）

另：`mat_lio_pre/out` 目前只有 `rel_s`，没有 `idx`/`grp_idx`/`phase`，无法唯一配对 live/replay
与两个更新组；S2 补 key 前不能用于 I 资格。

需要以下任一组合，才能在 T2 里把 I 从 `INCOMPLETE` 升级为可评价：

1. **最终 solution**（或每帧最终 pre/post 位姿）与 LIO handler 标签，绑定同一实际起止时刻；
2. 真实 6D 协方差的 **明确切空间**（rot/pos 同 frame、扰动左/右），或明确声明 `NOT_AVAILABLE` 只走单位权；
3. source scan 的成员列表（v8 的 `scan_first/last` + `n_scans` 已接近，但 v8 是单点 + 512 ns 量化）；
4. v7 的 join 若要升级，需要真实成员关系，而不是机械跨度。

## 4. 复现/出处

- `LIVMapper.cpp`：`handleLIO`（fout_pre 在 StateEstimation 前、fout_out 在之后、`writeTraceCovRow` 在最后）；
- `voxel_map.cpp`：`vec = state_propagat - state_`（L478）、`trace_cov_vec_ = vec`（L510）、
  `state_ += solution`（L519）；
- `docs/ali_h_v1_research/t2_summary.json` 的 `_meta.i_qualification`；
- `T2_RESULTS.md` 的 I 分位表与“修正前/修正后”栏。

本文件只读源码与已有输出；未跑宿主、未改生产代码。
