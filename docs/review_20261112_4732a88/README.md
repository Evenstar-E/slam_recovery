# 4732a88核验：真实trace已到，跨度假关联与自动原生检查点未通过

面向：开发S1/S2/S3与独立复核者。主线固定 `4732a881cfcb83dc5c59c9780bff955908364c00`，比较已验 `1fd75b3c061995011a85cec31cb0309255493787`；20:07 fetch新增归档分支 `exp/trace-cov` 固定 `ffd4b13ce86d03556e389e42236e913d4701cf8d`。AGENTS/A-B标准/REVIEW§10未变复用；四Cron仍repair-f3单owner，无旧owner双写、不重建。忽略stop.md/noCodex/参数停，私人handoff保护，现SSH，不算法/ROS/历史/冻结门。本轮读取Git原件及有限声明控制，未运行宿主或归档CLI。

## 1. 成果与旧缺口关闭：原件已到，phase旧误读关闭

**有真实宿主内部trace/运行原件交付，资格与失败机制认识推进；ALI-H有效分类、原生自动恢复和完整净收益尚未通过。** 不继续机械记“全部仅DEVELOPER_REPORTED”。本轮只核指定run和必要源码，未扫全部253档或重做旧946帧。

| 原件/独立读回 | 接受范围与限制 |
|---|---|
| 新on 115734Z_483777，同库声明49f2f941；off115203Z_476840 receipt/summary | run身份自洽、inputs/launch声明相同；真实外部库/bag字节本机未读取，不能把receipt声明当外部重现 |
| on availability原件531行、kf0..531缺503 | NIS computed530、node_map444/prev_scan86/none1；summary paired532/computed531，不用summary补缺行或填0 |
| on trace1042行 | 完整1041行+idx1041截断尾53列；phase0/1前缀886/156，完整885/156；has_out前缀975，完整974。截断矩阵不补零，不把所有has_out当完整I |
| buffered113855Z trace1208行 | 正确phase1=322、idx489–810，has_out1=1087；旧把has_out当phase的“phase不可用”关闭。完整1207+idx1207尾44列，同样保缺项 |
| buffered mat_out | 2173行，末XYZ(-482.656,-185.283,54.3946)、范数519.8513m；是记录世界位置，不GT误差/ATE，不能据此独立标真异常/唯一原因 |
| probe_v7s1..5 | 原件均PASS alive25s且日志末stack smashing；证明这些探针保存状态，不证完整宿主安全或根因 |
| 保存T2 prep18与新manifest控制 | 保存自测不执行；本机只已读check_manifest/_manifest控制：detection off、DISABLED/support空拒绝，unit-only有效声明通过。不是实际行对应已通过 |

[trace reader](trace_archive_reader.py)/[结果](trace_archive_checks.json)、[源码/phase/probe控制](source_checks.py)/[结果](source_checks.json)、[旧off/on原件](native_archive_reader.py)/[结果](native_archive_checks.json)、[新自动事件](episode_reader.py)/[结果](episode_checks.json)。独立只读代理只负责指定两新run的字段/关联读回，未委派或读host源码；主会话读完整reader/关键结果并直接核host/protocol/ACK，不以代理结论替代原件。

## 2. 直接正常关联反例：scan_first全−1，531/531“包含”不是身份

新on **1042行scan_first_ns全部−1**，有效跨度为零。COLLAB§134“531/531满足first≤stamp≤last”数学成立仅因无效下界：实际每availability机械匹配1–1038行、530/531多义，共296310候选边；1035个trace行机械涵盖多条availability。这不是真实source membership，**有效跨度关联0/531，当前I与availability join未解**。不能以范围包含替原身份或把无效first当0/填nearest。

grp_idx是捕获组身份，不是扫描身份；实际886组、156组各live/replay一行，abs_ns还存在额外重复。同组可能含多scan、同scan可能跨更新，availability的原header/pose与group update起止不是等概念。trace abs_ns/scan_last均落256ns网格，availability原scan戳只有1/531落该网格；与binary64量化一致，不是原ns整数。

