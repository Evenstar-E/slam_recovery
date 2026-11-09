# `verify_single_factor_bags.py` 判定逻辑复核（审阅 dc714e9）

只读复核，未改该脚本。规则实现见 `single_factor_audit_rules.py`，fixture 见
`test_single_factor_audit_rules.py`（17 项，含对已入库 receipt 的验收）。

## 结论

两条关键判定**在数据上成立**，且判定方式是对的（逐行字节比较，不是哈希集合）：

```
frames {total 599, in_window 199, outside 400}
checks {outside_all_equal_filtered: true, combined_equals_actual_in_window: true,
        arms_match_original_indices: true, row_counts_match: true}
failures 0
```

但有四处**判定强度**问题，其中第一处会让空集自动通过。

## 1. 「窗外四臂 == filtered 包」

代码 `:111-113`：

```python
else:
    n_out += 1
    for a in BAGS:
        if not np.array_equal(got[a], fil_rows):
            failures.append({"why": "outside window differs from filtered scan"})
```

- **做对了**：`np.array_equal` 比较的是逐行 `uint8`，不是哈希集合，所以行序与重复多重性都在比较范围内；四臂各自比，不是抽样。
- **空洞风险**：若 `n_out == 0`，该分支不执行，`checks` 里仍是 `True`。当前 400 帧，所以今天不触发。
- **判据来源**：`outside_all_equal_filtered` 由 `not any(why.startswith("outside"))` 推出，
  依赖失败消息的字符串前缀。若将来改了措辞（例如 "Outside window ..."），标志会静默变真。
- **未覆盖**：只比 `data` 行，不比 `height/row_step/is_dense`。行数相同而 `row_step` 写错时不会被发现。

## 2. 「O+F−B 窗内 == filtered 包」

代码 `:103-105`：

```python
if not np.array_equal(got["O_plus_F_minus_B"], fil_rows):
    failures.append({"why": "combined cell differs from actual filtered scan"})
```

- **做对了**：同一帧内直接与 filtered 的载荷逐行比较；且 `arms["O_plus_F_minus_B"] = kept`
  又与 `inj_rows[kept]` 比较过一次，等于双向校验。
- **空洞风险**：若窗口内一帧都没有（`n_in == 0`），同样自动通过。
- **构造风险**：`O_plus_F = np.union1d(bg, kept)` 会**排序**，`O_minus_B` 用
  `assume_unique=True` 的交集。只有当 sidecar 的 `bg`/`kept` 本身有序唯一时，
  臂内行序才等于「按原 index 升序」。当前 verifier 靠 `got[a] == inj_rows[idx]` 反向确认了这一点，
  但没有单独断言 sidecar 的单调性；若 sidecar 乱序，错误会以「rows differ」的形式出现，
  定位到的是臂而不是 sidecar。

## 3. 其他

- **短包会崩而不是报失败**：`next(it[a])`（`:84`）在某臂消息数少于 filtered 时抛
  `StopIteration`，脚本以异常退出，不写 receipt。这是 fail-loud，可接受，但不会留下可审计的
  失败记录。
- **`O` 与 `O_plus_F` 的行数**只通过 `expected_in_window_rows`（bag 侧）与实构造比对，
  verifier 本身不读取那份期望值；即 `single_factor_bags.json` 的 1,186,220 / 1,187,485 /
  1,162,613 / 1,163,878 与 receipt 的一致性没有被交叉核对。

## 3b. 后续：`0057df3` 已修掉三处判定弱点

复核该提交后确认：

| 弱点 | 现状 |
|---|---|
| 空集自动通过 | `n_out==0` / `n_in==0` 分别记 `empty_outside` / `empty_window`，且对应 check 显式要求 `n_* > 0` |
| 字符串前缀判据 | 失败改为 typed `kind` + 计数器，check 由 `failure_counts` 推出；`why` 保留为文本 |
| 元数据未比对 | 窗内逐帧比 `(width, height, row_step, point_step)`，窗外比完整 `_meta`（含 `is_dense`） |
| 短流无回执退出 | `StopIteration` 与任何异常都落 `missing_message` 并写 receipt，退出码非零 |

receipt 另增 `frames_complete` 检查与 `preregistration` 块（`repetitions_per_cell=2`、
`failure_threshold_ate_m=1.0`、四格、交互判据），并单独落
`single_factor_preregistration.json`。

