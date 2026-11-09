# 主线/旁支验收 291a0dd

范围2a6f2ac..291a0dd，一笔6文件。完整读115行score generator，AST语法、归档两run hash与receipt.output、首输出戳关系核对通过。未真实bag重跑，无新native control，未重复主单测。

接受first_output/first_scored/onset/gauge定义分开、补生成器及因果限定。T1/T2归档output hash和receipt逐项对应，旧11.3mm/1.95mm未逐值复现但新8.7/3.9mm onset统计均低于5cm，模式不稳定观察未改变。当前应叫协议明确后的重新测量，不称旧数字digit-perfect复现。

主线本轮没有新的确定性改进，只补可追溯评测保障。下一交付直接T3a只固定measurement grouping的patch/trace与运行（same串行baseline/config/rate/prefix），actualgroup IDs和state变化，或明确BLOCKED。若它仍不稳再T3b固定IMU窗，不同时改两个因素。不要求再单发本意见措辞确认。

旁支可集中：gauge prefix/匹配为空时需显式缺测，onset用nearest ts应记录dt；generator只列receipt hash未fail-closed对比，当前归档本机比对成立，后续真执行把身份assert与actual ns加入。不要为这些日志项单独重跑host，trace实施随主线带自检。

开发侧§10.12 PASS/FAIL/BLOCKED/NA+命令证据，报告本轮只是旁支与下一主线安排。已有hall条件收益/room失败/重复不稳保留，T1/T2未消除不稳定并非排除全部归约/调度贡献。今日日报主线执行与评测纠错分开。
