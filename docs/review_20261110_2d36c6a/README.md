# 接手复验：完成项、未完成项与七组卡点

日期：2026-11-10（UTC+8）。源码目标：`2d36c6a116535570f497f73706e24740a551a13a`，开发增量截止 `c82eece`。本报告不覆盖旧评分、旧负结果或旧失败记录；不修改算法，不运行 ROS/bag。

[可视化说明](status.html) · [可运行反例](boundary_probes.py) · [旧24项全表复验](../assessment_20261110_773b995/README.md)

## 1. 结论与复验范围

已有真实的**离线测量过滤→FAST-LIVO2原生重估→sidecar地图重建**链，以及 hall 条件性正结果、room 负结果。完整原生在线恢复、门控增量、独立泛化和独立发布仍未闭合。

旧全表评分固定于 `773b995`：A=16/36，B=12/36，24项完全闭合0。相对 `7fc67cf` 只有 B8 由1→2。本次只核最新 A5/A8/A9 边界、相关源码与方案，不把旧总分赋给最新提交，也不因46条测试通过自动升档。

最新局部变化：
- A5 `0a196b4`：已撤销/暂存帧的初始登记、开放隔离段期间新来帧登记已实现；两个新测试通过。**报警触发当帧仍漏登记。**
- A8 `4b1c926`：factor迭代器/pose mapping中途异常的旧半提交反例已修；stage失败恢复state，两负一正控制通过。**前置校验异常仍留VALIDATING；空间地图仍在manager提交之后单独更新。**
- A9 `c82eece`：新增方案，不是实现。第二次更早onset后已接纳repair pose仍残留，已本机复现。
- A7：before body-FIM与after world-FIM仍直接沿原弱方向比较；源码检查，未运行原生坐标变换判决实验。
- `1889e52`消费trace最小要求接受为方案，尚非trace实际运行；`7c4f85e/7365838`有界人口诊断仅排除同口径下715ns onset改变帧归属，bag-relative人口不能与旧absolute人口直接混比。两项gate-NIS仍NOT_REPRODUCIBLE、禁止当当前证据引用，不能让这个旁支抢占native主线。

## 2. 本机验证与失败记录

首次从 `D:/REPAIR` 执行绝对路径 unittest discovery，误导入兄弟目录 `D:/REPAIR/slam_recovery` 旧包：16条，2 FAIL、4 ERROR。该结果是**环境/输入身份失败**，不是目标源码回归。随后 `python -I` 加源码根失败，因为 numpy 位于用户site，隔离模式不可见；未安装或改环境。

正确复验使用 `python -B`，显式把目标仓库置于sys.path首位，并打印实际加载manager路径：

```python
import sys, pathlib, unittest
root = pathlib.Path('D:/REPAIR/slam_recovery_upstream')
sys.path.insert(0, str(root))
import slam_recovery.quarantine.manager as m
print(m.__file__)
r = unittest.TextTestRunner(verbosity=1).run(
    unittest.defaultTestLoader.discover(str(root / 'slam_recovery/tests')))
raise SystemExit(not r.wasSuccessful())
```

结果：**46/46 PASS，2.328s**，加载路径确为 `slam_recovery_upstream/slam_recovery/quarantine/manager.py`。既有docstring转义警告保留。三项额外内存反例均复现；脚本入口：`python -B docs/review_20261110_2d36c6a/boundary_probes.py`，输出是反例存在的验证成功，**不是恢复协议PASS**。

## 3. 已完成的局部交付

