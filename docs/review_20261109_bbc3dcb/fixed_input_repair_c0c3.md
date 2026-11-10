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

- **启动前快照**：脚本/输入包/两份配置/binary 的 sha256 与 revision 在**启动前**写入
  `pre_run.json`；结束时重新哈希并报告 `sources_changed_during_run`，不是退出时才去哈希。
- **清理**：`trap ... EXIT` + `INT`/`TERM` 转成正常退出，`setsid` 启动每个进程，清理时按
  **进程组**（`kill -- -PID`）逆序 TERM→KILL，roscore 的 rosmaster/rosout 子进程一并回收。
- **退出码由输出判据决定**：`output_check.json` 要求包存在、非空、可解析、
  `/aft_mapped_to_init` 消息数 >0、首末 stamp 有限且单调；recorder 非 0 或 drain 期间宿主退出同样判失败；
  receipt 写失败也返回非 0。`STATUS=OK` 与 `exit 0` 绑定，不会再出现"shell 成功 / receipt 失败"。
- **终止分类**：`PLANNED_KILL_AFTER_DRAIN` / `UNEXPECTED_NODE_DEATH` / `UNEXPECTED_PLAY_EXIT` /
  `PLANNED_TEST_ABORT`，与失败原因分开记录。
- **不覆盖**：输出路径已存在则失败，除非显式 `--overwrite`。
- **mock 失败回归** `test_fl_run_cleanup.sh` 现在**断言**而非打印：runner 退出码 == 3、
  master 端口关闭、receipt `status=FAIL` 且有 reason/termination、**每个受管 PID 都已消失**；
  任一不满足即非 0 退出。实测 `CLEANUP TEST PASSED`。
- 已用硬化后的运行器跑了一条 15 s **smoke**（`fixed_input_repair_smoke_receipt.json`，
  **SMOKE_NOT_FOR_NUMBERS**）：status `COMPLETE`，`rosbag_play=0`、`rosbag_record=0`、
  `fastlivo_node=137`（我们主动 KILL），197 条 odometry。
- 归档 C3 的**实跑**发生在运行器入库前，故 `run_receipt.status = RETROSPECTIVE_PARTIAL`，
  缺 `process exit codes`、`ROS parameter dump`、`wall-clock start` 三项，已显式列出；
  新的 smoke 不能补旧记录，只能作执行链的证据。
- 过滤审计改为**按精确 header ns join**（不再按序号），并核对 `point_step`/字段表/`frame_id`：
  源 598 帧、输出 598 帧、**598 绑定、0 不匹配、0 缺失、0 多余、0 布局不一致**。

## 8. 结论（有界指标下，读法收窄）

1. 位姿仍是第一位的：C0→C1，patch unsupported 0.625→0.315，覆盖 0.605→0.986。
2. 去污消掉剩余的几何错误：C1→C2，patch unsupported 0.315→0.059。
3. 真实链路 C3 patch unsupported 0.093、覆盖 0.985；**接近但未达到**上限，代价 46 帧缺位姿。
4. 有界指标能判坏 0.5 m / 5° 的错误候选，因此上面的数字不是"无界残差为 0"那种空转。

## 9. M3：同区域净正确几何（Q 对 C3）—— 重算版

协议见主树 `docs/MILESTONE_fixed_input_repair.md`；脚本 `run_m3_same_region.py`；
区域导出 `m3_region_export.json`（任何指标之前写出）；结果 `m3_same_region_results.json`。

**臂的定义已按审阅修正**：

- **Q = 注入前可信基座**（132 帧，宿主位姿）；
- **C3 = 同一份基座点 + 修复后的注入段帧**（400/446 帧，仓库过滤器 + FAST-LIVO2 重跑），
  即系统实际持有的地图。首版 C3 只含修复帧、漏了基座，两臂不对称，已作废。

**ROI 与输出位姿无关**：主 ROI = **整个干净参考云**（8 490 000 点），只依赖参考本身，不依赖任何被评估位姿；
index sha256 `9e062969…`，参考云 sha256 `37cf7cb6…`。敏感性 ROI = 基座支撑集（7 797 828 点，两臂共有）。

