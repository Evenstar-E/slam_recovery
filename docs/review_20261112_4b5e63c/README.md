# 4b5e63c增量审阅：v8来源推进、在线回退负结果与失败ACK误判

面向：开发S1/S2/S3与独立复核者。固定主线 `4b5e63cbdba6b8e936a5d3b13fa6770c2d212424`，比较上一已读634b6a8；21:08 UTC+8 fetch完成。原件固定 `exp/online-trace@553e2b8b74f11ab675b3f0afc5d5565498268c99`、`exp/online-v2@8ca557555926b0aa24c31082e4bc78a9dbdac3b6`，旧失败ACK只复用trace-cov@290aae8。跳过Auto-Review/纯审阅合入和已验组件，不重新执行旧T2/完整测试/归档CLI、ROS宿主、参数实验。已读AGENTS、A/B标准、REVIEW§10及历史末段；实际四Cron仍本session，其他本机session waiting/idle，没有接管或重建任务。忽略stop.md、直接用户暂停优先；私人handoff不提交，不合main/改历史或冻结门。

## 1. 本轮接受范围：来源与负结果推进，不是合法恢复或ALI性能通过

| 实交／检查项 | 状态、证据类型 | 接受与影响／下一动作 |
|---|---|---|
| v8完整宿主改动源码与实际run124217原件 | PASS（归档读取） | 五源码已取得，旧“没有完整最终导出源码”缺口在v8范围关闭。736行全部93列、phase全0、669 has_out；不是v7修复或完整60s评价 |
| v8关联产物输入SHA与新首戳 | PASS（本机reader） | trace/解压availability/receipt/summary四SHA与保存结果一致；444行=88 AVAILABLE+356 UNAVAILABLE，首末戳真实且每行n_scans=1。512ns候选匹配217行一组、227行两组，无未匹配，不能降格回旧全−1 |
| 唯一同次更新、post配对及完整点成员 | BLOCKED（资格证据不足） | span关系增加但不是全物理I资格；carryover/source成员和同次pre/post仍须明确，详见§3。暂不使用此关系声称精确eI/有效I人口 |
| 检查点晚ACK派生、scripted合法前组及online qstart边界 | PASS（本机普通控制） | 不再立即复制空ACK；边界980/实际975接受，实际990判晚；scripted声明与online qstart分别取边界。关闭旧两处记录问题，不当恢复语义已修 |
| 新纯online run125406四段实际ACK/边界 | FAIL（真实归档负结果） | driver SHA绑定de4360b；544 paired、0接纳4拒绝、四restore valid1但三份晚qstart。最后HEALTHY不能抵消不支持回退 |
| FAIL valid0被标成WITHIN_DECLARED_BOUNDARY | FAIL（正常已发生类型、本机复现） | §2给原始ACK和最低S1修正；只是新资格记录错误，不声称它已导致主线错误接纳 |
| v8构建与库来源 | PASS局部／FAIL整体（归档） | laser_mapping目标完成；总体make因test_vk_common_patch_score的CXXABI符号失败。声明库SHA与run一致，独立源码→执行库重建NOT_EXECUTED；不报全构建通过，不因该测试链接失败否认实际运行 |
| C′保留K份／按时间选择恢复 | 保留+报告为开发安排；选择恢复NOT_IMPLEMENTED于本次实交 | 目前只批准K=3有限研究、默认K=1，不改restore/reprocess选择；未见本轮C′代码/run，不预报覆盖率或成功 |
| ALI同人口检测效果 | BLOCKED／NOT_EVALUABLE | 本轮没有独立正常参照与事件标签解除证据，v8覆盖49.11162591s且两段全拒；本机未运行207测试或新检测方法 |

主线有效性支持证据有所推进：真实导出关联改善、在线不合法回退已可逐段验证；**新增合法在线恢复/修复净收益/ALI判别效果没有得到证明。** A1/A2/A11来源局部推进，A4/B2负边界明确但未闭合，A3/B3效果仍未评价，A6/A10/B4/B11不凭本轮全拒计成功。未重评全部24项，不报新总分，不继承历史16/36、11/36给此main。

## 2. 新普通反例：失败恢复ACK的负哨兵被当成合法检查点

`4b5e63c:slam_recovery/ros/recovery_node.py:1618–1659` 的_finalizer仅解析stamp并与boundary比较，没有先核action.ok和ACK valid。此前真实115734Z ep0原件是：

```text
ok=false
FAIL restore valid=0 stamp_ns=-1000000000 frame=0 voxels=0 nodes=0 points=0 restores=0 ...
```

[来源控制](provenance_checks.py)/[实际结果](provenance_checks.json)把这份原始action传入本目标已读三个metadata方法，boundary为真实qstart `1627785261507921600`，得到 `AT_OR_BEFORE_BOUNDARY / WITHIN_DECLARED_BOUNDARY`。另[小控制](run_checks.py)/[结果](local_checks.json)在边界980复现同问题。exit0表示断言成功复现缺陷，不是被审目标PASS；本机没有重跑旧宿主或制造恶意ACK。

**最低S1解除**：沿现action来源先区分失败/无有效cp，再对有效实际stamp作边界判断；FAIL/valid0不能支持回退，保留原ACK和未知/失败原因。复用上面一份已发生失败控制及已通过前/晚边界控制，不扩通用解析器/异常矩阵。此项阻断“该metadata证明合法回退”的评价口径；不要求停掉S2其余有限合法工作，不把记录修复当恢复实现。

新run125406四段 `actual − qstart` 的整数差已核：

