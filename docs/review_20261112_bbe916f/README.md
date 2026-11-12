# bbe916f增量审阅：成功路径串行化局部解除，失败仍继续写回

- 读者：用户、开发主会话S1、宿主执行S2、门研究S3及独立复核者。
- 取证：2026-11-12 10:25:47–10:28:19 UTC+8，现有SSH fetch成功。
- 比较 `70f68fbc3450569677659e8220d34fa2e3abaa4b`→`bbe916f948d7d8652783757844b0294592bf7c46`；本地独立review分支HEAD `6f3971a82528c754bbf3b2b5a556e3bcd971f07e`，没有merge/checkout目标。
- AGENTS、A/B标准与REVIEW第十部分已核；按用户指令忽略stop.md。20min/2h/daily三任务属repair-f3，无旧repair-3e可见owner，不新建自动化；唯一private untracked handoff保护。

## 1. 主线结论：部分工程推进，不等实际修复整链完成

本轮新增受控绝对stamp锚点（55750fc合入10688d5）、状态命令串行化（bbe916f）及开发接纳run报告。接受普通成功分支不再把reprocess覆盖成set_state/resume的局部解除；不把代码提交、164测试报告或门accepted计作实际原生修复完成。

开发文档新报告 `fl_native_20261112T020634Z_4148249`：受控绝对戳触发kf132，Mode2 accepted；32帧133–164 committed，71帧95–132及165–179 deferred；host末hold0，地图更新219/0/448；reprocess日志0、restores0、driver events停hold，并出现收尾double free。这是**DEVELOPER_REPORTED**，不能当本机宿主测量。目标树 `git ls-tree -r --name-only bbe916f -- docs/review_20261112_accepted_chain`为空，其引用原件未发布在该目标，因此本机不能独立复核这些计数、partial人口或double free原因；不猜根因、不据缺原件否定开发确有运行。

98c8b2e的“尚无新宿主运行”是较早时点记录；bbe后续文档已有上述新run报告，不能沿用本轮初查文字说全天没有run。该报告明确发生在串行化修复前；串行化后宿主是否重跑UNCONFIRMED。

## 2. 本机限定核验：明确目标源码，不冒充本地旧版本

[run_checks.py](run_checks.py)直接从目标Git blob在内存加载manager、driver/client及选定checkpoint测试，其他package依赖经差异/工作树检查未变；未改生产源码。driver blob `aed58debb07723e64909e25a03097c4a0d4df101`，SHA256 `18d92a032835dbfaff8593987bca9c6d5928882d33da876cb1549970646ea225`。完整身份与结果见[local_checks.json](local_checks.json)。

实际命令：

```text
python -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_bbe916f/run_checks.py
```

首次exit1：目标test_scripted_trigger导入test_recovery_node依赖pytest，本机没有pytest。未安装、未shim、未改production迎合环境。最低改审阅控制：实际节点/目标trigger核绝对时间锚；重运行exit0。

| 检查 | 状态 | 真实范围 |
|---|---|---|
| 排队命令未发送前不被快照期限误判 | PASS_LOCAL，1项unittest，0.010s | 目标test_a_queued_command_is_not_timed_out_before_it_is_sent |
| 绝对stamp触发 | PASS_LOCAL | 实际目标trigger+实际OnlineRecoveryTransactionNode：1299999999ns不触发、1300000000ns触发并登记key3；非自动检测/host |
| 普通成功串行 | PASS_LOCAL | 实际文件客户端，受控OK ack顺序reprocess→set_state→resume；received alone不推进、队列wall发送前None |
| reprocess失败后的依赖 | FAIL_REPRODUCED_LOCAL | 实际目标driver/client配模拟完整准入报告，见§3 |
| 新受控接纳run原件 | UNAVAILABLE_IN_TARGET | 文档已报告，引用目录未随目标发布 |
| actual修复→原生重估/地图→接回/E2 | NOT_VERIFIED | 未新运行ROS/native/bag，不拿受控准入或旧双拒绝代替 |

多命令fakehost tests未运行：Windows rename到已有cmd.done限制继承，确定性文件ack控制验证同一实际发送顺序，不改host/生产代码。没有全suite、算法/调参/大矩阵。code-review技能此次因其cwd为D:/REPAIR而非嵌套仓库返回blocked，未提供发现；本报告只依上列实际diff和控制，不伪称该技能审阅通过。

