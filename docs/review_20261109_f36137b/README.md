# M0增量验收 f36137b

范围f71f751..f36137b，一笔。按第十部分验收固定输入协议。已运行清单检查、Python语法检查及41/41主单测；未播真实bag。

## 通过

- scan读取携带header整数ns，detect_onset按整数ns匹配，pre/quar/floor分段整数比较。
- 清单primary446、healthy132、diagnostic252，count/唯一性/排序和subset检查成立。首次污染timestamp确在primary、不在healthy。
- comma-joined sorted ns三组sha可本机逐个复算一致。
- primary+healthy+20 missing raw IDs互斥，共598个扫描，缺输出公开。
- 老浮点归档明确标segment_boundary，不与新清单混用。旧诊断259→252/NIS变化不是新恢复结果。

## 状态

关闭上轮M0边界错分及hash编码意见。主集合作为明确paired cohort可用于C0–C3固定比较，raw missing另列；不把它称所有598原始扫描。整数ns文件身份与列表一致性本机可核，源bag对应性仍依赖远端实跑链。

建议立即推进完整点记录filtered exporter和actual host runner，不再因旧归档文本/数字整轮重跑。C3未运行、地图净恢复未知、BOUND_ONLY仍非独立相对运动证据；本轮通过不等于M2/M3完成。

非阻断：probe_c_good_attribution仍用float ev start_abs_sec分段；仅历史诊断，不要将其旧集合冒充新M0整数ns集合。后续新实验直接消费冻结清单与整数戳，保存生成命令/代码版本即可，无需为此又跑单NIS归因。