| 局部交付 | 已有证据 | 不可外推范围 |
|---|---|---|
| 完整点记录过滤/点身份 | PointCloud2记录、scan_ns、原始索引、字节/hash审计 | 历史所有运行尚未统一消费新ID包；时间窗口仍有oracle |
| 实际原生离线重估 | filtered bag进入FAST-LIVO2，真实位姿输出与重建地图归档 | 非在线原生checkpoint恢复；sidecar不等于宿主内部地图 |
| 有界地图评价 | 有限patch、邻域与远点反例；共同集合/clean→GT修正 | clean-run proxy不是独立GT表面 |
| hall条件正结果 | 400/446条件帧：覆盖60.38→98.49%，不支持62.51→9.31% | 46缺帧不能消失；不代表端到端恢复率 |
| room负确认/重复 | 326/398：覆盖76.72→69.52%，不支持45.85→65.90%；重复不稳 | 不能证明跨序列稳定、唯一初始化或过滤根因 |
| A5旧漏登记反例 | 系统登记撤销帧，开放段新帧登记，旧反例两测试通过 | 触发帧仍缺；未验真实宿主完整人口 |
| A8旧半提交反例 | caller iterable先物化、locals暂存，旧两异常测试通过 | 前置异常、跨空间地图/原生状态一致发布未闭合 |

以上称“组件或条件性交付完成”，不称24工作包中任何一项全部完成。

## 4. 七组卡点：机制、例子、最小解除

### 卡点1：隔离人口仍有入口缺口（A5）

旧 `[1,2,3]` 中候选只提交1，2/3丢失的manager反例已修。最新 `step_frame` 中报警帧先放入scan buffer，随后走HEALTHY→trigger分支，没有生成delta，也不会走后面的elif登记。用确定性报警替身触发key2：buffer=[2]、registered=[]。这不是检测器精度测试，是实际入口控制流反例。

影响：该帧既未提交又可能不在pending，候选不提它时系统无法追踪完整人口。最低解除：触发帧在开启隔离的同一入口登记；覆盖正常来帧、报警当帧、Mode3期间来帧、两批提交及幂等重复的节点级反例。不因这项补登记重跑所有历史bag。

### 卡点2：原子性只覆盖了部分异常范围（A8）

旧“pose42/factor999已公开、version/receipt未更新”已修。最新候选parent_version过期：调用抛RuntimeError，state由QUARANTINED变VALIDATING，因检查在新try之前而没有恢复。trusted pose未改变，**这不是旧factor半提交复发**，是失败状态没有返回原状态。另有node先manager提交再`_sync_spatial_map_with_trusted_poses`，没有统一提交边界；本轮未注入空间同步异常。

最低解除：声明失败契约，覆盖gate、parent/evidence检查和staging异常，恢复相关状态；对空间同步/版本/收据的一致发布给最小故障注入。先闭合Python边界，再验原生适配，不能把多次属性赋值本身视作并发读者原子快照。

### 卡点3：已接纳修复没有可逆历史（A9）

本机：首次接纳pose2/pose42、factor420与bias，再以更早onset触发回溯；pose2、pose42仍在可信状态，而factor=[]、bias=[0,0,0]、registered=['1']。这次只证实repair pose残留；不照抄旧“所有因子和bias必然残留”的更强描述。

方案选择不可只按时间排序before-image。反例：先晋升pose2=x2，再修复pose2=x20。若把修复条目按被修帧时间插在旧晋升前面，回滚可能先撤旧晋升、再把修复before-image=x2恢复，最终残留；factor长度标记也依赖实际写入顺序。必须区分**事件时间与写入顺序**，统一撤销依赖或显式拒绝超出支持范围。

最低解除：两个重叠事件、同key重复写、健康后续promotion、factor/bias/地图所有权、partial repair/retry的可观察正负例。当前只有方案，不能报A9已修。

### 卡点4：准入前后不在同一切空间（A7）

before来自body scan，after由候选world points估计；core使用同一个weak vector投影二者。点面旋转Jacobian依赖原点，地图整体平移100m可能改变数值而物理信息没变。本轮为源码不一致，不宣称已实测原生判决翻转。

最低解除：明确左/右扰动及参考坐标，正确transport FIM、cov、weak direction；全局平移/旋转重表达下判决一致，辅以单位/尺度声明。不能放大sigma或抬门限来代替。

### 卡点5：同一次原生在线链未贯通（A3/A4/A6/A10，B3/B11）

