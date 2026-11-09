# room_02 2×2 host 结果审计

对象：`room02_2x2_results.json`、8 份 `room02_2x2_receipt_fl_run_*.json`、独立复算
`evaluate_2x2_runs.json`（main acfc820）。只读。
脚本 `two_by_two_audit.py`，结果 `two_by_two_audit.json`。

## 结论

| # | 项 | 结论 |
|---|---|---|
| 1 | 判据与预声明一致 | **符合** |
| 2 | 8 份回执绑定输入与 runner，四包 sha 与 manifest 一致 | **符合** |
| 3 | 独立复算与宿主无结论冲突 | **符合**（数值差异大，但在阈值同侧） |
| 4 | **判定用的 ATE 是诊断量，不是协议量** | **发现（不推翻结论，但改变解读）** |

`NOT_A_CLEAN_INTERACTION` 在两种 ATE 口径下都成立——交互规则的前提（O+F 与 O−B 均不失败）
从未满足。但「**运行方差主导**」这个解读只在诊断口径下成立；换成协议口径，四格**全部两次失败**。

## 1. 判据未被事后改动

`room02_2x2_results.json:protocol` 与 `single_factor_preregistration.json` 对齐：

| 项 | 预声明 | 结果 protocol |
|---|---|---|
| 阈值 | `failure_threshold_ate_m: 1.0` | `fail_rule: "full-alignment ATE > 1.0 m fails"` |
| 重复次数 | `repetitions_per_cell: 2` | `"both repeats must land on the same side"` |
| 交互规则 | O+F−B 两次失败且 O+F/O−B 均不失败 | 同 |
| 声明时点 | `declared_before_results: true` | — |

措辞不同但规则相同，未见放宽或收紧。**但 `fail_rule` 指名的是 full-alignment ATE**——这是第 4 项的问题。

## 2. 回执与包的绑定

- 8 份回执，每格 2 份，全部 `status: OK`；
- 每份 `pre_run.sha256.input_bag` 与 `single_factor_bags.json` 对应格的 sha256 一致；
- 四个 bag 在磁盘上的现算 sha 与 manifest **全部一致**（O `f8b26ddf…` 等）；
- 每份记录宿主 binary 路径 `fastlivo_mapping`、`host_revision: 0d2c034…`、两份配置的 hash。

## 3. 独立复算 vs 宿主

8 次运行全部落在阈值**同一侧**，无结论冲突。绝对差最大约 `71 m`（O+F#1），来源是对断掉
的轨迹做整体 SE(3) 拟合时，对齐方式不同会放大差异——这不是小数级的口径差，但两侧都只是
诊断量，且从未用于判定协议口径。

## 4. 发现：判定变量用的是诊断 ATE

`room02_2x2_results.json` 每条记录同时给两个 ATE：

```
ate_full_alignment_diagnostic_m   整条轨迹拟合一次 SE(3)      ← fail 用它
ate_frozen_prefix_protocol_m      冻结 healthy-prefix 协议量
```

同一条记录里还写着：

> `ate_full_alignment_diagnostic_m is a FULL_ALIGNMENT_DIAGNOSTIC and must not be merged into
> the frozen-prefix protocol table; ate_frozen_prefix_protocol_m is the protocol number`

而 `fail_rule` 明确写的是 "full-alignment ATE > 1.0 m fails"。

两种口径下的失败模式：

| 格 | full-alignment | frozen-prefix |
|---|---|---|
| O | 0.072 / 14.439 → **不过 / 过** | 3.81 / 24.42 → **过 / 过** |
| O+F | 593.0 / 14.9 → 过 / 过 | 过 / 过 |
| O−B | 48.8 / 19.7 → 过 / 过 | 过 / 过 |
| O+F−B | 554.6 / 0.301 → **过 / 不过** | 过 / 过 |

- **full-alignment**：O 与 O+F−B 都不稳定 → 「运行方差主导」；
- **frozen-prefix**：四格**全部两次失败**，没有一格是好的 → 不是方差，是**协议口径下全盘失败**。

