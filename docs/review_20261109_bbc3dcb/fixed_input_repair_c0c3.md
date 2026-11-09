# 固定输入的端到端修复测量 C0–C3（M1 修订版：有界几何 + 统一配对 + 真实运行链）

序列与故障固定：`hall_01`，4.30 m 塑料布注入，输入 `hall01_inj43.bag`。key 集与评分规则来自
M0 冻结协议 `docs/milestone_m0_keys.json` @ `f36137b`（整数纳秒边界），本实验不自选集合。

- 脚本：`run_fixed_input_repair_c0c3.py`
- 运行器：`fl_run_isolated.sh`（每次运行独立目录 + trap 清理 + 失败判据）
- 清理回归：`test_fl_run_cleanup.sh`
- 产物：`fixed_input_repair_c0c3_results.json`、`fixed_input_repair_frozen_keys.json`、
  `fixed_input_repair_filter_report.json`、`fixed_input_repair_filter_audit.json`、
  `fixed_input_repair_smoke_receipt.json`

## 1. 本轮针对审阅的修改

| 项 | 修改 |
|---|---|
| **无界点面残差不能证明表面准确** | 新增**有界**指标：到干净参考的 NN 距离（上限 0.5 m，超限记 **unsupported**）+ 局部**有界 patch** 距离（邻域半径 ≤0.30 m、平面拟合 RMS ≤0.02 m）。unsupported 比例单列，tail 只在 supported 内部统计。无界点面数保留为**辅助**，不再作为准确度主张。 |
| **撤回"达到 oracle ceiling"** | 见 §5：有界指标下 C3 的 patch unsupported 是上限的 **1.57 倍**（0.0931 vs 0.0593）。该表述已撤回。 |
| **四条件位姿配对不统一** | 统一为一条规则（20 ms 最近 / 75 ms 内插 / 否则 **MISSING**），四条件同一实现；报实际 dt 与内插比例（§4）。C1/C2 由此暴露 **12 帧**此前被"最近帧"静默顶替。 |
| **运行记录只是快照** | 运行器入库，改为**每次运行一个目录**：日志、输入/配置/binary/脚本 hash、ROS 参数 dump、退出码、输出 hash 与消息覆盖。失败路径有 trap 清理，且有 mock 失败回归。 |
| **过滤计数靠两个裁剪数组相减** | 新增 `filter-audit`：按**原始 row index** 逐帧、全分辨率计数，并导出 keep-index；C2/C3 的计数改由它提供（§6）。 |
| **缺证据时 KeyError** | `_meta.real_filter` 缺失时显式写 `status: MISSING`，不再在后续索引处崩。 |
| **命名混淆** | `well_constrained_query_fraction` → `reference_query_well_fraction`，并注明分母是 40 000 个**参考查询点**，与 arm 的 well 比例不是同一个量。 |

## 2. 冻结集合与配对

| 集合 | 数量 | 复核 |
|---|---:|---|
| primary（配对隔离扫描） | 446 | ns 列表 hash 逐位复现 `89a8bfa1…`，且等于 `ns >= start_ns` |
| diagnostic subset | 252 | `2bb7fe3d…`；四条件都有支撑的 250 |
| healthy prefix | 132 | `74995bb9…`；对齐用 120 对 |
| 配对规则外原始扫描 | 20 | 单列，不进分母 |

**位姿配对（四条件统一）**：最近 ≤20 ms → 用；否则若夹住目标的两帧间隔 ≤75 ms → 插值；否则 MISSING。

| 条件 | nearest | interpolated | missing | dt p95 |
|---|---:|---:|---:|---:|
| C0 | 361 | 217 | 0 | 18.53 ms |
| C1 / C2 | 355 | 211 | **12** | 18.59 ms |
| C3 | 317 | 215 | **46** | 18.71 ms |

旧实现里 C1/C2 用"最近干净帧、无间隔上限、无缺测"，C3 用 50 ms 最近——三者不可比。现在同一规则下
C1/C2 有 12 帧、C3 有 46 帧无合格位姿，全部单列，不从分母静默剔除。

## 3. 有界几何定义

