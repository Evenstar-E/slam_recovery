# FAST-LIO 18:00截止独立报告：双事件逻辑链突破，完整恢复与自动检测未完成

面向：用户、开发S1/S2/S3与独立复核者。截止 **2026-11-13 18:00（UTC+8）**。18:34:15复核时，截止前最新开发main为 `5494cdbd324377de9cfcfa1392f4bd56cf3a28f8`，growth为 `d265903904fc8987b00a31e2d32c80d51cc992f4`；18:24的 `d9e4f34c251a526f3c0aa2cd4beb5a4dc074f6ea` 仅新增协作记录和TODO，**不计为截止前新实现或运行**。

已读AGENTS、PROJECT_HISTORY、A/B标准、REVIEW§10、今日任务和最新“功能先于内存/速度/实时性”的直接要求。一次性18:00任务已触发并自然消失，20min/2h/日报仍由repair-f3持有，无旧owner双写；无Codex分派或等待。私人handoff及本地未提交审阅材料未读、未公开、未纳入提交。

本报告只核Git原件、固定源码与已获取开发回执；**未代跑ROS/宿主、未重建、未安装、未修改算法或科学门**。S1/S2/S3均有实际交付，任务接收和开工已确认；远端当前进程状态不由Git推断。

## 1. 总结

**判定：部分推进，今天“完成FAST-LIO上的所有自适应ALI、自动检测以及二事件问题”的目标未完成。**

最重要的真实进展是：授权排空run首次在同一次运行中让 **E1与E2都实际触发，并对E2形成真实候选判决**。这证明事件识别、后继输入和第二事件处理逻辑已取得功能突破，不再停留在接口设计或单事件。

但它仍是 `CONTROLLED_INTERFACE_TEST`：

- E1走 `HOST_NATIVE_RECOVERY_TAKEOVER`，不是实际测量修复；
- E2候选 `MODE3_SOFT_BRIDGE_WAIT`、`accepted=false`，没有成功恢复；
- E2 restore被宿主以 `checkpoint_invalidated_by_re_slam` 拒绝，未reprocess；
- 收尾 `WAITING_FOR_EVIDENCE`、quarantine仍开放，尾段未闭合；
- E2在bag结束后的排空期处理，**不是实时能力证明**；
- ALI-H真实FAST-LIO通道、独立正常校准/故障标签和自动在线检测均未交付，性能不可评价。

因此不能把“双触发”“有candidate”“HEALTHY/takeover”“测试数”写成全部目标完成。

## 2. 截止run身份与原生状态范围

独立清单见[deadline_audit.py](deadline_audit.py)及[deadline_evidence.json](deadline_evidence.json)，命令：

```text
C:/Python315/python.exe -I -B docs/fastlio_deadline_review_20261113/deadline_audit.py <新JSON路径>
```

脚本exit0，固定读取 `two_event_drain_authorized/` 的pre_run、run_summary、candidate、capabilities和input_fates，不执行归档宿主代码。

| 身份项 | 截止证据与边界 |
|---|---|
| host | MM-LINS派生FAST-LIO前端独立工作区，不自动称原版上游FAST-LIO2；本次仅前端，无PGO |
| binary | v7 `a40e20d516b14914728c98baf6b8807868bd6eb9b6f47523818c4caf1d7f0852`；构建成功为开发归档，本机未独立重建 |
| input bag | SHA `a924b5f9b593fad111f2ef91197735b85c8d26d340f04d5ca61535f25eaaf2de` |
| E1/E2 | `1711547999352267771` / `1711548113452267771`；均按绝对stamp scripted触发 |
| driver | pre_run写 `0b4dc78+`，不是完整不可变SHA；config/source完整身份未在该文件闭合，A12不能称完整复现 |
| checkpoint内容 | ESKF state/cov、ikdtree点集、time cursor；**不含**IMU preintegration、deskew cache、external poses graph |
| 原生失效语义 | re_slam使cp失效，需重新snapshot；reprocess仅PARTIAL缓冲重放，不等于完整历史恢复 |

## 3. 逐项验收

