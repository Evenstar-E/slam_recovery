# 自适应低信息健康状态 V1：设计与有限测试交接

读者：用户、开发S1/S2/S3与独立复核者。方案简称 **ALI-H v1（Adaptive Low-Information Health）**。

## 0. 用户直接授权、版本及边界

用户2026-11-12直接要求：“你设计一版，然后并行接着做审阅的自动化工作，你设计好后通过github给开发侧做测试”。本文件是对此请求的设计与测试任务，**明确授权范围为开发侧的有限隔离方法测试**，不是本机实现算法/运行ROS，不是立即替换生产检测器/准入门。它允许本方案的隔离实现与有限验证，覆盖此前“新的可用性方法等待选择”的限制，仅限ALI-H v1；不解除旧sigma/κ/floor调参暂停，不顺带批准双参考大矩阵或其他未选方案。

设计源码基准：`5f54a449650e203a1c1d3bba29486a8476fb53ae`。本机已核同版本JointHealthDetector、step_frame/UNAVAILABLE入口；原生最新两事件运行另并行审阅，不能据开发“完成”标题直接验收。现20min审阅、2h总结与日报由repair-f3实际持有，继续，不新增重复自动任务。

分工保持 **1研究+2原生**：S3负责本方案的隔离研究，与已有门A/B/C研究使用同一研究时段/预算，安排顺序并回执，不占用S2重开诊断运行；S1负责接口审核和后继集成的唯一写入责任；S2继续native state/map→接回→E2。可复用S2已有trace，若确实需要导出少量真实健康证据，由S1/S2随原生已有运行顺带导出，不让研究挡原生。

状态：**DESIGNED / NOT_IMPLEMENTED / NOT_EXECUTED**。本文中的新配置/字段是建议契约，不伪称已存在。开发需报告实际branch/HEAD/文件/预算与认领状态；GitHub发布不等远端已收到/执行。

## 1. 要解决什么，不解决什么

当前 `available = support_pass and nis_present`；support是200个确定性抽样点至少60%在参考点1m内，不是单FIM信息阈值。UNAVAILABLE时绕过detector.step，仍可能进入延迟trusted提交；已知诊断402paired中285比例不足、22参考空，306不可用帧仍有fresh有限NIS。预测pose50帧改善/47反向/301都低只能证明support敏感性，不是真实漂移/覆盖的独立标签。

**核心改变**：把“证据条件”与“健康结论”分开。低支持/弱信息不等异常，也不等正常；每个paired帧都更新一个健康观察状态，即使地图判据不可用。只能在确有正向证据时判倾向正常，证据矛盾或不足时允许UNKNOWN。

V1是**信息条件化、可弃权的状态观察器**，不是改几个支持阈值，不输出没有训练/验证依据的“正常概率”。不解决缺测背景重建、不生成几何、不把candidate自产图或故障真值喂给在线模型，不以预测pose与自身图一致证明健康，不承诺每个低信息帧都能二分。

## 2. 输出：两轴状态，不新增manager生命周期

```text
information_context:
  map_support = EMPTY | LOW | SUPPORTED     # 沿旧1m/60%原值，保fraction和原因
  observability = WEAK | ADEQUATE | UNKNOWN # 沿旧声明FIM诊断基/尺度；只作上下文
  reference_source / age / reference_id / calibration_id

health_observation:
  NORMAL_CONSISTENT | SUSPECT | UNKNOWN
  scope = RELATIVE_MOTION_ONLY | MAP_AND_MOTION | NONE
  usable_channels[], missing_channels[], reason_codes[]
  observed_at_ns / evidence_span_ns / calibration_status
```

组合例如LOW+NORMAL_CONSISTENT、LOW+SUSPECT、LOW+UNKNOWN。**NORMAL_CONSISTENT仅表示声明范围的观测与正常条件相容**，不是全局定位正确/有独立GT证明。RELATIVE_MOTION_ONLY不能被包装成地图/绝对位姿健康。

复用现JointHealthDetector的HEALTHY/SUSPECT/QUARANTINED及manager状态；ALI-H是旁路观察，不把UNKNOWN伪装成第四个manager状态。研究日志保存两者，旧CUSUM不喂零/旧值冒当前观测；shadow阶段manager/native所有原决定保持不变。

## 3. 最小真实输入：区分可用证据与占位数

