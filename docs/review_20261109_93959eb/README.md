# 主线/旁支验收 93959eb

范围a0be959..93959eb，3笔、17文件（大部分审计保障）。完整读verifier增量、index唯一性/非scan记录及测试。实际38/38 acceptance规则PASS；test_original_index直接import因本机缺rosbags失败，随后AST提取当前pure函数运行17/17 fixture PASS，不伪称完整bag流水执行。无真实host新run。

## 旁支通过

上轮EOF遗漏已增加extra_messages检查；index负/越界/dtype/order、sidecar hash与独立audit窗口门禁均进入失败counter退出。open异常移入try，typed receipt更明确。非scan流单独归档验证、multiplicity修正有价值。原问题是复现保障，此轮修好不能代替四格native效果。

## 主线无新增宿主测量，下一步必须执行

四格输入已完成连续多轮build/verifier完善，当前无已实证有效包错误需要再阻断运行。要求远端直接执行两次/格，收据关联bag hash，shared prefix/config/outside policy，报告full service/common support与固定失败标准。若资源阻塞明确BLOCKED和预计解除/替代，不再纯修日志。

旁支健壮性集中随run处理：verifier receipt写hash/关闭npz在try外等仍可异常无收据、window.source字符串不是独立版本验证；不再逐项扩大台账。run前最低输入校验已有工具，采用真实receipt即可。规则测试和审计数字不算模型新一轮有效实验。

## 自检与方向

开发侧先§10.12 PASS/FAIL/BLOCKED/NA+命令/证据，给主线/旁支分工。原始index不唯一问题按归档multiplicity检查说明范围；无需为标题或copy数再次跑全bag。若四格运行完成可解释模型该改可靠性/背景保护/交互重估，尚未运行不定机制因果。