最低S1/S2/S3先核现采集时source scan→group成员/点时间与首次处理/重放事件关系，复用已有缓存或日志证明，不用grp_idx出现次数/序号猜更新。实证关系拿不到就INCOMPLETE/NO_TRACE_ROW/UNKNOWN，完整人口保留；不是要求通用时间框架或额外矩阵。若当前导出代码确漏原成员/起点，修本次最小导出而非换规则把−1接受为有效。未取得实际关系前不能称T2输入全部可用；真实内部量已到不等同物理时间的I已资格通过。

## 3. pre/post与cov约定：单位残差可继续，不能冒右SE3协方差

### 3.1 mat_pre/out不是按行号同键SE3文件

新on mat_pre2082行19列、mat_out1948行20列，均无group/idx/phase表头；数量恰为完整trace1041/完整has_out974的两倍，只是算术事实。按pre/out行号首戳相同0对，重复戳多，不能直接zip或只戳相等生成同更新eI。已上传旧v7源码可见LIO/VIO都写pre/out，解释混流候选，但最终v7u的完整LIVMapper/voxel patch未上传，不能按旧布局冒最终绑定。

最低沿已存执行顺序/真实更新事件核清LIO pre/post对应及Euler×57.3/外参/起止时间，不必新估计器。能重建的部分明确来源，无法唯一对应就I NOT_AVAILABLE，不配零/任意同戳。新trace最终尾行也列缺项。

### 3.2 可读宿主源码反证统一body切空间声明

归档 `include_common_lib.h.v7u:173–204`：rot=R*Exp(delta_rot)，pos=p+delta_pos，差值position=this.pos−b.pos。即**旋转右body增量、平移world加性增量的混合约定**，不是BUILD§3和trace表头称的统一body SE3扰动。原始vec是state_propagat−最终迭代前state，不能直接说等于Log(inv(pre)post)。这是真实源码对应问题，不是假设恶意输入或新阈值。

最低S1/S2/S3追加真实host vec/P坐标与eI映射/来源；没有同残差的协方差就READY_UNIT_ONLY/NOT_AVAILABLE，Ppre/Ppost只原量候选，不直接Ppre+Ppost或把frame字符串改pre_body冒转换。单位有量纲残差在pre/post资格通过后可报，冻结经验条件校准不改。先前三研究数学/资格组件修正仍关闭，未重测；新实际host约定不能由旧synthetic READY证明匹配。

## 4. 自动原生具体断点已可核：无cp与晚cp，不以wiring OK掩盖

新detection-on与scripted混合，不称纯自主链：

- off/on首个自动事件trigger1627785265674491405、qstart1627785261507921600，restore实际 **FAIL valid=0**，没有合法原生cp。
- on接纳段qstart1627785282444622421，实际reprocess ACK cp1627785302359221248/frame552，**晚19,914,598,827ns**；发布42但applied0/dropped42、within0/suffix311。不是修复成功。
- 旧同库3b26365f off112254Z实际修23/cpE1/244+439，on112753Z实际修0丢23/cpE2/0+151；buffered换49f2f941回E1cp修23/244+400。具体晚cp/捕获范围错配现在可核，逐行flush/负载/单槽覆盖的唯一根因仍UNKNOWN，不因为新缓冲较好就因果通过。

可读v7 snapshot复制单cp并clear capture，reprocess使用当前cp；最终完整源码/事件执行顺序仍须绑定。最低S1/S2把当前事件所需的合法cp/capture范围与实际ACK绑定，避免未来武装或自动快照取代在手事件；没有可支持的可信时间范围就明确不支持/安全拒绝，而非晚回退后公开成功。复用既有v6正确时间/suffix/skip和现在失败原件，先解除这个**当前实际工程断点**，不要继续trace run/手调制造通过或扩通用事务矩阵。S1共享接口单写，S2具体宿主实施/有限后继验证；真实信息/标签资格并行。

## 5. 不接受结果已知后删尾段分母或假根因

新T2_PROTOCOL§1.4在看到尾位置结果后新增“E2后不进NORMAL/SUSPECT/错误率”，与§1.3全部尾段和§3评价余下全部块矛盾，也违反其自身偏离另记规则；**不能称这一限制仍是结果前预注册完整人口**。

