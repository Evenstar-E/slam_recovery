# 1b8a449：第二次负运行已重武装，参考与等待解释仍需源码限定

2026-11-10，main `1b8a4492c1db21682f12f37d07a389eee92e20d5`，比较99e4eb0（前次实质审阅e3a60e7）。新增c0ad8d8/4500707第二次两事件负运行、1cb2c51/1b8a449参考分叉诊断，仅两份文档；driver/manager/node/newhost patch未变。先读AGENTS、A/B标准和REVIEW第十部分、复用历史；4既有Cron不复制、peer无repair-3e，私人handoff保护。不修算法、不跑ROS/原bag、不调门/等待参数。

## 主线变化：等待关闭/重武装/resume已有开发报告，E2仍未发生

开发第二次run `fl_native_20261110T105118Z_3341023`，wall104.9s、peakRSS721MB、471pose/598scan/312配对。报告wait_limit_closed+rearm、143unresolved、原生hold/restore/resume ack OK；接回后169帧全部UNAVAILABLE、fed仍5、E2未触发。接受这是**较首次真实的新负运行/局部工程推进报告**，不再把等待期限入口列成尚未接通，也不把终态HEALTHY叫成功恢复。312/598=52.174%是扫描侧配对率，不是输入完备/恢复成功率；169帧摄入不等算法修复接回。

同bag/同sigma旧run与新run对照可作为探索，pose/scan/kf/receipt原件未交，kf只是各run配对序号（515vs312），**同kf不保证同原始扫描/同时间**。旧run字段本轮两份文档不同：21–25旧ref prev_scan或node_map、旧pts923；26旧3237。当前diag在摄入前记录，报警后的地图变更可能下一diag才显示；不能只凭kf26位置宣称确在该行触发。最低沿已有pose/scan stamp关联两次原件，分别记录触发前/后、恢复后公共时间的地图/support/参考；没有原件直接UNKNOWN，不重造多run矩阵。

## 1. 撤销后空地图有源依据，但回滚方向解释写反

manager回滚条件`item.timestamp_ns >= t_q_start`；要清掉全部已提升项，边界应**早于或等于这些项的最早时间**。报告写“t_q_start落在几乎全部已提升帧之后→全部撤销”方向反了。接受不保留可疑帧来规避隔离的方向；最低报告actual estimated_onset、margin、t_q_start及被撤回戳范围，核符号和source，不改正确撤销语义。rollback+空间同步可以清空参考，但169帧建图后仍无支持的具体根因未闭合，不能由初次清空单独解释全部尾段。

NIS source选择与检测支持是**两个谓词**：LiveNis._reference需要至少30个半径3m内点，否则prev_scan；on_pair检测则用support_ref的1m/60%空间支持且value非None，不检测`reference == node_map`。本机单个合成actual on_pair：20个参考点覆盖查询、prev_scan有独立400点，结果`nis_reference=prev_scan`却`AVAILABLE`、fed1。因此“永远prev_scan于是supported=false”的一般因果不成立；反向node_map也不保证覆盖通过。本控制不是169帧实测复现。

最低S2从已有该run或下一实质运行给rearm后头20帧actual stamp/pose、cached/actual support点数与support fraction、NIS来源、host有效特征，先辨空参考/离当前位置远/覆盖不足/缓存滞后；不先加支持恢复门或新参考策略。host末特征426、平均残差0.113支持输出变化观察，不单独证明旧地图位姿错位；snapshot38/积压282/598扫描计数不证明配对无丢失或差额全由ack，缺配对归宿照实保留。算法/工程具体根因UNKNOWN，不从缺原件猜。

## 2. 10→2秒是开发提案，尚非实施或有效性证明

本轮无runner命令原件/源码改动/第三次运行，不能说2秒已采用。confirmation margin规定历史保护/推迟可信晋升，不自动推出等待新证据的唯一合适预算；2秒可作为显式声明的有限执行预算，非校准科学模型，不启动手调扫描，也不由本机批准它“解决参考回归”。用户旧参数任务暂停保持，不能借预算解释恢复sigma/κ/floor调参。

报告称“从决策时刻起算”，当前Mode3仅`wait_started_ns = active_quarantine.t_end_ns`，没有独立decision时刻参数。本机小manager控制：last segment frame4s、在8s模拟决策、wait2s、9s来帧即关闭，而若从8s决策起尚不应关闭。**这是clock source语义控制**，不声称真实run已发生此时间差；普通同步流最后帧与决策message time可能相等。最低明确message time/wall time及t_end/decision身份，若要求独立决策起点就沿现入口传该时刻，不建设新时钟框架。现run closed stamp等于真实注入起点只是观察，不证明10秒是所有失败唯一根因。

## 下一单一主线、旁支和验收

S1/S2仍交实际修复测量→原生重估/内部地图写回→接回→E2，或原预算内第一具体断点；若先host_poses编排控制，标签非算法修复/非恢复成功，提前注入报警与自然退化缺独立标签分开，不把提前报警自动当健康段误报率。S1旧unresolved provisional泄漏、fresh-decision/命令/写回正常问题source未改，复用已发最低反例，不重跑。S2先用已有rearm后身份/support原件定位，不盲跑第三趟或自动改支持/宿主架构。S3研究并行、旧参数停；日志命名/文字解释集中处理，不升级额外实验前置。

新远端Codex参考分支`bdc4c1f`的README/REVIEW已读：固定493c5b3、非当前main验收。旧“无宿主接口”不重开，固定方向/UNAVAILABLE标签限制可复用，不重跑1108行归档或把其建议替代用户唯一主线。本机未合该分支/未执行其脚本。

自检：`python -B -W ignore docs/review_20261110_1b8a449/run_checks.py` exit0，PASS_LOCAL为源码绑定/两个小控制，正常prev_scan⇒UNAVAILABLE一般解释被反例否定；BLOCKED为raw运行归属/support恢复根因/实际host source/修后E2和真实修复链；NOT_APPLICABLE为ROS/原bag/第三次预算试跑/全suite/完整A/B重评分。A9/A10等待与重武装有开发报告局部推进，A11身份/参考解释仍未闭合；B2/B4/B6/B11不通过，完整总分不升。完整链首次真正完成仍及时报告，目前未完成。

本轮仅本地提交，前push因携带rm-rf OUT被拒未解除，未重试/换工具/peer代推；remote review仍3965299，不称开发收到，不删原件、不提交私人handoff。
