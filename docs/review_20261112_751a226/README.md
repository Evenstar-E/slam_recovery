# 751a226审阅：既有LIVO受控两事件原件可核，四宿主优先任务不变

- 读者：用户、开发主会话S1、宿主执行S2及独立复核者。
- 取证：2026-11-12 11:05:51 SSH fetch成功，目标 `751a226ce2ffad3df5d01cce5d81a4ffc1b23835`，基线3dec39a。本地review HEAD6e959e9，未merge/checkout目标，私人handoff保护。
- AGENTS/A-B标准/REVIEW§10已核；用户直接指令优先、忽略stop.md。现20min/2h/daily归repair-f3，无旧owner/新后台代理，不双写。

## 1. 先报当前主线状态

**先跑非FAST-LIVO2四宿主各一次第二事件**仍是最新主线，[明确执行任务](../NON_FASTLIVO2_SECOND_EVENT_TASK_20261112.md)覆盖旧单宿主优先。此增量没有MM-LINS/FAST-LIO2/LIO-SAM/ORB-SLAM3本批新执行回执，当前接收/开跑UNCONFIRMED，不从缺提交断言远端无人执行。

本批发布的是FAST-LIVO2 run `fl_native_20261112T024337Z_4166038`既有结果；main提交10:50–10:52早于用户10:57本地明确纠正的交接记录。保存并接受其真实局部成果，不拿它充四宿主交付，不据此建议下一趟LIVO或要求先修完LIVO。这里审阅已有归档，不新增宿主实验。

## 2. 可核的受控接纳/接回/E2局部成果

两次只读 `python -I` inline命令成功核目标Git blob哈希、receipt/summary/candidates/events及少量host日志、复算时间人口；25/25一致。[结果摘要](archive_checks.json)及复现reader[check_archive.py](check_archive.py)，reader包装相同操作未另重跑。未执行归档脚本、原bag、host、算法或新测试。

receipt与driver源SHA18d92a03…绑定bbe逻辑，宿主binary0d7e23de…与旧两接纳run一致；内部身份一致不是独立源到binary构建或bag字节验证。

| 项 | E1 | E2 |
|---|---|---|
| 真实触发stamp | 1627785276215170145，run内kf146 | 1627785308048271418，kf422 |
| 准入 | Mode2 accepted，23commit、62candidate-deferred | Mode3拒绝 |
| 关闭时unresolved | 80 | 132 |
| 原生动作 | hold→reprocess→set_state→resume均OK | hold→restore→resume均OK |
| 宿主日志 | :17550真实重放316group，17876vox/337719点 | :34930 restore #2，37335→36511vox |
| release | rearm，不是commit_closed | rearm |
| 实际修复apply | 0 | 0 |

driver counts hold2/resume2/restore1/reprocess1、34snapshot、failures0；host内部restore #1为reprocess恢复起点，不冒第二条driver restore。终态HEALTHY、无开放段，原件无double free匹配（不由此宣布旧crash已修）。

按frame_diagnostics原stamp复算：`E1触发≤ts<E2触发`276帧；`E1 close<ts<E2 trigger`209帧（文档210应说明含close端点）；`E2 trigger≤ts`122帧；`E2 close<ts`仍28帧，末kf543。接受同run原生接回后第二事件和尾段继续的受控事实。不同run的kf编号不同，不用“同kf”代同stamp。

## 3. 未验收边界，不新增LIVO必修矩阵

- 输入host_poses、detection off，两个绝对stamp直接trigger，是CONTROLLED_INTERFACE_TEST，非自动检测成绩。
- host ack及log `repair_received/applied=0`：重放是原始扫描，候选仅通过set_state，不能叫实际测量修复重建内部地图，不能发用户actual整链首次完成声明。
- E1 cp1627785275080903168比隔离起点晚2.865733s；E2 cp1627785308590588416比起点晚4.542317s、比trigger晚0.542317s。和此前晚checkpoint同类，OK restore不证明完整隔离贡献撤净；维持旧A4/B2边界，不重跑旧反例。
- manager/driver/hostpatch本轮无源码差异，旧FAIL后依赖推进、旧尾/deferred写回、旧close释放新段不关闭、不新扩测试。确认性实际修复需最低解除，但**不能成为其余四宿主原生E2运行的统一前置**。
- 仓库“用户保持协议”的文字不是本会话直接用户授权；只记开发采用partial范围。合法拒绝有价值，不要求两次接纳，不调门追成功。

## 4. 交接与局部A/B变化

A6/A9/A10受控原始重放→接回→第二事件原件部分推进；A4/A8/B2可信状态/准入来源仍有限，B4实际修复收益/B11自动实际修复整链未闭合；不全表升分、不报告恢复成功率。

**下一单一主线仍四宿主第二事件批次**：S1确认真实owner/执行安排，两个主线会话复用MM-LINS、FAST-LIO2、LIO-SAM、ORB既有环境，各一次实际E1→持续输入→E2/尾段；明确原生自身恢复与slam_recovery实际修复、共享FAST-LIO前端身份。每项交PASS/FAIL/BLOCKED或NOT_STARTED真实原因、实际命令/source/input/run/事件stamp/原件/预算与退出，未知不猜不能跑，不拿LIVO未完成一律延期。不要求通用checkpoint/RPC/全部防御实现，不代跑本机。S3研究旁支和旧参数暂停不变。

已有LIVO结果归档/小计数口径作为旁支集中处理，**不启动新LIVO验证**。历史成果不删除；已启动具体运行原预算安全收尾，随后转向四宿主。完成actual修复整链时仍另即时报告，不混受控接口。

## 5. 发布

本轮有实质原件，白名单本地保存并追加历史/协作；未改算法/脚本/阈值、不合main、不删资产、private不stage/公开。push权限拒绝未解除，未重试/换工具/peer/Artifact外发绕过，不称S1收到本次或四宿主已开跑。
