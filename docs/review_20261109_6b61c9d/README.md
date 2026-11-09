# 主线验收 6b61c9d：oracle/hybrid原生重估对照

范围0b91b37..6b61c9d，两笔、15文件，约15k行大部分JSON。完整读155行builder、259行evaluation和107行row审计；本机AST语法、计数/分母及两run输入hash与启动receipt关联核对。未实际ROS/bag重跑、不宣称全15k逐条外部数据复现。核心算法未改，不重复跑41条单测。

## 主线推进：接受有条件的原生输入干预证据

oracle/hybrid receipt OK、sources unchanged且pre.input hash与bag_report output对应。归档actual .66485 unsupported、oracle .00729、hybrid .00691，在同实际比较集上差异明显。hybrid采用oracle窗内+actual窗外，削弱“健康窗误删单独足以导致此失败”的解释。支持窗内测量选择差异是重要因素，而非仅拿clean pose绕过估计；这是实质主线推进。

但新map_points80750/250=323帧，提交说明326不符，GT matched317。应按JSON frame_set实际数报告；旧326结果是不同共同集合，不混用。315.16m ATE使用评测frames全程SE3拟合，与原healthy-prefix协议不同，明确标full-alignment diagnostic并另报冻结prefix协议，不直接拼入旧表；该值极大提示发散，但不替代完整来源和支持说明。

## 下一主线：真正单因素2x2测量选择干预

当前actual vs oracle同时改变1265 retained injected与23607 dropped background。hybrid只分离窗外策略，不能判残留袋点单独为因。下一冻结实验建议以same oracle base：O exact clean-background retained；O+known retained fake；O-minus wrongly dropped background；两变化组合=actual in-window，窗外固定相同actual或clean策略并明确选择。使用真实original index、sameprefix/config/runner重估，oracle仅机制诊断。报告服务总体、完整公共集合、姿态/匹配残差，必要重复对照判断host run variance。

此轮不立即换大模型、不扩宿主、不调75ms/sigma。若残留fake为主，改进时序/可靠性与host防污染；若背景删除为主，改正常几何保护；若交互主导，联合权重/重估设计。两因尚未分离，不称1265条回波已证pull registration。

## 旁支集中修（不阻断当前对照方向）

row_audit以set(row hash)计数会丢重复row multiplicity，背景/污染原身份也应按同源逐index判而非集合值；采用已经导出的original indices/mask。false_negative_rate分母目前background_present=1186220，实际应为kept_injected+dropped_injected=9073943。本机重算正确FN=.00013941（0.01394%），当前字段.00106641是背景归一化残留率，不能叫FNR。现标题0.014%与正确数相合，但机器字段需一致。

builder hybrid用hash set匹配会对重复值恢复全部同值row，未核确实保持每个actual健康删除；原index sidecar可一次解决。hybrid input hash报告也未保存，后续将消费输入全部绑定，不人工用路径推身份。outside_diff是按min/max diff推窗后检查，逻辑恒空，非独立故障窗验证。

oracle_report只检查status OK而没比output/input hash，blocked/shape fail-closed方向正确但身份测试需真正调用；将这些旁支负例随2x2实现提交，勿单独审计循环。

## 自检与创新关系

开发侧先§10.12标准自检给PASS/FAIL/BLOCKED/NA、命令/证据与实际323集合；主线报告已收窄窗内选择差异，未证明部署无GT oracle。hall正/room负仍说明适用性受测量选择影响；本对照对新可靠性模型提供动机，尚不是该模型效果。今日日报分别写归档真实干预与未证单因素机制。
