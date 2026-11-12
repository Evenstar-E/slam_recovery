# b2f3983增量审阅：独立工作区原生取证推进，四宿主比较须纠正实际拓扑与功能归属

面向：开发S1/S2/S3与独立复核者。固定2026-11-13 01:45:56 UTC+8 fetch main `b2f3983801e6113f3c3626df0d95783666e1c24f`，比较 `1f7a6dc35e720b807502acdc258b2f0891c53f47`；新增原件在growth `4f205ef55fd023af9573eda324f01c5fcef7c6b1`，不是main树中的四宿主文档。已读AGENTS、MAINLINE_PROGRESS_STANDARD双表、REVIEW§10、历史§91–92，规则未改；跳过自己Auto-Review/纯合入与已验T2，不重跑其原件。四Cron仍repair-f3持有，未见旧owner；私人handoff仅untracked不读不动。忽略stop.md，直接用户暂停优先。

**结论：部分推进。** 新FAST-LIO2工作区的构建及原生两次休眠/重建执行证据到达，上一轮“run1全为开发转述”局部解除；尚不是原版FAST-LIO2独立实现验证或slam_recovery实际修复。四宿主接口分析确给出若干源码位置，但MM-LINS实际拓扑、测量输入可替换性、FAST-LIO2/FAST-LIVO2功能归属和LIO-SAM单进程结论须最小纠正，不能据错表扩大框架或豁免测量修复。

## 1. 原生运行的接受范围与原件限制

[自写只读reader](run_checks.py)、[首轮结果](local_checks.json)、[补同口径初始化标记结果](extended_checks.json)，两次实际exit0。仅标准库Python -I读fixed Git文本/JSON和独立算术；不导入/执行归档脚本、不解析真实bag、不ROS/build/安装/改算法。结果保哈希，额外输出路径支持复核且禁止覆盖已有JSON。

```text
C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_b2f3983/run_checks.py <新输出路径>
```

| 项 | 状态／证据 | 接受范围及最低下一动作 |
|---|---|---|
| 独立工作区构建 | PASS_ARCHIVE局部 | build.log第一次CMake策略失败保留；build2.log完成fastlio_mapping链接/目标。run1 PID692359路径与run2 PID705077声明均fastlio2_ws，不再称只有mmlins_ws二进制；声明新SHA4c31fada…/输入a924b5f9… |
| 实现/源码身份 | NOT_VERIFIED原版主张 | 源自MM-LINS/FAST-LIO复制，no-git-in-copy；source_commit c6d9e32在本仓是交接文档提交，不是原版FAST-LIO upstream revision。源码聚合sha未交计算命令/文件清单，config/launch原件hash未绑定run2。最低已有复制源文件清单、聚合命令/patch及实际加载配置，不重新构建或换实现 |
| run1失败原件 | FAIL有限可核 | play日志78798个进度值，最后375.960884s、无Done；节点日志323个IMU初始化标记/4次重建，实际进程路径已交。900s外层与reindex零消息仍开发说明，缺bag/info/完整退出原件；文件sha/路径是来源补齐非恢复效果 |
| run2原生行为 | PASS_ARCHIVE局部／bag独立重算未执行 | 节点日志两次sleep、两次rebuild按顺序；bag_info与analysis合计12980一致、4186 Odometry/418 path/各2个Bool。保存首末戳/两gap边界/尾人口与共享版一致，支持同一修改前端在新工作区重跑行为相容，不完整恢复验收 |
| 接回与跳变 | 负结果保留 | 真断流23.799380302/26.899189473s，跨gap位置跳60.4788/71.1224m至近原点。0.023395748/0.020962829是事件到下一条输出，不是停发时长。239.317980404s/2126条按声明E2起算，含26.899s断流，不冒连续尾或恢复成功 |
| 同口径数值比较 | PASS保存结果算术 | 独立短dt路径353.43290676加gap跳变131.60123002=485.03413678m，对共享全步485.07913907相容。E1/E2位姿差范数0.180876/0.229773m，不能称全轨迹逐位相同或忽略坐标重置；未独立重算全消息人口 |
| 修复/检测/收益 | NOT_IMPLEMENTED／NOT_EVALUABLE | 未接slam_recovery修复、可信checkpoint、历史重处理或事务提交；声明自然休眠观察不是注入二故障/自动检测性能，重建到原点不是历史可信恢复，独立净收益/GT未交 |

