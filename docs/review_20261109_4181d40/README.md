# 主线验收 4181d40：room_02独立确认负结果

补验c64c872/4181d40（上轮并发未审）；本轮无更多远端增量。不审自己的ce393e3。完整读确认脚本增量、clean conversion、receipt及结果核心字段；本机重算healthy filter计数、失败计数/分母和hash记录关联。未真实bag重跑，不声称独立实场复现。

## 主线有实质推进：接受条件性负结果

clean参考由原raw room_02转换，归档599同戳、199修改、400相同，clean standard-image配置输出864 odom且receipt OK。clean输出hash与结果记录一致，旧候选clean输入错配BLOCKED得到解除。外部bytes本机无法核，来源关系以远端归档为准。

同326/398条件帧，raw coverage .76722→C3 .69515（-7.2066pp），patch unsupported .45853→.65896（+20.0429pp）；novel53027仅60 supported；lost15028 supported。分析规则两项不通过与多维恶化方向一致，不只是任意阈值失败。现有normal-window filter报告本机重聚合：400帧20576778点删除919702（4.4696%）、52帧有干预。服务326/398，72missing明确。保留失败，不调ROI/规则或删掉该序列。

可以说“当前过滤+native重估配置在此room_02代理确认未复现hall_01改善”，不能推所有room场景或所有模型都失败。hall_01单序列条件收益保留、跨序列效果/通用健康安全不获支持。C3失效有正常误删伴随，但尚未证明误删是全因，不能仅凭它决定要换学习模型。

## 下一主线：一次分解诊断，而非再扩序列

冻结该room输入/config/窗口/参考，先用已有输出和点mask分解：注入窗与健康窗分别统计错误位置/误删、前后状态误差，加入raw观测+高质量pose、oracle removal+高质量pose以及实际filter+参考pose。清楚独立/同源proxy限制。若oracle正常、实际filter损害明显，模型改进优先时序可靠性/正常墙保护；若测量较净但native pose仍差，优先重估/同步/偏置；若评价参考局部质量不足，先修评价。不要再花一轮解释单NIS。

必要的新native诊断必须基于证据选择一个因素（如实际filter vs oracle mask仅作上限），保持same healthy prefix和标准图像配置；不直接拼接参考轨迹冒充deployable修复。先适用标准自检并冻结要回答的问题，失败/未知都能推进机制判断。

## 旁支并行，不阻断已有诊断

room确认脚本仍读固定/tmp/filtered_bag_report.json、以毫秒容差分窗，没有核该sidecar身份；checked-inroom报告本机计数一致但脚本未来可误读hall旧report。改为room专属hash绑定sidecar和integer ns随诊断交付。冻结599primary只有count/hash，raw→paired缺输出未全列：对条件326与总体服务保持清楚，尽量按ns导出列表。无需为日志修复重跑全部host。

源恢复与clean conversion是主线输入真实性改进；runtime receipt和index/schema属于旁支保障。按§10.12每轮附PASS/FAIL/BLOCKED/NA、命令/证据、主线推进及旁支分工，不能说“41tests即确认失败原因”。此次不重复跑核心单测，因为模型未改。

## 止损轮次与创新主张

这可作为一次有信息量的独立确认负结果（若远端输入/评价自检通过），不是自动满足“三轮无改进换模型”。当前一正一负说明需机制分解与收窄适用域，暂不增加宿主数。对论文：支持失败可见性和有限离线修复链，否定现条件下跨序列稳定收益；尚无独立GT地图、部署/验证准入增量。今晚日报准确标注该关系，不把负结果归为无进展。
