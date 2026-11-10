# 969c424：浅拷贝诊断有源码依据，修后报告不等真实修复/E2验收

2026-11-10，main `969c424aefdf8732e0f379bc6097357fac5ccbde`，比较d5f7d8f。本轮06076e8/969c424只改两份报告，无新版host patch/运行原件、无driver/匹配脚本源码变动。本机已读AGENTS、A/B标准、REVIEW第十部分并复用历史；核4个既有Cron、peer无repair-3e，不新起自动任务。只核源码、开发读数算术和单个合成匹配控制，未跑ROS/原bag/算法、未调参。私人handoff保护。

## 主线实质变化与接受范围

开发现在给出**同末stamp `1627785284.679`**的live/control/treatment表，报告捕获共享云被live原地改动，深拷贝后control地图10824→16196 voxels。这比此前跨运行比较有实质改善，接受撤回14.23m注入效应和重新核旧8帧PASS的方向。d5f关于“没有同stamp表”的缺口在**报告层**已补，不重复要求重造该表。

本机核三个已报位姿：control-live欧氏差0.07239081m；treatment-control差0.02882930m。它们是开发报告算术，不是本机宿主测量，也不是质量收益。报告未给重放保真容差/重复散布，不能仅由“亚分米”自动判完整状态保真PASS；不新增逐位一致或新阈值前置，随实际链保留误差及不确定性即可。“20/426做平均所以小效应是对的”并非已证机制，估计器非线性，改称观测差，不解释成真实算法修复效应。

## 1. 旧捕获路径支持浅拷贝风险，actual修法仍BLOCKED

公开patch仍sha256 `f5efce7160e45933f84b23c365f08b9a51798aeb9c201c4e48a5ba026e2c2f21`，gitblob仍fd15b982：`replay_buffer_.push_back(LidarMeasures)`和`LidarMeasures = replay_buffer_[i]`均值拷贝结构。固定上游[common_lib.h@0d2c034](https://github.com/hku-mars/FAST-LIVO2/blob/0d2c034/include/common_lib.h#L75-L99)的三个云是Ptr；[LIVMapper.cpp@0d2c034](https://github.com/hku-mars/FAST-LIVO2/blob/0d2c034/src/LIVMapper.cpp#L1001-L1002)确有修改`*pcl_proc_cur`/swap清`*pcl_proc_next`的路径，handleLIO也有空云早退。这独立支持**旧归档存在别名/跨组变更风险**；当前实际配置是否走该分支、实际空云日志、修后每轮不变输入尚未随提交给出，不把上游源码自动当本次因果原件。

最低S2归档已经运行的深拷贝/每轮消费代码与已有log/receipt，并说明control之后treatment的源缓存是否仍是原捕获内容。若replay也改共享源，用已有复制helper在消费处保持源缓存，不另造缓存框架。旧8帧PASS不能继续当已确认有效的重放证据，标**待复核/未可独立验收**；只有点数/实际估计写图原件支持才恢复该范围。可复用下一两事件的每帧点数及地图变化；若原8帧确失效追加撤回，不改旧数字。

## 2. 20/20是匹配数量，不证明scan归属

新报告规则“取最大戳≤group end且差≤0.2s”扩大时间邻域，未发表actual匹配代码或逐条raw header→group清单。`had_group_but_missed=11`/`no_group_nearby=0`也未交原件；附近有group不等同该scan属于该group，不能单从它定位“精度而非缺帧”。

本机**仅照文字实现**一个整数戳正常反例：当前group原scan戳100s、结束100.09s，当前repair缺失、队列有前一scan repair99.9s。该规则会选99.9s（差0.19s）替当前组。不是本次20条实际错配证明，也不是实际host代码测试；它说明一般身份保证不足。最低沿现原header/成员戳记验证这20条实际替换所属scan，或明确仅时间近邻的受控机制范围，不能把leftover0算身份PASS；不再放宽窗口、不造宽矩阵。d5f分类脚本source未改，旧标签反例不重跑。

## 3. 已冻结host_poses只验编排，不闭合实际修复目标

日报冻结`--candidate-source host_poses`。当前driver `decide()`先把ep.frames原host poses当repaired，只有`icp_reregistration`才调用实际候选修复。这是已声明的拒绝/生命周期控制，可按原900s预算执行并保留E1/E2/安全拒绝/尾段结果，**不把它叫实际测量修复或成功恢复闭环**。人工zshift亦非算法修复。已有0.884配置不是本轮新调参证据，不重开sigma研究。

下一唯一主线仍实际修复测量→宿主原生重估/内部地图写回→接回→E2；S1/S2保持两主线角色，S3研究并行/旧参数停。若先交host_poses受控两事件，标签与最终算法链缺口分开；不由本机选新算法/换宿主或代跑。S1旧命令归属、trustedstamp、partial/deferred/失败写回问题source未变，沿已发最低任务修，不重复全部测试。

## 自检与交接

| 项 | 状态 | 证据/命令 | 下一动作 |
|---|---|---|---|
| 报告算术及版本范围 | PASS_LOCAL | `python -B docs/review_20261110_969c424/run_checks.py`，exit0；local_checks.json | 复用，不跑宿主 |
| 旧浅拷贝风险 | SOURCE_SUPPORTED，actual根因原件BLOCKED | 旧gitblob+固定上游Ptr/原地修改源码 | S2归档已运行新patch/log/receipt |
| 新20/20归属 | BLOCKED；文字规则合成反例已复现 | 同脚本整数戳控制，非实际host错配 | 20条原scan/group归属，非扩大窗 |
| 修后同stamp对照 | DEVELOPER_REPORTED，算术已核 | 7.239cm/2.883cm；非独立效果指标 | 保留同次原件与差异，不指定新容差 |
| 实际修复与原生接回E2 | BLOCKED | 新冻结host_poses为编排控制；暂无完整运行 | S1/S2交真实链或预算内第一断点 |
| ROS/原bag/129全suite/调参/完整A/B重评分 | NOT_APPLICABLE | 本机未执行 | 不把开发129当本机通过 |

A4/A6继续有原生组件探索、A10仍待持续链；B2/B4/B6/B11不由近邻命中/厘米差证明。只局部核、不升完整总分。旧8帧实际重放效力暂不作为正验收依据，不抹去源码实现。完整链首次真正完成仍单独及时报告。

本轮本地提交，前push携带rm-rf OUT被拒限制未解除，不重试/换工具/peer代推。远端review仍3965299，不冒称开发收到；未执行删除或诊断shell。
