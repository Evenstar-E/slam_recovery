# 主线/旁支验收 a5e93c8：T1/T2确定性控制

范围f3e9b65..a5e93c8，3笔、15文件。完整读四patch、预注册与两结果，四receipt逐项核input/binary/config/rate；未远端重编译或真实bag运行。补丁和JSON为归档证据，不声称本机复現测量。

## 主线推进接受

T1通过NO_MP opt-in与两loop guard关闭并行，四receipt串行binary hash6e0a3e57、相同O输入f8b26ddf、主config一致、sources unchanged。T1与T2均rate1.0/drain40，与先前2x2真实receipt一致；不能以早期交接泛泛.5说明误判当前对照rate改变。T2 adds taskset0-7，归档mode各GOOD/BAD，支持所执行控制未消除不稳定。

不接受“neither reduction nor scheduling is the seed”排他根因结论。关闭一个机制仍有其他机制可独立造成失败，它可排除“该控制足以使结果稳定”的假设，不能证明原并行归约/调度完全不贡献。T2同时改变affinity/nice/负载是组合资源控制，不隔离各自效应；n=2结果只能有限描述。允许下一阶段sync/group与IMU窗口分开，不直接同时改两者。

## P2：首位姿字段与收据不符

room02_T1_results.first_stamps均1627643759.5540829(onset)，receipt.output.first_stamp_sec却r1=1627643742.844585、r2=1627643741.5119612。它可能是评分区/共同区首pose而非真正first output，但原字段及commit解释错误。1.13cm/1.9mm需提供评价脚本、匹配/健康gauge范围、实际common ID/hash；本轮仅简短JSON无生成器，不认为可追溯early-state定位已完成。以已有输出重算/命名即可，不重跑host。

## 下一主线（有界止损）

先提交T3a“只固定measurement grouping”可运行patch/trace：保持当前串行binary基线之外的config/rate/prefix/input不变，记录每组实际scan/image/IMU IDs及初始化样本。若固定group重复仍不同，再预注册T3b只固定IMU init绝对样本窗。必须给变化前后关键state/相对运动与固定服务总体，不能仅good/bad标签。

这是宿主可重复性保障与状态估计研究支撑，不是新地图修复模型收益。若再两轮正确单因素控制仍不稳，按用户工程复审/机制止损规则暂停无假设排障，审适配假设、同步校准或换可控宿主；不要无限“剩下的只有X”排除法。

## 旁支分工

工程并行补评测生成脚本、runtime compile宏/启动日志hash、first_output与first_scored字段；旧binary/revision/patch身份分离。NO_MP startup omp_max128不说明guard仍parallel，只代表runtime默认上限；应校验实际loop guard/日志，保留真实框架限定。现代patch只有opt-in，无需本机改算法。

开发側按§10.12先PASS/FAIL/BLOCKED/NA自检，报告主线真实控制及否定的具体假设、旁支最小修复。当前hall条件正、room负/不稳定均保留；未获跨序列稳定/在线部署/独立GT地图证明。今晚日报记T1/T2控制未消除不稳定，不定根因。
