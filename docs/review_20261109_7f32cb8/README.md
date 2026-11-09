# M0增量验收 7f32cb8

范围1077bdd..7f32cb8，两份协议/清单，无算法改动。按第十部分审阅，未跑全算法测试或真实bag。实际解析清单，核对长度、唯一性、排序及集合关系。

## 接受的进展

固定主集合445、候选相关诊断子集259、prefix133并先导出清单，方向正确；三组计数与数组长度一致、无重复、排序、诊断包含于主集。C3改OFFLINE_NATIVE_REESTIMATION，记录完整ring/time/header、真实运行链、oracle评分仅注入窗，符合上轮要求。M0草案已明显收口，应优先进入实现，不继续泛泛文字往返。

## 运行前P2：第一污染scan被列为healthy prefix

milestone_m0_keys.json明确injection start=1627785275.607409；healthy_prefix最后一个timestamp恰等于该start，primary首timestamp却为1627785275.707604。实际检查：一个at/after-onset帧在healthy，第一改动scan不在primary。

协议定义start是clean/injected首次raw差异，故这帧不能成为可信prefix或评分对齐的健康证据。请用完整精度绝对戳/整数ns构造ts<start的prefix、ts>=start的primary，报告missing。不要用取到3位小数的1627785275.607比较6位扫描后又称同一边界，且不要看结果改集合。此前133/445结果需要明确所用边界精度；本轮不据此推断所有旧数都错误。

清单冻结版本需原生成脚本/边界规则。主集若只包含旧C0成功配对scan，仍缺raw scan缺pose清单及源bag身份：可定义固定paired cohort作诊断，但不能称全部raw scans且默默跳缺输出。保留主集外missing IDs即可，优先不让该信息缺口阻止filtered exporter开发。

## 非阻断：hash编码尚未定义

三组sha未声明canonical编码/整数ns或生成方法，本机default/compact JSON、换行六位戳尝试均不匹配。不能据此宣布hash错误，但其他实现无法验证身份。请提交生成/校验命令，优先整数(sec,nsec)或固定canonical清单、绑定源bag hash。运行前检查实际集合，非人工复制标题digest。

## 状态与下一步

方向与C3契约通过，边界错分修完后才能以该prefix启动对照。将M0具体生成器和M1/M2完整点记录exporter/host-runner作为下一交付；hash消费链在真正运行时捕获。独立proxy限制维持，不以oracle map计deployable效果。此轮不加新模型、不调NIS、不更新实验收益。
