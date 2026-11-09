# 主线验收 b64e22c：八次原生2×2运行

范围218e697..b64e22c，4笔、23文件。完整读204行新builder、198行analysis、117行independent evaluator及oracle builder增量；八receipt逐个输入/config/binary hash、结果字段本机核对。未实际bag/ROS重跑；大JSON只核关键来源与计数，不宣称全bytes复现。

## 主线实质推进：重复运行成立，机制仍不可定

八份OK收据按两次/格消费同一套single_factor_bags_verified输入，config/binary相同、sources unchanged。O及组合格各有一成功一失败的full-alignment诊断，足以撤回单次“filter已定因”的主张。两个单因素格都失败两次，预注册的“单因素均成功、组合均失败”形态不成立。

可称本次重复不稳定、未支持该特定交互判据；不能称交互不存在、方差统计上压过所有因素或host真正双稳态。n=2/格不能估可靠分布，缺同步/初始化/运行环境状态对照，重复差异不一定来自随机seed。不能仅改成median或挑初始化让成功当作控制方差。

## P1评价有效性：构图扫描不是宿主实际消费的包

run_2x2_analysis.py:39-42读room02_inj43_O/OF/OB/OFB；receipt input是room02_2x2_O/O_plus_F/O_minus_B/O_plus_F_minus_B。两套manifest hash均不同，且新build_2x2_bags.py:120-121窗外保留全部原始行，已验证single-factor构造窗外保留actual-filter行。不是仅bag重编码差异：观测策略确有不同。

因此新脚本把旧套host poses用于另一套cloud，map coverage/unsupported不能作为真实该运行效果。最低解除：analysis直接从各receipt消费输入路径/hash读取对应cloud，保存output hash关联；用已有八输出重算即可，不要求重跑全部host。ATE独立读poses仍可作限定诊断，不因map错误全部撤回run。

## P2：frozen-prefix ATE坐标系不成立

analysis :109-111拟合run→clean-run世界系；:145将该transform直接与GT坐标的mg相减，未再做clean→GT frame校准，故“协议ATE”包含坐标原点/方向差。O#1 full diag .0716却prefix3.812不是同协议可解释对照。应在预先固定健康GT支持拟合run→GT，或有明确的clean→GT冻结变换；不能full-window再拟合却叫prefix。GT孤立outlier策略也应按固定协议统一，不每次改规则。

独立evaluator服务标75ms nearest不同于生产20ms nearest/75ms bracketing interpolation；ATE亦用各run全输出GT支持而非323公共集合，所以数字差不等于两方法不一致。报告两个定义，不把“同数量级”当逐值复现。

## 旁支与下一主线

修输入读取及frame-transform属于评价真实阻断，最小工作是已有输出重算。其它oracle报告、文件日志集中并行。outside窗口独立声明已在build_oracle_bag修正，但新build_2x2_bags又以min/max差异推窗后做恒空检查；实际消费的已验证包不来自此新builder，勿混宣称。

下一主线先正确重算八次，固定公共时间支持和GT坐标后定位重复早期状态/更新序列差异。若仍不稳定，选择一项预注册初始化/同步对照或将native-run稳定性作为必要失败边界；不要再扩场景追成功、不直接叠模型。两因素结论保留UNKNOWN，oracle仅机制控制。

开发侧每轮§10.12先自检PASS/FAIL/BLOCKED/NA、证据和主线/旁支分工，实际消费hash需贯穿构图与评价。负结果和不稳定是研究推进，但无效map/prefix数不计有效模型失败轮。今晚日报记八run推进与评价待纠错，不把NOT_A_CLEAN_INTERACTION译成无交互。
