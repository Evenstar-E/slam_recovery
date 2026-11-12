# c915197增量审阅：C′历史时间候选实证，完整恢复与追赶仍未实现

面向：开发S1/S2/S3与独立复核者。2026-11-12 21:25:58 UTC+8 fetch固定主线 `c91519734de99397e97e368d015f17694ffe303f`，比较4b5e63c；新归档 `exp/online-v2@99bfe1e63a1a9b1306018eb9dda19d0ebf89e670`。跳过已验收、Auto-Review和纯审阅合入，不复测旧ALI/残差反例。已读AGENTS、A/B标准、REVIEW§10和历史§85；四Cron本session单owner，另两本机会话waiting/idle，不双写或重建。忽略stop.md，用户直接暂停优先；现review分支、SSH、私人handoff保护。只源码/归档/有限表达式控制，不算法修改、ROS宿主、旧调参或大实验。

## 1. 本轮主线证据与验收范围

**部分推进：首次可核K=3确实保留了一个早于隔离起点的历史时间候选；但没有从该候选恢复、应用修复或重处理。** summary崩溃修正属必要来源保障，不单独当恢复成果。

| 检查项 | 状态／证据 | 影响与下一动作 |
|---|---|---|
| 未决段导致summary失败的新修正 | PASS（本机已读表达式控制） | 旧4b无meta抛AttributeError，新c915无meta输出空列表、混合段保有check、已有段不变；208全测试未本机执行。开发报告130945Z失败档未在本次新增路径，真实崩溃原因仅DEVELOPER_REPORTED；普通函数反例可核 |
| K=3运行、五摘要/脚本/RSS SHA | PASS（归档reader） | launch实际_cp_history_k:=3、无scripted、旧检测器on、341 paired/64 fed、0接纳1拒绝；receipt/summary/wiring/launch/rss与清单一致，wiring不是恢复成功 |
| 环形保留时间候选 | PASS局部（真实ACK） | restore当时hist两条，frame2比qstart早36.967360ms，frame27晚1.634398272s；候选存在，但仅1段，不能全事件覆盖率 |
| 实际选择恢复与重处理 | FAIL时间范围／NOT_IMPLEMENTED历史选择 | 实际restore仍用frame53，晚qstart3.366059328s；repair_applied=0、replay_within=0、suffix=0；finalHEALTHY仍unresolved_segments=1，catch_up NOT_IMPLEMENTED |
| 保留的完整状态/capture | BLOCKED历史恢复资格（源码） | entry未保匹配IMU延续量，后续snapshot清replay_buffer；详见§3。当前仅保留/报告没有执行历史选择，不把此缺项冒本次已发生错恢复 |
| driver来源绑定 | BLOCKED仅同版本实跑主张 | receipt 7cfcccf7…不等main c5efdd73…，本机有限查看近20个改动refs未找到；不把该run视为c915修后原生验证。最低补实际执行源码/diff，不为审阅重跑 |
| 成本、尾段与启动 | 归档负结果／效果NOT_EVALUABLE | 外部RSS最高7136584（文件声明KB，采样PID命令未归档），summary recovery PID564385峰1039732KB是另一口径；hist_bytes为旧历史估算。库v9c探针5/5存活25s不能证明尾段正常或唯一启动根因 |

A4保留能力实现与局部宿主证据增加，但完整可信检查点未通过；A2/A12来源、A5/A6/A10/B2/B11仍有明确缺项。A3/B3/B4没有新增ALI效果或修复净收益；只局部核验、不全表重评分，不把历史总分赋给最新main。

## 2. 真正时间关系：早36.97ms，不是早3.68s

来源固定run `131213Z_563253` 的run_summary ep0.native_checkpoint.ack：

| 项 | stamp_ns | 相对qstart |
|---|---:|---:|
| qstart | 1627785261507921600 | 0 |
| hist frame2 | 1627785261470954240 | −36967360ns（−0.036967360s） |
| hist frame27 | 1627785263142319872 | +1634398272ns |
| actual restore frame53 | 1627785264873980928 | +3366059328ns |

main COLLAB§145所称“前者早3.68s”不符qstart，未取得其计算依据，不从不同事件时间猜来源；合法边界距离须按上表原整数相减。最小随下次实交集中纠正，无需新宿主运行或为此停工。frame2早期初始化资格仍须实证，而不是只因帧号2判不可信；时间满足不等状态/地图健康。

拒绝分支restore_disposition仍用trigger−margin写checkpoint_stamp `1627785261674491405`，不等实际ACK；沿§85旧来源意见收口，不新开重复控制。真正实际输入归宿须ACK/capture/全部pending证据，不能以resume或后续有pose说历史已追赶。

## 3. 当前历史条目不是可直接使用的完整旧检查点

固定 `99bfe1e:host_change_trace_cov/src_LIVMapper.cpp.v9:17–43,1002–1068` 已读源码：

- CpHistoryEntry保存state、propagat、map、stamp/frame及计数；没有对应cp_last_imu、last_prop_end_time、acc_s_last、angvel_last，亦无旧snapshot的replay capture。
- snapshot把旧cp_map move进history后，按K保留旧条目；随后更新当前槽IMU状态并**replay_buffer_.clear()**。
- restoreCheckpoint与v8函数逐字相同，仍用当前cp_map/cp_state和当前槽IMU延续状态；并未从hist按时间选一份。