交互规则在两种口径下都不满足（O+F 与 O−B 都稳定失败），所以 `NOT_A_CLEAN_INTERACTION`
本身不受影响。受影响的是**为什么**：说「运行方差主导」等于说「同一个格时好时坏」，
而在协议口径下没有任何一次是好。

**建议**：2×2 的失败判据改用 `ate_frozen_prefix_protocol_m`（即协议量的定义），
或把两种口径的判定都列出来并明确最终采用哪一个。诊断量可以作为补充列，但不应是判定变量。

## 5. P2 修正后的复核（main 067b8ba）

| 验收项 | 结果 | 证据 |
|---|---|---|
| 冻结 clean→GT 每个 run 共用 | **PASS** | `clean_to_gt` 只出现一次（177 匹配、RMSE 0.0907 m），没有任何 cell 自带变换 |
| 复合顺序 | **PASS** | 代码为 `(me @ R_p.T + t_p) @ R_cg.T + t_cg`，先 run→clean 再 clean→GT |
| hash 链 | **PASS** | 4 个 map 包记录值 = manifest = 磁盘现算；8 个 run 包 sha 逐个与磁盘一致 |
| 诊断量逐位不变 | **PASS** | 8 个 cell 的 `ate_full_alignment_diagnostic_m`、coverage、unsupported（含窗内/健康）、`frames_scored`、`poses_matched_gt` **全部逐位相同**，只有 `ate_frozen_prefix_protocol_m` 改变 |

修正后的协议读数：O 0.0926/26.373、O+F 743.311/26.148、O−B 76.070/33.682、O+F−B 687.520/0.314。
**只有 O#1 与 O+F−B#2 通过**，与诊断口径的通过集合相同。

因此先前「协议口径下八次全失败」是**漏掉 clean→GT 的假象**，我的第 4 项发现随之失效：
两种口径现在给出一致的通过/失败集合与一致的 `NOT_A_CLEAN_INTERACTION`。
「运行方差主导」不再依赖口径选择——两口径都显示同一格两次运行相差三个数量级。

本文件第 4 节保留为**历史记录**（针对 9bd2ff7 的旧数值），但不作为当前结论。

## 6. 方差对照审计（main 5f2284f）

| 项 | 结果 |
|---|---|
| 8 份 bist receipt 绑定 | **PASS**：O 4 份、O+F−B 4 份；输入包 sha = manifest = 磁盘；config/script/revision 八份同一；8 个 output sha 全部与磁盘一致 |
| `mode_rule` 与逐次分类 | **PASS**：按 `unsupported < 0.1 / > 0.5 / else` 重算得 O `BAD,GOOD,BAD,BAD`、O+F−B `UNCLEAR,UNCLEAR,BAD,BAD`，与记录逐项相同 |
| 2/6、1/6 的量级表述 | **PASS**：DAILY 与 MILESTONE 都写明「只作量级，不作概率估计」，未出现 probability/rate/chance 措辞 |
| 首分歧诊断的标签 | **PASS**：MILESTONE 标 `POST_HOC_DESCRIPTIVE`，规则明写「for prospective use on the next repeat pair」，未写成已预注册 |

### 一处无法核验：双稳协议的「预注册」

`room02_bistability_results.json:protocol.source` 写作 `preregistered bistability estimate`，
DAILY §12 标题写「预注册，`55f7b87`」，正文写「该判据写在运行之前」。

但 `55f7b87` 正是**加入这 8 份 receipt 的那次提交**；`55f7b87^` 的全部文件里没有任何一处出现
"bistability"。也就是说，仓库内没有任何证据表明该判据早于运行被写下——它可能是会话中先声明的，
但那不可被审计。

判 **UNVERIFIABLE**（不是 FAIL）。建议：像 2×2 那样单独提交一份
`bistability_preregistration.json`（含 `declared_before_results` 与声明时戳），
或把 DAILY 的引用从 `55f7b87` 改成一个确实早于 receipt 的提交。

## 7. 共同集重算复核（main 71b31d3）

