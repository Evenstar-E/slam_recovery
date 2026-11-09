# 主线/旁支验收 5f2284f

范围29d8c7f..5f2284f，3笔、23文件。完整读89行repeat divergence、159行重复评价、receipt强制增量及审计规则；本机11/11 two_by_two审计fixtures PASS，核八新增receipt输入hash/status与逐run样本数。未本机bag/ROS实跑，大JSON核关键schema和来源，不声称外部数值独立复现。

## 主线实质推进

新增O和组合格各四次native重复，八收据OK、sources unchanged且输入hash与此前verified包一致。归档O四次BAD/GOOD/BAD/BAD，组合UNCLEAR/UNCLEAR/BAD/BAD，支持当前配置同输入单次结果不稳，单run无法承担精细因果归因。连续/中间结果保留，不强行叫二值双稳态。旧eight-run input/output/config门禁本轮落实，旁支收口通过。

## 主线解释需收窄：未对齐坐标不能定位初始化首处分歧

analyze_repeat_divergence.py:5-8直接假设两世界系因同input/初始化而相同，:62比较原xyz，:63比较原quat。但独立run首output时刻相差3.4s，地图原点/姿态基准可能不同；同bag不证明gauge相同。首次匹配记录差1.59m/.122rad既可能是frame gauge，也可能有真实误差。当前没有健康前缀对齐或relative pose控制，因此不能定“split在窗前已被初始化种下、与窗内因素无关”。

最低解除主线：复用已有输出，将共同健康时段拟合单一SE3，报告aligned early residual与相邻relative motion、首输出/初始化IMU/同步帧ID；找首个物理一致性的分歧，不把首次可观测匹配时刻当算法首个分歧。后续必要native run只针对一项初始化/同步条件冻结改变，不能靠调seed/挑median制造稳定。

## 重复评价是描述，不是发生概率或通用sequence不可用

run_bistability_analysis docstring说common set，但_score每次用自身可用ids，O323/组合326，非各run共同集合；缺帧应并列，共同集合和全服务两口径分别报。当前大幅差异有价值，GOOD1/4或pooled2/6是观察比例，n=6不足概率模型，“sequence unusable”只限此host/config的single-run比较，不是数据集本身不可用。

代码crosses_modes把BAD与UNCLEAR不同也叫跨mode；不能据此保证确实有两个吸引子。GT full alignment依旧诊断。新结果未全绑定receipt输出hash于_score消费路径，已有强制receipt函数应复用；源和评价身份门禁旁支集中做，不重跑所有数据。

## 分工与自检

| 类别 | 下一交付 | 验收 |
|---|---|---|
| 主线 | 共同健康prefix gauge对齐后的early relative pose/sync首处分歧定位 | 使用已有输出，先消除frame混杂；机制未知保留UNKNOWN |
| 可并行旁支 | 全run/common支持定义与output hash核验、audit负例 | 不用日志完善阻断有效对齐分析 |
| 延后 | 大模型/随机新场景/挑median当方案 | 等定位可操作瓶颈 |

开发侧先§10.12标准自检PASS/FAIL/BLOCKED/NA，报告真实repeat与posthoc描述分开。此轮有主线实验推进，但稳定性因果和修复泛化仍未证；不把测试数量当主线，也不把gauge差异算有效模型失败轮。今晚日报如实记录。
