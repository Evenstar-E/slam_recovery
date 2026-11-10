# Codex 独立复现与集成验证 · 2026-11-10

**交付状态：独立验证包已完成；目标算法验收未通过。** 本轮把协作表中的正常路径问题变成了可复跑的验收检查，并用 Git 原始 CSV 重算了事件对应关系。没有修改生产算法，没有运行 ROS、bag、训练或原生重估。

本次是新增 Codex 会话的本地验证，不是 S1/S2/S3 的开发或运行状态确认，也不是论文收益实验。

## 1. 实际版本与环境

| 项 | 本次实际值 |
|---|---|
| 分支 | `codex/independent-reproduction-20261110` |
| 被验证源码 | `39eac2f337eaf2b9df28aa0e9b015b36d0ecf34d` |
| `slam_recovery` 目录 Git tree | `b147adc5d82e6c0f2bd24b237c07feeffd04f186` |
| 协作说明及上游探针 | `review/repair-f3-handoff-20261110@bd85346a42c2540dc80dcbd5ca301cac3659e386` |
| 开工时抓取的 main | `f20a5468292997a815f2d75545099c6396bb9733`；其 `slam_recovery` 与上述基线无 diff。本报告固定验证39e，不自动追认后续提交 |
| 实际环境 | Windows 11 / Python 3.12.14 / NumPy 2.3.5 / Git；复用已有 bundled runtime，未安装依赖 |
| 加载位置 | 新独立 worktree 的 `slam_recovery/__init__.py`；精确路径见收据 |
| 修改范围 | 仅本目录中的脚本、报告、验证结果；生产目录 `git diff HEAD -- slam_recovery` 为空 |

独立工作树隔离了旧 checkout；这不等于已在全新容器或独立原生宿主复现论文结果。SHA、完整命令、退出码、耗时及导入路径见 [run_01/result.json](run_01/result.json)。上游两脚本按原字节保存，来源见 [upstream_sources.json](upstream_sources.json)；没有合并审阅分支的全部历史。

## 2. 验收结果与主线关系

| 检查 | 结果 | 本机观察 | 主线影响 |
|---|---|---|---|
| 原有核心 unittest | PASS，60/60 | 原测试保持通过 | 说明已有测试覆盖内无回归，不抵消下面的失败 |
| 子集提交→新来帧→第二批提交 | PASS | 先修2后 pending 为3、4；再修3、4后全部归入 trusted | A5已有分批路径确实可用 |
| 报警当帧登记 | **FAIL** | 帧2触发报警，scan buffer有2，但pending为空；随后帧3正常登记 | A5：第一次报警的那帧可能没有恢复机会 |
| 修复→第二次迟到检测 | **FAIL** | 修复2、3后再次回退，trusted为空、pending仅1、4；2、3不在两者中 | A5/A9：回退删除了修复结果，却丢失原帧的待修归宿 |
| 隔离期间新来帧的撤销时间 | **FAIL** | 实际0.4秒的帧4，repair undo登记0.3秒；第二次onset=0.35秒时，4仍留在trusted | A9：晚来帧会漏撤销 |
| 弱方向的坐标平移一致性 | **FAIL** | 只平移世界原点2米，MODE2接纳变MODE3等待 | A7：判定仍依赖坐标表示 |
| 协方差的坐标平移一致性 | **FAIL** | 只平移世界原点5米，MODE2接纳变MODE3等待 | A7：另一独立的坐标依赖路径 |
| trace配对工具正负例 | PASS，5/5 | 拒绝缺STATE、重复身份、交错GROUP、缺package；乱序仍按身份配对并暴露时间差 | 支持A11评价有效性 |
| 3份CSV原件及runner收据核对 | PASS | 原Git blob SHA一致；Windows副本仅换行不同；按事件身份完成重算 | 支持A2/A11、B6/B8；不证明原生恢复收益 |

六项目标不变量中为 **1通过、5失败**。本包总入口返回1，与这些失败一致。原有60测及配对工具5测的通过，不应合并成“整个系统通过”。本轮不重评分整张A/B表，不修改冻结P0–P5；`paper_ready` 没有因此变为true。

## 3. 为什么失败，以及最低修改范围

### A5/A9：正常事件生命周期

详见 [normal_paths.py](normal_paths.py) 和 [原始结果](run_01/normal_paths.stdout.txt)。

