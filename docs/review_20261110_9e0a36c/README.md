# 9e0a36c：段级ICP实际求解已跑，不把低信息量归因为阈值错误

2026-11-10。目标 `9e0a36c98b30d7244e5d5208bcb3dfc23edc9a05`，比较5f59f47，三笔增量。已读AGENTS、评分表及REVIEW§10，核本会话三自动任务/Windows旧owner不运行；忽略stop.md，保护私人handoff。不改算法/门、不代跑宿主、不调参。

**接受实际候选求解尝试：新段级ICP代码与原receipt/summary/candidate已交，不再只是实现或日报。**这仍是宿主输出→Python候选求解→gate拒绝的旁路流程；没有宿主checkpoint恢复/实际测量重处理/内部状态地图写回、接回或E2。失败运行有研究价值，不算恢复成功。

## 1. 真实运行原件与本机验证

run `fl_native_20261110T051744Z_3059939`，receipt/summary/candidate IDs同；room输入/host binary/library/config SHA沿前次，固定Git driver SHA `e5bc98f0…`与receipt一致。receipt仅绑定driver，未绑定全部repair/core依赖，本机按现source与收据声明范围核验，不声称已独立重跑。实际rate1、drain5、sigma=.884、启动load51.26/51.30/99.11、nproc128。

- 599scan/800pose、584配对、15未配scan/216未配pose，365检测可用/219未检测摄入、backlog116；墙钟77.587s、RSS460796kB，callback error0。
- 25候选/25配对改善，现单侧Wilson复算下界 `.9023308107`与记录一致；paired status PASSED、info_after **4.470129<冻结tau_info25**、holdout .024494、最终Mode3。
- 1次段ICP，归档耗时 **11.827734s**、150000合并点→2000求解点、19039参考点、20iterations/ITERATION_LIMIT；修正幅度.459185m/3.728982°。接受已执行且可完成，不称实时、轨迹更准或地图已修好。2000实际抽样原件补齐，前次6000日志误读已由开发纠正，不再重开。
- 1episode/1决定/0接纳/E2零、最终WAITING。决定后254消费不是接回。t_decision比episode deadline晚 **.535017s**，记录的是启动决策的输入时间，未包含11.8s求解完成；不能用它算端到端恢复延迟。

本机直接调用改动ICP的16个既有test函数（含3个新segment例）：16PASS、0FAIL、13.634s，非pytest。正常actual wrapper控制返回4候选，状态ITERATION_LIMIT；没有本机ROS/真实bag运行。复用命令和原测试/fixture入口见[run_checks.py](run_checks.py)，本轮先执行同等inline命令再保存runner；原档案未改。[local_checks.json](local_checks.json)给版本/数据与范围。

## 2. 当前失败不能自动变成调tau_info的理由

开发从host候选约4.66和段ICP约4.47均小于25，推断“阈值与当前量级不在同一尺度”，现证据不支持该因果。**两个候选没过同一个门，也可能是信息确实不足或评价producer定义有问题，不证明门错。**不能为了G≠Q、Mode2或B10比较可见而重新选科学门。

最低工作不是再造逐帧FIM日志/参数分布矩阵：先复用已有公式/归档，核info_before/after/25的基、单位、归一化和既有依据；实际尺度不一致才修producer或明确提出新科学协议，保留旧负结果。任何新门须按独立证据、确认前冻结的既有要求处理，不拿这些已看过的拒绝样本拟出能过的阈值。**不以阈值讨论挡宿主恢复/生命周期接口**，拒绝分支亦可接续到有限终态和E2。

当前report“Insufficient verified info”是泛化reason；info4.47足以不接纳，不证明posterior cov等其余条件通过。A7 world ridge和service变长窗沿上一版本已验范围保留，本轮不重跑、不重开正确transport/时间包络。新summary原cleared主张尚无实际producerfix解除。

## 3. 段级模型和证据边界：只声明范围，不扩框架

