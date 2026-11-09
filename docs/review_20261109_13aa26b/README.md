# 增量验收 13aa26b

范围 c280fff..13aa26b：16e323d、de98967、13aa26b。2026-11-09。独立本机 unittest 40/40 PASS；复跑旧入口探针并增加两个轻量反例。未重跑 bag/宿主，不修改算法。

## 已关闭或通过

1. 首次部分提交不再立即恢复 HEALTHY：创建 deferred 段、状态 WAITING_FOR_EVIDENCE，旧 8 好帧/12 坏帧反例可以再次调用验证而无 No active quarantine 错误。
2. 缺 holdout 的 evidence_status 已从 PASSED 改为 MISSING，有新增断言。
3. 无时间戳的 1.5 m 跨洞偏移反例现被 boundary check 拒绝。
4. 全部旧四臂数值改为作废记录，接受该披露；更换输入路径尚不构成匹配运行的有效实验。

## P1：重试子集仍可丢失其他 pending 帧

quarantine/manager.py:262 起决定是否保留隔离，仅看当前 candidate.deferred_pose_keys，不与已有 pending 集合对账。

本机实际调用真实 manager：先提交 keys 0..7、deferred 8..19，pending 正确记录 12 帧；随后只重试并提交 keys 8..11，当前候选 deferred=()。manager 恢复 HEALTHY、active=None，但 keys 12..19 从未解决。

合法重试不应要求调用者每次重新提交全部 pending 才能保住状态。pending 应作为持久集合由管理器维护：old_pending - committed + newly_deferred；仅为空时结束隔离。补子集分批重试、空重试、重复/越界 key 的回归。当前测试只证明重试不抛异常，没证明分批完成期间 pending 不丢。

## P2：边界检查目前是速度包络，不是几何/运动连续性

transaction_manager_node.py 新检查用 jump <= 0.5 + 2.0 * dt；没有独立相对运动残差，也无出边界及旋转检查。它能拦无时间戳的大跳，但有时间间隔时合法位移与错误偏移无法区分。

实测把旧 20 帧 gap 反例补每帧 0.5 s 时间戳：帧 8 不支持，9..19 相对前段切向偏移 1.5 m；边界从 7 到 9 间隔 1 s，界为 2.5 m，结果 accepted=True、jumps=[1.5]、boundary_ok=True。其他构造与上轮一致，参考平面切向残差为 0、辅助信息显式给定。

这不说明所有允许移动的边界都错误，而是证明新增测试通过只能说明“无时间戳速度包络”成立，不能关闭独立连续性主张。应将测量相对位姿与候选边界相对位姿比较，计入不确定度；缺测保留未知。不应把常量 2 m/s 说成通用宿主约束。

## P2：用未验证头帧代表第一段边界仍有缺口

de98967 用输入候选第一帧替代第一 committed 帧，避免把长时间正常运动误当作跳变，这一动机正确。但当第一帧缺扫描/不支持、后续首个可提交 run 独立偏移时，它仍可提供 0 jump；runs 的检查仅 zip(runs,runs[1:])，不校验第一个 run 与可信时间线的衔接。应验证首个可提交段的独立边界预测，而不是用一个未验证头帧担保它。

## 四臂 provenance 检查不足

run_four_arm_same_input.py 新 pose_bag_ate_against_gt_m 实际仅在 leading 20% 的健康 prefix 上拟合并评分。两个不同注入的运行在该 prefix 本来可能相同，该数无法判断 0.35/4.30 m 的输入匹配。误差大小也不是输入身份凭证。

应链接 host 运行记录到转换输出 hash、配置与版本，匹配实际运行输入 bag；若需要严重度诊断，报告共同支持上的全程/注入窗误差并明确它不是 provenance。脚本默认路径也不能取代 hash 链。既有 INVALID_INPUT_PAIRING 标记应保留直至有效匹配重跑。

## 优先顺序

先由 manager 持久维护 pending 集合，再完善独立分段边界；最后用输入 hash 链重跑四臂。旧审阅中实序列探针坐标系、打印 float 为整数、部分诊断用错 key 集等未被这三笔触及，不重复报新缺陷。

测试 40/40 PASS（既有 docstring escape 警告）。新增入口观察为受控代码反例，不是实场错误率或实场误提交记录。
