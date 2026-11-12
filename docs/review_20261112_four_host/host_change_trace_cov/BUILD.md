# 宿主改动 v7：ALI-H v1 协方差/位姿 trace（opt-in）

基线：0d2c034 + 已部署补丁（v1–v6），源码快照见本目录 `*.v6`。
状态：**已构建并部署到 `devel/lib`，但两次 bag 运行都在宿主启动阶段失败**
（见 §5，与 trace 代码无关，是进程早期内存/环境损坏）。实验性，未进 v1–v6 版本链。

## 1. 改动（4 个文件，+145/−5 行）

| 文件 | 改动 |
|---|---|
| `include/LIVMapper.h` | `trace_cov_en` / `fout_cov` / `trace_cov_rows` 成员；`writeTraceCovRow()` 声明（+10） |
| `src/LIVMapper.cpp` | 私有参数 `~trace_cov`（默认 false）；`initializeFiles()` 打开 `Log/trace_cov.txt` 并写表头；构造时把开关传给 voxelmap；`handleLIO()` 进入时保存 `_state.cov.block<6,6>(0,0)`（P⁻），早退路径写 `has_out=0`，正常结束写 `has_out=1`；`writeTraceCovRow()` 实现（+74/−5） |
| `include/voxel_map.h` | trace 成员（`trace_cov_Ppre_`、`vec_`、`eff_`、`r_*`）（+17） |
| `src/voxel_map.cpp` | `StateEstimation()` 入口保存 P⁻；更新点（`vec = state_propagat - state_` 之后）统计 `meas_vec` 的均值/中位/绝对均值/χ²/加权χ²（+44） |

- 全部为只读诊断：不改 EKF 数学、不改检测/注入/checkpoint/replay/set_state；
- 默认关；打开只多写一个文件；
- 行写在 `std::endl` 处 flush，宿主被 SIGTERM 也不会丢已写行；文件与 `mat_pre/mat_out` 一样**每次运行 trunc**。

## 2. trace 字段（v2，按 S1 2026-11-12 更正版）

每行一个 LIO 帧：

```
idx rel_s abs_ns has_out phase eff r_mean r_med r_abs_mean r_chi2 r_chi2w
vec6(6) Ppre6x6(36) Ppost6x6(36)
```

| 字段 | 含义 |
|---|---|
| `idx` | 本 run 内单调行号（唯一配对键） |
| `rel_s` | `last_lio_update_time − _first_lidar_time`（秒，与 mat_pre/mat_out 同键） |
| `abs_ns` | `last_lio_update_time`（lidar 帧末，绝对 ns，`llround(t*1e9)`） |
| `has_out` | 1 = 该帧跑完 `StateEstimation`；0 = 早退（只有 Ppre，其余为 0） |
| `phase` | 0 = live，1 = replay 重放（`replay_mode_`；重放会重复时间戳，必须按 `idx`） |
| `eff` | `effct_feat_num_`（参与点面约束的实际点数 m） |
| `r_mean/r_med/r_abs_mean` | `meas_vec` 的均值/中位数/绝对均值（米） |
| `r_chi2` | Σ r² |
| `r_chi2w` | rᵀR⁻¹r（用该次更新的 R；仅作测量空间统计，**不是** e_I 协方差） |
| `vec6` | `(state_propagat − state_)[0..5]`，即更新前位姿域差 |
| `Ppre6x6` | **P⁻** 位姿块（旋转+平移），更新前传播一步的协方差 |
| `Ppost6x6` | **P⁺** 位姿块，`StateEstimation` 之后 `_state.cov` |

**不导出 m×m 的 S = H P⁻ Hᵀ + R**（m=eff，本数据数百–数千，体积与用途都不成立；也不是任何 6 维位姿残差的协方差）。
若需要 `covariance=NOT_AVAILABLE`：直接声明 e_I 的协方差不可用，P⁻/P⁺ 仅为候选来源，不得相加当 e_I 协方差（共享先验、同一次测量，不独立）。

## 3. 状态/协方差约定（必须与数据一起引用）

- 状态 19 维：`rot(0..2) so3 切空间, pos(3..5), inv_expo(6), vel(7..9), bg(10..12), ba(13..15), gravity(16..18)`。
- 协方差是**body(IMU)系**切空间协方差；`pos` 在世界系表达，但扰动在 body 切空间（与 `StatesGroup::operator+` / `state_ += solution` 一致）。
- 旋转参数化：SO(3) 李代数 3 维（`Exp(rot_add)` 右乘到 `rot_end`）。
- 时间：`last_lio_update_time` 是 **lidar 帧末**时刻；`mat_pre`/`mat_out` 的 `rel_s` 与 `trace_cov` 的 `rel_s` 同键。

## 4. 构建与身份

