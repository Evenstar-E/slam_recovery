# 0bdd1f4：实际检测与ICP组件有进展，原生恢复和第二事件仍缺接口

2026-11-10。开发目标 `0bdd1f494f62f3941865700a8f321b080933f1b2`，比较基线36e9bef，三笔增量（ead841c/a59d145/0bdd1f4）。本机已读AGENTS、项目历史、评分表及REVIEW§10，核三项自动任务属于本会话，旧owner未见运行；忽略stop.md，保护私人handoff。审阅不改算法、不调门、不代跑ROS。

**结论：部分推进，不再称只有离线统计。**新原生宿主＋旁路节点实际运行在注入附近报警，ICP候选生成模块的现有13个测试函数本机通过。但本趟候选仍是缓存host poses，0接纳、1次决定、E2为0、最终WAITING。没有实际宿主checkpoint恢复、测量重处理和内部状态/地图写回；375条决定后消费不是接回成功。

## 1. 接受的交付和版本绑定

- 固定Git原blob `slam_recovery/ros/recovery_node.py` SHA256为 `29940c086922c3724bb68a7c86b4c1d8311da4b6cc36c815170708e22db3f04c`，与receipt一致。receipt/summary/wiring/candidate的run ID同为 `fl_native_20261110T035825Z_3008585`。实际输入room02_2x2_O、SHA `f8b26ddf54838f5314be664cf4c49e13b5f5ab476118811e135cbc89c118751d`；rate1、drain3、sigma=.884、detection on、candidate_source host_poses。
- 归档800pose/599scan、584配对、15未配scan/216未配pose、364检测可用/220未检测摄入、backlog116、墙钟75.193s、RSS386208kB、callback error0。接受这次覆盖改善，不由此证明持续1×余量或全输入完整。独立host/recovery PID同PGID是进程管理，不是内部恢复。
- 按报告引用的room audit onset `1627643759554082870` 重算：首次报警 **−0.027424097s**，隔离 **+0.105644942s**，估计起点−0.127424097s，决定+2.236528636s。27ms是绝对时差，不是正检测延迟；单次近onset报警不证明系统性起点无偏或完整B3召回/误报性能。
- 197/197非HEALTHY是开发报告读数，未取得逐帧原summary独立重算；状态不关闭造成持续非HEALTHY，不能当197次独立检出。单窗口命中可描述，事件定义/早报容差未独立冻结，不能自动升级为完整召回验收。
- 新 `pose_reregistration.py` 是真实点到面ICP候选生成实现，不再称根本没有修复代码。本机直接调用既有13个无参数 `test_*` 函数，13PASS、0FAIL、48.15s，打印加载路径绑定目标包；**不是pytest运行**，不声称ROS集成通过。已知pytest环境缺失不重试/不安装。
- driver `decide()` 仍直接 `repaired = {kf: pose for ... ep.frames}`，没有导入或调用ICP；CLI允许 `icp_reregistration` 但只将其用于来源字段，当前不能用这个选项证明已执行重配准。报告引用的 `icp_candidate_offline_results.json` 在目标Git tree和本机均不存在，离线实际跑分记UNAVAILABLE；脚本存在不等结果已交。该脚本使用注入onset选择离线人口，不能直接复制成oracle在线触发。

## 2. 拒绝定位：时间基确有问题，但不能宣称修一处就通关

归档cand_0000：22帧host poses；信息before/after 1.101917/4.628084；holdout NIS .094753；17/22配对改善，Wilson .600983、局部paired approved=true；位置差1.250633m。实际report先命中segment boundary分支，聚合evidence_status FAILED。局部paired通过不等完整准入通过。

### 接受的正常路径问题

`extrapolate_incumbent()` 将incumbent搬到各候选时间，却返回**旧时刻anchor**；node `_measure_paired_evidence()` 将候选首帧与这个anchor直接相减。首个committed run的dt0还以候选首帧为时间基，未包含旧anchor→候选首帧的间隔。两处判据须保持同一时间定义，不能只改一个jump字段。

本机最小反例：[reentry_time_probe.py](reentry_time_probe.py)，命令：

```sh
python -B docs/review_20261110_0bdd1f4/reentry_time_probe.py
```

复用真实extrapolation和node原始jump函数：连续0.3m/s、2.328956843s的运动被量成0.698687m、超过默认0.5；时间对齐的差为0。连续0.1m/s则仅0.232896m、不超限。因此问题是**可能把经过时间的运动当跳变**，不是“只要移动且margin>0就永远拒绝”。另算时间对齐后真实1m瞬移仍为1m，仅作评价定义控制，未实现fix或证明完整gate PASS。脚本首次因精确浮点相等断言失败，审阅fixture改isclose容差后通过，未改生产阈值。

### 本次实际候选不能被直接洗成连续或接纳

1. 归档tail速度为 `[.144856,.032990,.013337]`m/s，模长约.149163。旧anchor到trigger约2.329s，现匀速模型只预测.347394m。由三角不等式，按该模型搬到trigger后与候选的差**至少.903239m，仍大于.5**。单看1.25/2.329≈.54m/s“像步行速度”不能证明这是正常连续运动；该模型也非独立运动真值。
2. 即便解除边界，`core.py`后续仍要求 `info_after >= tau_info=25`；本候选4.628084未满足。不能据“唯一首个拒绝reason”说只有一个不满足条件，或承诺时间外推后Mode2必达。posterior covariance亦未在这份候选记录中提供完整独立核验。
3. 最低修正是明确同时间边界/相对运动依据，复用上述正常运动＋真实跳变控制，不提高0.5、不降低25、不扣除任意运动制造通过。仅匀速外推/速度包络仍标BOUND_ONLY，非独立连续性证据。实际拒绝保留，不要求必须Mode2。

