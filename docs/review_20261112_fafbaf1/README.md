# fafbaf1增量核验：地图尾段覆盖增加，轨迹差异真实但干预因果未证明

面向：开发S1/S2/S3与独立复核者。固定目标 `fafbaf173b873502d248164adff8cd185dfa0dfc`，比较已验 `eeda1224da57fa9d380811f4009cb954615286c7`；2026-11-12 17:28 UTC+8 fetch。本轮新增0188b0b归档及S1总结，无slam_recovery实现改动，旧审阅合入不重审、不重跑未变单测。AGENTS、A/B标准、REVIEW§10已读/未变复用；实际20min/2h/日报仍repair-f3单owner，未新增自动任务，私人handoff保护/用户忽略stop.md优先。

## 1. 主线没有新增恢复运行，支持旁支有真实新原件

新 `fl_native_20261112T085719Z_276974` 是无注入/scripted、detection off地图保存pass；实际repair_publish=false、hold/restore/reprocess/resume均0，不能称自动检测或修复E2推进。接受这次运行尾段/地图文件，不接受以“clean/HEALTHY”作为独立正常真值或质量证据。

[隔离reader](check_archive.py) / [实际结果](archive_checks.json)读目标Git bytes，Python -I，不运行归档脚本、ROS、bag、ICP或参数实验：

| 检查 | 结果与范围 |
|---|---|
| 新档12项SHA | **PASS，12/12一致**；driver4742dbc1与target一致、config副本hash一致、库声明v5 9e7d8cdf |
| 播放尾部 | play.log `59.981342 / 59.993771`、`Done.`，receipt play exit0，支持bag播放完成，不等每条native消息都独立核了消费 |
| 位姿/配对尾段 | pose819行，1627785261.403843–1627785320.909074（约59.505231s）；paired544，末戳1627785320909073830，native snapshot frame819同末戳 |
| 消息人口 | recovery收到819pose/598scan，paired544，未配对275/54；544个pose戳与旧544诊断行逐行一致。pose文本仅6位小数，匹配舍入误差最大500ns，不逐ns/逐值等同 |
| 地图保存 | raw2,889,123点/远端hash未读；downsample15,647点、250,534B/SHA f1367c1c…实际解码 |
| 运行代价/负结果 | recovery wall135.484s、peakRSS1,010,636KB（不等全部保存/退出时间）；44snapshot/6ACK timeout；host末仍terminate异常，不能称优雅退出 |

旧第一pass“近静止”已由新报告承认读法错误：这不是重跑后才恢复运动，原pass749行本来就最大|p|11.99m，见[上一轮核验](../review_20261112_eeda122/README.md)。新尾段补足接受，不继承“bag320s”解释，也不抹第一次的缺尾/退出异常。

## 2. 原件证实跨运行差异，不等证明干预是唯一原因

本机按544个pose戳对应新819行位置，未做跨run健康prefix注册，故以下为**记录坐标下的同戳位置差，不是GT误差/已注册ATE/物理跳变**：

| 诊断key | 新旧记录位置差 | 新PCD同1m保存样本核验 |
|---|---:|---|
| 22 | 约0.000000243m（文本精度内近似同） | 20/20、median0.248899m；**只保存20/200，partial，不算完整帧通过** |
| 157 | 39.903317m | 完整200样本0/200、median18.437115m |
| 228 | 32.923310m | 完整200样本0/200、median8.997566m |

全544对应中，未注册差首次>1m为kf46、1.761249m；最大kf173、80.002159m。因此“约15s后30–40m”只是选择帧描述，不能当完整分叉范围/精确起点。上述两个低支持帧有限复算支持当前pose+参考不相容；没有独立定位/可信参考/固定覆盖，仍不能称真实位姿错误，更不能认定唯一根因。

S1§112归因 detection on 的hold/restore/resume vs off。原件确有诊断8hold/8restore/7resume而新pass没有这些动作，**干预是合理候选解释**；但比较不是只改干预：

- 诊断host实际库 **v3 `9c0330be…`**，新地图host **v5 `9e7d8cdf…`**；可执行文件同0d7e23de不等host实现同，逻辑在动态库。
- 诊断driver `43c65a9d…`，新driver `4742dbc1…`；config hash `47a1bfd9…` vs `94ffa5db…`。
- detection、sigma记录(.884/.12)、drain20/60、退出保存及负载/时序也不同；配置宣称仅保存改项不能替代完整同版本控制。

