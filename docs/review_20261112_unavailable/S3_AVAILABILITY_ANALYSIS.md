# UNAVAILABLE 可用性归因：源码分支 + 既有归档能核到什么（S3，2026-11-12）

> 范围：**只做源码与既有归档分析**。0 次宿主运行、不启动 ROS、不改门/阈值/检测、不改生产代码。
> 评审基准：main `eeedb7f`。该版本的 `recovery_node.py` 哈希 `5877388c…c686d5` 与目标
> `e82d900` 相同；下文行号对两者都成立。脚本 `availability_source_audit.py`，结果
> `availability_source_audit.json`（40 条源码行引用 + 1 条整文件“字段不存在”检查，**41 PASS / 0 FAIL**）。

> **与 S1 实现的时间关系**：本报告的源码基准是 `eeedb7f`（写作时 S1 的实现尚未提交）。
> 随后 S1 提交了 `c35b162`（逐帧可用性诊断 + `availability_log.py`）与 `8bbef74`（状态记录）。
> 本报告**不评价**这两个提交；§3.2 的“必须补”清单可作为对照 `c35b162` 的检查表，
> 其正确性/完备性由 S1 自检与独立复核判断。

---

## 1. 前置分支清单（源码逐个列出）

### 1.0 判决式

`recovery_node.py:1100`：

```python
available = bool(supported) and value is not None
status = "AVAILABLE" if available else "UNAVAILABLE"      # 1101
```

一帧 UNAVAILABLE 只有两种可能：`supported == False`，或 `value is None`（或两者同时）。
**`carried_forward` 本身不是 UNAVAILABLE 的原因**：沿用值使 `value is not None`，
此时是否可用只取决于 `supported`。任务清单把它列为一种 UNAVAILABLE 来源，源码上不成立；
它的真实问题是"支持通过时，检测器会拿旧 NIS 当本帧证据"，这在 `detection_status` 里**看不出来**。

### 1.1 分支表

| # | 分支 | 文件:行 | 触发条件 | 需要的分母/样本 | 既有字段能否判定 |
|---|---|---|---|---|---|
| A | 检测关闭 | `recovery_node.py:1084-1093` | `detection_enabled` 为假 | — | **PASS**：`DISABLED_FOR_DIAGNOSIS` 独立状态；**不是** UNAVAILABLE |
| B | 受控触发 | `recovery_node.py:1074-1082` | 脚本声明触发 | — | **PASS**：`SCRIPTED_TRIGGER` 独立状态 |
| C1a | reference 为空 | `transaction_manager_node.py:377-378` | `len(ref_pts) == 0` | 无（数组长度） | **PASS（分支级）**：`frame_diagnostics.map_points` 就是同一数组的 `len`（`recovery_node.py:1068,1072`），`map_points==0` 即此分支 |
| C1b | scan 缺失 | `transaction_manager_node.py:383-384` | `kf_id` 不在 `scan_buffer_body` | 无 | **NOT_APPLICABLE（on_pair 路径）**：`on_pair` 在支持判定前已写入该帧（`recovery_node.py:1056`）；判决路径另调（`transaction_manager_node.py:505`），那部分 **BLOCKED** |
| C1c | pose 缺失 | 同上 | `kf_id` 不在 `repaired_poses` | 无 | **NOT_APPLICABLE（on_pair 路径）**：调用处传入 `{kf_id: pose}`（`recovery_node.py:1095-1096`） |
| C1d | pose 非法 | `transaction_manager_node.py:386-387` | 非 4×4 或含非有限值 | 无 | **BLOCKED**：`pose_to_matrix` 仅在 odometry 含 NaN/Inf 时产生；归档没有逐帧 pose 有效性字段 |
| C1e | scan 空 | `transaction_manager_node.py:389-390` | `len(pts_b) == 0` | 无 | **NOT_APPLICABLE**：`_on_scan` 已丢弃空云、不派发（`recovery_node.py:2092-2102`） |
| C1f | **支持比例 < 60%** | `transaction_manager_node.py:392-395` | `mean(inside) < 0.60` | 抽样：`pts_w[::max(1,len//200)][:200]`（392 行），分母 = 实际抽到的点数（≤200，点数<200 时为全量）；半径 1.0 m（368 行）；mask 由 `_RadiusIndex.within_radius_mask` 给出（394 行） | **PASS（分支级）**：`map_points>0` 且 `nis_source=computed` 时，C1a–C1e 全部被排除，只剩此分支；**比例数值本身 BLOCKED**（未记录） |
| C2a | NIS reference 为 None | `recovery_node.py:484-494` | `len(trusted)<30`，或 3 m 内 `<30` 且无 `prev_scan` | trusted 总数、位姿 3 m 内点数、prev_scan 点数 | **部分**：`nis_source=unavailable`/`nis_reference=none` 只标识结果，不区分是哪一个子条件 → **BLOCKED** |
| C2b | current < 10 点 | `recovery_node.py:504` | `len(world) < 10` | 当前帧点数 | **BLOCKED**：无逐帧点数 |
| C2c | 底层 NIS 非有限 | `recovery_node.py:507-510` | 返回值 inf/NaN | — | **汇总级 PASS / 逐帧 BLOCKED**：`nis.nonfinite_estimator_output` 有总数，无逐帧标记 |
| C2d | 无沿用值可用 | `recovery_node.py:517-527` | `_last_value is None` | — | **PASS（结果级）**：`nis_source=unavailable`；成因仍 BLOCKED |

