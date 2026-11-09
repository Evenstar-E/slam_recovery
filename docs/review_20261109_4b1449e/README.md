# M2身份审计增量验收 4b1449e

范围c3822d8..4b1449e，一笔、四文件。仅身份审计与测试，不改修复模型或host执行。

## 通过

主audit_id_topic现在实际计算源/输出bag sha并与sidecar比较，不再仅回传声明；authoritative_status明确指向解码验证而非旧topic存在性结果。负例现在通过真实validate驱动错误hash、同stamp重复mask、错stride/type/schema和缺sidecar拒绝。

本机从当前源码AST抽取validate与TestFixtures（只避开缺失ROS/bag依赖，不替换校验逻辑），7/7 synthetic tests PASS；另用该fixture实际重复同stamp pair，validate返回duplicate错误。远端bag依赖的8项未独立执行，不将7项说成15项全部本机通过。

关闭上轮身份hash与负例范围意见，未发现本增量新增阻断。主算法未变，本次无需重复跑41条主测试或host。旧新ID包、回顾性host receipt、bounded评价与proxy限制仍按已有记录保持，不因审计通过宣布整体M2/M3完成。

## 下一交付

不再继续纯审计措辞循环。集中落实runner成功/失败退出与启动身份快照（上轮已报），随后推进M3固定ROI/shared base/query下只隔离与实际修复的新增几何对照。无需为本次identity测试重跑全部C3数字，除非输入或实际观测发生变化。