这与开发声明“只保留+报告、不改选择语义”相符，本轮有限研究接受，不将其误说成现行安全回退已实现。**最低S1/S2下一恢复依赖**：复用现检查点状态字段、IMU get/set接口和capture/reprocess链，保所选历史时刻配套必要状态及实际可重放区间；若无法取得所选旧stamp之后完整历史，显式拒绝该范围。只map/state选择不能补时间一致性，也不能在当前snapshot清掉历史后宣全部可追赶。不是要求通用多层框架或罕见异常矩阵，不需先补所有生产特性；这个缺项仅在准备实际启用历史恢复时必须先解除。

同时接受v9 final file-static实现避免增加类成员，voxel/common/header核心数学无变，不重测旧I错误。探针原件v9为4FAIL/1PASS，v9b为5FAIL，v9c为5PASS；不能笼统“任何布局变化必崩”或据此证明内存故障唯一因果。v9c仅laser_mapping目标完成，总体make测试链接失败，旧构建限定口径继续。

## 4. 来源和资源不能拼成干净K=3/K=1对照

[有限reader](run_checks.py)/[实际结果](local_checks.json)第一次退出1于driver SHA断言：main SHA `c5efdd733cdcf65fadc4fc28fd1f509ad9ccd2e87a644b9d38165a80554cc830`，receipt `7cfcccf7ce144d71cacfe47b1b7ea41cf845fe5187dde600a1bbcef2636b8c82`。保留这个缺口，改reader只记录而不将它冒PASS，归档未改；后续exit0是已定义有限检查完成，不是来源匹配通过。本机有限查已获取近20个driver改动refs没有匹配，不推断所有源码永久不可取得。库声明 `18e039e1…` 与receipt一致，实际源码→binary独立重建NOT_EXECUTED。

源码hist_bytes=Σ(old.points×32+old.voxels×96)，**只旧历史条目、排除当前槽，并不是全检查点RSS**；未显式包含node存储/caches/allocator。ACK估算最大235760928 bytes（约235.8MB），不能与总体RSS相减得纯保留成本。外部rss57行最高7136584，采样命令/PID尚不可核；summary记录的是recovery_node PID564385，不把两口径当矛盾或已绑定host。最低补原采样命令/PID/单位，不重跑大矩阵。

真实宿主pose档515行，末位置约(−714.52,−121.91,−3697.29)m，仅是记录坐标、非ATE/GT。它与开发后段异常/地图增长负结果相容，不独自证明漂移机制；没有同版本同人口干净K1控制，不宣增K导致或修复发散，也不把本次内存作为方法稳定成本上限。

## 5. 下一单一主线、旁支与分工

**唯一实交：现宿主/授权预算内，从真实≤qstart的完整检查点恢复，实际修复测量重处理，原生状态/地图重估，接回并给全部后继输入归宿；不支持范围明确拒绝并继续未阻工作。** 本次历史候选证据应直接推动这个断点，不无限停在“保留+报告”。不把开发安排“明天选择恢复”当用户自动延期15h，普通失败保负结果、合法工作继续。

| 分类 | 责任与最低工作 | 验收／当前认领 |
|---|---|---|
| 主线 | S1唯一共享集成、S2现宿主：所选完整旧cp+capture→repair/reprocess→全部后继 | 已认领保留半程并实交；选择/配套状态/原生run仍未交，不预报完成 |
| 必须先做，仅实际历史恢复 | S1/S2保匹配IMU延续量及capture；无历史拒绝 | 本源码缺口与实际晚restore成立；复用现API，不新通用框架 |
| 必须先做，仅来源/有效性主张 | S1/S2补7cf执行源码与现driver关系，S3沿已验最小真实I对应及正确Log | 不把summary函数控制当新宿主验证；旧§85失败ACK未在本目标修复，不机械重测，待实际后继 |
| 可并行 | S3在现授权内核正常/标签材料、完整shadow/UNKNOWN；S2补现采样身份与快照配套说明 | ALI-B2未解/效果NOT_EVALUABLE；不重复问同声明注入离线授权，不增Codex前置 |
| 集中延期 | 时间数字/清单self-hash、次要文案及非必要兼容清理 | 不影响输入/判决者集中处理，不因审计重跑宿主/重新手调 |

开发后继逐项**PASS/FAIL/BLOCKED/NOT_APPLICABLE＋实际命令/原件＋受影响主线/下一动作**，包含actual source/库/input、qstart/所选cp/全部必要状态、capture范围和输入完整归宿、物理修复/未修/误改/未知、完整后继/失败与成本；NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE保留。ALI正常与标签缺项仍待真实证据/必要用户决定，仓库Codex推荐明确不是用户选A/B/C，不再制造推荐回复循环或停native。旧sigma/κ/floor继续暂停，冻结科学门不降。

本轮新增真实历史候选/源码依赖及负结果构成实质增量，现review分支中文SSH发布；不修改算法或远端进程、不合main、不公开私人handoff、不覆盖开发日报。
