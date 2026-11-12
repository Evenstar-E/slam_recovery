# f2bbbb5：hold接线与候选输入归档有增量，原生两事件仍未交

2026-11-10，main固定`f2bbbb54faac950845e6543233cff4465e695060`，比较已核adff0b0；跳过merge/旧审阅。新增082cba6测试发现、7d76c60宿主hold报告/诊断入口、d90c597 Python hold/rearm接线、f2bbbb5候选输入sidecar/测试发现。协议和既有自动任务归属已核，旧owner PID无进程，不双写；私人handoff未提交。生产门、manager/node准入源码未改，本机不修算法、不跑ROS/原bag、不调参。

## 主线增量与原件范围

**实际Python源码**新增开段异步hold、main-thread collect、manager rearm→resume及native action记录，不是纯文字。可接受为A9/A10接线组件推进，不能当原生接回/E2完成。runner已接wait参数是上一轮已关闭范围，不重开。

**宿主侧新增是开发测量报告＋诊断脚本**：README给hold后265706 points不增，处理22/72/128帧；restore到242541后继续30帧仍保持，resume后增长。若原件成立，这是地图写入隔离局部证据；估计状态并未被冻结，报告主动保留轨迹不连续。它不证明状态/map同stamp或实际修复。

关键缺口：本版本checkpoint目录仍仅README/旧diff/.cpp/.h，**实际运行的新hold patch、完整ack/log/result没有提交**。adff与f2的host diff完全相同，sha256仍`f5efce7160e45933f84b23c365f08b9a51798aeb9c201c4e48a5ba026e2c2f21`，旧patch不识别hold/resume。不能拿新版README替代新部署源码关闭停写图/无输入poll/重放cloud问题，也不能断言报告运行造假。最低保存已有工作区diff和已有log/result/binary/config绑定，不重跑矩阵。

新smoke_hold等待循环50×wait_s×.02s正确；但收到任意非空ack包括FAIL也return0、调用处不传播失败、不比较地图关系。它是打印式诊断，不是“四项全PASS”自动证书。可提供已有完整ack/log人工或算术自检；只有宣称退出码验收时才最低修OK/命令匹配和失败传播，无需另建测试框架。

## 1. 正常命令通道：事件队列没有保护一格文件/确认归属

`CheckpointClient._write`每次覆盖同一个cmd，事件放_pending；collect直接pop最老项，任何非空ack只看startswithOK、不校验command、不消费ack。事件队列不等实际命令队列。当前hold由callback写、snapshot/restore/reprocess由主线程写，是真实多入口接线，不是额外假设并发。

本机确定性控制（不跑线程/host）：write hold→write restore，物理cmd只剩restore；放一个`OK restore done`，连续两次collect分别记hold成功、restore成功，holds=1/restores=1。一个执行确认可被消费两次，未执行hold也能记成功。

**另一个直接贴合service的控制**：hold后collect(.05)无ack时立刻把pending丢掉、判失败；随后write restore并收到迟到`OK hold done`，restore计成功。服务轮询50ms不是host已有30s动作期限；报告snapshot ack .086s已显示50ms不能当通用终态保证，但不由此推每次hold都会迟到。

最低解除：沿现文件通道保持单个真实in-flight，后续正常命令不能覆盖它；短轮询未到原动作期限保留pending，实际ack校验命令并消费一次。不新增通用RPC/分布式事务框架，不放大期限追PASS。复用两条控制和正常匹配ack正例验即可。是否native执行成功必须与gate接纳分开。

## 2. 完整接纳不是rearm事件：解除hold路径未交

实际manager完整Mode2提交→HEALTHY，无rearm lifecycle event；partial仍WAIT。driver只在_open_episode发hold、decide接纳发reprocess，只有_apply_lifecycle看到rearm才resume。模拟完整accepted report/HEALTHY/noevents正常编排：命令仅hold→reprocess，没有resume。

