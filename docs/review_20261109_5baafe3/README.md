# 主线验收 5baafe3：冻结446完整度与健康窗代价

范围cd1d1d5..5baafe3，两笔、230行新脚本及归档。完整读run_m4_completeness.py，解析归档逐项核对；本机从现有filter_audit重新汇总398健康窗/200污染窗、46缺帧与规则不满足。无主算法变动，不重复跑41条主测试；未运行真实bag。该脚本名M4只是当前诊断命名，不代表交接协议在线扩展M4已完成。

## 主线推进：接受窄范围证据

- 46帧均有filtered scan，记录nearest dt>20ms且bracketing gap>75ms（约133ms），所以在冻结配对规则下MISSING；400/446=.89686099服务完整度成立。不是扫描被过滤掉，也不能称全部恢复。
- 外窗398帧20062836点，0删除；内窗200帧8974676删除。数量本机按同一归档audit再次计算一致。
- 主线从400条件效果推进到446服务代价，收益与不足同时报告；已有离线proxy修复结论保留，不因缺帧诊断归零。

## 解释与自检界限

PAIRING_RULE_MISSING是最后测量阶段为何无配对的直接原因，不是host为何降发布频率的根因。无host log/queue/更新周期证据不能排除调度、输入同步或内部tracking问题。“放宽到150ms可插值”不等于这些位姿准确可恢复；不改冻结阈值正确，后续新协议要独立验证插值误差。

healthy-region脚本只读取checked-in filter_audit JSON，不重新执行filter或读取clean独立数据。称“独立聚合复核”而非“过滤器独立实跑”；这一clip外窗零删除可报告，不等于跨场景specificity=1。需保留正常近墙反例和同注入时间clean counterpart，后续确认测正常区代价。

## 非阻断代码健壮性（旁支）

missing循环只遍历无pose的key，若有pose但filtered scan缺失/空云，不进入missing；written也仅检查timestamp存在而未查空云。未来服务分母需统一success=pose AND nonempty observation，所有其他key列原因；现档46全has_scan，所以未宣布现记录错误。gap=None且近pose<1s时f-string格式化gap*1000会TypeError；加fixture即可，不需重跑现host。

filter_audit来源hash未在本脚本验证与当前输入/filtered bag一致，输出inputs_sha也漏实际RERUN_BAG hash。旁支补结果消费的全部输入hash与audit绑定，不能把旧audit聚合挂上新运行身份；现本机无法核外部bytes，不作当前数字伪造判断。

## 下一轮分工（必须有主线交付）

| 分类 | 下一动作 | 验收 |
|---|---|---|
| 主线 | 选择一条短、带完整runtime receipt的冻结输入诊断，判断7.5Hz发布与46missing的机制；或在预注册独立序列确认已见修复收益 | 提交一个明确选择，actual输入/输出覆盖与状态日志，不先调75ms门限；随后回到完整恢复/确认 |
| 可并行旁支 | success/missing统一、gap空值fixture、audit hash绑定与rerun身份 | 集中最小修复，不因它重复全套C0-C3 |
| 延后 | 大模型/更多宿主/强制成功评分 | 等确认真实瓶颈与一条独立结果 |

开发侧先按§10.12自检附PASS/FAIL/BLOCKED/NA及命令/证据，区分本轮归档聚合与真实run；缺原因UNKNOWN。日报应写本轮主线完整度诊断和零外窗删除的限定，不把单个clip称通用安全。现结果无新的已实证算法阻断，整体实时部署/M3准入独立增量仍未完成。
