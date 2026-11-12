# cdd3bf7增量审阅：资格分层及本run尾段接受，旧档header资格误标须最小解除

面向：开发S1/S2/S3与独立复核者。固定2026-11-13 02:05:55 UTC+8 fetch main `cdd3bf70eb78287b102301bb5c6529185cea231d`，比较已验 `b2f3983801e6113f3c3626df0d95783666e1c24f`；开发实交 `ca384cf47560645174a313a1eb6b445ea9ca147e`，另两提交为集成/记录。先读AGENTS、MAINLINE_PROGRESS_STANDARD双表、REVIEW§10、历史§92–93，未变规则沿用；四Cron为repair-f3持有，未见旧owner，不重建/双写。忽略stop.md、直接用户暂停优先；私人handoff仅untracked不读不动。

**结论：旁支证据资格与事件人口局部推进；没有新增原生实际测量修复→状态/地图重处理→接回成果，也没有ALI检测性能新结果。** 本轮只核49行源码改动及保存人口/元数据，不重复已验parser/Log/旧排序或宿主原件，未新起代理、宿主、构建、调参。

## 1. 已接受变化

[标准库只读reader](run_checks.py)/[结果](local_checks.json)实际exit0，仅fixed Git数据算术及AST常量检查，未执行归档代码/完整T2 CLI/ROS/bag/数学工具。命令（输出到新路径，禁止覆盖原结果）：

```text
C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_cdd3bf7/run_checks.py <新JSON输出路径>
```

| 检查项 | 状态、原件范围 | 接受与限制 |
|---|---|---|
| v11资格分层 | PASS_LOCAL/SOURCE局部 | RAW_HEADER数值与SAME_UPDATE_PRE_POST分开；完整点成员ASSERTED_NOT_VERIFIED、cov NOT_AVAILABLE。不会把462数值行写成462独立合格观测 |
| 零约束 | PASS保存人口/标记 | v11 462数值中18 eff0且Log0，旧v7 504中24；保存每条eff与原trace idx对应、zero_constraint一致，不剔除；全has_out eff0的37/35沿原件计数声明。没有把零修正转成NORMAL |
| 派生值来源 | PASS差异核验 | v11数值行mode改same_row_pre_post，旧v7仍vec/M2DGR；既有数字逐值未变，输入四hash未变；相应504/462诊断和531/482人口均保留 |
| 本run尾行 | PASS数值/人口限定 | v11从第二episode取trigger17.002940433s、deadline21.002940433s，相对首trace；按精确deadline1627785282081956625ns标303条尾行，179条之前；0→303是旧错误54s范围的修正，不新检测/新恢复 |
| 时间块 | PASS，量化口径 | 106块全UNKNOWN；64尾块/32个块秒，块成员304条，比精确尾行303多一边界行。首尾块边界是1627785282000000000ns而非精确deadline，相差81.956625ms；不能称完整连续32s恢复服务 |
| 旧档尾段 | PASS未改旧结果 | v7仍legacy_54s_not_run_bound，47尾行/12尾块/51块成员，120块全UNKNOWN；COLLAB§172“51块”是字段误述，51为行、12为块，不重新打开已验两口径差 |

全UNKNOWN是校准/独立正常参照缺项，不等风险为0；unknown_normal是deadline前分区字段，不是独立正常真值。第二episode后的输出不是第二独立真实故障、不是接纳恢复后尾段或catch-up；两晚cp/零修复/零replay/未决负结果沿旧run，不重跑。

## 2. 新正常原件反例：旧v7被无条件标header PASS

新 `t2_run.py:663–667` 的 `i_qualification_layers.RAW_HEADER_CONTAINMENT` 直接常量 `"PASS"`，未引用本run的join模式。保存 `t2_summary.json:_meta` 已据此写PASS，但同份meta仍join_status=HEURISTIC_UNPROVEN，原115734档完整1041行scan_first全−1，使用机械关联，不具备真实raw首末跨度。这个新资格字段覆盖到旧档、与已冻结旧资料及新的资格正文冲突；不是假设格式兼容或恶意输入。

**状态：FAIL_REPRODUCED_SAVED_METADATA。最低S3/S1**只从现有join.mode/status派生这一层：实际true_span_512限定PASS；旧机械人口维持HEURISTIC_UNPROVEN/未验证，与旧输入一致。保原数字、tail、零约束和完整人口，不重做parser/成员架构、不新导出/宿主run。不影响当前v11数字或非FAST-LIVO2原生接线，只阻止引用旧v7这一层作合格来源证明。

v11正文§5尚保“source scan身份PASS”的旧笼统行，一页表已拆三层；最低随同集中对齐即可，不另开文案循环。zero_constraint保present只是保数值分母，当前全UNKNOWN尚无NORMAL消费者行为可验，不冒称生产检测器已完成零约束拒绝。分类、误报/漏检/延迟、净收益继续NOT_EVALUABLE。

## 3. 唯一主线与旁支交接

| 分类 | 责任与验收 |
|---|---|
| 主线 | S1唯一共享集成、S2实际宿主：复用上一轮实际MM-LINS FAST-LIO＋PGO两节点输入面，实交测量修复→前端状态map重处理→PGO后继接回/E2，或具体文件/函数首断点＋最小解除及实际认领；本轮无新主线实现/运行 |
| 必须先做 | 所选host的真实input/config/source、恢复状态时间/map依赖/完整后继归宿；不把T2标签收口或完整四宿主表列成原生接线前置 |
| 可并行 | S3现一层旧档资格修正＋18零约束/三层/精确deadline已验组件复用；真实校准/独立标签继续既有有限范围；S2既有run2身份/输出/实际脚本与上一轮比较纠正，未交不假称已解除 |
| 集中延期 | 一般旧meta/§172措辞对齐、FAST-LIVO2新构建/适配/实验、ASan/大根因矩阵；旧手调仍停、科学门不降 |

四宿主需求分别验收；已有派生前端workspace成功不代原版实现或测量修复净收益，也不放行FAST-LIVO2。后继交付须逐项**PASS/FAIL/BLOCKED/NOT_APPLICABLE＋命令/原件＋影响/下一动作**，保NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE/UNKNOWN与完整失败/缺项人口。S3分层实交已确认，S1集成已见；新原生接线与S2实际认领未交，不能用“已通知”替代。权限/用户授权从实际来源核，不由开发/代理转述升级，不绕拒绝。

A1/A11来源资格与A3/B3研究可解释性仅局部，A4/A5/A6/A9/A10/B2/B4/B11没有新整链证据，不重评全表总分。四Cron单owner/08:53如实报告不延期、不新增Codex前置；中文review现分支SSH白名单发布，不算法/main merge/历史重写/私人/开发日报/凭据。