| 项 | 结果 |
|---|---|
| 12 个 run 的 `output_sha256` | **PASS**：每条都能对上某份 receipt 的 `output.sha256`，且该包磁盘现算值相同 |
| `mode` vs `mode_common` | **PASS**：12/12 相同，无一条因换共同集而翻类 |
| 逐 run 序列 vs 共同集序列 | **PASS**：O `BAD,GOOD,BAD,BAD` 与 O+F−B `UNCLEAR,UNCLEAR,BAD,BAD` 两口径逐项相同 |
| `crosses_good_and_bad` 推导 | **PASS**：O 有 GOOD 与 BAD → True；O+F−B 只有 UNCLEAR 与 BAD → False |

最后一条正是要点：O+F−B 的 `crosses_modes=True` 但 `crosses_good_and_bad=False`，
不是两个吸引子之间的跨越，而是「一个坏态 + 一个中间态」。判定仍按运行前写的**类别跨模式**
规则触发，这个区分在数据里成立。

### 一处文档内自相矛盾

`docs/DAILY_20261109.md:118`（§11）仍写着：

> **好模式在 O 与 actual 各出现一次，与臂无关**，即宿主在这条序列上**双稳**。

而同文件 `:160`（§12）写着「**"双稳"一词不再使用**」。§11 的这句没有被改，
只读 §11 的人会拿到已被 §12 撤回的结论。建议在 §11 该句后加「（§12 已撤回：O+F−B 只有
中间态与坏态，不构成两个吸引子）」，或直接改写。

## 8. 身份修复与阈值复核（main 656b229）

| 项 | 结果 |
|---|---|
| 12 个 run 的身份 | **PASS**：`new:` 8 + `earlier:` 4，唯一键无碰撞，`per_run_available` 12 条齐全且带批次前缀，`n_runs=12` |
| 共同集 323 帧 | **PASS** |
| 逐 run 指标不变 | **PASS**：12 个 run 的 `frames / coverage / unsupported / ate_full_alignment / mode` 与 71b31d3 版**逐项相同**，无一处变动 |
| 新阈值时间点 | **PASS**：>5 cm 为 O +0.37、O−B +0.31、O+F−B +0.24、O+F **−5.95**；>10 cm 为 +0.50/+0.77/+0.84/+0.84；>1 m 为 +15.46/+16.12/+17.19/+17.86 |

gauge 残差 1.32–1.54 cm，所以 1 cm 阈值确实会在首样本必然触发，改到 5 cm 起步是对的。

**O+F 的 −5.95 s 是唯一一条支持"初始化已种下分歧"的数据，它被保留在记录里、没有被悄悄丢掉**，
但也不被用来下结论——这与撤回该判断一致。建议在文档里把这层意思写明：
「该点保留但当前不解读，它是唯一可能支持初始化假说的证据，也是将来若要重提该假说时必须先解释的点」。

### 10 号检查的加固（审阅 dfa20d24）

原版 `check_run_identity` 只比较两个内部列表的长度，因此 `check_run_identity({})` 会返回
`PASS / runs=[] / common_frames=None`——**一个不可能失败的检查**。

现在：空输入、无 run 记录、`protocol` 未声明 cells/repeats → **UNVERIFIABLE**；
期望键集由 `protocol.cells × repeats_per_cell` 加两批 earlier 推导，缺一或多一 → **FAIL**；
`common_set.per_run_available` 缺失、条数不符、缺批次前缀 → **FAIL**；`n_runs` 缺失或不等 → **FAIL**。

7 项 fixture：完整集 PASS；`{}` 判 UNVERIFIABLE；缺 run、多 run、缺 `n_runs`、`n_runs` 不符、
批次前缀丢失各自判 FAIL。

## 9. T1/T2 对齐复算（main 291a0dd）

用**不共享任何代码**的实现独立复算（rosbag 读位姿、自己的最近邻关联、自己的 Umeyama、
自己读 TUM GT）：