**一处仍建议**：兜底 `except Exception` 复用 `kind="missing_message"`，其 `why` 是
「某个包先于参考流结束」，与真正的致命异常语义不符；`error=repr(exc)` 带上了真相，但
读 `failure_counts` 的人会把它误读成短流。建议单列 `kind="fatal"`。

我的规则也随之改为**优先读 `failure_counts`**，仅在缺该字段时回退到 `why` 前缀——
否则我自己就还在依赖被批评的那套判据。

## 3c. `700c1b7` 的 sidecar 顺序断言：已加，但未接入判据

`700c1b7` 在逐帧比较前先断言每帧 `k<ns>`/`b<ns>` 严格递增，违例记
`kind="sidecar_order"` 并指向 sidecar——这是对的，乱序不再被算到臂上。

**但它没有进入 `checks`**：`checks` 只由 `outside_mismatch / metadata_mismatch /
combined_mismatch / index_mismatch / row_count / stamp_mismatch / missing_message` 推出，
而退出码是 `return 0 if all(checks.values()) else 1`。因此：

- `sidecar_order` 违例 → 计数加一、`failures` 有一条，但五项 check 仍全 True，**退出码 0**；
- 同样地，兜底的 `kind="fatal"` 也不在任何 check 里，异常中止后若 `n_in/n_out` 已计数，
  也可能以 0 退出。

即：失败被**记录**了，但没有**门控**结论。今天的 receipt 全零，所以不触发。

新增两条规则：

| 规则 | 作用 |
|---|---|
| `check_sidecar_order` | `failure_counts` 必须含 `sidecar_order` 且为 0；缺字段判 UNVERIFIABLE |
| `check_failures_gate_the_verdict` | 只要 `failure_counts` 有任何非零项，`checks` 就不能全为 True |

建议修法（任选其一）：把 `sidecar_order` 与 `fatal` 纳入 `checks`，或让退出码改为
`0 if not any(counts.values()) else 1`。

## 3d. `1fb8afd` 的增量与索引唯一性复核

新增 `extra_messages`（EOF 假通过）、`sidecar_dtype/bounds/missing_frame/hash_mismatch`
（sidecar 门禁不再只看 `diff > 0`）、`window_mismatch`（窗口来自独立声明并与 sidecar 帧集
双向核对），以及非扫描流的独立 verifier。receipt 现有 **9 项 check**，全 True，计数全零。

**索引唯一性**：我独立复算了 199 个窗内帧——

| 量 | 审计记录 | 我的复算 |
|---|---:|---:|
| 含重复 kept 行的帧 | 0 | **0** |
| 含重复 injected 行的帧 | 未记 | **0**（更强） |
| 单行最大重数 | `max_multiplicity: 0` | **1** |

结论成立：本序列窗内无重复行，按值恢复索引唯一。但 `max_multiplicity: 0` 与我算出的 1
不一致——这个字段显然记的是「超出首份的额外份数」，而字段名读起来是「最大重数」。
建议改名 `max_extra_copies`，或直接报 `max_multiplicity: 1`。数值本身不影响结论。

## 4. 新增的验收规则（对 fixture 可跑）

| 规则 | 作用 |
|---|---|
| `check_outside_equals_filtered` | 要求 `outside > 0`、`failures` 与 `checks` 字段存在、无 outside 失败、标志为 True。空集判违规。 |
| `check_combined_equals_filtered` | 要求 `in_window > 0`、无 combined 失败、标志为 True。空集判违规。 |
| `check_all_checks_present` | 四个 check 键必须齐全，缺一即违规。 |
| `check_eof` | `extra_messages` 计数为 0 且 `frames_complete` 为 True；缺字段判 UNVERIFIABLE |
| `check_sidecar_valid` | 五个 sidecar 类计数全部为 0 且 `sidecar_valid` 为 True |
| `check_window_matches_sidecar` | `window_mismatch` 为 0 且 `window_matches_sidecar` 为 True |
| `check_preregistration` | `declared_before_results=True`、`repetitions_per_cell >= 2`、`failure_threshold_ate_m == 1.0`、四格名称齐全。 |

「缺字段」一律判 UNVERIFIABLE（返回违规），不当作通过。

已入库 receipt 通过全部四条；四项违规 fixture（空窗外、空窗内、真实差异、标志为假）全部被拒。
