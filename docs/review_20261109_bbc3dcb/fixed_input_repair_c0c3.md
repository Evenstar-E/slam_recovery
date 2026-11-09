# 固定输入的端到端修复测量 C0–C3（M0 协议，整数纳秒边界）

序列与故障固定：`hall_01`，4.30 m 塑料布注入，输入 `hall01_inj43.bag`。key 集、参考面与评分规则
来自 M0 冻结协议 `docs/milestone_m0_keys.json` @ `f36137b`（整数纳秒边界），本实验不再自选集合。

- 脚本：`run_fixed_input_repair_c0c3.py`
- 原始输出：`fixed_input_repair_c0c3_results.json`
- 冻结 key（含 ns 与哈希复核）：`fixed_input_repair_frozen_keys.json`
- 真实过滤器逐帧记录：`fixed_input_repair_filter_report.json`

> 旧的 445/259/133（6 位浮点边界，commit `057c266`）结果已在结果 JSON 的
> `superseded_by_ns_boundary` 里保留记录并标明**只作留档、不得引用**。浮点边界会把**第一帧注入扫描**
> 划进 healthy prefix；本文件全部按整数纳秒重算。

## 1. 冻结集合（M0 @ f36137b）

| 集合 | 数量 | M0 sha256 | 本实验复核 |
|---|---:|---|---|
| primary（配对隔离扫描） | **446** | `89a8bfa1…d3235a3f` | **逐位复现**，且与 `ns >= start_ns` 集合相同 |
| diagnostic subset | 252 | `2bb7fe3d…00101f5` | 逐位复现；四条件都有支撑的 **250** 帧 |
| healthy prefix | 132 | `74995bb9…62268788` | 逐位复现；对齐用 120 对（12 帧在干净跑丢弃头部内） |
| 配对规则外的原始扫描 | 20 | —（文件未给 hash） | 全部确实未被配对，**单列**，不进任何分母 |

- 哈希编码按文件声明：整数 ns 排序后逗号连接再 sha256；本次用**从 bag header 读出的真实 ns**重算，
  三个集合全部 `match=True`。
- 关键帧身份不再经过浮点：`load_scan_ns()` 直读 `header.stamp.sec/nanosec`，缓存按内容 sha 键控。
  理由写在代码里：1.6e9 s 处的 double 步长约 240 ns，6 位小数根本表示不了纳秒边界。

## 2. 四个条件与标签

| | 标签 | 扫描 | 位姿 | 说明 |
|---|---|---|---|---|
| **C0** | `REAL_HOST` | 污染 | 宿主（归档 FAST-LIVO2） | 无修复 |
| **C1** | `OFFLINE_CONSTRUCT` | 污染 | 参考（干净位姿经注入前 SE(3) 搬入） | oracle/proxy 一致性控制，**不是** GT 准确度 |
| **C2** | `ORACLE_CEILING` | oracle 去污 | 参考 | **仅上限**；不恢复遮挡背景，**不是**普适最优地图界 |
| **C3** | `OFFLINE_NATIVE_REESTIMATION` | 仓库真实过滤 | 实际重估（宿主重跑） | **不叫 `DEPLOYABLE_REPAIR`** |

每个条件都用自己的 pre-onset SE(3) 对齐到干净帧（120 对，只用注入前）：C0/C1/C2 `|t|=0.7413 m`，C3 `0.8444 m`。

参考面：干净跑**全部 8 490 000 点，不截断**；每点距离是它自己 8 邻域 PCA 平面的**点到面**距离，
不设全局 cap、不用 sigma。覆盖率查询点从干净点云随机抽 40 000 个。

## 3. 结果（共同支撑 402 帧，四条件同一批 key）

| 条件 | tail>0.25 | tail>0.5 | tail>1.0 | 中位 | well 比例 | 覆盖@0.5 | 分量@0.1m | 最大分量 | 缺口 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C0 | 0.4461 | **0.3138** | 0.1278 | 0.1771 | 0.375 | **0.6047** | 13494 | 0.169 | 0 |
| C1 | 0.2518 | **0.1947** | 0.0937 | 0.0078 | 0.684 | **0.9864** | 27352 | 0.359 | 0 |
| C2（上限） | 0.0000 | **0.0000** | 0.0000 | 0.0044 | 0.940 | **0.9840** | 11286 | 0.270 | 0 |
| C3（真实链路） | 0.0032 | **0.0013** | 0.0011 | 0.0077 | 0.908 | **0.9856** | 12703 | 0.273 | 0 |

"well 比例"＝落点邻域半径 <0.30 m 且参考平面拟合 RMS <0.02 m 的点占比，即**落在被充分采样的真实表面上的点占比**。

按 primary 446 单独报（分母不同）：C0 0.3230 / 0.6146 / well 0.369；C1 0.2253 / 0.9878 / 0.643；
C2 0.0000 / 0.9844 / 0.936；C3 0.0013 / 0.9856 / 0.908，但 C3 只有 **402/446** 帧有位姿
（`missing_pose_ids` 44 个全部列出，缺观测 0）。