| ep | delta_ns | 结论 |
|---|---:|---|
| 0 | 3767115328 | 晚3.767115328s |
| 1 | -4839131621 | 早4.839131621s，复用前一份frame59 |
| 2 | 3833355876 | 晚3.833355876s |
| 3 | 4233352959 | 晚4.233352959s |

四ACK均OK/valid1，故此run不受上述valid0反例影响，三晚负结果仍成立。run driver来源是de4360b，保存check没有后来8789505新增rollback_support；本机没有把4b字段假称归档运行已产生。新support只是summary标注，**不是阻止晚检查点restore的执行门**。早于qstart只证明时间范围，不证明完整状态/缓存/capture一致或已追赶。

## 3. v8关联升级成立的部分与不能跨越的资格

实际run124217库 `1239f35f…`，trace SHA `3728c94c…`；四输入SHA见结果。v8确实填入actual merged headers且新增n_scans，按列名读92/93列是合理复用。512ns只作double时间导出量化候选保护，不是降低科学门或姿态容差；接受真实header关联改进和完整保留227行多组，不强制一一对应，不把v8结果搬回v7。

但 `553e2b8:host_change_trace_cov/src_LIVMapper.cpp.v8:2042–2101` 先把上一pcl_proc_next拷到pcl_proc_cur，再把新raw scan按点time分成cur/next；仅merged_scans>0时更新first/last/count。故n_scans计本次新pop的raw扫描，**源码尚不能由n_scans=1独自证明当前完整点云只来自一个source scan**；无新raw时字段可能沿前组，而carryover仍参与当前云。相同scan戳的两条live trace是已观察到的真实关系，不等两个独立样本，也未给出与availability所配pose的唯一更新关系。本轮结论为NOT_VERIFIED，不宣布所有v8关联无效或把源码疑点冒实际错配率。

另完整v8 `src_voxel_map.cpp.v8:478/510/521` 继续先算state_propagat−state_并保存vec，随后state_+=solution。因此vec与最终post精确差仍不由源码保证；混合旋转右body/平移world约定没有变。旧t2_run exact_e漏Jinv缺陷没有本轮修复，直接复用上一已验反例，不重测/重开旧正确工具。**最低S2/S3**在当前同run明确source/carryover→更新→所用pre/post/vec阶段；缺关系保UNKNOWN/INCOMPLETE，cov继续NOT_AVAILABLE，不靠改frame字符串、按行zip或近邻时间补资格。只阻受影响I计算及效果主张，不阻原件交付与原生修复开发。

归档wall116.63s/peak1008976KB为run摘要读数，不本机资源实测，不等实时能力。49.11162591s/444人口不可当完整60s曝光，缺失尾段保留范围限制；无需为本机审阅重跑全部宿主。

## 4. 单一下一主线与旁支、责任确认

**主线：在现单宿主与授权预算内，给一个时间合法、完整状态/capture一致的在线检查点恢复→物理一致实际修复测量→原生状态/地图重处理→全部后继输入归宿；不能支持的范围明确拒绝。** 区分现旧检测器自动与ALI-H自动，未完成部分允许明确负结果，不用K快照计数/ACK支持字段替代真实选择恢复。S1共享代码唯一集成，S2真实宿主，S3方法研究；现开发归档/driver认领可核，C′新代码/部署/实际回执尚未交。

| 分类 | 最低工作与责任 | 依赖和验收 |
|---|---|---|
| 必须先做 | S1/S2：合法cp与capture/replay时间范围 | 当前三晚已实证；retain历史是候选手段，选择恢复须真实支持。早cp但中间历史未捕获也不PASS；复用既有受控恢复/重处理组件，不新造通用框架 |
| 必须先做，仅受影响评价 | S1失败ACK资格；S2/S3真实I阶段对应及复用正确Log | 已复现的记录/数学、来源缺项最低解除；不因此停其余未阻原生工作或等全部旁支完成 |
| 可并行 | 现授权内C′K=3保留+报告有限研究；S3现材料正常/标签核查与shadow | 保实际预算/负结果和全人口；K覆盖非合法恢复，不把S1“明天选择”安排当用户延期15h。实验无有效快照则报负结果，不能只无限增加审计 |
| 集中延期 | 次要数字/措辞、清单汇总和非必要兼容性 | 不影响本轮输入/判决的不要求宿主重跑，不追单测数量或新调参矩阵 |

仓库Codex路线文档的RECOMMENDATION_PUBLISHED/EVIDENCE_CONDITIONS_PENDING可作为建议，**不把其转述用户委托当本session已验证用户选择B/C、ALI-B2解除或恢复Codex人员配置**。其当前诚实资格、现材料核查、条件满足且现授权内有限离线评价与既有15h任务相容；不重复泛问A/B/C、不增Codex前置，也不自动停native。完整校准与效果评价仍分别需要独立正常证据、事件标签；已有声明注入只离线使用无需再次问同范围授权，确需新来源/安装/超预算等再具体中文GitHub请求。原参数手调停、科学门不降。

开发下一实交随主线给**PASS/FAIL/BLOCKED/NOT_APPLICABLE＋命令/原件＋影响/下一动作**：实际owner/HEAD、source/config/input/library、有效ACK与qstart/capture/replay关系、损坏/修复/未修/误改/未知、全部pending/后继和缺测、ALI独立校准标签及UNKNOWN、成本。NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE不补成通过。

本机两个有限reader实际exit0，生产算法未改、未代跑远端、未安装依赖。仅此次来源推进/负结果和已复现普通缺陷形成中文增量，现review分支白名单SSH提交推送；不发布私人handoff或凭据、不覆盖开发日报。
