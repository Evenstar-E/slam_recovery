# 负结果：在线自动隔离的检查点无法保证"不晚于隔离起点"

日期：2026-11-12。证据 run：`fl_native_20261112T125406Z_533623`（纯在线、detection on、无 scripted、
driver `8d9cd0d`、宿主 `1239f35f…`）。原件在同目录 `trace_online_fl_native_20261112T125406Z_533623/`。

## 观测

| ep | 边界（段 `quarantine_start_ns`） | 实际 checkpoint | frames | 状态 | 偏移 |
|---|---|---|---|---|---|
| 0 | `1627785261507921600` | `1627785265275036928` | 59 | LATE_AFTER_BOUNDARY | **+3.77 s** |
| 1 | `1627785270114168549` | `1627785265275036928` | 59 | AT_OR_BEFORE_BOUNDARY | −4.84 s（复用 ep0 的应用结果） |
| 2 | `1627785288459063196` | `1627785292292419072` | 417 | LATE_AFTER_BOUNDARY | **+3.83 s** |
| 3 | `1627785302541834497` | `1627785306775187456` | 618 | LATE_AFTER_BOUNDARY | **+4.23 s** |

同 run：paired 544、accepted 0 / rejected 4 / errored 0、终态 HEALTHY。

## 结论（负结果，不是未知）

- 在线路径**不支持**"回滚到不晚于 qstart 的检查点"。机制：rolling `snapshot` 不带 apply stamp，
  宿主在**下一个已处理帧边界**执行深拷贝；播放 backlog 下，应用时刻比发出时刻晚数秒，槽内状态的
  时间戳因此晚于隔离起点。
- ep1 的 AT_OR_BEFORE 只是复用 ep0 时应用的那份快照，不是机制保证了正确性。
- 该区间的输入既没有被重放，也没有被正确回滚（`catch_up=NOT_IMPLEMENTED`），因此
  **在线段的回退一律标记为 `UNSUPPORTED_AT_OR_BEFORE_QSTART`，不得写成"自动恢复成功"**。
- scripted 路径不受此结论影响：armed 快照带 `apply_stamp = trigger − margin`，实测早于边界
  15.9 / 12.4 ms。

## 修复语义（同时固化）

被接受的隔离段发布的修复帧（如 42 条）替换的是**扫描的点测量**，宿主在 replay 时用修正后的测量
重新估计；它**不是**对已估计状态/位姿的误差修正。任何"注入已修回"的表述都不成立。

## 可行的修复方向（未实施，供决策）

1. **A（不可行）**：给在线 snapshot 带 `apply_stamp=qstart`。宿主只能复制"当前"状态，无法回到
   过去某个 stamp；命令在 qstart 之后发出，仍然落在下一帧。
2. **B（只解决身份，不解决时间）**：按 episode id 的 keyed checkpoint。它能防止"用错别的段的
   检查点"，但快照仍只能在应用时刻拍，晚于 qstart 的问题不变。
3. **C′（建议）**：宿主保留最近 K 份带时间戳的 checkpoint（环形），`restore`/`reprocess` 可选
   "不晚于 S 的最新一份"。由于宿主被 backlog 拖住，队列里较早的那份通常满足 ≤ qstart；代价是
   回滚更远、需要重放的帧更多，且每份快照是一份地图深拷贝（内存 K×当前快照）。默认 K=1 时
   行为与现状一致，可灰发。
