# 主线/旁支验收 016b92e 与待审方案/历史诊断

补验c064f86、eabd008、4f2cc3d、224c520（上轮复验期间并发未审）及新增f28855e/016b92e，跳过48c1ce2自审。目标016b92e。完整读73行trace plan、四臂gap、新verdict rules及134行三观测说明，源码预算/辅助surface增量；三观测三个脚本仅核协议相关片段，非完整真实重跑。34/34 scope/identity fixtures本机PASS，未运行ROS/bag。

## 主线状态

没有新宿主运行。trace计划接受改为先观察actual GROUP/IMUINIT而非继续叠wait；四臂NIS复现gap显式列NOT_REPRODUCIBLE、禁引用两个当前值正确，不覆盖旧档。辅助surface保持独立field不改primary。主要是A2/A11及B6/B8保障和方案，未达到新阶段验收，不自动改昨日/今天完整评分。

## 主线下一交付及真实最小条件

实施TRACE_GROUP并同O输入两次，先比actual group/sample ID、IMU init集合、state对应事件。只计日志却声称“行为中性”不能保证：每事件flush会改变调度和IO延迟，callback锁释放后读buffer长度会与main消费并发。应在现有锁内snapshot字段后在单写者/预分配缓冲写出，或明确观测扰动并配trace on/off控制，不为日志新增unsafe共享访问。日志先保全完整样本IDs而非只有首末戳/数量（相同数量首末仍可能内部不同）。

方案B的逐帧ack barrier是输入时间干预，不是node完全不动/行为中性；时钟timer和跨topic delivery仍需明确。在GROUP相同但state不同的两次观测后，不足以证S3/S4完全作废，更可能缺trace字段、测量数值/状态分歧；保留UNKNOWN，按预算工程/机制复审，不直接唯一根因排除。

## 旁支历史证据范围（不再另开文字循环）

EVIDENCE_three_observation第33-39/52行球壳4.0–4.6删除与“过滤不是解法”属于已否定完整去污染对照；445旧边界/50旧门控人口也非当前ns/52协议。文件应标historical superseded，不将其当新独立机制事实；中位数匹配只是同统计复算，不排除共享协议偏差。辅助5cm voxel改善采样合理，但不会使所有距离完全无采样影响。

四臂gap265.81/41.67禁引用当前值范围接受；到底归因哪个revision字段待查，但不应抢占native trace主线。日志schema/key guards只保护结构，不保护数学/来源，34tests不提升B4/B6正向效果。

## 下一轮分工与自检

主线开发角色直接交actual消费trace与限额两run分析，runtime实际loaded so+exec/config/input身份；安全snapshot/writer是必要最小工程依赖。其余scope、gap版本与历史图口径旁支集中随主线交付，不全量重跑旧实验。先§10.12 PASS/FAIL/BLOCKED/NA+命令证据自检，报告主线推进或确切BLOCKED/最小解除，不能再只提交方案文字。

A/B本轮局部映射：A2/A11、B6/B8实现/归档保障补证，当前完整评分仍以assessment_20261110_773b995为版本快照，不将本轮纯计划自动加分；其他行未重新验证。评估成本错room/hall收据、pending/半提交/多事件/切空间主线阻断按全表复验保留，不因新日志说明宣布闭环。
