# T2 join 升级：v8 真实 scan_first 的实测结果（2026-11-12）

> 输入 run `fl_native_20261112T124217Z_521833`（S2 的 v8 trace：`scan_first_ns` 真实、新增
> `n_scans`、无截断；库 `1239f35f…`）。**只升级 join 与人口统计，不改变分类结论**：
> `NORMAL/SUSPECT/误报/漏检/延迟/错误 NORMAL` 仍因 `ALI-B2` 缺独立正常参照/标签而
> **`NOT_EVALUABLE`**。未跑宿主、未改生产代码。

## 0. 一句话

v8 的 `scan_first_ns` 确实不再是 -1，但**每个组都是单扫描点跨度**（`first==last`、`n_scans=1`），
所以"跨度包含"必须带 **512 ns 的双精度量化保护**；加上保护后 **444/444** availability 行都落到
至少一个组，**227 行落在 2 个组**（多对一，来自同一 scan stamp 的两条 trace 行，不是合并扫描）。
旧机械规则（上一个不同 `last`）只与真实包含一致 **222/444**，差 221 行，**不能再用于该 run**。

## 1. 运行与人口

| 项 | 值 |
|---|---|
| run id | `fl_native_20261112T124217Z_521833` |
| run mode | `ONLINE_DETECTION`；detection on；final `HEALTHY` |
| 输入 | bag `c3e905da…`（60.0 s）；injection `INJECTION_DECLARED_Z_BIAS`；candidate source `icp_reregistration` |
| library / driver | `1239f35f…` / `62c165d1…` |
| paired / availability | **444 / 444**；88 AVAILABLE + 356 UNAVAILABLE；support 444/444 非空 |
| 触发/候选 | **2 段，全部 `MODE3_SOFT_BRIDGE_WAIT` 拒绝，0 accepted**（上次 run 为 5 段、1 accepted，拒绝分布不同） |

**人口限制（必须写进结论）**：本 run 只处理到 **rel 49.11 s**（bag 播满 60.0 s；上次追到 59.8 s），
trace **736 行**、paired **444**。**不是 60 s 完整覆盖**，不能当"完整人口"。

## 2. trace 形状

| 项 | 值 |
|---|---|
| 行 / 组 | **736 / 736**（每行一个 grp_idx） |
| `n_scans` | **全部 1**（无合并扫描） |
| `scan_first == scan_last` | **736/736**（单扫描点跨度） |
| phase | **全部 0**（本 run 无 replay 行） |
| has_out | 669 行 1 / 67 行 0 |
| rel 最大值 | **49.1116 s** |
| 相同 scan stamp 的组 | 246 个时间戳 1 组、**245 个时间戳 2 组**（同一扫描的两条 LIO trace 行） |

## 3. join 实测（口径：真实跨度包含 + 512 ns 量化保护）

规则：`scan_first_ns − 512 ≤ scan_stamp_ns ≤ scan_last_ns + 512`；**多对一保留**，不拆组；
512 ns 是 double 秒打印的量化/ulp，不是 nearest 搜索。

| 项 | 值 |
|---|---|
| 分母 | **444** |
| 每行落入的组数 | **1 组：217 行；2 组：227 行；0 组：0 行** |
| 多对一行 | **227 / 444** |
| 匹配组的 `n_scans` | 全部 1（671 个组次） |
| 未匹配 | **0** |

## 4. 旧机械规则 vs 真实跨度包含

旧规则：`previous distinct scan_last < S ≤ current scan_last`（`scan_first=-1` 时用的规则）。

| 对照 | 行数 |
|---|---:|
| 旧组在真实组集合内 | **222 / 444** |
| 旧组不在真实组集合内 | **221 / 444** |
| 旧规则无映射 | **1 / 444** |

**原因**：v8 的每个组是 `first==last` 的单点；availability 的 header 戳与它常差 **几十到几百 ns**
（打印量化）。旧规则取"下一个 `last`"，当 S 比当前组的 `last` 晚几 ns 时会错跳到下一组；
加上 512 ns 量化保护后，正确的组就是这个 S 所在的单点组。所以旧规则在该 run **不可用**。

## 5. 升级结论与边界

- 本 run 的 `join.status` 从 `HEURISTIC_UNPROVEN` 升级为 **`TRUE_SPAN_CONTAINMENT_WITH_512NS_QUANTIZATION`**；
  旧 v7 run（`115734Z`）的 `scan_first` 仍为 -1，**保持 `HEURISTIC_UNPROVEN`**，不混用。
- 多对一由**同一 scan stamp 的多条 LIO trace 行**造成（`n_scans=1`，不是合并扫描）；保留 227 行
  多组，不强行拆成一対一。
- 本 run 只覆盖 49.1 s、444 paired；分类与错误率仍 `NOT_EVALUABLE`（`ALI-B2`）。
- **修复对象边界**：审阅 `646d4f2` 指出 ep3 的 42 条修复扫描时间都在声明注入窗之后；涉及
  "修复收益/修复对象"的结论必须写"修复的是点测量还是状态误差尚未区分"，不能称注入测量已修回。
  本 run 的候选全部拒绝，也不用于修复收益。

## 6. 复现

```bash
~/mm/micromamba run -p ~/mm/ros python -I docs/ali_h_v1_research/t2_join_upgrade.py \
  --run /tmp/fl_native_20261112T124217Z_521833
```

输出 `t2_join_upgrade.json`（汇总）与 `t2_join_upgrade_rows.jsonl`（444 行逐行映射）。
