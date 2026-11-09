# 主线验收 1388013：shared-base M3重算

范围86c481e..1388013（65ce1d4、1388013），此前并发合并未验收；本轮无其他远端增量。不审自己的708c187。完整读M3增量及当前结果；本机语法/JSON计数与集合不变量核验，不运行真实bag。未改主算法，未为测量协议重复跑41条主测试。

## 主线推进：通过两项评价修复，结论保留条件性

C3明确vstack相同base与repair，Q就是同一base；主ROI改为完整clean参考，与C3输出pose无关。关闭上轮两个M3评价阻断。归档覆盖7797828→8421708，差623880，与newly_covered逐项一致，主ROI8490000，+7.3484pp。missing_repair46、written532与132+400一致。只隔离对照与实际修复现在可讨论同proxy内的新增覆盖及代价，不再比较两张没有shared base的图。

当前仍是250点/frame sidecar、clean proxy非GT、离线native重估，不是在线宿主地图修复证明。M2历史runtime receipt限制保留。

## 主线解释需调整：不能用恒等式否定覆盖价值

所有新增覆盖位于Q支持之外，是newly_covered=(C3 covered AND NOT Q covered)的定义；敏感性ROI取Q已覆盖集合，两臂因C3包含Q都100%也属定义。它们不证明增量“仅来自轨迹覆盖”或“与修复质量无关”。修复正确性可能正是后段观测能在正确地方覆盖proxy的原因。

同时coverage独自不能证明质量，这点正确。无需立刻选择权重形成胜负分数；应在同一固定后段帧上比较base+raw/native、base+filtered/native修复、必要oracle控制，分别报新增proxy覆盖及unsupported。这样分离“多写了帧”与“把同批测量修得更好”。已有输出可重建；新host rerun仅在来源或条件确不匹配时需要。

## 主线结果的另一分母必须保留

C3总unsupported11183-Q1874=9309，是全部新增repair贡献的unsupported；“novel points”中4318只对应离Q>0.5m的15112点子集。其余新增点在Q附近也可能失败：9309-4318=4991。只报71.4% novel supported不能代表全部修复新增点的质量。归档绝对数没算错，需将100000全部added points、15112 novel子集两层同时报告，避免用子集低代价覆盖整体代价。

proxy点数按原点密度加权，不是面积或独立几何单元；将623880称proxy sampled points，非623880独立正确结构。以后若做面积/体素去密度统计，先固定协议，不因看结果改变ROI。

## 交接分工与自检要求

| 分类 | 下一交付 | 阻塞/验收 |
|---|---|---|
| 主线 | 相同base/ROI/后段scan集的raw-vs-repaired新增覆盖和错误贡献对照 | 检验修复是否优于单纯多写帧；保留缺帧与proxy限定 |
| 可并行旁支 | snapshot/base hash、paired query ID、全部added vs novel分层、缺字段负例 | 集中处理，当前已有输出可评价，不要求清完旁支才跑主线 |
| 延后 | 新宿主、学习模型、主观净效用权重 | 等可靠同帧对照定位瓶颈 |

开发侧每轮先按§10.12自检，再交接PASS/FAIL/BLOCKED/NOT_APPLICABLE与命令/证据；不能只回复tests总数。此次有主线实质推进，应明确归档重算而非本机独立实跑。下一轮交付同帧对照，不另发一笔纯“已修改措辞”确认，不机械扩多代理。

## 旁支非阻断

源hash检查/receipt等既有问题仍按相关运行范围处理；shared base最好导出content hash以证明literal identity。主ROI已不依赖candidate；基座支持ROI只作敏感性正确。不能称本轮恢复闭环全部完成，也不将有限proxy对照不足再包装成新增软件bug。
