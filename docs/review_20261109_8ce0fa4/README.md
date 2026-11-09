# 主线/旁支验收 8ce0fa4

范围a3b0b5f..8ce0fa4，一笔、5文件。完整读98行sidecar utility及76行precheck增量，AST语法/结果版本核对；无算法改动、新host run或新效果数字，不重跑41条主测试。

## 主线

本轮仅旁支完整性推进，room_02负确认主线结论不变。下一交付继续固定room输入做过滤/位姿贡献分解，不能因旁支工作又停在“缺字段→再修字段”。此前hall_01条件收益和room负结果都保留。

## 接受与最低保障缺口

room专属sidecar path+当前bag hash门禁优于固定/tmp路径，新wrong-stamp输入保存BLOCKED而不造指标的方向正确。

但实际missing输入仍在main首行_sha_file全六文件时抛FileNotFoundError，后面的sha.get(role) is None永远不到；因此MISSING状态未实现该场景。无共同stamp分支min(empty)亦会崩。用无bagstub/空topic fixture一次性修，旁支不阻断当前实测room结果。

bind_filter_report验证的是毫秒stamp+每帧counts，不是内容/精确ns：两过滤器留相同数量不同row仍可BOUND，函数还把当前文件hash新写入sidecar，是事后身份快照而非确认它产生时绑定了这些bags。方法标签当前明确计数，接受其窄范围；不得称完整point identity/source consumption证明。继续串已有exact ns/row mask audit，缺内容身份UNVERIFIABLE，不因归档结果hash看起来一致自动通过。

NO_COMMON_STAMPS也用于存在common但零diff的情况，日志语义应NO_DIFFERENCE/NO_INJECTION；集中清理，不单独开文档循环。

## 分工要求

主线实验角色推进room观测/状态分解、固定全部支持服务；旁支工程角色同时补preflight状态和exact内容绑定负例。没有证据当前input/metric无效不暂停主线，不为小改重跑host。开发侧先§10.12自检PASS/FAIL/BLOCKED/NA+命令/证据，若只有旁支明确主线未推进。
