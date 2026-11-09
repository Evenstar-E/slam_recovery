# 主线验收 067b8ba：八运行正确输入/坐标重算

范围328696b..067b8ba，一笔、7文件。完整diff核读、输入manifest/八output receipt hash逐个关联、两ATE分类和受控row-vector组合fixture本机通过。无新host运行，属于已有输出评价纠错；未真实bag重跑，不重复主41测试。

## 主线推进：关闭上轮两项评价阻断

ARMS现读room02_2x2_*，当前hash强制匹配已验证manifest；结果四map input和八run output hash均与归档identity一致。本轮正确input-map链核对可通过，未使用平行builder不同窗外策略包。

prefix评测现run→clean(prefix)再clean→GT(pre-onset177matches)组合，数学row-vector变换正确，clean→GT校准残差.09067m公开。O#1 corrected prefix.09264、组合#2 .31428，与full diag阈值同侧；旧3.8m/all8fail原点错配结论已撤回。接受保留预注册full决策变量不结果后换判据。

## 有效结论仍有限

八repeat显著不稳定，预注册特殊interaction形态未获支持；不能定无交互、真正双稳态、方差统计主导所有因素。两个重复不支持完整概率校准，不用median掩盖坏run。不能为了保证模型有效而无限修改初始化或阈值。

原oracle/base1pass1fail和actual1fail1pass提示需定位早期state/同步/运行差异。主线下一步选择一个预注册稳定性诊断：比较相同输入重复的早期pose/IMU初始化、有效scan/image时间分组及状态更新，找首处分歧；若不可控则明确适用限制与改进方向。不要继续仅审计旧ATE数字、也不再扩随机场景追成功。

## 旁支集中

analysis记录output hash但尚未runtime强制逐receipt验证实际input/config/output链，可以复用现identity映射；空/missing run结果不应false interaction/noCell成功。已有健康独立参考和calibration支持限定保留。未宣称当前归档缺失，因为本轮八全部存在且核对一致。

开发侧先§10.12自检PASS/FAIL/BLOCKED/NA，交接主线纠错完成/下阶段目标与旁支并行，避免纯接受措辞提交。此轮可计为主线评价恢复有效性，不是新模型收益或额外有效失败轮。今晚daily report将prefix撤回/纠错范围清楚列出，保留room跨场景失败和机制未知。
