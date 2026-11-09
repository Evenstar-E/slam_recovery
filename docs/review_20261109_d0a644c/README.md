# 主线验收 d0a644c：room_02测量/状态分解

范围c1e6351..d0a644c，两笔、254行新脚本及归档/研究更新。完整读脚本，AST语法、归档五臂/差值/分母核对及研究镜像一致性通过。未运行真实bag，无host新run，未重复跑主算法测试。按§10.11/10.12主线和旁支。

## 主线实质推进，接受窄机制结论

同326/398条件帧、同proxy：actual-filter+clean pose(D) unsupported .00704，actual-filter+native rerun pose(E) .65896；coverage .99880→.69515。直接支持“固定filtered观测下，当前重估pose显著劣于clean reference pose”。raw→reference pose和oracle去污对照也有信息，不是单NIS循环。hall正/room负均保留。

## 不能据此排除filter对状态的作用

D使用与评价proxy同源的clean运行pose，故D好不是独立reference质量认证；它绕过host从actual-filter观测估计状态的难题。真实filter误删/保留空间分布仍可造成状态漂移，D不能否证这条因果路径。oracle C和actual D地图近似也不等于两输入对host具有相同可观测性。

“11.34%保留→geometrically starved为机制”目前是数量解释，不是方向信息/匹配有效点/IMU bias等测量。hall同样约11%却可运行已说明纯比例不足。允许判状态重估为瓶颈，不定因果“not filter or reference”。先测剩余空间/信息与host更新，不直接宣布桥接是唯一解。

## 下一主线：一个可区分机制的对照

固定room输入/config/prefix/326条件及398服务总体，在同原生host上比较actual-filter与exact oracle-removal的真实重估（oracle仅诊断上限，不叫部署修复）。同时测注入/恢复尾段的方向约束、有效匹配点数、姿态/偏置和轨迹误差。若oracle重估也坏，优先辅助/窗口状态修复；若oracle好而actual坏，定位误删/几何分布/策略。先冻结问题与来源，负结果也推进，不调ROI/75ms追回成功。

可以先从现有row masks计算空间覆盖/弱方向信息，必要host rerun只选一条诊断，不扩随机场景。若没有完整pose GT，clean pose依旧proxy，旋转/bias能力明确边界。模型改进应由该对照选择，不立即叠新学习模块。

## 旁支集中处理，不抢占主线

_oracle_body shape不匹配时静默回raw，会把未知数据标oracle，需fail-closed并输出missing身份。frame set只检查rerun+filtered，未取clean参考pose公共可用性，缺clean pose会KeyError；该归档成功不据此宣布现数错。healthy sidecar核source hash但没核当前output hash，现绑定计数仍需内容限定。exact row-diff应验证clean/injected layout/order一致，不能把重编码差异自动算注入点。

新增文本称报告in-window unsupported与retained fractions，但结果JSON仅全条件五臂与healthy块；下一次随主线补时间分区/实际计数来源，不再单发措辞修复。开发侧先标准自检PASS/FAIL/BLOCKED/NA+命令/证据，报告本轮归档重算、旁支最小修复和下一真实对照。

结论：分解通过，泛化/部署/准入安全未证；本轮不把proxy比较变为全因果根因或立即达到换模型轮数。今日日报将此记为状态瓶颈证据与filter→状态因果仍待区分。
