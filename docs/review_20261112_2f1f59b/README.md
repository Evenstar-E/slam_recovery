# 2f1f59b审阅：偏差估计有进展，修复未应用，失败后仍接回

- 面向用户、开发S1/S2与独立复核者。
- 目标 `2f1f59bfdab1203a7ef6eb3eb2e72eb345a7b8cb`；比较 `18baefd89e70a65b1a493b0c1e532558b6bff6e0`。本轮SSH fetch成功；review HEAD54e1110，未merge main，私人handoff保护。
- AGENTS、A/B标准及REVIEW§10已读，复用未变内容；三既有Cron由repair-f3持有，无旧owner双写。忽略stop.md，20min直接配置及用户宿主指令优先。四宿主前批尝试不重开，旧参数仍停。

## 1. 两项主线交付：部分推进，不报有效修复整链完成

| 检查项 | 状态 | 实际证据与范围 |
|---|---|---|
| incumbent初值尝试 | FAIL（拟合/准入）；已执行 | run044445Z_85628，driver SHA匹配e472410而非最新target；ICP31帧、0.815235m/0.356838°、未收敛；Wilson0.285519，门拒绝，0commit/19deferred，未发布修复 |
| 拒绝原生命令 | PASS（动作事实） | hold→restore→resume均OK；后续214配对帧；21个native失败诊断仍保留，不称安全/质量全部通过 |
| 解耦偏差估计 | PASS（声明容差内的单次估计） | run045238Z_92133，driver SHA匹配bfe2939和target；26帧median+0.40m/MAD0.05、范围0.25–0.55，每帧n_valid≥27；按PLAN的±0.15m结果合理，不是实际恢复收益 |
| 修正符号与完整消息工具 | PASS_LOCAL | 新估计定义为偏置、施加−bias；11项目标cloud tests通过0.399s，声明packed little-endian布局，不冒充原bag逐点检查 |
| 修复传输/应用 | FAIL（本次） | 发布26，host实际received20/queued20/applied0/dropped0；无reprocess、无applied日志，6条未观察到接收 |
| 未应用后的持续运行 | 有实际输入，非恢复PASS | wait_limit_closed→ABORTED rearm→resume；resume ACK pos约[-418,208,-308]，末snapshot约[-1823,1488,-1387]；后续263配对帧，未重放纠偏 |
| 第二事件 | NOT_EXECUTED（两run） | 两者各一episode/decision、detection off；不能用bag名或HEALTHY代E2 |
| 独立质量/公平对照 | UNAVAILABLE | 本轮未跑对照，实际修复效应未执行，不能声称地图/轨迹收益 |

两个relay各598frame=60移位/538原样；解耦发布26stamp均在损坏集。本轮不是重新证明上一043602Z的25应用：那次组件成果保留，这次未应用的失败也保留。incumbent试验0.815m只是位姿配准修正范数，不是测得0.5m量测偏置；没有独立真姿态，不能直接说初值离真值0.8m或唯一原因就是对应门限。常速外推仍非独立GT。

## 2. 本机核验与身份

[隔离reader](check_archive.py)、[结果](archive_checks.json)：`C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_2f1f59b/check_archive.py`，exit0。37/37新列示原件/更新README及旧REPORT哈希一致，复算偏差中位数及stamp集合，核两driver各自source SHA；未读远端bag/binary字节，不执行归档runner。初版reader误从summary.actions取命令（该run另存native_checkpoint_events.json）导致空动作；已改从独立events原件读取并重跑，最终非缺命令。

[小源码控制](run_checks.py)、[结果](local_checks.json)：`C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_2f1f59b/run_checks.py`，exit0；目标Git blob内存加载，其他package源码无目标差异。11cloud tests与两个正常小反例，非全suite/ROS/native实验。首控制脚本exit1因自写fake CP缺enabled，11tests当次已PASS；补该辅助属性后重跑exit0，不改production。repair_sync module因pytest依赖及既有Windows fake-host rename边界未执行，不安装/shim。code-review low给1候选发现，本机actual estimator复核如下，不把技能候选直接当已证。

## 3. 新source必须保持实际测量与候选一致，不仅把估计解耦

`recovery_node.py:1480`仍先用原始损坏scan_buffer_body与host-pose ICP候选evaluate/commit；`:1537`才估bias、发布减bias的新云；`:1554`写回现在改成**candidate尾pose**（旧raw尾来源局部改进），但这个candidate从旧坏云产生，并不是已修复云重估状态。更没有使用committed子集尾来源或保留host真实重估状态的证明。

本机actual decide/producer控制：干净平面body/world z0，+0.5损坏云配已吸收偏差的host/candidate pose z−0.5，门所见world z0；incumbent identity估bias+0.5，发布body z0；保留同candidate pose并set_state z−0.5，发布云的world z变−0.5。此处gate/ICP候选模拟，actual target决定/发布/payload真实；不是说本次未应用run已造成该0.5m错误。

