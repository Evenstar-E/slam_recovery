# fafbd0c：受控两次拒绝回滚有报告，触发帧与撤销参考接线遗漏

2026-11-10，main `fafbd0cbfb21e4456b8c187494638b778a0d3466`，比较4b47249。新增受控触发与runner标签代码/测试及同实例两次拒绝接口报告；actual新版host patch/raw run_summary/receipt/log仍未归档。先读适用AGENTS、A/B标准和REVIEW第十部分、复用历史，4既有Cron不复制、peer无repair-3e，私人handoff保护。本机只正常小控制/静态核，不修算法、不跑ROS/原bag、不调参。

## 主线增量：两次拒绝接口已尝试，不是实际修复完整完成

开发run `fl_native_20261110T112059Z_3361446`报告wall104.6s、detection off、host_poses、wait2、声明14.6/42s，实际14.678/42.022s开段、17.882/44.830s决定；两次Mode3拒绝，hold/restore各2次、resume1次，E1决定后至E2有216帧摄入、节点地图增长，终态第二段WAIT未关闭。接受**受控E1拒绝回滚→恢复消费→第二次触发/拒绝回滚**的实质机制探索报告；不再说第二次恢复接口从未尝试。实际宿主原件仍缺，不冒成本机原生验收。

本次没有接纳后的实际修复测量重处理/原生修复写回，E2之后亦没有完成释放及尾段持续链。因此标题“恢复链走完”只能限定两次拒绝接口，不触发用户所要求**完整实际修复写回→接回→E2**的完成通知，不提升B4/B11。声明测试时刻不当自动检测成绩；前段自动链BLOCKED保留，不能据此全停原生开发。触发时刻按首个配对帧而非bag开头计算，实际bag基准须原件说明，不因几十毫秒差强求逐值一致。

## 1. scripted触发登记了帧，但漏候选跟踪与空间撤销同步

新on_pair scripted分支调用trigger/register、open_episode后立即return，没有调用普通尾部的_track_episode，也没有普通报警分支的node._sync_spatial_map_with_trusted_poses。本机源绑定actual node/loop，detection off、一个合法已提升key7在t=.5s、next provisional key8@1.5s、受控触发@1.5s/onset减margin后撤key7：

- trigger key0已登记pending（raw refs[0,7,8]），episode确生成，但episode.frames=[]；下一隔离输入只跟踪key1，候选全集漏报警当帧。**不是manager丢帧**，它仍pending；最低触发开episode后复用_track_episode保存当前帧，与正常报警入口一致。
- manager trusted为空，node._kf_map_points却仍含已撤key7/get_trusted_map_points仍100点；下一隔离来帧也不清。拒绝evaluate亦不会同步（只在accepted时同步），所以不是只延迟一瞬的统计。**FAIL_LOCAL：已撤云仍可进入NIS/候选参考**，最低复用现_sync_spatial_map_with_trusted_poses在受控触发回滚后同步，不建新图/参考系统。解除条件是revoked key不留在节点参考，合法存活key保留。

`python -B -W ignore docs/review_20261110_fafbd0c/run_checks.py` exit0，小控制正常反例见local_checks.json；非真实host污染/性能试验。旧unresolved provisional泄漏、step_frame旧decision/旧rearm释放新段、ack及accepted写回缺陷未变，本轮不重测，沿已发最低正常任务。

## 2. 等待起点解释：持续来帧不重置计时，晚设原因仍UNKNOWN

接受S1否定“t_end每帧推进使wait计时每帧重置”：register只改t_end，wait_started在进入WAIT时取一次值。本机复用manager无候选等待，连续.5/1/1.5s来帧不改wait_started，2.005s关闭，PASS_LOCAL。它不证明真实run晚设起点的原因，也不把真实报告13.1s延迟叫timer算法故障。

日报给事件wait_started约290.02、决定约278.88、closed-start约2.005；原raw行未交、数字精度不同，不能独立重构因果。决定记录ts与validate实际读取t_end并非同一固定时刻，代码供应该可能性；是否线程推进/decision记录过早需要actual小窗日志。本机不新起远端任务，S1沿已声明现入口三处最小诊断在下一实质窗口核t_end/decision/wait_started/close，不加通用锁或时钟框架、不再调wait。README旧持续重置解释已被日报否定，集中注明失效，不为文字重跑宿主。

## 3. summary正确区分未触发，receipt仍只按声明标签

summary按fired==declared数给CONTROLLED_INTERFACE_TEST，否则CONTROLLED_TRIGGERS_NOT_FIRED，范围改进接受。但runner receipt.launch.run_mode仍仅看SCRIPTED字符串是否非空。实际source表达式控制声明42s且0次fired：summary NOT_FIRED，receipt CONTROLLED_INTERFACE_TEST，**FAIL_LOCAL标签不一致**；不是本次两次都fired的实际报告反例。最低receipt保留requested mode并从已有summary取actual mode/触发记录，不写新收据框架；声明而未触发不能提升受控执行证书。

新test_scripted_trigger导入依pytest的旧test模块，本机未安装pytest/未执行该开发suite；本机用实际node控制替代，不伪称全套通过。`bash -n slam_recovery/ros/run_native_loop.sh` exit0，仅语法未执行runner。runner脚本正当控制预算不授额外清理/推送权限。

## 下一单一主线/自检

S1最小接上受控触发的帧跟踪与空间撤销同步，复用旧正常归属/释放/失败动作任务；S2按原900s预算保留同次已有host patch/run_summary/receipt/log与实际动作/原scan-group身份，推进实际修复测量驱动原生重估/内部地图写回→接回→第二事件和尾段，或具体首断点。若先两次拒绝机制，声明范围与最终修复链分开，不强行调门接纳。S3门研究独立、旧参数停、生产gate不改，不把所有研究/日志项作前置。

开发自检分PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令/原件：受控触发时刻/候选输入/已撤参考、native动作结果/等待起点/E2释放尾段、actual修复来源/质量。当前PASS_LOCAL为受控开段/连续WAIT不重置/语法；FAIL_LOCAL为候选trigger帧遗漏/已撤空间参考残留/未触发mode不一致；BLOCKED为actual宿主原件及实际修复完整链；NOT_APPLICABLE为本机ROS/原bag/开发suite/参数/完整A/B重评分。A9/A10有受控负机制报告推进，A5/A7/A8/B2有具体正常范围缺口，B4/B11未通过，不给新完整总分。完整原生恢复首次真正完成仍及时单独报告，目前未到。

前push携带rm-rf OUT被拒未解除，本轮只本地提交，不重试/换工具/peer代推，remote review仍3965299，不称开发收到。私人handoff不提交/不公开，未删运行原件。
