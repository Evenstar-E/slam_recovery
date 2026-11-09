# 增量验收 e6ae2de

范围 8cd2ee6..e6ae2de，一笔提交、两个文件。结论：本轮 floor 分段缺陷关闭，未发现新的阻断缺陷。

## 独立核验

- run_four_arm_same_input.py 的 floor_ids 已使用 ts < ONSET_ABS，与 pre/quar 条件一致。
- 本机从当前源码 AST 提取 floor_ids 原表达式运行缺头帧反例：injected 零点100、第一共同时间102、onset_abs110、ONSET_REL8，扫描100/102/109/110/111；得到 [0,1,2]，正确保留109时刻健康扫描。不是手工重写条件后测试。
- unittest 41/41 PASS；manifest 严格 JSON 解析通过。
- 新 first_common_abs_sec 可追踪共同零点。归档补充 offset=0 不等于独立重跑证明；本机无 bag，仅核对现有记录。

## 非阻断审计说明

脚本 head_frame_offset_sec 使用 inj_kfs[0]（首个成功配对关键帧），而 pair_keyframes 的 rel 使用首个原始扫描。若配对丢掉头部扫描，该 offset 混入配对丢帧延迟，不只表示两 bag 头部差异。主要分段现在用绝对戳，不受此影响；后续建议分别记录 first_raw_scan、first_paired_scan、first_common_scan，而不以该 offset 证明无缺头。

## 状态

本轮不改变四臂数字或修复准入结论。仍保持 A3=A1、无已准入修复的限定；raw/filtered/clean 观测与实际参考预算对照、完整 host 输入 hash 链、BOUND_ONLY 之外的独立边界证据仍待后续实作，不重复报为本轮新增问题。

未重跑真实 bag、宿主或完整四臂实验。审阅只追加意见，不修改算法。
