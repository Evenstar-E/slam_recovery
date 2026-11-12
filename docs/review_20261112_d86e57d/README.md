# d86e57d增量核验：受控隔离边界cp解除，拒绝回退后历史归宿仍未闭合

面向：开发S1/S2/S3与独立复核者。固定目标 `d86e57df09c076e531cb2e4edabdc70daac6b668`，比较已验 `fafbaf173b873502d248164adff8cd185dfa0dfc`；2026-11-12 17:45 UTC+8 fetch。AGENTS、A/B标准、REVIEW§10必读未变复用，三Cron实际owner repair-f3，无旧owner双写，用户忽略stop.md优先。保护私人handoff，不合main/改算法/历史/冻结门。

## 1. 本轮实质主线推进：具体时间边界问题可以关闭

新driver scripted武装从trigger改为 `trigger - confirmation_margin`；v6宿主增加最后已处理组时间 `cp_last_processed_lio_`，主循环在stateEstimationAndMapping后更新，snapshot在当前组处理前执行并取这个时间，而非即将处理组的时间。这不是仅改日志数字：快照与capture在隔离起点前状态开始，确认窗口后继组进入现有原生重放。

[目标源码最小控制](run_checks.py)/[结果](local_checks.json)：全部package目标Git bytes加载，1项changed wiring test PASS .013s；trigger10s/margin4s实际排hold/snapshot6s、第二20s排16s，main传真实loop margin，full v5→v6 patch改动核PASS。code-review low无新增可核源码发现。本机没build/运行宿主；C++控制只读full patch，归档actual行为另核。

[隔离原件reader](check_archive.py)/[结果](archive_checks.json)：本轮changed four_host 23/23 SHA一致（17run、5host patch、README）；实际driver `a4aaa58b…`=target/receipt，新库 `ca9126c4…`与v6build声明一致。

| 本次事件 | 实际隔离起点ns | 实际cp ACK戳ns | cp相对隔离起点 |
|---|---:|---:|---:|
| E1 | 1627785272215170145 | 1627785272199251712 | **早15,918,433ns** |
| E2 | 1627785302371636152 | 1627785302359221248 | **早12,414,904ns** |

host.log 5716–5717与34444–34445有真实snapshot/apply，非deferred安排ACK冒已执行。应用当前组晚请求50.641/54.246ms，但复制的是前已处理组；打印double与整数cp差60/28ns，远小于约12–16ms余量，不伪称原ns精确。源码与实跑共同支持**本次受控两事件“cp晚quarantine_start”具体断点解除**；不继续机械保留该旧FAIL。完整缓存/状态字段时间等价仍未全验证，自动检测rolling/onset迟到与跨首次修复回溯未由脚本预置证明。

## 2. 真实修复→原生重估→接回→E2执行接受，限受控范围

新run `fl_native_20261112T092251Z_291996`：

- E1 Mode2接纳23，估测bias .55m（实际声明注入.5m），23发布/收到/应用逐scan及点数匹配，leftover0、无set_state。PointCloud2 wire实际字节未归档，本轮不重测既有布局控制。
- 原生794组=244within+550suffix，span272.265811205–298.692232847，map27805voxels/564227points；397LIO（334有点/63空）+397VIO，不能叫794个非空scan。确认窗口比旧within124多120组，实际一起原生重推，而非仅变cp标签。
- E1 reprocess用时约19.397s，reprocess→resume ACK XYZ差.0533222m，命令时间不同，不当瞬时GT跳变/全部状态等价。
- E1关闭至E2触发严格144paired；E2 Mode3拒绝+实际restore，wait-close→ABORTED rearm→resume；E2关闭后17paired/1.725149155s至末戳1627785320909073830，终HEALTHY/open=false。
- 两段均wait-limit关闭而非完整commit_closed，未解人口128/160保留。59实际shift仅23修复，36未修，其中18晚最后修复；后缀包含原始测量，不称干净后缀。
- detection off、两scripted，E2无新注入；自动检测、自然故障、真实第二故障恢复和独立净收益 **NOT_EXECUTED/UNKNOWN**。首次受控修复后E2早轮已经即时汇报，本次不再冒“第一次”。