最低把归因改为**观察到动作与跨run差异、原因未分离UNKNOWN**，保输入/source/library/config/消费支持；不据此新开ON/OFF矩阵或追同值。本轮真实差异不是随机性豁免的逐位要求；反过来，也不将一次差异推广成所有运行必然分叉。

## 3. “独立参考必须同估计轨迹”不是必要条件，当前仍UNKNOWN

独立地图应对应同一物理场景、合法坐标注册及可见/评价支持，**不需要复制待评价运行的估计轨迹**。若独立地图已证明可信，某估计轨迹偏离它可以恰是需要测的错误；不能仅因待评价估计不同，就宣布独立参考原则上不可用。当前图不是GT，单prefix与覆盖未合法确认，因此不能反向宣布本图有效。

kf22近似同pose、20裁样本命中说明局部保存子集相容，不证明所有方向/整段gauge无问题、全200样本覆盖或健康真值。把诊断T_wb作为新reference运行set_state来制造同轨迹，会让待测位姿进入参考；只能标同轨迹/自参考proxy，不当独立位姿评价，也不批准这种新运行。

**最低解除与停止**：先保中性事实/当前参考结论UNKNOWN与覆盖缺项，已有评分若用于原因结论附命令/输出/单prefix变换/完整分母。不再要求第三次clean pass；用户已明确下一ALI-H研究交付，独立参考旁支不足不挡T0资格和真实运动证据路径。

## 4. 旧报告追加说明导致单个manifest失配，只作集中旁支

目标更新旧 `reference_map_20261112/REPORT.md` 加§6，但保原SHA256SUMS：当前旧清单 **10/11一致，仅REPORT失配**；其原expected ab3e2b4c…，当前c97c14f6…。不是PCD/log篡改或旧eeda核验错误（原目标当时11/11）；新增目标不应写全仓0fail。最低保原历史checksum与版本绑定，追加新版/补充manifest或把后续说明放外部，修当前验证入口即可；不修改旧Git历史、不为文档hash重跑宿主。

## 5. 下一交付与主线/旁支分工

- **原生主线S1/S2：**合法quarantine_start前可信完整cp→物理一致修复/真实native state-map重估→全部输入归宿/接回及后继事件尾段，或明确拒绝不支持范围。旧cp时间与失败UNKNOWN写回依赖没有实现更新，不重测；已有suffix/skip/受控E2和39尾帧直接复用。
- **用户新授权的研究单一交付S3：**执行[ALI-H §10真实数据任务](../ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md#10-用户明确交接的下一单一交付真实数据验证-ali-h)，先402/544现数据资格/缺项，优先真实IMU preupdate与LiDAR update证据，必要一次既有预算最小导出，同trace同人口交漏检/误报/延迟/错误NORMAL/UNKNOWN时间与成本。不要继续换图解释，不造零bias/占位、不贴另一run状态到旧run。任务已105b5be SSH发布，新target未包含该任务提交；**不据时间先后指控已忽略，也不称实际认领/测试开始**。
- **必须先做的评价旁支S1：**若使用上述报告作因果/质量结论，先限定动态库版本混杂、partial范围、合法参考与时空支持；只阻该结论，不阻native研发或ALI-H资格核。
- **集中旁支：**旧REPORT单hash/中性表述收口，无算法/阈值/测试矩阵扩展。旧参数停/1研究+2native不变。

下次实质交付须按PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令输出或原件+受影响结果+下一动作自检，source/input/library/config、时间人口/完整样本、native成功依赖、label/calibration和缺项、全部UNKNOWN/失败、真实质量/成本。NOT_IMPLEMENTED/NOT_EXECUTED照实，不能只说217tests或all_ok。A2/A11仅参考运行身份/共同戳支持增加，A3/B3/A11原因/质量尚未闭合；A4/A6/A8/A9/A10/B2/B4/B11无本轮恢复结果，不重评总分。当前原因归工程/评价证据限制，参数效果/代价/上限无同版本同人口规律，不resume手调。

实际命令 `C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_fafbaf1/check_archive.py` exit0。新增实质证据/评价意见按既有授权白名单SSH review提交推送，不合main/改算法/历史/私人文件/开发日报；不造重复规则或两小时空报告。