| 通道 | 可复用量/声明 | 在低支持时能做什么 | 缺项时 |
|---|---|---|---|
| M 地图残差 | 当前raw NIS/residual、真实node_map参考、局部覆盖、query/reference身份、参考age；沿compute_disjoint_holdout_point_to_plane_nis采样/面，不新建ICP | 在参考对应确可信且有匹配校准条件时，异常残差可作地图不一致证据 | 不因数值finite即“可信”，低覆盖/错误参考可能无法解释；UNKNOWN |
| T 邻帧一致性 | raw prev_scan NIS、scan配对dt、实际采样/覆盖及前帧身份 | 可提示短时测量/相对运动不一致；**不能单独证明正常或绝对位姿正确** | carried_forward没有新证据；不当当前raw |
| I 运动一致性（V1首选新真实量） | 宿主在本次LiDAR更新**之前**的IMU预测与更新后位姿/旋转增量，以及预测误差协方差/实际dt/滤波版本（若已有导出）；同一物理frame/tangent比较 | 在声明可观测方向发现LiDAR修正与IMU预测冲突；支持低时也可使用 | 目前未核已导出；没有就NOT_AVAILABLE，不自建另一套惯导/零bias predictor |
| V 可选真实视觉证据 | 已有宿主实际跟踪失败/重置或真实创新，绑定传感器时刻/跟踪支持 | 在实际使用视觉且有校准时补充；没有不用 | 不为V1新造视觉模型/无视觉不阻基础研究 |

M与T同源LiDAR，不能当两个独立传感器投票。I虽不同模态，但共享滤波历史，不宣称统计独立；高一致性也不能排除共同偏差。V1首版使用已有M/T与**若可直接导出则用I**，V不作为前置。

源码现实：step_frame默认loso_primary=.5/aux=.5、sync_lag=0、loop_spike=.3；当前在线调用未传实际多传感器值，这些是占位，不得进入正常证据/训练。BackendDelta当前velocity/bias也有零值，不能当真实宿主运动。`nis_q90 = value*1.35`是合成量，不当实测残差分位数；ALI-H用保存的真实残差分位。当前scan FIM以sigma=.075计算，不能和LiveNis .884混作同一噪声模型。

I的建议标量（仅真实数据可算）：

`e_I = Log( inverse(DeltaT_IMU_preupdate) * DeltaT_host_observed )`；其中两个增量对应**相同实际起止输入时刻/同基**，定义并记录传感器外参。用真实预测innovation covariance在可观测子空间算 `s_I=e_I^T Sigma_I^+ e_I`，记录有效rank；协方差缺失则只保带单位残差，不能补单位阵、不能宣称卡方概率。平移与旋转分别保留，不把米/弧度无声明相加。这里不是提供独立GT，是明确的跨模态冲突证据。

## 4. “自适应”的具体实现：固定规则按上下文选正常参照，不在线追异常调门

### 4.1 第一版可复现的条件校准

不沿已有全部UNAVAILABLE分布估“正常”，不拿manager HEALTHY/trusted标签作健康真值。使用**指定的无注入健康前缀或单独正常开发输入**，由独立离线证据确认其可用范围；健康标签只评价/离线校准，在线不读注入窗/故障GT。若原bag自然退化，不能仅“没注入”就称正常。现hall/room已开发，不称新held-out。

按实际通道分别建立经验正常参照，条件键只用两项：
1. 通道来源 M / T / I；
2. 旧map_support上下文 EMPTY / LOW / SUPPORTED。

每个参照同时记录校准中的dt、参考age、query覆盖、有效rank（适用通道）的**实际支持范围**。在线若落在未覆盖条件，该通道calibration=OUT_OF_SUPPORT，不从最近高支持格子硬套门，不叠fallback。I缺校准、LOW健康样本缺失都可以BLOCKED；保留连续原分数，不能造NORMAL分类。

健康校准按**非重叠0.5s传感器时间块**取分数中位数，不把点/帧当独立样本。每条件至少20个有效块才启用探索分类（10s有观测的校准支持）；不足INCOMPLETE。20是首版研究支持声明，不是统计保证，不能不足时反复改小。

对当前块分数 `s` 在相应正常参照 `B_c` 下计算异常百分位

`u_c=(1 + count{b in B_c : b <= s})/(len(B_c)+1)`。

它是**经验异常次序分数，不是校准的故障概率或严格p值**。分数越大越异常；来源不同分别校准，绝不直接比node_map NIS与prev_scan NIS数值。协方差有效时记录物理归一分数，无协方差保原量，用经验参照比较。

### 4.2 冻结首版探索配置

- 时间块0.5s，传感器戳而非机器负载wall time；块内同通道至少有一个真实fresh样本，缺样本标missing。
- 通道alarm：`u_c >= .95`，持续两个**相邻有证据**块；旧检测min_dwell=2思路复用，新shadow用明确秒尺度。
- 通道normal-compatible：`u_c <= .80`；.80–.95为grey，不强分。
- 不修改旧1m/60%、NIS sigma/κ、FIM门/准入P0–P5。上方新值是一次冻结的**探索观察器**配置，非确认有效性门；同数据最多报告这版，不扫描参数追好成绩。
- 不在故障/隔离/UNKNOWN期更新正常参照，V1确认阶段也不在线更新。自适应体现在**上下文切换和证据可用性**，不是跟着异常降低阈值。先验证这版，再研究因果更新/更复杂模型；不要一开始在线自标注污染基线。

