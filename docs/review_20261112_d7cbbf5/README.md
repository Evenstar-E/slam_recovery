# d7cbbf5核验：纯在线修复确有应用，可信回退与测量正确性未闭合

面向：开发S1/S2/S3与独立复核者。主线目标 `d7cbbf5132f486b17f686709f6abda977c328941`，比较已验 `4732a881cfcb83dc5c59c9780bff955908364c00`；2026-11-12 20:27:46 UTC+8 fetch。新归档 `exp/online-trace` 固定 `e991eaf6b390ec77e74753dbd5b926fb91589d8b`。必读AGENTS/A-B标准/REVIEW§10未变复用；四Cron实际owner repair-f3、无旧owner双写、不重建；忽略stop.md/noCodex/旧参数停，私人handoff保护，现SSH，不算法/ROS/历史/冻结门。跳过168769e旧核验/纯merge。

## 1. 本轮有纯在线自动执行实证，不再说全部只受控/scripted

[有限源码及原件reader](run_checks.py)/[结果](local_checks.json) `C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_d7cbbf5/run_checks.py` exit0，只读Git字节、编译已读两个新增metadata方法，不执行归档CLI/selftests或host。实际source SHA `62c165d1…`与receipt绑定目标一致。receipt/summary/wiring/launch/availability五项登记SHA同；清单自hash失配保来源旁支，不据此指控原件篡改。

| 实际交付 | 接受的推进 | 不能代替 |
|---|---|---|
| 121127Z_497953，detection on、无scripted声明/命令，库49f2f941 | 五自动事件，1接纳/3拒绝/1校验异常；原生自动触发→接纳→发布修复→reprocess确实执行 | 是原有检测器自动执行，不ALI-H自动检测已接入或性能通过；不是五个独立真实故障标签 |
| 接纳ep3 | 42发布/收到/applied42/dropped0、759within+615suffix、无set_state、map输出ACK有真实重估 | 门committed11与修复42不同人口，不叫42全部正确恢复；完整输入/状态/map一致与独立净质量仍未证 |
| 同run availability529 | AVAILABLE194/UNAVAILABLE335，computed528与paired529，原件真实 | 缺正常参照/标签，不能从HEALTHY/无新注入认正常 |
| trace1568行 | 本次全部92列完整、phase0/1=886/682，has_out1=1439，SHA435fff50…；上一run截断不是本run同缺陷 | scan_first1568全−1，组/状态配对仍未解；mat_pre3145/out2887混流不直接zip |
| 终HEALTHY/open=false | 生命周期有末输出，recovery进程wall133.347s/RSS986516KB、未配对pose290/scan53 | lifecycle unresolved4及一异常保留，不算完整正常闭合/全host成本；计划kill不优雅退出证明 |

**A2/A6/A10局部真实自动执行增加，不能把先前“无纯在线实跑”机械沿用。** 首次受控实际修复→E2流程早已单报，本次只称新的纯在线自动执行，不再冒此前首次成果。完整科学恢复/独立净收益/ALI性能仍未通过。

## 2. 自动cp有实际ACK，但前两事件晚隔离起点

新增“在线EXPECTED_UNKNOWN”不等可信边界未知不可测。episode本就有 `quarantine_start_ns`，实际restore/reprocess ACK有cp戳：

| 事件 | qstart | ACK cp | cp−qstart |
|---|---:|---:|---:|
| ep0拒绝 | 1627785261507921600 | 1627785265408197888 | **晚3,900,276,288ns** |
| ep1拒绝 | 1627785270514891768 | 1627785274348550656 | **晚3,833,658,888ns** |
| ep2拒绝 | 1627785276381083632 | 1627785274348550656 | 早2,032,532,976ns |
| ep3接纳 | 1627785283044299269 | 1627785274348550656 | 早8,695,748,613ns |
| ep4异常 | 1627785283044299269 | 无应用ACK | UNKNOWN |

ep3具体晚cp问题本次没有发生，42修复应用接受；ep0/1虽然valid1，仍非隔离起点前可信边界，**不能因改纯在线就关闭回退合法性**。早于qstart也不自动证明全部缓存/修复历史一致。最低S1/S2沿当前rolling历史能力选择合法范围，缺早cp就明确不支持该范围，不能用晚cp公开全部保护成功；仅判时间是否合法不要求知道精确唯一“期望快照戳”。避免新通用多槽框架/矩阵，复用受控v6前已处理时刻/现捕获入口。

## 3. 新检查点记录存在两个普通路径错误，最低在汇总收口

1. **在ACK到达前解析并复制标量（recovery_node.py:1891/1896、1917、2122）。** `_send`不等待应用，调用 `_record_checkpoint_check`时action没有ack；随后collect/poll补action，但复制进meta的actual戳不会更新。正常控制先无ACK记录、随后事件补`OK restore valid1 stamp975 frame1`，meta仍null，实际run五段actual_stamp/actual_frame均null而前三拒绝与接纳的native_checkpoint已有有效ACK，直接佐证。最低在现collect/poll/最终summary对对应event重新派生或晚更新；不安装/新遥测/重跑整轮，保expected未知与actual缺失/失败分别状态，不混成EXPECTED_UNKNOWN。
2. **scripted精确相等错判合法前已处理cp（:1583–1614）。** 声明戳是apply/request边界，v6复制最近前已处理组，非同值。正常请求980、实际975被标MISMATCH；已有E1早15.918ms/E2早12.415ms会同样被误列。最低分request/quarantine边界与actual cp合法关系，不用精确相等，也不加模糊容差追通过；晚于边界和不支持范围仍明确FAIL。当前tests只喂同步ACK与精确等值，不证真实异步接线，本机没跑204全库测试。