1. `OnlineRecoveryTransactionNode.step_frame()` 的 HEALTHY→QUARANTINED 分支调用了 `trigger_quarantine()`，却未把触发报警的当前帧登记进去。已经处于隔离状态的后续帧才调用 `register_quarantined_frame()`。因此不是所有隔离帧都丢，而是分支切换时漏了报警帧。原始点云仍在 scan buffer，本报告不称原始数据被删除。
2. `manager.trigger_quarantine()` 撤销 repair undo 时，明确不把该条目加入原始 backend delta 队列。这能避免拿修复状态冒充原始观测，但缺少另一条路径恢复原帧的 pending 身份，结果2、3失去待修登记。
3. `register_quarantined_frame(key, timestamp_ns)` 收到时间却只保存 key。后续 repair undo 全部使用旧 `segment.t_end_ns`，本例把0.4秒来帧记成0.3秒。第二次按0.35秒截断时自然漏掉它。

最低修复应围绕**帧身份、真实观测时间、当前归宿**建立一致记录：报警当帧也登记；回退修复时恢复原始帧引用而非伪造原始 BackendDelta；撤销按真实帧时刻或明确声明的原子回溯边界处理。仅把整个段的结束时间改大，不能证明每一帧的时间语义正确。

经理级测试复用了现有A9测试的候选构造，预先提供通过的几何/收益证据，用于隔离事务行为。节点报警测试仅替换 detector 的返回决策，以稳定进入该分支，实际调用生产 `step_frame()` 和登记链路。它们**没有验证真实检测精度、候选几何质量或原生建图**。

### A7：同一问题换坐标，门却改变

详见 [a7_acceptance.py](a7_acceptance.py) 和 [原始结果](run_01/a7_acceptance.stdout.txt)。

| 构造 | 原点不变 | 平移原点后 | 直接原因 |
|---|---:|---:|---|
| 真实点云FIM，平移2米 | after信息48.726302；接纳 | after信息12.507525；等待 | 伴随变换后的弱方向又按欧氏范数单位化，改变了物理方向的尺度 |
| 正确搬运协方差，平移5米 | 协方差谱范数0.200000；接纳 | 谱范数0.628026；等待 | 原点变化后直接比较包含旋转/平移耦合的谱范数 |

作为对照，未重新单位化的二次型在第一例保持48.726302，协方差搬回原坐标后的最大元素误差分别为 `1.04e-17`、`5.55e-17`。因此不是变换代数失效，而是当前门的度量没有固定到同一评价基准。

S3应把弱方向、信息矩阵、协方差统一到明确的评价原点、切空间与尺度后再做判断。只删除一处单位化、改frame字符串或放宽阈值，不能同时解决两例。这里判断的是同一物理评价的坐标重表达；若有意改变实际评价点，应单独声明，不能混作gauge变化。

`upstream_a7_gauge_probes.py` 的退出0仅表示“成功复现缺陷”，它断言的是旧错误行为；新增 `a7_acceptance.py` 断言期望的不变量，本轮正确返回1。将来修复后的验收应使用后者。

## 4. 原生trace的独立重算

输入直接读取固定39e提交中的Git blob，没有把已有汇总JSON当数值来源。[trace_events.py](trace_events.py) 先在单一writer流内关联GROUP→下一STATE，再使用 `(img_stamp_ns, mesures)` 对应跨运行的事件；GROUP支持字段也必须相同。缺失、重复、交错关系明确失败，不按行号硬配。

| 计数 | DEFAULT | ON#1 | ON#2 |
|---|---:|---:|---:|
| ARRIVE | 599 | 599 | 599 |
| GROUP / STATE | 1766 / 1766 | 1766 / 1766 | 1766 / 1766 |
| IMUINIT | 5 | 5 | 5 |
| 空IMU的GROUP | 884 | 884 | 884 |
| 完整“空阶段→非空阶段”图像事件 | 882 | 882 | 882 |
| 首部非图像初始化事件 | 1 | 1 | 1 |
| 尾部仅空阶段的图像事件 | 1 | 1 | 1 |
| 不同图像时间身份 | 883 | 883 | 883 |
| 同package的GROUP/STATE时间标记不一致 | 878 | 0 | 0 |

三份GROUP和IMUINIT摘要支持相同。884个空组中883个带图像；这是实际子阶段分布，不能直接解释成“半数帧同步坏掉”。`mesures` 是原日志拼写，表示记录中的measure数量，本包没有据此虚构传感器帧数。

