# 930563d：状态写回接线新增，但写回了旧位姿/待定帧

2026-11-10，main固定`930563d31b826420fd6960e5b240f7c5b1b3f5f5`，比较d0743e1。新增b11eb7d `set_state`客户端/四元数工具/诊断脚本及受控运行报告。协议、评分与既有Cron归属已核，旧owner无进程，私人handoff保护。远端实现和运行，本机仅源码/正常编排控制；无算法修改、ROS/原bag、参数扫描或新模型。

**发布状态**：前轮push因携带开发脚本的`rm -rf OUT`被权限检查阻止；本轮没有重试、换工具或让其他会话代推。原review远端停3965299，本轮记录仅本地保存/提交，不冒称开发侧收到。新smoke_writeback同样自动删除既有OUT，最低开发改新空目录/拒绝覆盖旧产物，或等待用户明确权限；本机未执行/删除。

## 1. 接口进展与实测边界

确有Python `CheckpointClient.set_state`载荷入口，四元数helper单位旋转/z90两个新测试本机PASS（2项/.001s），bash -n通过。开发报告人工set_state x10后未来x10.276→11.229、地图计数增长，可记为**受控位姿写入/后续传播报告**，不是经过门接纳的实际修复链。报告精确匹配两次失败/回退和未匹配未知也保留，不以失败抹去接口探索。

宿主实际set_state/hold/repair subscriber/apply源码依旧没有归档：本版host diff与d074相同，sha256`f5efce7160e45933f84b23c365f08b9a51798aeb9c201c4e48a5ba026e2c2f21`，旧文件不识别新命令；原ack/log/results/config/binary receipt未交。129测试是开发报告，不是本机复跑。因此不能独立确认写入了哪些状态、地图与状态是否同stamp，以及真正持续接回。最低保存已有实际patch/log/命令与receipt，不重跑矩阵。

仅live_points231k→361k无法证明“全是新观测/地图在新位置从零长起”；旧几何是否仍留原位置、写入了哪些新几何需要原件或收窄为地图计数增长。人工跳变是受控压力/接口探针，不是修复净收益或正常无缝接回。没有E2运行，本轮不发完成通知。

## 2. 实际正常写回来源错误（A8/A10/B2）

位置：`recovery_node.py:1088`使用`ep.frames[-1][2]`。这些frames在on_pair约852保存的是原宿主输出pose；ICP候选在decide生成另一份`repaired`，node再过滤verified并提交实际支持子集。该行既没有使用修复位姿，也不查committed_keys。

本机模拟正常候选编排（不调门、不是候选质量实测）：两帧旧host x10/20，repairer返回x1/2，gate报告完整提交且Python trusted为x1/2，native命令却set_state x20。**原修复被旧输出覆盖**，注释“last repaired pose”与实参不符。

同一控制改为正常partial，只有key1通过并提交x1，key2 deferred、manager WAIT；native仍set_state最后旧key2 x20。未通过验证的尾帧被当accepted写回。这个正常部分接纳是项目已支持路径，不是极端故障推演。

最低：明确原生重处理后的合法终态由实际修复测量/状态重估产生；不为满足旧任务文字再将任意host/ICP位姿灌回。若当前接口仍需显式set_state，必须选**实际已提交且与宿主重放时刻对齐**的修复状态，不选ep输入尾帧；partial/deferred不能把未准入尾部写入可信宿主，需保留段归属。复用这两个控制和正常正确来源正例验，不重写估计器/通用状态框架。

## 3. 原生重处理失败后仍写状态

同编排模拟reprocess返回okFalse，driver不检查便继续set_state x20并记录native_writeback。这个失败是现接口已经记录的常见动作结果（包尾控制/ack错配/未知命令均未闭合），不是新增恶意故障空间。

最低：失败native重处理不继续发布依赖它的写回成功，动作失败与gate accepted分开，不宣称原生提交/接回完成；与已发single in-flight/matching-ack任务一起最小解除。不能先修这一行而把旧ack错归属当已解决。全接纳resume与partial隔离契约仍待实际host source；本轮未改该路径，不重跑旧suite。

## 4. 精确匹配回退的事实与解释

日报已承认merged_scans217–230/multi_scan_groups0的语义需澄清；接受保持UNKNOWN，不用这两计数自动排除合并/证明单成员身份。把合并组header改成最后scan时间不等保存每个原始成员header；尝试失败不否定此前保留真实rawheader/成员映射的最低建议。分组/未匹配按checkpoint前、重放尾后、区间内无组分类方向有用，但“多数早于checkpoint”只是预测，需按已有20条stamp实际记账，不看结果更改窗口/扩大匹配误差。

同instance/checkpoint/buffer对照更接近隔离修复效应，仍不自动排除重放非确定性/状态未恢复的影响；沿上轮现量级和不确定性，不扩大重复矩阵或强求逐值同结论。

## 下一唯一主线及自检

S1集成：修正常写回来源/committed时间归属、原生动作失败顺序，复用旧命令归属、trustedstamp、评分子集/full-vs-partial释放最小任务；不重开已接受transport/协方差/旧队列成果。S2：随在手运行归档真实host新版patch/原件、把实际修复测量接进宿主重估与内部map/state、证明后续输入继续和E2。受控接口探针可先检机制，但人工x10/shift不是算法闭环；失败按原budget保留、接口不可行重比较，不无限修FAST-LIVO2。

S3门研究独立、参数手调继续停、生产门不改，研究不挡两主线。下次实际交付给PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令与同source/host/input/config/完整帧归属/缺测/尾段/成本原件。首次完整真实写回→接回→第二事件仍单独汇报。

本机PASS_LOCAL：两个四元数测试/sourcepin/bash语法；FAIL_LOCAL：旧host位姿覆盖修复、deferred尾写回、重处理失败继续写入三个编排控制；BLOCKED：host实际部署原件/同时间线map-state写回/接回/E2；NOT_APPLICABLE：ROS/原bag/129全suite/完整A/B重评分。A8/A10仅新增入口，不闭合；B2/B11未获证，不提高完整总分。主要工程正常接线/来源，修复净收益UNKNOWN。

命令：`python -B -W ignore docs/review_20261110_930563d/run_checks.py`。退出0表示缺陷成功复现，不是修复通过。模拟report/ack明确非实际gate/host接纳，生产源码未改。
