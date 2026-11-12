# 64bfed1审阅：分批修复实际应用，候选冻结有效，收益与E2仍未闭合

- 面向用户、开发主会话S1、宿主执行S2及独立复核者。
- 目标 `64bfed115f7d2058bbfe076caf103491036560c1`，比较 `2f1f59bfdab1203a7ef6eb3eb2e72eb345a7b8cb`；本轮SSH fetch成功，review HEADf810116，未merge分叉main。私人未提交handoff未stage/公开。
- AGENTS、A/B标准、REVIEW§10已读并复用未变内容；实际三Cron由repair-f3持有，无旧owner双写。用户20min/忽略stop.md/旧参数暂停优先；四非LIVO前批尝试边界保留，不重新开矩阵。

## 1. 有实证的部分主线推进

| 运行与source | 实際交付 | 状态/未完成 |
|---|---|---|
| success_batched `045944Z_96435` /8790452 | +0.45m估计，施加−bias；4批10/10/10/2、32received/32applied、676group原生重放、map22334vox/417461点；hold→reprocess→set_state→resume，决定后315配对帧 | PASS传输/替换执行；32commit/**87deferred**，非无deferred；实际修复净收益未验证 |
| control_dryrun `050645Z_102106` /e6f7430 | 同损坏、估计但不发布；23候选、0修复应用，529group原始重放，决定后330配对帧 | PASS有限控制执行；与修复source/候选人口/重放支持不同，不公平效应对照 |
| freeze repair `051523Z_107073` /7b02fa7 | 冻结23候选、23received/applied，815group重放，决定后247配对帧 | PASS冻结入口/实际替换；23commit/147deferred，未全段修复 |
| freeze control `051728Z_109595` /7b02fa7 | 同23个候选pose stamp及freeze stamp，0应用、692group重放，决定后248配对帧 | PASS同候选时间人口；23commit/148deferred，仍非同native重放支持 |

后两driver SHA与target源码完全匹配；前两各匹配报告历史source，不将四run都当target执行。各run都只有一episode/一decision，detection off，**E2全部NOT_EXECUTED**；最后HEALTHY都伴随wait_limit_closed/ABORTED rearm/unresolved，不等有效完整恢复。native failure计数依次1/2/1/4，主要snapshot等诊断不能隐去，亦不等实际重放全失败。

上轮20/26未应用的传输首断点，已在新32/32与23/23实际运行中局部解除，不继续重复要求重修已通过组件；原生替换/重估的组件成果接受。+0.45/+0.40/−bias有实际测量修正，但不能由接收数、应用数、地图变大或set_state接近宣布质量改善、首次有效修复整链或论文主线完成。PLAN_batched写死26、实际32/23应区分声明数值与后来实际人口，保留历史，不能宣称字面26指标已满足。

## 2. A/B人口和区间：已对齐什么、未对齐什么

[本机隔离原件reader](check_archive.py)、[结果](archive_checks.json)核freeze两臂**全部23个candidate pose时间戳列表相同**，不是只按run-local kf/数量判断。freeze stamp同为1627785280281185627；host pose数值、估计及原生处理条件不因此相同。已发布scan stamps也保留、均属于损坏窗。候选deadline crossing实际冻结接受。

原生重放原log：

- repair：815group `[1627785276.348868608,1627785303.492495537]`，跨度**27.143626929s**，23应用，24503vox/473187点。
- control：692group `[1627785275.080903053,1627785298.158921719]`，跨度**23.078018666s**，0应用，21870vox/418979点。
- 起点差**1.267965555s**、终点差**5.333573818s**、跨度差**4.065608263s**、group差123。文档“5.3s跨度差”混淆终点差与长度差，集中更正，不为文字重跑。

因此接受开发“不归因地图差异”的限制；不同支持使净效应UNKNOWN。发布/回执额外成本和滚动snapshot能解释差异方向，但一次观察不测得唯一因果或保证消除此二项就逐值一致。

set_state ACK位置差本机复算**0.046982609m**（约4.7cm非6cm）。这是**主动写入candidate尾pose后的状态**，不能当独立原生重估结果、地图正确或“修复轨迹回可信地图”的证据。该命令与之前原生重放状态来源问题未解除，旧坏云候选先准入再发布新云的物理不一致source仍在，不重跑旧反例。

## 3. 新源码有限控制：有效baseline路径解除，None不得等零

[源码核验和最小交接](source_handoff.md)、[脚本](run_checks.py)、[结果](local_checks.json)。目标Git blob内存加载，其他package无源码目标差异；actual driver/publisher/tracking，receipt与bias模拟，无ROS/host/bag：

- PASS_LOCAL：非零baseline25+本次25，批次等待35/45/50，final50放行；header顺序/减bias保持。
- PASS_LOCAL：第二批receipt失败，停在20条、不发表剩余5，repair gate不放行。不等失败公开/恢复链通过。
- PASS_LOCAL：deadline crossing冻结21帧，后24帧不加候选、首次pending wall不覆盖；两相同时间流一致。不等host replay跨度冻结/pending完整归宿。
- **FAIL_REPRODUCED_LOCAL**：`recovery_node.py:1454–1456`baseline None被`int(baseline or 0)`当0。E1旧累计25、E2新收到0时，发25条却等待10/20/25都可被旧计数满足，final25亦满足错误等式，synced/gate_proceed=true。code-review low提出后本机确认；四归档run有效baseline0，没有声称它们已发生此错配。

**最低解除S1/S2**：None保持UNKNOWN，先取得有效本次baseline再发表/等待增量，复用原status/scan身份，不新RPC。不能因分批和首事件通过就关闭第二事件receipt问题；received仍不等queued/applied/匹配成功。

新frame_freeze/repair_sync测试模块因pytest辅助依赖未本机运行，无安装/shim；小目标控制exit0。未变cloud helpers/已验11tests不重跑。Git Bash `git show 64bfed1:slam_recovery/ros/run_native_loop.sh | bash -n` exit0；初PowerShell调用PATH bash实际是未安装发行版的WSL入口、exit1，未安装，改用现Git Bash工具，仅语法非执行。

## 4. 原件范围与完整性

只读代理核新原件及本机完成必要stamp/算术；代理输出被截断不冒取隐藏结论，已读其MANIFEST/source/replay结果。代理scope69独立路径全一致；本机按全本轮changed manifest路径含PLAN_batched/修改旧REPORT扩至**70/70**一致，不冲突，不称整旧归档/远端大bag已复验。

实际命令：`C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_64bfed1/check_archive.py` exit0。核run source SHA、receipt/report边界、candidate stamps、应用log、重放ns和生命周期；不执行归档runner、不读远端bag/binary。源码控制命令见source_handoff，exit0。原件readback只是实际远端归档，本机未代跑算法/宿主。

## 5. 下一单一主线与最小保障，不能再次陷入A/B日志循环

**下一交付仍是一个物理一致的实际测量修复→原生完整状态/内部地图→接回→第二事件/尾段，或真实第一断点。** 分批与候选冻结已有局部通过，不要求重造/全异常矩阵；先修直接影响实际准入/成功来源的最小正常问题：新云及对应pose作为同一候选，native未应用不发布成功/不无条件resume，保原生完整state/map同stamp、不再candidate尾set_state代原生重估，baseline未知不当0。旧source未改的支持失败默认0/可信checkpoint边界保留，不机械全重测。

S1单写共享manager/lifecycle/成功依赖与集成；S2现measurement/runner/有限宿主运行；S3门研究专用、旧sigma/κ/floor调参停。开发“下一sham”是其方案记录，不当本会话新的用户选择。若沿既有有限任务做sham，它可控制发布/回执成本，但**同样批次或墙钟时序不保证native checkpoint和replay同绝对支持**；以实际输入/扫描/重放支持核共同人口，一旦仍不同则报断点，不无限对照重跑。更不能让sham/地图数替代物理一致修复及E2，或主动等待用户重复授权既有主线。

后继自检逐项**PASS/FAIL/BLOCKED/NOT_APPLICABLE+实际命令和原件**：版本/source/input/config/binary，完整scan/点布局/修复符号/产物人口，新测量对应候选与独立评价，baseline/queued/applied/未修复，native同stamp完整状态/map/失败公开一致，接回/E2/尾段/成本/缺测。truth/clean proxy仅离线评价，失败保留，未执行明确NOT_EXECUTED，未知UNKNOWN。只要没有新证据不另做参数/防御/字段循环。

A1/A2/A6/A12局部传输、执行及复現推进，A5候选时间人口冻结局部接受；A7新测量候选一致、A8/B2成功来源、A9/A10及B4/B11有效整链仍未闭合。**不产生新全表总分**，四宿主历史结论不变。

## 6. 发布

仅本轮审阅脚本/结果及历史/协作增量，独立review正常SSH提交推送，不合main、不改算法/冻结门/旧记录、不公开私人handoff。开发实际接收与后继执行仍待真实回执。