- **NN（有界最近邻）**：到干净参考云（8 490 000 点，不截断）的最近距离；上限 **0.5 m**，超过即
  **UNSUPPORTED** 并从 tail 中排除。上限以内只统计 `>0.10 m` 与 `>0.25 m`——在上限处统计 `>0.5 m`
  恒为 0，会读成完美结果。
- **patch（有界局部面）**：8 邻域 PCA 平面，且要求邻域半径 ≤**0.30 m**、平面拟合 RMS ≤**0.02 m**；
  不满足或 NN 超限即 UNSUPPORTED。距离是该局部平面上的点到面距离。
- **辅助**：无界点面残差照常报告，但明确标 AUXILIARY——审阅的反例（原点 0.2 m 平面片 vs 查询点
  (100,0,0)，残差 0、最近距离 99.9 m）说明它单独不能主张表面准确。

## 4. 结果

### 4.1 共同支撑 400 帧（四条件同一批 key）

| 条件 | 标签 | NN unsupported | patch unsupported | patch >0.10 (sup.) | patch >0.25 (sup.) | patch 中位 | 辅助无界 >0.5 | 覆盖@0.5 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| C0 | `REAL_HOST` | 0.3755 | **0.6251** | 0.1811 | 0.0193 | 0.0180 | 0.3135 | 0.6047 |
| C1 | `OFFLINE_CONSTRUCT` | 0.2147 | **0.3147** | 0.0400 | 0.0055 | 0.0042 | 0.1937 | 0.9864 |
| C2 | `ORACLE_CEILING` | 0.0000 | **0.0593** | 0.0000 | 0.0000 | 0.0041 | 0.0000 | 0.9840 |
| C3 | `OFFLINE_NATIVE_REESTIMATION` | 0.0015 | **0.0931** | 0.0140 | 0.0004 | 0.0069 | 0.0013 | 0.9849 |

### 4.2 primary 446（分母不同，单列）

| 条件 | 提交帧 | 缺位姿 | NN unsup | patch unsup | patch >0.25 | 覆盖@0.5 |
|---|---:|---:|---:|---:|---:|---:|
| C0 | 446 | 0 | 0.3845 | 0.6307 | 0.0199 | 0.6146 |
| C1 | 446 | 0 | 0.2490 | 0.3567 | 0.0067 | 0.9878 |
| C2 | 446 | 0 | 0.0000 | 0.0640 | 0.0000 | 0.9844 |
| C3 | **400** | **46** | 0.0015 | 0.0931 | 0.0004 | 0.9849 |

诊断子集 250：C0 0.3299/0.6001，C1 0.0066/0.0556，C2 0.0000/0.0475，C3 0.0000/0.0652（NN unsup / patch unsup）。

### 4.3 反例回归（有界指标必须判坏）

把 C1 的地图整体施加误差后，用同一有界指标评分：

| 施加的误差 | NN unsupported | patch unsupported | 判定 |
|---|---:|---:|---|
| 无（C1 基线） | 0.2489 | 0.3567 | 正常 |
| 平移 0.5 m | 0.539 | **0.743** | `JUDGED_BAD` |
| 绕 z 转 5° | 0.557 | **0.755** | `JUDGED_BAD` |

有界指标确实把错的候选判坏——这是"tail 为 0"不能单独证明的事。

## 5. 撤回与限定

- **撤回"C3 达到 oracle ceiling"**：有界 patch unsupported C3 = 0.0931、C2 = 0.0593，C3 是上限的
  **1.57 倍**；patch 中位 0.0069 vs 0.0041；NN unsupported 0.0015 vs 0.0000。C3 很接近，但**没有达到**，
  日志里的该表述已由审阅撤回，本文件不再使用。
- **0.028 m 只说明该平移统计可重复**：未过滤重跑与归档位姿的对比**只比了位置**，没有比旋转，
  也没有覆盖消息计数与窗后差异（窗后 mean 0.488 m）。因此这不是完整确定性的结论。
- **重建是每帧 250 点的 sidecar，不是宿主输出的配准地图**：每个 keyframe 只取自身扫描的 250 点按
  该条件位姿摆放；它衡量的是位姿+点源，不是 FAST-LIVO2 内部建图。