| 量 | T1 | T2 | 与记录 |
|---|---|---|---|
| `first_output`（两 run） | 42.844585 / 41.511961 | 41.378685 / 42.244886 | **逐位相同** |
| `first_scored` | 42.844585 | 42.244886 | **逐位相同** |
| `common_ids` | 769 | 778 | **相同** |
| `common_ids_sha256` | `f2e3aac4…` | `279585d5…` | **逐位相同** |
| gauge 残差 | 0.015743 | 0.014334 | **相同** |
| `aligned_at_onset_m` | 0.008715 | 0.003900 | **相同** |
| `aligned_first_scored_m` | 0.015113 | 0.007726 | **相同** |
| ATE（两 run） | 0.347764/300.275260 | 0.084578/18.510512 | 记录 0.347758/300.275246、0.084548/18.510589（≈1e-5 相对差） |

只有 ATE 在 1e-5 量级有差，来源是 GT 关联的并列取舍（`associate_trajectories` 与我的实现
在等距时选点不同）。所有对齐量与两个 common-ID 哈希**完全可复现**。

两套口径的定义写在 `field_definitions` 里，清楚：`aligned_at_onset_m` 是结果 JSON 报的那个量，
`aligned_first_scored_m` 是从首个共同帧算的。两个数（8.7 mm vs 15.1 mm、3.9 mm vs 7.7 mm）
都远低于 5 cm，且 T1/T2 各自都是一好一坏（0.348/300.3、0.085/18.5），所以「该控制未稳定结果」
成立，与「排除该机制贡献」是两回事——文档现在也是这么分开写的。

复算脚本：`docs/review_20261109_6b61c9d/verify_determinism_alignment.py`，
结果 `determinism_alignment_verified.json`。

## 10. T3a 审计（main 2381d82）

| 项 | 结果 |
|---|---|
| 6 份 receipt 的输入/config/身份 | **PASS**：同一 input `f8b26ddf…`、同一 config、同一 exec `76359f53…`、6 份全 `OK` |
| **receipt 是否记录加载的库 hash** | **FAIL**：6/6 都没有 `library_sha256` 字段（`grep library` 在 receipt 里命中 0） |
| `room02_T3a_results.json` 的 verdict 作用域 | **FAIL**：不带 run 集合、不带 build 标识，`S3_ACCEPTED_AS_SEED` 可脱离上下文被单独引用 |
| `room02_T3a_enriched_results.json` 的作用域 | **PASS**：含 `runs`、`four_runs_same_build`、`build_comparison` |
| mode 规则一致性 | **PASS**：GOOD <0.10 / BAD >0.50，与 bistability 同一规则；r1 0.0067、r2 0.044 均判 GOOD |

### 两条都是同一个教训的两半

provenance 的教训是「exec sha 相同，行为在 `liblaser_mapping.so`」。但**修复只落在分析文件里**：
`build_comparison` 的键名写作 `lib_6337ec0f`，而 **receipt 本身仍只有一个跨 build 相同的 exec sha**。
也就是说：拿到任何一份 T3a receipt 的人，**无法从 receipt 判断它跑的是 build A 还是 build B**——
这正是该教训要防的事。

同理，`S3_ACCEPTED_AS_SEED` 写在 `room02_T3a_results.json` 里，而该文件不写它覆盖了哪两次运行、
哪个 build。四个 run 的 enriched 文件推翻它时，两份记录之间没有任何机器可读的关联。

**处置（`0ca16fd` 后）**：verdict_scope 已 **PASS**（`runs_analysed`、`build`、`scope.superseded_for_conclusion_by` 齐全）。
receipt_library 改为三分：新 receipt 缺库 hash → **FAIL**；**已声明 `provenance_gap.receipt_library_sha256 = ABSENT` 的历史批次 → `RETROSPECTIVE_PARTIAL`**；
缺字段又无声明 → FAIL。这样这一条不会永远红着稀释新回归，同时对**新** receipt 仍然能抓。

历史批次逐 run 回填是不可能的：六份 receipt 只有跨 build 相同的 exec sha，补一个"当时的库 hash"就是伪造 provenance。
`RETROSPECTIVE_PARTIAL` 的含义是「缺口已知且被写下」，不是「可以忽略」。

