# 主线/旁支验收 2b6ba3c：完整prefix资源对照

范围43ed9fe..2b6ba3c（6cbe85b、2b6ba3c），读193行controlled脚本、runner affinity增量、两run receipt及结果字段。JSON一致性/首戳/模式核对本机通过；未本机真实ROS/bag运行。非核心算法变动，不重复全41条测试。

## 主线：接受资源干预未消除节奏的条件证据

新clip首lidar1627785261.079016，保留原起点；A/B status OK，rate=.5/drain20，B配置8核taskset，避免旧初始化混杂。两run503间隔中slow-mask相同，onset前0、后.208609、首slow+0.273813s归档一致。这是主线真实确认推进，而非日志修复。

可说“本次affinity/负载条件变化未改变该慢发布现象；确定性同步或内容相关路径值得后续检查”。不必继续无限调机器或放宽75ms。此前46missing与400条件proxy收益仍保留。

## 范围限定与当前版本不一致

1. 代码与machine JSON verdict仍CONTENTION_SUSPECTED，最新commit/研究文本称CONTENTION_REJECTED并content-driven。按失败不证明否定的原则，A/B都存在资源等待，taskset只是pinning非保留核心；该试验削弱简单CPU饥饿解释，但不能排除全部调度影响。保留“本次资源干预未消除，机制UNKNOWN”即可。
2. same_pattern比较的是d>.100的布尔mask，不是时间戳或完整publication intervals逐字节一致。不得称完整发布series bit-identical；当前布尔一致本机可核。
3. onset前后相关不证明是注入内容造成。两run相同filtered clip，没有clean/未过滤同片段对照；host周期/sync/点数量等均可能在相同时刻变化。content effect标SUSPECTED而不是已定因果。
4. schedstat采集进程主线程，不能代表多线程host全部任务等待，load为全机。作为环境描述有价值，不从小wait fraction推出全host已不受争用。

这些不阻断已有同帧修复收益，也不要求再跑一轮纯rate归因。解释/状态同步随下一主线交付集中做。

## 下一轮主线（应直接执行）

依开发侧声明停止本链排障，预注册一条独立序列/故障强度确认：固定输入/窗口/config，实际filter→native重估→重建，用相同raw/repaired帧、完整服务分母、健康代价与有界proxy/独立参考评价。在运行前提交选择、关键判据和接受范围。不是再改一段M4结论；保持oracle/离线/GT限定。

旁支：同步analysis rule/machine verdict与布尔pattern命名，hash/affinity证据、自检字段集中处理，不令其抢占确认实验。开发侧先§10.12 PASS/FAIL/BLOCKED/NA自检，提供启动/结束receipt与证据，报告本轮已真实确认的部分及未定位原因。

本轮不自动计为模型失败或成功泛化，不用资源对照冒充新地图净收益。审阅侧今晚daily report记主线完整prefix确认与机制未知，并与隔离/修复/部署创新主张分开。
