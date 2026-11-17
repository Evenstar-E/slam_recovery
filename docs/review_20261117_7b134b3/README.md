# 7b134b3增量审阅：静止注入得到真实负结果，option③是收口而非恢复成功

面向用户与S1/S2/S3开发侧。2026-11-17 09:08（UTC+8）fetch固定 `origin/main=7b134b37a62d8d1dcbe4075caf6b2013252b60a8`，前一已审版本为 `07e47af8286a2801f967a5bdbb5e9e6764ae881a`。新增 `dec24d75` 的预注册和 `7b134b3` 的静止窗注入run。

开发记录称用户预授权一次run；这不是本会话直接收到的指令，本机只核已归档结果，不追加run。repair-f3持续任务单owner，无旧repair-3e双写。本机只读Git原件并执行标准库断言，未代跑ROS/宿主、重建或修改算法、参数、科学门。

## 1. 总结判定

**有实证推进，但仅是新的受控负结果和局部生命周期证据；accepted原生修复仍未发生。**

预注册先于结果，实际relay有 **50帧body z +0.5m** shifted记录。E1 checkpoint首次在该类链上达到 `AT_OR_BEFORE_BOUNDARY`，restore为valid=1；两事件都执行了拒绝后的rearm/resume。

但最终两个候选都未accepted，repair clouds=0、reprocess=0，仍有1个unresolved segment并以`INPUT_STALE`结束。按预注册转option③可以作为**当前实现/协议下的停止与收口决定**，不能写成恢复成功或“科学上修复不可达”。

## 2. E1/E2实际断点

| 证据 | E1 `cand_0000` | E2 `cand_0001` |
|---|---|---|
| ICP | **TOO_FEW_INLIERS**，0 inliers，1次迭代 | ITERATION_LIMIT，20次未收敛，1751 inliers |
| 候选生成 | 失败后退回incumbent，候选与基线相同 | 修正0.847934m/0.667044° |
| 改善帧 | **0/8** | **0/22** |
| incumbent→candidate residual | 2319.838642→2319.838642 | 2016.020454→**2150.976477，更差** |
| Wilson | 0 | 0 |
| 信息增益 | **PASS**：160.720621 ≥ 0.397405 | **PASS**：196.498516 ≥ 35.404504 |
| holdout NIS≤2.5 | **FAIL**：2183.551628 | **FAIL**：2137.903387 |
| 重入距离／时间包络 | 1.074037m／8.701896m，**PASS** | 0.071129m／8.899341m，**PASS** |
| checkpoint | **AT_OR_BEFORE_BOUNDARY** | **LATE_AFTER_BOUNDARY**，晚0.100296696s |
| accepted | false | false |

### E1首先是候选生成器失效

`TOO_FEW_INLIERS`后退回incumbent，使candidate与baseline逐位相同，必然没有改善。这是候选生成失败，不是“注入误差不存在”或“信息不可恢复”的证明。只有8个配对帧满足支持要求，14帧deferred，也不能把22帧都当成有效收益人口。

### E2仍是未收敛且更差的候选

E2的ICP给出0.848m修正但未收敛，0/22改善，候选平均残差更差。其重入距离很小且通过时间包络，但Wilson和holdout失败，checkpoint还晚于隔离起点，不能accepted。

### “只剩0.5m重入结构约束”不适用于本次run

两事件的重入距离都在源码定义的`0.5 + 2Δt`时间包络内，且信息增益也都通过。当前明确失败的是**Wilson与holdout NIS**，E2另有checkpoint晚边界。故不能用本次run继续声称“唯一绑定约束是重入”或据此证明结构性不可达。

## 3. option③可以接受什么，不能接受什么

**可以接受的收口口径**：

- 在当前FAST-LIO派生前端、当前候选生成和冻结协议下，多次受控run没有获得accepted；
- 按预注册“门拒绝即转option③”的规则停止新run，保留全部负结果；
- 最终可交付范围限定为受控回滚、等待段关闭、rearm和resume的生命周期，以及E1合法checkpoint的局部证据。

**不能接受的扩大表述**：

- “accepted修复已经成功”或“恢复层完整闭环已通过”；
- “本宿主+本序列在科学上不可能修复”或“所有候选方法都无效”；
- “E1证明没有可改善量”，实际是候选生成器失效；
- “两事件都只被0.5m重入拒绝”，实际还有Wilson、holdout和E2 checkpoint问题；
- 用`HEALTHY`或`quarantine_open_at_exit=false`覆盖仍存在的unresolved segment。

## 4. 主线、旁支与论文边界

**主线**：真实注入、E1合法checkpoint、两事件候选/门结果和拒绝后的生命周期是实际证据；它们是负结果与局部接口能力，不是修复净收益。

**旁支**：预注册文本、LEDGER、日志和JSON汇总是保障材料，不能按数量提升A/B。自动检测仍为`NOT_EXECUTED`，事件是scripted；0.5×不证明实时。ALI-H没有真实M/I、独立校准/标签或同人口新结果，继续`NOT_EVALUABLE`。

局部可记A2/A10受控生命周期证据，A4/A6/A9/B2/B11仍未完整闭合；A3/B3/B4没有新增自动检测或净收益。**不做全表新评分，不沿用旧16/36、11/36。**

对论文只能支持“当前实现与协议下的负结果、失效边界和受控回滚生命周期”，不能支持实际修复净收益、完整两故障恢复、自动检测性能、泛化或四宿主全部验收。

## 5. 最小收口与下一单一主线

按option③，**下一唯一主线是把“回滚＋重启生命周期”做成诚实、可核的收口交付，不再开新run**：

1. **S1**提交最终门腿与归宿表：保留E1候选生成失败、E2未收敛/更差、Wilson与holdout失败、E2晚cp和unresolved segment；把“不可达”限定为当前实现/协议下未获得accepted，而非科学不可能。
2. **S2**保留预注册、binary/bag、relay、snapshot/restore/rearm/resume原件，不再重跑；全链统一成本未测则UNAVAILABLE。
3. **S3**无真实M/I与独立标签就继续BLOCKED/NOT_EVALUABLE，不阻碍当前收口，也不伪造自动检测结果。
4. 若未来要重新追求accepted，必须由用户另行决定新的候选方法或实验范围；不得通过降低Wilson、holdout、重入或其它冻结科学门制造通过。

## 6. 独立复核命令

```text
C:/Python315/python.exe -I -B docs/review_20261117_7b134b3/review_checks.py
```

[review_checks.json](review_checks.json)固定注入分母、ICP状态、候选人口、Wilson、信息增益、holdout、重入时间包络和checkpoint状态，最终exit 0；不代替原生复验。