建议：
1. receipt 的 `host` 增加 `library_path` 与 `library_sha256`（运行时从 `/proc/<pid>/maps` 或
   `ldd` 解析出实际加载的 `.so`，而不是声明值）；
2. 任何 `verdict` 旁附 `runs_analysed` 与 `build`，缺这两项时下游规则判 FAIL（已加入第 11 组检查）。

## 11. hall_01 适用性（main 324b8db）

| 项 | 结果 |
|---|---|
| 共同集与逐 run 计数 | **PASS**：`common_frames` 562，四次 `n_common` 全 562，`map_points` 全 140,500，`nn_supported_fraction` 全 1.0 |
| 原始 unsupported | 0.2282 / 0.2790 / 0.2427 / 0.2715，跨度 **0.0508**，与记录一致 |
| 身份 | **PASS**：四份 receipt 同一 input `905c6a15…`、同一 exec `76359f53…`、同一 config，全 `OK` |
| **receipt 库 hash** | **FAIL（4/4）**：同 T3a 一样缺 `library_sha256`，而 `hall01_stability_results.json` **没有 `provenance_gap` 声明** |
| 不得把「四次 UNCLEAR」当稳定证据 | **PASS**：Milestone 明写「the stability reading rests on the raw values, not on a shared label」，并说明 0.10/0.50 的阈值描述的是 room_02 的分布、不可迁移 |

### 跨数据集比较的是"离散度"而不是"水平"

hall_01 的 0.0508 与 room_02 的 0.68 比的是**同一统计量在各自数据集内的跨度**，不是把两个
绝对水平放在一起比。这个比较是成立的，因为代理面不同、基线不同，水平不可比而离散度可比。
文档现在的写法正是这个，无需改。

### 库 hash 的两批需要同一份声明

T3a 走的是结果文件内的 `provenance_gap`；hall_01 没有这个字段，所以现在判 **FAIL**。
同一类历史缺口分两种判法会让规则失去一致性。已支持一份**批次注册表**：审计读
`docs/review_20261109_bbc3dcb/library_hash_gap.json`，形如

```json
{"batches": {
  "room02_T3a": {"reason": "receipts predate the requirement; behaviour lives in liblaser_mapping.so",
                 "observed": "6/6 receipts carry only the cross-build executable sha"},
  "hall01_stab": {"reason": "same batch requirement, same absence",
                  "observed": "4/4 receipts carry only the executable sha"}}}
```

注册表已由 `3c2091b` 落盘，两批均判 `RETROSPECTIVE_PARTIAL`（6/6、4/4）。

**一处收紧**：注册表列的是**具体记录名**（`records` 数组），所以规则也按记录名豁免——
同一批次里**新增**的 receipt 若缺库 hash，仍判 **FAIL**，不会因为批次名在册而继承豁免。
否则只要批次被列过一次，该批次以后所有漏记都会被同一条声明掩护过去，注册表就退化成通用豁免了。

## 12. T3a verdict 冲突（已解）

`criterion.verdict = S3_ACCEPTED_AS_SEED__SUPERSEDED_BY_BUILD_B_FOUR_RUNS`，
同时保留 `runs_analysed ["r1","r2"]`、`build`、`scope.superseded_for_conclusion_by`
与 `superseded_by.file`。三处指向同一事实，无矛盾。

## 13. hall_01 轨迹项（main c458a22）

| 项 | 结果 |
|---|---|
| 六个输入 sha | **PASS**：逐个与磁盘现算一致（`aa740037` / `03e75983` / `905c6a15` / `32f0bf44` / `c90300cb` / `1109fccf`） |
| `frame_set.ns_sha256` | **PASS**：`8a53f296…` 与上一版**相同**，400 帧 / 446 keys / 46 missing 未变 |
| 冻结 clean→GT | **PASS**：`cln_ts < onset_ns` 上拟合一次（77 匹配、0.085 m），在臂循环外计算，两臂共用 |
| 每臂 run→clean | **PASS**：用 `healthy_prefix` 拟合，再复合 `(me @ R_p.T + t_p) @ R_cg.T + t_cg` |
| 种群标注 | **PASS**：`trajectory.population = {frame_set 400, gt_matched 252, gt path}`；两臂 `gt_matched` 都是 252 |
| 诊断 / 协议分列 | **PASS**：`ate_full_alignment_diagnostic_m` 与 `ate_frozen_prefix_protocol_m` 分字段，R 1.909/10.929、C3 0.319/0.492 |