| 检查项 | 截止状态 | 实际证据、影响与下一动作 |
|---|---|---|
| 任务接收/责任与真实运行 | **PASS** | S1共享集成、S2宿主、S3研究均有版本化交付；多次授权run和负结果原件存在。远端进程当前状态不推断 |
| E1→后继→E2逻辑链 | **PASS组件／完整链PARTIAL** | E1 actual 115.599s、E2 actual 229.696s；2 episodes、second_and_later=1。E1 takeover+abandon，E2有实际decision。下一步闭合E2段和尾段 |
| E2候选与修复结果 | **FAIL（恢复未成功）** | cand_0001 Mode3、accepted=false；只有1 paired frame而要求4，paired benefit MISSING，reentry jump 9.3956905m。需真实证据/候选，不把拒绝当恢复 |
| checkpoint/restore/状态地图 | **FAIL／PARTIAL** | E2 restore=`valid=0 reason=checkpoint_invalidated_by_re_slam`；cp缺IMU/deskew缓存。driver却把scope写成ROLLBACK_ONLY、后续写成CONTINUES_FROM_RESTORED_STATE，须改NO_ROLLBACK/UNRESTORED |
| 真实测量修复→原生update/map | **NOT_EXECUTED（截止run）** | repair clouds published=0、reprocess=0；candidate_source=host_poses。ctrl2的83组PARTIAL replay与地图增长是另一受控证据，不能贴成本run修复或净收益 |
| 全输入归宿/拒绝追赶 | **PARTIAL** | driver 2085 paired/ingested，515 scans unpaired；never 2081、deferred 1、skipped 3；fully_accounted=true但fully_decided=false。host 1269 ingested+982 quarantined，无replayed。catch-up未实现，driver true不外溢为全宿主成功 |
| 段关闭/重武装/尾段 | **FAIL（未闭合）** | final WAITING_FOR_EVIDENCE、quarantine_open_at_exit=true；bag+drain结束后STALE。E1 rearm已成立，E2 Mode3等待段未关闭 |
| ALI-H真实M/I/T/support | **BLOCKED／T NOT_APPLICABLE** | reader 11个合成用例通过；真实FAST-LIO M/I同update导出未交，T按F2结构判断不存在。无本host逐帧/块三态和UNKNOWN区间 |
| 独立校准/标签/同人口比较 | **BLOCKED／NOT_EXECUTED** | 无独立正常前缀和故障标签；开发实测bag仅IMU+LiDAR、无GT，本机未重跑rosbag。旧方法vs ALI-H同人口评价未执行 |
| 自动检测/自动动作 | **NOT_EXECUTED** | 两事件都是scripted绝对stamp，run_mode明确CONTROLLED_INTERFACE_TEST。旧检测/宿主休眠信号不是ALI-H自动检测通过 |
| 召回/误报/延迟/onset/错误NORMAL | **NOT_EVALUABLE** | 无独立标签与在线检测人口，不能填0率；真实UNKNOWN总时长/最长区间也不可从空导出填0 |
| 净收益/四策略/独立参考 | **NOT_EVALUABLE** | 无真实accepted修复、无同人口原生/只隔离/无条件修复/完整门控和独立ROI/GT；不能从地图点数或位置范数宣称收益 |
| 成本与实时性 | **PARTIAL／非实时** | driver wall 334.505s、PID峰RSS 2,446,880KB；pose mean 98.4ms、scan 24.266ms、ingest 69.943ms、nis 54.735ms。E2在drain期处理，整链峰值/费用UNAVAILABLE；只诊断，不设放行门 |

A2/A10有真实运行和两事件逻辑推进，A3/A4/A5/A6/A9/B2/B3/B4/B11未完整闭合；不全表重评分，不沿用旧16/36、11/36作为当前分数。

## 4. 负结果与阻塞归因

**已证工程/功能缺口**：
1. 队列曾挤掉E1后233条突发消息，修正后才使E2可达；这是输入功能正确性，不是性能调优。
2. E2宿主reset使checkpoint失效，restore真实失败；driver失败归宿误写为已回滚，须优先保证结果诚实和状态安全。
3. E2段在限定drain窗口结束时仍开放，完整生命周期尚未完成。

**算法/科学证据缺口**：E2只有1个paired frame、独立收益证据不足；ALI-H真实导出、正常校准和事件标签均缺。无法判断候选方法能否成功，也不能据此宣称信息不可恢复或模型永久失效。

**宿主因素**：原生休眠/re_slam反复存在，但最新E2已经能发布并触发，不能继续把当前未闭合简单归因“宿主未到E2”。

**参数**：没有同版本、同人口的参数变化—效果/代价和改善上限证据，不恢复调参或改变冻结科学门。

**资源**：成本、内存和速度只作后置诊断。按用户直接要求，先功能正确，再优化实时性；不以CPU/RSS或预算阈值阻止下一次功能验证。

## 5. 下一单一主线交付与责任

**先完成E2段和尾段的真实闭合**：在同一功能链中，E2判决后的restore/拒绝归宿必须与宿主真实结果一致，段关闭或明确安全终止、后继输入有归宿、尾段完成；成功动作才按真实update/map验收，拒绝则写NO_ROLLBACK，不把开放WAITING写成完成。

- **S1**：修正在valid=0时仍写已回滚的功能错误，交E2段/尾段实际结果；
- **S2**：保宿主reset/cp失效和原生输出原件，执行后续实际获授权的功能run；
- **S3**：复用reader，待真实M/I导出后交ALI-H资格；没有标签继续NOT_EVALUABLE，不阻主线；
- **S4**：只核实际结果，不新增工程、算力或内存放行门。

完成这一闭合后，下一独立里程碑才是**真实accepted测量修复→原生重估/map→接回→E2**。资源优化放最后，不提前。

## 6. 截止后增量与持续任务

18:24的TODO没有新代码或run，不补记为截止成果。其中“把`--require-contract`固定进所有后续run”的建议与最新“链条优先、工程诊断不设放行门”的直接裁决冲突，**不作为后续前置**；A1段关闭与A2真实accepted链才是功能主线。

本报告是截止核验，不自动停止20min/2h/日报，不杀未知进程、不授权新重试。已完成的实际功能子项给予接受，未做保持NOT_IMPLEMENTED/NOT_EXECUTED，缺标签保持NOT_EVALUABLE，负结果全部保留。