| 项 | 值 |
|---|---|
| 构建 | `catkin_make -j8`，日志 `host_build_v7.log`（首次）与 `host_build_v7b.log`（更正字段后） |
| 宿主目标 | `Built target laser_mapping` 两次均成功；退出码 1 仍只来自无关 `test_vk_common_patch_score` ABI |
| 库 sha | 首次 `691d733444f4…8ed3`；更正后 **`0308c216ed2b…784ab`**（当前 `devel/lib`） |
| 可执行文件 | `0d7e23de…`（未变） |
| 驱动 | `/tmp/wt-sim`，branch `exp/m0-updated`，HEAD `584604c1…`；`run_native_loop.sh` 增加 `TRACE_COV` 与 rospack 预热（未提交） |

## 5. 运行阻塞（2026-11-12）

两次运行（`fl_native_20261112T100744Z_326380`、`...T101116Z_329791`）都在宿主启动阶段失败：
`[rospack] Error: package 'image_transport' not found` → `No plugins found!` → `terminate`。
`pose_messages=0`、`scan=598`、`paired=0`，recovery 写 0 条候选。

最小诊断（详见交付报告）：单独拉起宿主二进制可复现；`env -i` 最小环境、预热 rospack 缓存、给环境加 8 KB 填充都不能避免；
同一环境下一个只做 `image_transport::ImageTransport::advertise` 的探针程序正常。
进程内 `getenv` 跟踪显示：从 OpenCV 初始化起，**所有** ROS 变量（以及 `CMAKE_PREFIX_PATH`）都返回 NULL，而 `environ` 指针未变；
`OMP_NUM_THREADS=1` 时同一位置变成 SIGSEGV —— 指向早期初始化阶段的内存损坏，不是启动 shell 没 source、也不是 rospack 缓存。
`mat_pre.txt`/`mat_out.txt` 已被失败的启动 trunc 成 0 字节；最后一次成功 run 的绝对位姿轨迹另存在 `last_good_pose/`。

## 6. 后续修订（2026-11-12 晚，仍属 v7）

- **逐行 `std::endl` → `'\n'` + 每 32 行 flush**：逐行 flush 在 `Log/`（近满网络挂载）上会 stall 宿主，实测导致命令迟到、扫描组 span 丢失、修复 23 条全丢；缓冲后 replay/修复恢复（库 `49f2f941…`）。
- **新增列**：`grp_idx`（采集时分配、随组复制，跨 replay 唯一）、`scan_first_ns` / `scan_last_ns`（合并扫描跨度两端的 header 戳）；`include/common_lib.h` 的 `LidarMeasureGroup` 增加 `native_group_index`。
- **`phase` 语义确认**：`replay_mode_`，只在 `reprocessCheckpoint()` 内为 1；实测 1208 行中 322 行 phase=1，恰为重复 grp 的第二次出现（readers 应按列名取，不要按位置）。
- 最终库 sha：`49f2f941cc0a90357e088d2271f21e60fdeb18c88b5b89a1c6acce5f55e48eda`；构建日志 `host_build_v7u.log`。
- availability sidecar 在 `--detection off` 下为 `status=DISABLED`、`support=null`；`--detection on` 下才有 support/旧 status（见 `trace_fl_native_20261112T115734Z_483777/`）。

## 7. 已知数据缺陷（2026-11-12 夜，如实标注）

1. **`scan_first_ns` 恒为 `-1`（不可用）**：本模式下 `LidarMeasureGroup::lidar_frame_beg_time` 为 0
   （见 `src/LIVMapper.cpp:824` 注释），span 只在 VIO 合并分支写（`src/LIVMapper.cpp:2079`），
   于是写进 0，trace 把非正值映射为 `-1`。`scan_last_ns` 是真实值。**不得用
   `[scan_first, scan_last]` 做区间包含**（`-1 <= ts` 恒真）；应使用"上一个不同的 `scan_last` < stamp <= 当前 `scan_last`"。
   最小修法：合并循环开头记录首条扫描头戳，写
   `native_scan_first = (lidar_frame_beg_time > 0 ? lidar_frame_beg_time : first_merged_time)`。
2. **最后一行可能不完整**：宿主被 SIGTERM 杀死时可能截断正在写的行（`113855Z` 末行 44 列、
   `115734Z` 末行 53 列，正常 92 列；`121127Z` 未截断）。读取端丢弃列数不足 92 的行。
3. `phase` 语义：只在 `reprocessCheckpoint()` 内为 1。

## 8. v9：C′ 检查点历史（环）

- 新增私有参数 `~cp_history_k`（默认 **1**）。`K=1` 时**不保留历史、不复制、不增加任何行为**，
  与 v8 完全等价；`K>1` 时 `snapshotCheckpoint()` 把上一份活动快照**移动**进环形（不克隆地图），
  只保留最近 K 份（含活动槽）。`restore`/`reprocess` 的选择语义**未改**：仍然只用活动槽。