### 4.3 UNKNOWN与时间状态

若可解释证据缺失：输出UNKNOWN，原异常累计不吸收0、不假装正常，也不对跨缺测的块加dwell。一个SUSPECT后遇缺证据可输出UNKNOWN，但保留last_suspect/首次证据时间供追溯，**缺证据不是解除报警的依据**。

若只剩T通道正常、或只有同地图上的预测pose支持通过，仍UNKNOWN（可报告RELATIVE_MOTION_ONLY的相容观测）；预测pose不是真值且非独立，不能作为NORMAL充分证据。新证据恢复后按实际新块重新判断；onset只回溯到首个真实异常证据块，不能把缺证据期强行估成精确起点，报告可能漏检区间。

## 5. 冻结的判决表：先证据资格，再状态

`positive_conflict` = 至少一条**可解释且条件校准覆盖**的M或I通道持续报警，或已有真实host hard-failure/reset事件（非默认placeholder）；不要求等support通过才报告SUSPECT。

| 可用证据（满足其身份/条件支持） | ALI-H状态 | 解释 |
|---|---|---|
| positive_conflict，不论map_support高低 | SUSPECT | 报告具体冲突，不断言漂移唯一根因；T单独alarm仅称measurement_conflict可疑，不称pose/map错误 |
| 无报警、真实I normal-compatible，且另一实际观测通道M或T normal-compatible，持续两块 | NORMAL_CONSISTENT | 若M合格则scope MAP_AND_MOTION；只有I+T则RELATIVE_MOTION_ONLY，不授予绝对地图正确 |
| 只有M通过且无I（或I未导出/未校准） | UNKNOWN（低信息路径） | 不能凭同源地图自一致确认正常；旧高支持检测决定可另外保留，不强制换它 |
| 仅T正常，预测支持改善，或无参考/缺NIS/沿用旧NIS/全部灰区/校准外 | UNKNOWN | 保留原因和缺证据人口，不补零、不勉强二分 |

T单独持续alarm可给SUSPECT、scope RELATIVE_MOTION_ONLY、reason MEASUREMENT_INCONSISTENT；不得用其normal alone降为NORMAL。M低支持仅在其实际局部参考/对应及正常条件分布足够可解释时作为冲突，否则M失格；需要保存该资格证据，不能把fresh finite等同qualified。

信息弱本身不自动触发SUSPECT，仍保WEAK上下文和风险范围；它可能是正常廊道/运动条件，分类必须来自有意义的状态/测量冲突。若真实I在当前方向也不可观测，normal资格不足则UNKNOWN。

**绝不能输出：**全部低信息已分正常/异常、预测通过等于真实健康、经验u等于异常概率、两个LiDAR统计等于两个独立证据。不可分情况就是预期边界而非测试失败可删除项。

## 6. shadow实现与后继状态动作分开

第一阶段只新增研究观察输出，不调用manager/native恢复，不把LOW+NORMAL_CONSISTENT换成step_healthy捷径，不改变旧detector/日志原值。既有HealthDecision/state与ALI-H的timestamp/result同时记录，可复用availability sidecar，不动冻结candidate schema。

用户希望区别正常/不正常，**改名不等修复检测盲区**：shadow只判断是否可区分。若验证有用，后继集成建议如下（本轮不部署）：
- SUSPECT：把真实冲突送既有suspect/quarantine入口，低支持不能独自屏蔽报警；保正常onset/margin/可信cp约束。
- UNKNOWN：不得宣称已正常；可研究“有限pending、不能默认为可信”的状态动作。具体超时/原生map_hold/输入追赶必须与S1现事务接口整合，并明确成本，不在本轮新造无限缓存/通用框架。
- NORMAL_CONSISTENT：按声明相对/地图scope使用，不因相对运动相容就无条件提交绝对地图。

**生产集成须另交策略差异与有限原生对照，用户确认后再采用。** 本次明确请求授权设计/开发测试，不推断授权上线门结构替换。单个观测方法通过也不解除已证native checkpoint/写回来源等主线问题。

## 7. 测试方案：先已有数据，再至多一次必要的真实导出

### T0 现有数据可回答多少（不重跑宿主）

S3先读两个已有402/544行diagnostic archive及source绑定。输出本版每块资格/上下文/缺项、shadow结果；**无真实I/M低支持校准就UNKNOWN**，可计算支持状态/分数但不能假称正常或给故障率。旧资料缺参考点/独立标签，不能用后来map重建冒旧参考。复用正常/异常边界、kf157 node_map高NIS但support低、空参考、预测反向47作为针对性案例，不扩极端异常矩阵。

已知T0可能大量UNKNOWN，这说明有真实信息缺口，不算新检测算法失败，也不算解决了盲区。准确报告能证明的分类与不能证明的范围。

