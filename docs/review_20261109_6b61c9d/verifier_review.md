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

## 4. 新增的验收规则（对 fixture 可跑）

| 规则 | 作用 |
|---|---|
| `check_outside_equals_filtered` | 要求 `outside > 0`、`failures` 与 `checks` 字段存在、无 outside 失败、标志为 True。空集判违规。 |
| `check_combined_equals_filtered` | 要求 `in_window > 0`、无 combined 失败、标志为 True。空集判违规。 |
| `check_all_checks_present` | 四个 check 键必须齐全，缺一即违规。 |
| `check_preregistration` | `declared_before_results=True`、`repetitions_per_cell >= 2`、`failure_threshold_ate_m == 1.0`、四格名称齐全。 |

「缺字段」一律判 UNVERIFIABLE（返回违规），不当作通过。

已入库 receipt 通过全部四条；四项违规 fixture（空窗外、空窗内、真实差异、标志为假）全部被拒。
