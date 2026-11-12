# d193680审阅：终点限制生效，晚快照与截断清空破坏完整修复接回

- 面向用户、开发主会话S1、宿主执行S2及独立复核者。
- 目标 `d193680aa6f3bb7945e8bf01fdd2d8932819c49c`；比较 `64bfed115f7d2058bbfe076caf103491036560c1`。本轮SSH fetch成功，review HEAD1d8c2fa，未merge main；仅私人handoff未提交，保护不stage/公开。
- AGENTS、A/B与REVIEW§10先读并复用未变内容；三Cron属repair-f3，无旧owner双写。忽略stop.md，用户20min和最新宿主指令优先；旧参数停、不重开四宿主矩阵。本机审阅不改算法/代宿主。

## 1. 主线部分推进，但新完整人口未应用

| 项 | 实际交付与状态 |
|---|---|
| sham `052437Z_114016` /7aef6bc | 零修正云23received/23applied、686group重放，决定后263配对帧；PASS控制替换执行，非实际去偏。与历史freeze repair重放支持不同，地图效应UNKNOWN |
| 新宿主构建/身份 | 新`liblaser_mapping.so` SHA `f27d1730927e6ce9deacd63f8141c664e2452a8e2f375e04f7afdbb206679d0c`，两terminal receipt实际加载hash匹配；binary仍旧0d7。build log确有Built target laser_mapping，也有无关vikit测试ABI链接失败/整体失败；不称完整构建PASS或本机独立可重建 |
| terminal repair `053647Z_122935` /b3f4f47 | 发布/收到23，**应用7、丢弃16**；重放34group/截断451，内部map17322vox/324279点，后继300配对帧 |
| terminal sham `053917Z_128272` /b3f4f47 | 发布/收到23，**应用12、丢弃11**；重放64group/截断509，内部map17283vox/325824点，后继286配对帧 |
| 重放终点限制 | PASS（本次范围）：两payload和实际重放终点均1627785280281185627，候选23个pose stamp全一致 |
| 起点/全人口实际修复 | FAIL：两实际起点差0.999728918s；开段snapshot比trigger晚约2.933/1.934s，候选前段未重放，received不是applied |
| E2/有效修复/独立收益 | E2三run均NOT_EXECUTED、一episode/decision、detection off；收益UNAVAILABLE、不可归因。HEALTHY来自wait关闭/ABORTED rearm，不报首次有效整链完成 |

旧32/32与23/23成功组件不被本次失败抹去；本次部分7/12也不能继承旧23/23通过。terminal两run改relay起点为trigger，59损坏帧/539原样，旧窗60/538保留；相对旧实验仅改的不止测量修正，也有host/起点/捕获机制，不能混池收益。

## 2. 确认新实际人口和可信时间，而非只对齐端点

[原件reader](check_archive.py)、[结果](archive_checks.json)核终点两端：

- repair `[1627785279.215156794,1627785280.281185627]`，跨度1.066028833s，34group、applied7；host.log:18474 leftover16/no_group_nearby16、:18477重放。
- sham `[1627785278.215427876,1627785280.281185627]`，跨度2.065757751s，64group、applied12，leftover11/no_group_nearby11。
- 两者received23、queued清为0是**剩余修复被丢弃**，非全部应用。repair reprocess ACK明确`repair_applied=7 repair_dropped=16`，随后仍set_state和resume；sham对应12/11。目标REPORT一处“repair_received/applied是23/23但只部分消费”错误，按原件received23/applied7或12，不能把计数语义换掉。

新driver开段`hold`后`snapshot_now`队列成功不等可信trigger checkpoint：snapshot随host当前处理边界生效，repair ACK snapshot stamp1627785279148534528，trigger1627785276215170145，晚2.933364383s；sham同样晚。hold只冻结map写，不冻结filter/IMU，晚snapshot可能把较早的held地图与较晚state放一起，不能称同trigger可信完整状态。前段修复云无对应重放group是已实测，不从缺交付猜根因。

**最低解除S1/S2**：恢复一个在允许可信时刻的native完整state/map检查点，不覆盖唯一可信checkpoint为晚触发state；明确支持的回溯界限，不能支持则显式拒绝。开发已提出按脚本戳提前arm方案，属于受控输入接口探索/开发派工记录，尚未执行验收；即使实现也不等自动检测/未知起点能力。不得为对照端点固定牺牲真实隔离撤销与接回。

## 3. 新终点截断的正常连续输入缺口（源码+本次截断人口）

部署完整patch `deployed_host_v2.diff:714–829`：restore完整状态后，新分支跳过cand_end>end_stamp（:748–752），结束时仍`replay_buffer_.clear()`/capture=false（:829）。live捕获发生在sync_packages已消费group之后（:1140）。**被截断后缀是宿主先前已消费、需要在回退后重推的输入，不是尚未消费的ROS未来消息**；它被跳过又清空，resume不能自动找回。

