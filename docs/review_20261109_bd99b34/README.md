# 增量验收 bd99b34

范围37ac89b..bd99b34，一笔；2026-11-09。源码diff、manifest与文档核对，本机41/41 unittest PASS。无真实bag重跑，不把数字复核当作运行复现。

## 通过

- 两份研究文档逐字节一致，C_bad表已对齐当前归档：194配对/159改善/Wilson0.7699/NIS265.8；C_good259/248/0.9318/18.07。incumbent改回常速度外推，不再把另一未归档对照当作当前实测。
- 删除“唯一原因是600预算”的断言；明确clean poses配raw injected scans，要求固定key/query的raw/filtered/clean观测和内部预算对照。
- pre/quar与跨运行对齐使用绝对header时间，修复主要分段零点混用。
- p11披露实际注入窗[114.528,134.467]与原名义[120,140]不同；跨宿主同协议声明仍需携带该差异。
- 四臂manifest说明evidence_status仅覆盖配对项，accepted=False不得误读为全部证据通过。

## P2剩余：common-support floor仍按旧相对零点分段

run_four_arm_same_input.py:692：floor_ids仍用inj_kfs[i]['rel'] < ONSET_REL，而pre/quar已用绝对戳。detect_onset的rel基于第一共同scan，pair_keyframes基于该bag第一scan。若clean缺头部scan且第一共同scan迟于injected开头，同一个绝对onset会在floor_ids中被提前切分。

例如injected第一scan=100，第一共同scan=102，onset_abs=110：ONSET_REL=8；frame_ts=109的rel=9，被floor_ids排除，却被pre保留。该集合用于后续指标，不能称全脚本零点统一。应用ts<ONSET_ABS，与pre一致，并补缺头帧回归。现归档compared598未显示该反例已发生，所以这是可触发代码缺陷，不宣布现有数字因此错误。

## 未变的证据边界

A3依然与A1相同且没有准入修复；proxy不是GT面；hash列表仍不等于宿主消费输入hash的运行链。BOUND_ONLY与独立连续性界限仍开放。本次无新的算法修改，因此不重复提交上轮相同问题。

建议关闭本轮表格与因果措辞问题，顺手修剩余floor时间条件；接下来应做固定观测/预算因果对照，不再围绕已更正文字循环全套实验。