| 项 | 主 ROI（全体 8 490 000） | | 敏感性 ROI（基座 7 797 828） | |
|---|---:|---:|---:|---:|
| | **Q** | **C3** | **Q** | **C3** |
| 地图点数 | 33 000 | 133 000（基座 33 000 + 修复 100 000） | 33 000 | 133 000 |
| 覆盖代理点 | 7 797 828 | 8 421 708 | 7 797 828 | 7 797 828 |
| 覆盖率 | 0.9185 | **0.9920** | 1.0000 | 1.0000 |
| patch unsupported 点数 | 1 874 | 11 183 | 1 874 | 11 183 |
| patch unsupported 比例 | 0.0568 | 0.0841 | 0.0568 | 0.0841 |

**C3 相对 Q 新增**：

| | 主 ROI | 敏感性 ROI |
|---|---:|---:|
| 新覆盖代理点 | **623 880**（7.348 pp） | **0**（0.000 pp） |
| 新增地图点（Q 在 0.5 m 内没有） | 15 112 | 15 112 |
| 其中 supported / unsupported | 10 794 / 4 318（71.4% 支持） | 同左 |
| 新增点 patch 中位 | 见 JSON | 同左 |

**帧**：Q 132/132；C3 写 532 帧（基座 132 + 修复 400/446，缺位姿 46 个 ID 全部列出）。

### 读法与结论（按审阅要求，不为出结论换 ROI）

- 主 ROI 下 C3 比 Q 多覆盖 **7.35 pp**，但那 623 880 个点**全部在基座支撑集之外**——也就是
  C3 多写出来的那段轨迹看到的区域。这是"轨迹覆盖范围"的差异，不是"修复质量"的差异。
- 在**两臂共有的区域**（敏感性 ROI）里，两臂覆盖率都是 100%，**覆盖差为 0**；差异只剩
  15 112 个新增点（71.4% 落在参考面上）与 unsupported 比例 0.0568 → 0.0841。
- 因此：**在该 ROI 下无法用覆盖率区分两臂的修复质量**。可比的结论只有两条——C3 把注入段
  那部分场景也写进了地图（+7.35 pp，全部在基座之外），并且新增点里 71.4% 是有界 supported，
  同时它的 unsupported 点从 1 874 增到 11 183（其中 9 309 来自修复帧）。

## 10. 同帧 raw vs repaired（R 对 C3）

固定同一批帧：**C3 同时具备过滤扫描与重跑位姿的 400 帧**（446 中缺 46，ID 见 JSON）。
两臂同帧，所以轨迹覆盖范围的混淆被消除。ROI = 整个干净参考云（与输出位姿无关），
query 样本相同。脚本 `run_raw_vs_repaired.py`，结果 `raw_vs_repaired_results.json`。

| 臂 | 地图点 | 覆盖代理点 | 覆盖率 | patch unsupported | unsupported 比例 |
|---|---:|---:|---:|---:|---:|
| **R**（注入原始扫描 + 宿主位姿） | 100 000 | 5 125 990 | **0.6038** | 62 510 | **0.6251** |
| **C3**（过滤扫描 + 重估位姿） | 100 000 | 8 361 975 | **0.9849** | 9 309 | **0.0931** |

**C3 相对 R 新增的点**

| 子集 | 总数 | supported | unsupported | supported 比例 |
|---|---:|---:|---:|---:|
| 总新增 | 42 227 | **35 999** | 6 228 | 0.8526 |
| 仅 novel（基座支撑之外） | 10 581 | **7 318** | 3 263 | 0.6916 |

**R 有而 C3 没有的点**

| 子集 | 总数 | supported | unsupported | unsupported 比例 |
|---|---:|---:|---:|---:|
| 总损失 | 50 234 | 2 444 | **47 790** | 0.9514 |
| 仅 novel | 48 814 | 1 995 | **46 819** | 0.9591 |

**预先声明的判据**：`novel 子集 supported > unsupported` **且** `总新增的 unsupported 比例 ≤ R 自身`。
- novel 新增 7 318 supported vs 3 263 unsupported → 满足；
- 总新增 unsupported 比例 **0.1475** ≤ R 的 **0.6251** → 满足。

**判定：`REPAIR_BENEFIT_SUPPORTED`**（同帧、同 ROI、同 query，未换帧集或 ROI 重试）。

读法：C3 新增的点 85.3% 落在参考面上；被替换掉的 R 点 95.1% 本来就是 unsupported——
修复主要是在删坏点、补好点，而不是简单地把地图搬了个位置。参考面仍是干净跑地图而非 GT。

## 11. 冻结 446 的服务完整度与健康区代价

预注册于主树 `docs/MILESTONE_fixed_input_repair.md`；脚本 `run_m4_completeness.py`；
结果 `completeness_healthy_region_results.json`。provenance `OFFLINE_NATIVE_REESTIMATION`，
参考面是干净跑地图（proxy，非 GT）。

