# 5f54a44审阅：双事件尾段推进，触发前检查点不等隔离起点前检查点

读者：用户、开发S1/S2/S3及独立复核者。目标 `5f54a449650e203a1c1d3bba29486a8476fb53ae`，比较已验 `70e3e7cab942839e88727579787c7210012ef5f9`。

## 1. 范围与执行身份

AGENTS、主线评分标准与REVIEW§10已读，未变内容复用；actual三Cron均repair-f3持有，无旧owner双写，按用户忽略stop.md。16:22 SSH fetch成功取得目标，16:29后继fetch因DNS失败，不能宣称目标仍是远端实时最新。review独立分支、不merge main、不改算法/真实宿主/阈值；私人handoff保护。

本轮并行独立核原生新增两run；父会话另核研究总结/论文一致性/选项新增状态分析，未重复代理原件工作。[reader](check_archive.py)及[结果](archive_checks.json)全读后交付；没有执行归档runner或代跑ROS/bag。

两run实际driver为 `b1bce5ef7b3c4258f65371e32b4930f7ca2147ea` / SHA `a7cf030c…`，不是target整driver `4742dbc1…`；新arm/open/service/main四个入口AST相同。receipt宿主库 `9e7d8cdf…` 与v5构建声明一致，input/config/binary沿现bag。其余全package源码及完整state/map等价UNKNOWN，不把driver绑定冒全部实跑源码验证。

## 2. 实际主线成果：每脚本戳arm和更长E2尾段

| 项 | armed `080204Z_228057` | final `080914Z_233068` |
|---|---|---|
| 原件SHA | 新17/17一致 | 新17/17一致 |
| E1测量修复 | 23发布/接收/应用，bias+.40、shift−.40 | 23发布/接收/应用，bias+.45、shift−.45 |
| 原生重放 | 437=124窗口+313suffix；map20154/375577 | 503=124窗口+379suffix；map21578/403642 |
| 写回/接回 | 无set_state，reprocess/resume ACK XYZ同 | 无set_state，reprocess/resume ACK XYZ同 |
| E2 | 实际拒绝/restore；无第二close/resume，最终WAITING/open | 实际拒绝/restore→close→ABORTED rearm→resume，HEALTHY/open=false |
| E2关闭后尾段 | NOT_COMPLETED | 严格后继39paired、4.650639773s |

接受final同实例实际修复→原生重估/内部地图→接回→E2拒绝→尾段执行事实，更长尾段比旧70目标17帧/1.725s有实证推进；不是首次E2，首次实际修复后受控E2已在70审阅即时报告。新armed的尾段不足负结果保留，不用final结果覆盖它。final两次waitclose仍保101/138 unresolved；完整commit_closed→resume未验，partial接纳后仍wait/rearm放写。

host应用stamp是double秒打印，整数发布戳与打印转回ns差0–239ns，唯一一一匹配同一double精度；不称逐ns完全一致，也不据浮点打印误差宣输入错配。两run relay598扫描/59shift，修复23、未修36；suffix使用原输入可能含剩余损坏，不称全损坏窗修复。检测off、两个预声明scripted触发、E2无新注入；独立故障检测性能、地图/轨迹净收益UNKNOWN。

## 3. 首断点仍是可信回退边界，而不是再增加一个武装接口

新功能确实解除旧“cp晚于trigger”这一范围：每个scripted戳排hold/snapshot，scripted关闭rolling，online仍保rolling。**尚未解除“cp晚于quarantine_start”**：

| run/事件 | cp相对trigger | cp相对quarantine_start |
|---|---:|---:|
| 两run E1 | −97ns | +3.999999903s |
| armed E2 | −58ns | +3.999999942s |
| final E2 | −0.067801784s | +3.932198216s |

final E2 cp1627785306303834368、trigger1627785306371636152、quarantine_start1627785302371636152。最小正常反例trigger10s、margin4s、隔离起点6s：arm10s不能撤6–10s已经进入宿主的贡献。**本次E1注入从trigger才开始、E2无新注入，不能反过来断言这4s必有真实污染**；已证的是Python隔离/回溯声明与native checkpoint覆盖不一致，因此不能泛化为可信完整回退、迟到检测保护通过。

