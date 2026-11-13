# 4cacc31增量审阅：旧资格反例已关闭，同边界hold/snapshot仍存在跨组件时序缺口

面向：S1共享集成、S2 FAST-LIO宿主、S3方法研究及用户。固定2026-11-13 12:07:49（UTC+8）fetch main `4cacc31d8d904102eeceabb812c3e5d81959a01a`、growth `442bd2cdb4309420192ea7a977f6cdd8e56d9ad6`、ALI `121f7efd33658c519969eff228e6bc42058e13e7`。跳过已合入的 `24a7833` 审阅，不重开旧SE(3)数学、旧宿主失败或已关闭反例。四Cron仍repair-f3单owner；私人文件未读未动。

本轮仅固定源码、归档和独立本机控制；未构建/运行宿主、未改生产算法、未调参或安装。开发记录继续保持用户暂停，v4未构建、未运行。

## 1. 可以关闭的旧发现

[独立控制](closure_checks.py)及[保存结果](closure_checks.json)实际exit0：

| 上轮发现 | 当前证据 | 判定 |
|---|---|---|
| F2缺run_id仍PASS | 11个合成selftest实际通过；缺id为INVALID、I_rows只含合格行、pairing=`INCOMPLETE_MISSING_RUN_ID` | **CLOSED，限源码/合成控制** |
| F2 NO_PAIR与PASS并存 | pairing=`INCOMPLETE_MISSING_PAIR`，NO_PAIR保人口 | **CLOSED** |
| 无n的fraction误判SUPPORTED | `UNKNOWN_CONTEXT` | **CLOSED** |
| skipped不在任何类、重叠事件空unresolved | skipped单列、fully_decided=false；重叠key进unresolved且fully_accounted=false | **CLOSED，限driver侧** |
| deferred OK被当applied | 当前客户端deferred保持pending，applied才完成 | **单命令语义CLOSED；组合时序见下文** |

这些是通过特定反例关闭，不是检测性能或整链通过。真实FAST-LIO同update导出、正常校准/事件标签仍未到，A3/B3/B4不提升。

## 2. 新阻断：同一目标戳的snapshot在hold applied前并未发给宿主

当前[arm_scripted_checkpoints:2668–2678](https://github.com/Evenstar-E/slam_recovery/blob/4cacc31d8d904102eeceabb812c3e5d81959a01a/slam_recovery/ros/recovery_node.py#L2668-L2678)对每个边界依次调用 `cp.hold(at)`、`cp.snapshot_now(at)`。F3新ACK语义是正确的单命令修正，但与串行outbox组合后出现以下实际顺序：

1. hold(123)写入host，snapshot(123)留在client outbox。
2. host回 `OK hold deferred`；client保持hold pending，**仍不发送snapshot**。
3. host在目标组前apply hold；client收到applied后才flush，cmd文件此时才变为snapshot。
4. v4只能在后续组的 `nr_apply_deferred(lidar_end_time)` 执行该snapshot，并以 `g_nr_lidar_end`（此前已完成帧）为cp戳。目标组的估计已经完成，因此cp仍可等于/晚于声明边界。

本机AST隔离执行当前CheckpointClient，保存的实际状态为：

```text
deferred后：hold armed=true、ok未设置、outbox=1、host cmd=hold
applied后：hold ok=true、host cmd=snapshot
```

所以**“v4把执行点移到sync后/估计前”单看成立，但同边界两条命令没有在目标前一起预武装**。现有14项源码文本检查没有覆盖这个跨组件序列；不能据其PASS认定边界已关闭。

**最低解除（S1/S2共同）**：把同一边界hold+snapshot作为一次预武装/一次applied的边界事务，或以等价方式保证两条命令在目标帧前均已在host队列中，并保持ACK可唯一关联。用一个target落在两帧之间的双命令控制同时验：snapshot在hold applied前已 armed、实际cp为前一完成帧、目标组未进可信地图。不要为绕过时序简单恢复“deferred即完成”。

此项只阻断下一次构建/run前的合法checkpoint主张；F2已修资格和其它未阻工作不需回退。

## 3. v4的update回执尚未被driver消费

v4已在帧尾提供 `repaired_in_update/last_repaired_update_ns`，比v2入队计数更有区分力；replay按组标记、reprocess释放hold及目标组前defer的源码形态也接受为**待运行实现**。

但main driver仍在 `recovery_node.py:2097` 以 `repaired_fed>0` 设置 `repair_entered_estimator`，全文件没有消费 `repaired_in_update`。因此上轮“入队被命名为进入估计器”在**集成层尚未关闭**。S1需在replay实际推进后读取/关联update回执；fed保留为queue字段，不能继续直接当estimator证据。离线 `83/899` 是对旧ctrl2标签的算术纠正，不是v4已经在宿主上正确标帧的运行证据。

## 4. 主线/旁支与下一单一交付

- **主线**：S1/S2只收敛同边界预武装与真实update回执，随后才在用户恢复授权下有界复验合法cp→accepted E1→真实update/map→实时输入→E2。
- **必须先做**：上述双命令边界控制；否则可能再次得到晚cp或空图，浪费有限run。
- **可并行**：S3已修reader等待真实导出；F3 `message_disposition`目前只证明driver自身分类，host/driver跨层join在driver中未实现，下次run可用离线原件对账，不必为上线另造框架。
- **延期**：新模型、阈值扫描、通用checkpoint框架和任何新host矩阵。冻结科学门不变。

本轮为源码/控制面的局部推进，不增加A/B总分；A4/A6/A10/B11仍待真实整链。命令：`C:/Python315/python.exe -I -B docs/review_20261113_4cacc31/closure_checks.py`，exit0。未执行ROS、构建或生产算法。仅提交本增量、控制JSON和历史索引，不合main、不改历史或私人文件。
