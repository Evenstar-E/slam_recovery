# c416a68审阅：已消费后缀原生重推接受，候选末端灌位姿仍破坏接回

- 读者：用户、开发S1/S2/S3与独立复核者。
- 目标 `c416a68d736c3fb9eee3bc0cfecdb23d586aba34`，比较已验 `4740d94a583886afc04b361aee3c6403d5072ecf`。本轮15:45 SSH fetch成功；AGENTS/评分标准/REVIEW§10未变内容复用，actual三Cron为repair-f3所有，无旧owner双写。按用户忽略stop.md，保护私人handoff，不merge main/改算法/代host/调参。

## 1. 实际主线推进：以前skip+clear的后缀现在通过原生处理循环

S2交run `fl_native_20261112T072902Z_207524`，宿主v4增量67行；driver源码未变，sha43c65a9d匹配target Git bytes/receipt，实际库声明c0833d9f匹配新build SHA。输入/config/binary沿同bag声明；host.log/deployed patch/命令原件已核，不本机运行ROS或重新build。

| 检查项 | 状态及原件 |
|---|---|
| 原件完整性/版本 | PASS：本轮changed scope中23/23列示SHA一致，driver/receipt/target与库/build声明绑定，非本机核bag或binary实体 |
| 同戳checkpoint应用 | PASS限定受控首事件：真实deferred snapshot在lio1627785276.281966925执行，snapshot stamp1627785276215170048/frame209；late66.797ms。不是只收到deferred ACK |
| 修复测量替换 | PASS限定23发布人口：+0.5注入，估bias+.45、施加−.45；23received/applied、dropped0/queued0/leftover0，stamp均在损坏集 |
| 后缀原生重推 | PASS限定捕获buffer：572group=124within_end+448suffix；原生循环每组handleFirstFrame/processImu/stateEstimationAndMapping，后缀不匹配修复云但不跳过处理。真实重放区间[1627785276.281966925,1627785295.292295218]，map21257vox/379069点 |
| 点/模态人口 | 572不是572个非空LiDAR scan：LIO286（有点226/空60）、VIO286；整体with_points226/empty346、undistorted总1086941。保留原分母，不把空处理计为成功建图帧 |
| 完整接回 | FAIL：紧随reprocess的set_state仍写冻结候选末端pose，随后resume并不能证明同一时刻state/map一致 |
| E2/自动检测 | NOT_EXECUTED：仅一episode/decision、detection off、首绝对scripted戳；没有修复后第二事件，HEALTHY经wait关闭/ABORTED rearm而来 |

此次具体的“已捕获后缀被跳过后清空”断点局部解除，不能继续写当前仍truncated399/372；那是旧v3原件。接受实际原生重估与地图变化，不据572计数声称完整状态等价、质量或恢复收益。完整逐group输入身份/全部状态map字节未独立验证，不要求为此造通用框架才推进有限运行。

原生下一断点不是“没有重推实现”，而是重推之后仍旧pose灌回。新运行不能用v3对照的地图点数证明净收益：checkpoint/source/消费人口不同，且无独立质量评价。

## 2. 已有状态来源问题现在在实际后缀运行中确认

| 实际命令ACK | state_pos | live地图vox/points |
|---|---|---|
| reprocess | 3.167535,6.145446,−0.110570 | 21257 / 379069 |
| set_state | 7.050962,5.921306,−0.446735 | 21257 / 379069 |
| resume | 7.317790,6.075148,0.200500 | 21257 / 379069 |

候选最后key161，stamp1627785280281185627，原件完整SE(3)的translation与set_state ACK一致；重放结束1627785295.292295218，比该候选末端晚约15.0111s。两ACK位置差3.904388673m，地图计数未变。**3.904m是分开命令边界状态差，不冒瞬时跳变/GT轨迹误差**；期间仍有处理，但明确set_state写入旧候选来源，并非重放边界的native完整状态。

这不是新提出的假设性防御要求：此前已有candidate尾pose≠native完整状态/FAIL依赖控制；此次后缀重放后实际ACK确认了时间来源冲突。开发REPORT称“本轮新冲突/原先为截断重放设计”只作开发解释，不把旧截断+set_state当已通过完整state/map的历史成果。

**最低解除**：复用现成功reprocess与状态接口，保留宿主实际重估边界state，不再用候选末端灌回；拒绝/未知reprocess不推进成功尾命令。S1已记录决定并派S2在ACK暴露replay_suffix、driver有suffix时跳过set_state；这是开发认领方案，**尚未实施或实跑**（target driver无改）。无需复制边界pose再set_state、无需新RPC/通用事务层或改门。即使suffix=0，也不自动证明candidate位姿与修复测量/完整native状态一致；旧物理定义问题保留，不靠此工程条件豁免。

