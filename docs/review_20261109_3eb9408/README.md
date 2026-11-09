# 增量验收 3eb9408

范围1e794f5..3eb9408，一笔、两文件。2026-11-09。本机41/41 unittest PASS，读取当前源码与归档；无真实bag回放。

## 结论

接受pair_keyframes新增first_raw_scan_abs_sec、first_paired_abs_sec：今后转换输出可区分原始头与配对头。绝对时间分段不变，本轮无新算法安全缺陷。不要为仅审计措辞反复重跑全实验。

## 归档说明尚不能确认

新time_bases声明三零点均为1627785261.079，并写“598/598 scans paired at the head”。同一归档pairing.injected实际是scans598、paired578、dropped20，dropped_time_ranges_rel_sec含[0.0,1.2]和[57.41,58.01]。当前pair_keyframes只在丢帧时写drop_rel=ts-first_raw_time，因此该记录至少需要解释，不能据人工补的time_bases宣称头部完全一致。

代码新增字段位于pairing stats，但归档pairing.injected尚未含这两项；top-level time_bases也没有由main生成。本次“新增字段可用”与“旧运行已测出这些值”必须分开。无bag不能确定实际首配对时间，不反推具体秒值；下次实际回放直接保存函数返回字段，并自动汇总time_bases，勿手工补零点。现有head_frame_offset仍来自首配对帧减首共同帧，分别列出其含义即可。

非阻断审计意见：不影响已经使用绝对时间的pre/quar/floor选择；本轮不撤回其数值，也不视为新地图效果。其余修复净收益、独立边界和观测/预算对照保持既有开放状态，不重复扩报。
