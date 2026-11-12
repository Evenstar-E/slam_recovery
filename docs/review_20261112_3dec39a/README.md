# 3dec39a增量审阅：原生重放已执行，实际修复与第二事件未执行

- 读者：用户、开发主会话S1、宿主执行S2、门研究S3及独立复核者。
- 取证：2026-11-12 10:44–10:53 UTC+8；10:49:05现有SSH fetch成功，main `3dec39a7f8f8b6d21281d56645a7fc10237460aa`。完整比较基线bbe916f；新archive合入bf965bf、说明提交3dec39a。
- 本地review分支HEAD `4429392e4342eab0c66fa571fa58c2132ae6ec4b`，没有merge/checkout目标。私人handoff保护；3既有自动任务单owner，无旧repair-3e可见活owner。AGENTS/A-B/REVIEW第十部分已核，用户直接指令优先、忽略stop.md。

## 1. 主线变化：从开发报告升为原件可核的组件进展

相对[bbe核验](../review_20261112_bbe916f/README.md)，两次接纳run原件现在公开，旧“目录不存在”缺口解除。实际源码没有新的串行化后依赖/状态修正，不重跑旧本机反例。

**可以确认**：同一实际FAST-LIVO2宿主中，串行化后hold→reprocess→set_state→resume的OK ack均有记录；host.log确实记录一次原生重放及内部地图增长；resume由rearm触发，后续输入继续。该局部成功不能抹去。

**仍不能确认完成用户主线**：两个run都是host_poses、detection off、只声明一个trigger；修复输入接收/应用为0。第二事件没有动作；原始扫描重放＋set_state不等“实际测量修复→原生重估/内部地图→接回→第二事件”。不发整链首次完成声明。

## 2. 实际核验及失败保留

命令：`python -I -B docs/review_20261112_3dec39a/check_archive.py`，exit0。只读取目标Git blob并核SHA/抽取JSON和少量日志行；不运行归档脚本、不提取执行代码、不代跑host/bag、不新测试/调参。源代码与记录在[check_archive.py](check_archive.py)、[结果摘要](archive_checks.json)。

首次inline读取exit1：SHA256SUMS路径带`./`，git对象路径未正规化，Git拒绝；审阅reader用PurePosixPath修正后25/25均通过，没有修改原件。此错误不算宿主运行失败。

| 项目 | 串行化前020634Z | 串行化后022158Z |
|---|---|---|
| archive SHA256 | 25/25一致 | 25/25一致 |
| driver源SHA | fb746ddd… | 18d92a03…，与bbe实际源码一致 |
| trigger原stamp | 1627785276215170145 | 同stamp |
| 实际run内部kf | 132 | **140**，不是INDEX写的132 |
| episode/decision/accepted | 1/1/1 | 1/1/1 |
| candidate committed/deferred | 32/53 | 31/81 |
| wait关闭时unresolved | 71 | 100 |
| reprocess/resume驱动记录 | 0/0，events停hold | 1/1，状态动作均OK |
| 实际修复apply | 0 | 0 |
| E2 | 未处理 | 未处理 |
| 终态 | HEALTHY；收尾double free原日志30808行 | HEALTHY；选定日志无double free |

candidate.deferred与后续closure.unresolved是不同时间人口，不混成一个数。两次同stamp仍可不同kf编号，沿run自身scan/stamp归属；绝对stamp支持声明同一触发时间，不保证跨run连续编号相同。两个结果方向相容，不要求逐数值一致；不称“同一候选总体逐位相同”。

串行化后host.log:20885：`reprocess #1: 416 frames replayed over [1627785274.681471348 .. 1627785288.544604540], repairs applied=0 queued=0, map now 19194 voxels/362286 points`。reprocess、set_state、resume累计ack字段和记录顺序对应；reprocess接收1794450177.670575、driver观察OK1794450183.170，约5.499s；resume接收1794450183.672810、观察OK1794450184.170，约0.497s。这是接收→driver观察应用确认的间隔，不是精确宿主apply CPU计时。

归档内部哈希一致不证明独立源码→binary重建、完整输入bag字节或恢复质量。本次不重建宿主。9 snapshot timeout与状态动作成功分开，不叫全命令0失败；软件timeout仍非宿主取消。前run double free保留、未定位，不用后run没出现证明已修。

## 3. 必须先做的保障只复用已证正常断点

- **恢复依赖FAIL仍推进**：bbe目标本机实际driver/client反例仍适用，reprocess失败会flush旧尾set_state、后可resume；本轮无生产修正，不重跑。最低按实际applied成功推进该依赖链，失败/未知停后继，不造RPC。
- **状态/测量来源**：本run ack repair_received/applied=0，候选只通过set_state进入，源码仍写旧episode尾；原生地图来自原始buffer重放。最低用真实修复产物驱动同stamp原生重估，准入/deferred范围如实绑定；直接灌位姿不替代。
- **可信时间与段release**：旧close释放新active以及checkpoint晚于隔离边界未修，沿[70证据](../review_20261112_70f68fb/README.md)。本run rolling cp stamp1627785274681471232，而margin4隔离边界1627785272215170145，cp仍晚约2.466s；OK恢复不等回到完整可信边界。无需无限历史缓存，未支持范围明确拒绝。