解除证据：现有有限运行的reprocess末端→实际resume状态/map来源连续，命令/消费边界及完整人口可追溯，保失败；然后交修复后E2及尾段或真实拒绝/不支持范围。受控一次修正不当自动检测可靠性通过，不无限单事件循环代E2。

## 3. 修复范围、负结果和成本边界

- relay598帧中59shift、539原样；23发布修复，另36shift未发布，其中18在最后发布stamp之后。捕获后缀用**原始输入测量**不是clean数据；原输入还包括注入窗剩余部分。接受buffer恢复覆盖，不称整59损坏帧全去偏或所有后缀健康。缺项如实列，不能为结果改eligible人口。
- candidate23commit/106deferred；paired531、决定后300不是完成E2。snapshot成功26/超时8，summary explicit restore0但reprocess内部restore实际执行，二者不混。
- node wall112.339s、peakRSS982740KB、pose799/scan598为记录值；不是整个宿主峰值/端到端恢复净开销。负载356.74/340.32/282.30不证明任何具体丢帧唯一根因。
- host build目标laser_mapping Built、新库hash绑定；整体catkin_make退出1，仍vikit test的CXXABI_1.3.15链接错，不称全构建PASS。本机未build/未重放。
- 旧坏云candidate先通过再产新云、native成功依赖、baseline None→0等未变源码问题保范围，不重测旧控制/不展开异常矩阵，不凭本次成功23应用消除它们。

## 4. 可用性诊断旁支：收窄接受，不擅自继续实验

开发新增选项页/S3审阅并声明暂停诊断、转回native。本机没有“用户暂停/已选分解”的新直接消息，记DEVELOPER_REPORTED，不据转述控制远端进程或批准B双参考。当前本机不新起诊断实验，主线已明确native，开发实际本轮也交了宿主后缀运行。

接受选项页对旧65/65不可用→新同戳37/65可用方向、跨source人口、两者低不能排除共错/预测失效与不同NIS参考不可直接比较的限定；但尚不接受“only_host_low就是真实位姿错误”或“保持现状E2必然无法自愈”的一般结论。当前证据是分支/支持敏感性，不是独立位姿或系统不可能性证明。预测source/参考快照缺项、4740d94真实终态和分母意见已在d442793核验；c416a68早于该意见推送，不指控开发忽略尚未送达审阅。

旧191/54分段数字、306比例误称、预测短时/一pose规则与raw row身份等集中随后继说明，不因它们重跑宿主，不扩新诊断字段循环阻断native。旧S3/tmp历史统计只开发报告，不将其当本机新实跑/同版本调参规律。

## 5. 本机核验与下一单一交付

[reader](check_archive.py)/[结果](archive_checks.json)：`C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_c416a68/check_archive.py` exit0；Git原blob/hash/source+host.log/事件算术，无归档脚本执行或ROS/bag。本轮最初字段末尾逗号解析ValueError exit1，仅修自写reader后PASS，未动production。code-review low针对增量patch完成无finding，不冒C++构建/动态正确性通过；driver未变不重跑旧单测，source-bound新循环与实际运行核验即可。

**主线S1/S2**：收口本次实际set_state回拨，保持native完整重估状态，继而同次接回→修复后E2/尾段或首断点。S1共享driver/成功依赖集成单写，S2宿主后缀已交/边界运行继续；native成链首次完成立即单独报告用户，不等日报。

**最小保障**：native边界state/map/命令依赖一致是本次已证真实阻断；候选/修复测量同物理定义、全注入/候选/后缀人口和UNKNOWN质量保留。不以所有日志完备或新的预测方案作前置。

**并行/延期**：S3门A/B/C研究专用，旧sigma/κ/floor停；可用性旁支按开发pause记录，不自动双参考/策略部署，不扩防御框架/阈值/单测矩阵。数字/措辞随后继集中收口。

开发逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令/原件/下一动作：同版本source/input/library、真实checkpoint/修复应用人口及未修shift、全部捕获后缀/native状态来源、成功/失败依赖、resume/E2尾段、独立质量/成本/未知。未实施/未运行明确NOT_IMPLEMENTED/NOT_EXECUTED。A5/A6/A10捕获后缀组件局部推进，A8/A9/A10/B2/B4/B11整链仍未闭合；不全表升分。独立review白名单SSH提交推送，不合main/改历史/冻结门/private，发布不等开发接收新意见。
