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
| source scan 身份 | trace `grp_idx`、`scan_first_ns`/`scan_last_ns`、`n_scans`；availability `scan_stamp_ns` | 组建立时 | v8 **PASS（含 512 ns 量化）**；v7 **`HEURISTIC_UNPROVEN`** | v7 的 `scan_first` 为 -1；v8 的跨度是单点 + 量化 |
| update 阶段 | `LIVMapper::handleLIO`：`has_out=0` 在 StateEstimation 前返回；`has_out=1` 在更新后写 trace | 每 LIO 帧 | **PASS（阶段标签）** | — |
| post 位姿 | `M2DGR_room_02.txt`（`pose_output_en`，StateEstimation 之后，body→world）；v10 起同行 `pose_x…qw` 优先 | update 后 | **`ASSERTED_NOT_VERIFIED` / `INCOMPLETE`（v8）** | `grp_idx`/首末戳**不唯一对应**所用的那次更新；v7 的 join 同样未证 |
| pre 位姿 | `mat_pre.txt`：`handleVIO` 与 `handleLIO` 各写一次，**无 handler 标签**；trace 的 `state_propagat` 不单独导出 | update 前 | **INCOMPLETE** | 没有可唯一归属 LIO 的 pre 位姿 |
| `vec6` | `voxel_map.cpp`：`vec = state_propagat - state_`（L478），`trace_cov_vec_ = vec`（L510），**之后**才 `state_ += solution`（L519） | 最终 solution **之前** | **INCOMPLETE** | 最终 solution 未导出；`vec6` 不是最终 pre−post |
| `Ppre` / `Ppost` | `_state.cov` 6×6 rot+pos 块；Ppre 在 StateEstimation 前取，Ppost 更新后取 | update 前/后 | **`NOT_AVAILABLE`（for e_I）** | 混合约定（rot 右 body、pos 世界加性）；无已验证 6D 切空间转换 |
| carryover / 成员 | trace `n_scans`、`grp_idx`；v8 全为 1 | — | **`ASSERTED_NOT_VERIFIED`**（v8） / **UNKNOWN**（v7） | `n_scans` 计的是新 pop 的 raw，carryover 在 cur/next；**完整点成员未证**；v7 无 `n_scans` |

## 2. 结论与影响

- **总体 I 资格：`INCOMPLETE/UNKNOWN`**。数值 `e_I`（含 V⁻¹ 修正）是**派生量**：
  依赖 `vec6` 是最终 pre−post 的假设（未证）、post 位姿（同行优先，但 `grp_idx`/首末戳唯一对应未证）、
  以及混合约定。
- 504 个数值行**不是** 504 个合格独立 I 证据；`s_I` 只是诊断，不能作卡方/概率。
- 不能把 `P⁻+P⁺`、改 frame 字符串、或按行近邻当作补来源/转换。
- `vec6` 的状态：`NOT_VERIFIED`（最终 solution 前保存；同次 pre/post 与 carryover 成员未证）。

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