### 一处建议（不阻断）

`clean_to_gt` 只记 `matched` 与 `residual_rmse_m`，**不记拟合窗口，也不记变换本身**。
「在 onset 前 clean keyframes 上拟合」这句话只存在于代码注释与 note 字符串里，读者无法从 JSON
验证，也无法复算。建议补三个字段：`fitted_on: "pre-onset clean keyframes"`、`start_ns`、
以及 `R_cg`/`t_cg` 的数值。这与之前 `window.declared_from` 那次是同一类问题——**声明在文字里，
不在数据里**。

## 14. B4 成本 / 缺测敏感性 / 覆盖度口径（main 60c4b1c + cf81d17）

| 项 | 结果 |
|---|---|
| `clean_to_gt.start_ns` | **PASS**：`1627785275607408524` 与 `docs/milestone_m0_keys.json` 的 `injection_window.start_ns` 完全相同 |
| `clean_to_gt.fitted_on` | **PASS**：与代码 `cln_ts < start_ns*1e-9` 一致；`R_cg`/`t_cg` 已入数据 |
| 成本两口径 | **PASS**：R `DERIVED_FROM_COMMAND ... not measured`（296 s，rate 0.5/drain 150）、C3 `MEASURED`（122.9 s，rate 1.0/drain 40），峰值内存各自注明 UNAVAILABLE 及原因；**全库无任何加速比或 ratio** |
| 缺测敏感性 | **PASS**：319 = 400 − 81；R 0.7977/0.4200/1.617、C3 0.9759/0.0975/0.274，排序不变 |
| 覆盖度两套口径 | **FAIL**：0.6278/0.9850（`hall01_b4_cost_and_gap.json`）与 0.6038/0.9849（`raw_vs_repaired_results.json`）不一致，且**前者没有 `reference` 字段** |

### 两处需要修

**（a）`trajectory.population` 在 60c4b1c 中消失了。** c458a22 有结构化块
`{frame_set: 400, gt_matched: 252, gt: ...}`；60c4b1c 加入变换字段时把它删了，只剩 notes 里那句散文。
于是「ATE 是 252 帧诊断、不是 400 帧指标」这条**不再可被机器读取或校验**——
为修一项而删掉另一项的防护，是最容易漏掉的一种回归。

**（b）两套 coverage 只有一套被标注。** 0.6278/0.9850 只出现在 B4 文件里，没有任何字段说明用的是
完整干净参考；0.6038 出现在 `raw_vs_repaired_results.json` 与 DAILY。R 差 0.024，读者很容易把
0.6278 当成对 0.6038 的更正，而不是另一套口径。

**两处均已修（`7fc5231`），复核通过**：

- `trajectory.population` 恢复为 `{frame_set 400, frame_set_keys 446, gt_matched 252, gt, note}`，
  且由脚本生成而非事后补写；轨迹值逐位不变（R 10.928765 / C3 0.491844）；
- B4 文件新增 `reference = {surface: "full clean reference", points: 8,490,000, downsampled: false, note: ...}`，
  明写与 120k proxy 是**不同人口、不是更正**。

`13_hall01_trajectory` 与 `14_b4` 现已全部 PASS。

## 5b. R2 / R3 处置（同意你的提议）

- **R2**：旧 `room02_hybrid_bag_report.json` 属已废弃的 X/Y 设计，2×2 已取代它。
  同意按 **`SUPERSEDED, 不再用于结论`** 关闭，而不是等新报告。规则保留，供将来的 hybrid
  报告使用；测试改为断言「该归档文件缺少绑定字段」这一既成事实，不再标 expectedFailure。
- **R3**：`build_oracle_bag.py` 已改为读声明窗口，但归档 oracle report 未重建，
  `window_mismatch` 无从判断 → **保持 expectedFailure**。
