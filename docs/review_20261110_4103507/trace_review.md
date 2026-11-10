# trace旁支补验：4103507

日期2026-11-10。固定目标 `41035074f63fe1d9e77b9b8f0643f757bb191eab`，来源 `1c2c770/4d38242/4f8f5d8/4103507`。仅审trace_schema.md、trace_compare.py、test_trace_compare.py及适用协议；不修改算法，不跑ROS、不生成真实trace。

## 结论与主线关系

规范pipe-only格式可解析，**14/14合成fixture通过**，但不能用现工具判定实际消费是否相同或排除机制。归并为三个最小保障包：身份/完整性、数值/CSV完整性、判决/因果边界。它们只阻断依赖这个比较器的trace判决，不阻断A5/A8/A9事务主线。对应A2/A11、B6/B8，没有新原生测量、没有新全表评分。

独立旁支审阅后，主会话绑定固定git源码再次执行：

```text
python -I -B docs/review_20261110_4103507/trace_boundary_probes.py
14 tests ... OK (0.029s)
Six invalid-evidence counterexamples and one valid control confirmed at the fixed revision.
```

脚本通过代表已复现产品边界，不是产品保障通过。读取CSV反例全部在内存；fixture临时文件限制在独立TemporaryDirectory并清理。

## 1. 同帧身份与缺测未fail-closed（必须先做，限trace判决）

`trace_compare.py:146-159`按STATE行号zip，不核lid_stamp_ns。A stamp100、B stamp900，位置同为0时判NO_DIVERGENCE；移位序列还会把不同帧的位置差说成首个状态分歧。双方空CSV/没有STATE也判NO_DIVERGENCE，GROUP/IMUINIT零条时identical=true（:117-143/170-176）。

GROUP signature（:111-114）不包含lid_stamp_ns、img_stamp_ns。改变lidar100→999、image90→95，其余摘要相同，仍groups.identical=true，并说“group composition cannot be the mechanism”。摘要相等只能限定它实际覆盖的字段，不能排除未记录的图像/消息差异。

独立复核还确认重复STATE/GROUP ID、缺STATE ID、非digest的GROUP sha及必要字段为空能被接受。ARRIVE被解析但不参与比较；仅样本时间戳hash不能证明IMU测量内容相同，不能据其定位逐样本数值首差。

最低解除：在实际运行前冻结匹配键、必要字段/唯一性/顺序和共同支持；缺失与有效相等分开，首差携带双方身份。GROUP绑定具体lidar/image与STATE；没有实际记录时INVALID/UNAVAILABLE，不给排除结论。run/source/config/input/actual executable+so由runner/receipt另绑定，本轮未审runner，不能据三文件断言整条链不存在这些记录。

## 2. 非有限/错误维数/损坏CSV当作正常（必须先做，限trace判决）

`Event.xyz(:39-45)`不校验3维有限数；`parse(:84-107)`不拒绝额外CSV列、重复extra key（:78覆盖）。

主会话复现：A pos=nan|0|0，B pos=20|0|0，判NO_DIVERGENCE；裸CSV A pos=0,4,9与B pos=0,8,12都只解析首个分量0，仍NO_DIVERGENCE。独立审阅另确认双方2维、inf及重复pos覆盖。

最低解除：精确表头/列数、3个finite位置分量、duplicate key显式拒绝；损坏/缺测不进入正常判决。未知kind、浮点时间、缺GROUP sha现有拒绝方向保留，不推翻已通过正例。

## 3. 判决与ON/OFF因果结论过强（必须收窄，不扩排障）

`judge(:181-187)`将任何非None control_div当作有效分歧。OFF双方共同状态相同，但一侧少一帧，输出length differs，并推断“not caused by tracing”；这是缺测而非状态效应。即使OFF有真实小分歧，也只能说明现象可在OFF出现，不能排除trace放大幅度/概率/其他贡献。schema:75和test:125-131固化了过强排除；“单对不出因果结论”不足以抵消。

另外比较器只比pos，却称every state sample一致；diagR不同、速度/bias未比较不能宣称完整状态一致。GROUP不同且pos同，顶层NO_DIVERGENCE与schema:74的GROUP_COMPOSITION_VARIES优先级不一致；分别报告位置一致性/分组变化更清楚。IMUINIT当前摘要不覆盖max字段。CLI只给一个control路径会静默忽略，其他参数数量也不严格（:195-201）。

最低解除：有效位置分歧、缺测、无效输入分型；对照报告事实与未排除项，不宣布因果排除。限定“位置/已比较字段相同”，若要扩状态字段先冻协议。判决优先级、CLI路径数量、旧schema表分号与img_stamp名称集中收口，不为这些文案重跑宿主。

## 已验收与未验收

| 项 | 状态 | 范围 |
|---|---|---|
| canonical pipe解析/现有fixture | PASS（局部） | 14合成tests，未知kind/浮点时间/空sha已有拒绝 |
| 同帧身份/必要证据/数值损坏 | FAIL | 固定源码六反例再次复现 |
| 同帧第二位置首差正例 | PASS | index1/stamp200/max_axis_delta5m |
| 实际writer/线程安全/采集扰动 | NOT_APPLICABLE（本轮） | 无C++实现或实际ON/OFF trace运行 |
| 真正根因/完整状态一致性 | UNAVAILABLE | 工具与单对trace不能证明 |
| 新native效果与A/B升档 | NOT_APPLICABLE | 旁支保障不能冒充主线修复成果 |

开发主会话并行分发：事务主线继续；trace侧一次性完成上述最小保障和针对性正负例，再给安全snapshot/单writer采集的有限真实证据。A7可按资源并行准备。交接前先按§10.12给PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令/证据、已选主线与调整分工，不再生成一轮纯“接受意见”的文字反馈。
