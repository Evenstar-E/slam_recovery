# 主线/旁支验收 2fe53b5及待审独立对齐复算

范围补验291a0dd..89ef555三笔（前轮并发未审）和本轮2fe53b5，四笔纯评测/记录。完整读119行独立verify与13行guard增量，核现archive与verified JSON；本机AST实际最终guard反例。未运行真实bag或独立verify，不称归档PASS本机复现。

## 旁支进展

独立读取/对齐复算归档PASS、common ID hash一致，能够加强特定量的实现复核，不是新T3控制结果。新增prefix不足状态和onset dt标签方向正确，当前receipt flags均True。本轮主线没有新native/模型实验，仍要求T3a grouping单因素或actual trace。

## P2：hash fail-closed门禁实际跳过正常记录（已复现）

evaluate_determinism_pairs.py rec没有status='OK'，最终mismatched comprehension却只筛r.get('status')=='OK'。现T1/T2 archive status均None，因此所有正常记录均不参与拒绝。AST执行当前最终赋值：T1 receipt_r1_matches_bag=False、无status，得到mismatched={}、receipt_outputs_match_disk=True。需要给正常记录明确status或用字段存在性，并把missing receipt记UNVERIFIABLE，不以缺False视通过。

此外TOO_FEW_PREFIX返回记录仅prefix_ids，最后print仍取first_output等会KeyError；保存缺测结果后应跳过summary，添加真正执行的negative fixture，而不只静态source检查。当前完整archive没触发，不宣布旧数错误。独立verifier TOL=.05而producer=.01，现hash一致仅说明这些样本碰巧同集，协议应明确或一致；reference字段缺失被跳过也不能算整表验证。

## 主线与旁支分工

主线远端直接运行已选grouping控制并给实际IMU/image/scan IDs/state首差，不再增加对同一mm值的复算提交。旁支角色集中补以上两个可运行negative、标准化prefix/receipt状态和版本字段；这属于下一评测身份保障，不需为其重跑全部host。若真实输入身份无法核则BLOCKED+最小解除，否则并行。

先§10.12 PASS/FAIL/BLOCKED/NA自检，报告本轮只旁支及主线进行中/缺资源。已观察hall条件正、room负与repeat不稳定保持，独立实现相合不证明统计泛化或根因。今晚日报把此门禁未闭合与T3待运行区分。