## 3. 正常阻断：序列化不等按成功推进依赖

目标CheckpointClient.poll():730–738无论OK或FAIL都pop并 `_flush_outbox()`；_write_file失败后:641亦flush。正常accepted决定仍:1369–1376先安排reprocess及旧 `ep.frames[-1][2]` set_state，生命周期:1425–1427再安排resume。

本机同上一轮完整准入控制：旧host x10/20，修复x1/2，trusted两key接纳。新代码确实保住物理cmd=reprocess，outbox `[set_state,resume]`，因此**旧命令覆盖成功分支局部关闭**。但提供 `FAIL reprocess replay_failed` 后，poll自动发送set_state，其payload仍旧x20而非修复尾x2；之后OK set_state即可发送resume。产品行为为FAIL；脚本exit0只表示核到此预期反例。

**最低解除（S1/S2，A8/B2/A10）**：沿现outbox明确这条恢复依赖链，只在reprocess实际applied成功后推进后继；FAIL/未知停止或清除该链的依赖写回/release，不能把“不再覆盖”当“重放成功”。状态来源须来自同逻辑时刻实际准入/原生重估，不用旧尾/deferred尾灌状态替代修复测量→deskew/估计/内部地图。无需通用RPC/异常框架，不扩故障矩阵。

## 4. 未变旧断点保留，不重复造测试

本轮manager、deployed_host.diff、门研究均无差异；_apply_lifecycle仍无active段身份判断，set_state旧尾来源未改。上一[70核验](../review_20261112_70f68fb/README.md)的旧close释放新active和E2 checkpoint比隔离起点晚约3s原件断点不关闭、不重复跑。

snapshot可supersede/timeout后继续不等宿主已完成/取消，快照会覆盖宿主唯一checkpoint；契约“只读、不影响决策”和“同名歧义不再出现”不能一般成立。保持上一真实时间归属任务，不另开通用token/并发矩阵。最低checkpoint与trusted/隔离边界一致、release绑定对应段；不支持的回溯明确拒绝。

开发新run指出回滚95–132不在driver候选133起的人口，全提交close不可达、靠wait/rearm释放。此具体人口暂无公开原件可核；旧A5原生/driver人口支持范围必须明确，不能叫已完整接纳修复。优先发布已经存在的原件并在下一实际运行核每帧归宿，不为协议文字单独再跑宿主。

## 5. A/B局部变化与主线/旁支分工

- **A8/A10、B2**：成功命令串行局部PASS；FAIL后依赖推进与旧状态来源仍FAIL。不是新的全表升档。
- **A1/A12**：受控absolute stamp实现局部核验，不能保证缺帧时仍同scan、不充自动检测性能或实时性。
- **A4/A9**：旧可信checkpoint时间与release段归属未修，沿70证据。
- **A5/A6/B4/B11**：新partial接纳run仅开发报告，修复重放未执行；完整原生修复/净收益未闭合，不发布新总分或成功率。

**下一唯一主线（S1/S2）**：复用串行化和已有原生组件，最低解除成功依赖、状态/人口、可信检查点/段释放归属；在既有900s预算交一次actual测量修复支配原生重估/内部地图→接回真实输入→E2/尾段，或具体宿主文件/函数首断点。不等门研究完成；首次真实完成立即单报。

**可并行旁支**：S2归档已存在accepted run原件，保留double free负结果/未定位，不推断修复质量或状态等价；S3本轮无增量，沿62f294旧纠正范围收口A/B逻辑/人口，小文档问题集中处理、不新开矩阵。原参数任务继续暂停、不改冻结门、不自动部署未选模型。

开发下一交付先逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE，附实际命令和原件：成功/失败依赖推进、可信逻辑时刻state/map、候选/准入/deferred/frame归宿、修复点真实进入原生估计/地图、同run reentry/E2尾段与成本、独立质量和负结果；缺合法GT/原件标UNAVAILABLE。当前远端工作树/进程及本地意见接收UNCONFIRMED。

## 6. 发布

本轮实质增量仅保存本目录并追加历史/协作变化，旧报告/数字不改。不修算法、不合main、不删实验资产；私人handoff不stage/提交/提供Codex/公开。

此前push权限拒绝未解除，本轮只本地白名单提交，不重试受限推送、不换工具/peer/Artifact外发绕过，不称开发已收到。实际提交结果另报。