诊断子集（250 帧）：C0 0.2658 / 0.5595；C1 0.0059 / 0.9674；C2 0.0000 / 0.9667；C3 0.0000 / 0.9673。
子集上 C1 比 primary 低一个量级——该子集本身偏向有支撑的帧，只能作诊断。

## 4. C3 记录（可复跑）

| 项 | 值 |
|---|---|
| 原始扫描包 | `/tmp/fastlivo/hall01_inj43.bag` · `aa740037…` |
| 转换（过滤）包 | `/tmp/fastlivo/hall01_inj43_filtered.bag` · `c90300cb…` |
| 重跑位姿包（C3） | `/tmp/fastlivo/res_h1_inj43_filtered.bag` · `1109fccf…` |
| 控制组位姿包 | `/tmp/fastlivo/res_h1_inj43_rerun_unfiltered.bag` · `2a3880ad…` |
| 宿主 | FAST-LIVO2 · `fastlivo_mapping` · binary `ca1959c4…` |
| 宿主源码 revision | `0d2c0346107b75b59934975adec9a6eeeb913c64` |
| 配置 | `m2dgr.yaml` + `camera_m2dgr.yaml`（sha256 见 JSON） |
| 运行参数 | rate 0.5，drain 60 s，录 `/aft_mapped_to_init`，私有 ROS master 端口 |

四条完整命令见结果 JSON 的 `_meta.c3_record.commands`。

- **过滤器**：`filter_self_consistent_near_field_contaminants` + 出厂 `MixtureFilterConfig()`，
  逐帧独立判定，**不看时间窗、不看干净包**：窗内 200 帧平均剔除 **0.8876**，窗外 398 帧 **0.0000**，
  剔除 >10% 的帧恰好 200 个；同时 `repairable=false` 的有 **189/200** 帧。
- **主机可复现性**：未过滤同包重跑 vs 归档位姿（pre-onset 对齐）：注入前 mean **0.011 m**、
  窗内 mean **0.028 m**（p95 0.049）、窗后 0.488 m。窗内 3 cm 远小于要测的米级效应。

## 5. C1/C2 的定位（按审阅限定）

- C1/C2 用**干净跑位姿**并对**干净跑地图**评分 → **oracle/proxy 一致性控制**，不是独立 GT 准确度。
- C2 删点**不恢复被遮挡背景** → 不是"普适最优地图"的数学上界，只是"没有污染点"的上界。
- oracle 污染 identity **只在绝对注入窗内评分**（窗内 30 个抽样帧标记率 0.890，与 88% 方位扇区一致）；
  窗外同扇区被标记的点是**健康背景**，只报"若不设窗限的误删率"约 3.3%，**不计 true positive**。

## 6. 连通性指标

固定 0.10 m / 0.20 m 两档体素、26 邻接，单位为体素；**不作拓扑正确性的唯一判据**。
C1 分量数最高（27352）、最大分量占比也不是最好，因为位姿准确的地图铺在更大的真实表面上，
而每帧只留 250 点，稀疏度本身会抬高分量数。C2 与 C3 接近（11286/0.270 与 12703/0.273）。
轨迹支撑（1.0 m 内、且必须来自**其他帧**的点）四条件全为 0，无区分度。

## 7. 结论（ns 边界重算后）

1. **位姿优先**：C0→C1，尾部 0.3138→0.1947，覆盖 0.6047→0.9864，well 比例 0.375→0.684。
   C0 位姿相对参考轨迹中位偏差 5.85 m、p90 18.5 m、最大 19.7 m。
2. **去污消掉剩余尾部**：C1→C2，尾部 0.1947→0.0000，well 比例 0.684→0.940，覆盖基本不变。
3. **真实 C3 落在上限 0.1–3 pp 内**：尾部 0.0013、覆盖 0.9856、well 0.908；代价 44 帧缺位姿。
4. 过滤器在这一条真实序列上判定近乎精确，但只是单一序列、单一注入器，且注入窗由 oracle 定义；
   `repairable=false` 的 189 帧说明恢复后的可观测性并不总达标。

## 8. 复现

```bash
python3 -B docs/review_20261109_bbc3dcb/run_fixed_input_repair_c0c3.py build-filtered-bag   # 约 10 min
bash /tmp/fl_run_isolated.sh /tmp/fastlivo/hall01_inj43_filtered.bag \
     /tmp/fastlivo/res_h1_inj43_filtered.bag 0.5 60
bash /tmp/fl_run_isolated.sh /tmp/fastlivo/hall01_inj43.bag \
     /tmp/fastlivo/res_h1_inj43_rerun_unfiltered.bag 0.5 60
python3 -B docs/review_20261109_bbc3dcb/run_fixed_input_repair_c0c3.py measure               # 约 1 min
```

未改 node/core/manager，未改 `fim_and_holdout.py` 默认值，未改已发表 manifest，未 push。
