# d35671f：受控两次拒绝链完成有报告，接纳后的异步依赖顺序仍FAIL

2026-11-10，固定main `d35671f97a54f611fef70318b7f0534d2011d470`，比较95b0d97。新增所有native动作异步化、received/applied记录、service pending检查及受控两段完成报告。必读规则/评分/REVIEW第十部分与历史已核，4既有Cron无复制、peer无repair-3e；私人handoff保护。本机不修算法、不跑ROS/原bag、不调门。

## 主线变化：及时报告局部完成，和用户实际修复目标分开

开发run `fl_native_20261110T115717Z_3390402`报告103.1s、两段Mode3拒绝、hold→restore→resume各2次、368帧中间消费、两段关闭/重武装、终态HEALTHY。接受这是**首次报告受控两次拒绝回滚及释放完整走完**，较此前E2动作超时/第二段未释放有实质进展，已即时向用户说明。不抹去这项机制成果，也不要求随机读数逐值相同。

但本次非实际修复测量接纳/重估/地图写回，没有独立质量及完整尾段原件；host_poses与脚本触发不证明自动检测或算法修复。**用户要求的实际修复写回→接回→第二事件整链仍未验收完成。**无需等检测解决才继续原生机制，亦不能把拒绝接口完成当实际修复成功。

actual新host独立线程源码/received-applied日志与run_summary/receipt仍未归档，公开host diff仍gitblob fd15b982（旧590版）。只能接受开发完成报告，不称本机独立native PASS。宿主四条received/applied读数是开发观察；客户端ack_wall含轮询收取时刻，不等host实际应用时刻，最低沿已有host行明确二者。日报“snapshot×30全部OK”与README“30中7次超时”口径冲突，需分别列写入/received/applied/timeout/superseded；不删失败、不要因命名superseded当真实宿主操作已取消，不为文字另跑实验。

撤回本趟“restore后LIO一定变慢”合理，但新run前后1–18ms不能证明旧run30s超时原因；负载/同步仍只假设。沿已有原件记录不扩归因矩阵，旧根因不作架构有效性证明。

## 本机局部通过

`python -B -W ignore docs/review_20261110_d35671f/run_checks.py` exit0。3项选定测试PASS（0.233s）：received先于applied、silent host保pending、snapshot不阻塞。实际client文件控制仅RECEIVED restore时pending仍在且没有ok；正确applied ack到达才成功，**PASS_LOCAL**。所有动作_send现在写后返回，旧30s阻塞等待这一调用范围已解除；新的service pending门可避免普通service决策在已知命令未确认时启动，范围接受。

这些不是全suite/独立宿主线程验收。silent动作pending需在既有预算结果中如实保留；不能在finish直接决定后立即总结时把未收取applied当成功，按真实动作结果报告即可，不增加通用重试框架。

## 接纳正常路径的新异步顺序缺陷

driver decide在accepted时连续`cp.reprocess()`→`cp.set_state(ep.frames[-1][2])`，没有等待前者applied；pending检查只在进入service决策前，不在该决定的依赖动作之间。实际文件通道控制复用930正常修复fixture：旧host x10/20、修复x1/2，模拟partial gate提交key1、key2 deferred。调用actual decide/client后：

- pending=[reprocess,set_state]，物理cmd已经是set_state；reprocess尚未执行/applied即被覆盖。
- native payload x20（旧host未准入尾），trusted修复x1；旧来源/partial问题仍在。
- 后续供给`FAIL reprocess replay_failed`时，它虽可被poll记失败，但set_state早已发送。

**FAIL_REPRODUCED_LOCAL**：模拟准入报告隔离正常编排，实际Python/client/file写入，非真实native接纳/污染实测。异步化不能绕过本来必须执行的原生重估，也不能靠立即灌位姿称重处理通过。

最低S1/S2在现通道单真实in-flight下，用已applied成功结果推进依赖动作，失败或未知不发送依赖set_state；使用实际已准入且与replay时刻一致的状态来源，partial尾保持归属。复用既有动作/event对象和最小正常反例，不新建RPC/分布式事务。旧status/hold覆盖、同名迟到ack、旧rearm释放新段、trigger帧/空间参考/unresolved、首次资格wall覆盖仍未改，本轮不重测全部旧例，不能用两段成功报告关闭它们。

## 下一唯一交付与自检

S1/S2最低正常依赖动作/帧/命令归属修后，按原900s预算交**实际修复测量→原生重估/内部地图写回→接回→E2及尾段**或首个具体断点，归档已运行新host patch/已有source-input-config receipt/log/动作applied原件。受控拒绝完整与真实修复、自动检测、收益分别记账；S3独立门研究、旧sigma/κ/floor调参停、生产门不改，非必要日志/重复规则集中旁支。

自检：PASS_LOCAL为3测试/received≠applied；FAIL_LOCAL为accepted异步覆盖及失败前已发set_state；DEVELOPER_REPORTED为两次拒绝机制完整；BLOCKED为actual新host原件、正常依赖顺序与实际修复整链；NOT_APPLICABLE为本机ROS/原bag/全suite/调参/完整A/B重评分。开发下一次PASS/FAIL/BLOCKED/NOT_APPLICABLE附命令原件，分别报actual修复来源、原生重估结果、partial归属、applied、E2/尾段。A9/A10局部机制推进，A8/B2正常写回仍FAIL，B4/B11真实修复条件未闭合，不发布新总分。

首次真实整链完成仍单独及时报告，目前仅报告受控拒绝范围。此前push携带rm-rf OUT被拒未解除，本轮只本地提交，未重试/换工具/peer代推；remote review仍3965299，不称开发收到。私人handoff未提交/公开，未删运行原件。
