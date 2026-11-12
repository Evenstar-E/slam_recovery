# 1f7a6dc增量审阅：实际块消费者与旧索引关闭，同行数值成立但测量资格须分层

面向：开发S1/S2/S3与独立复核者。固定2026-11-13 01:31:59 UTC+8 fetch的main `1f7a6dc35e720b807502acdc258b2f0891c53f47`，比较已验 `23e019bf7f9ac4bab71db9e50a009db704ffb952`；新增growth报告 `ab2fd2a01e0b6e833b6d8edae38b283989a8096b`。跳过Auto-Review、纯合入与已验原生结果。先读AGENTS、MAINLINE_PROGRESS_STANDARD双表、REVIEW§10和历史最新项；固定main规则未新增变化，四宿主限制性交接继续。四Cron仍repair-f3持有，未见旧repair-3e live owner，其他本机会话waiting/idle，不重建任务/双写；忽略stop.md，直接用户暂停优先。

**本轮结论：研究取证/数值部分推进，原生实际测量修复→状态地图重处理→输入接回主线没有新的可独立验收结果。** 两项旧正常路径缺陷关闭，不继续开旧单；单位权真实同行Log与来源成立，但“source scan PASS”“462条合格I”“无E2尾段”的范围不能一起升级。独立FAST-LIO2新失败仅开发记录，执行原件未发布；负载与授权不据转述替用户决定。

## 1. 已关闭项与保存结果核验

[有限自写reader](run_checks.py)、[首个完成结果](local_checks.json)、[增加分窗/事件时轴的结果](extended_checks.json)。只AST执行已读函数/位姿查找语句及fixed Git数据，不运行归档CLI、selftest临时文件、ROS、bag、构建、安装、调参或生产算法。NumPy用已存在明确site-packages；数值比较rel/abs各1e-10，725行另用相对变换及解V·rho=t复核Log（1e-8）。先两次严格浮点字典相等失败、第三次数值已核但np.int64 JSON序列化失败，均为本机reader问题；保留此过程，不归因开发。改有限容差/显式int后完成exit0，随后同资料补分窗exit0，无目标缺陷隐瞒。

```text
C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_1f7a6dc/run_checks.py <新JSON输出路径>
```

| 项 | 状态/证据 | 接受范围 |
|---|---|---|
| 两实际块消费者 | PASS_LOCAL_EXISTING_ARCHIVE | t2_run与t2_join_upgrade均直接读原792×107，0 malformed，全部14个pose/pre_pose标量逐值一致；不再称pose7块header未接通 |
| 旧排序索引 | PASS，旧反例关闭 | 当前沿pose_rows[j][1]读原行；531人口/504诊断、92分数变化，中位72.2938760853与保存结果一致，全部非i字段不变；仍旧heuristic、非合格检测成绩 |
| 真同行Log | PASS_SOURCE/LOCAL局部 | 725 has_out同行pre/post；全部用独立V求解复核，摆脱vec最终增量假设。旧Jinv数学不重开，新路径/source资格不是新native run |
| 保存v11结果 | PASS数值/人口一致 | 482条、481映射、1无trace、246多对一；选取462条数值，19 HAS_OUT_0、1 NO_TRACE_ROW保留；106块与482行全UNKNOWN |
| 单位权分位 | PASS，诊断限定 | norm p50 0.03424097551/max0.59070600863，energy p50 0.001172599568/max0.348933588629；s p50 57.6816118仅诊断，混合状态cov不是Log差值Sigma |

trace SHA b14d4f57e4c488f64365e5fa48c72c32d946ef51d00371a4f21456ac87ccd736；解压availability/receipt/summary四SHA均与保存meta绑定，脚本结果列source/input/output SHA。不能称完整T2 CLI、全测试或远端实体binary/bag重算。原run来源与两次晚cp/零修复负结果复用上轮，不重跑。

## 2. 真实量可用不等测量资格全部PASS

