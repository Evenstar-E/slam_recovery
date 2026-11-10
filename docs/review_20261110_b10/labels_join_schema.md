# 独立标签与分段：join 格式（2026-11-10 冻结）

B5/B7 的归档核实结论是 `BLOCKED`：库里 0 条记录同时带"身份 + 决定 + 独立标签"，1 条有决定无标签（`docs/review_20261105/audit_results.json` 的 R3）。补足它不需要新增遥测，只需要**两份产物 join**：

- `candidates.jsonl`：门自己产生的决定，格式见 [candidate_stream_schema.md](candidate_stream_schema.md)；
- `labels.jsonl`：**离线**独立评价产生的标签与分段，格式见本文。

两者以 `(run_id, candidate_id)` join。标签**不得**写进候选流——采集时是实时的，GT/clean proxy 只存在于离线。

## `labels.jsonl`

```json
{
  "run_id": "fl_run_20261110T023139Z_2912547",
  "candidate_id": "cand_0007",
  "segment": "degraded",
  "segment_basis": "pre_registered_window",
  "independent_label": "beneficial",
  "label_source": "gt_trajectory",
  "label_rule": "pre_registered: benefit if unsupported fraction falls by >= 0.05 on the candidate's own frames and ATE does not worsen",
  "label_evidence": {
    "unsupported_before": 0.6251,
    "unsupported_after": 0.0931,
    "ate_delta_m": -1.59,
    "frames": 400
  },
  "provenance": {
    "script_sha256": "<sha of the evaluator that produced this line>",
    "reference": "hall01 clean-run proxy, 8,490,000 points",
    "input_sha256": {"clean_bag": "<sha>", "candidate_poses": "<sha>"}
  }
}
```

## 键的含义与纪律

| 键 | 要求 |
|---|---|
| `segment` | `normal` / `degraded` / `recovery_tail`。分段来自**预注册的注入窗边界与时间戳**，不得由门的状态反推 |
| `segment_basis` | 写明依据：`pre_registered_window` 或 `gt_clean_proxy`；不允许空 |
| `independent_label` | `beneficial` / `harmful` / `neutral` / `unknown` |
| `label_source` | `gt_trajectory` 或 `clean_run_proxy`；**不得**是门自身的任何输出（`weak_dir_info_*`、`holdout_nis`、`paired_benefit_status`） |
| `label_rule` | 判定规则必须**先于**看结果写死，并原样存在每行里；改规则=新实验 |
| `provenance` | 评价脚本 sha、参考面、输入 sha；缺一项则该行作废 |

## join 规则

1. **每个候选都必须出现**在 `labels.jsonl` 里；标签缺失写 `"unknown"` 并在结果中**计数**，不得丢弃该候选。
2. 标签为 `unknown` 的候选**不进**混淆矩阵的分母，但必须在 `unlabeled_count` 里报出来。
3. join 后每个候选必须恰好一行标签；重复键视为错误，不取其一。
4. B5 的分母 = 被判为 `harmful` / `beneficial` 的候选数；B7 的分母 = 某段的候选数。都从记录取，不从 GROUP/帧数换算。

## 归属

- `candidates.jsonl`：A10/B11 原生闭环产出（r11070-c3）；
- `labels.jsonl`：离线独立评价产出（r26534-58）；
- join 与混淆矩阵：B5/B7 分析者，结果里必须附两份输入的 sha。