## 3. 新归因不能覆盖已有身份和反馈边界

这部分随实际交付一并更正，不要求为措辞新采集、新σ扫描或新统计框架。

- `A10_B11_sigma0884_run.md` §3称旧replay使用“早期冻结小参考”，不符合其来源：旧detection-off诊断可信图持续长到373关键帧，replay使用该增长图产生的已存NIS。参考/人口、真实support/FIM分支、首次隔离后的反馈不同均可能影响；不能未经控制就宣布差异“不随机且唯一由静态/动态参考导致”。接受本次真实近onset触发，不苛求不同随机运行逐数一致，也不从混人口曲线拼因果。
- 新 `hall01_injection_severity.json` 是hall输入（onset `1627785275607408524`），本次检测及旧replay是room输入（onset `1627643759554082870`）。本机核hall归档598记录、200差异帧/窗内200帧、0字节相同窗内帧、20桶计数合200一致；原bag未本机读取。这不能证明room尾部未标帧都是漏检，不能据此撤销room的UNCONFIRMED。字节改写行数也不是独立标定的故障强度/必报警标签。
- sigma=.884仍是同开发数据、启动箱n=2选择，并同时改变live NIS与candidate holdout/paired尺度；探索价值接受，不称独立校准或旧科学准入配置已通过。保持原负结果和未知边界，不继续盲调。

## 4. 下一单一主线交付与最小分工

沿用[最高优先运行任务](../NATIVE_RECOVERY_RUN_TASK_20261110.md)，不重新造轮子：

| 类别 | 责任与下一交付 | 验收/不阻断边界 |
|---|---|---|
| 主线：原生恢复→接回→E2 | S1集成、r11070-c3宿主执行：接实际checkpoint/测量重处理/状态及内部地图写回，并让真实Mode3段继续收证据、形成后续候选/有限终态、重武装 | 一次限定运行，给真实动作、宿主恢复状态、持续输入和E2；若无接口给第一处宿主文件/函数及最小实现，不再仅交σ/状态计数 |
| 当前候选接线 | S1/S2沿新ICP模块复用，不只改source标签；提供已有离线结果或如实UNAVAILABLE | pose-level ICP不等测量过滤、deskew/速度/bias重估或原生内部地图恢复；不能替代主线接口 |
| 最低评价修正，可并行 | S3（既有A7责任），由S1确认边界metric接口写入责任：旧actual node固定基正则＋本次时间基最小修正 | 只修正常评价问题；不重写正确transport、不调epsilon/门。匀速控制通过不要求本次真实候选接纳，不挡宿主恢复接线 |
| 旁支 | Codex复用工具独立核集成；KITTI/四策略待主线证据 | 不新增参数矩阵、极端测试框架、日志字段或“已收到”提交 |

主要阻塞属于**工程接口/生命周期实施**：`recovery_node.py:707`先置decided，后续`on_pair():599`不再扩该episode候选，manager仍有active quarantine，`finish()`也跳过；status Publisher没有宿主restore/writeback接口。这些旧具体缺口在本版本未解除，后续375消费不能代替接回。评价时间基/A7是必要数学依赖；ICP真实净收益及独立运动依据未验证，不猜算法必败。参数探索已有进展，但不能靠调sigma解除缺失接口，故不是当前首要阻塞。

各角色当前工作树/branch/运行中进程仍须直接回报，不能从归档推现在正在做；早期任务采用不能证明最新任务已阅读。下次实际交付按REVIEW§10.12提供PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令、source/host/input/config、完整人口和证据路径，不另交纯收到报告。

## 5. 自检与A/B范围

见[local_checks.json](local_checks.json)：固定source SHA/run关联、13个既有ICP函数、5Python AST、runner `bash -n`、hall归档计数、时间反例与算术均核过。13函数执行命令为目标包import后遍历 `inspect.getmembers(module, inspect.isfunction)` 的全部 `test_*`，逐项直接调用，列表/用时已归档；未伪造pytest。可在本源码根复用以下命令（本机实际运行还记录逐函数用时/错误）：

```sh
python -B - <<'PY'
import sys, importlib, inspect
sys.path.insert(0, 'D:/REPAIR/slam_recovery_upstream')  # 其他环境换成其目标源码根
m = importlib.import_module('slam_recovery.tests.test_pose_reregistration')
print(m.__file__)
for name, fn in inspect.getmembers(m, inspect.isfunction):
    if name.startswith('test_'):
        fn()
        print(name, 'PASS')
PY
bash -n slam_recovery/ros/run_native_loop.sh
```

语法警告保留，不为未变docstring扩工程。

| 范围 | 状态 |
|---|---|
| 真实订阅/配对/检测/一次决定的归档身份 | PASS（归档核验，非本机ROS） |
| ICP既有合成函数测试 | PASS 13/13（本机实测，非真实输入跑分） |
| 不同时间运动混入jump | FAIL缺陷复现；最低反例脚本运行PASS，不是生产fix验收 |
| ICP离线真实结果/在线调用 | UNAVAILABLE / 未接入 |
| 原生内部恢复、接回、E2 | BLOCKED / 未交付 |
| 原68核心重跑/新完整评分 | NOT_APPLICABLE，core/manager/node本轮未变 |
| driver pytest suite | BLOCKED（已知环境缺pytest），未重复失败或安装 |

局部进展映射A2/A3/A6组件、A7评价、A9/A10及B3/B11范围；接受新实际检测尝试/ICP组件，**不升完整A10/B11，不继承旧总分作当前全表评分**。仍未完成用户优先的原生恢复→接回→第二事件。
