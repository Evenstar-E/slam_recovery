# 088906a审阅：两宿主实际负尝试已交，矩阵继续向其余两项推进

- 读者：用户、开发主会话S1、执行S2与独立复核者。
- 目标 `088906ae7cda17fb50b32580323a1008c542e3b1`，基线2ef0169，取证2026-11-12 12:05–12:08 UTC+8。现SSH fetch成功；review分支在tracked无改动时fast-forward到目标，私人handoff仍untracked且未覆盖，不合main。
- 规则/任务owner已核：20min/2h/daily属repair-f3，无旧活owner；用户要求先跑非LIVO四宿主，忽略stop.md、原参数仍停。生产算法与阈值本增量未改。

## 1. 本轮主线：真实执行推进，恢复成功未证明

S1交LIO-SAM连续260s及ORB-SLAM3完整351.65s运行记录，两个都失败，负结果保留。此前两宿主第二事件任务NOT_STARTED/原因UNKNOWN的缺口由具体执行尝试部分解除，不再说没有运行。

这是**已执行的原生观察负尝试**，不是成功恢复，也不是已经独立验证两次物理故障。slam_recovery接线两项均NOT_IMPLEMENTED，不要求先适配才能跑原生机制。主线仍先非FAST-LIVO2四宿主，不回LIVO、不等门研究。

## 2. 本机读回结果

[结果](local_readback.json)、[复现reader](check_records.py)。实际inline `python -I`只读目标Git CSV/log并自行计算，exit0；未执行开发归档脚本、ROS、bag、host、算法或测试。包装reader未另外重跑。

### LIO-SAM：输出未恢复，不称进程死亡

从trajectory.csv复算1120行，路径44574.557m、最大单步535.019m、最大断流3.201s，与已归档主要window字段一致：E1观察窗96对、最大0.571m且无>1m跳跃；E2窗55对、26次>1m跳跃/9次>0.5s断流；尾段240对、86次大步，最大526.630m。支持轨迹发散并持续到尾段的负结果，不是合法GT ATE或恢复率；仍有输出，README“宿主未存活”应写“轨迹未恢复/输出不可用”，不据坏轨迹推断进程死掉。

### ORB-SLAM3：完整原log支持初始化/收尾失败

原orb.log直接核80次New Map/80个mnFirstFrameId、385次Not enough motion、43次bad imu reset。末尾Map0 has0KFs、exit=139，支持初始化不稳定与收尾崩溃负结果，不定位算法/输入/退出根因。times.txt未归档，4/6/3窗口计数仍DEVELOPER_REPORTED，不能称本机精确复算通过；无需为这条表述再运行宿主，补已有times即可。

## 3. 两个最小评价边界，不升级成重跑矩阵

1. **声明时点与事件定义**：两declaration.txt明确“运行开始后、分析之前”，README却写“运行前落盘”。记录应按前者，不能包装预运行冻结；仅有观察窗不是独立物理故障定义。LIO E1窗正常、首次失效在其后约130s；ORB在E1前已反复重建，不能按这次run声称“E1恢复成功后E2再次失败”。最低用已有输入/日志说明实际故障/恢复证据；没有就写两观察窗覆盖的负尝试，第二独立事件/成功接回未证，保留本run不追成功。
2. **时间与执行复现**：LIO windows.py以首输出stamp为t0，而declaration称bag起点；缺bag起点绑定时当前数字应叫“首输出相对窗”，不能直接套物理事件bag时间。ORB按frame→times映射但缺times。两个run.sh仍只列远端/tmp路径，未归档；LIO receipt是JSON后附checksum行，整体非单JSON，且缺实际binary/config哈希。最低归档已有runner、实际时间索引/输入身份及明确时钟；不要求新框架/安装/全异常单测或复现宿主才能继续矩阵。

以上限制的是**两事件恢复/因果结论和独立复现**，不抹去两项真实执行与明确负结果；不能把补齐它们变成MM-LINS/FAST-LIO2开跑前置。没有证据不强行归因信息不可恢复、模型坏、IMU配置错或某阈值不够。

## 4. 当前四宿主矩阵与下一唯一交付

| 宿主 | 当前可核状态 | 下一动作/责任 |
|---|---|---|
| LIO-SAM | S1真实原生运行负尝试，CSV负结果本机复算；第二物理事件恢复未证 | 保留FAIL，已有原件/时钟说明并行补，不追成功重跑 |
| ORB-SLAM3 | S1真实完整运行负尝试，rawlog失败可核；稳定E1恢复/E2响应未证 | 保留FAIL/exit139，现times和runner旁支补，不扩自动新算法 |
| MM-LINS | §65报告S2发起campus12运行，尚无新结果原件 | S2沿预算交此次结果或实际失败断点；运行中是开发快照非本机实时确认 |
| FAST-LIO2 | §65 NOT_STARTED，现前端共享source/binary | S2交实际启动/结果或具体原因；SHARED_EXECUTION不是第二次独立运行，不隐去尚缺 |

**下一单一主线：收齐非LIVO批次余下MM-LINS、FAST-LIO2实际E1→持续输入→E2/尾段结果或命令级具体BLOCKED。** S1集成、S2执行回执；S3门旁支/参数停不变。两已跑宿主的原生机制层与slam_recovery层分开；若E1前未稳定/事件未发生如实FAIL/未验证，不要求成功恢复才能交付，不用计数强充闭环。

开发自检按适用项PASS/FAIL/BLOCKED/NOT_APPLICABLE，附实际命令/run/source/config/input、事件/观察窗定义、原stamp与时钟、E1/E2行为、尾段/缺输出/退出/成本原件。未做就NOT_STARTED并真实原因，不能NOT_APPLICABLE藏任务。新运行已有但source/参考/事件不足处UNAVAILABLE；不降冻结门、不猜根因、不追同值。

## 5. A/B与发布

A2/A12执行与负结果可核性局部推进，A9/A10覆盖观察窗不等完整二次恢复，B7宿主失败范围认识增加；B4实际修复收益/B11完整修复在线链仍未闭合。局部证据不新全表评分。

本轮实质新运行保存本目录并追加历史/协作，旧结果不改写。用户已授权提交，前push阻断已通过保留旧输出的最小修改解除，1f1527b发布且由main0e23548接收。沿当前独立review分支提交/SSH推送，不合main、不删实验资产，不发布private handoff。远端收到新审阅需后续回执，不把推送当采用/执行确认。
