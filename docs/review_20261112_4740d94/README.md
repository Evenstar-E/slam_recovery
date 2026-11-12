# 4740d94审阅：预测支持敏感性可核，漂移/覆盖因果及恢复E2未证明

- 读者：用户、开发S1/S2/S3和独立复核者。
- 目标 `4740d94a583886afc04b361aee3c6403d5072ecf`，比较已验 `70531bef27467519e370ac4819609398f1933533`。本轮fetch一度120s转后台，最终成功；不重复请求、不推断开发停滞。必读AGENTS、评分标准、REVIEW§10未变内容复用，20min/2h/日报实际repair-f3 owner，无活跃旧owner双写，按用户忽略stop.md。
- 本机不改算法/代host/调参，不merge main，私人handoff保护；上一fe56883已推送但本目标15:14早于其15:17发布，不能指控开发无视尚未送达意见。

## 1. 实际增量和可信计数

新增 `_predicted_pose` 与同scan/同reference下第二次support计算，仅availability开启时执行，不进入available判决；S2新run `fl_native_20261112T070801Z_197026`。这是诊断旁支的新运行，不是实际修复链增加。

| 检查项 | 状态/原件 |
|---|---|
| 来源与完整性 | PASS：14/14列示SHA、gz/raw SHA匹配；544行与paired/summary一致，驱动SHA43c65a9d匹配目标Git bytes；receipt库9c0330be为已核v3声明，当前无hostlog/实际库实体，不称重验进程加载 |
| 实际人口 | 819pose/598scan，544paired，275/54未配对；AVAILABLE132、UNAVAILABLE412。不是全部消息都检测，也不把544对402人口差唯一归因负载 |
| 两位姿支持联合 | 480有预测：both_low301、both_pass82、only_host_low50、only_pred_low47；null64且当时trusted_keys均0。全部480预测块保存200样本，mask/分母/pass复算一致 |
| 本次UNAVAILABLE分支 | 61参考空+351比例不足=412；预测输出不会实际把50帧送检测器，仍按宿主席判决 |
| 非scripted运行范围 | detection on、实际args及三scripted列表均空。summary scripted.note是沿用的错误固定说明，不据note反向认定本次人工触发；8episode不等8已标注真实故障，第三trigger诊断HEALTHY，不能宣称八个全是独立有效检出 |
| 原生动作/终态 | 8候选全部MODE3拒绝，commit/reprocess0；hold8/restore8/resume7 ACK，snapshot10成功、2superseded（非超时）；最终WAITING_FOR_EVIDENCE、open=true。不是HEALTHY，也未证明最后一段已接回 |
| 实际测量修复 | NOT_EXECUTED：actual repair_publish=false、log off；没有测量应用/首次修复后的E2，wiring通过不是成功恢复 |

run配置仍sigma.884、40ms pairing、scan_cap6000、wait_limit2s，无relay注入。node wall92.223s、peakRSS764,912KB记录接受，非整宿主或新增预测/I/O净开销；gz24,433,349B/raw79,323,160B。未执行归档analyze脚本或ROS/host/bag。

## 2. 必须更正的两个真实评价错误

1. COLLAB§91写“both_pass82与AVAILABLE132差为NIS门”不成立。实际 **132=82双通过+47仅宿主席通过+3无预测但宿主席通过**；480有预测帧的nis_present全True。双方support统计不是available的另一分母，不可把47的预测失败误判NIS缺失。kf88 host.765/pred.345/NIS19.1859而AVAILABLE，是直接反例。
2. 新REPORT运行表写HEALTHY，与receipt、run_summary、lifecycle三者均WAITING_FOR_EVIDENCE/open=true矛盾；最后一次restore之后只有7/8 resume，须如实保留开放尾段。最低后继增量说明更正，不覆盖失败原件、不为文字重跑宿主。

分段“147漂移/191覆盖/54预测差/null64”还混了人口：归档analysis探索标签合计 null21/both_low187/improved147/lower57=412，其中26–86段61帧只有21个有效预测，40个null被整段覆盖标签包含；全population null64含3个AVAILABLE，不能直接加进UNAVAILABLE分母。REPORT列作both_low的520–522三帧在analysis实际为predicted_lower；表中所谓191覆盖按列举段长实际190，不是191。最低报告逐帧联合结果和明确有效分母；这些探索标签不当真值，不新调分类阈值。

## 3. 预测能显示支持敏感性，但不能独立二分物理根因

接受以下事实：在同帧同参考下50帧从宿主席support失败变为预测pose通过；另47帧反方向翻转，301双方都低。kf147 host.505→pred.705/NIS353.6220，证明support对pose选取敏感，**并未施加宿主修复**。

