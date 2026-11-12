# b581a7c：等待诊断接入，迟决策的快照归因仍待时间重叠证据

2026-11-10，main `b581a7c155d8d4ca18b3590eb4332d86e68afb66`，比较fafbd0c。新增manager默认关闭诊断及开发小窗口报告，driver/runner/实际host patch未变。已读AGENTS、A/B标准、REVIEW第十部分并复用历史；4既有Cron未复制、peer无repair-3e、私人handoff保护。本机只诊断开关小控制与报告算术，不修算法、不跑ROS/原bag、不调参数。

## 接受的局部推进

开发run `fl_native_20261110T112727Z_3365609`首次报告validate入口t_end与wait_started赋值同为1627785296625585318，支持“进入WAIT时读取段尾、不是连续来帧重置计时”的解释。默认关闭SLAM_RECOVERY_WAITDIAG符合最小诊断尺度，manager等待语义未修改；不能当作迟决策已修或完整原生链完成。

本机`python -B -W ignore docs/review_20261110_b581a7c/run_checks.py` exit0：默认无诊断行，开启4行，两种情况连续来帧后都在2.005s关闭至ABORTED。PASS_LOCAL仅当前正常管理器语义/日志开关，非真实宿主延迟根因复现。沿fafbd0c已通过的计时范围复用，不跑全suite或新实验矩阵。

## 快照可能阻塞，但当前摘录不足以确认该18.55s迟决策因果

源码确有tick→_send→collect的长等待（默认30s）在service里、决策之前，**可能**阻塞决策；旧f2命令/短poll丢pending缺陷仍未改。但报告给第一snapshot执行wall1794310079.327、validate wall1794310114.969131，间隔**35.642131s**；bag t_end35.63、deadline17.08，差18.55s。不能把启动前第一snapshot的16.42s等待直接当作已到期决策被阻塞的同一区间。

若这些数来自同一1×连续播放，且t_end接近validate wall对应bag时刻，那么隐含bag起点约wall1794310079.339，deadline到达约1794310096.419，反而晚于第一ack约17.09s。这只是条件性算术，不证明实际bag起点、队列迟滞或其他快照不存在；它要求原件来区分，不能替代日志实测。当前报告缺rosbag实际开始、首次pending_decision、service进入/退出、快照cmd/ack与deadline到达时段的一致时间线，快照因果仍DEVELOPER_REPORTED/UNKNOWN，不确认全部迟决策由它造成。manager注释把本次诊断的16s阻塞写成旧112059Z来源，亦需run身份核定，不改旧证据。

最低S2先复用该次已有cmd/ack/host/recovery日志，指出**哪条等待区间覆盖了实际deadline后service**；不为归因文字再跑宿主。确有阻塞时沿原通道最小使滚动快照不阻塞决策，并复用single in-flight/短poll保持pending/匹配消费ack任务。仅把timeout改0.5仍是阻塞，不能叫不阻塞；主循环本就2Hz，新的≤0.5s指标若声明须实测，不当先验已达。若“第一ack前不发快照”字面指任何命令且启动无其他命令，必须明确哪条已有ready/应答启动它，避免快照永远不开；不要求新RPC或握手框架。driver本轮没有修改，也没有修后运行，不能说已落实。

## 主线与下一最低交付

完整实际修复测量→原生重估/内部地图写回→接回→E2及尾段仍未完成。受控两次拒绝接口报告保留为局部机制进展，自动检测BLOCKED与原生接口继续开发分开；不以136测试/诊断输出当恢复成果。S1等待起点保持段尾语义可按现source声明，旧trigger帧/撤销空间参考、unresolved provisional、旧decision/rearm、ack及accepted写回正常缺口复用已有反例，未改不重测。S2随下一原预算实质交付保存actual host patch/原件，最小解除已证正常阻塞后推进实际链或给第一断点。S3研究独立，旧sigma/κ/floor任务暂停，生产gate不改。

开发自检须PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令原件，分别给诊断语义、实际阻塞区间、驱动修后决策时序、真实修复来源及E2/尾段。当前PASS_LOCAL为诊断开关/时刻算术；BLOCKED为快照因果原件、驱动修后、actual完整链；NOT_APPLICABLE为ROS/原bag/136全suite/新调参/完整A/B重评分。主线结果未新增成功恢复，只工程诊断支持推进；A4/A6/A9/A10不因这次日志升完整项，B2/B4/B6/B11未闭合，不发布新总分。首次真实整链完成仍及时单独报，目前未到。

前push携带rm-rf OUT被拒未解除，记录仅本地提交，未重试/换工具/peer代推；remote review仍3965299，不称开发收到。私人handoff未提交/公开，未删运行证据。