最低S1/S2复用现checkpoint/回放，把实际应用检查点绑定到所声明可信回退起点，不晚于quarantine_start；若没有该历史状态，明确拒绝不支持的回溯范围，并保该点后每帧归宿。不是要求在线预知异常，不以给更多未来脚本trigger预置snapshot替代历史保护；不新建通用RPC/全宿主事务框架，不为这个正常时间问题改科学门或把margin调小追通过。

旧collect None/FAIL→suffix未知→set_state分支在该delta未改，70目标已实际控制复现，不重测、不声称在两新run发生。最低成功/UNKNOWN依赖一致保留；候选旧坏云准入与新测量同物理定义亦未解除。新成功非零suffix skip及后缀重放已接受，直接复用不重做。

## 4. 总结、论文与可用性旁支的准确范围

研究文档§13.21/论文一致性页对自注入、检测off、无GT/收益与未完成四策略比较的限定接受；论文未实际改稿，不替用户决定。可写“受控整链执行与39尾帧已完成”，不可因trigger前cp就写“可信完整状态回退全部通过”或删除相关限制。

原件final E2 before实际20.322206/after19.615581、Wilson0（报告/总结引用旧before22.064应更正）；armed E1 after7.286747而非7.3024、E2 Wilson.016685，不把较早run门数字移给新run。superseded报告1实际0，注入60实际59等集中更正，不为文档重跑宿主。

5f新增availability按manager状态分析来自旧544行，无新运行：HEALTHY标签不能用作独立健康真值，trusted_keyframe数量不变不能单独证明参考几何完全冻结；152 HEALTHY+UNAVAILABLE支持“不可用并非隔离独有”，但不唯一确定宿主位姿错误。保持UNKNOWN，不把新统计当方法成功或参数规律。

**最新用户直接授权优先**：[ALI-H v1设计与有限隔离测试](../ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md)已b7ad580推送；它有限更新旧“等待用户选/暂停全部诊断方法研究”的转述，仅允许本方案开发测试、先shadow，不批准生产替换/所有其他选项/重开旧参数。S3唯一研究角色安排既有预算并回实际认领；S1接口单写，S2 native继续，自动审阅并行。此target早于方案发布，不指控其未含新任务即忽略；实际新任务接收UNKNOWN。

## 5. 核验命令、A/B和下一唯一交付

独立代理实际：`python -I D:/REPAIR/slam_recovery_upstream/docs/review_20261112_5f54a44_native/check_archive.py D:/REPAIR/slam_recovery_upstream D:/REPAIR/slam_recovery_upstream/docs/review_20261112_5f54a44_native/archive_checks.json` exit0。manifest全341/341只是完整性检查，历史run未重审；新增run34列示原件。四个target入口小控制PASS：逐戳排序arm、open取消pending在hold前、scripted无rolling、online仍rolling；运行entry AST与target等价，非host C++动态复现。

reader早期schema/人口/浮点戳断言失败，仅修自写reader解释实际结构后最终PASS，不改production/原件。catkin目标laser_mapping Built，整体exit1/vikit CXXABI_1.3.15链接错保留，无本机build/ROS/bag/依赖安装。当前没有完整同版本独立GT/地图质量，不能由日志/测试数升分。

**下一单一native交付**：合法历史可信cp→实际测量/完整native重估→所有输入归宿→接回/后继拒绝或修复尾段，或显式不支持范围；优先收口本轮隔离起点与检查点不一致，配失败UNKNOWN依赖及物理候选同定义，不无限受控单事件/E2移戳追终态。

开发自检逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令/原件/下一动作：run/source/库/输入、实际cp相对隔离边界、修复/未修/后缀人口、applied/catch-up/状态来源、成功失败依赖、E2尾段、独立质量/成本UNKNOWN；未实施/未运行NOT_IMPLEMENTED/NOT_EXECUTED。A2/A6/A10受控后继/尾段局部推进，A4/A8/A9/B2/B4/B11完整条件仍未闭合，不全表升分。仅review增量SSH提交推送，若DNS继续失败如实报告，不换认证/PAT/peer绕权限、不合main/private保护。