### T1 最小正常反例与不变性（本地研究代码，不必ROS）

只做与设计直接相关的几个构造控制，全部标synthetic/unit，不称真实恢复：
- support低但真实跨模态一致→NORMAL_CONSISTENT限定scope；只T一致→UNKNOWN。
- support低但真实合格I/M冲突→SUSPECT，不因可用门屏蔽。
- 无参考/无I、carried NIS→UNKNOWN，missing不喂0；缺测不清除历史suspect。
- M/T相同数值不同source使用各自校准；没有LOW健康参照→OUT_OF_SUPPORT，不借SUPPORTED分布。
- 同物理残差的坐标重表达/输入时刻契约正确；仅检查新数学用到的已有SE(3)工具，不重做全gauge工程。
- shadow开关前后旧可用性/NIS/准入/manager/native命令相同（限定实际控制），不靠测试数宣传。

### T2 仅在T0有明确可解除缺项时的有限trace

首选S2已授权native运行中可复用的真实IMU preupdate/update创新trace；没有就S1确认现宿主导出位置、成本与**一次**现输入/预算内的短诊断导出（正常前缀+已声明退化窗+恢复尾段）。不改变检测/注入/host行为，不为新算法多次调整故障/参数，不加宿主/序列大矩阵。研究运行不得占用第二个native会话整轮；资源超已有预算BLOCKED并向用户报，不自动安装/下载数据。

只研究已有退化类别。自然故障有独立标签则纳入；自注入标签仅评价，不能从scripted trigger或manager状态生成训练/评价真值。原数据不足以支持正常低覆盖/真实异常标签时，报明确NOT_EVALUABLE，不临时扩dataset追完成。

### T3 配对评价与停止

旧方法和ALI-H**观察器**在同一保存trace/source/calibration上对照，分别报告：
1. 全paired及全部消息/未配对；旧UNAVAILABLE中多少SUSPECT/NORMAL_CONSISTENT/UNKNOWN，每格分母和scope。
2. 独立已标事件中的漏检、延迟/起点误差、正常段误报/小时；未标人口不当负例，UNKNOWN单列漏检上界/未判范围，不静默删除。
3. 低信息正常误报、低信息异常漏检和错误NORMAL数量/时长；拒绝分类覆盖率与风险一起报，不能靠全UNKNOWN获得假零误报。
4. block/事件级趋势与效应量，人口小时不足只给count/exposure不声称稳定率；不把相关点当独立样本。
5. 每帧/块耗时、峰值内存/输出量、实际采样、未知/输入缺项；shadow无map动作，因此真实地图损害/恢复收益NOT_EXECUTED，不冒安全提交已验证。

V1在T0/T1+一份足够trace后停止并交结论。若来源身份错、I不是真实preupdate、低支持参考不可解释/标签不足，STOP/BLOCKED；若仅靠T/预测能得到“正常”，FAIL设计实现。若LOW+SUSPECT增加同时大量正常误报，保负结果并报告取舍，**不扫sigma/κ/.95/.80或support门找通过**。当前是探索性研究，最小收益/非劣界限UNDECLARED；不看结果补门宣确认成功。没有证据优于现状就不推荐生产部署。

## 8. 最小交付文件与自检

开发可自行用现仓库研究目录组织，建议单一`docs/ali_h_v1_research/`（不存在不写已存在）；实现位于独立research模块/branch，不S3直接抢写manager/recovery共享代码。交：
- 设计契约实现版本/config/calibration manifest（normal来源、时间分割、source/frame/外参/cov、块及上下文支持范围、所有缺项）；
- shadow JSONL：run/source/scan/pose stamp、每通道raw/source/fresh/age/资格与原因、information_context、u、state/scope、证据起止、旧决定；坐标/hash引用复用原工具；
- 固定版本/人口的T0/T1/T2实际命令/输出、配对评价和资源，负结果/UNKNOWN/无法分类范围；
- 自检每项PASS/FAIL/BLOCKED/NOT_APPLICABLE+证据+下一动作。未实施/未运行明确NOT_IMPLEMENTED/NOT_EXECUTED；独立证据未导出不填占位。

S1回实际认领、S3研究顺序/已有预算、S2提供trace是否可复用；不用另造仅“收到规则”周期。算法实现与真实执行属开发，本机只设计/核验/自动审阅。A3/B3可能推进的信息条件化检测证据，A1/A11/A12支持追溯；观察器不会自动提高A6/A8/A9/A10/B4/B11或A/B总分。

## 9. 一句话验收

**低信息时，有真实冲突就能报告疑似异常，有足够正向证据才报告限定范围的正常相容，不能区分就明确UNKNOWN；用同版本完整人口证明漏检/误报/延迟取舍，而不是把UNAVAILABLE改名。**