### 11.1 46 个缺位姿帧：逐帧归因

| 归因 | 帧数 |
|---|---:|
| 过滤包缺扫描 | **0** |
| 位姿流无近邻（>1 s） | **0** |
| **配对规则判 MISSING**（夹逼间隔超过 75 ms） | **46** |

- 46 帧**全部都有过滤后的扫描**——不是过滤器丢的；
- 最近位姿距目标 **20.2–66.5 ms**（中位 61.6 ms），夹住目标的相邻位姿间隔 **133.2–133.6 ms**；
- 也就是说重跑那段里程计是 ~7.5 Hz（正常 ~15 Hz），配对规则不允许跨 133 ms 内插，故判 MISSING；
- 两段：`1627785275.808–1627785285.226`（约 9.4 s）与 `1627785295.246–1627785295.446`；
- **可恢复性**：在冻结协议下 **0 帧可恢复**；仅在放宽 75 ms 间隔上限时可恢复 **46 帧**——
  协议不允许，所以不恢复，也不改阈值。

### 11.2 健康区（非注入帧）误删

注入窗 `[1627785275.607, 1627785295.546]` 之外：

| 项 | 值 |
|---|---:|
| 帧数 | 398 |
| 总点数 | 20 062 836 |
| 删除点数 | **0** |
| 删除比例 | **0.0000** |
| 有任何删除的帧 | **0** |
| 帧删除比例 >0.1% | 0 |
| 每帧删除点数 min/p50/p95/max | 0 / 0 / 0 / 0 |

对照（窗内 200 帧）：10 110 613 点，删除 8 974 676（**0.8876**）。
即"窗外 0/20,062,836"独立复核成立：过滤器在健康区没有付出任何删除代价，
窗内外的差异是 0.8876 对 0。

### 11.3 服务完整度（446 为分母）

| 口径 | 帧数 | 完整度 | 每帧地图点 |
|---|---:|---:|---:|
| **冻结 446**（缺帧记为 missing，不剔除） | 446 | **0.8969** | 224.2 |
| 旧口径（分母 = 存活帧） | 400 | 1.0000 | 250.0 |

缺帧 46 = 10.31%，全部为上面的 `PAIRING_RULE_MISSING`。
覆盖率与 patch unsupported 是**地图本身**的属性，不随分母变化（见 §4/§10 同帧对照）；
随分母变化的是任何按帧的比率，故两套口径并列给出，不混用。




## 12. 速率诊断（第一版，已作废）

> 结论 `SCHEDULING_CONTENTION` 已撤回：那段 30 s 片段从 `1627785269.996` 起，跳过约 8.92 s 健康前缀，
> 宿主是冷启动重新初始化的；而且只报了 load average，没有记录可运行等待。以下 §12b 为准。

## 12b. 受控 vs 非受控重做（完整前缀）

脚本 `run_rate_diagnosis.py` / `run_rate_controlled.py`，结果 `rate_controlled_results.json`。
片段从**原始输入起点** `1627785261.0` 起（39 s），覆盖两段缺帧区间与邻段。A 非受控（load 中位 291.6，
procs_running 峰 117），B 受控（`taskset` 到启动时最空闲的 8 核，load 中位 102.4）。

| | A 非受控 | B 受控 |
|---|---:|---:|
| odom 中位间隔 | 66.66 ms | 66.66 ms |
| 慢间隔（>100 ms） | 63 / 503 | 63 / 503 |
| 段1内 / 邻段慢比例 | 43.30% / 4.70% | 43.30% / 4.70% |
| 慢间隔**布尔掩码** | — | **与 A 相同**（不是完整序列逐位） |
| 节点运行队列等待占比 | 1.19% | 2.06% |

注入起点两侧（两次运行一致）：之前 **0.0%**，之后 **20.86%**，首个慢间隔在 onset + 0.274 s。

**判定：`CONTENTION_WEAKENED`** —— 受控运行下慢发布没有消失，故不支持调度争用；慢间隔随注入内容出现，
内容效应只记 **SUSPECTED**（同一 filtered clip，无 clean/未过滤对照），不在此链上继续排障。

## 13b. room_02 独立序列确认（结论：不支持净收益）