当前T2_V11_RESULTS的一页表/§5把source scan身份写PASS，依据是raw header跨度+512ns包含。**包含计算已复核，但不是完整source→update成员证明**：现宿主cur先接上次next carryover，n_scans只计新pop raw；相同scan header出现两个更新组是实际资料。725同行pre/post可作为该update的真实修正量，不能同时宣462个availability帧已唯一绑定完整测量集合。最低S3/S1将资格分成“raw-header containment数值成立/同update pre-post成立/完整点成员ASSERTED_NOT_VERIFIED”，保原462/多对一与缺项，不新发FAST-LIVO2导出任务。

本轮原件正常反例：所选462数值中**18条eff=0，Log全0**（idx见extended_checks）；全725 has_out中37 eff0。函数完成不证明有点面测量约束，零修正不证明IMU与LiDAR物理一致。当前i_evidence只看has_out及vec/P finite就present，s_i仍由不可用P计算作诊断。**最低只在已有shadow/资格层给18条无有效约束的状态与原因，不能作为NORMAL的I支持；保原482/462报表与这些行，不能悄悄减分母。** 其余444条也不能自动升级全合格：完整成员、独立正常校准/事件标签仍缺。无需改生产检测器或增泛化fallback/矩阵；目前全UNKNOWN的输出不被本轮推成错误NORMAL，但将来健康组合使用前须把这一证据缺项表示清楚。

旧vec/post/cov限制继续；v11同行公式对应Log(inv(pre)post)，meta内沿旧vec/M2DGR的formula/sign/mode文案集中整理即可，不因此否认已核数字、重跑宿主或再开完整schema工程。单位权rot与translation组合不是有概率解释的健康风险分。

## 3. 事件/尾段须绑定本run，不能沿旧54s口径冒称没有实际E2后输出

t2_run仍固定 `E2_REL_S=54.0`，v11正文称“无尾段（run未到E2之后）”。本run实有第二自动episode；其触发时刻相对首trace为17.002940433s、确认deadline21.002940433s，而原件输出支持到约52.8s。**0条tail只证明未进入沿用旧run的54s标签范围，不证明未到本run第二episode之后。** 同时episode不是第二独立真实故障，输出也不是合法恢复后的catch-up。

最低S3/S1：既有资料分别报“旧预声明54s窗口未覆盖”和“本run第二episode触发/决定后输出”，真实独立二故障标注仍UNKNOWN；需比较多事件尾段时用已声明run-specific事件时间及完整人口，不用改E2_REL_S常数偷换旧结果/科学门。0 accepted、两晚cp、零repair/replay及未决2不变；不把后继有输出称恢复成功或历史重放。

## 4. 新growth文字：可复算分窗与不可核峰/因果分开

ab2fd2a只新增38行REPORT，未新增原生执行、地图采样序列或原增长脚本。独立只读核查加主会话有限时间/分窗控制确认：统一origin1627785261079016192，两段如下。

| episode | 回溯quarantine_start | 实际trigger | deadline（传感器rel秒） |
|---|---:|---:|---:|
| 0 | 0.428905408 | 4.595475213 | 8.595475213 |
| 1 | 12.702741067 | 17.002940433 | 21.002940433 |

REPORT把0.43/12.7写“隔离开启”，把12.7→16.7写第二确认窗，与原件trigger/deadline不符；COLLAB§161沿同解释。最低S2沿原run区分回溯边界、触发/命令时刻、确认deadline，不需要新run。

报告的5秒窗eff中位可从全部trace数值复算（25–30s=2；30–35s=25），但各窗有has_out0：30–35s75条中有效后验56，其eff中位39.5；20–25s76条中56后验，中位3570.5而非全行2451.5。全部早退/Ppost0不是测量残差0的健康后验。最低保全人口并分层，不让混合中位作唯一退化机制；本次结果明确两种分母。

42.9k/263k峰、最终593925/4.15M及40.5s精确峰无新地图序列/计算脚本/采样窗/时钟映射，仍DEVELOPER_REPORTED；上轮稀疏ACK有限净增事实不重开。晚段低约束/条件残差上升和增长可以并列观察，不能从不同步排除隔离越界写或证明匹配退化唯一根因。**最低只补已保存原序列/原计算入口（若有），没有则UNKNOWN；不得为此恢复FAST-LIVO2/ASan/K矩阵。**

## 5. FAST-LIO2执行失败、负载与权限：原件/实际授权未闭合