本次实际451/509group被truncated，与此正常新路径相符；不据此计算实际轨迹误差/IMU间隔或声称所有group独立lidar帧。源码算术小例：[1,2,3,4]group全部已消费，bounded重放到2，3/4跳过且clear，下一live5；native estimator/IMU恢复至2后缺3/4的重推。这里只做source-bound bookkeeping说明，**不是执行C++宿主仿真**，原件实际输入/轨迹质量仍UNAVAILABLE。

**最低解除**：冻结用于同人口评价的修复区间与持续运行的catch-up分开。保留并在同一原生state/map上按序重推未修复/待处理后缀，接到实际输入边界后再resume；或当前能力拒绝/显式不完成接回，不把truncated处理为成功删除。复用现replay buffer，不造通用历史/RPC系统。只是把起点再arm正确还不解除后缀丢失。

S1成功公开/依赖须核**实际应用人口/未重处理贡献**，不是reprocess OK就继续set_state/resume：本次23准入、仅7应用的实际源已经证明不完整；允许合法拒绝/失败但不叫成功修复。旧坏云候选先准入再发新云、candidate尾set_state替代原生重估与None baseline旧反例source未改，不重复重测、不关闭。

## 4. 本机实际范围与检查

- 原件：`C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_d193680/check_archive.py` exit0，59/59本轮changed清单哈希一致，核三driver SHA各匹配7aef6bc/b3f4f47，后两匹配target；核新库receipt与构建hash。输入/binary/library是远端记录哈希，本机未读字节/重建。
- 首reader错误从receipt顶层找inputs，导致null/false；已Read本机结果并改按嵌套inputs重跑，最终两library一致。这是reader错误，**不是实际库身份错配**。旧sham没有开段snapshot，不把其接回后滚动snapshot标开段。
- [源码控制](run_checks.py)、[结果](local_checks.json)：`C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_d193680/run_checks.py` exit0，目标Git blob内存加载。actual driver/client hold→snapshot按OK串行及end payload/默认空payloadPASS；sham完整点data零平移PASS；后缀算术为明确source-bound说明，不冒C++动态实测。
- `git show d193680:slam_recovery/ros/run_native_loop.sh | bash -n` Git Bash exit0，仅语法。
- code-review low无候选发现不当完整正确性验收。新多命令checkpoint fake host在Windows rename既有cmd.done边界未跑，repair_sync含pytest辅助未跑，不装/shim；不为旧通过组件重复全suite。本机未代host/bag/算法实验、未更改production。

## 5. 下一单一主线：修复与连续接回，不再只对齐A/B

**限定当前产物/宿主能力，交一次真实、完整记账的修复→原生state/map→后缀追赶→接回→第二事件/尾段，或第一实际接口断点/不支持范围。** 先解除直接影响当前链的晚checkpoint/部分应用仍成功释放/后缀被清空，以及已核物理候选与状态来源最低问题；不是全部生产防御要求。

- S1共享manager/lifecycle/成功结果单写集成，明示applied不足或后缀未处理时公开失败、分派实际回执。
- S2已有完整PointCloud/scan身份、replay buffer/host构建复用；受控按戳arm仍是开发方案，若原预算实施必须同stamp完整state/map、实际保后缀和catch-up，不再靠地图点数/端点一致宣布完成。
- S3门研究、旧σ/κ/floor参数保持暂停；四宿主前批不重开、不新装原版FAST。一般日志、被截断span术语、旧提前4s文字（旧实际仅前7.17ms，不是前4s）、测试兼容集中延期，不为文字再跑。
- sham零修正确认接口控制，不算算法修复；施加−bias、truth仅离线评价，不拿oracle或受控触发当自动修复能力。不强求随机轨迹逐值一致，但确定性输入身份、支持人口/连续状态不豁免。

开发下次逐项**PASS/FAIL/BLOCKED/NOT_APPLICABLE + 实际命令/原件 + 下一动作**：source/input/config/library，可信时刻完整state/map，真实修复测量候选/全人口应用/丢弃，截断后缀归宿与catch-up、native成功依赖、接回/E2/尾段/成本、独立质量与失败/未知范围；未执行NOT_EXECUTED/NOT_IMPLEMENTED，UNKNOWN明说。不新造单NIS/字段循环、不调冻结门。A2/A6/A12新endpoint/构建执行局部推进，A4/A5/A8/A10正常完整状态/输入边界有新FAIL证据，A9/B4/B11未闭合；不全表新评分。

## 6. 发布

只审阅/控制结果及历史/协作增量，独立review正常SSH提交推送，不合main、不改算法/冻结门/旧历史、不公开private或凭据。开发接收后继待真实回执。
