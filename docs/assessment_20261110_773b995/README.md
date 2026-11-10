# 全表复验 2026-11-10

目标固定773b995b9babc9951fbb9672bffe7914b785ecbc；比较昨日标准基线7fc67cf。沿用MAINLINE_PROGRESS_STANDARD_20261109.md 0–3序数阶段分，不修改旧baseline。A轴独立源码/测试复核，B轴逐项核证据；本机41核心+25审计+9结构测试通过，另三事务入口反例实测。没有原生ROS/bag运行；远端receipt/结果属于归档核读，非本机独立实场复现。有限scope含单宿主明确故障，非生产认证。

## 结果

A=16/36（原16，净+0）；B=12/36（原11，净+1）。完成3分工作包A0/12、B0/12，新增完全闭合0。唯一阶段升档B8 1→2，其余23项逐项维持。评分表示证据阶段，不是代码完成百分比、工时或录用概率。

## A原型轴逐项复验

| ID | 原→现 | 核验依据与未闭合 |
|---|---|---|
| A1 输入/point身份 |2→2| exact ns/index/row audit和hash已有；hall旧C3未消费ID新包、所有运行链不统一 |
| A2 原生执行身份 |2→2| archived native receipts存在；缺actual host消费消息/group完整ledger、历史library gaps |
| A3 在线检测 |1→1| node detector调用和局部测试；native试验仍oracle窗，未同链在线事件指标 |
| A4 完整checkpoint |1→1| Python poses/factors/bias/version snapshot；非完整native map/filter/cache/velocity |
| A5 authoritative pending |1→1| 分批retry修复有测试；初始全集/报警帧/后续隔离帧未完整登记，入口反例失败 |
| A6 历史重处理 |2→2| actual过滤+native离线重跑及sidecar map；未在线checkpoint接入，质量/成本不完整 |
| A7 独立准入 |1→1| independent参考/paired测试；before body FIM与after world FIM直接投影，切空间未统一 |
| A8 原子公开提交 |1→1| commit API/局部assert；factor extension异常后poses/factors已公开，version/history未更新 |
| A9 多事件回溯 |1→1| 普通promotion undo；repair未入undo，第二更早onset有修复残留 |
| A10 原生接回持续运行 |1→1| Python路径/BOUND_ONLY；无同进程native提交后继续输入/第二事件运行证据 |
| A11 共同人口同步评价 |2→2| common batch修复、gauge、GT变换/hash；部分scorer各run独立GT支持/非唯一匹配、历史评价来源仍需分开 |
| A12 独立封装/预算 |1→1| runner/config/receipt；私有路径/依赖、缺clean environment复现，成本receipt错身份/峰内存缺 |

A主要证据：core.py、quarantine/manager.py、sim/transaction_manager_node.py及tests/test_commit_evidence_coverage.py；native identity与结果见docs/review_20261109_bbc3dcb/各receipt/MILESTONE。标准要求真实host对应阶段，不能仅Python修复升2/3。

## B论文证据轴逐项复验

| ID | 原→现 | 核验依据与未闭合 |
|---|---|---|
| B1 损害问题/必要性 |2→2| 原生污染/有界proxy/重复失效；检测-污染扩散事件时序同native链未冻结验证 |
| B2 可信保护 |1→1| Python invariance/rollback测试；pending/halfcommit/repair undo反例失败，native故障注入缺 |
| B3 在线检测定位 |1→1| e1 SYNTHETIC、real局部特征；无全部native事件recall/FP小时/迟漏检时延同链 |
| B4 修复净收益 |2→2| hall raw→filtered condition400/446、GT252支持有限正结果；room负/不稳；未全人口独立GT和合法完整成本 |
| B5 验证门增量 |1→1| street拒绝/paired局部测试；sim validity FAILED；无同候选stream条件下有害减少/有益损失完整比较 |
| B6 因果机制 |1→1| 2x2/T1/T2/T3a、gauge描述有进展；run/group不稳、T3a未固定分组，oracle干预因果未唯一分离 |
| B7 正常代价/有害风险 |1→1| hall外窗0/room4.47%以及nearwall hardnegative；无完整错接纳/漏修/拒绝后native持续运行分母 |
| B8 重复/不确定性 |1→2| batch共同12run/323身份修复及runtime receipts，实际native重复暴露条件不稳定；n少、预注册gap、无确认性效应区间/相关性完整处理，不能3 |
| B9 未开发环境边界 |1→1| room最初负确认保留；hall/room已反复参与开发，未冻结方法的新环境 |
| B10 公平完整基线 |0→0| 有raw/repaired和Q探索；无同候选原生/仅隔离/无条件/门控+能力匹配外部baseline完整证据 |
| B11 原生在线链/成本 |0→0| 多离线run、组件timing；无同次检测至接回/积压完整链，不能以runtime smoke升档 |
| B12 冻结独立复现 |0→0| independent实现局部复算，不是独立clean environment发布核心表；依赖/数据不可本机重跑 |

B证据：raw_vs_repaired_results.json（400条件、GT252）、room02_confirmation_results.json（负）、room02_bistability_results.json（native repeats/common323）、room02_T3a_enriched_results.json；e1 provenance SYNTHETIC，sim manifest validity FAILED，p10近墙58/76误删的归档限定。未把代码/doc标题当效果证据。

## 新增实测阻断（本机，不是真实场景错误率）

1. authoritative pending：margin0，healthy keys1/2/3，onset1s/current4s，quarantine raw_frame_refs=[]；仅提交key1、candidate不声明deferred，最终HEALTHY/activeNone、keys2/3不在待处理。已有retry修复正确但只能处理已由candidate建立的pending。
2. atomic publication：repaired_factor_ids iterator先yield999再抛异常，pose42/factor999仍trusted，version0/history0。应先validate/materialize/stage所有状态及空间map，再发布/撤销，不能半commit。
3. repair undo：接受pose42/factor420/bias[1,1,1]，第二onset早于首次修复，三者仍trusted且history无repair撤销。将repair带时间范围纳入undo或明确拒不支持回溯。
4. tangent basis：node before用body scan FIM，after world points FIM，core沿原weak vector直接比较；全局重表达不是同物理信息，需transport/invariance。未宣称本机native verdict flip。
5. cost provenance：hall01_b4_cost_and_gap.json C3 run目录fl_run_20261109T105559Z_2414230，在room02_filtered_receipt.json实际input room02、output res_room02_filtered。hall 122.9s“实测”不可通过；source identity需改为真实hall证据或UNAVAILABLE。不阻止已有map效果分析。

## 卡点统计与交接

技术阻断四组（1初始pending登记、2原子提交、3多事件repair undo、4准入切空间）；完整度关口三组（5原生在线checkpoint到接回、6论文净收益/公平baseline/未开发泛化、7可复现发布与合法预算）。按组计共7，不是24个互相独立bug；成本错收据属于组7保障，不能阻断全部研究。

唯一优先主线：完整状态事务三反例和正两批/两事件闭合，随后一条限定native同进程accept/reject→持续输入→第二事件。切空间transport并行最小必需验证；hash/报告/成本收口旁支集中，不再次围绕mm/单NIS循环。真实影响安全/评价的最小修复先做，非必要工程不要扩大主线阻断。

开发侧§10.12先自检PASS/FAIL/BLOCKED/NA及命令证据，主线/旁支分工与解除条件。无法实际native运行明确未完成，不造结果；同样不因负确认否定全部研究价值。新评分绑定773b995，后续提交不自动继承升级。
