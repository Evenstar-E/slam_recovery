# 4b47249：五段负运行有推进，拒绝循环不等完整机械恢复链

2026-11-10，main `4b472495bc38c134965ab74f6f9433d4c3674a70`，比较9ee52dd。仅两份开发运行报告新增，无driver/node/manager/actual宿主patch变化。已读适用AGENTS、A/B标准、REVIEW第十部分并复用历史；核4既有Cron/peer无repair-3e，不双写，私人handoff保护。仅静态核/报告时间差算术，无ROS/原bag/修复算法/调参，旧测试不重跑。

## 主线增量与不接受的提升

新run `fl_native_20261110T110616Z_3349738`报告wall154.3s、wiring all_ok、receipt OK、5 candidate detail rows；5段均拒绝/51key deferred并close/rearm，原生hold/restore/resume各5次ack，终态HEALTHY无遗留段。接受新负运行/episode接线可继续推进的开发观察，不能再说替换episode只停在无运行验证；但原件未归档，不能叫本机独立验收。

真实E2窗42–52s的87帧全部UNAVAILABLE、没有进入检测器；第5次rearm后支持未恢复。**完整实际修复→原生重估/内部地图写回→接回→E2未完成。**拒绝/restore循环不包含准入修复测量重处理或成功修复写回，host_poses依旧不是算法修复；wiring OK只是当前接线检查，不是科学/机械完整认证。五段触发中13.82s仅略早于注入，其余23.35/30.43在首注入之后，缺独立自然退化/正常标签，不能把所有5段先验都定为“健康假警报”，不能给泛化误报率。

## 源码/算术限定：只纠正本次过强解释

1. 真实检测支持默认是**1m/60%**（node `_frame_has_reference_support`），3m是NIS选node_map邻域的半径。两者不能合成“3m/60%支持条件”；沿1b8已复现prev_scan且AVAILABLE的小例，不重测。地图增长和prev_scan计数不能单独定位当前pose与云错位，缺87帧actual support fraction/stamp/pose/参考支持原件则原因UNKNOWN。
2. 表中decision→close是**2.14/3.15/5.67/4.68/5.60s**，非每段恰2秒。期限是等待起点后的下界、来帧驱动求值，起点仍segment.t_end且事件可能迟到；本轮没有证据证明timer故障或越限，也不能称恰2秒。最低归档已有wait_started/decision/closed stamp与求值输入；不另建计时系统、不调budget。
3. 五次恢复各回到旧stamp，可以报告各次恢复跨度；把5×约2秒相加称“累计改变轨迹约10秒/同区域反复重走”缺实际中间消费/重放与状态时间支持。跳过历史输入还是重放同区域必须看actual日志。特征下降/残差升高是开发观察，不证明唯一的地图-位姿不一致根因；不从这些汇总直接选择新地图维持/rearm支持门架构。
4. 2次snapshot ack_timeout需保留。当前cp单文件命令/ack归属缺陷未改，本轮未给超时原件；不能由“restore密集时段”确认并发撞车或宣称完全不影响决策。复用f2/9ee已发布最低命令与释放归属任务，不增通用并发框架。

**旧正常阻断未解除**：9ee控制的新段hold→旧rearm resume、step_frame旧decision、unresolved provisional再晋升、accepted旧host尾/partial/失败继续set_state源码均未变化。新5段表不能关闭这些正常反例，也不重复旧测试。S1先最低使旧事件不释放新段/保持旧帧归属与正常命令结果，S2继续选定宿主有限流程，不让所有旁支变永久前置。

## 下一单一主线：受控两事件接口方向可保留，和自动链分开

开发提出声明测试触发+14.6/+42s的CONTROLLED_INTERFACE_TEST，符合已有宿主交接允许先检机制的范围，不是新自动检测成绩/新模型选择。可按既有900s预算验证同实例恢复→接回→第二次恢复并交失败；必须说明实际执行restore还是带修复测量reprocess、内部状态/地图变更、同stamp后续输入及E2/尾段，不能仅发布两个触发消息、人工set_state或统计两个ack就完成。

自动检测链保持BLOCKED，但不据此暂停用户已恢复的全部原生接口开发；旧sigma/κ/floor任务停，S3研究独立。涉及新的支持恢复/隔离保图模型只有具体证据后报告方案供用户选，不由本机或仓库措辞自动采用。实际修复收益也不靠受控触发获证，最终真实修复写回→接回→E2目标不变。

自检：PASS_LOCAL仅版本范围/支持默认/表中时间差算术（`python -I` Decimal，exit0）；DEVELOPER_REPORTED为5拒绝循环及成本；BLOCKED为actual源码/原件、帧/命令释放归属、真实修复与E2，原因不足标UNKNOWN；NOT_APPLICABLE为本机ROS/原bag/旧回归重跑/新参数实验/完整A/B重评分。下次开发按PASS/FAIL/BLOCKED/NOT_APPLICABLE附命令原件，分开接口、检测、修复和收益，不用wiring OK提升恢复PASS。A9/A10局部负探索推进，A8/B2/B4/B6/B11完整条件未通过，不给新完整总分。首次真实整链完成仍及时单独汇报，目前未到。

前push携带rm-rf OUT被拒限制未解除，记录只本地提交，未重试/换工具/peer代推；remote review仍3965299，不称开发已收到，未删原件/提交私人handoff。