上轮共享前端局部事实不抹去，本轮补“新工作区独立编译/执行”这一工程来源。**NATIVE_INDEPENDENT若保留须限定为独立workspace构建的MM-LINS派生前端**，不能升级独立原版实现、完整A4/A6/A10/B4/B11或四宿主需求通过。原bag/binary远端实体未本机重新hash，声明与归档文本证据分开。

## 2. 运行控制与根因：实际录制六话题，不是报告的四话题

main COLLAB§171和growth REPORT§7称仅录Odometry/path/两Bool；实际runner、record.log、bag_info、analysis全都显示另外录了cloud_registered与cloud_registered_body，各4186条，文件868.8MB。故不能将run2成功归因于“去掉全量云录制”。最低S2改实际执行口径，原件保留，不为文字重跑。

保存runner包含120s速率检查和cgroup采样，但run2 runner.log缺其应写的bag_duration_after_120s/cgroup差字段，缺play.log/cgroup_start/120s及执行脚本hash；0.92×仅开发报告，不能独立确认这份脚本对应实跑版本。cgroup只是采样/echo，无独立停止阈值；1800s兜底不在此脚本内，若外层设置须交实际命令。最低补已经执行的脚本/diff/命令与已存进度采样，不新建资源控制架构/重试矩阵。

run2节点日志IMU Initial Done=165，共享版用同一字符串统计也165；run1=323，不是“共享整段2次”。不能把每条日志自动计为独立物理重初始化事件，需源码/事件阶段定义；但按同口径数字可关闭旧对比误述。run2成功与run1失败不排除任何代码/时序/记录因素，负载root仍UNKNOWN，不将文档“与代码无关”认证因果，不据load推处置其他进程许可。

run2/frontend.bag未入库且无输出bag SHA；同run派生analysis和bag_info可核自洽，不是独立读bag验证。最低补已有输出bag hash/实际分析命令/source/config身份与可获取逐消息索引或合适原件路径；不把大bag上传Git当唯一前置，缺项保UNAVAILABLE。run2结束原件新交，旧BLOCKED_LOAD可在“出现输出的原生run”范围解除；不能声称实时全链预算/峰内存通过，未测成本保持UNAVAILABLE。

## 3. 四宿主分析：先纠正所选路径，再给首个实际恢复断点

四文档由只读独立核验分别检查，主会话已核关键归属源码/launch。以下行号绑定growth4f205ef。只读分析不等实现/运行。

| 问题及真实反例 | 最低解除／主线影响 |
|---|---|
| MMLINS_RECOVERY_INTERFACE:8–15/54–70与比较表:12–16默认ALOAM四节点；既有run_mmlins.sh:49–52实际FAST-LIO前端＋PGO两节点，后端fastlio_ouster64.launch:27–36只起PGO | S1锁既有两节点路径或显式另选四节点，绑定launch/source/binary。不能让既有两节点主线被泛化四节点checkpoint框架串行阻塞 |
| MM-LINS“无测量注入点”不成立：ALOAM scanRegistration.cpp:492订阅velodyne_points；FAST-LIO laserMapping.cpp:758–759有可配点云/IMU输入。替换输入需重跑后续估计正是M2要求，不是测量修复不可能证明 | 最低明确外部消息过滤→现前端原生重估→PGO贡献的接入；在线局部首缺口是完整可信状态/历史输入/PGO一致后继，不默认删测量要求或仅做状态回滚。健康前缀离线原生重跑若获当前授权可作为限定M2，不冒在线闭环 |
| 比较表:17–19/29将FAST-LIO2写体素八叉树、已有replay_buffer_/reprocess和地图暴涨；可访问FAST-LIO实际state_ikfom/ESKF＋ikdtree，re_slam:673–693重置滤波/IMU并清树 | 旧FAST-LIVO2功能/失败不搬FAST-LIO2。本轮限定树未找到声明的重放接口，无新实现；给准确host文件/方法与版本化证据，否则NOT_IMPLEMENTED，不以表格当A6已有实现 |
| LIOSAM_DIVERGENCE:57–63宣5模块同一节点/进程；既有receipt记lio_sam_nodes=4，无对应PID/launch源码支撑同进程 | 先补已有实际拓扑原件，节点数不等PID数，不能据单进程假设认证完整快照/原子性或成本低。接口文档不是原生恢复 |
| ORBSLAM3“无ROS话题→不能测量修复”，却自身列TrackMonocular(image,time,IMU) | 无ROS不排除runner层改真实输入/native重处理。未实现历史恢复须直写未实现，不凭调用模式判不可行或豁免A6；Atlas存取API存在声明不等完整tracker/IMU/缓存可信checkpoint |
| 工作量~40/60/80/100行及成本排序ORB<FAST-LIO2<LIO-SAM<MM-LINS没有测量/完整状态范围 | 作为粗估且列UNKNOWN，不作为已验证选型理由；复用现manager/cmd/ack，但新host必须实交apply/repair、身份/帧归宿。Issleeping/Isbuilding是子图生命周期信号，不是已验事务hold |

