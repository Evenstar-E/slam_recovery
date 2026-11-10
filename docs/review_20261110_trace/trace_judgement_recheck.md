# trace 判据复算（2026-11-10）

对方已出结论 `UNKNOWN / TRACING_IS_NOT_THE_MECHANISM`。这里用**预先写死的判据**
（`docs/review_20261109_bbc3dcb/trace_compare.py`）复算，只报数据支持到哪一步。

## 输入（取自 main，未改动）

| 文件 | 来源 | sha256 |
|---|---|---|
| `on1.csv` | `main:docs/review_20261109_bbc3dcb/on1.csv` | `00af7948…f7c5` |
| `on2.csv` | `main:docs/review_20261109_bbc3dcb/on2.csv` | `edb804c4…aec3` |
| `trace_default_emit_fixed.csv` | `39eac2f`（默认构建，移到 DET_SYNC 之外后） | `5fcccddc…642a` |

三次运行的 receipt 表明：`on1/on2` 与 `off1/off2` 用**同一个二进制**
（`76359f53…a53b`），`default` 是另一个二进制（`6e0a3e57…3d8e`）。

## 判据结果

| 对 | GROUP | IMUINIT | 首个 STATE 分歧 | 判据 |
|---|---|---|---|---|
| `on1` vs `on2` | 1766/1766 完全相同 | 5/5 相同 | index 87，`1.192 mm` | **UNKNOWN** |
| `on1` vs `default` | 1766/1766 完全相同 | 5/5 相同 | index 75，`1.104 mm` | **UNKNOWN** |

分组构成在两趟之间逐项相同（数量、首末时间戳、样本 sha、`mesures`/`img`），而状态分歧——
按预注册规则，分歧**不能**归给分组构成，且单对 trace 不出因果结论。与对方结论一致。

## 但控制组不在 trace 里

预注册判据里"tracing OFF 的对照也分歧 → 分歧不是 tracing 造成的"需要**两趟 OFF 的 trace**。
这两趟 OFF 存在（`off1`/`off2`，`res_off1.bag`/`res_off2.bag`），但 tracing 关闭时**不产出 CSV**，
所以 trace 层面的控制组是**空的**，判据只能停在 `UNKNOWN`。

用输出 bag 补这个控制（`pose_control.py`，读 `/aft_mapped_to_init`，同一物理量）：

| 对 | tracing | 首个 >1mm | 中位差 | 最大差 | >1mm 的帧 |
|---|---|---|---|---|---|
| `on1`–`on2` | ON | index 38，1.33 mm | 19.2 mm | 355 m（index 777） | 743/800 |
| `off1`–`off2` | **OFF** | index 38，1.35 mm | 17.3 mm | 729 m（index 799） | 730/800 |

两趟 OFF 在**同样的 index 38** 开始分歧，末端差到 729 m。也就是说：run-to-run 分歧在
tracing 关闭时同样存在，且量级不更小。这才使"分歧不是 tracing 造成的"从"与数据不矛盾"
变成"被数据支持"。

## 边界

1. 这是**同一个不稳定 cell**（room02 `O`）的两对 run；它证明分歧在 OFF 下存在，不证明量级可迁移。
2. `default` 是**不同二进制**，`on1`–`default` 的 75 与 ON/ON 的 87 不可直接比较先后——构建差异与
   tracing 差异在这里是混在一起的。
3. 结论仍是 `UNKNOWN`：没有机制被识别。`TRACING_IS_NOT_THE_MECHANISM` 是"排除了 tracing 是主因"，
   不是"找到了原因"。

## 复现

```bash
python -I docs/review_20261109_bbc3dcb/trace_compare.py on1.csv on2.csv
python -I docs/review_20261110_trace/pose_control.py \
    /tmp/fastlivo/res_on1.bag /tmp/fastlivo/res_on2.bag \
    /tmp/fastlivo/res_off1.bag /tmp/fastlivo/res_off2.bag
```