3dec39a文档称“用户决定保持现协议/不扩candidate”；这不是本会话收到的直接用户消息，不能据此代授权限或改变本会话验收标准。仅记录开发侧采用的partial支持范围。本轮不要求为触达commit_closed追门/扩大候选，不把这条路径未执行抹成完整PASS。

## 4. 最新用户直接要求：所有宿主第二事件矩阵

2026-11-12用户直接强调：“给我总结所有宿主的第二事件的情况，有执行记录的就汇报，没执行记录的就汇报为什么没执行，我之前提过要求先跑所有宿主的第二事件矩阵。”此前交接收窄为“选一个宿主先验证”不能算这个矩阵交付；这次直接要求优先于旧“不扩多宿主矩阵”范围。原参数暂停与本机不代跑不变，不能借矩阵无限安装/调参。

已核五个命名实验宿主，按执行身份区分：

| 宿主 | 实际已有第二/多事件记录 | 当前新修复E2 | 未执行原因的可核范围 |
|---|---|---|---|
| FAST-LIVO2 | 旧115717Z双受控拒绝有原件，两restore/resume及尾段；今天两新run仅单事件 | 未完成 | 自动链曾提前报警/E2检测不可用；今天任务只声明一触发且关检测，收成接纳/通道验证，不是新E2尝试 |
| MM-LINS/SC-PGO | Campus-12两sleep115.99/230.09s，REAL_HOST 644PGO关键帧、349.48m、首尾闭合0.1758m | 未找到执行记录 | 开发选择LIVO因新checkpoint/restore/replay未接；这是范围/接线选择，不证明宿主原生多事件不可能 |
| ORB-SLAM3 | room_dark_01原rawlog多次Relocalized/Map0–4/merge/Shutdown；181lost、74未合并尾保留 | 未找到统一新事务E2记录 | 宿主专属原因UNKNOWN，未找到具体E2任务/失败命令/技术阻断 |
| FAST-LIO2 | MM-LINS执行中的FAST-LIO前端双事件输入输出可引用，不独立宿主恢复验证；其他主要单窗 | 独立E1恢复→E2未找到 | 旧选择表无独立工作区、不单列；不等技术上不可跑，须交复用现前端执行身份/结果 |
| LIO-SAM | clean/污染/过滤重跑有记录；主要单窗，部分B6为OFFLINE_CONSTRUCT | 未找到两事件恢复记录 | UNKNOWN，没有已交具体技术阻断或排除理由 |

证据：Campus12双sleep `experiments/manifests/e2_real_world_mmlins_campus_r1_r2_r3_benchmark.json:36–59`（该manifest整体OFFLINE_CONSTRUCT，不能拿其中B6当原生修复）；独立REAL_HOST P7 `p7_campus_and_overhead_benchmark.json:7191–7205`；Campus runner读取已发布/aft_pgo_path做离线选择，不执行host恢复；ORB `e3_orbslam3/room_dark_01/logs/raw_run.log`及REAL_HOST manifest；FAST-LIO2/LIO-SAM旧clean manifests、street08单[50,70]窗。README的E2=Experiment2，不是第二故障事件；compound同时三故障不等先后两事件；FAST-LIO2/frontend和MM/backend不计成两次独立执行。

**下一单一主线交付改为：五宿主第二事件执行矩阵**。S1按用户要求认领并分配现有宿主，S2复用已有run/runner/环境填各项实际E1动作→真实输入接回→E2→尾段，历史原生机制与slam_recovery实际修复分列。已有记录先归档，不要求每宿主先造完整通用checkpoint；未执行项必须给实际命令/环境/首个具体文件函数BLOCKED，或明确NOT_STARTED及真实未执行理由，不能凭无记录猜不能运行。每次执行沿既有授权实际预算，新增安装/适配/超预算具体报出，不自行扩大无限矩阵。FAST-LIVO2正常依赖最低修仍必要，但不作为其他宿主一律延期理由。S3维持门旁支/参数停，不等其收口。

自检每项PASS/FAIL/BLOCKED/NOT_APPLICABLE＋实际命令、source/input/run、原件路径：E1/E2事件定义与时间、恢复/拒绝/缺帧、修复真实输入/原生地图、接回/尾段/成本、oracle/proxy、负结果与未执行原因；没有运行的项用NOT_STARTED/UNCONFIRMED说明，不能借NOT_APPLICABLE藏未交付。

## 5. A/B变化与发布

A2/A6/A10原生成功动作从DEVELOPER_REPORTED升为ARCHIVE_VERIFIED限定范围；A8/B2旧正常反例不关闭，B4实际修复净收益、B11完整在线E2未闭合。全宿主矩阵覆盖A9/A10/B10适用范围，但目前未完成，不全表重评分、不报告新恢复率。

实际分工/当前远端执行及本地意见接收UNCONFIRMED，由S1下一实际交付确认，不向无关peer代派。本轮实质原件/主线要求变化白名单本地提交，追加历史/协作，不改旧记录、算法或冻结门，不合main/删资产；私人handoff不提交/公开/提供Codex。此前push权限拒绝未解除，未重试、不换工具/peer/Artifact外发绕过，不能称开发已收到。