- C1/C2 是 oracle/proxy 一致性控制，不是独立 GT 准确度；C2 删除污染点**不恢复被遮挡背景**，
  不是普适最优地图的数学上界。
- 连通性固定 0.10/0.20 m 体素、26 邻接，不作拓扑正确性判据；轨迹支撑缺口四条件均为 0，无区分度。

## 6. 过滤计数与点身份

`filter-audit` 对 598 帧逐帧、全分辨率执行**车间里真实的** `filter_self_consistent_near_field_contaminants`
（`MixtureFilterConfig()` 默认值），记录每帧 `n / n_kept / oracle_removed` 与**原始 row index** 的 keep mask：

- 全局 keep mask sha256：见 JSON `filter_audit.global_keep_mask_sha256`；
- **与输出 bag 逐帧绑定**：598/598 帧的保留行字节 hash 与 `hall01_inj43_filtered.bag` 完全一致，
  `frames_mismatched = 0`；
- cohort 计数（不再用两个裁剪数组相减）：primary 446 帧上 filter 剔除 **0.3981**、oracle **0.4197**；
  **注入窗内** filter **0.8876**、oracle **0.8855**；
- 保存原始扫描的 keep index（`/tmp/filtered_bag_keep_index.npz`），可由输入 bag 重建输出。

附带记录：`repairable=false` 的窗内帧 189/200。

## 7. 运行收据

`fl_run_isolated.sh` 每次运行写 `/tmp/fl_run_<utc>_<pid>/`：`command.txt`、`roscore.log`、`record.log`、
`node.log`、`play.log`、`ros_params.yaml`（实际加载的 ROS 参数 dump）、`receipt.json`（输入/配置/binary/
脚本 hash、退出码、输出 hash、消息数、首末 stamp）。

- **清理**：`trap cleanup EXIT`，按 PID 逆序 TERM→KILL，只杀自己启动的进程。
- **失败判据**：master 60 s 未就绪、node 未启动/中途死亡、`rosbag play` 非 0、输出包缺失/为空/
  `/aft_mapped_to_init` 消息数为 0，全部 `exit` 非 0，不再以 `stat` 成功结尾。
- **不覆盖**：输出路径已存在则失败，除非显式 `--overwrite`。
- **mock 失败回归** `test_fl_run_cleanup.sh`：`FL_TEST_FAIL_AFTER_START=1` 让脚本在三个进程都起来后
  失败，实测 `exit=3`、master 端口关闭、receipt 写 `FAIL`。
- 已用硬化后的运行器跑了一条 15 s **smoke**（`fixed_input_repair_smoke_receipt.json`，
  **SMOKE_NOT_FOR_NUMBERS**）：status `COMPLETE`，`rosbag_play=0`、`rosbag_record=0`、
  `fastlivo_node=137`（我们主动 KILL），197 条 odometry。
- 归档 C3 的**实跑**发生在运行器入库前，故 `run_receipt.status = RETROSPECTIVE_PARTIAL`，
  缺 `process exit codes`、`ROS parameter dump`、`wall-clock start` 三项，已显式列出。

## 8. 结论（有界指标下，读法收窄）

1. 位姿仍是第一位的：C0→C1，patch unsupported 0.625→0.315，覆盖 0.605→0.986。
2. 去污消掉剩余的几何错误：C1→C2，patch unsupported 0.315→0.059。
3. 真实链路 C3 patch unsupported 0.093、覆盖 0.985；**接近但未达到**上限，代价 46 帧缺位姿。
4. 有界指标能判坏 0.5 m / 5° 的错误候选，因此上面的数字不是"无界残差为 0"那种空转。

## 9. 复现

```bash
python3 -B docs/review_20261109_bbc3dcb/run_fixed_input_repair_c0c3.py filter-audit
python3 -B docs/review_20261109_bbc3dcb/run_fixed_input_repair_c0c3.py measure
bash docs/review_20261109_bbc3dcb/fl_run_isolated.sh <bag> <new-out> 0.5 60
bash docs/review_20261109_bbc3dcb/test_fl_run_cleanup.sh
```

未改 node/core/manager、未改 `fim_and_holdout.py` 默认值、未改已发表 manifest、未 push。