不接受以下强因果：
- “预测更好 ⇒ 真实位姿漂移直接证据”：预测来自同一宿主的trusted历史，不是独立位姿真值；地图也来自该历史。更贴合参考可能是回到旧图、忽略真实转动/运动、历史偏差或覆盖变化，不能唯一证明宿主席错误。
- “两个都低 ⇒ 与位姿无关/覆盖不足”：两个位姿都可能错，特别是共源历史与旋转冻结。失败的替代位姿不是排除位姿原因的充分控制。S1末段已承认预测失效/根因UNKNOWN，REPORT及§90的强标签也须统一收窄，不保留相反断言。
- “147帧都是漂移”：三段长度147，只有50帧跨.60，另97帧仍双方失败；中位数差只是探索性段级变化，不是147帧故障真值。分析脚本用median差≥.25/低于host−.10划标签；未有这些数值运行前冻结证据，不称科学确认门，不继续调它们。

[recovery_node.py:1308](../../slam_recovery/ros/recovery_node.py#L1308)实为最后两trusted **位置差/时间差**外推，旋转保最新值；没有外推时间上限，也没有在记录中保存基准key/时间/velocity/预测T/horizon。target实际控制：t0@0s/x0、t1@1s/x2，query20s输出x40，说明代码未限制短时，非声称此run所有外推达19s。只有一个trusted时返回最后pose而非null；原件kf21确实trusted1且预测fraction.605，与§90“少于2帧null”不符。最低记录已有基准和实际时间跨度，区分last_pose/velocity，不先加新防御阈值或预测器。

当前仍无当时reference坐标/cache快照hash、原raw行映射；已核70531be缺项在新source未修，保留不重测。新预测块保全点但未保存预测矩阵/源身份；不能独立重建预测/PCA/参考几何。无需强求随机逐值一致或完整checkpoint bitwise，缺的是可解释的条件与独立参照。

## 4. 跨run与选择授权边界

同bag/配置声明不等同人口/状态：旧run53–117绝对戳窗口本次65帧中37AVAILABLE，旧199–401窗口203帧中37AVAILABLE。接受availability是运行状态相关而非仅输入固定属性；不能从两run差异确定“负载导致配对差”或“唯独地图导致状态差”，source、历史与消费人口均变化。

COLLAB§90转述“用户选中位姿-地图分解”，本机会话没有该项直接用户选择证据：记DEVELOPER_REPORTED，不据仓库文字当新的用户授权。现新增实现只观测、不改生产gate/判决，实际执行如实核验，不抹去；**不据它自动批准下一双参考实验或替代方法**。用户已经要求的最小同次参考取证可沿既有诊断任务收口；新的双参考因果方案另待直接选择/实际范围确认，当前不新起。

## 5. 本机检查

[reader](check_archive.py)/[结果](archive_checks.json)：`C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4740d94/check_archive.py` exit0，Git原blob+gzip/stdlib，544逐行/480预测完整mask核、联合与真实终态/动作；不执行归档脚本。本轮已知文件直接本机核，不重复代理大原件。

[控制](run_checks.py)/[结果](local_checks.json)：`C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_4740d94/run_checks.py` exit0，所有slam_recovery import从精确Git版本内存加载；12帧9不可用/3可用base/target/log开关diag/NIS/counts/records/trusted相同。actual方法两pose输出x4、一pose返回last/zero为null以及未限时控制PASS，非宿主修复。新两个test依赖pytest辅助未跑，不安装/shim，实际方法小控制替代。code-review首因D:/REPAIR非repo未执行，带明确repo路径重试完成无finding，不冒全正确性证明。

## 6. 下一唯一主线和旁支归属

**主线S1/S2**：物理一致实际修复→native完整state/map→保已消费后缀按序catch-up→接回→修复后E2/尾段，或首断点；已有23全量替换及按戳checkpoint复用。此次预测运行不解除v3后缀skip+clear，也不解除native成功依赖/新测量候选物理一致，源码未改不重测旧缺陷。

**诊断最小旁支**：S1集中修真实分母/终态与因果措辞、保已有预测基准/同次reference身份和原row及少数边界全样本，S2随下一已授权运行交对应原件或具体BLOCKED；不可事后用新map伪造旧参考。不为修标签无限起新诊断矩阵，不自动部署双参考/放宽支持门。只阻断强诊断主张，不让日志挡全部native。

**延期/并行**：S3维持一研究+两native分工，返回既定A/B/C门研究，旧sigma/κ/floor停；此处新因果选项未有直接选用证据。未配对原因、独立GT/覆盖数据不足记UNKNOWN，不无证据扩同步/预测架构。

开发逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令/原件/下一动作：诊断观测不改变决定的范围、联合有效分母/同次pose参考身份、最后开放段/失败/native applied/catch-up/E2、真实质量/成本未知；未做NOT_IMPLEMENTED/NOT_EXECUTED。A3/B3诊断敏感性局部观察接受，因果标签不通过；A1/A11/A12仍有限，A6/A8/A9/A10/B4/B11修复链未增加，不全表升分。仅review白名单SSH提交推送、不改算法历史/冻结门、不合main/private保护，发布不等开发已读。