**底层 NIS 的实际门槛**（`fim_and_holdout.py`）：train<30 或 holdout<10 直接返回 `inf`（120-121）；
train 抽样 600、query 抽样 300（127-128）；k=8（132）；残差 2 m 截断（143）；
**覆盖 <70% 不返回 None，而是用全部残差**（147-148），覆盖 ≥70% 才用截断残差（149）。
所以"覆盖低"不等于"NIS 缺失"，这一点与任务 §1 的纠正一致。

**诊断记录上限**：`diag_cap = 2000`（`recovery_node.py:1220-1221`），超出**静默不记录**。
本次核到的检测 on 运行最长 584 帧，未触及上限；但这是长运行的结构性盲区。

---

## 2. 结构性 vs 数据性：既有归档能核到什么

### 2.1 人口与绑定

| 项 | 值 |
|---|---|
| 检测 on 的运行 | **21 个**（`/tmp/fl_native_*/run_summary.json`，按 `frame_diagnostics` 中出现 AVAILABLE/UNAVAILABLE 判定） |
| 不同 `recovery_node.py` 源哈希 | **15 个**（跨 2026-11-10 03:18–11:12 多个修订） |
| 其中 UNAVAILABLE 帧总数 | **4128** |
| 仓库内归档的 run（`review_20261110_native_checkpoint/chain_run_…3390402`） | `detection_enabled=false`，542 帧 `DISABLED_FOR_DIAGNOSIS` → **NOT_APPLICABLE** |
| 主要原件（E2 窗口） | `/tmp/fl_native_20261110T110616Z_3349738/run_summary.json`，sha256 `8c6d3d56…052b58`；**未进仓库归档** |

**E2 运行的源码身份可查**：其 `recovery_node_source.sha256` 为 `9269c888…`，对应提交
**`466f1a3`**（逐提交比对得到）。该版本的可用性判据与 HEAD **结构相同**：同样的提前返回顺序、
同样的 200 点抽样、1 m/60%；差别只在距离查询实现——`466f1a3` 对 200 个抽样点**逐块算出了精确最近距离**
（`nearest[s:s+chunk] = d2.min(axis=1)`），然后只保留布尔结果；HEAD 改用 `_RadiusIndex`（`57-105`），
只回答"有没有点在半径内"。**同一份比例/距离在运行时就已算出，只是没有落盘。**

### 2.2 可证的结论（跨 21 个运行）