旧restore_disposition仍trigger-margin替实际cp，在线ep0请求记录与真实cp差数秒，上一核验保留，不重复控制；只记录不改实际恢复行为。此metadata收口可并行，不挡原生最小解除或真实I资格。

## 4. 修复42全在声明注入窗之后：实际应用不等正确测量修复

本run relay声明注入 `[1627785276215170145,1627785282215170145]`、z+.5m；ep3修复扫描范围 `[1627785295446205139,1627785299554250717]`，**全部在注入窗之后**，修复估测bias+.75m并实际施加纠正。这里没有证明这些扫描正常，也不直接判全部错误，但不能把42应用称注入测量已修回。它们可能是污染状态影响后的ICP偏差/参考问题，尚未可核唯一原因；原生从较早cp重处理也含声明注入区原始输入，suffix不是独立确认干净。

最低S1/S3用本run已有repair scan时间/实际过滤点、候选物理位姿/参考及标签出处说明修复对象和对应评价：点测量确实错误，还是估计状态误差被错误转成点z偏置；报正常后继误干预/完整原始损坏窗未修/缺测。不要以bias数、ACK42或committed11证明收益，不调门或新大实验来制造接纳。已有声明注入标签仅离线授权可复用，独立正常参照/效果标签仍缺，缺项NOT_EVALUABLE。

## 5. cand_0004是真实未决异常，末HEALTHY不抹除

ep4候选41，决策时报`RuntimeError: No active quarantine segment to validate`，ep4恢复action只有wall null无ACK，lifecycle unresolved4。开发已定位这个正常active segment与driver episode不一致，接受其负结果公开；**不能把errored计安全拒绝或成功后继恢复**。最低S1沿已有segment/episode身份与关闭时序核为何已关闭段仍决策，接既有生命周期同步，不扩恶意输入/并发防御框架；修后对应最小控制和有限后继证据。其他三拒绝只rollback/NOT_REPLAYED，完整历史追赶继续NOT_IMPLEMENTED，不能以未来输出替代。

## 6. T2新结果仍为回报，差分scan_last算法不是身份凭证

COLLAB§136报告S3旧115734 T2 I504/rank6、120块全UNKNOWN/尾51单列、1.97s/218MB；main和新online归档均无T2运行实现/manifest/输出产物，记 **DEVELOPER_REPORTED**，不冒本机实测。前轮fa35519还未合本目标，不指控已忽略；旧scan_first−1解释纠正接受但新“上一不同last < stamp ≤ 当前last”只是分箱规则，**不是由原成员/点时间证明的同扫描/同更新**。live/replay时间回退、group多对一和double量化不因此消失，不把人工prev-last填作真实first。最低上传已做T2脚本/行级关联manifest/结果原件，先核source成员与实际mat_pre/out对应，无法核则I资格未知，不rank6冒Sigma来源或直接−vec6冒精确SE3。

上一轮已证host旋转body/平移world混合约定、最终v7u源码绑定不足与事后删尾段分母仍沿证据保留，不重复数学/旧946帧控制。完整人口全部尾/phase/缺块/UNKNOWN与失败保留，条件子集另列，尾无标签NOT_EVALUABLE。ALI-B2正常校准/事件标签阻塞确认仍空；两类证据分别解除，不重复既有离线注入授权，不代选C。

## 7. 下一单一交付、旁支与验收

**下一实交：纯在线合法回退范围→物理一致实际修复→原生重估/地图→全部input归宿及后继闭合；本次部分执行直接复用，无法支持部分显式拒绝。** 不重复混合scripted/trace矩阵追成功。S1单写rolling合法性、active episode同步与实际成功依赖；S2沿在手宿主接口支持合法时间及现buffer重推；S3现真实I资格/已做T2原件、修复对象物理一致/正常代价与校准标签范围并行。本机S4保持自动审阅/2h/日报/截止，无Codex/旧手调停、不代ROS/算法。

只有合法cp/真实测量与状态对应/实际active段影响当前安全/评价须先做；ACK派生、上传现T2来源与清单修正并行集中，不让每字段挡重估，不要求全生产框架。遇真需超授权/输入不可得/能力不支持且用户需选，立即中文重大阻塞，只停被阻部分；现已授权未受阻工作继续。

下次逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+实际命令/输出原件+影响/下一动作，实际source/input/lib/config、cp与qstart、原损坏窗/实际修复扫描与正确/误改/未知、未配对/全部phase与缺块、native applied/dropped/success、异常未决与后继input、独立校准标签、资源/完整服务代价。NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE保留，不204tests/all_ok/HEALTHY算成功。A2/A6/A10局部自动执行实证增加，A4/B2前两边界FAIL、A5/A8/A9/完整B4/B11未闭合，A3/B3原检测自动执行非ALI性能。局部不全表总分/历史分；中文review现SSH白名单发布，不合main/历史/生产算法/冻结门/private/开发日报。