最低保原完整输入/块/phase人口和缺测/UNKNOWN/服务失败，新增`POST_E2_NO_CATCHUP`是分层/不支持范围，不删除主结果。没有标签的该段错误率NOT_EVALUABLE，不强填错误或把有限可评价子集分数说成全population风险。明确记录结果后协议偏离及对比范围，不在当前结果上重定义eligible。标签缺不等把全部坏尾段删除。replay/restore后时间跳转按执行phase分开、缺块断dwell，既有传感器时间块保留。

“尾段原因是无catchup、不是host新缺陷”只能机制相容候选；无catchup已知，但无受控排除就不推唯一因果，记录位置范数不GT异常标签。此问题仅阻完整效果/因果结论，不挡当前资格和原生最小解除。

## 6. 原件绑定、重大阻塞与下一单一交付

receipt/summary/availability登记SHA匹配；SHA256SUMS自hash失配是清单自身问题，不扩成全部篡改。host trace/pre/out未在相关run SHA清单内，新算Git SHA只绑定所读原件；本次读到真实数据但最终完整v7u patch和运行输出绑定仍不足。最低上传现最终patch/输出清单，**不因此重跑宿主**；既有数据可核部分先保留。reader初把manifest默认协方差和完整尾宽误作预期，各只修自写控制显式unit-only/不完整行保留，没改目标/人口/科学门。

ALI-B2正常参照/事件标签文件和真实用户确认本增量未变，仍等待；不代选C、不把开发批准/定时提示当用户决定。完整评价需两类证据，已有声明注入仅离线范围已授权，不为同范围再等批准；必要新输入/超预算或范围降级由用户选。只停受阻效果，其他合法部分继续；若实际接口/信息证明现范围不能继续且需要新决定，立即中文追加重大阻塞，不等22:00/08:53。

**唯一下一交付：在手事件的合法原生cp/capture→实际修复应用/明确拒绝→全部后继输入归宿；同次真实trace资格/完整UNKNOWN人口并行，校准标签解除后才报ALI风险和有限自动接线。**

- S1单写共享检测/事件-cp/成功依赖与拒绝后归宿，复用受控成果不重新造。
- S2最小修在手cp/capture断点、实际成员/前后状态时间证据，上传现最终patch，不盲重复运行/扩宿主。
- S3现trace实际I资格/完整人口、真实混合坐标与unit-only、校准/标签状态；不以invalid span通过，不事后删尾、不重算旧全UNKNOWN。
- S4现自动审阅/2h/日报/截止持续，不算法/ROS/noCodex/参数停。必须先做只有当前状态安全/关联与评价有效性；来源清单/格式集中旁支，不要求生产框架全备。

下次实交逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE、实际命令与输出原件、影响/下一动作；全部input/paired/缺503/截断行/未知成员/phase/缺块与UNKNOWN时长、实际cp是否有效早起点、repair applied/dropped/native success、校准标签、服务尾段/失败与成本；NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE保留，不test数/all_ok/HEALTHY冒闭环。

A2真实归档与A3/B3资格组件推进、A1/A11新真实关联FAIL、A4/A5/A8/B2新自动native范围FAIL，A6/A10只受控部分证据；A9/B4/B11完整未闭合。按版本局部核、不重评全表或继承历史总分。中文review白名单SSH提交，private/开发日报不动、不合main/改算法历史冻结门。

### 实际命令与自检

- `C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4732a88/source_checks.py` 最终exit0，数据/声明控制；初两reader预期修正如上，数值源码不执行。
- `C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4732a88/native_archive_reader.py` exit0，三个指定旧run实际ACK/末XYZ读回。
- `C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4732a88/episode_reader.py` exit0，新自动事件FAIL/晚cp+42丢弃读回。
- `python -I D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4732a88/trace_archive_reader.py --repo D:/REPAIR/slam_recovery_upstream --output D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4732a88/trace_archive_checks.json` 实际代理最终exit0，一轮必要解析，主会话不重算。