| 结论 | 证据 | 状态 |
|---|---|---|
| UNAVAILABLE **不是** NIS 缺失造成的 | 4128 帧中 **4107** 帧 `nis_source=computed` 且有有限数值；例外 21 帧 = **每个 run 恰好 1 帧**，都是首帧（同时 `map_points=0`、`nis_source=unavailable`） | **PASS** |
| `carried_forward` 不是本次 UNAVAILABLE 的来源 | 4128 帧中 `carried_forward` = **0** | **PASS** |
| 支持失败可分为"reference 空"与"比例不足"两类 | 分区：`empty_reference` **1656**（其中 1635 帧 NIS 仍算出）；`fraction` **2472**；两者之外的"map 非空但 NIS 未算" = **0** | **PASS（分区）** |
| 位姿 3 m 邻域稀疏 | **2286** 帧 `map_points≥30` 且 `nis_reference=prev_scan`。按 `_reference`（484-494），这只在 trusted 总数 ≥30、但 3 m 内 <30 时发生 → **源级精确** | **PASS** |
| 支持比例的具体数值 | 归档只有布尔结果，没有 `mean(inside)`、分母、逐点 mask | **BLOCKED** |
| 当时参考快照的身份/版本 | `map_points` 只是点数；cache key、刷新戳、快照 hash 都未记录 | **BLOCKED** |
| 空 reference 的**原因**（地图回退 / cache 未刷新 / 确实为空） | 只能证明"当时缓存数组为空"；`trusted_version` 未记录 | **BLOCKED** |
| 是否"因为漂移" | 无独立位姿/地图一致性证据；**禁止**由 unsupported 推漂移 | **BLOCKED** |
| 全 population 完整性 | 21 个运行中 **1 个** `frame_diagnostics` 只有 377 行、`frames.paired=584`（`fl_native_20261110T031851Z_2949682`）；其余 20 个完整 | **FAIL（该 run）** |

### 2.3 E2 窗口（`+42…52 s`）逐帧核

以**首个 `frame_diagnostics` 行**为 0 点，`[42, 52] s` 内：

| 项 | 值 |
|---|---|
| 帧数 | **83**（kf 376–458）；报告里的"87 帧"应是窗口原点/端点口径不同（同一段按秒的帧数分布一致），无论 83 还是 87 归因相同 |
| `detection_status` | **83/83 UNAVAILABLE** |
| `nis_source` | **83/83 computed**（全部有有限 NIS） |
| `nis_reference` | **83/83 prev_scan** → 3 m 内 trusted 点 **<30** |
| `map_points` | 36 354 – 90 809（**非空**）→ 支持分支只能是**比例 <60%**（C1f） |
| `trusted_keyframes` | 67 – 148 |
| NIS | min **0.688** / median **1.095** / max **4.453** |
| 检测器状态 | 83/83 HEALTHY（这些帧根本没进检测器） |

**所以这一段的原因可以写到分支级**：不是没有 NIS、不是 NIS 非有限、不是沿用值、不是空 reference、
不是 scan/pose 缺失，而是**位姿附近 3 m 内 trusted 点 <30、且 1 m/60% 支持不达标**。
**不能**写"因此是漂移"——比例数值和参考快照都没有落盘。

另需注意：这 83 帧的 NIS 参考是 `prev_scan`，是**上一帧扫描对当前帧**的自比较，不是独立参考；
NIS 落在 0.69–4.45 只说明相邻扫描彼此一致，**不构成地图或位姿正确的证据**，更不能用来否定 UNAVAILABLE。

### 2.4 空 reference 的两段（E2 运行）

| kf | 帧数 | 时间段（ns） | 状态 |
|---|---:|---|---|
| 0–20 | 21 | 1627785261.403–1627785263.408 | 冷启动，`map_points=0` |
| 26–64 | 39 | 1627785264.007–1627785267.805 | **再次为空**；39 帧 ≈ 3.8 s，远长于 0.5 s 刷新周期，不能由单次 cache 滞后解释；原因（回退/冻结/版本未变）**BLOCKED** |

这一段与生命周期事件时间相邻，但归档没有把 `trusted_version`/快照并进逐帧记录，**不建立因果**。