协议 `docs/MILESTONE_fixed_input_repair.md` @ 107c05a。参考面 **`CLEAN_RUN_FROM_RAW_WINDOW`**：
从 `M2DGR/raw/room_02.bag`（sha `ee621ccb…`）同转换、同窗口、零注入重建 clean 窗口（sha `809b98f1…`），
再跑 FAST-LIVO2（标准带图像 config，receipt `room02_clean_run_receipt.json`，864 条 odometry，OK）。

oracle 窗（逐帧 buffer 相等）：599 帧中 **199 帧不同**，`1627643759.554–1627643779.393`；窗外 400 帧字节相同。
冻结总体：primary scans 599、healthy prefix 171、quarantine keys 398、frame set **326**（缺 72，全部
`NO_RERUN_POSE_UNDER_THE_75MS_RULE`）。

| | R（原始+宿主） | C3（过滤+重估） |
|---|---:|---:|
| 覆盖代理点 / 比例 | 6 617 272 / 0.7672 | 5 995 707 / **0.6952** |
| patch unsupported | 37 370 / 0.4585 | 53 705 / **0.6590** |

新增 64 315（10 724 sup / 53 591 unsup），其中 novel 53 027（**60 / 52 967**）；lost 49 160（15 028 sup）。
服务完整度 326/398 = 0.8191；健康区删除 919 702 / 20 576 778（4.47%，52 帧）。
判据两条都不满足 → **`SAME_FRAME_COMPARISON_DOES_NOT_SUPPORT_NET_BENEFIT`**。

## 13c. 五臂分解（按时间分区）

脚本 `run_room02_decomposition.py`，结果 `room02_decomposition_results.json`。
oracle 为逐行 diff（注入帧与同戳 clean 帧不同的行即注入点），精确而非几何模型。

| 臂 | 扫描 | 位姿 | 窗内 unsup | 窗外 unsup | 覆盖 |
|---|---|---|---:|---:|---:|
| A | raw | 宿主 | 0.7259 | 0.2879 | 0.7672 |
| B | raw | clean 参考 | 0.7353 | 0.0039 | 0.9990 |
| C | oracle | clean 参考 | **0.0094** | 0.0039 | 0.9988 |
| D | filter | clean 参考 | **0.0111** | 0.0045 | 0.9988 |
| E | filter | 重估 | 0.1246 | **1.0000** | 0.6952 |

Delta（全集 / 窗内 / 窗外）：A→B −0.1697 / +0.0095 / −0.2841；B→C −0.2828 / **−0.7259** / 0.0000；
C→D +0.0010 / +0.0016 / +0.0006；D→E +0.6519 / +0.1135 / **+0.9955**。

读法限定：E 的窗外 1.0000 是轨迹崩掉后的后果，不是独立的窗外分区发现；失效起点是窗内 0.1246。
C/D 用 clean 参考位姿、与评价 proxy 同源，绕过宿主从 actual-filter 观测估计状态，因此**不能据此排除"过滤器→状态"**。

## 13d. E_actual vs E_oracle vs E_hybrid

脚本 `run_e_oracle_vs_actual.py`，结果 `room02_e_oracle_results.json`。共同集 **323 帧**（不是 326），
GT 匹配 317。ATE 为 **`FULL_ALIGNMENT_DIAGNOSTIC`**，冻结前缀协议数字单列。

| 臂 | 覆盖 | unsupported | ATE（FULL_ALIGNMENT_DIAGNOSTIC） |
|---|---:|---:|---:|
| E_actual | 0.6951 | 0.6649 | 315.16 m |
| E_oracle | 0.9988 | 0.0073 | 0.074 m |
| E_hybrid（窗内 oracle + 窗外 filter） | 0.9988 | **0.0069** | — |

E_hybrid 保留了过滤器在健康区的全部 919 702 点删除仍与 oracle 等价 → 健康区误删不是原因。
逐行审计（窗内）：背景行 1 186 220，过滤器保留 1 162 613（98.0%）、误删 23 607（1.99%）、
漏掉注入行 1 265（FNR = 1 265 / 9 073 943 = **0.00013941**；旧量 1 265/1 186 220 改名为
`background_normalized_residual_rate`）。

## 13e. 单因素 2×2（每格 2 次）

四包由预注册流程生成并经等价核验；本机同 runner/prefix/config 每格 2 次，8 份 receipt 入库。

| 格 | rep1 ATE | rep2 ATE | fail 次数 | 稳定 |
|---|---:|---:|---:|---|
| O | 0.072 | 14.439 | 1/2 | 否 |
| O+F | 593.026 | 14.872 | 2/2 | 是 |
| O−B | 48.847 | 19.673 | 2/2 | 是 |
| O+F−B | 554.561 | 0.301 | 1/2 | 否 |

