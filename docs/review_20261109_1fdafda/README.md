# 主线/旁支验收 1fdafda

范围9b7d35d..1fdafda，三笔、9文件。完整读223行rate诊断、完整度增量及128行fixture；本机AST提取当前纯函数运行15/15 fixtures PASS，健康邻居窗口反例实测；读receipt与归档，未真实ROS/bag重跑，不宣称41+15全流程本机复现。

## 主线推进：有带收据的新诊断，但根因仍需确认

归档新30s clip重现首段慢发布、输入header间隔无大洞，并记录高load与host长处理尾部，支持“调度/资源争用是候选机制”。第二短段仅两odom间隔未复现。记录诊断是实质推进，不只是字段修复。

但不接受“原46missing全部是环境artifact，not filter/tracking，无法在本机重跑消除”的确定性结论。load average含可运行/不可中断任务，不直接测CPU runnable等待；低CPU占用也可来自同步/IO/阻塞。未做低负载同输入对照，代码只凭load>=cpu_count即SCHEDULING_CONTENTION，甚至不要求od_slow同时成立。应叫CONTENTION_SUSPECTED，原因未知部分保留UNKNOWN；无需为此先发纯文字提交，随确认实验一起报告。

## 主线阻断：新运行未保留原健康prefix/初始化

归档clip首lidar=1627785269.99646，原输入起点1627785261.079016，跳过约8.92s。新host从clip启动，且尚未给同状态checkpoint。不同初始化/局部地图会影响同步、更新节奏和可观测性，不能以此确定原46缺帧的根因。之前交接已明确保持健康prefix。

最低解除：同完整prefix/同配置输入，在一次相对低负载或明确CPU资源控制下复测发布/处理序列；记录wall arrival、queue/update与header时间。可以复用冻结bag，不改75ms规则；若不能控制环境，则诊断结论保持相关性，转向预注册独立确认而非无限排障。

## 旁支：接受完整度健壮性修复

success=pose AND nonempty observation、gap=None不崩、实际width而非采样长度比较、rerun输入hash已加；15 fixtures本机纯函数通过。无新当前归档错误断言。

rate _segment_stats对左右邻居拼接后diff，跨被排除故障窗造一个虚假长间隔。本机ts=[0,.066,1,1.066,2,2.066]、故障[.9,1.1]：左右各66ms正常，却neighbor slow fraction=.3333。左右分开算diff再合并；这会影响邻居slow比例，集中修，不为它独自重跑host。

check_audit_binding只比较source hash/paths与kept counts，不比较输出内容hash或row hash；相同点数但不同payload仍可BOUND，空per列表也可BOUND。现已有字节审计可串接该身份，补无bag负例即可。它是保障项，不阻塞已有条件修复结果。

## 下一轮分工与自检

主线：一次同prefix、受控资源的发布确认或明确选择独立场景确认；给出机制能区分的证据，不调阈值制造完整。旁支：双邻居统计、audit内容绑定、header/wall日志集中处理。开发侧先§10.12自检，PASS/FAIL/BLOCKED/NA及命令/证据，报告本轮归档真实run与本机核读边界。

此前400帧条件proxy改善与446完整度不因本诊断归零；真实在线部署、独立GT、泛化仍未证明。不要把一次高负载相关性当修复路线已无缺陷，也不把发布诊断本身当新增地图净收益。