---

## 3. 字段审查（对照任务 §2）与候选选项

### 3.1 已有的逐帧字段（`_record_diag`，`recovery_node.py:1218-1233`）

`kf_id, ts_ns, nis, nis_source, nis_reference, detection_status, detector_state, cusum,
suspect_dwell, map_points, trusted_keyframes`。

**没有**：`supported` 布尔、支持比例/分母/抽样索引/逐点 mask、提前退出原因、scan_stamp/pose-scan dt/
frame_id/T_wb、原始/有限/采样点数、原始 row 映射、reference cache key/刷新戳/age/快照 hash、
trusted_version、manager state/active 段、3 m 内点数、prev_scan 戳/点数、current 点数、
raw NIS 状态与原因、沿用值来源/年龄、底层 train/query 实际采样数/邻居/面/残差/覆盖分支。

### 3.2 补齐方式分三档

| 档 | 量 | 依据 |
|---|---|---|
| **零额外计算**（值已算出，只需返回/记录） | `supported`、`supported_fraction=mean(inside)`、`sampled_count=len(q)`、抽样 step、提前退出 reason；NIS 的 `train/holdout` 点数、stride、实际采样数、k、sigma、`inlier_coverage`、`branch`、mean/rms/分位数；`_reference` 的 trusted 总数、3 m 内点数、prev_scan 点数与来源；`carried_forward` 的来源帧/戳/年龄；support cache 的 key/刷新戳；manager state/段 id | `transaction_manager_node.py:392-395` 已算比例；`fim_and_holdout.py:142-149` 已算全部残差统计；`recovery_node.py:484-494` 已算两组点数 |
| **需改签名**（计算为零，但当前不返回） | 底层 NIS 的逐点 `nn_ids/centroid/normal/eigenvalues/residual/chi2/within_2m`。**HEAD 的 `compute_disjoint_holdout_point_to_plane_nis` 没有 `details` 形参**（`fim_and_holdout.py:107-112`），所有量在函数内算完后被丢弃 | 任务 §2 要求的点级详情；加一个可选 dict 即可，估计器不变 |
| **额外计算/存储** | 精确最近距离与匹配参考 ID；参考快照（按 ID/hash 复用）；原始 row 映射 | `_RadiusIndex.within_radius_mask` 只回布尔且逐点短路（`transaction_manager_node.py:98-104`），**不能把首个命中距离叫最近距离**；HEAD 需对保存样本/同一参考离线复算。`cloud_to_xyz` 在 2042 行丢弃非有限行且不返回 mask，原始 row 映射已丢失 |

### 3.3 选项（只列，不实现、不选、不调参）

证据指向**前置可用条件的结构盲区**：支持判据只看"缓存 trusted 地图 1 m 内 60% 覆盖"，
无法区分（i）冷启动无图、（ii）恢复后地图回退/为空、（iii）位姿与地图不一致、（iv）确实在覆盖外。
E2 运行里 39 帧的二次空 reference 与 281 帧的比例失败就是这四种情况的混合面。

| 选项 | 做什么 | 代价 | 判别性 |
|---|---|---|---|
| **A. 诊断分解（不改判决）** | 记录 `supported`、比例、分母、抽样规则、提前退出 reason、逐点 mask；NIS 记录 `details` | 估计器零额外计算；I/O 与存储小幅增加 | 区分"接近 60%"与"0 覆盖"，并把 C1a–C1f 落到具体分支；**这是回答用户问题的必要条件**，本身不改检测 |
| **B. 双参考支持** | 同一帧分别对"当前缓存地图"和"冻结的 restore 前快照"做支持测试 | 每帧多一次半径查询（或复用快照索引）；需保存/引用快照 | 当前失败而冻结快照通过 → 问题在地图/位姿一致性；两者都失败 → 扫描/位姿本身；可直接检验 §2.4 的二次空 reference |
| **C. 位姿-地图分解** | 同一帧在宿主位姿与短时预测位姿下各做一次支持测试 | 每帧多一次变换+查询；需声明预测器（如最近一次 AVAILABLE 的常速度） | 预测位姿通过而宿主位姿失败 → 指向位姿；两者都失败 → 指向地图覆盖。**不得**据此自动改位姿 |

