# 22d7933增量审阅：具名尾字段解析通过，真实pose7表头仍不匹配

面向：开发S1/S2/S3与独立复核者。固定2026-11-13 00:45:59 UTC+8 fetch主线 `22d79337ba80c01ae05988d7dec3bb87db0f0e60`，比较66cc814；producer仍固定宿主归档 `eb2630ef10f827626ee1eaad87fa7ddc39cc825c`。跳过Auto-Review/纯合入与已验组件；AGENTS/A-B标准/REVIEW§10及历史当前范围已读。四Cron repair-f3单owner，其他本机session waiting/idle，不双写/重建；忽略stop.md，直接用户暂停优先。无算法修改/ROS/bag/完整CLI/新参数或安装，不合main/改历史门、保私人handoff。

## 1. 本轮接受范围与状态

**消费者代码有局部推进，但已声明v10导出到消费的普通路径仍未接通。没有新增真实I或恢复结果。**

| 检查项 | 状态、实际证据 | 影响／下一动作 |
|---|---|---|
| 两parser对七个具名pose尾字段 | PASS_LOCAL限定schema | 自测展开header+100标量行可解析1行、malformed空；t2_run pose_from_tail读七值一致，旧93列无tail仍解析。不宣全部v10兼容 |
| 真实v10 producer表头+100标量行 | FAIL_REPRODUCED_LOCAL | C++真实header只尾部pose7一个block名，两parser期望93或94，而writer实际100；都0行/malformed100，详见§2 |
| 同行post优先源码分支 | PASS_SOURCE限定范围 | parsed pose可进入exact_by_idx并跳外部fallback；真实header尚无parsed rows，此分支不能收实际v10数据。原vec采集未修，仍不证明物理I |
| I资格子PASS收窄 | PASS文档范围 | v8 post与carryover改ASSERTED_NOT_VERIFIED/INCOMPLETE，额外LIO文件无key不用于I资格；总体UNKNOWN不被数值行洗成独立证据 |
| 保存人口/数值与真实运行 | 数值原件未变；新运行NOT_EXECUTED | t2_join/summary与66cc逐字相同，无新trace/bag/成本/恢复选择、ALI效果NOT_EVALUABLE |

[有限脚本](run_checks.py)/[完整实际输出](local_checks.json)：`C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_22d7933/run_checks.py` exit0。从固定C++源头提取实际header，NumPy仅明确现有安装路径；内存执行已读parse/pose函数，用同一普通有效100列输入分别核真实header与自测header，不运行归档CLI/selftest临时文件/ROS。exit0表示预期局部通过及接口反例成立，不目标整体PASS。

A1/A11/A3/B3消费者和资格准备局部推进，实际接通未闭合，A4/A5/A6/A10/B2/B4/B11无新成果。未复核全表、不报新总分；不重测刚关闭的SE3公式或旧native反例。

## 2. 一个实际接口反例：producer的pose7块名不等七个标量字段名

`eb2630e:host_change_trace_cov/src_LIVMapper.cpp.v10:367–368` 真正的表头结尾为：

```text
... r_chi2w vec6 Ppre6x6 Ppost6x6 pose7
```

writer依声明追加7个xyz/四元数标量，block_end=93、实际宽100。`22d7933:t2_run.py:128–136` 与 `t2_join_upgrade.py:43–51` 取Ppost6x6之后的header token数量作为tail宽；actual tail_names=[pose7]，因此仅接受93或94，拒绝完整100。只有新增selftest的七个展开pose_x/pose_y/pose_z/pose_qx/pose_qy/pose_qz/pose_qw表头才通过。

这不是罕见格式/恶意数据，也不是新实验矩阵；是**本次固定producer/consumer对同一个已声明7维块的直接不一致**。本轮尚无实际v10 bag数据，不能冒称实际运行已丢全行/触发误判；它阻断的是该版本新数据的读取资格，旧93档正常控制仍通过。

**最低S3/S1**：沿现parser对明确pose7块按producer已声明顺序展开七字段，或由S1/S2统一producer具名header与消费者并绑定版本；当前已部署v10块名的读取不能仅靠未来改表头宣布修好。复用一个实际header控制＋旧93/具名控制即可，不扩任意schema框架、阈值或异常矩阵。不要只硬放宽100列但留pose_tail只有pose7/仍回外部近邻；验收必须取得七值并进入同行post分支。

main仍允许无可用tail时外部pose时间关联，及始终读取已存在M2DGR文件；对旧92/93支持保留，v10已声明尾块不能默默当旧行回落补资格。外部关联此前已限定HEURISTIC，当前整体I仍INCOMPLETE/UNKNOWN，不在此轮新造其旧排序/重复戳控制。

## 3. 下一唯一主线与最小旁支

**原生主线仍：完整且≤qstart的检查点＋可重放历史→物理一致实际测量修复→原生状态/地图重处理→全部后继输入归宿；不支持范围明确拒绝。** 不因本次schema小修暂停S1/S2其余合法工作；研究直接回一次有效真实运动资格/shadow，避免连续导出/日志循环。

| 分类 | 责任与验收 |
|---|---|
| 主线 | S1唯一共享集成、S2真实宿主：完整历史cp配套IMU/capture与恢复/reprocess、后继归宿；后半未交，不用parser/探针成果代替 |
| 必须先做，仅v10消费者 | S3/S1统一真实pose7块布局，实际header正常行解析七值并用同行post；复用已读控制不需要新host run证明parser |
| 必须先做，仅I物理资格 | S2/S3真实pre绑定同更新idx/group/phase；cov维持NOT_AVAILABLE，unit-only可行，旧vec不当最终pre-post。真实数据与版本身份须同run |
| 可并行/集中延期 | S3现材料正常/标签、S2新有限导出与原生run身份随实交；一般文案/兼容/审计集中，不复旧调参或Codex前置 |

S3 f90a748代码/S1集成及派S2补pre key认领可核；真正接口闭合/新run/预配对仍未交。15h窗到08:53不被“明天”安排延期，普通失败保存后未阻工作继续；正常校准/标签真需用户新来源预算则具体中文GitHub呈报，现授权声明注入只离线不再泛问A/B/C，门不降。

后继逐项**PASS/FAIL/BLOCKED/NOT_APPLICABLE＋实际命令/原件＋影响/下一动作**，含owner/HEAD/input/source/binary/library、所选cp/qstart/IMU/capture/全部后继，修复/未知/误改、pre/post key/phase/空点/截断/全人口及UNKNOWN/独立标签/成本；NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE保留，不只tests或HEALTHY。

局部parser接受与新实际producer不匹配证据构成增量，现review分支白名单中文SSH发布；不算法/host/main历史、不动私人文件或开发日报，不另造重复总结。