当前是已知注入窗→导出filtered bag→从健康前缀原生重跑→sidecar构图。原生速度/bias/filter/tree/cache的完整checkpoint、提交后继续消费与第二事件未给出同进程证据。例：从头离线重跑修好地图，不说明正在运行的机器人能无缝接回。

最低解除：限定单宿主、单故障，单次运行贯通在线检测、检查点、修复、独立验证、接纳或拒绝、接回、第二事件；记录全人口缺测、中断、跳变、积压。1×可持续能力实测，启动成功不等于实时。

### 卡点6：论文增量与适用边界不足（B4/B5/B6/B7/B8/B9/B10）

hall正、room负都成立，尚无同候选流“原生/仅隔离/无条件接纳/完整门控”完整比较。例：gate拒绝所有候选能避免错接纳，却可能永远修不了地图；必须同时测丢失的有益修复。重复不稳时不能把一次好/坏归给某个因素，grouping/IMU init机制仍UNKNOWN。hall/room已参与开发，不能再称全新留出。

最低解除：固定候选流、底图、ROI、共同人口，报告新增正确/错误几何、健康损失、轨迹、46/72缺帧、成本和不确定性；正确单因素/消费trace有界排障后，冻结方法在新环境确认。旧三轮/五轮换模型建议未证明有效冻结，不能自动触发。

### 卡点7：独立复现与成本链未闭合（A1/A2/A11/A12，B11/B12）

hall C3曾引用room运行122.9s收据，已撤回UNAVAILABLE；R=296s为推导而非同口径实测。入口依赖私有运行环境，actual grouping/IMU样本与动态so身份尚未完整。例：exe相同不表示行为相同，代码可能在不同liblaser_mapping.so中。本次还亲自遇到同名本地旧包误导入。

最低解除：可获取固定环境、输入/配置/运行时exe+so身份、统一入口，独立环境重算核心表并记录真实wall/峰内存/吞吐。成本缺失不抹掉条件地图效果，也不阻断现有有效输出的分析。

## 5. 24项账本

完整旧分及缺口见 `assessment_20261110_773b995/README.md`。A：输入/运行身份/历史重估/共同评价为2；在线检测、完整checkpoint、pending、准入、原子发布、多事件、原生接回、复现预算为1。B：损害、净收益、重复为2；保护、检测、门控、因果、正常风险、泛化为1；公平基线、原生在线链、独立冻结发布为0。**这属于旧全表快照。** 最新A5/A8组件修复是本报告局部覆盖，A/B所有阶段总分未重评。

## 6. 主线/旁支交接与自检

唯一优先主线：闭合报警帧登记、失败状态恢复与跨事件repair撤销的最小状态协议，然后给限定的同进程native链。A7 transport/invariance并行推进。消费trace保持安全snapshot、单写者、完整样本ID及扰动对照，不扩大无假设排障。成本来源、字段、旧历史声明集中旁支；不能再每修一字段就重跑全部宿主。

| 检查 | 状态 | 依据/下一动作 |
|---|---|---|
| A5已登记旧集合/新来帧 | PASS（局部） | 新两测试；补node报警当帧反例 |
| A8旧iterable半提交 | PASS（局部） | 两异常+一正控制；补前置失败/空间边界 |
| A5报警帧、A8前置异常、A9回溯 | FAIL | boundary_probes.py，三项本机内存复现 |
| A7 transport | 未通过验收 | body/world路径源码；原生invariance未测 |
| 真实宿主/新效果数字 | NOT_APPLICABLE（本轮） | 本机无ROS运行，旧宿主仅归档 |
| 完整新A/B评分 | NOT_APPLICABLE（本轮） | 不冒充新全表 |

开发侧下轮先按§10.12给逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令/证据、主线推进和调整后的旁支分工；不得只写测试总数。本报告的局部失败不否定hall条件收益，也不等于论文或整个项目必然失败。

接手安全边界：忽略stop.md，暂停/恢复看用户直接要求。旧会话定时任务仍可能存活，接手任务先核所有权，不双写。已泄露PAT需凭据所有者撤销，审阅不使用/复制，不擅自改写Git历史。