独立只读核验已完成；范围只新增COLLAB§161–166与growth文字，未重复完整原run审计。固定main目录无所称fastlio2_independent_20261113/run1及process_identity/play/node/bag原件；本机也不可读远端环境。以下仅为**DEVELOPER_REPORTED**，不是本机复现：

- run1 PID692359，900s timeout，play376/469.4s、无Done、reindex后0消息；323次IMU初始化/4次重建是旁证，不能验独立原生双故障、恢复、尾段或代码根因。最低S2上传已存source/build/binary/config/input/identity/日志/退出与两个bag身份，缺原件直写UNAVAILABLE，不为了记录重跑。
- §164 load359.52归给mmlins；§165单进程88%“与load359相符”；§166改为host全局值、容器合计2.8核。CPU%、全局runnable/D load、cgroup可用配额不等量。host全局load不是容器专属，但不能断言对可用能力无判别力，亦不能由现数字确定共享核/I/O是播放慢根因。最低S1声明旧归因已被收窄、root UNKNOWN；复用已有同步cpu.stat/cpu.max/节流差、vmstat/play进度原件，不新设参数/重试矩阵。
- 停止FAST-LIVO2、清5个roscore、16PID environ归属、两peer回复及分类器拒绝，目前只有开发转述。PPID/PWD/environ是历史来源线索，不自动证明现无消费者/可杀。**不绕过拒绝、不让peer代杀、不把S1批准/S2归属当用户杀进程授权。** 原权限制约仅交用户，未阻工作继续。
- §166“load>200硬门改warning、加cpu.stat判据”只有通知：具体版本/判据/实际S2接收、run2在途或未开跑未交，不称已部署或BLOCKED已解除。S1保用户实际授权来源/范围与拒绝回执，S2交实际状态；旧负载归因变更后不要将终止节点机械设为所有主线前置。

这份中文GitHub审阅记录重大阻断与证据限制，但**不是批准安装、终止进程、重试、扩算力/宿主矩阵**。本会话不请求peer绕权限，也不自行认证仓库“用户原话”为新直接裁决。按限制性交接不发新FAST-LIVO2工作。

## 6. 主线/旁支与下一单一交付

| 分类 | 执行责任与最低验收 |
|---|---|
| 主线 | S1唯一共享集成；当前开发称转MM-LINS接口只读分析。下一交付锁该既有host具体文件/函数/输入状态map接口首断点及最小接入，或交实际测量修复→native状态/地图重处理→接回真实输入/E2；不能只再写全表/观察基线 |
| 必须先做 | 所选宿主实际输入→完整点记录→原生重处理接入与状态时间/map一致；若MM-LINS可独立于FAST-LIO2环境推进，不等进程处置。具体owner/HEAD/调用点回执尚未交，不凭缺交付猜算法根因 |
| 可并行 | S2既有FAST-LIO2失败原件与真实权限/状态；S3现数据18 eff0、成员资格和run-specific事件分层；正常校准/独立标签按既有任务，不能重复抽象选项问授权 |
| 集中延期 | FAST-LIVO2新执行/构建/适配/ASan/增长因果；一般文案/重复§163/旧meta集中整理，旧sigma/κ/floor停、门不降 |

公共已验reader/Log/修复与通道组件版本化复用。四宿主分别验收，不以共享改版前端冒独立FAST-LIO2，不由一个通过豁免其余或提前放行FAST-LIVO2。开发交付逐项**PASS/FAIL/BLOCKED/NOT_APPLICABLE＋真实命令/原件＋主线影响/下一动作**；另保NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE/UNKNOWN、正常/失败/缺项完整人口、资源作用域。S1分工、S2新接口实认领、S3修后shadow接收均须实际回执，不能只记“已通知”。

A1/A11 source取证与A3/B3数学研究局部推进、A2/A12失败资料待核；A4/A5/A6/A9/A10/B2/B4/B11没有新整链/净收益证明，B6环境/增长根因未知，不报新全表总分。15h08:53仍如实结果报告，未获用户延期/目标改门；自动化只当前会话存活有效。只提交本轮reader/结果/中文review与历史索引，现独立分支SSH发布，不main merge/改算法历史门/私人handoff/开发日报/凭据。
