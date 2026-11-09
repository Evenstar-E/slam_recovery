# 主线验收 4ee0392：同帧raw/native与实际修复对照

范围2168c32..4ee0392，3笔、7文件。完整读新增217行测量脚本、结果JSON与日报改动；本机语法/计数不变量检查通过。未真实bag重跑，无主算法改动，不重复跑41条主测试。按§10.11/10.12主线与旁支区分。

## 主线：接受明确限定的恢复收益证据

这是主线实质推进，不是审计措辞循环。两臂同400帧、全clean proxy ROI，分别raw扫描+host poses与filtered扫描+native rerun poses；构图/评分复用同流程。归档coverage .603768→.984920，patch unsupported .62510→.09309。新增42227 sampled map points中35999 supported，丢失50234中47790 unsupported；计数逐项一致。可报告单序列、C3存活共同支持、clean proxy上的离线恢复改善，不是只隔离或多写帧的结果。

前轮shared-base Q比较仍有其价值；本轮raw-vs-repaired回答相同采集机会下修复质量，两种比较应共同报告，不能互相替代。支持“实际测量过滤+native重估能修复此注入条件”的窄结论，尚不支持验证准入独立增量、安全保证、全宿主/全传感器或在线checkpoint。

## 主线解释边界（随下一交付集中处理）

1. 400集由C3有pose/filtered observation选出，条件比较正确，但不算预先冻结的独立400输入；冻结总体446缺46必须继续单列，不能宣布全部恢复。图ROI固定与frame survival selection分开。
2. “criterion declared before reading numbers”目前只有同一脚本/提交和结果，没有独立先行协议版本。记录为本轮分析规则；若后续用于止损/泛化，先独立冻结版本与样本。不是否定当前大幅实际差异。
3. 当前predicate只检查新增novel多数supported及added unsupported不高于R；不约束lost good geometry、覆盖、缺帧或成本。示例新增6good/4bad、R unsupported=.9可通过，无论丢掉多少good点。故不是通用“净收益”充分判据。当前归档覆盖与错误组成同时改善，比仅predicate更有说服力；以后预注册联合维度并保持无主观权重也可报告Pareto改善。
4. 100k都是250/frame抽样，point set added/lost为0.5m几何相邻总体而非原point ID编辑数量；称sampled geometric disagreement，不称删除了确切47790个错误原回波。支持来自proxy/局部质量，不是GT。

## 下一轮主线与旁支

| 分类 | 交付 | 验收 |
|---|---|---|
| 主线 | 在一条预先选定独立序列/故障强度确认同帧收益，或在本链上补冻结446服务完整度/健康区代价并定位46缺帧 | 选择一种明确目标，预注册来源/集合与指标，不再调单NIS；本结果作为基线，不改成功标准追数 |
| 可并行旁支 | runtime receipt新运行身份、actual sampled map/source hash、分析规则版本与自检表 | 仅真实输入/评价不合法时阻断；已有输出可继续评价 |
| 延后 | 新大模型、多宿主扩矩阵、论文夸大 | 首个可靠确认/健康代价结果出来再决定 |

开发侧先按标准自检并提供PASS/FAIL/BLOCKED/NA+命令/路径，回答本轮主线交付、旁支分工调整与未完成；不要另发一笔纯确认文字。以有效实验轮次评判模型，不把过去INVALID诊断当失败轮次。

## 日报关系

接受今日开发日报把实际同帧结果置于主线。审阅侧今晚日报会将此记为远端归档离线proxy恢复证据，将通用模型/准入/部署主张保留未证明。没有独立实跑就不写“本机复现”。