预注册要求"O+F−B 两次 fail 且 O+F、O−B 都不 fail"才可称交互；实际 O+F 与 O−B 都 2/2 fail →
**`NOT_A_CLEAN_INTERACTION`**，且 O 与 O+F−B 各自跨模式 → 预注册交互形态未获支持、重复不稳定；n=2 不足以声称"交互不存在"或"方差统计上压过所有因素"，四格保持 UNKNOWN。

## 13f. 方差对照（同一格 4 次，只改运行次序）

| 格 | 4 次模式 | 跨模式 | 合并先前 2 次（n=6） |
|---|---|---|---|
| O | BAD, GOOD, BAD, BAD | 是 | GOOD 2 / BAD 4 |
| O+F−B | UNCLEAR, UNCLEAR, BAD, BAD | 是 | GOOD 1 / BAD 3 / UNCLEAR 2 |

两格都跨模式 → **`SEQUENCE_UNUSABLE_FOR_SINGLE_RUN`**。不是非黑即白：O+F−B 的两次 UNCLEAR
（unsupported 0.114 / 0.190，ATE 0.69 / 1.93）说明所谓"双稳"其实是连续分布的两端；该词已不再使用。

## 13g. 非确定性来源（源码阅读）

详见 `FAST_LIVO2_variance_sources.md`：
S1 `src/vio.cpp:1554` OpenMP 归约（浮点求和顺序随调度）；S2 `CMakeLists.txt:46-58` 自动开 `MP_EN`、
`omp_set_num_threads()` 写死使 `OMP_NUM_THREADS` 无效；S3 `src/LIVMapper.cpp:537` 5 kHz 墙钟轮询 +
`sync_packages`；S4 `imu_int_frame: 30` 的 IMU 初始化窗口由 S3 决定；S5 4 ms 墙钟定时器；
S6 无随机数、队列 200000 不丢消息、odometry 时间戳非墙钟。

## 13h. T1：关掉 OpenMP 并行（只改 MP_EN）

`option(NO_MP)` 默认 OFF，两处 `#ifdef MP_EN` → `#if defined(MP_EN) && !defined(NO_MP)`，加一行启动日志。
旧 binary `ca1959c4…` 已备份；新 binary `6e0a3e57…`；rate/config/prefix/bag/runner 未动。

同格 O 两次：r1 GOOD（0.9467 / 0.0960 / 0.309 m），r2 BAD（0.6767 / 0.6913 / 336.75 m）。
对齐首帧差 1.13 cm（且两次首帧 stamp 相同，均为 onset 帧），但**跨模式** → `GO_TO_T2`。
注：`first_stamps` 记的是 onset 帧，首输出应看 receipt 的 `output.first_stamp_sec`。

## 13i. T2：串行 + 固定核 + 低负载

`taskset -c 0-7` + 同 nice + 机器空闲（load 中位 52.1 / 128 核）。r1 GOOD（0.9988 / 0.0067 / 0.072 m），
r2 BAD（0.6933 / 0.6552 / 17.910 m）。对齐首帧差 **1.9 mm**，仍跨模式 → `GO_TO_T3`。

三组对照：归档 1.6–2.9 cm、T1 1.13 cm、T2 1.9 mm，首帧压到毫米级仍分叉 → 种子不是归约顺序、不是调度/负载。

## 13j. T3a：去掉墙钟相位依赖（`DET_SYNC`）

`AsyncSpinner(1)` 接管回调，主循环在条件变量上阻塞（20 ms 兜底），lidar 回调释放锁后 notify；
`option(DET_SYNC)` 默认 OFF。其余保持 T2。

| build | runs | 模式 | ATE |
|---|---|---|---|
| A（exec `76359f53` + lib X） | 2 | GOOD, GOOD | 0.073 / 0.311 m |
| B（exec `76359f53` + lib `6337ec0f`） | **4** | **BAD, BAD, GOOD, GOOD** | 24.17 / 17.36 / 0.071 / 0.073 m |

同一 build 跑四次再次分叉 → S3 未被确立为种子。provenance 教训：两轮可执行文件 sha 相同，行为在
`liblaser_mapping.so` 里，receipt 只记 exec sha 不够，结果中已补 `library_sha256`。
`room02_T3a_results.json` 的 `S3_ACCEPTED_AS_SEED` 指 build A 两次，已标 `superseded_by`。

