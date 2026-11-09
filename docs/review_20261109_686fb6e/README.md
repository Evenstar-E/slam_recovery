# M2记录审计验收 686fb6e

范围6b7cb6f..686fb6e，两笔、699新增行。完整读303行审计和42行runner、报告/归档；41/41主单测PASS、bash -n PASS。未运行ROS/bag审计；外部文件/hash核验属于远端归档。核对git对象runner 1558字节sha aba9b27e...629b588c94，与记录一致（Windows工作树CRLF hash不同，不当作源hash错误）。

## 接受

runner入库解决/tmp-only依赖，PASS/FAIL/UNVERIFIABLE区分正确，实际host消费输入与旧pose来历没有被强行判PASS。完整record exporter进展保留；original point index仍需side topic/sidecar，这是M2要求而非新增模型问题。

## P2：row验证未覆盖任何被过滤帧

m2_record_audit.py:77只检查前25帧，报告第103行对应样本声明正确，但不能概括为实际剥离记录全部验证。本机读filter report：first25 stripping=0，首次strip index145。应从200个被过滤帧中取样（含首/末/最强），验证完整记录、有序原index、一对一multiplicity而非np.isin仅集合包含。现记录证明健康帧保持，不证明过滤处ring/time/row选择已被独立审计；不据此断言其错误。

## P2：审计缺观测字段可误判PASS

:204-207 miss_obs用不存在字段missing_observations（归档实际missing_observation），并接受None为PASS。已AST抽取audit_labels执行缺观测字段fixture，返回“missing observations is explicit, recorded=None, PASS”。应读实际字段，缺字段UNVERIFIABLE，检查计数与IDs一致。point ID检查仅凭topic名含'id'也不能证明每点身份，需要解码schema和对应索引。

## P2：runner失败路径不清理、成功也不保证有host输出

set -e下rosparam load或rosbag play失败会直接退出，没有EXIT/INT/TERM trap，已启动RC/REC/NODE可能残留；当前只正常路径kill，不能承诺始终只管理并清理自己的进程。添加trap、run唯一日志目录、启动就绪/host存活检查、record结束wait/status、输出非空和topic消息数量判据。空/坏输出应FAIL，不以最后stat/echo成功结尾。

日志统一/tmp/c3_*.log在并发运行互相覆盖，不会直接破坏ROS master隔离，但破坏证据保存，run目录一并解决。运行前不要rm已有OUT，要求新路径/显式覆盖，保留旧结果。

## 范围与下一交付

“19通过1阻断”是有限记录清单，不是整体M2/地图效果全部通过。0.028m窗内translation复算只证该统计可重复，不排除rotation、消息缺失和窗后差异；bounded geometry尚未实现，不能恢复oracle ceiling或地图准确度声明。

建议一次性提交point-index exporter及对应filtered-frame回归、runner runtime receipt/cleanup测试、有界几何评价。不因本轮日志说明重跑全宿主；先可本地mock进程失败/审计缺字段，再做一条短实跑验证运行链。现bag评价数字保留诊断，不修改算法或已撤回结果。
