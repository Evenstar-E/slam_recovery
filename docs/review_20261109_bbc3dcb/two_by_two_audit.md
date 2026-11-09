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

## 5b. R2 / R3 处置（同意你的提议）

- **R2**：旧 `room02_hybrid_bag_report.json` 属已废弃的 X/Y 设计，2×2 已取代它。
  同意按 **`SUPERSEDED, 不再用于结论`** 关闭，而不是等新报告。规则保留，供将来的 hybrid
  报告使用；测试改为断言「该归档文件缺少绑定字段」这一既成事实，不再标 expectedFailure。
- **R3**：`build_oracle_bag.py` 已改为读声明窗口，但归档 oracle report 未重建，
  `window_mismatch` 无从判断 → **保持 expectedFailure**。