**止损触发**：T1/T2/T3a 三个单变量控制都做完方差仍在，停止"剩下的只有 X"的排除法。

## 13k. 适用性检查：hall_01 干净序列 4 次

同 build B、同 `NO_MP`+`DET_SYNC`、`taskset 0-7`、低负载，在不注入的 `hall01_100_160.bag` 上跑 4 次；
参考面为 hall_01 干净跑地图 5 cm 体素降采样（2 422 718 点 / 8 490 000），四次同一共同帧集（562/566）。

| run | NN supported | patch unsupported |
|---|---:|---:|
| r1 | 1.0000 | 0.2282 |
| r2 | 1.0000 | 0.2790 |
| r3 | 1.0000 | 0.2427 |
| r4 | 1.0000 | 0.2715 |

四次按 0.10/0.50 都是 UNCLEAR（阈值对 hall_01 太粗），但原始值只跨 **0.0508**，NN supported 全 1.0000；
对照 room_02 的 0.007 vs 0.66–0.69（跨度 0.68）→ **`STABLE_ON_HALL01_ROOM02_IS_SEQUENCE_SPECIFIC`**。
限定：该阈值是 room_02 分布的形状，不能跨数据集硬套；结论基于原始值与 NN，不是"四次同 mode"；
hall_01 无注入、窗口 100–160 s、参考是干净跑 proxy 非 GT、n=4；只界定现象不解释根因。

## 13l. hall_01 B4：运行成本与缺测敏感性

| 臂 | 运行身份 | rate / drain | wall time | 峰值内存 |
|---|---|---|---:|---|
| R | `/tmp/run43.sh:14` → `fl_record.sh`（pre-runner，无 receipt） | 0.5 / 150 s | 296 s（*派生*） | UNAVAILABLE |
| C3 | `fl_run_20261109T105559Z_2414230/receipt.json` | 1.0 / 40 s | 122.9 s（*实测*） | UNAVAILABLE |

峰值内存两项不可得（旧脚本不采样、硬化 runner 未采 `VmHWM`），列为待补字段，不回填。

缺测敏感性（剔除与 46 个缺测帧相距 <1 s 的 81 帧，400 → 319）：

| 臂 | coverage | patch unsupported | full-ATE |
|---|---|---|---|
| R 全部 400 → 319 | 0.6278 → 0.7977 | 0.5986 → 0.4200 | 1.909 → 1.617 m |
| C3 全部 400 → 319 | 0.9850 → 0.9759 | 0.0957 → 0.0975 | 0.319 → 0.274 m |

缺测邻域只占 81 帧却把 R 拉高 0.18 / 0.29 m，C3 几乎不动 → **排序不变，46 帧缺测不承担结论**。
本表 coverage 用不截断的完整干净参考面（0.6278→0.9850），四臂表用 12 万点 proxy（0.6038→0.9849）。


## 14. 复现

```bash
python3 -B docs/review_20261109_bbc3dcb/run_fixed_input_repair_c0c3.py filter-audit
python3 -B docs/review_20261109_bbc3dcb/run_fixed_input_repair_c0c3.py measure
python3 -B docs/review_20261109_bbc3dcb/run_m3_same_region.py
python3 -B docs/review_20261109_bbc3dcb/run_raw_vs_repaired.py
python3 -B docs/review_20261109_bbc3dcb/run_m4_completeness.py
python3 -B docs/review_20261109_bbc3dcb/run_rate_diagnosis.py   # §12a, superseded
python3 -B docs/review_20261109_bbc3dcb/run_rate_controlled.py
python3 -B docs/review_20261109_bbc3dcb/run_room02_confirmation.py
python3 -B docs/review_20261109_bbc3dcb/run_room02_decomposition.py
python3 -B docs/review_20261109_bbc3dcb/room02_filter_row_audit.py
python3 -B docs/review_20261109_bbc3dcb/run_e_oracle_vs_actual.py
python3 -B docs/review_20261109_bbc3dcb/run_2x2_analysis.py
python3 -B docs/review_20261109_bbc3dcb/run_bistability_analysis.py
bash docs/review_20261109_bbc3dcb/fl_run_isolated.sh <bag> <new-out> 0.5 60
bash docs/review_20261109_bbc3dcb/test_fl_run_cleanup.sh
```

未改 node/core/manager、未改 `fim_and_holdout.py` 默认值、未改已发表 manifest、未 push。