**结论**：换成独立1-D估bias改善估计/符号，不解除“旧坏测量通过的候选≠发布新测量及其原生状态”问题。不能因原候选Wilson高选择保留它再把另一个物理产物纳入成功；不降低旧门，必须用真正修复产物/对应状态验证。最低复用已有修复云/ICP/原生重放，先构成一个物理一致候选，保持原生完整state/map同逻辑时刻，不再灌旧或未重估candidate尾pose。无需新门/框架。

## 4. 当前首工程断点与失败后的状态

- **已证断点**：本次26发布只有20接收，0应用/0重放；当前receipt阻止了不完整重放，这部分正确。
- **不是整个失败路径正确**：本次门先公开26commit，repair_sync_timeout后正常wait关闭/rearm仍resume，host无restore/reprocess，带20未应用云继续运行。源码`evaluate_and_commit_candidate`先于repair gate，旧释放反例现在有实际原件支持。终态HEALTHY不表示Python成功记录与宿主状态一致，必须标未修复/失败；S1最低按native成功结果推进该段发布/依赖，失败恢复已有可信状态或显式能力限制，不无条件接回污染状态冒充恢复。
- **队列归因范围**：已公开host patch:409订阅队列确为20，burst26与received20吻合，队列丢弃是有依据的工程解释，但无传输drop trace，不能由数字宣称6条确切在哪层丢失。上一25发布也在相同20队列下全部接收，说明不能按“>20必丢”推理。本次20接收日志在约4.4ms内打印，不证明报告宣称每条处理5–10ms。不需要大归因实验才最低修。
- **最低流控**：S2沿开发已经派发的≤20分批+现status回执，按本次开始的计数增量/scan身份等全批到位再重放，继承E2累计receipt反例；固定sleep不作为完成证明，不新RPC/异常矩阵。实际applied/匹配/leftover与完整人口仍需核，queued不是有效修复。

## 5. 新估计器正常少支持反例（不是本次失败原因）

`cloud_repair.py:108–144`不足min_valid返回默认bias0/n_best0；`recovery_node.py:1370–1373`不核n_valid就把0计入median和frames_estimated。actual estimator控制：1帧支持80点估+0.5，两帧非空10点不足20返回0，最终median0/MAD0/frames_estimated3，把UNKNOWN当无偏差。skill发现已本机确认。

本次归档26帧全n_valid≥27，不将此问题当本次20/26传输首因，也不要求先扩异常测试才修流控。最低无估计的帧标UNKNOWN、不当有效0合并；不足支持时明确当前修复能力，不用默认0发表未修复云冒充校正。ReferenceGrid新索引可复用已有空间支持索引，文档“1.5m reach”不等实际欧氏半径；这类实现复用/措辞集中旁支，不本轮扩大性能/格式矩阵。

## 6. 下一单一主线与自检

**交付：有限声明范围内，修复测量和对应候选/原生状态一致，完整分批传输→实际原生重估/内部map→接回→第二事件及尾段，或交第一实际算法/接口断点。** +0.40合理估计已接受，不靠重新调容差/σ、只补计数或不停重跑追成功。若一致候选被门合法拒绝，如实交拒绝与后继输入，不能换回旧坏云候选绕过。

S1单写共享生命周期/公开成功依赖及集成；S2物理一致修复、现通道流控、实际host有限运行；S3门研究/旧参数继续停。开发已派S2流控是仓库报告，实际认领/后继执行待新回执。四非LIVO前批运行边界保留，不开原版FAST安装或新全宿主矩阵。

自检须逐项**PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令和原件**：source/input/config/binary，scan完整记录/修复符号及未估计人口，实际修复测量候选准入，当前事件received/queued/applied/丢弃，native完整state/map同stamp，失败公开一致/恢复边界，接回/E2/尾段/成本，独立质量及oracle边界。偏差真值/容差只评价不进入估计/准入，未做NOT_EXECUTED/NOT_IMPLEMENTED、未知UNKNOWN。源码输出的expected0.5/within tolerance目前不参与publish条件，不据此指控直接oracle反演；新的无参考/低支持结果与有效估计要分开。

A6估计组件/符号局部推进、A2/A12与B7新负结果可追溯；A7实际候选一致、A8/B2失败公开/原生状态、A9/A10及B4/B11未闭合，未全表新评分。一般日志/协议/新索引复用/格式防御并行延期，不阻当前最低修；本机不改算法、不代host。

## 7. 发布

仅新增本轮审阅/控制结果及历史/协作增量，独立review正常SSH提交推送，不合main、不改历史/冻结门、不公开私人handoff。开发接收意见须实际回执，发布不代表已执行。
