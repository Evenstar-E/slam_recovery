# 18297d1增量审阅：旧档header资格误标关闭，主线运行结果未增加

面向：开发S1/S2/S3与独立复核者。固定2026-11-13 02:25:55 UTC+8 fetch main `18297d1d4e8bf4518e7329359a56f29beb5130f9`，比较 `cdd3bf70eb78287b102301bb5c6529185cea231d`；开发修正 `4796f97976c26dfb6ca8373f7d3e728c8264c61f`。已读AGENTS、MAINLINE_PROGRESS_STANDARD双表、REVIEW§10、历史§93–94；规则未变，忽略stop.md、直接用户暂停优先。四Cron仍repair-f3持有，未见旧owner、不重建/双写；私人handoff不读不动。跳过Auto-Review/纯合入及已验原件。

**结论：旁支资格缺陷已关闭；实际测量修复→原生状态/地图重处理→输入接回主线结果未增加。** 新增只有一个资格表达式、旧summary对应字段与文档口径对齐，无新宿主实现/运行、独立检测性能或净收益。

## 1. 有限核验与关闭范围

[自写reader](run_checks.py)/[结果](local_checks.json)实际exit0，标准库Python -I仅执行已读资格表达式的两个正常分支及fixed Git字节/JSON比较，不执行归档CLI/ROS/bag/build/安装/算法，不重跑旧parser/Log/成员或原生资料。

```text
C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_18297d1/run_checks.py <新JSON输出路径>
```

| 项 | 状态、证据 | 影响与范围 |
|---|---|---|
| 实际跨度资格 | PASS_LOCAL | true_span_512→PASS；原v11限定raw-header数值层不变，不升级完整点成员 |
| 旧机械资格 | PASS_LOCAL，旧缺陷关闭 | mechanical_prev_last→HEURISTIC_UNPROVEN；旧v7不再无条件PASS |
| 保存结果对齐 | PASS | 旧t2_summary只有RAW_HEADER_CONTAINMENT字段变；其他全JSON等价。两join与v11 summary逐字相同，数值/人口/零约束/tail/UNKNOWN未改 |
| 文档 | PASS_SOURCE限定 | v11 §5拆三层，179 deadline前/303之后补齐；旧47尾行/12尾块/51块成员表述统一。COLLAB历史原文保留、更正另列，不改写历史 |

新source/输入/结果SHA在JSON列明。上一轮正常原件反例在此版本关闭，后继不再要求重做同缺陷/实验。完整成员ASSERTED_NOT_VERIFIED、cov NOT_AVAILABLE、全部UNKNOWN与正常校准/独立标签未解；资格字段修好不证明检测风险或恢复成功。

## 2. 主线和旁支

| 分类 | 下一实交、责任与依赖 |
|---|---|
| 主线 | S1唯一集成、S2真实宿主：沿已指出的MM-LINS FAST-LIO＋PGO两节点输入面，交实际测量修复→前端native状态/map→PGO后继接回/E2，或具体文件/函数首断点＋最低解除和实际认领；本轮未交新接线/运行 |
| 必须先做 | 仅所选host真实输入/config/source、恢复状态时间和map/后继一致依赖；不把本轮资格收口或完整多宿主防御框架前置 |
| 可并行 | S3回真实数据校准/独立标签的既有有限工作，复用已验资格/零约束/事件口径；S2上一轮独立workspace身份/输出/实际脚本与四宿主比较纠正，未交不假称解除 |
| 延期 | 一般文案、FAST-LIVO2新增适配/构建/实验、ASan/大矩阵；旧sigma/κ/floor仍停、科学门不降 |

S3最小修正实交、S1集成可核；S2新主线认领/具体调用点与执行尚未交。后继随实际交付逐项**PASS/FAIL/BLOCKED/NOT_APPLICABLE＋命令/原件＋主线影响/下一动作**，保NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE/UNKNOWN及完整失败/缺项人口。不再制造纯收到规则循环，不按日志/test数计主线成果。

A1/A11资格记录局部关闭；A3/B3未增检测性能，A4/A6/A9/A10/B2/B4/B11无新完整恢复/收益，未重评全表总分。四宿主分别验、不以派生前端工作区运行代原版实现或豁免其余、不提前放行FAST-LIVO2；08:53如实报告不延期。中文关闭记录现独立review分支SSH白名单发布，不算法/main merge/历史重写/私人/开发日报/凭据，不新增授权/绕权限。
