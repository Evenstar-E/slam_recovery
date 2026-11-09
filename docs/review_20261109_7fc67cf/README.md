# 主线/旁支验收 7fc67cf

范围b0bfbac..7fc67cf，4笔、11文件。完整读gauge对齐、first-pose delay、common-set增量及74行host-source说明；本机AST运行共同集合身份反例、核JSON对齐残差与mirror。未读取远端host完整源码或实际bag，不将source说明作为本机独立验证；无新host run。

## 主线推进与可接受结论

健康pre-onset单一SE3 gauge现使用且姿态左乘对应旋转，旧raw初始差混gauge缺陷已改。归档prefix RMSE .013-.015m、首aligned差.016-.029m，>0.1m在onset+.5-.84s，说明大漂移增长时刻与旧raw判断不同。delay proxy区间重叠，不能阈值区分GOOD/BAD，负结果保留。prereg证据改UNVERIFIABLE、UNCLEAR非二吸引子，声明更诚实。

## P2：common-set新旧run身份覆盖（本机复现）

run_bistability_analysis的all_paths用dict(list(NEW.items())+list(EARLIER.items()))，双方都有('O',1/2)、('O+F-B',1/2)。4个new paths被earlier覆盖。预期8新+4早共12该脚本run，实际8dict entries，漏new r1/r2两cell；更不包含单因素O+F/O-B的4个2x2run。因此commit“16 runs共同323”不由该代码产生。每_score还过滤common IDs，遗漏run若缺某key会偷偷降common_frames。

最低解除：key包含batch/cell/rep或用独立路径唯一ID，对声明参与所有run求完整交集、逐run检查无遗漏；导出run list/outputhash+IDs。用已有输出重算，不重跑host。现共同323可能数值未变，不能以可能一致跳过身份bug。

## 主线候选机制，未定位根因

FAST_LIVO2_variance_sources.md source-only指出OpenMP reduction、sync polling、IMU init分组候选，能指导实验但“唯一缺口/唯一能消除”“200000队列不会丢”“原因一定在S3/S4”均过强。大queue不保证无ROS/drop，同线程数也不保证跨run同实际measurement grouping。

建议只执行T1串行/稳定归约控制，其他config/rate/prefix/input保持原.5不变、记录二进制和分组。报告该特定循环sum是否真正进入state更新而非仅diagnostic error；不能source看到reduction即定它引发漂移。若要验证sync/init先记录actual sample/group IDs，再改触发。doc建议rate1.0是额外变化，与“只改T1”冲突，不能同时做以免失去归因。

相邻step lengths与rotation残差仍会受≤10ms非同时匹配和短interval影响，厘米级early差是posthoc描述，不证明init因果；不把它当初始状态已定位。共同prefix对齐用全健康段，首残差阈值低于fit RMS会自然有越限，需预注册时间/测量误差基线。

## 下一轮分工与自检

主线：选一个不混杂的确定性控制（如串行T1），实际运行并记录sameprefix grouping与repeat稳定性，或在已有输出先把分组首差定位。不能再只提交source疑点列表。旁支：run identity修复、协议/输出hash一致性和说明范围随同交付；仅common指标引用需先修，既有重复不稳观察保留。

按§10.12先自检PASS/FAIL/BLOCKED/NA+证据。今日日报将此记为gauge纠错与候选机制定位，不称新模型已解决或跨场景恢复获证明。无真实host新执行，已观察room重复失效与hall条件正结果同时保留。
