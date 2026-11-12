# 8ca5b41：异步快照局部接受，真实单在途与迟到ack仍未闭合

2026-11-10，main `8ca5b41f9e1aabfd75d21a9e9adfdbfd78883356`，比较b581a7c。新driver异步snapshot/status probe、命令名ack校验、决策offset与node分段计时；开发另报告小窗延迟和一次partial MODE2。先读AGENTS、A/B标准、REVIEW第十部分并复用历史；4既有Cron未复制、peer无repair-3e。私人handoff保护，只正常小控制/静态核，不修算法、不跑ROS/原bag、不调门。

## 主线进展与接受范围

源码tick写入后返回、poll无等待、未匹配ack保留pending，service改用poll，确实解除旧同步滚动snapshot阻塞及短50ms poll即丢pending的**该入口范围**；不能再把它列成完全未修。先status探针再快照也有实际启动入口，无需新握手框架。两项选定不依fakehost多次rename的测试PASS（0.056s），实际文件小控制status→host_ready→snapshot，以及错误命令名不消费/正确名poll通过。命令名字校验解除旧“restore ack也当hold成功”的一般异名错配范围，真实单在途/同名迟到归属仍见下。

开发报告决策入口相对deadline18.5→0.400s、14次snapshot无超时；评估内部约18s，validate进入时段尾已推进；这些是开发小窗读数，raw receipt/log/actual宿主patch未新增，不算本机因果复现或完整成本验收。保留新优化后观察，不反复起快照诊断实验；旧启动阻塞归因仍不自动获得同版时间重叠证明。

另一小窗MODE2提交23key、169deferred属于**部分准入机制报告**，非独立修复质量，更非已完成原生接回/E2。host_poses来源、accepted写旧host尾/失败仍set_state/partial写未准入尾source均未修，不能由这次接纳自动关闭。完整实际修复测量→原生重估/内部地图写回→接回→E2及尾段仍未完成。

## 1. 只有tick守单在途，普通hold仍覆盖探针/快照

本机无host正常文件控制：tick发status（未消费），正常callback开段hold，物理cmd变hold、pending=[status,hold]。写正确`OK hold` ack后poll只查队首status，返回None且两者都仍pending。**FAIL_REPRODUCED_LOCAL**：旧status被覆盖、已完成hold无法按归属收取。不是Windows重复rename问题，也不需假设恶意输入；是本轮新增启动探针与既有正常callback的交接。tick的pending guard不覆盖_write/hold/_send。

最低S1/S2在现入口保证所有正常命令同一个真实in-flight，保留必要hold顺序和真正已执行ack归属；不靠_pending list增加长度伪装硬盘单cmd队列，不造RPC/分布式框架。解除用此一个旧通道正常例即可，未应答status不能被hold覆盖，或明示合法撤销/新命令所有权；不能用正确hold ack吞队首错误。

## 2. snapshot超时退出软件队列不等宿主操作已结束

新expire_pending丢队首snapshot后可重新tick发同名snapshot；_read_ack_for只匹配第二段cmd名、不消费ack。本机明确标**合成迟到控制**：第一snapshot软件timeout、新snapshot已写但未执行，旧第一条`OK snapshot first-command-done`到达，poll把它记成新snapshot成功。它不证明报告14次快照存在错归属，只证明计数/状态单靠命令名不具一般同次保证。

最低沿真实single in-flight范围：超时后保留宿主完成/未知归属，不在同一次尚未确认结束时发同名命令并认旧ack成功；消费已匹配应答一次。可用现文件通道最小标记/顺序，不强推新协议框架。新poll保pending与异名检查有价值，但不能称全部旧命令安全问题已闭合。

## 3. 分段计时是累计读数，offset尚非实际等待起点

node的_mark打印从evaluate入口起**累计elapsed**，不是每段独立耗时；相邻marker差才是增量。gate_and_commit在node空间同步/voxel_journal.commit_generation之前，全部决策还含之前候选/外推及之后native reprocess/set_state/restore等待；不能将最后marker当完整decision成本。默认env关闭/小常数time采样无生产门语义变化，接受有限定位方向，不跑新成本矩阵。

driver `wait_start_offset_s`在调用evaluate**之前**采样seg.t_end，评估期间仍来帧，manager真实wait_started在validate内取较晚段尾。本次已报告18s内部推进，恰不能用入口offset0.400s宣称实际wait起点只晚0.400s。最低沿已有marker把入口、manager赋值、返回时刻分别记清；用已运行下一实质窗口分段原件找主要成本，不先重定义等待窗口/调门或新建并发估计器。

## 下一单一主线与自检

S1/S2先现通道最小命令归属/必要帧安全修，按新marker沿已有有限小窗确认主要成本，再交实际修复驱动内部状态/地图写回→接回→E2及尾段或原900s预算第一断点。受控partial接纳/host_poses和算法修复收益分开，未获独立模型选择不改支持/保图策略。S3研究独立、旧sigma/κ/floor调参停、生产门不改；日志格式/性能细分集中旁支，不所有完备才允许原生探索。旧trigger输入/撤销参考、unresolved/旧decision-rearm/accepted写回source未改，不重复旧测试。

自检命令：`python -B -W ignore docs/review_20261110_8ca5b41/run_checks.py` exit0，PASS_LOCAL为2测试与非阻塞poll/探针/异名检查；FAIL_LOCAL为status覆盖队首阻塞与同名迟到ack错归；BLOCKED为实际partial原生动作/成本分段原件/真实修复与E2；NOT_APPLICABLE为ROS/原bag/旧全suite/算法调参/完整A/B重评分。exit0表示预期观察已核，不是产品全部通过。开发下次PASS/FAIL/BLOCKED/NOT_APPLICABLE附命令与原件，别用入口延迟/23提交数/marker数量代完整主线成果。A9/A10工程接线局部推进，A8/B2正常命令风险保持、B4/B11未闭合，不升完整总分。首次真实整链完成仍及时单独报，目前未到。

前push携带rm-rf OUT被拒未解除，记录仅本地提交，不重试/换工具/peer代推；remote review仍3965299，不称开发已收到。私人handoff未提交/公开，未删运行原件。
