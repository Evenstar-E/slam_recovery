# 95b0d97：原生动作超时是实际负结果，调度起点计时需最小纠正

2026-11-10，固定main `95b0d979de2bdd2ea03ac0b28ac870895151a0e7`，比较9862ad5。新增受控两事件负运行报告和decide计时，actual宿主新patch未交。适用AGENTS、A/B标准、REVIEW第十部分及4既有Cron/旧owner已核，不双写，私人handoff保护。本机不修算法、不跑ROS/原bag、不调门，只一个正常计时控制。

## 主线结果

开发run `fl_native_20261110T114748Z_3383280`报告wall128.8s、两次脚本触发/Mode3拒绝、216帧旧run之外本run355帧消费；段0restore ack_timeout30s，段1hold ack_timeout，第二段未在结束前关闭。保留**原生动作未确认、受控链未完成**的负结果，不因wiring all_ok说恢复成功。355帧继续消费不是成功接回证明，actual修复测量/重估写回/E2尾段仍未验收；不发整链完成通知。

本轮只计时字段代码变化，旧真实single in-flight、迟到ack、trigger候选遗漏/撤销参考残留、旧帧晋升/decision-rearm释放及accepted写回source未修，不重复旧测试。失败已给具体运行断点，按原预算保存原件/最小修回主线，不继续调sigma/门或扩矩阵。

## 1. scheduler_delay_s不是首次到期后的排队延迟

_track_episode在每个ts>=deadline帧都重新设置_pending_decision_wall；decide用进入wall减这个最后值。因此连续正常来帧会不断缩短已排队时间。源绑定本机控制：首次到期wall100，后续帧wall124，假设125进入decision，公式记1s而首次到期后25s。**FAIL_LOCAL**仅计时语义，不是报告24.126s真实延迟复现，不证明计时器或恢复状态机失败。

最低首次提出该episode pending时只记一次起点，新episode重置；保存message deadline与实际wall/monotonic资格起点，不把最后到帧wall当首次资格。不改历史数字，旧24.126s只能按该字段实际定义保留，不当精确调度排队量。post_eval仍在native动作之前结束，后续restore30s阻塞未包含，不能称完整决定后段0.001s。

命令`python -B -W ignore docs/review_20261110_95b0d97/run_checks.py`，exit0；合成actual episode帧跟踪，未ROS/native/原bag。结果见local_checks.json。最低补此正常例即可，不追大计时矩阵。

## 2. 原生超时根因与独立线程提案的边界

报告“restore之后LIO变慢→同循环轮询饿死→该restore ack超时”缺实际host时序。在旧公开patch中，poll调用restore、checkpointStatus后立即写ack，然后才返回继续下一LIO；后续慢帧不能直接先于该restore ack。新actual部署source未交，所以不把旧顺序自动当最新宿主反证，但必须归档当次cmd发送、宿主读取/应用起止、ack写入和driver读取，再确认等的是哪条命令。ack_timeout只证明driver没有确认，不证明操作未应用；单cmd队列旧归属缺陷仍可解释错误等待，不能先排除。

若某个慢帧发生在读取命令之前，会推迟应用；独立线程可早记received，却不能让仍在同主循环应用的restore自动更快。**received不等applied**，这点提案方向合理；不由此宣布独立线程必解链路。仅atomic flag也不自动保证命令payload/单在途归属，需要现通道明确当前命令所有权，不要求新RPC/一般并发框架。默认先核已有日志和实际source，定位读取迟、执行慢、ack迟或归属错中的一个具体断点。

仓库“S1唯一授权改独立线程”是开发协调提案，不是本会话用户新的模型/架构选择；本机不实现或代授新宿主架构。现有授权下的最小控制接线可由开发协调并如实交source/received-applied原件；若确需更大设计决定按用户规则先报告选择。不要因一个未闭合根因把原生主线换成无限控制线程研究，也不把修后必须秒级/设计上限当已有科学门。

## 下一唯一交付与自检

S1/S2复用现通道的最低命令/动作归属修与actual原件，先把本次原生动作超时定位到具体入口，再按原900s预算交实际修复测量→原生重估/内部地图写回→接回→E2及尾段，或首断点。受控拒绝/host_poses机制与真实修复/收益分开；S3门研究并行，旧sigma/κ/floor任务继续暂停，生产门不改。计时字段集中最小修，不成为重跑一套旁支实验的理由。

自检：PASS_LOCAL为source绑定/正常计时控制成功复现；FAIL_LOCAL为首次资格wall被覆盖；DEVELOPER_REPORTED为原生ack超时及成本；BLOCKED为actual宿主cmd/应用/ack身份、完整修复E2，根因不足UNKNOWN；NOT_APPLICABLE为本机ROS/原bag/线程实现/全suite/调参/完整A/B重评分。开发下次逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令原件，receipt/wiring不代动作applied或整链通过。A10/B11有实际负探索，A8/B2安全及原生恢复仍待验收，不升完整总分。

前push携带rm-rf OUT被拒未解除，本轮仅本地提交，未重试/换工具/peer代推；remote review仍3965299，不称开发收到。私人handoff未提交/公开，未删运行原件。首次真实整链完成仍及时单独报，目前未到。