- 逐帧独立SE(3)变为整段一个左乘ΔT，即使常数仍相同，**模型自由度、合并拟合人口、参考中心已变**，应标新探索候选，不称原§9实验完全不变。一次段刚体不能表达段内相对漂移；25帧与旧22帧、不同source/load/drain不能直接拼成同候选公平增益。
- 拟合使用整个episode各scan合并后的抽样点，参考为trusted map；后续paired/每5帧holdout又评价这些scan对同一trusted参考的残差。参考未由候选自建是正确的，但**可信历史≠与求解独立的评价数据**。当前没有预留未参与拟合的帧/点人口，不能把25/25和Wilson当独立候选质量或门有效性确认；它们是当前共享拟合条件下的一致性读数。现有独立离线GT/proxy规则后继复用，缺则UNKNOWN，不新增统计/标签框架挡探索。
- 20次ITERATION_LIMIT可提供探索候选，但一次未收敛不能证明1e-6不可达；此前53/399离线帧曾CONVERGED。残差floor因果仍未证，沿076bd意见收窄即可，不再新密度扫描。
- 新detail只保存ΔT的平移/旋转幅度，未保留完整矩阵、所有repaired poses和成员时戳；当前candidate第一trigger矩阵仍是原host pose。幅度不能重建候选/独立标签，不当全候选已可复算。沿已有B10来源要求在下一实际交付引用已有完整产物即可，不另建格式/为补字段重跑。

### 正常失败语义：求解失败仍被封装成ICP候选

新 `_icp_candidate()`无论res.status都执行 `{k: delta @ inits[k]}`。`reregister_segment()`在REFERENCE_TOO_SMALL/NO_FRAMES等返回identity；结果是未求解也把旧host poses返回并贴ICP来源，丢失上一逐帧分支“失败不替换回host poses”的语义。

本机复用上一实际loop setup，4个有scan/init帧，trusted参考仅10点：solver status **REFERENCE_TOO_SMALL**、scan1600/reference10，wrapper仍返回keys1/2/3/4且poses全等原host。不是恶意输入或人为异常，是参考不足的正常拒绝路径。本例未声称gate误接纳。

最低修正：只有已有成功候选状态CONVERGED/ITERATION_LIMIT应用ΔT；其余status保持无修复候选并记录原failure/pending，沿旧未替换语义，不添加fallback/新门/防御矩阵。同一小例和现成功控制即可验，具体改动由开发侧负责。

## 4. 下一唯一主线与分工

**S1集成/S2宿主：**这次可完成的段ICP探索代码直接复用，最低失败语义修随接线处理；现在优先实际宿主checkpoint/测量重处理/internal state-map writeback和真实Mode3后续候选/有限终态/重武装，交一次恢复→接回→E2或第一宿主文件/函数断点及最低实现。别把11.8s优化、tau_info文件或候选粒度迭代当接口前置。

**S3必要数学并行：**旧actual producer固定基正则最小修；info尺度核现公式/依据不盲扫、不调门，不重造已通过组件。确认性独立标签/同候选四策略由既有工具后继核，不挡接口准备。Codex/KITTI后继，当前远端checkout/未提交/正在运行及最新意见接收仍需直接回报。

首要阻塞仍工程恢复接口/生命周期；候选求解实际尝试有实证进展，算法净收益/信息可恢复上限未测，阈值不匹配原因未证。局部映射A6候选/A12成本、A7评价与B11部分流程，不升完整A10/B11或重新评分。

自检PASS：原件run/source/配对及Wilson算术、16既有函数/新segment控制、实际wrapper正常与参考不足反例、改动Python AST/runner语法。FAIL：失败fit仍产host poses；反例退出0表示复现，不是生产fix通过。BLOCKED：已知pytest不装/不重复、原bag/独立质量与全source依赖未本机核；NOT_APPLICABLE：ROS/旧不变core回归/全表评分。下一按REVIEW§10.12给PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令/source/host/input/config、预算/完整人口/原产物。失败保留、不调门制造Mode2，不另交仅“收到/改措辞”周期。
