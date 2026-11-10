# 21fa650验收：旧正常路径反例解除，优先原生两事件运行

2026-11-10。目标`21fa6506f8b1c63f95b135f7052b2fb84ea7c9c3`；基线c82aae5；a6bbb93、70f745a、bcede15、21fa650四笔开发增量。按AGENTS、主线标准和REVIEW§10核当前任务：本会话审阅/日报/两小时总结启用，旧owner进程不运行；忽略stop.md，用户直接暂停优先。保护私人未跟踪handoff，不修算法、不运行ROS/bag。

## 主线变化：有实质组件修复，不再重开旧反例

**A5/A9此前三个正常路径反例本机已通过；这轮是实质保障进展，不是仅增加测试数。**A7另见下方专项结论。尚无新的原生恢复/接回/两事件运行，新S1状态仍B11 NOT STARTED；本轮没有新的地图修复收益或完整A/B总分。主线缺口仍是实际宿主接线/执行；本轮A5/A9旧工程阻断解除，A7剩余项属于同评价基内的数学正确性，不归为继续调参的理由。

| 原具体卡点 | 新版本机结果 | 接受范围 |
|---|---|---|
| A5报警当帧buffer有2但pending为空 | buffer=[2]、pending=[2] | 报警入口已登记，不再报此旧缺陷 |
| A9第二事件撤repair后2/3既不trusted也不pending | trusted=[]、pending=[1,2,3,4]；provisional=[1,4] | 修复帧身份回系统pending，不把repair marker冒充原始测量 |
| A9等待key4@400ms按旧end300ms记undo，onset350ms漏撤 | undo改400ms；两批提交后第二事件trusted=[1]、pending=[2,3,4,5] | 原漏撤场景解除；批量撤销使用更新segment end，不宣称所有per-key写依赖或任意重叠事件已经证明 |

命令：`python -B -W ignore docs/review_20261110_21fa650/transaction_acceptance.py`。原报告脚本不改；这里复用原场景并仅适配新版frame/cov/anchor调用契约，把期望改为应成立的正常不变量，不跑人为undo故障注入。完整结果见[local_checks.json](local_checks.json)。

核心测试一次本机PASS：68/68，0FAIL/ERROR，unittest 2.348s；显式sys.path绑定目标仓库且打印manager实际路径。docstring转义SyntaxWarning保留，不据此扩工程任务。测试数量不等于A5/A9工作包完整3分。

## A7专项复核

**接受旧两反例及固定评价基的数学修复；实际node协方差producer仍有一个相同物理场景的判决翻转。**独立专项核目标core Git blob与21fa650相同；`a7_gauge_probes_fixed.py`两旧反例及旋转/平移例PASS，before/after/cov在固定anchor基保持一致。AST核GateThresholds前后未改，未放宽门。

实际`evaluate_and_commit_candidate`仍先在world基计算`inv(info_after + 0.001 I)`再搬回anchor，固定world单位阵正则未随基搬运。`fim_and_holdout.py` producer内部的`1e-6 I`同属该固定基问题，不另开无关清单。

专项直接跑真实node：独立trusted key0参考，rng0的400点cloud×0.16，四候选keys1–4，incumbent x偏移0.12m；仅整体world原点y=0/20m，anchor同步变换。holdout/support/paired实际计算，不mock准入；直接trigger控制同一隔离段，不声称在线检测或原生实测。

| world y原点 | before信息 | after信息 | posterior cov norm | holdout NIS | mode |
|---|---:|---:|---:|---:|---|
| 0m |20|62.98292984|0.513613665|0.335222364|MODE3 |
| 20m |20|62.98292984|0.469490005|0.335222364|MODE2 |

paired均4/4改善、PASSED，Wilson0.59647854，reentry=0；cov跨默认0.5门而不是无关小数误差。固定gauge脚本先在body构cov再搬world，未经过实际node的world正则，所以它PASS不能推广到完整producer。

**最低解除：**在固定anchor基构造/聚合info、用现有epsilon正则求cov，或把正则信息一起正确搬运。epsilon和冻结门不改，不新增一个调参周期。证据见[a7_producer_review.md](a7_producer_review.md)、[最小node反例](a7_node_cov_probe.py)、[实际结果](a7_node_cov_results.json)。只限制依赖此cov的准入科学结论，不挡原生接口实现和有限探索；aux/E3等旧延期不扩大。

## Codex有独立交付，绑定旧版本不误作新版回归

新远端分支`codex/independent-reproduction-20261110`，固定交付`ee6a1964da0df5e42904bc7545c7c4bc0bb4cc01`。本机核读其README与结果元信息，**没有重跑或合入该包**。

Codex报告实际验证39eac2f（与其开工时f20a546算法相同），Windows11/Python3.12.14/NumPy2.3.5、独立worktree；核心60tests通过、旧A5/A9与A7共五个正常不变量失败，分批正例通过；有package配对和原blob复算。它独立确认了旧问题，但**不代表21fa650的新修复失败**。不能把旧源报告直接套给当前main，也不能称已独立复验新fix。新增Codex角色“尚无结果”状态由此更新；原生环境/实际运行仍未交付。

后续Codex只需沿自己的现有包做新版anchor/cov最小fixture适配和集成复验，不重写第二套工具、不重跑旧trace。目标源码、环境、适配和期望不变量写清。没有新的输入/失败证据，已通过范围不继续重开。

## 下一唯一交付与并行旁支

**仍执行用户最高优先级[原生恢复→接回输入→第二事件任务](../NATIVE_RECOVERY_RUN_TASK_20261110.md)。**

- S1沿已确认manager唯一写入/集成责任，复用本轮已通过组件；不再因旧报警/人口/旧end问题拖延接口。
- r11070-c3负责实际宿主接口和一次限定运行；缓存宿主位姿/Python回滚仅阶段证据，不替代原生内部状态/地图恢复与真实重处理。
- r26534-58只最小处理A7当前实际依赖范围，已有公式/契约和验证复用，不追加新门或调sigma。
- Codex可并行独立验证，不是S2开工前置；KITTI仅备用数据准备，B10标签/外部基线不挡本次运行。

若无接口，交第一个具体文件/函数断点与最小实现；若运行失败或全拒，照实归档，不调门制造接纳。每次自检给PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令/结果、实际分工和当前断点，不另交纯“收到”文档周期。

## 自检与评分范围

| 检查 | 状态 | 证据/范围 |
|---|---|---|
| A5/A9旧三个正常反例 | PASS（限定） | transaction_acceptance.py及local_checks.json |
| 全核心一次回归 | PASS | 68/68，目标source21fa650 |
| A7专项 | 旧反例PASS；实际node producer FAIL | 正确搬运修复接受；world正则导致cov跨0.5门，限定最小解除 |
| Codex旧版独立交付 | 已核读归档、未本机重跑 | ee6a196；目标39e不等21fa650 |
| 原生两事件/修复质量 | NOT_APPLICABLE（本机）；开发未交 | 不跑ROS/bag，不宣布恢复完成 |
| 完整A/B重评分 | NOT_APPLICABLE | 映射A5/A7/A9、B2保障；A10/B11仍缺运行，B5/B10仍缺真实效果 |
