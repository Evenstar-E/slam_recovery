# UNAVAILABLE逐帧与计算样本取证任务

面向开发主会话S1、在线执行S2与独立复核者。用户2026-11-12直接要求：弄清楚为什么出现UNAVAILABLE，逐次打印两个指标以及计算它们的相关指标。本机负责核源码/交接，远端实现并运行；不是再次解释标签、不改自动检测策略/阈值/模型。

## 1. 已核入口与当前缺口

源码核验目标 `e82d90041c090dcb8a9df6402ebfdb98f465a0b8`。本轮fetch发现新main，但其v3/clean A/B原件尚未完整审阅；不继承d193680旧缺陷为新target仍失败，也不据提交标题验收恢复。

当前recovery_node：`available = bool(supported) and value is not None`。`_record_diag`已有kf/pose ts、最终nis/nis_source/nis_reference/status、CUSUM/dwell/map_points/trusted_keyframes；没有support比例与分母、原始NIS失败原因和计算样本，`diag_cap=2000`后静默不记录。已有字段复用，不重新建通用日志框架。

- 支持条件：`_frame_has_reference_support`使用当前scan按T_wb变换到world、最多200个确定性抽样点，至少60%在参考点1m内。提前返回包括reference空、scan/pose缺失或无效、scan空。
- NIS：LiveNis优先当前位姿3m内至少30个trusted参考点，不足再用至少30点prev_scan；current至少10点才调用底层。底层train最多600/query最多300，最近8参考点拟合局部面，残差2m裁剪/70%覆盖决定使用全部或裁剪残差；非有限或无法计算时可能沿用_last_value。
- **纠正诊断理解**：覆盖<70%不会返回None，而是使用所有残差算NIS，可能得到很大的有限值；不得把“覆盖低”直接标成NIS缺失。沿用旧值也不是本帧有效新证据，必须分字段。

## 2. 最小实际输出：逐帧一行，先观测不改行为

复用当前诊断，增加流式JSONL（建议`availability_frames.jsonl`）写盘；每个实际paired frame一行、和本次decision保持相同计算入口，不受2000条summary内存上限静默截断。控制台每帧打印短摘要即可，不刷全参考点；点级详情写文件。无需改冻结18-key candidate schema。

### 身份及当时参考

run/source/实际配置绑定；kf、整数pose_stamp_ns、scan_stamp_ns、pose-scan dt、原header frame_id、实际T_wb、scan原始/有限/采样点数、manager state/active段、trusted version/key数。support参考cache key/version、上次刷新stamp/age、参考快照ID/hash与点数；NIS参考来源和snapshot ID单列。保存的是**评估时、输入更新可信地图之前**使用的参考，不能用事后更新map重新算再声称当时原因。

### 条件一：地图支持

- 是否具备reference/scan/有效pose，具体提前退出原因；不能统称no_reference_support。
- 实际radius=1.0、threshold_fraction=0.60；sampled_query_count、within_radius_count、supported_fraction、support_pass。
- 明确实际样本索引/抽样规则。复用半径索引返回的mask，不为打印先计算一遍再以另一遍结果判断。
- 点级保存body/world xyz、原始点记录row index（保finite筛行+stride到原row的映射）、within_1m bool、可用的匹配参考ID/距离。当前索引只需“是否有点在半径内”且找到即短路，**不能把任意首个命中距离叫全局最近距离**。需要精确最近距离作诊断时对保存样本/同一参考离线复算并标诊断，原判据不变。

### 条件二：NIS与分支

- trusted_total、位姿3m内参考数、prev_scan参考stamp/点数、selected_reference_source及实际选中点数；current点数、train/query实际采样数、sigma实值。
- attempted/computed状态，当前原始raw_nis的数值类别（finite/inf/nan/not_computed及reason）、最终用于检测的effective_nis、source computed/carried_forward/unavailable；沿用值的来源frame/stamp/age明确，不能把旧NIS填进本帧raw_nis。
- 底层实际holdout点的参考邻居ID（k=8）、面中心/法向与特征值、点面残差r、(r/sigma)^2、是否r<2m；total/valid计数、inlier_coverage、最终使用all_residuals或clipped_residuals的分支、mean/rms/分位数与最终NIS。没有执行的量写null和原因，不能补0。
- 可复算均值和coverage即可，不输出新confidence/阈值层，也不把相关点当独立样本做新的显著性结论。

