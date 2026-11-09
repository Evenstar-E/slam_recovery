# 增量验收 6023655

范围 cd1d118..6023655，两笔：027bd28、6023655。2026-11-09。源码增量+归档核对；本机 unittest 41/41 PASS，并实测 pending 分批提交收据。未播 bag，不独立复现归档实验数字。

## 验收

接受 pending 收据与 oracle 标签修复。接受四臂新归档作为隔离效果的代理测量，不接受验证修复新增收益或“仅由600点预算导致好候选拒绝”的因果结论。

已实测：首次提交0..7/pending8..19，再提交8..11后，实际 pending与report.deferred均为12..19，partial_commit=True。新增 newly_deferred/remaining_pending字段正确。

首个可提交段 first_run_jump 已实际参与速度包络判定；原来仅记录未使用的问题关闭。依然 BOUND_ONLY，不视为独立相对运动一致性验证。

## 四臂记录的准确含义

归档：A0/A2 578帧、tail>0.5m=.3647；A1/A3 133帧、tail=.0079；四臂 common-support ATE均为.0848。A3未接受候选；good candidate也未接受（NIS18.0694）。

这支持oracle隔离相对于全部写入的地图代理尾部下降，不能证明验证准入恢复了更多正确几何。共同支持ATE仅涉及所有臂共同保留的帧，不能将A0 admitted ATE9.136与A1 admitted .085直接解释成恢复精度提升。地图proxy不是GT表面；独立 clean源构造good候选再对clean proxy算效果已明确 UNAVAILABLE，保持该限定。

## 需收窄：good poses不等于good scans，也不能只归因预算

good候选用clean运行位姿，但node_good.scan_buffer_body仍是注入扫描，且未调用点过滤器。位姿改善没有移除4.30m袋面回波。NIS18.07可能包含真实错误测量、参考范围和局部平面近似等影响；尚无同候选同查询仅改变有效参考预算的对照，不能断言“only cross-scan budget拒绝一个已完整修好的候选”。

建议同一固定key/query集对照：clean pose+raw injected scans、clean pose+filtered scans、clean pose+clean scans（仅诊断oracle）；再扫描实际内部参考预算/邻域半径。记录支持选择、残差分布、sigma来源。修改外层cap不会自动修改内部600。

## 来源链与时间基准：有改进，未闭合

inputs_sha256四文件hash是身份快照，不能证明pose运行实际消费了指定scan bag；仍需host run manifest链接converted_input_sha256、result_sha256、配置、命令和版本。健康prefix ATE .0806不能作为注入严重度匹配证明。

oracle已标nondeployable，并处理无共同时间和无变化。绝对起止写进metadata，但实际pre/quar仍比较k['rel']与ONSET_REL：pair_keyframes以本bag第一扫描为零，detect_onset以第一共同扫描为零。若两bag头部不齐，仍会混用基准；建议分段直接比较绝对戳。当前记录compared598未提示该场景发生，不将潜在泛化错误冒充本次已发生。

## 其余限定

- 归档gate_result_A3 evidence_status=PASSED而accepted=False是当前字段只描述paired evidence的语义，不应外推全部准入通过。建议明确字段命名/分项报告。
- oracle出现起点14.528而旧协议称20秒，须在论文报告真实注入窗和零点；不使用clean对照推断在线检测延迟。
- 41 tests覆盖收据，但未测绝对时间头缺失和raw/filtered扫描对照。

下一步：保持隔离正结果与修复证据分开；建立host输入hash链；固定时间和key集合，先比较filtered观测再定位参考预算问题；不要以放大sigma或忽略污染点来恢复准入漂亮数字。
