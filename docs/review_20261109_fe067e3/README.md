# 增量验收 fe067e3

范围 78ae835..fe067e3，5 笔提交。2026-11-09。本机 unittest 41/41 PASS；读增量源码、记录与论文。未重跑真实 bag、PDF 未独立提取。仅提交意见，不改算法。

## 通过与状态

- 7dbcfcd 的 pending=(old_pending|new_deferred)-committed 已修上轮分批重试丢帧，有新回归。首次 partial commit 保持等待，分批至全完成才健康。
- boundary_basis=BOUND_ONLY 明确降低声明强度，接受该披露，不作为独立连续性验证已完成。
- 222fb3d 的 pair builder 现在两云在 world axes、位移 world delta，原坐标系混用修复；新增解析 yaw 例作为回归依据。归档 sigma 数值仅核读，未独立重跑 bags。
- c3a0c78/fe067e3 更新 RSS/期刊撤回声明和现版仿真 mean，方向正确。
- f4bbac8 修浮点打印、错 key 表撤为 UNAVAILABLE、good pose 投影、条件分位数标签、信息标志。四臂仍 PENDING_RERUN，不可恢复此前作废效应数字。

## 尚未关闭：首次可提交段边界只记录

transaction_manager_node.py:558 后计算 first_run_jump，但不更新 boundary_ok，也未传入独立边界证据。reentry 仍用完整候选头帧，即可能未验证的头帧。此次仅使审计可见，不闭合首次可提交段衔接。速度包络并非相对运动残差；BOUND_ONLY 对照有帮助，但 Mode 2 仍可通过，论文不可称几何连续已获证明。

## P2：pending 收据仍与管理器真实集合不一致

manager :226 的 report.deferred_pose_keys 来自当前候选，:266 后 pending 已改为持久并集差集，但 :report.partial_commit 仍基于当前 report.deferred。场景：旧 pending=8..19，提交8..11，candidate.deferred=()。状态正确 WAITING、pending=12..19，但收据 deferred=[]、partial_commit=False。下游会误认为完全提交。应在收据写最终 pending，并区分本次 newly_deferred 与 remaining_pending。补状态/收据一致性测试。

## P2：四臂 detect_onset 是注入 oracle，不是在线故障检测

run_four_arm_same_input.py:213-236 比较 clean/injected raw buffers，能为受控注入定位改动时间，但需要部署时不存在的 clean bag；只能标 INJECTION_ORACLE/离线协议对齐，不应声称实际检测器找到了起点。隔离策略若使用该标签，需把 detector 测试单列，避免 oracle 收益算作检测能力。

该函数无共同时间戳时 common[0] 抛 IndexError；无差异时返回 None，main 直接用 k['rel'] < ONSET_REL 抛 TypeError。应明确失败/无注入处理并停止写有效实验。

同时 t0 为第一共同 scan，而 pair_keyframes 的 rel 以该 bag 第一 scan 为基准；缺头帧情况下两个基准不同。建议返回绝对起止戳，所有分段直接比较绝对时间，并记录对齐计数、缺帧与消息 layout。raw buffers 不同只说明字节有变化，不证明变化全是所设故障；输入转换 layout 不同时需语义检查与 hash 链。

## sigma 半分检查的解释仍需收窄

calibrate_sigma :278-283 做交错 even/odd pair 划分，不是互不重叠的时间窗口；_pairs_from_odom step=2、lag=5，相邻两折频繁共享 scan 作为不同 pair 端点，且时间强相关。转移数接近1说明同段残差尺度相近，不建立独立时间/序列泛化。

definition :289-291 写“一 clean window 拟合，another 评测”不准确，应称同窗交错 pair 检查。另 :420 优先取 MM-LINS clean sigma 再用于 LIO-SAM street_08 候选，若声称同宿主标定需解释这项选择/分别报告。无实测 bags 不判数字为错，只要求可追溯标定身份。

## 下一步

先修收据与 pending 一致性；保持 BOUND_ONLY 与真实连续性界限；用绝对戳标注 oracle 起点并处理空/无注入；在匹配 hash 链下重跑四臂；独立不重叠区间校准后再解释评分转移。已有 600 点预算、合法回环和真实修复净收益仍开放，不反复扩报。