| 对比 | 匹配package数 | STATE时刻不同数 | 首次单轴位置差>1mm，0起始事件号 | 最大单轴位置差 |
|---|---:|---:|---:|---:|
| ON#1→ON#2 | 1766 | 0 | 87，1.192mm | 309.706199m |
| DEFAULT→ON#1 | 1766 | 878 | 75，1.104mm | 424.605314m |

这些是**匹配处理事件上的输出差异**。DEFAULT/ON有878处STATE时刻不同，不可把其最大差值称为同一物理时刻的轨迹误差；所有数值均非GT、ATE或RPE。ON对虽然时间标记一致，也只说明复现差异，不定位完整原因。

归档补丁的GROUP读取更新前的 `last_lio_update_time`，STATE在 `stateEstimationAndMapping()` 后再次读取它；时间列并非不可变的事件ID。DEFAULT和ON的二进制、动态库及CPU绑定也不同，不能由此单独归因于一个编译开关。

三份CSV的checkout SHA与收据不同，但LF规范化后逐字节相同；Git blob原件与收据SHA吻合。全部归档记录 `status=OK`，同时明确 `termination=PLANNED_KILL_AFTER_DRAIN`、node退出137，不能转述为原生自然退出0。800条odom是收据中的数值，本机缺原output bag，未独立重算。

缺少原始输入/输出bag、完整宿主build与GT，本轮对原生重跑、完整IMU内容、全状态一致、独立地图收益及成本均为 **UNAVAILABLE / 未验证**。时间戳hash相同不等于传感器数值内容全相同。

## 5. 复跑

依赖仅Python、NumPy、Git。需保留39e与4255提交对象；archive重算固定39e，A5/A9和A7验收加载当前checkout源码，收据记录实际HEAD与源码SHA。复制本目录到后续修复分支即可做集成验证；接口改变需明确适配，不能改变期望结果来追求通过。

在仓库根目录执行，`--output` 必须是新目录：

```bash
python -X utf8 -W ignore::SyntaxWarning -B docs/independent_reproduction_20261110_codex/run_checks.py --output docs/independent_reproduction_20261110_codex/run_new
```

本次入口真实运行输出在 [run_01](run_01/result.json)。当前应返回1，且结果中：核心测试0、normal_paths为1、a7_acceptance为1、trace工具测试0、trace重算0。不要把总返回1当作环境错误后自动重跑；查看每项结果中的FAIL/BLOCKED。

也可单跑 `normal_paths.py`、`a7_acceptance.py`，快速确认修复。两个上游探针原始复现收据另见 [command_receipts.json](command_receipts.json)；不需要重新播放bag复现这些问题。

## 6. 交接与停止边界

| 分类 | 下一具体交付 | 负责人/协作边界 | 完成条件 |
|---|---|---|---|
| 主线目标 | 同一运行检测→隔离→候选→采用→继续输入及第二事件 | S1统筹；本包不代替原生运行 | 联合地图/轨迹/覆盖/正常安全结果，失败纳入分母 |
| 必须先修的状态问题 | A5/A9三个正常路径缺口 | S1指定单一manager负责人；Codex提供本包验收，不抢写共有代码 | 保住partial_retry正例，并让报警帧、二次回退、晚来帧三例通过 |
| 必须先修的判断问题 | A7固定评价基准 | S3负责算法；Codex接续复验 | 两个gauge不变量通过，保留原正常/混系拒绝测试 |
| 配套证据 | package身份与时间口径 | S2负责宿主，S4/Codex复算 | 使用本轮身份结果，缺raw内容明确保留；不为计数说明重跑宿主 |
| 延后项 | 极端异常完备、E3共同基扩展、模型/故障扩展 | 维持协作表范围 | 仅实际消费或新主线证据需要时重开 |

本轮推进的是**主线正确性阻断的可执行定位和跨机器交接**，没有新增地图修复收益。下一步应交付A5/A9最小修复以及S3的A7修复，随后用同一包复验并回到限定原生闭环；不要继续扩大审计清单。本包通过独立分支发布，供S1及其他协作会话读取或集成，不直接合入main，也不改变远端协作分工。用户已要求此后每批完成工作均提交；沿用独立分支提交并推送，记录验证结果及失败项。

本目录的 .gitattributes 使用 -text 保留交付原字节，避免Git换行转换使日志或SHA清单失配。