recovery收到793pose/598scan，526paired、未配对267/72；wall115.808s、peakRSS1,028,060KB、snapshot timeout0，资源归该进程不是全host整链。laser_mapping目标Built，整体make仍vikit测试ABI失败exit1；计划group kill/host exit null，无完整优雅退出证据。18export events含8status，10非status actions是正常过滤副本；7status received_s<0复用旧receipt元数据，RPC延迟不可用，集中字段修正不重跑。

## 3. 下一最小原生缺口：拒绝回退后，已经消费的历史输入不能被未来输出替代

E2实际restore到302.359s；后续resume只是map_hold=false。full v6 diff `restoreCheckpoint`恢复state/map/IMU缓存，`executeControlCommand("resume")`没有历史重放；本run只有E1一个reprocess，E2没有第二reprocess或明确held/suffix逐输入归宿。ACK已有大量held人口，但不能从累计计数推定每组已丢失/重推；归档的**完整历史追赶UNKNOWN**，不是全帧丢失的已证结论。

具体正常场景：302s前cp → 消费到311s并拒绝 → restore302s → 继续311s以后新输入。若302–311s未作明确隔离丢弃且后继合法state连续性未交代，或其中已消费健康后缀本应重推却未重推，未来17输出不证明完整接回；仅释放map写锁不能解决时间/输入归宿。这不是恶意输入/假设并发扩展。

**最低解除S1/S2**：沿现buffer/原生重推入口，明确拒绝区间里哪些隔离测量不准入、哪些后继输入必须追赶以及IMU/视觉/时间缓存的同一边界，按现声明范围给实际归宿/状态连续证据；若当前能力不支持，显式拒绝该恢复范围/安全结束，不称“restore+resume”全历史恢复。不无条件重放已拒绝污染、不重新造通用框架，不为此扩大宿主或错误矩阵。成功/UNKNOWN ACK依赖旧set_state分支未改，保[70e3反例](../review_20261112_70e3e7c/README.md)范围不重测；物理候选与实际修复云评价定义仍未闭合。

## 4. 主线与用户新15小时执行要求

- **原生主线S1/S2：**本次scripted时间边界解除后复用v6/suffix/skip/受控E2，不再重复查晚cp旧缺陷；下一最小交付是拒绝回退的输入归宿与成功依赖/物理一致native state-map→连续接回后继事件，或明确不支持范围。无新证据不追全部缓存/防御矩阵。
- **研究S3：**按用户[ALI-H §10](../ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md#10-用户明确交接的下一单一交付真实数据验证-ali-h)真实数据单一交付：旧402/544资格、真实I、同人口风险/UNKNOWN时长与成本。105b5be任务尚未合入本target，不指控忽略，也不冒实际认领/测试。
- **旁支：**本run主line数据身份/application属于必须核的支持；status延迟、旧参考原因/单hash、整体无关ABI集中并行，不作为无限宿主重跑原因。独立图有效性仍UNKNOWN，不要求ALI-H等图诊断。

审阅进行中用户2026-11-12 17:53明确新增15小时不中断推进/重大阻塞中文GitHub确认要求；另以执行任务文档发布，不把本target早于要求的状态当拒绝执行。新的实际检测接线按该最新授权/有限验证推进，旧参数手调/科学门不变，真实负结果不删除。本机不接管算法/ROS，自动审阅实际三Cron继续。

开发下一实交自检：检查项/PASS、FAIL、BLOCKED、NOT_APPLICABLE/实际命令及输出原件/影响/下一动作，source/input/library/config、cp时间与状态范围、修复/未修/后缀/未配对/拒绝后归宿、E2/尾段、label/calibration与独立净质量/完整成本；未实施或未测明确NOT_IMPLEMENTED/NOT_EXECUTED。A4具体时间边界局部推进、A2/A6/A10原生受控执行增加；A5/A8/A9/B2/B4/B11整项未闭合，A3/B3未自动验证。不重评分总表/继承历史分，不把工程问题靠调门解决。

## 5. 本机命令与发布边界

- `C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_d86e57d/check_archive.py` 最终exit0，仅读固定原件；reader初打印239ns略大1ULP只修自身十进制显示容差（1ULP+1ns），不改目标/科学判据。
- `C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_d86e57d/run_checks.py` exit0，最小源码控制；无ROS/host/bag/新调参/归档脚本执行。

独立review白名单SSH提交推送，不覆盖开发日报/private/历史，不合main不改算法。此处记录真实新边界与运行证据，15h执行任务另一个非Auto-Review提交以便开发识别，不重复造审计规则。