最小MM-LINS接线面已可具体指出：FAST-LIO的点云/IMU订阅与标准点云预处理→状态更新/ikdtree→SC-PGO订阅前端输出及ActiveMap。S1按实际两节点认领首断点与输入/状态时刻/map后继，不先推演通用序列化/跨全部host框架。已有信号/语义可复用，但不原样冒通过。

## 4. LIO-SAM/ORB负结果接受，独立根因仍未知

独立核验旧trajectory.csv支持LIO-SAM首个>1m相邻步130.097372→130.297323s、1.145557m；首个>0.5s gap146.797288→148.197169s。新文档130.3/148.2用后端戳、旧130.1/146.8用前端戳，须明示约定，不把差异算新事件证据。点数26k→797→203/110次IMU重置没有本次可获取点数序列/原日志/原计算入口，引用analysis.json也不在固定growth；不能从轨迹渐坏及grep无loop直接确定输入是直接原因、排除图优化。最低补已存原件并保持候选假设，不为开loop日志另起run。

ORB原日志支持80次New Map、385次Not enough motion、43次bad imu、末Atlas1图0KF及exit139，原负结果不删。日志本身不认证“两视图低视差”唯一根因或任意策略永不能稳定；初始化判据/System/Atlas宿主源码未在该树可核。最低补已有固定相关源码片段和判据/输入限定，不能自动换序列/安装或以Atlas API推最小完整恢复成本。

“输入信息不足可能限制恢复”是合理待检假设；不把四宿主共同根因/永久恢复前提宣布已证。没有测量的几何不凭空补，旧阈值/独立评价不降，真输入故障vs算法故障按实际数据判UNKNOWN，不能从未交恢复猜结构失效。

## 5. 下一唯一主线及旁支

| 分类 | owner与验收 |
|---|---|
| 主线 | S1唯一共享集成、S2实际host：锁现MM-LINS FAST-LIO＋PGO两节点路径，实交测量修复→前端native状态/地图→PGO后继接回/E2；尚未能接则交具体函数首断点＋最小变更/可复用物件及实际认领，不再用错误比较表停在选型 |
| 必须先做 | 实际路径/source/config/输入身份及恢复起点/map依赖一致；原生源修正为MM-LINS派生实现。仅影响该目标的缺口前置，不要求所有旁支/完整多host防御先通过 |
| 可并行 | S2既有run2脚本/输出hash/同口径事件缺项与run1失败原件；S3上一轮18 eff0、成员三层与本run事件人口（本次仅收到要求，未交修后）；已有LIO/ORB原因候选收口 |
| 延期 | FAST-LIVO2新增构建/适配/实验/ASan；未经授权的换输入/新矩阵/进程处置；一般措辞集中整理。四项分别验收，不以一项或派生前端代全体，不提前放行FAST-LIVO2 |

开发随下次实际交付提供**PASS/FAIL/BLOCKED/NOT_APPLICABLE＋真实命令/原件＋影响/下一动作**；NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE与失败/中断完整人口保留；声明自然事件、实际恢复后继、输出可用性、独立收益和资源分别记账。S1认领/源码首断点、S2执行接收和S3修后回执待交，不将“已转发”当实交。原运行进展不抹去，工作区独立构建及归档对A2/A12有局部支持，A4/A6/A9/A10/B2/B4/B11未整链通过，B6因果未证，不报新全表分。

四Cron单owner保持，15h08:53如实报告不延期；权限拒绝不绕过，不自行认证仓库S1/用户转述为新授权，不恢复旧手调/降门。当前中文审阅白名单现分支SSH发布，不算法/main merge/历史重写/私人/开发日报/凭据。
