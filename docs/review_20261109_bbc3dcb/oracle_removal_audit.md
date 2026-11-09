# room_02 oracle-removal 审计

对象：`docs/review_20261109_bbc3dcb/run_room02_decomposition.py`（主树 a05a8ba / da09333）
及其产物 `room02_decomposition_results.json`、`room02_filter_report.json`。
脚本 `oracle_removal_audit.py`，结果 `oracle_removal_audit.json`，fixture
`test_oracle_removal_audit.py`（11 项）。

**只读审计**：未改主树、未改对端脚本、未重跑宿主。

## 结论

**第 1 项通过，oracle 臂的身份成立，不是 BLOCKED。**
其余四项不符合：一处 fail-open、一处会抛 KeyError、一处只按计数绑定、一处缺字段。
四项都**不影响今天的数字**（当前数据没有任何一帧触发它们），但都属于「换个输入就会错且不报错」的类型。

| # | 项 | 结论 |
|---|---|---|
| 1 | layout/order 一致性 | **符合** |
| 2 | `_oracle_body` fail-closed | **不符合**（fail-open） |
| 3 | clean pose 可用性 | **不符合**（KeyError） |
| 4 | healthy sidecar 绑定 | **不符合**（只按计数） |
| 5 | 时间分区计数 | **不符合**（字段缺失） |

## 1. layout / order：符合

599 个共同 header ns，逐帧核对：

| 检查 | 结果 |
|---|---|
| `point_step` 不一致 | 0 |
| 字段布局不一致 | 0 |
| 每帧行数不一致 | 0 |
| 字节不同的帧 | 199 |
| 窗口 `[min,max]` 内未判为不同的帧 | **0**（窗口连续，无缺口） |
| 行集合相同但顺序不同的帧 | **0**（前 200 帧全查） |
| 每帧不同行占比 | median 0.882，max 0.897 |
| 整帧每行都不同的帧 | 0 |

这直接回答了审阅最担心的情况：两包没有重编码/顺序差异。`differing` 是**逐行、同索引**比较
（`(a != b).any(axis=1)`），不同行占比 0.88 与注入器的方位扇区 0.88 吻合，且没有任何一帧
整体不同——如果是重排，整帧都会"不同"。

**因此第 1 项不是 BLOCKED**：C 臂（oracle）确实剔除了被注入改写的那些行。

## 2. `_oracle_body` fail-open：不符合

```python
# run_room02_decomposition.py:133-135
if a.shape != b.shape:
    return inj_kfs[i]["pts"]           # cannot split rows; fall back to the raw scan
```

形状不匹配时**静默返回原始注入扫描**，且返回值的类型与正常 oracle 帧完全没有区别——
调用方无从得知这一帧其实是 RAW。结果是把「无法拆分」的帧按 `ORACLE_CLEAN` 计入 C 臂。
此外没有 `if ns not in inj_raw` 之类的缺帧保护，缺帧会直接 KeyError。

**今天的实际影响：0。** 599 个共同帧里形状不匹配的有 0 个，所以该分支从未触发。
但它是一个陷阱：任何一次重新编码（改变 `point_step` 或行数）都会让 C 臂在该帧退化成 B 臂，
而结果 JSON 不会显示任何异常。

fixture 用构造输入（4 行 vs 5 行）确认该分支会被走到的条件；因为 `_oracle_body` 是
`main()` 内部的闭包，进入它需要调用 `main`，所以这一项是**静态断言 + 分支条件复现**，
不是真正执行到它——证据强度低于其余各项，报告如实标注。

## 3. clean pose 可用性：不符合

```python
# :122-123
frames = [i for i in keys
          if i in rerun_poses and round(inj_kfs[i]["ts"], 6) in by_stamp]
# :120
ref_poses = {i: T_inv @ cln_poses[i] for i in cln_poses}
# :155
w = body @ poses[i][:3, :3].T + poses[i][:3, 3]
```

frame set 只检查 rerun 位姿与过滤扫描，**不检查 clean 参考位姿**。`ref_poses` 是
「有 clean pose 的帧」的子集字典；某个 key 若缺 clean pose，会走到 `poses[i]` 抛 **KeyError**，
脚本终止，而不是把它计入 `missing`。

**今天的实际影响：0**（脚本跑通，说明 326 帧都有 clean pose）。但「跑通」只证明当前数据
恰好覆盖，不证明逻辑正确：缺一帧的 clean 位姿会让整次分解中止，而不是给出一个带 missing
的诚实结果——`frame_set.missing`（72 帧）里也不会出现它。

## 4. healthy sidecar 绑定：不符合

```python
# :204-205
ok = (fr.get("binding", {}).get("verdict") == "BOUND"
      and fr.get("input_sha256") == sha["injected_scans"])
```

只核 `binding.verdict` 与源包 hash，**不核 `output_sha256`**。而报告自带的 binding 本身
就是按计数定义的：

```
"method": "every frame's n must equal the input bag's point count and its kept must equal
           the output bag's point count, at the same header millisecond"
```

同计数、不同内容 → 仍然 BOUND。报告里**确实有** `output_sha256`，所以这条检查本可以做得更强。

fixture 直接复用生产者的条件表达式，喂入一份 `output_sha256` 被改掉、其余不变的报告，
断言它仍然通过——这不是推测，是把那一行条件原样跑一遍。

**今天的实际影响：0。** 现算：报告 `output_sha256` = 当前 `room02_inj43_filtered.bag` 的
sha256 = `6bb96618…`，与 `inputs_sha256["filtered_scans"]` 也一致。所以
`real_filter_removed 919,702 / 4.47%` 这个数今天是站得住的；不成立的是「它被验证过」这件事。

## 5. 时间分区计数：不符合

`arms` 每个臂只有整集总量：

```
scan_source, pose_source, map_points, proxy_covered, proxy_coverage_fraction,
patch_unsupported_points, patch_unsupported_fraction, patch_median_m
```

**缺**：`in_window_unsupported_fraction`、`in_window_retained_fraction`、`in_window_map_points`、
`healthy_unsupported_fraction`。脚本 docstring 承诺了 "the in-window unsupported fraction per arm"，
结果里没有。

只有 `healthy_window` 块按窗外分区（`points_outside 20,576,778`、`real_filter_removed 919,702`、
`oracle_removed 0`），**没有对应的窗内块**。

影响的是解释力而不是数字本身：五臂的 coverage/unsupported 是窗口内外混在一起的，而
A→B（位姿）、B→C（测量）这两个分解只在窗内有意义。窗口外两臂的扫描其实相同，
把窗外 400 帧混进分母会稀释差异。**这不是数值错误，是分母口径没有披露。**

## 无法核验

- **闭包的运行时行为**：第 2、3 项是静态断言。要真正执行 `_oracle_body` 与其调用方需要
  调用 `main()`，那会重跑分解并写结果文件——超出「只读」约束。
- **clean 参考的独立性**：`CLEAN_RUN_FROM_RAW_WINDOW` 是同一段 raw 窗口的另一次运行，
  不是独立 GT；报告已把它标为 proxy，本次未对其做进一步核验。

## 对既有结论的影响

- C 臂（oracle 天花板）**可信**：第 1 项通过，且当前数据没有触发第 2 项的退化路径。
- 第 3、4 项是「换输入才出错」的脆弱性，不影响已发布数字。
- 第 5 项建议补窗内分区后再引用 A→B / B→C 的分解幅度，否则读者无法判断这些差异是否被
  窗外 400 帧稀释。