**结论限定**：新host patch缺失，不能排除远端reprocess内部自行解除hold，但当前发布接口和Python源码未给这一契约；因此完整接纳后地图持续写入恢复是BLOCKED，不宣称实测永久hold。最低在真实宿主接口约定中明确成功重处理后的解除时点，或在完整成功接纳路径显式resume；不能对partial/deferred仍隔离的段无条件放写。提供一次完整接纳后正常新帧内部地图增长/失败ack不伪成功证据，不用调门造候选，不扩状态机。

旧SUSPECT覆盖trusted快照、backdated可信边界、三生命周期正常缺陷相关source未改，沿既有最小任务保留，不重跑旧suite。无输入poll/重放cloud修未见新patch，沿旧入口核，不重复扩台账。

## 3. 候选sidecar保存输入全集，尚非实际info_after评分集

新增`candidate_detail_record`保留ep.frames的keys/timestamps及repairer输入poses，作为**候选输入归档**有价值；不应撤掉或用假字段代替缺失。但node随后独立support过滤commit_keys，再从其每holdout_stride选scorable_holdout生成fims_after，而driver写的是过滤前全集。它不是注释声称的“gate scored/info_after actual frame set”。

本机实际node正常控制：7帧候选、key4远离参考；6帧有独立支持，stride5只让key1/7进入info_after；sidecar写1…7且仍包含key4。没有修改门/支持规则/producer。若从此sidecar把全部7帧重新平均FIM，就是新人口同名量，恰好违反此提交想解决的问题。

最低在node现评价处返回/记录**实际verified/holdout帧ID及对应pose、固定anchor基**，driver sidecar区分输入/评分/待定，而非从report.committed（拒绝为空）猜评分集。完整新producer比较还需原scan与独立reference身份；本sidecar本来没保存P/Λ，不说它已解除旧四条covBLOCKED，也不为补旧字段重跑所有宿主。既有主线自然产物顺手归档，研究不挡原生接线。

## 4. 测试发现修正接受，但本机范围有限

082/d90改checkpoint测试为TestCase，f2给recovery_node模块load_tests wrapper，能修此前unittest不收集的组织问题。它不等新增33项研究成果。当前本机pytest未安装，而test_recovery_node仍importpytest，相关完整发现无法在此环境执行；不install/shim、不把0项称通过。

本机选5项实跑PASS（.214s）：silent-host/disabled-client两项及candidate_detail三个TestCase。未跑Windows fake-host重复rename（平台行为不同）、未跑开发报告90/全suite、ROS/原bag。正常控制退出0意味着错误归属/缺接线/人口不一致已复现，**不是fix PASS**；固定sourcepin已核。

## 下一唯一主线与分工

- **S1集成/manager**：最小单in-flight/匹配ack/短poll不终结，完整接纳释放与partial隔离区别；旧正常生命周期和trustedstamp任务直接复用。候选评分ID顺手在现评价处归档，不为它停主线。
- **S2宿主**：先保存本次真正运行hold patch及已有原件；沿现budget接入实际修复测量重处理/内部状态地图写回/同时间线接回/E2，并关闭无组控制/公开旧cloud正常问题。不用“已声明不连续”代替接回验收，不再修FAST-LIVO2所有故障；原预算内接口失败按已选宿主规则重新比较。
- **S3专用门研究**：独立继续原已发最低纠正，不因新sidecar认为旧A/B/C完整候选/独立质量已获证；参数手调仍停、生产未选方法不部署，不要求主线重跑旧研究人口。
- **S4本机**：归档核源码/小正常控制，不代跑host/改算法。下一实质交付给PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令和同host/source/input/config原件、完整帧归属/尾段/成本，不交测试数替代实际修复链。

本轮A9/A10组件接线与A12发现入口有局部进展；A4可信stamp、A6真实修复、A7同人口重算、A8原生公开提交/动作一致性、B2/B11未闭合，不升完整A/B总分。主要工程接线/实际部署证据，算法净收益/参数上限UNKNOWN。完整写回→接回→第二事件未交，首次真实完成仍单独向用户汇报。

复现：`python -B -W ignore docs/review_20261110_f2bbbb5/run_checks.py`。原门不改，临时目录只放本机模拟命令，原测量/失败数据未删除。