### 合成最终原因

每帧保留`support_pass`与`nis_present`两布尔及**所有失败原因**（两项可能同时失败）。status必须可由两值重算；检测off另记DISABLED，不称真实UNAVAILABLE。当帧没送检测器时，不沿用旧detector state冒充本帧判断。

## 3. 不可用帧点级证据与有限人口

此次有限输入范围内，对**每个UNAVAILABLE帧**保存实际计算样本及对应参考快照：support最多200点、NIS query最多300/train最多600或所用邻居，不是每帧打印数万原点和整幅地图。参考快照按ID/hash复用、body/raw row映射沿已有完整点记录导出，不让几何/ID丢失。没有reference/没算NIS的帧仍保存原因、输入/pose及已有样本，不能完全无记录。

逐帧摘要覆盖本次全部paired人口，包括AVAILABLE，用作边界对比；至少保存边界附近正常帧的同类计算样本。只给“不支持点”的列表而无完整样本分母不能复算60%。如固定预算不够保存某部分，明确预声明人口/实际缺项和原因，不能2000后无声丢记录，也不默认扩大资源或下载新数据。

## 4. 执行与验收：得到原因，不只增加日志

1. **S1**认领共享诊断改动，复用`_record_diag`、LiveNis、支持索引及底层计算；可选details返回/旁路记录，默认计算、缓存更新时间、阈值与检测决定不变。小控制核诊断开关前后原决定和值一致即可，不扩异常单测矩阵。
2. **S2**先用已有可复算原件：若缺当时参考/pose/原点身份，直说不能回推，不事后造当时指标；在现有宿主/输入和预算内跑一次**检测on**的有限诊断，声明事件窗口只供离线定位，不通过scripted触发充自动检测。不新开参数/全宿主大矩阵；实际命令/运行版本由开发交付，不把建议新flag写成已实现。
3. 交按真实原因的计数及占比：参考空/支持比例不足/无NIS/非有限/沿用值/输入缺项，各自分母、允许多因重叠；画面或统计可后继，但先给逐帧原件。
4. 对UNAVAILABLE连续段交开始/结束ns、每帧支持比例及raw/effective NIS，检查进入前后pose/参考覆盖/版本更新。至少一正常边界、一不可用反例从保存点复算，能复算within比例、NIS mean和最终status。无确定因果则UNKNOWN，不从unsupported就推“必然漂移”。
5. 输出结论必须回答：究竟是哪些代码分支让帧未进检测器；是否出现有新异常证据却被前置条件排除；旧值沿用占多少；哪些原因已证、哪些仍需数据。不得以诊断文件条数或单个NIS当成自动检测已通过。

当前目标是**这一段UNAVAILABLE的实证归因与最小解除依据**，不让日志任务无限取代已授权native恢复/E2。原生主线可并行，S3门研究专用/旧参数仍停。若证据指向前置可用条件的结构盲区，再报告具体模型/算法选项及有限比较，不未经用户选择自动改检测门或放宽阈值。

## 5. 开发自检与发布

下一实际交付逐项`PASS/FAIL/BLOCKED/NOT_APPLICABLE + 实际命令/输出或原件 + 下一动作`：source/config/input/run、时间/点/参考身份、全population摘要完整性、支撑/NIS复算、诊断前后计算决定不变、自动检测实际on/非oracle、实测成本/缺项、原因归因和UNKNOWN。UNIMPLEMENTED/NOT_EXECUTED明确。A3/B3是本任务实际检测证据，A1/A11/A12支持可追溯；诊断本身不提升端到端恢复或A/B总分。

用户此要求是新的有限任务授权；本机只交接并沿既有独立review提交SSH推送，不合main、不改算法/历史/冻结门、不公开私人handoff或凭据。发布不等开发收到/实现/执行，S1下一交实际认领回执。