（可选 D，仅记录：**参考年龄条件化**——记录 cache age/version，并规定"刷新未完成时不判 UNAVAILABLE"。
代价低，但这是行为策略决定，先列为选项。）

**三个选项都必须在用户选择后才能实现**；本报告不写实现、不设参数、不比较效果。

> 写作后 S1 的 `c35b162` 看起来已覆盖 §3.2 的多数“零额外计算”项（`support` 块、`nis`/`holdout`
> 分支与 `detail`、沿用值来源、无上限 JSONL）。**本报告未复核其字段是否齐全、抽样/裁剪是否符合任务 §2**，
> 这里只记录版本关系，不作 PASS 结论。

---

## 4. 逐项状态

| 项 | 状态 | 证据/原件 |
|---|---|---|
| 源码引用（40 条行 + 1 条整文件检查） | **PASS 41/0** | `availability_source_audit.json.source_checks` |
| 判决式 `supported and value is not None` | **PASS** | `recovery_node.py:1100-1101` |
| 支持半径/比例/抽样 | **PASS** | `transaction_manager_node.py:368-369,392-395` |
| 空 reference 与支持比例的归档区分 | **PASS（分支级）** | §2.2，分区 1656 / 2472 / 0 |
| 支持比例数值 | **BLOCKED** | 未记录 |
| 参考快照身份/版本 | **BLOCKED** | 未记录 |
| NIS 缺失/非有限/沿用值作为 UNAVAILABLE 原因 | **FAIL（作为原因）**：4107/4128 已算出 NIS，沿用 0 | §2.2 |
| E2 窗口归因 | **PASS（分支级）**：83/83 computed、prev_scan、map 非空 → 比例分支 | §2.3 |
| E2 窗口"87 帧"计数 | **PASS（口径差异，已说明）**：同一段，[42,52] 从首帧起为 83 | §2.3 |
| 二次空 reference 的原因 | **BLOCKED** | §2.4 |
| 全 population 完整性 | **FAIL（1/21 run 截断 377/584）** | §2.2 |
| 是否漂移/因果 | **BLOCKED（禁止推断）** | 规则 |
| 宿主运行/门/阈值改动 | **NOT_APPLICABLE（0 次）** | 本报告范围 |

## 5. 能推出 / 不能推出

**能推出**：
1. 本次全部检测 on 运行里，UNAVAILABLE 的判决来源是**支持谓词**，不是 NIS 缺失或沿用值
   （4107/4128 computed，`carried_forward=0`；唯一例外是每个 run 的首帧冷启动）。
2. 支持失败可分为**空 reference**（1656）与**1 m/60% 比例不足**（2472）；E2 窗口 83 帧全部属于后者，
   且这 83 帧的位姿 3 m 内 trusted 点 <30（源级精确）。
3. `carried_forward` 单独不会产生 UNAVAILABLE；它在支持通过时会被检测器当作本帧证据，
   这是一个**独立于 UNAVAILABLE 的问题**，当前状态字段看不出来。
4. 现有归档能定位到**分支**，不能定位到**数值与原因**；需要 S1 记录 §3.2 的零额外计算量。

**不能推出**：UNAVAILABLE 等于漂移；某段 UNAVAILABLE 必然由 restore/回退造成；比例失败是"当前位姿
错了"还是"地图没覆盖到"；新诊断会提升端到端恢复或 A/B 分。这些都需要 S1/S2 的真实原件。

## 6. 复现

```bash
python -I docs/review_20261112_unavailable/availability_source_audit.py --scan-tmp
```

只读 `run_summary.json` 与源码；不跑 ROS/宿主；不改生产代码。`--scan-tmp` 依赖 `/tmp/fl_native_*`
仍存在（本机当前存在）；缺失时脚本把该 run 标 `BLOCKED: file not present`，不影响源码检查与结论。