- **存储放在 `LIVMapper.cpp` 的文件级 static，类布局与 v8 逐字节一致**。两次独立验证：把环形或
  `ofstream` 做成 `LIVMapper` 成员后，重建的库启动探针 0/5～5/5 失败（SIGSEGV/stack smashing）；
  改回 file-static 后 5/5 通过。任何类布局变化都会唤醒那个既有启动期内存缺陷。
- 输出：每次 snapshot 的 `ROS_INFO` 与 `checkpointStatus()` 都追加
  `hist_k=`（深度）、`hist_bytes=`（估算 `points*32 + voxels*96`）、
  `hist=<stamp_ns:frame:voxels:points;…>`（不含活动槽；活动槽仍是 `stamp_ns=`）。
- 首次测量（`cphist_fl_native_20261112T131213Z_563253`，K=3）：环形工作正常；该 run 后段地图失控
  （323k→453k voxels、RSS 峰值 6.97 GB），**内存对照无效**，不能当作 K=3 的代价结论。
- **更正（2026-11-12 夜）**：该 run 唯一一段的合法候选是 `1627785261470954240`（frame 2），
  比段边界 `1627785261507921600` **早 36.97 ms**（早先"早 3.68 s"的写法是把"实际使用的
  checkpoint"与候选混算，已作废）。用 `analyze_cp_candidates.py` 可复算。C′ 的时间可用性成立，
  真正代价是"回滚后需重放的帧数/地图体量"（frame 2 对 frame 53）。

## 9. 可执行文件重链（2026-11-12 夜，必须声明）

- ASan 构建尝试使 `devel/lib/fast_livo/fastlivo_mapping` 被 make 删除且链接失败；恢复后的可执行文件为
  **`6dd71953…`**（原 `0d7e23de…`），库仍为 `18e039e1…`（v9c）。行为在库中，代码未变。
- 重链需要 `-L/home/R26534/mm/ros/lib`（libstdc++ 6.0.36；系统 GCC 11 缺少 GLIBCXX_3.4.32）与
  `-L/home/R26534/fast_livo2_deps/build/Sophus`。**链接环境与早先 run 不同，因此今晚之后的 run
  不能与早先 run 按"同一二进制"直接比较**；每份报告都要声明这一点。

## 10. C′ 历史条目的边界（来源核对后确认，2026-11-12 夜）

- `CpHistoryEntry` 只保存 `state / propagat / map / stamp / frame / 统计`，**没有**
  `cp_last_imu_ / last_prop_end_time_ / acc_s_last_ / angvel_last_`，也没有该快照对应的
  可重放区间（`snapshotCheckpoint()` 会 `replay_buffer_.clear()`）。
- 因此即使按 stamp 选中一份历史条目，也**无法恢复 IMU 延续状态、无法重放该区间**。当前唯一合法的
  用法是"只保留 + 报告候选"；在补上这些配套字段与可重放区间之前，任何按历史条目恢复的路径都必须
  **显式拒绝**该范围，而不是悄悄用活动槽。
- 另附（来源核对）：`cphist_fl_native_20261112T131213Z_563253` 实际执行的 driver 是
  `8d9cd0d` + 一处本地 `getattr(ep,"meta")` 绕过（sha `7cfcccf7…`，原件见
  `../run_provenance_131213/`），**不是** `c915197`；该 run 的 LATE 结论仍有效，但不能称为
  "c915 修复后的验证"。

## 11. v10：S3 的最小导出补齐（2026-11-13）

库 `69dc8ac5…`（可执行文件未重链，仍 `6dd71953…`）。三项都只写文件、不改估计：

1. **最终位姿**：trace 行尾新增 7 列 `pose_x pose_y pose_z qx qy qz qw`，取 `StateEstimation` 之后
   `_state` 的 `pos_end` 与 `rot_end` 四元数（行数 93 → **100**）。`vec6` 仍是更新前的量。
2. **handler 标签**：新增 LIO-only 的 `mat_lio_pre.txt` / `mat_lio_out.txt`，只在 `handleLIO()` 写，
   列与 `mat_pre/mat_out` 相同（out 多一列点数）；共享文件的双写问题不再影响判读。
3. **切空间声明**：trace 文件头明确写出——协方差是 19 维状态里 rot+pos 的 6×6 块，**body(IMU) 切空间、
   右乘 SO(3) 增量**，pos 为世界系位置；只有在该约定下才可作为 e_I 的协方差使用，否则 `NOT_AVAILABLE`。

启动探针 5/5 PASS（类布局未变：新增的全部是文件级 static）。
