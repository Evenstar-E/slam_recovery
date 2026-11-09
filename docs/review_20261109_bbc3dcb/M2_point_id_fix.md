# M2 point-id fix：并行 mask + sidecar + 回归

对应阻断项（`M2_record_audit.md`「不符合 1」）：过滤包只保留了 24 B 字节行，无法按原始点索引命名。
本次一并交付审阅指出的两处审计漏洞修复。**两类改动分开列在最后一节。**

## 1. 导出器改动

文件：`docs/review_20261109_bbc3dcb/run_fixed_input_repair_c0c3.py` 的 `build_filtered_bag()`。

**并行话题**：`/velodyne_points/kept_index`，类型 `std_msgs/msg/UInt32MultiArray`。

- 载荷 = `np.flatnonzero(keep)`，即该帧**保留下来的原始点索引**，有序、一对一。
- 与 `/velodyne_points` 用**同一个 rosbag 时间戳**写入，二者严格成对。
- 该消息类型没有 header 字段，因此把扫描的整数纳秒写进 `layout.dim[0].label`（`scan_ns=<ns>`），
  让配对不依赖"第几条消息"这种脆弱假设。
- 未改 `point_step`（仍 24），字段顺序/偏移不变，宿主解码不受影响。

**sidecar**（`FILTER_REPORT_OUT`，默认 `/tmp/filtered_bag_report.json`）新增：

```
source_bag_sha256 / output_bag_sha256      源包与输出包的 sha256
id_topic / id_msgtype                      /velodyne_points/kept_index, std_msgs/msg/UInt32MultiArray
id_encoding                                uint32 原始索引；mask_sha256 是同一索引按 int32 小端 C 序的 sha256
id_payload_bytes                           4 × 保留点数
per_frame[].scan_ns / n_original / n_kept / mask_sha256
```

`per_frame` 原有的 `t` / `n` / `kept` 保留不动，避免影响已发表报告的下游读取。

## 2. 从 mask 重建原始 id

```python
mask = np.asarray(id_msg.data, dtype=np.uint32)        # 有序、无重复
src_rows = source_cloud_rows[std_msgs_kept_index]      # 过滤包里的第 j 行 == 源包第 mask[j] 行
deleted = np.setdiff1d(np.arange(n_original), mask)    # 被删的原始索引
assert np.array_equal(src_rows, filtered_rows)         # 逐行 24 B 相同
```

即：**过滤包的第 j 行由源包第 `mask[j]` 行原样搬来**，其余行 `deleted` 被删。
不需要值匹配，也不需要重放。

## 3. 体积

int32 掩码：21,198,773 保留点 × 4 B = **84,795,092 B**，输出包 1,415,868,354 B，
**开销 5.99%**。用 int64 会翻倍到约 12%，没有理由：单帧点数 5×10⁴ 远小于 2³²。

## 4. 回归测试

`test_m2_point_id.py`，`python3 -m unittest discover -s docs/review_20261109_bbc3dcb -p "test_m2_point_id.py"`，
5 项全过：

| 测试 | 断言 |
|---|---|
| `test_sidecar_binds_both_bags` | `source_bag_sha256` / `output_bag_sha256` 存在且为 64 位 |
| `test_mask_pairing_and_sha` | 每条 mask 都能用 `scan_ns` 找到 sidecar 行；长度与 `n_kept` 一致；sha256 复算一致（598/598） |
| `test_mask_is_sorted_and_in_range` | 掩码严格递增、无重复 |
| `test_retained_rows_are_exactly_the_mask` | 抽样 20 帧：`source_rows[mask]` 与过滤包载荷逐字节相同；字段表与 header 不变；`row_step == point_step × width` |
| `test_zero_deletion_frame_has_identity_mask` | 零删除帧 mask == `[0..N-1]`，且该帧载荷与源包**逐字节相同** |

## 5. 样例值

| 帧 | scan_ns | n_original | n_kept | mask_sha256 |
|---|---|---:|---:|---|
| 首个被过滤帧（145） | 1627785275607408524 | 50,260 | 5,852 | `93f9216463adfa61227d61a1a57c98be768d9759a97fca30d3a44e4361921bf3` |
| 零删除帧（0） | 1627785261079016209 | 50,426 | 50,426 | `fdbecf773f522ddc43695d72d888bf527b422940711891793204e95720f7edee` |

**交叉验证**：首个被过滤帧的 `mask_sha256` 与本地独立导出器（`docs/review_20261109_6023655/c3_export_filtered_bag.py`，
它把 `flatnonzero(keep)` 写在 `/slam_recovery/filtered_point_ids`）对该帧记录的
`kept_id_sha256` **逐位相同**。两个互不相干的实现给出同一个掩码，说明这不是某一侧的口径产物。

新包 sha256 `a1113a765f2e3783698c6c1b6b342ec49501fee6dcb3b3098a277eb8d41187ec`，
写在 `/tmp/fastlivo/hall01_inj43_filtered_id.bag`；原来被审计的 `c90300cb…` 包**原样保留、未覆盖**
（重跑时 Writer 会拒绝覆盖已存在文件，本次是显式写到新路径）。

## 6. 这次提交的两类改动

### A. 导出器改动（修阻断项）

- `run_fixed_input_repair_c0c3.py`：并行 mask 话题、sidecar 的 mask 字段与两个 bag 的 sha256；
  `FILTER_REPORT_OUT` 环境变量让 sidecar 可写到别的路径（原先硬编码，多输出会互相覆盖）。
- `test_m2_point_id.py`：新增回归。
- 本文件。

### B. 审计改动（修审阅指出的两处漏洞）

- **行验证原先只取前 25 帧**，而前 25 帧 `strip_fraction` 全为 0，首次剥离在 index 145——
  也就是说原审计的"逐行一致"只覆盖了健康帧。现在 `verify_stripped_frames()` 从 **200 个被过滤帧**
  里取样 12 帧（含首帧、末帧、剥离比例最大帧）：要求保留行在源包中**有序且一对一**
  （贪心唯一分配，不是 `np.isin` 集合包含），被删行恰为 `keep` 的补集，且每帧计数与
  filter report 吻合。12 帧全部通过，`rows_missing_from_source=0`。
- **`missing_observation` 字段名写错**：原审计读 `missing_observations`（复数），归档里是单数，
  于是缺失字段被当成 PASS。现在按实际字段读取，字段缺失即 `UNVERIFIABLE`，并校验
  计数与 ID 列表长度一致、计数非零时列表必须可枚举。
- **point id 判定改为解码 schema**：不再用"话题名里有没有 id"，而是检查点云字段表里是否有
  `id/index/point_id`，以及除三个已知话题外是否还有并行话题。对旧包 `c90300cb…` 仍判 FAIL
  （它确实没有），对新包判 PASS。

审计结果随之更新（`M2_record_audit.json`）：被过滤帧抽样 **PASS**，
标签相关 4 项全部 **PASS**，point id 对旧包仍为 **FAIL**——这正是本文件第 1 节要修的东西。
