# slam_recovery 协作状态

**2026-11-10增补入口：**所有角色先读[项目历史与当前唯一主线](PROJECT_HISTORY.md)；算法设计、阈值与单测同样避免无证据防御扩展，历史局部验收先复用。最新开发基线与实际同步状态见§7。以下§1–6保留原快照，不将旧HEAD或“正在编写”当作当前在线状态。

更新：2026-11-10 10:37–10:40 UTC+8。供开发主会话、两个执行会话、本机审阅会话，以及另一台电脑上的 Codex 使用。

**这是证据快照，不是在线会话/进程看板。** 四个既有会话按用户说明解释为“开发主会话＋两个执行会话＋审阅会话”；Codex 是新增独立复现/集成验证角色。远端工作树、会话当前分支和未提交内容未取得直接回报时明确记 `UNCONFIRMED`，不能从已合入main的提交反推当前正在做什么。

## 1. 共同版本与协作原则

| 项 | 固定值／状态 |
|---|---|
| 仓库 | `Evenstar-E/slam_recovery`；使用已有安全认证，不在文档、命令或提交保存凭据 |
| 当前开发基线 | `origin/main@39eac2f337eaf2b9df28aa0e9b015b36d0ecf34d`，本机已fetch |
| 审阅发布分支 | `review/repair-f3-handoff-20261110`；本文件提交到此分支，不自动合main |
| 此次提交前本地HEAD | `dff09750d8f571e101ceb751393a559a1a14d55c`，含39eac2f合入审阅分支的merge；尚未推送的该merge会随本文件一起推送 |
| 此次提交前远端审阅HEAD | `bc66685e2b8036f07aad77579abf1b7e8173c9ee` |
| 旧完整评分 | `773b995`：A16/36、B12/36、24项完整闭合0；不是39eac2f最新评分，不自动继承/升档 |
| 必读 | `AGENTS.md`、`docs/MAINLINE_PROGRESS_STANDARD_20261109.md`、`REVIEW_AND_SIMULATION_PLAN.md` §10.10–10.13 |

一个完整主线交付验收后晋级；必要旁支可并行。开发主会话分发、调整依赖并集成，共享manager代码须有明确单一写入责任。只优先修影响正常实验输入、帧归宿、状态撤销或实际评价的最小问题，不追求生产级防御框架。远端开发负责算法与真实宿主；审阅侧不自动修改算法，不改历史，不覆盖未提交工作，不降低冻结科学阈值。

## 2. 四个既有会话职责、版本和当前状态

### S1 开发主会话：分发、集成、主线里程碑

- **会话名称：** `UNCONFIRMED`；用户确认存在一个开发主会话，但当前名称未记录。
- **职责：**向S2/S3分发主线/旁支，指定事务manager修改责任，集成提交、冻结输入/验收范围并回报实际执行分工。
- **已发布位置：**开发交付合入 `main`，当前已核发布基线39eac2f。不能由此认定远端当前checkout也是main。
- **当前checkout分支/HEAD、远端工作目录、未提交工作：** `UNCONFIRMED`，须由该会话直接填报。
- **最近发布文件：** `docs/DAILY_20261109.md`、`docs/review_20261109_bbc3dcb/fl_run_isolated.sh`、trace结果/收据、`fastlivo_patch/*.v2.diff`。runner原件已同步，当前Git blob SHA与默认运行receipt的script SHA一致。
- **正在修改的文件：** `UNCONFIRMED`；上列是最近提交范围，不是正在编辑清单。
- **下一交付：**明确A5/A9正常路径修复负责人；给限定native检测/检查点/修复/接回接口计划；勿把三个会话全用于trace排障。
- **验收：**每个包先自检PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令/证据、主线推进、旁支分工和未验项；不以测试数量或“已派任务”代替实际完成。

### S2 `r11070-c3`：FAST-LIVO2宿主运行与消费trace

- **责任证据：** `docs/DAILY_20261109.md` §19及历史执行交接明确指定该会话；最近原生ON/OFF/default运行归档已提交。
- **最后可核的交付分支：** `exp/m0-updated`，交付commit `42c6c6d69a8c936acd57865a3c72893f38ed6f5c`（见trace_v2_delivery_review.json）。该分支当前不在本机origin远端引用中，该commit本机不可解析，**不是当前checkout确认**。
- **当前checkout/HEAD及未提交工作：** `UNCONFIRMED`。已合入main的可复现材料以39eac2f为准。
- **宿主基线：** FAST-LIVO2 `0d2c0346107b75b59934975adec9a6eeeb913c64` **加T3a补丁**；不是干净0d2c034。补丁base备份曾在 `/tmp/fastlivo_bin_backup/*.pre_trace`，当前可获取性待执行侧确认。
- **最近改动文件：**宿主 `CMakeLists.txt`、`src/LIVMapper.cpp`、`src/IMU_Processing.cpp`；仓库对应 `docs/review_20261109_bbc3dcb/fastlivo_patch/*.v2.diff`、runner、CSV、receipt。header diff为空是有意无改动，不视作缺交付。
- **正在修改文件/运行中进程：** `UNCONFIRMED`，不宣称现在仍在运行。
- **验收已知：**两ON CSV原件/receipt本机核hash，各1766 GROUP/STATE、599 ARRIVE、5 IMUINIT，GROUP摘要相同且位置分叉；OFF两receipt对应成功运行但原output bag未本机复算。默认构建CSV/receipt已交，见§4当前检查。
- **结果入口：** `docs/review_20261109_bbc3dcb/on1.csv`、`on2.csv`、`trace_default_emit_fixed.csv`、`trace_*_receipt.json`、`trace_on_pair_results.json`、`trace_off_pair_verified.json`、`trace_default_build_results.json`。
- **远端数据：**receipt中原input/output为 `/tmp/fastlivo/room02_2x2_O.bag`、`res_on1.bag`、`res_on2.bag`、`res_off1.bag`、`res_off2.bag`、`res_default3.bag`；宿主源码 `/home/R26534/FAST-LIVO2`、build `/home/R26534/fast_livo2_ws`。路径是归档记载，非本次在线存在性保证。新增完整数据/临时实验优先持久数据盘；旧档案只读，不删除。

### S3 `r26534-58`：A7坐标/切空间数学与准入实现

- **责任证据：** `docs/DAILY_20261109.md` §20明确派A7给该会话。
- **文档声明基线：** `exp/trace@a01169d`（`docs/review_20261110_a7/A7_TANGENT_FRAME.md:3`）；该ref/短SHA本机不可解析，**远端当前checkout/HEAD未确认**。
- **已发布交付：** `aa42031280f6c403549becc7c64d079c609208a0`、`b571b9f9ba1c80b3ed8ee27f67bb5ac490239b18`、`56ae4e4b2ad999bb15a06f5896957db383c800ef`，已进入4255cbe及当前main。
- **最近改动文件：** `slam_recovery/core.py`、`quarantine/manager.py`、`sim/transaction_manager_node.py`、`__init__.py`及契约调用点/tests；`docs/review_20261110_a7/A7_TANGENT_FRAME.md`、`negctl_a7.py`。
- **正在修改文件、未提交工作：** `UNCONFIRMED`。不能把已提交列表称为当前编辑中。
- **已有结果：**显式frame/order/anchor、混系拒绝与伴随公式局部通过，目标核心60/60测试PASS；普通世界平移仍造成两类mode翻转，A7整体未验收。
- **最小验收：**固定评价切空间/原点/尺度，information、weak direction和covariance联合transport；真实默认FIM旋转弱方向＋非零平移、正确cov搬运两反例通过且mode/指标不因gauge变化。不得只改frame字符串、删一处单位化或调阈值。
- **证据：** `docs/review_20261110_4255cbe/a7_review.md`、`a7_gauge_probes.py`；E3多扫描共同基问题延期到实际消费该证据，不阻断当前trace。

### S4 `repair-f3`：本机独立审阅、复算与交接

- **实际工作分支：** `review/repair-f3-handoff-20261110`；本地/远端HEAD见§1，源码开发基线39eac2f。目录 `D:/REPAIR/slam_recovery_upstream`。
- **职责：**增量源码审阅、归档原件复算、正常路径反例、自检/分工意见与日报；不代替远端开发修改算法或运行宿主。
- **已发布结果：** `docs/review_20261110_2d36c6a/`、`review_20261110_4103507/`、`review_20261110_fc062fe/`、`review_20261110_42d2d88/`、`review_20261110_4255cbe/`；协作/审阅尺度协议在此review分支的REVIEW§10.11中。main未自动合入这些审阅提交。
- **当前正在编写：** `docs/COLLABORATION_STATUS.md`；39eac2f默认trace审阅尚在核身份口径，会随证据追加报告。
- **未提交工作（已实际git status核实）：**原未跟踪 `docs/review_20261110_2d36c6a/handoff.md`，仅私人会话压缩笔记，**不提交、不提供给Codex、不读取用于公开协作表**；本文件创建前无tracked工作树修改、无staged文件。此快照以本文件提交前为准。
- **自动化：**5分钟审阅与每日汇报在本会话中启用，session结束即失效、7天过期；旧repair-3e已关闭、不再承担工作。不把私人历史或凭据推到Git。
- **验收：**实际加载源码绑定版本；区分原生运行、归档重算、合成fixture。审阅独立分支可被开发侧读取，不自动批准算法合main。

## 3. 已有负责人 vs 可交Codex的任务

| 任务 | 目前责任证据 | Codex安排 |
|---|---|---|
| 宿主/trace/runner实现与原生采集 | S2已有交付，S1集成；当前是否继续运行未确认 | 不重复改writer/runner，不重新调同一实验；独立检查已归档原件即可 |
| A7算法最小数学修复 | S3已明确派任；最新修复是否在编辑未确认 | 独立重现两gauge反例、验证后续fix，不默认抢写core/node |
| A5/A9剩余正常路径修复 | **没有明确执行负责人/新修复交付确认**；0a196b4/bd75d6e仅旧局部fix | Codex可先复现反例、做集成验证；算法修复要S1先认领/分发并确认是否给Codex，不自行判为无人后覆盖 |
| A8人为异常注入完备 | 已降工程旁支，不是当前主线先决 | 暂不扩极端异常测试框架 |
| 审阅/评分/日报 | S4 | Codex给独立证据，不覆盖旧评分与本机review文档 |
| 干净环境独立复现与集成验证 | **用户本次明确交给新增Codex角色** | 可立即从固定39eac2f及审阅分支克隆，先只读复算/测试，报告独立结果 |

### Codex建议分支与入口（尚未创建，不冒充实际状态）

- 建议分支：`codex/independent-reproduction-20261110`，从固定 `39eac2f337eaf2b9df28aa0e9b015b36d0ecf34d` 创建；另fetch `review/repair-f3-handoff-20261110`获取反例/验收意见，**先复现目标，不盲目合入所有review历史**。
- 建议文档目录：`docs/independent_reproduction_20261110_codex/`，由Codex创建，绑定其实际source/environment/data SHA。
- 先记录实际branch/HEAD、工作区status和环境。检查`import slam_recovery`路径，避免本地同名旧包；Windows本机numpy在用户site，python -I可能看不到，勿把环境导入错误当算法回归。
- 可直接执行：
  - 从目标源码根运行 `python -B -m unittest discover -s slam_recovery/tests`，记录加载路径和测试结果；60tests为4255cbe历史期望，不是所有未来版本固定数。
  - 独立复现本review分支 `docs/review_20261110_4255cbe/a7_gauge_probes.py` 与A5/A9正常人口/时间反例。旧脚本fixture在A7契约加入后可能需要明确frame调用适配，记录适配，不修改算法制造通过；新版复现报告中说明版本差异。
  - `python -I -B docs/review_20261110_4255cbe/verify_trace_pair.py`：该脚本从固定4255cbe git blobs重算ON对，不依赖最新tree数据。核原CSV/receipt的hash及相同支持，禁止只转述JSON。
  - 默认trace重配对与空组按事件类型分析，可从现CSV独立做，不需新宿主/大数据。
- 核CSV/runner收据hash时读取固定commit的 `git show <SHA>:<path>` 原blob或保持LF：本机Windows checkout默认CSV变CRLF，checkout SHA会不同，但Git blob SHA与receipt一致；不能把换行转换误判为实验数据错配。先记原blob与环境转换，不擅自重写数据。
- 若缺原input/output bag、native环境或base patch，报告BLOCKED/UNAVAILABLE，不伪造独立运行；请S1/S2提供持久、可访问只读输入位置及hash。首次工作包不自动授权安装、删除旧数据、无限重跑或修改宿主源码。
- 集成验证先在Codex分支核适配API、partial retry/两事件正常路径和A7gauge；不得为了测试过关修改阈值、删失败样本、覆盖历史结论。算法整合由S1批准范围和写入责任。

## 4. 当前可用结果与未验收项

- **ON对：**两份原CSV和receipt本机独立复算一致，1766记录GROUP/IMUINIT摘要相同；位置87号事件首次>1mm，max单坐标309.706199m。不是GT/ATE，不定位完整根因。
- **OFF对：**两receipt成功，归档output SHA关联；远端统计OFF-OFF欧氏互差max729m。本机没有原output bag，不称独立复算；只支持OFF也出现分歧，不排除trace贡献。
- **默认构建：**原CSV hash及runner Git blob hash与receipt一致；599 ARRIVE/1766 GROUP/5 IMUINIT/1766 STATE，884空IMU组；GROUP完整记录与ON#1相同。
- **默认构建新待验问题（本机当前复算）：**默认CSV GROUP→STATE相同行号的lid_stamp有878处不同，DEFAULT与ON#1的STATE时间也有878处不同；现有跨构建index-only比较不能直接称同帧首差/最大误差。应按实际package事件身份/前后更新时间定义重配对。884空组中883为img=1，非空882也为img=1，须按实际LIO/VIO子事件解释，不能把~50%总计自动当作坏同步。此问题限默认跨构建比较，ON-ON时间一致的已有验收不撤回。
- **3ca0556计数补验：**DEFAULT/on1/on2均有882完整“空→非空”图像事件、1首部img_stamp=-1初始化行、1尾部仅空行事件；不同图像身份883，不是完整配对883。按图像事件/阶段配对，不能将1766行一律折半后称完整帧；odom800也另列。见 `docs/review_20261110_3ca0556/README.md`。只补口径，不要求新宿主运行。
- 当前本机检查首次把默认STATE与ON逐行同时间assert时失败；这是实际身份口径未满足，不是默认宿主运行失败。没有为此重跑宿主或增加防御性检查。
- **A7：**60单测PASS但两个普通gauge反例仍翻转，见a7_review；完整准入未通过。
- **A5/A9：**仍缺报警当帧登记、撤repair后原始人口归宿、等待来帧真实时间的正常路径闭合；未看到其剩余fix交付。不能引用日报“三组已闭合”为验收事实。
- 完整原生在线检查点→修复→提交→持续输入→第二事件、同候选四策略净收益、冻结后新环境、独立发布均未完成。hall条件正/room负结果保留，proxy非GT，不把缺帧隐藏。

## 5. 暂停／延期／不得自动开始

| 状态 | 事项与恢复条件 |
|---|---|
| 已停止旧会话 | repair-3e不再负责审阅，由S4接续；不是暂停整个研究 |
| 不再扩的旁支 | 无假设trace/分组/单NIS排除法、永久runner字段/极端防御完善；新真实阻断须具体证据 |
| 延期 | E3共同基重构、aux未声明系路线、扩宿主/扩故障/大模型；到实际消费这些证据时再计划 |
| 未验收前不可宣称 | A7修复前的完整准入安全、A5/A9工作包闭合、原生同进程恢复已完成 |
| 支持先做 | Codex独立归档复算/正常集成验证、S2已限定数据观察、S3 A7最小修复，均不要求所有旁支完备 |
| 直接用户暂停优先 | 忽略stop.md，不据其自行停止/恢复；任何用户后续直接暂停立即遵守。没有用户指令暂停整个研究 |

## 6. 每位负责人下次交付必须补齐

请S1统一汇总实际信息后更新本表，不另制造纯“收到要求”周期：

```text
会话ID/角色：
实际工作目录、branch、HEAD、实验/补丁base SHA：
git status --short（包括tracked修改及相关untracked；不含凭据）：
正在修改的文件（与已提交文件分开）：
当前运行/暂停/排队任务及停止预算：
任务责任人/集成责任人、主线与可并行旁支：
PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令、结果/数据/receipt路径：
仍未验收项、下一交付、交给Codex或明确不可重复的范围：
```

截至本快照，S1/S2/S3的远端未提交清单与实际checkout尚未直接获得；Codex尚未给环境/branch或运行结果。**“已分派”“建议分支”“最近发布文件”不能写成“正在执行”“实际checkout”“完整通过”。**

## 7. 2026-11-10主线收敛与全开发侧同步

本增补绑定开发 `f20a5468292997a815f2d75545099c6396bb9733`；其新增仅B10预注册/schema，没有新的原生恢复运行。S4实际分支仍为`review/repair-f3-handoff-20261110`，本轮已merge该开发基线，不改历史；旧§1/§2的HEAD、正在编写及分工信息是旧快照，不自动成为最新状态。

### 全体共同规则与历史复用

用户明确要求同步到各开发侧：避免防御性考虑包括算法设计、阈值和单元测试；历史已完成部分确定后不再造轮子；不能持续以细枝末节提交替代研究主线。规范与版本化成果详见[PROJECT_HISTORY.md](PROJECT_HISTORY.md)，必读入口已写入AGENTS及REVIEW§10.11。已有冻结科学门、独立证据、完整人口和负结果要求不降低；不是删测试或为Mode2放宽阈值。用户同日追加避免反复调参：多次调整后先用已有运行总结参数变化规律、收益/代价平台与可改善上限，再决定停止或更换算法；见PROJECT_HISTORY§2.1。所有角色沿用此决策口径，不机械设调参次数、不新起无假设大矩阵。

**下一个实际交付：**限定的一次原生同进程检测→可信状态恢复→实际重处理/状态重估/地图重建→准入或拒绝→继续输入→第二事件。若不可执行，交具体宿主接口/文件/函数缺口、执行及集成负责人和最小解除，不再单独交日志、预注册或测试数量。A5/A9正常人口与撤销、A7评价基按既有反例最小修，和原生接口准备并行；B10完整比较是后继，不挡先观察链。

### 同步实际状态（不是已阅读保证）

| 角色 | 本轮同步渠道/事实 | 送达或采用状态 |
|---|---|---|
| S1开发主会话 | GitHub共同历史文档、AGENTS/REVIEW及本表；要求下一实际交付分发S2/S3/Codex并回报执行责任 | 直接消息通道未取得，UNCONFIRMED |
| S2 r11070-c3 | 同一仓库入口；已有宿主责任证据保留，优先原生接线而不是追加trace | 当前branch/编辑/接收未直接确认，UNCONFIRMED |
| S3 r26534-58 | 同一仓库入口；沿用A7局部成果，只修已复现固定度量问题 | 当前branch/编辑/接收未直接确认，UNCONFIRMED |
| 新增Codex | 同一仓库入口；独立复用现有反例/复算工具，不抢写现有算法 | 环境/branch/接收/结果仍UNCONFIRMED |
| S4 repair-f3 | 本机实际编写历史、协议和B10局部审阅，不修改算法；本轮仅文档改动 | 已应用；提交发布结果由Git记录 |

本机ListAgents仅有两个其他可寻址会话；已分别发角色核实与收敛要求，两者均明确回复**不是slam_recovery开发角色**。不向它们继续分派本项目任务，也不把这两次送达当成S1/S2/S3已收到。当前`gh`命令不可用，未创建issue/PR；通过既有SSH发布审阅分支，不改认证、不擅自合main。

### 本轮工作区与未提交内容范围

S4修改文档：`AGENTS.md`、`REVIEW_AND_SIMULATION_PLAN.md`、本协作表；新增`docs/PROJECT_HISTORY.md`与`docs/review_20261110_f20a546/README.md`。tracked算法源码未改；原私人`review_20261110_2d36c6a/handoff.md`保持untracked、不公开。S1/S2/S3/Codex远端未提交清单仍未取得，不猜填。

主会话无需另造“已收到”提交：随下一真实实现/运行汇报同步与分工，更新真正变化的历史行。已完成组件、旧反例和延期范围沿用PROJECT_HISTORY，不重新扩审计/阈值/测试循环。

## 8. 最新责任回报与两小时检查（c82aae5，11:00核读）

本节更新§7当时未确认的部分，不覆盖原快照。开发main已合审阅至bd85346，交[docs/S1_STATUS_20261110.md](S1_STATUS_20261110.md)。S1直接报告会话名“MM-LINS改进”，工作目录`/home/R26534/MM-LINS`、main@f5e23ce；当时无tracked修改，untracked为两个FAST-LIO日志锁文件与MM_LINS.pdf。正在修改文件“无”，是其快照声明，不保证本机检查时仍相同。

- **事务manager：S1明确唯一写入/集成责任。**A5/A9正常路径未闭合，下一轮优先旁支之前；原负责人未确认状态解除。
- **宿主：r11070-c3。**阶段一原生闭环待开工，ICP阶段二未开始；不从“已派任务”认定已运行。
- **A7：r26534-58。**主会话报告执行最小修复，尚无新源码/修复效果交付，未验收。
- **Codex：**仍未给实际环境/branch/独立结果，保留只读复现安排，UNCONFIRMED。
- **同步：**早期交接已进入开发main，有实际采用证据；最新算法/阈值/单测收敛与调参上限规则db4f011未进入c82aae5，各会话采用未确认。仍无可寻址远端消息通道。

用户新增每两小时主线总结；本会话任务a249a2ce，下次实际12:37，session-only、7天过期，不替代5分钟增量审阅。首次[09:00–11:00报告](MAINLINE_CHECK_20261110_1100.md)区分工程接线/实施缺口、已复现A5/A9和A7依赖、参数缺少阻塞证据。下一只交限定运行或具体接口解除，不为状态表增加新防御/调参轮次。

## 9. 用户要求立即优先下发一次原生两事件运行

2026-11-10，任务入口：[NATIVE_RECOVERY_RUN_TASK_20261110.md](NATIVE_RECOVERY_RUN_TASK_20261110.md)。沿既有实际责任：S1集成/manager最小A5/A9；r11070-c3负责原生接线及一次限定恢复→接回→E2运行；r26534-58并行A7最小修复；Codex独立核验而非开工前置。S1须向S2/S3分发本任务，下一交付直接给代码/运行或具体接口断点，不另交仅“收到”提交。

用户首先要真实原生恢复，缓存旧宿主pose和Python/sidecar接线仅阶段证据，不作替代。接纳或拒绝照实报告，至少尝试实际重处理/状态重估/内部地图恢复；未具备接口明确BLOCKED并给最小实现。用已有hall链优先，不扩实验矩阵，不自动调参重跑。实际运行前执行侧沿现资源填固定输入窗口和墙钟停止预算。

发布渠道是GitHub审阅分支共同任务入口；本机仍无S1/S2/S3可寻址消息通道，**本次接收/开工未确认**。已确定负责人不等于执行已经开始。配套[KITTI备用集](KITTI_HELDOUT_RESERVE_20261110.md)为旁支：05/07和封存08先待真实未见历史/Raw IMU兼容核验，不阻塞本次原生运行；本轮未下载数据。

## 10. 21fa650及Codex独立包状态更新

开发main固定`21fa6506f8b1c63f95b135f7052b2fb84ea7c9c3`，新A5/A9三旧正常场景本机均通过、核心68/68 PASS；详见[增量核验](review_20261110_21fa650/README.md)。已解除报警帧、回滚人口、旧end漏撤范围，不继续当当前阻塞。A7旧两个gauge门反例和固定基transport已通过；实际node world正则仍造成cov跨默认0.5门翻判，仅保留最小固定基修正，原生接线并行。S1最新仍报B11 NOT STARTED，未交原生恢复运行。

**Codex已有实际独立分支与结果：**`origin/codex/independent-reproduction-20261110@ee6a1964da0df5e42904bc7545c7c4bc0bb4cc01`，入口`docs/independent_reproduction_20261110_codex/README.md`（在该分支，未合到本审阅树）。本机核读报告/结果元信息，未重跑。目标39eac2f，报告环境Windows11/Python3.12.14/NumPy2.3.5，独立worktree；旧A5/A9/A7五个正常不变量FAIL、分批控制PASS、60核心与trace工具5例PASS。该包独立确认旧源问题，不是21fa650新fix的失败/验收；原生环境和实际运行仍未交付。

Codex接续沿自己包做新anchor/cov最小适配与正常集成复验，不再造工具、不抢写算法。S1/S2/S3实际工作树变化仍需各自回报；算法/阈值/单测收敛及最高优先运行任务本次是否已接收/开工尚未确认，不从合早期审阅分支推断已接收最新任务。

## 11. 6631da8：B11接线执行尝试已报告

开发S1新快照将B11从NOT STARTED改为IN PROGRESS，引用r11070-c3的649d504：位姿/扫描接收、配对、一次gate决定及相关参数、进程组和NIS来源五项PASS。此前§10的未开工状态只适用于21fa650，不能套给本版本。**本机仅核读汇总，649d504 commit不可解析，驱动源码与原run_summary/candidates/receipt未取得**；执行侧当前branch/HEAD/未提交清单依旧需直接回报。

首个报告断点为warm-up后0.3s即隔离、比注入早16.7s；sigma诊断绑定1500参考点/1关键帧。归档.55是等效归一化，不作新修复参数，也不据此独断cap为唯一根因。候选结果汇总已提到cand_0000拒绝，不应称零候选记录；但目标故障段完整流、原生恢复/接回/E2仍未交。

[增量意见](review_20261110_6631da8/README.md)：S1集成；S2最小核参考空间支持/更新时间，回到实际恢复与E2；S3不继续sigma说明或调参，处理已给实际A7正则反例；Codex/KITTI/B10旁支不挡开工。现驱动和原小型收据随实际交付提供，不为补字段单独重跑。

## 12. 2a7d447驱动已归档，主线分工收窄到两个实际缺口

此前649d504不可取得的状态由新merge解除，ROS recovery_node/run_native_loop及stage1b原receipt/wiring/candidate已入main。本机核fixed source SHA256与receipt一致、runID相同；归档584/599配对、独立host/recovery PID同PGID、一次拒绝、最终WAITING。

责任仍沿现S1/S2/S3：S1集成，S2接**原生内部恢复/重处理/状态地图写回**及**真实Mode3后续证据/返回终态/重武装处理E2**；现driver仅缓存旧host pose/发布status，未实现这两点。后续消费不是接回成功，禁止仅改来源标签称ICP。S3并行最小A7固定基正则，Codex独立核集成而非开工前置；KITTI备用不占本次主线。

[本轮核验](review_20261110_2a7d447/README.md)记录本机69-entry unittest有pytest缺失ERROR1（原68无断言失败），新adapter pytest未执行；runner语法通过，无ROS重跑。未知工作树/当前运行仍需执行侧直接回报，不能由driver归档推当前进程仍活。

用户新增随机实验按趋势复现：总体方向、效果量级、失败范围相容即可，不逐值/逐次苛求同结论；小样本保留证据不足。不豁免身份/帧归属/接口和坐标不变量，不改冻结门、不挑好运行。规则入口已更新AGENTS、REVIEW§10.11、PROJECT_HISTORY§2；下次实际交付一起应用，不另造“收到”周期。

## 13. 2efe470有限诊断交付，主线接口继续优先

执行侧detection-off run已归档summary/receipt/wiring，393配对/373可信帧、0事件/0决定；source SHA核过。S1报告当前检测配置不可用，有限观察中各地图规模NIS中位均>2、窗前较大箱亦高。接受该负趋势并收口启动K/纯sigma调整；不要求随机重复逐数一致、不把有限结果推广全部配置。

599扫描393配对、206未配、backlog207，当前1×完整性未通过；可能因素未唯一定位，性能缺口不升级成无限优化任务。报告[review_20261110_2efe470](review_20261110_2efe470/README.md)要求S1/S2原生恢复/写回与Mode3继续处理/重武装并行优先，S3最小参考/残差解释及现A7正则，不继续分箱文字循环。执行方若选择有限慢速/固定窗口须如实声明非实时与全部缺失，不降低门、不改人口。

当前任务/工作树在线状态仍需负责人直接回报；图增长HEALTHY不表示场景健康或恢复接回。Codex/KITTI/四策略旁支不阻塞本次实现，两事件原生运行仍未交。

## 14. 2efebc7参数旁支收口，接口实施未变化

新NIS-only离线重放撤回“任何固定sigma都不可用”，同开发轨迹sigma≥约0.62避开窗前NIS告警、约+6s首次报警，0.884/1.2首次时间近平台。报告[review_20261110_2efebc7](review_20261110_2efebc7/README.md)接受有限趋势，不据此称全检测/原生恢复已PASS；生产源码未变。

提出下一运行sigma=.884须作为探索配置明确：启动箱仅2帧、已看同一故障表现，不是独立标定；该node参数还同时改变候选holdout/paired准入尺度。不降低/隐去旧科学门，不继续sigma扫描。真实support/FIM与首次隔离后的反馈未在replay复现，E2不能从该序列得出。

S1/S2原生写回＋Mode3后续处理/重武装仍优先，S3固定基正则并行；参数认识和当前角色正在编辑/运行状态分开，不从离线8个参数结果认定已开新的原生流程。

## 15. 36e9bef描述性占比接受，不再扩统计旁支

新增同诊断run的coverage JSON/脚本/说明，本机核197/196/70计数和35.53%/35.71%比例一致；是配对归档人口的NIS-only离线告警占比，不是完整输入/时间覆盖或在线召回。生产源码未变，没有新增恢复/E2运行。详见[增量意见](review_20261110_36e9bef/README.md)。

S1/S2原生恢复接口与Mode3继续处理/重武装优先；S3最小A7正则并行；统计旁支到此收口，不为更正人口/秒数文字继续调参重跑。现角色正在修改/运行状态仍须直接回报，不从新统计提交推断开工。

## 16. 0bdd1f4实际检测已交，下一回到原生恢复/持续处理

新room detection-on（sigma=.884）原件身份与source SHA核过，首次报警−27ms、隔离+106ms；584配对、1决定/0接纳/E2零、最终WAITING。新ICP模块13个既有函数本机实测通过（非pytest），但driver未调用、真实离线结果未归档；接受部分进展，不称完整原生恢复。详细[0bdd1f4核验](review_20261110_0bdd1f4/README.md)。

S1仍集成/manager唯一写入；S2仍优先宿主checkpoint/测量重处理/内部状态地图写回和真实Mode3续处理/终态/重武装，不仅缓存host poses或改ICP标签。S3最小A7正则并行；本次边界时间基修正由S1确认接口写入责任，不能只修一个jump字段/放大门。候选4.628<tau_info25，且归档匀速模型搬运后位置差下界仍0.903m，不能承诺修边界即Mode2。hall差异时间线不判room漏检，旧off图实际增长不作静态参考归因；这些随交付收窄，不另造调参/文字周期。

Codex沿独立工具核新集成，KITTI/四策略不阻断。当前远端checkout/未提交清单/运行中任务及最新意见接收仍UNCONFIRMED，不能从已交run或早期merge推在线状态。下一单一交付是一次真实恢复→接回→E2或第一具体宿主接口实现/断点，提供PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令与证据；不再单独交收到规则。

## 17. bcadd9f边界旁支局部通过，原生接口主线未增加

开发首段包络改用anchor时间，三个helper控制本机通过；真实node连续运动例仍在core第二raw-distance检查被拒，须统一既有两处时间定义，不重开已修首段、不提高门。详见[bcadd9f核验](review_20261110_bcadd9f/README.md)。本轮无新原生运行/恢复/E2。

S1继续集成/指定边界接口写入责任，S2优先宿主实际恢复重处理写回与Mode3续处理/重武装，S3最小A7/时间评价修正并行；不把这轮helper测试串行挡接口开工。Codex复用工具独立核集成，KITTI/四策略仍后继。当前实际编辑/工作树/运行/意见接收状态需直接回报，不猜已完成或正在执行。

## 18. f9ad688重复边界拒绝已解除，停止这一旁支循环

新增elapsed传入core，真实node原连续运动例evidence现在PASSED，35相关unittest本机通过；[局部核验](review_20261110_f9ad688/README.md)接受限定修正，直接复用，不再重新立边界任务。仍为BOUND_ONLY，fixture cov和真实候选info门仍未过，不称完整Mode2。无新原生运行。

S1集成/S2下一交实际宿主恢复重处理/内部状态地图写回与Mode3续处理/终态/重武装的恢复→接回→E2；S3仅旧A7固定基正则最小修并行。Codex/KITTI后继不挡接口，当前checkout/编辑/运行/本意见接收仍待直接回报；不以提交数或局部PASS推完整主线完成。

## 19. 12:37两小时汇总：责任不变，下一优先真实恢复/E2

[窗口总结](MAINLINE_CHECK_20261110_1237.md)绑定10:37–12:37、开发f9ad688：部分推进（新实际检测接线/ICP组件与必要正常修正），完整原生恢复/接回/E2未交。主因是工程接口/生命周期，次要A7数学；参数有限趋势已收口，不能代替接口，模型不可恢复/极限证据不足。不重跑测试或制造新实验。

沿S1直接确认的集成/manager唯一责任、S2宿主、S3A7，Codex独立工具复用/KITTI后继并行；当前执行开工、工作树与最新任务接收仍须直接回报。原生接口准备不等待全部旁支，下一直接给真实运行或第一宿主文件/函数BLOCKED及最低实现，自检提供命令与证据，不交纯收到规则。

## 20. 076bd24离线ICP真实结果已有，主线不被负载旁支拖走

S2新离线399候选及两次宿主＋旁路运行已归档，原缺真实跑分状态解除；本机核计数/原件身份与改动ICP13函数。仍未在线调用ICP或实际恢复写回/E2；详见[076bd24核验](review_20261110_076bd24/README.md)。负载与Wilson因果未隔离（每次评分22、参考/位姿不同、旧收据无load），27倍位移/残差floor因果未证，不为收窄文字继续跑数据或做负载矩阵。

S1集成/S2下一优先真实宿主恢复重处理/状态地图写回和Mode3续处理/重武装，S3旧A7最小正则并行，不调门或追加逐帧FIM日志；Codex/KITTI/四策略及负载因果后继不挡开工。最新实际工作树/正在编辑/运行任务及收到意见仍待直接回报，不从已交数据推正在实施主线。

## 21. a2e721e较低启动load实际运行接受，停止为Wilson归因循环

新归档run044830Z有load原收据，516配对、20/22改善、Wilson.7591、paired PASSED，仍info4.661<25/0接纳/E2零/WAITING。生产未变，完整恢复没有增加；[核验](review_20261110_a2e721e/README.md)。接受开发撤回窗内帧变少、参考图假说仍未证；当前成员/负载因果UNKNOWN，不继续矩阵或重跑追同值。

S1集成/S2下一直接实际宿主恢复重处理/地图写回＋Mode3续处理/终态/重武装，S3旧正则最小修并行。Codex/KITTI/四策略后继不挡接口，actual branch/工作树/正在运行及最新任务接收仍待直接回报；不因再一趟旁路观察推已经实施恢复接口。

## 22. 5f59f47真实ICP调用接线接受，窗口/A7限制保持

driver已调用ICP，本机actual node4帧接线核过；执行方最新尝试与七run对照只有日报、未交原件。当前6000缓冲再采样2000，违反冻结采样未证明；段刚体是新模型/人口假说，不立即换法或跑矩阵。service延后改变候选窗有最小正常例，新A7 cleared标签仍被旧actual producer反例否定；详见[5f59f47核验](review_20261110_5f59f47/README.md)。

S1集成/明确共享入口责任，S2复用新接线优先实际宿主restore/reprocess/internal map writeback及真实Mode3续处理/终态/重武装/E2，S3旧正则最小修并行；窗口最低snapshot/能力声明不扩线程防御框架。Codex/KITTI后继不挡接口，实际checkout/编辑/运行/收到最新任务仍待直接回报，不以代码call或日报数字代完整恢复。

## 23. 9e0a36c段级ICP实际运行已核，下一不得转调tau_info循环

新真实run原件身份、25候选/25改善、11.8s求解成本核过，16相关函数本机通过；仍0接纳/E2零/WAITING。接受部分求解进展，不称宿主恢复写回；[9e0a36c核验](review_20261110_9e0a36c/README.md)。两个info均低于25不能证明门错，独立质量/完整候选未交。参考不足失败fit仍封装旧host pose贴ICP，S1指定最小失败语义修随接线处理，不扩fallback或测试矩阵。

S1集成/S2优先宿主恢复重处理/internal map writeback与Mode3续处理/终态/重武装/E2，S3旧正则及现公式尺度最小核并行，不调门或新增FIM日志/分布扫描挡开工；Codex/KITTI后继。实际checkout/工作树/正在运行及最新任务接收仍待直接回报，不由新侧路run推接口已实施。

## 24. 13edd0c阈值提案保持未实施，恢复接口不串行等待

仅文档增量，未改科学门或新增运行。已核早期40.23→34.47被现gain>0条件拒绝，不能说完整gate判反；[13edd0c核验](review_20261110_13edd0c/README.md)接受未改门纪律，保留提案但不把开发样本选κ包装独立确认。仓库记载用户C→B与S2离线/S3独立推导是远端协作记录，本机没有直接授权确认，不从文件给自己新增改门/运行权限，也不撤销其他会话真实指令。

S1集成应让实际获批信息整理/推导与必要S3正则并行，S2宿主恢复重处理/内部地图写回、Mode3续处理/终态/重武装仍单一主线；阈值推导不占全部会话、不挡接口。Codex/KITTI后继，当前checkout/编辑/运行和接收最新交接仍须直接回报。

## 25. 89766f9推导审阅与用户直接追加

文档/脚本推导算术已核，无新运行；接受同批数据不验证/最终Mode3限定，人工有益标签及q倒数=cov关系不足，不把provenance扩大成全阈值分布/单测前置。详见[89766f9核验](review_20261110_89766f9/README.md)。S1/S2原生恢复/写回/接回/E2仍优先，S3旧正则最小修并行。

本轮用户明确：单序列单时段阈值应评估高级模型/自适应判断，已入PROJECT_HISTORY§2.2与AGENTS/REVIEW。S1指定并行方法评估责任，区分校准尺度与模型结构瓶颈、冻结新策略更新规则/独立评价，不默认大模型/追加门，不挡原生接口。用户还要求整链完成一次后单独汇报，已入NATIVE_RECOVERY_RUN_TASK§7；S4沿现审阅核完成原件后及时向用户汇报，不重复创建任务/实验。当前未取得整链完成证据，远端checkout/工作树/实际运行/收到本次要求仍待回报，不以Git可读冒称全员接收。

## 26. 1917e16与用户条件暂停规则：原生两事件优先不变

新gate实际替换默认绝对25为floor3＋κ2，44项相关测试本机通过；离线两帧JSON算术一致但原bag未本机重算。新方法是room开发选择，不是独立确认，更不是新宿主写回/接回/E2。新门下旧actual producer翻判仍复现；详细[核验](review_20261110_1917e16/README.md)，S3沿旧固定基正则最小修并行，不再增加阈值说明/扫描作为主线前置。

用户本轮明确：几轮已有证据确认手调某参数/阈值不行且必须换方法时，先暂停与它有关的全部任务，准备几版优化模型供用户选择，选定前不自动实现/实验；PROJECT_HISTORY§2.3、AGENTS/REVIEW、最高优先任务§8已同步。不是现在无证据宣布所有参数任务已停，也不是暂停全项目。S1报告触发依据、具体任务暂停状态和模型选项，S1/S2继续唯一主线**原生恢复写回→接回输入→第二事件**；必要数学修正/Codex/KITTI旁支不挡接口。最新远端branch/未提交/运行、接收及实际暂停尚未确认；S4未接管远端任务，不由Git可读称全员采用。完整流程第一次真实完成后仍单独向用户汇报。

## 27. b5554ef：开发暂停声明与原生主线范围需由S1协调

新hall两次旁路原件已核，均窗前触发/1拒绝/0接纳/E2零/WAITING；已有filtered开发输入，不是未见确认，无写回/接回新增。逐帧分布不能推出固定方向candidate的数学上限，ICP失败仍23hostpose再被node筛空，旧actual A7正则未解除；详见[增量核验](review_20261110_b5554ef/README.md)。不重跑生产未变的旧tests/宿主，不继续参数扫描。

HANDOFF声明“开发暂停、审阅侧决定”，属远端记录而非本机用户模型选择授权。本机不选删除信息腿、不控制或擅自恢复远端进程。S1应报告真正暂停哪些任务、是否有另一侧直接全局暂停及与用户本会话原生主线优先指令的协调；相关参数任务保持停，原生接口/生命周期不是默认暂停范围。S1/S2下一仍真实restore/reprocess/internal writeback→接回→E2或第一宿主文件/函数断点，S3旧最小producer正确性修并行；模型方案可准备供用户选择，选定前不实现/实验，不让其成为接口前置。当前actual checkout/未提交/进程及最新审阅收到状态未确认。

## 28. 14:37两小时汇总：S1协调暂停，S2主线不转参数

[窗口报告](MAINLINE_CHECK_20261110_1437.md)绑定12:37–14:37、截止493c5b3：组件/实际ICP尝试部分推进，原生写回→接回→E2未增加。主要工程接口/生命周期，producer正则为次要已证依赖；模型净收益、参数上限/唯一因果UNKNOWN。本机仅复用已核证据，无新实验/重复测试/重评分。

S1既有集成/manager责任、S2原生宿主、S3最小producer修保持；S1须先协调actual参数暂停与其他侧指令，不由文档让整个原生接口停工，不由S4代用户选模型。下一单一交付真实写回/接回/E2或第一宿主具体接口断点，Codex/KITTI/B10/model方案不串行挡；当前checkout/编辑/进程/收到最新要求仍需直接回报。整链完成首次单独向用户汇报，不等下个16:37窗口。

## 29. 用户已裁决恢复范围，并授权逐方案门实验调研

2026-11-10用户直接选择：**仅恢复原生恢复写回→接回→第二事件开发；参数任务继续暂停；门的每种改法先充分实验调研，详细汇报结论。**此前“待用户选择暂停范围”解除，最新入口为[NATIVE任务§9](NATIVE_RECOVERY_RUN_TASK_20261110.md)及[门调研任务](GATE_METHOD_RESEARCH_TASK_20261110.md)。不是S4建议，不再让S1/S2等待审阅侧决定删门。

S1分发/集成并确认实际恢复与暂停任务，S2优先原生接口/生命周期及既定一次流程，S3由S1确认门研究责任、必要producer数学修正并行；Codex沿现工具独立核。A删除信息腿、B因果健康历史条件化、C FIM量纲/方向重定义各做可核理论、同候选有限实验、独立质量/完整人口、负结果/代价/不确定性报告；选定前允许隔离研究，不恢复旧sigma/κ/floor手调，不自动改生产gate或部署未选方法。研究复用旧证据和主线已有产物，资源冲突原生优先，不为“充分”起无预算矩阵。

S4已将真实裁决写入共同入口并发布，不代跑/不选方案；本机当前可寻址会话仍不是已确认slam开发角色，不向其他项目派任。远端本次接收、实际进程恢复/暂停、checkout/未提交与开工待直接回报，Git可读不冒称已执行。每种门方案完成研究后详细汇报，原生整链首次完成仍单独汇报，不等三方案结束。

## 30. 用户要求再次提交：明确1个门实验会话＋2个原生主线会话

2026-11-10用户直接要求：“你再提交一次，向开发侧说明让它分一个会话来做门的改法实验，其余专注主线”。本轮重新发布明确分工，替代§29中可能让S3同时承担主线数学修复和研究的模糊安排，不改变原生恢复范围与参数暂停。

| 开发会话 | 本轮明确责任 | 不再分派 |
|---|---|---|
| S1“MM-LINS改进” | 原生主线集成/manager/有限终态和重武装；必要最小producer正确性由S1认领/集成，共享源码唯一写入 | 不亲自转入门A/B/C实验/调参循环，不等门研究完成才继续 |
| S2 r11070-c3 | 当前宿主实际恢复、修复测量重处理、内部状态地图写回、真实接回及E2运行 | 不先为三个门方案重复跑宿主，不转调门 |
| S3 r26534-58 | **唯一门实验专用会话**，逐版A/B/C理论/文献、隔离实现、有限实验与详细结论 | 不同时承担另一条原生接口/生命周期主线，不改生产门或恢复旧手调 |

由S1按实际人员/分支确认；允许换人但保持1研究＋2主线，随下一实质交付报告实际分工/状态，不另造收到周期。研究复用原生主线自然产物，缺数据先推进可独立理论/控制，不要求S1/S2停工；资源冲突原生优先。S4仅发布和审阅，不新增本机开发代理/远端实验。本轮Git发布可核，远端送达、实际分派/开工仍待回报，不冒称已执行。

## 31. 用户要求正式转向：在手任务收尾后立即按接口选宿主

2026-11-10用户要求将此前尚未提交的“先比较已有宿主接口、选择合适宿主验证”正式发布，开发完成手头任务后立即转向。最新[宿主选择交接](HOST_SELECTION_HANDOFF_20261110.md)替代原生任务对FAST-LIVO2的硬绑定，不改变两个主线＋一个门研究的分工、参数暂停和最终写回→接回→第二事件目标。

S1/S2报告当前具体改动/已启动运行，沿原预算收尾并保存代码/结果；未开工直接转，已BLOCKED给具体断点不无限等。随后核已有FAST-LIO2/MM-LINS/FAST-LIVO2真实checkpoint/重处理/内部地图写回/接回重武装调用点，选择最低真实新增工作且可验证的一个宿主；不按好ATE挑有利结果，不等检测/门全部完善，不新起多宿主矩阵。S1集成/manager单写责任保持，S2选定宿主实现与运行，S3门实验独立继续不挡主线。

下一实质交付附在手任务结果、实际接口表/选定理由及实现，或第一具体断点；受控接口两事件测试与自动原生链严格分开，完整流程首次完成单独汇报。本机本次是首次发布该转向，不宣称远端已收尾/转向/换宿主；实际会话branch/未提交/进程/收到要求仍待回报。

## 32. 16:20 S1 执行快照：两主线已开工，S1 三笔代码（实际回报）

自动化已恢复。以下均为**实际回执/实际提交**，不是任务发布。

| 角色 | 实际状态（16:20 UTC+8） |
|---|---|
| S1 本会话 | 位置 `/home/R26534/MM-LINS`，main 上本地含 `19e53b2`＋三笔 S1 代码：`04b7dd1`（候选 cov 改在 anchor body 基构造）、`a1a371d`（WAITING 段有限终态＋rearm＋`--wait-limit-sec`）、`915213f`（空候选与畸形候选分开报，`weak_dir_info_after/gain` 可为 null）。全套 **83/83 PASS**，三组新测试均修前失败。推送由有凭据会话执行（本会话凭据不可用），以远端 SHA 为准 |
| S2 r11070-c3 | 已回执：`/tmp/wt-sim`，branch `exp/m0-updated`，HEAD `b515ed5`；宿主 `/home/R26534/fast_livo2_ws/src/FAST-LIVO2`（upstream `0d2c034`＋8 文件观测补丁，**当前 binary 为 MP_EN**，sha 与 hall 两趟 receipt 一致）。**第一处实际断点**：宿主无任何 restore/checkpoint 入口、全仓 0 个 ServiceServer；缺快照与从快照重放，需新写。输入 hall01 filtered `c90300cb…`（单事件），将在 /tmp 派生双事件包（E1 +14.6 s，E2 +45…55 s），预算 rate 1.0、整包约 60 s、drain 30 s、墙钟上限 900 s |
| S3 r26534-58 | 已回执：`/tmp/wt-fourarm`，branch `exp/gate-method-research`，HEAD `19e53b2`。0 次宿主运行；A/B/C 预算分别 ≤15/≤20/≤30 min，内存 <1/1/2 GB。A-1 先做：18 条归档候选逐条重放自检，缺 `‖P_after‖` 的 4 条标 BLOCKED，诚实结论"至多 4 条、至少 0 条"；B-1 做房间02 窗前误报警因果 replay；C 排后 |
| S4 repair-f3 | 审阅侧不变；本轮只核验开发侧实际交付与结论 |

**口径提醒（来自审阅 b5554ef）**：不得再用"每帧自选弱方向的最大值"当固定触发方向上候选的上限；"三分之二数学不可达"按该定义撤回。A7 producer 的世界正则缺陷本轮已修（`04b7dd1`），但**协方差腿的判别力仍未证明**（实测 0.02–0.11，远低于 0.5），不能据此宣称 A7 准入通过。

本节为开发侧回报快照，不保证当前仍同一工作树/进程；§31用户较新的宿主选择转向保留，不因本快照丢弃。其实际接收/收尾/转向还需回报，代码效果由下一版本化审阅独立核验。

## 33. repair-f3核0edc3d7与独立研究b289283：实际增量和最低收尾

[主线核验](review_20261110_0edc3d7/README.md)、[门研究核验](review_20261110_0edc3d7/GATE_RESEARCH_REVIEW.md)分开绑定版本，不混研究与生产结果。S1源码/19e分工已采用，S2具体快照/重放缺口已回报，S3研究分支新增A1/B1/B2；这是实质增量。仍没有真实原生写回→接回→E2原件，05f宿主转向在此main尚未接收可核。

- **S1主线最低收尾**：body评价基正则局部修接受，本机60相关测试和旧模式翻转例通过，不重开。三个正常生命周期控制仍FAIL：UNAVAILABLE输入不服务期限、rearm消费旧decision、unresolved旧provisional再晋升；沿现入口/helper完成最低修和runner预算接入/新episode识别，不扩防御框架。空候选null局部接受，solver失败/0committable阶段沿旧任务如实归属。
- **S2主线**：保存当前具体接口断点/在手结果后，与S1立即按§31比较已有宿主真实接口、选最低新增工作者，不继续无限修FAST-LIVO2。现双事件包/运行仅计划，不算已跑；不因S3缺候选让主线停。
- **S3唯一门研究**：A18条归档/4缺P继续BLOCKED，别以0已确认翻转称无价值。B重复sigma归一化/漏CUSUM衰减是真基线错误；输入O包、名义窗与故障标签不能混。沿既有人口/规则有限纠正B-v1/v2并修数量/解释，保留旧结果；不自动开B-v3、扫描旧参数或部署。C定义研究未交、成本实际值待记录，尚无选型依据。详见独立核验，不承担主线修。
- **S4本机**：只核原件与正常小控制、归档复算，不改生产算法/门、不跑ROS/原bag；私人handoff保护。执行接收/当前远端进程不从快照猜，下一实质交付给自检命令和证据，无新成果不造收到循环。

## 34. 17:20 实质交付：checkpoint 冒烟 PASS、宿主选定 LIVO、A/B/C 收口

以下均为实际提交/实测，不是任务发布。

| 项 | 实际状态 |
|---|---|
| S2 原生 checkpoint | `590aa50`（合入 `4aac70c`）：深拷贝 10734 voxels / 21349 nodes / 210985 pts（ack 0.086 s）；回滚逐值相同；8 帧重放走 `processImu`+`handleLIO`+`UpdateVoxelMap` 0.358 s。**未实现**：修复测量注入、隔离期停写图 |
| 宿主选择 | S1 `055b200`：继续 FAST-LIVO2（LIO 主路径）。理由：唯一已有实测 checkpoint/restore/reprocess；视觉地图 LIO 模式不读；MM-LINS 组件齐全但未跑通。重开条件写在文档里 |
| 第一断点 | **隔离期宿主仍写图**：`restore` 只在回滚瞬间成立，下一帧 `UpdateVoxelMap` 把污染写回。S2 下一步（`handleLIO` 门控 + `sync_packages` 处置） |
| A/B/C | 分支 `exp/gate-method-research@545340f` 已推远端。A 0 翻转/4 BLOCKED；B 两版负结论（吸收比 49.9×、覆盖 0.291）；C 定位到评价样本，补丁使复制输入逐位不变（1.121），但 `min_eig_trans` 40.91→1.12（−36×）⇒ `tau_abs_min` 必须重导 |
| 裁决 | C 补丁**暂不集成**（版本化后再入，确认性运行前重导 floor）；A 不删；B 搁置。S3 研究任务收口 |
| 主链状态 | `main@5bae7bf`；双事件包 `/tmp/fastlivo/hall01_two_event_v1.bag`（`c3e905da…`）保留；原生两事件**尚未开始** |
| 已知交付缺陷 | `test_checkpoint_client.py` 为 pytest 风格，`unittest discover` 发现 0 项；已要求 S2 改为 TestCase |

## 35. repair-f3核adff0b0/545340f：原生入口推进，下一次直接验证持续链

[原生审阅](review_20261110_adff0b0/README.md)接受真实C++snapshot/restore/reprocess实现，A4/A6局部推进；报告冒烟数量/耗时不是本机原件实测，逐值等价缺原件，最低提供已有log/result/config receipt不重跑矩阵。宿主转向已收到并按接口选FAST-LIVO2 LIO，选定可先推进有限验证，不把研究校准作为前置。

- **S1集成/manager**：实际SUSPECT且无active时仍snapshot，本机正常控制FAIL；绑定hoststamp与backdated可信边界，复用明确健康prefix受控快照即可先检机制，不造快照库。旧三个生命周期最低修仍相关，runnerwait接线已完成不重开。gate accepted与native动作结果分别记录，失败ack不算成功写回/接回。
- **S2宿主**：沿现循环无group也服务控制、重放旧cloud等公开输出门控；当前隔离仍写图/捕获原云重放未注入修复测量/restore后时间线未闭合。最小接通实际修复输入支配原生重估和内部地图、再接回/E2；不是把ICP位姿直接写_state。双事件包准备不等运行，沿原预算保存失败/完整人口与尾段结果。
- **S3专用研究**：C有实际新增，重复控制局部接受但新坐标采样控制FAIL约4%；两因素消融不纯、κ自动保留无证、示意patch不能apply。A/B旧基线/输入标签错误未纠正；先有限纠正并保持真实候选效益BLOCKED，不重导floor/调旧参数/集成生产。不把仓库裁决当本会话用户已选，S3收口是开发状态而非研究已验收。
- **S4本机**：只读源码/归档和小正常控制，未代跑ROS/原bag或改算法。局部进度不升完整A/B，总链首次真实完成仍单独报告；原件缺失和源码断点分开，不说“没有任何进展”。

## 36. repair-f3核f2bbbb5：hold编排/测试发现推进，不等实际两事件

[版本化核验](review_20261110_f2bbbb5/README.md)接受Python开段hold/rearm-resume接线、候选输入归档、unittest入口修正；host hold表是开发报告，新实际patch与ack/log/result尚未提交，旧host diff不识别hold/resume。完整两事件仍未运行，不升完整A/B。

- **S1最低接线修**：事件队列不保护单cmd/ack，本机正常确定性控制错计两次成功及迟到hold→restore；沿现通道单in-flight、短poll不终结、匹配ack消费一次。完整接纳HEALTHY没有rearm event，Python不发resume；与S2明确实际成功reprocess后的解除契约、partial仍隔离，不无条件放写。sidecar区分输入全集与真实verified/holdout/anchor，复用现node评价处，不为研究补字段延迟宿主。
- **S2宿主**：保存已运行hold源码patch/完整ack/log/result及binary/config绑定，不重跑矩阵。map计数不证明状态与地图同stamp；修复注入/原生重估/同时间线接回/E2及旧无组control/旧cloud公开正常修沿既定budget直接交付，失败按已选宿主范围回报，不无限绑定。
- **S3研究**：不由候选输入sidecar宣布完整after/P/独立质量已获证，沿旧最低纠正并行，不调旧参数、不部署未选生产方法，不要求主线重跑旧人口。
- **S4本机**：5选定测试PASS、正常控制FAIL/BLOCKED如实归档；pytest未装/全discover不跑、不install/shim、不因测试数量增加称闭环。私人文件保持不提交，本机不修算法/跑ROS。下一实质交付仍实际写回→接回→第二事件，首次完成立即单独汇报。

## 37. repair-f3核06f543a/2449c0b：主线无新执行，门研究控制对象需纠正

[核验](review_20261110_06f543a/README.md)保留撤回C2集成方向，main本次只有日报追加，无新原生源码/两事件；不从测试数/日报记录提升验收。§36主线最小接线和部署原件任务继续，S1/S2直接交实际修复写回→接回→E2，不等研究。

S3新P1固定方向缩放12.137倍有算术证据，但四位小数匹配不叫逐位，最近scan配对5–23ms/方向约28°有范围，真实candidate after仍BLOCKED。P2 r1/24排序比较自选最弱向与λmin，不是固定trigger方向；复用正常actual gate例after100≠λmin38.89否定一般恒等。m0只等价全谱最小值阈值，在P=Λ逆同基限定下对应cov腿；新Loewner/序贯定义不等候选有效性或部署裁决。最低纠正对象/基/precision/JSON reading，不新跑bag/重导floor/扩新模型；旧A/B错误仍按已发最低要求，研究不占主线。

## 38. repair-f3核e2db4b3/3e9f947：证据补齐接受，比较基需最小纠正

[核验](review_20261110_e2db4b3/README.md)接受研究rotation_control原件/Loewner定义和reading文字一致；主线没有新源码/运行，不升A/B。新fixed列同时加平移且重新单位化Ad方向，本机exact协变SPD原投影1/物理搬运1/再单位化1/6，说明一般比较对象变了；不推归档数全错，也不撤C2不集成。最低纯旋转t0或完整SE3不再单位化/回anchor，不扩扫描/重导floor/改正确生产transport。

S3专用研究纠正这个小控制并保留缺candidate/独立质量BLOCKED；S1/S2继续§36已发原生正常接线与部署原件、下一唯一实际修复→内部写回→接回→E2，研究不作前置，参数仍停。本机只算术/sourcepin，无ROS/原bag，私人文件保护；首次真实整链完成仍单独汇报。

## 39. 20:12 实质交付：受控两事件整链完成；在线链仍 BLOCKED 在上游检测

以下均为实际运行/提交，不是任务发布。main `d35671f`。

| 项 | 实际状态 |
|---|---|
| 受控两事件整链 | **完成**（`fl_native_20261110T115717Z_3390402`）：两段触发 15.08/42.43（声明 14.6/42.0）、决策 17.28/45.24、关闭+rearm 22.55/49.06、`hold→restore→resume` ×2 全 ack、终态 HEALTHY、`candidates_detail.jsonl` 2 行、两事件间消费 368 帧。run_mode 标 `CONTROLLED_INTERFACE_TEST` |
| 控制通道 | 已移出 LIO 主循环（独立线程 + 原子标志，`bd87db8`）：received/applied 0.001–0.005 / 0.196–0.592 s，**调度延迟 24.1 s → 0.006 / 0.119 s** |
| 决策耗时 | 索引优化后 **4356.5 → 842.9 ms**（support 273 / holdout 275 / paired 294 / gate 0.6），五段无一 >1 s |
| 等待上限 | `e3a60e7` 修好"隔离路径从不求值"；`466f1a3` 修好"替换式开段无 episode"；wait 固定 2.0 s（一个确认裕度） |
| LIO 单帧 | restore 前后 2–18 ms / 1–16 ms（中位 12 ms，单次 1.066 s 离群）——**restore 不变慢**，旧的 30 s 超时解释已撤回 |
| 在线自动链 | **BLOCKED（上游检测）**：38 s 内多次假警报 → 反复 restore → 位姿/地图不再一致 → E2 窗口 87 帧全 UNAVAILABLE。受控结论不能替代它 |
| S3 门研究 | `exp/gate-method-research@3e9f947`，A/B/C + 门控形态 Part 1/2 已交付并推送；C-2 补丁因旋转不不变性**撤回集成**；S3 待命 |
| 已知限制 | 30 次滚动快照 7 次 ack 超时（0.5 s 预算，单列）；受控触发的 MODE2 接纳是机制证据、非修复质量 |

本节保留开发侧实际回报，不自动接受其研究归因/裁决；§33原审阅范围仍绑定0edc3d7/b289283，新原生与C研究另按adff0b0/545340f核验。宿主转向05f7fc5已由新main接收并完成接口选择，取代此前该项“未收到”状态；完整原生两事件仍未交。


## 40. 复核 S3 更正与 S2 归档；补上"接纳不放写"缺口

以下为 S1 复核实测（非自报）。

| 项 | 实际状态 |
|---|---|
| S3 更正 | `62f294b`（合入 `aa731b5`）：两脚本本机重跑复现——P1 5/5 在 5e-4 内（max rel 1.56e-5 / abs 3.79e-5，扫描 dt 5.39–23.19 ms）；P2 纯旋转 C-2 room02 0.66/0.39/20.1%、hall01 40.4/14.9/426%；SPD 1→1.0→1/6、`‖Ad v0‖²=6`；actual gate 100 / `λmin=38.8889` / Mode 2 接受。旧混合读法保留并标注 |
| S2 归档 | `792d838`（合入 `10900c9`）：`deployed_host.diff` 对干净 `0d2c034` apply 成功，与本机宿主 `diff -r` **0 个已跟踪文件不同**；`SHA256SUMS` 26/26 OK；二进制/库/配置/launch/bag 与 receipt 逐位一致；157 测试通过 |
| 新修缺口 | `resume` 原本只跟 `rearm`；Mode 2 完整接纳静默置 `HEALTHY`，宿主 `map_hold_` 不释放。已加 `commit_closed` 事件 + 驱动放写；test-first，全量 **160 通过**。**未在宿主上跑过接纳路径** |
| 未闭合 | §57 LIO 逐帧耗时原始记录未归档（NOT_ARCHIVED）；在线链仍 BLOCKED 在上游检测；接纳路径需一次真实整链验证 |

## 41. S2 触发锚改为绝对 pose 戳；仍未跑新的宿主运行

以下为 S1 复核实测。

| 项 | 实际状态 |
|---|---|
| S2 提交 | `55750fc`（S2 侧合 main 后 `b86b889`；S1 合入 main）：新增 `--scripted-trigger-stamps`（ns，首个 ≥ 戳的帧触发）与 `--confirmation-margin-sec` 透传；触发体抽成 `_trigger_segment_now`，两个锚走同一 manager 入口；receipt 记两种声明与 margin；全量 **161 测试通过** |
| 动机 | 相对首配帧的秒数随启动/负载漂移约 0.2 s，而相邻扫描的门读数一个 3.14（可接受）、下一个 21.14（拒绝），声明 14.6 s 的两次运行并不测同一件事 |
| 未做 | **没有新的宿主运行**（巡检时无 fastlivo/rosbag/recovery 进程，无新 receipt）；接纳路径的 `commit_closed→resume` 仍只有单测 |
| S3 | `exp/gate-method-research@62f294b` 无新提交、工作树干净，待命 |

## 42. 受控接纳 run 复核：门真过、宿主真放写；三处断点（串行化已修）

以下为 S1 复核 S2 原始件（`docs/review_20261112_accepted_chain/`）的实测。

| 项 | 实际状态 |
|---|---|
| 运行 | `fl_native_20261112T020634Z_4148249`，`CONTROLLED_INTERFACE_TEST`，宿主二进制未变（`0d7e23de…`）；绝对戳触发落在 kf 132 |
| 门 | before 3.1388 → after 6.6937（≥6.2776），Wilson 0.9220，holdout 0.4421，Mode 2 accepted；committed kf 133–164（32 帧），deferred 95–132 + 165–179（71 帧） |
| 宿主放写 | 末 ack `OK resume … hold=0 held_frames=104`；`host.log` 的 `Update Voxel Map`：hold 前 219、hold→resume 间 **0**、resume 后 **448**（本机独立计数，667 行总计） |
| 断点 1 | `commit_closed` 结构性不可达：隔离段 population 含回滚帧 95–132（manager 触发时登记），驱动候选只从触发帧起，故任何候选都无法覆盖全段；本次经 wait 超时 + `rearm` 放写。**属协议选择，未动** |
| 断点 2 | `reprocess` 从未执行：`decide()` 连发 reprocess→set_state，宿主 5 ms 轮询只读到后者；`host.log` 中 `[NATIVE_CHECKPOINT] reprocess` **0 行**，`restores=0`。**已修**：客户端串行化（`_outbox`，只有快照可被抢占），test-first 2 项在旧代码 FAIL，全量 164 通过 |
| 断点 3 | 驱动记账卡死（队头 reprocess 永不被认领，`native_checkpoint.events` 停在 `hold`）——同一修复消除；本机复核 events 仅 11 条、末条 `hold` |
| 未解释 | 宿主收尾时 `double free or corruption (out)` 一行，发生在前两次运行没有；未定位，已记录 |
| 不能声称 | `commit_closed→resume` 走通、接纳后地图已被 reprocess 重建、驱动侧记录了 resume |

## 43. 串行化验证 run：reprocess→set_state→resume 各一次并执行；协议保持

以下为 S1 复核 S2 原始件 `docs/review_20261112_accepted_chain/run_fl_native_20261112T022158Z_4156288/`
（合入 `bf965bf`）。

| 项 | 实际状态 |
|---|---|
| 门 | 同一绝对戳/声明，Mode 2 accepted：before 3.1388 → after 6.6761（≥6.2776）、Wilson 0.9197、holdout 0.4412；committed 31 / deferred 81（仍 partial） |
| 命令通道 | `native_checkpoint.events`：hold → reprocess → set_state → resume，**各有且仅各一条**；reprocess 应用耗时 5.5 s，set_state/resume 各 0.5 s；resume `trigger=rearm` |
| 重放 | `host.log` `[NATIVE_CHECKPOINT] reprocess #1: 416 frames replayed …, map now 19194 voxels/362286 points`（checkpoint 15161/298650）；`repairs applied=0` |
| 放写 | resume ack `hold=0 held_frames=171`；之后快照持续增长到 56639 voxels（末条） |
| 口径修正 | “hold 窗口内 `Update Voxel Map`=0” 在有 reprocess 的 run 里不适用：`reprocessCheckpoint` 重放期间临时清 `map_hold_`（`LIVMapper.cpp:933-977`，本机核对），窗口内写图来自重放 |
| 限制 | `repairs applied=0`：重放用的是宿主自己的原始扫描，候选的“修复”只通过末尾 `set_state` 进入；不能声称“用修复测量重建了地图” |
| 用户决定 | 2026-11-12：**保持现协议**（候选总体不扩到隔离总体）；`commit_closed` 仍不可达，按接受限制记录 |
| double free | 本轮未出现；上轮那行保持原记录，未推测 |

## 44. 主线达成（受控）：同一 run 内写回→接回→第二事件两段走完

以下为 S1 复核 S2 原始件 `docs/review_20261112_accepted_chain/run_fl_native_20261112T024337Z_4166038/`
（`cf948be`，合入后 main）。

| 项 | 事件 1 | 事件 2 |
|---|---|---|
| trigger | kf 146 `1627785276215170145` | kf 422 `1627785308048271418` |
| 决策 | `1627785280281185627` | `1627785312188321114` |
| 门 | before 3.1388 → after 7.2145，Wilson .8947，holdout .3906，**Mode 2 accepted**，committed 23 / deferred 62 | before 22.0641 → after 17.6810，Wilson .8304，holdout .5588，**Mode 3 refused** |
| 关闭 | `wait_limit_closed`(80 帧) → `rearm` | `wait_limit_closed`(132 帧) → `rearm` |
| 原生 | hold → reprocess(applied 3.611 s) → set_state → resume(`trigger=rearm`) | hold → restore(applied 0.496 s) → resume(`trigger=rearm`) |

- 触发 1→2 **276 帧**；第一段关闭→触发 2 **210 帧**；触发 2→bag 末 **122 帧**；`candidates.jsonl` **2 行**；
  `lifecycle.events` 4 条；终态 **HEALTHY**、`quarantine_open_at_exit=false`；本轮无 `double free`。
- 宿主日志：`reprocess #1`（316 帧重放，map 17876 voxels）与 `restore #2`（37335→36511）均在；
  `restore #1` 是 reprocess 内部那次，与驱动 `restores=1` 一致。
- INDEX 初版三处数值与自身 JSON 不符（after 7.2154、holdout 0.4369 / 0.4677），S2 已按
  `candidates.jsonl` 改正并留修订注脚；其中 0.4369 追到 `fl_native_20261110T113447Z_3372448` 的
  `cand_0000.holdout_nis = 0.4368596204571292`（本机 `/tmp` 原件核对存在）。
- 输入身份（`README.md` §0，字段取自三份 `receipt.json → inputs`，S1 已逐项核对）：宿主二进制
  `0d7e23de…` 与运行时库 `0eacffe1…` 三次**逐位相同**；`recovery_node_source` 在命令串行化（`bbe916f`）
  前后不同（`fb746ddd…` → `18d92a03…`），run 2/3 相同。
- **限制**：第二事件是事件、不是第二次接纳；`commit_closed` 仍不可达（用户已定保持现协议）；
  `repairs applied=0` 表示重放用宿主原始扫描，修复仅经 `set_state` 进入；该 run 的 hold 窗口不能用
  `Update Voxel Map` 计数判断停写（reprocess/restore 都会写图），普通帧看 `held_frames` 126 / 248。

## 45. repair-f3核d0743e1：受控注入部分命中，原生部署身份仍BLOCKED

[核验](review_20261110_d0743e1/README.md)接受新人工zshift接口probe及开发20/10/10负结果保留，非算法修复/完整两事件；helper完整24-byte记录/header本机PASS，host新版apply/hold patch/log/result仍未提交、旧diff未变，不能关闭实际部署/接回验收。126测试不替代运行证据。

S2沿已给rawheader/组成员归属最小修，随下一实质交付保存actual新patch/已有inject戳/ack/log/input-config-binary receipt；10未匹配UNKNOWN不猜LIVO，实际wall窗/26s默认与27.7s报告差须真实命令限定。smoke重复OUT会删旧结果，最低新空目录/拒绝既有目录，禁止自动清前次数据。同实例同checkpoint对照方向合理但仍保留重放不确定性，不宣称差值自动纯修复效应；不新矩阵、不直接灌ICP姿态替重估。

S1复用§36命令归属/trustedstamp/full-vs-partial释放/评分集最低接线，source未改不重跑；S3研究独立和参数暂停保持，不挡S1/S2实际修复写回→接回→E2。本机仅字节/静态核、无ROS/原bag，私人文件保护；完整A/B不提升，首次真实整链完成单独汇报。

## 46. repair-f3核930563d：写回来源/顺序FAIL，记录仅本地未发布

[本机核验](review_20261110_930563d/README.md)两个四元数测试PASS；actual normal driver写ep旧host尾x20，而候选修复末帧x2；partial尾deferred仍写x20；reprocess失败也set_state。本机用模拟正常report/ack隔离编排，不叫真实门/宿主成功。S1最低已准入/同stamp修复来源、partial隔离与失败动作顺序，复用single in-flight/ack和trustedstamp任务，不重构估计器。

S2人工set_state烟测试是受控位姿接口观察，不是算法修复/地图等价/完整接回E2；新版host source/log/results/config receipt仍未归档。计数增不证明地图从零或全是新点，精确匹配回退/merged计数语义保持UNKNOWN。下一主线仍实际修复测量支配原生重估/内部map-state写回→接回→第二事件，S3并行/参数停，不等新研究。

发布阻断：上一轮push因携带开发smoke脚本rm-rf既有OUT被权限检查拒绝，本轮新增smoke_writeback亦有同删除。本机未执行、未删数据、未重试/换工具/要求peer代推；本条与前轮d074核验仅本地，远端review仍3965299。需实际开发改新空目录/拒绝覆盖旧产物，或用户明确相关发布权限后再处理，不冒称已送达。

## 47. repair-f3核d5f7d8f：进程内负对照新增，保真度与效应归因未闭合（仅本地）

[核验](review_20261110_d5f7d8f/README.md)接受开发保留426group、12替换/8未匹配和撤修复效应PASS；三差值本机算术核过，非独立宿主实测。不能拿旧run live量级或z→x非线性响应确认本次control失真；本次同末stamp live终态/实际control源码/原件仍缺，保真度UNKNOWN，不从缺交付猜二次积分或restore根因。README效果已测与日报撤PASS最低统一，不为措辞另跑宿主。

S2随下一主线实质交付归档同次live/control/treatment末stamp、已运行host patch/log/receipt及已有matched戳。新分类读发布全集且用cp而非lo作inside下界：本机单个合成正常空隙反例复现，不能代actual8缺测归属；复用已有20戳分类，不新宽窗/大重复矩阵。S1仍负责正常命令/准入写回来源与失败顺序最低修，旧source未变不重跑；S3研究并行、旧参数继续停，生产门不改。下一唯一主线仍实际修复测量→原生重估/地图写回→接回→E2，完整A/B不重评分。

本机sourcepin分类控制与bash-n退出0，无ROS/原bag。实际自动所有权已核：本会话4既有Cron未复制，peer列表无repair-3e；未向其他会话要求代推。私人handoff保护，前push拒绝未解除，本条及报告只本地、远端review仍3965299，不称开发已收到。

## 48. repair-f3核969c424：浅拷贝诊断/修后同stamp表推进，host_poses不等实际修复（仅本地）

[核验](review_20261110_969c424/README.md)接受撤14m与补同stamp表，报告差值7.239cm/2.883cm本机算术成立；旧归档指针别名风险固定上游源码支持，actual深拷贝/新匹配代码和日志尚未归档，旧8帧重放PASS待实效复核。S2随下一实质交付保存已运行patch/log/receipt、每帧点数/地图变化与20条rawscan→group归属，复用已有helper保持两次消费源缓存，不造新缓存框架。≤0.2s最大前戳的单个合成正常例可选前一scan，非本次实际错配证明；不把20/20当身份验收，不再扩窗口。

S1冻结host_poses为已声明编排控制，可交受控两事件/拒绝/尾段，不包装算法修复；参数0.884是已有配置，不重启调参。主线最终仍实际修复测量→原生重估/内部写回→接回→E2，S1旧命令归属/写回来源/partial及失败顺序沿最低已发任务修，S3研究独立且旧参数停。actual当前远端进程未独立核，不由日报“已合入129/129”猜已完成运行；本机无ROS/原bag/全suite，只读源及小控制退出0，不升完整A/B。

4个既有Cron/无旧repair-3e owner已核，不复制任务、不找peer代推。私人handoff保护，前push拒绝仍未解除，本条只本地、remote review仍3965299，不称开发收到。

## 49. repair-f3核e3a60e7：两事件负尝试已交，期限入口修好但旧段归属仍FAIL（仅本地）

[核验](review_20261110_e3a60e7/README.md)接受开发双事件bag同实例102.7s负尝试报告：E1提前报警/拒绝、hold/restore后498配对、E2未触发；是接线探索非完整实际修复链。S2旧8帧PASS显式取代方向接受，新4LIO非空/地图增长报告待原件，本机未跑宿主；实际host源码/log/receipt仍未交。

S1新UNAVAILABLE期限服务本机4项测试和actual on_pair复用例PASS，关闭/rearm确可达；同入口马上使旧unresolved provisional key7再次trusted pose/factor/空间地图，正常反例FAIL。最低既有关闭/队列移出该段旧provisional，保留归档/新帧，与已发fresh-decision/命令归属并行修，不造新状态机/防御矩阵。S2原900s预算继续真实接回/E2或首断点，host_poses若先验编排如实标签；最终主线仍实际修复测量→原生重估/内部地图写回→接回→E2。已有原件随实质交付归档，措辞集中清理，S3独立/旧参数停，不为Mode2调门。

开发下次自检用PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令/证据逐项给期限/归属/真实释放/事件/修复来源/E2/尾段，不能用测试总数或继续消费替成功。A9/A10局部探索推进，不升完整A/B；本机脚本退出0、无ROS原bag。实际owner核4既有Cron且无旧repair-3e，不复制/代推，远端进程当前未独立核。私人handoff保护，前push拒绝未解除，本条仅本地、remote review3965299，不称开发收到。

## 50. repair-f3核1b8a449：等待/重武装已运行报告，参考恢复与预算解释待定位（仅本地）

[核验](review_20261110_1b8a449/README.md)接受第二次负run等待关闭/rearm/resume报告局部推进，不叫完整接回/E2；169帧UNAVAILABLE/fed5/E2未开仍是断点。S2先沿已有stamp把旧新run及rearm后头20帧support fraction/参考缓存与实际点数/pose/host特征对齐，同kf不同配对人口不是身份。初次清空地图及末特征降不足以单独定位尾段根因；本机小例prev_scan且AVAILABLE/fed1，二者谓词不同；回滚timestamp≥t_q_start与报告“边界在所有项之后”方向需纠正，不改正确隔离。

S1的wait10→2秒只记预算提案，无第三次原件/源码新增；confirmation margin不是唯一等待预算证据，当前wait从segment.t_end而非独立decision参数起算，最低明确message/wall身份、若声明独立decision起点沿现入口传入，不新时钟框架/参数扫描。本机两个小控制exit0，非真实169帧根因或2秒部署复现。S1旧unresolved provisional/decision/命令/写回正常任务source未改不重复测；S2下一仍实际修复→原生写回→接回→E2或预算首断点，先host_poses控制如实非算法修复。S3独立/旧参数停、生产gate不改，文档集中清理不升级新实验前置。

新增Codex bdc4c1f README/REVIEW已读、固定493c5b3仅参考，未合/未执行；不把旧无接口论点当当前缺陷、不据其建议替代用户主线。开发自检仍需PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令/原件，actual当前远端进程未独立核；4既有Cron无复制/旧repair-3e无活peer。A/B完整分不升、首次整链完成仍单独报，目前未完成。私人handoff保护，前push拒绝未解除/未绕过，记录仅本地、remote review3965299，不称开发收到。

## 51. repair-f3核9ee52dd：replacement episode补齐，旧rearm释放新段须最小修（仅本地）

[核验](review_20261110_9ee52dd/README.md)保留第三次wait2负run支持局部恢复、两提前报警段/第三段无episode/E2未处理，不能宣布2秒最佳或真实修复完成。S1新after身份比较本机actual loop开episodePASS，但复用旧decision路径+模拟宿主正确ack，on_pair新段hold后service旧rearm resume、新段active却释放FAIL。最低现生命周期使旧段释放不作用当前隔离，fresh-decision避免reset后用旧报警，保留正常无新段resume；不用新RPC/矩阵，旧provisional/ack/写回来源任务沿已有反例修。

S2 runner两个记账修复局部接受：存活期savedPGID退出后可用、receipt写成功exit0不洗JSON FAIL且整体STATUS仍检查；bash-n PASS。本机4选定测试0.043s与小控制exit0，新开发test在首main guard后且依pytest模块未实跑，不叫131本机验收。S2固定原预算/wait2不扫描交下一实际修复→原生重估/内部写回→接回→E2或首断点，host_poses编排控制如实单列；actual patch/已有receipt/log随实质交付，guard/文字集中旁支，S3独立/旧参数停、生产门不动。

自检需PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令原件，段数/131不能代真实E2/恢复。A9/A10局部推进，A8/B2仍具体隔离风险、B4/B11未闭合，不升完整A/B。实际owner4既有Cron无复制/旧repair-3e无活peer，远端当前进程未独立核；私人handoff保护，前push拒绝未解除未绕过、本条只本地、remote review3965299，不称开发收到。

## 52. repair-f3核4b47249：五段拒绝循环有报告，完整恢复与真实E2仍未交（仅本地）

[核验](review_20261110_4b47249/README.md)保留run154.3s/5episode/拒绝51deferred/close-rearm与原生动作报告，E2窗87不可判、未完成；wiring OK不关闭旧正常反例，driver/node/manager/hostpatch本轮未改不重测试。支持1m/60%≠NIS半径3m；表中等待间隔算术不证明timer失败、累计5次回旧stamp不证明10秒轨迹改动或唯一错图根因，snapshot2超时保留UNKNOWN不称无影响。

S1沿9ee已发最低修新旧段释放/fresh-decision/帧及命令/写回归属；S2声明测试触发的受控两事件接口可在原预算先检机制，实际恢复→同stamp接回→E2/尾段结果与automatic BLOCKED分开，host_poses/人工输入不当算法修复成功。最终唯一主线仍实际修复→原生重估/内部写回→接回→E2，S3独立/旧参数停，支持恢复或保图新策略须具体证据后交选择，不自动部署。

开发下次自检分PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令原件，接口/检测/修复/收益分开，归档已有实际patch/run_summary/receipt/log/stamp，不新矩阵。A/B完整分不升、本机静态/算术无ROS原bag，首次整链真完成仍单独报，当前未到。4既有Cron无复制/旧repair-3e无活peer、远端当前进程未独立核；私人handoff保护，push拒绝未解除未绕过、记录仅本地remote review3965299，不称开发收到。

## 53. repair-f3核fafbd0c：受控第二次拒绝接口已报告，实际修复整链仍未完成（仅本地）

[核验](review_20261110_fafbd0c/README.md)接受同实例受控两次触发/拒绝native restore、中间216帧消费报告；原件/actual hostpatch未归档、第二段终态WAIT无尾段释放，不能叫actual修复/整链完成。S1新scripted分支需最低保存trigger当帧candidate input并同步已撤node空间参考：本机actual node/loop撤trusted key7后ref仍7/100点、下一隔离帧不清，trigger pending有0但episode frames空；复用现_track_episode/_sync_spatial_map即可，不新参考框架。旧归属/释放/ack/写回任务source未变不重测。

S1连续来帧不重置wait的解释纠正接受、本机control PASS；晚设wait起点仍UNKNOWN，沿下一实质小窗既有三处诊断核decision/t_end/wait_start，不新锁/时钟/参数矩阵。S2 summary未fired标签已分，receipt仍只按声明，最低requested/actual取已有summary，属于记账旁支不把本次两fired报错。S2下一仍实际修复测量→原生重估/内部地图写回→接回→E2/尾段或预算断点，受控拒绝范围单列，S3独立/旧参数停、生产门不改。

本机小控制与bash-n exit0，无ROS原bag/开发suite，A/B完整分不升，首次真实整链仍单独及时报、当前未到。开发自检PASS/FAIL/BLOCKED/NOT_APPLICABLE+原件/命令区分受控触发/输入归属/参考撤销/native结果/等待/E2尾段/算法修复。4既有Cron无复制/旧repair-3e无活peer，远端当前进程未独立核；私人handoff保护、push拒绝未解除未绕过、本条只本地remote review3965299，不称开发收到。

## 54. repair-f3核b581a7c：诊断默认关闭/语义未变，驱动阻塞修复尚未交（仅本地）

[核验](review_20261110_b581a7c/README.md)接受SLAM_RECOVERY_WAITDIAG默认安静与段尾起点声明，本机开关2.005s同关闭/0vs4行PASS；只工程诊断、不是原生恢复。小窗validate晚t_end与进入WAIT取值报告保留，但首次snapshot ack早validate35.642s、deadline到段尾18.55s，缺实际bag start/deadline到达/service/cmd-ack重叠，不能断言启动期16.42s等待阻塞已到期决策。S2先复用已有原件定位哪条等待覆盖，不为归因再跑大矩阵；driver本轮未改，0.5s等待不等非阻塞、第一ack前不发须明确已有ready启动，不新RPC/锁框架。

S1保持现等待语义可声明，旧trigger候选输入/参考撤销/unresolved/旧decision-rearm/ack/accepted写回正常任务source未改不重测；S2沿现通道最小正常阻塞解除后交实际修复→原生重估/内部写回→接回→E2/尾段或原预算首断点，S3独立/旧参数停/生产门不改。自检PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令原件分诊断/实际阻塞/驱动修后/真实修复E2，不拿136测试或日志数量代成果，完整A/B不升。

本机小控制exit0无ROS原bag/全suite，完整链未到首次完成；4既有Cron无复制/旧repair-3e无活peer、actual远端当前进程未独立核。私人handoff保护，push拒绝未解除未绕过，记录只本地remote review3965299，不称开发收到。

## 55. repair-f3核8ca5b41：异步snapshot局部解除，普通hold/迟到同名ack仍需归属修（仅本地）

[核验](review_20261110_8ca5b41/README.md)接受tick异步/status启动/poll保pending/异名检查，2测试0.056s与正常文件控制PASS，旧同步快照与50ms即丢pending该入口关闭。S1/S2最低所有正常命令真single in-flight：未消费status可被hold覆盖并卡队首、snapshot软件timeout后旧同名ack可计新成功，两个明确本机控制非native错配实测，不造RPC/新框架。旧帧/trigger参考/decision-rearm/accepted写回正常source未修不重跑。

开发报告0.4s入口延迟、评估18s与MODE2 23key/169deferred保留为机制/成本观察，不当actual修复质量/E2。S1新marker是累计elapsed且不含尾部node同步/native动作，driver offset在evaluate前非实际wait赋值，沿已有原件分入口/赋值/返回最小定位，别改wait藏迟决策/新成本矩阵。S2下一仍实际修复测量→原生重估/内部地图写回→接回→E2/尾段或原预算断点，partial/host_poses控制单列；S3研究独立、旧参数停、生产门不动。

自检PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令原件分异步/命令归属/实际partial动作/成本/真实修复E2，入口延迟和提交数不代完整成果。A/B完整分不升、本机exit0无ROS原bag/全suite，首次真实整链未到；4既有Cron无复制/旧repair-3e无活peer、远端当前进程未独立核。私人handoff保护、push拒绝未解除未绕过、记录只本地remote review3965299，不称开发收到。

## 56. repair-f3核9862ad5：精确索引等价性通过，成本旁支回到受控两事件（仅本地）

[核验](review_20261110_9862ad5/README.md)27邻格原距离判定及同decision索引复用局部接受，3测试0.143s/actual support正负控制与暴力一致，不改生产阈值/人口、不造第二套索引。开发16→13candidate窗口4356.5→842.9ms保留优化后成本观察，不当纯同人口5.168倍，不为逐值复现新矩阵；完整native成本/原件仍待实际交付。

2.2s消息时差减墙钟计算不是独立wall阶段证据，只需诚实保留并沿下一主线最小三时刻分时钟记录，不要求消除后才推进。S1/S2继续旧正常命令/帧/参考/释放/accepted写回最低修，S2下一实际修复→原生重估/内部地图写回→接回→E2/尾段或900s首断点，host_poses/受控准入机制非质量；S3研究独立、旧参数停、生产gate不改。自检PASS/FAIL/BLOCKED/NOT_APPLICABLE+原件，843ms/140不代整链，完整A/B不升。

本机脚本exit0无ROS原bag/全suite/性能大矩阵，首次真实整链未到；4既有Cron无复制/旧repair-3e无活peer、远端当前进程未独立核。私人handoff保护，前push拒绝未解除未绕过，记录只本地remote review3965299，不称开发收到。

## 57. repair-f3核95b0d97：原生动作超时待归属，调度时间戳最低修（仅本地）

[核验](review_20261110_95b0d97/README.md)保留受控run128.8s/restore与hold ack超时/355帧继续消费，actual修复E2链未完成，ack超时不确认动作未应用。S1/S2新sched字段每到期帧重设，本机首次wall100后帧124入125记1而首次资格25正常例复现，最低同episode首次记录/新段重置、分wall/message，不重改历史时序/扩测试矩阵；post_eval仍不含native等待。

S2先已有actual hostsource/cmd读取应用ack日志核具体断点；旧公开restore返回后立即写ack再LIO，不能直接用恢复后慢LIO解释该restore未ack，旧single-inflight/ack缺口仍未修。S1独立线程received/applied提案非本会话用户新架构选择，received不等主循环应用变快，现通道最小归属改动保持研究尺度，大设计按规则报用户选择、不代授/代实现。下一仍真实修复测量→原生重估/内部写回→接回→E2/尾段或原900s首断点，S3独立/旧参数停/生产门不改。

自检PASS/FAIL/BLOCKED/NOT_APPLICABLE+原件/命令分首次排队/动作received-applied/真实修复E2，wiring OK不代动作成功。完整A/B不升，本机小control exit0无ROS原bag/全suite；4既有Cron无复制/旧repair-3e无活peer，远端当前进程未独立核。私人handoff保护、push拒绝未解除未绕过、记录仅本地remote review3965299，不称开发收到。

## 58. repair-f3核d35671f：受控拒绝两段完成有报告，accepted依赖顺序仍FAIL（仅本地）

[核验](review_20261110_d35671f/README.md)首次报告受控两Mode3拒绝hold/restore/resume均完成、两rearm/终态HEALTHY，已即时说明局部成果；actual修复写回/自动检测/独立收益与完整尾段原件仍缺，旧host patch不含新线程。S2保留已运行newpatch/receipt/log/applied时间人口，30快照全OK与7超时分开，撤本run慢LIO强因果合理不当旧run根因已证。

3项本机测试0.233s、received不能代applied控制PASS，所有_send异步解除旧30s调用等待，但S1/S2 actual driver/client模拟partial正常准入reprocess尚未applied就set_state覆盖物理cmd、写deferred旧尾x20；即使后reprocess FAIL依赖动作已发。最低现通道真实single-inflight/apply成功后推进、失败未知停依赖、实际准入同stamp来源/partial归属，不造RPC/新事务框架。service pending检查只在新决定前不保护该依赖序列；旧normal帧/参考/释放/ack/首次资格任务source未改不重测。

下一唯一仍实际修复测量→原生重估/内部地图写回→接回→E2/尾段或900s首断点，S3研究独立/旧参数停/生产gate不改。自检PASS/FAIL/BLOCKED/NOT_APPLICABLE+原件分拒绝机制/actual修复/动作结果/partial/E2尾段，完整A/B不升，本机exit0无ROS原bag/全suite。4既有Cron无复制/旧repair-3e无活peer、actual远端当前进程未独立核；私人handoff保护、push拒绝未解除未绕过、记录仅本地remote review3965299，不称开发收到。

## 59. repair-f3核70f68fb：公开部署与旧受控原件推进，下一仍actual修复整链（仅本地）

[核验](review_20261112_70f68fb/README.md)局部接受actual部署patch/26归档哈希及旧d356双拒绝、持续输入/E2后尾段；纠正§52“原件全缺”和368区间解释（实际E1decision→E2trigger诊断217帧），不改旧报告。受控run无repair/reprocess/set_state，不等actual恢复；E2原生snapshot/restore比隔离起点晚约3s，trusted时间归属有原件断点，source→binary构建仍UNKNOWN。

S1/S2最低解除真实single-in-flight/applied依赖、旧close不得release新active、checkpoint不晚于可信隔离边界。70新fullcommit event两testPASS0.007s但本机目标blob控制复现：reprocess/set_state旧尾→未applied再resume覆盖；实际manager串行旧close→新trigger/hold→旧resume释放新段。两反例FAIL非部署接纳实测，不扩RPC/锁/异常矩阵。下一900s预算actual测量修复→原生状态重估/内部地图→接回/E2尾段或具体宿主首断点，逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+实际命令原件；成功首次及时单报，不等研究。

S3旁支接受62f294对fixed/own与坐标/精度控制的有限纠正，A/B旧逻辑/人口缺口未动；集中修既有缺口/小数值叙述，不开大矩阵、不自动生产部署，旧参数继续停。A/B仅行ID局部变化不新全表评分，远端当前执行/本地意见接收UNCONFIRMED。20min8e05b042、2ha249a2ce、daily7f3f33f6属本会话，旧5min已取消；无双写。记录仅本地、push拒绝未解除不重试/绕过，private保护、不改算法、不合main。

## 60. repair-f3核bbe916f：串行成功局部解除，失败依赖仍需最低修（仅本地）

[核验](review_20261112_bbe916f/README.md)本机目标blob支持outbox成功reprocess→set_state→resume与received不推进，1test0.010s/actual节点absolute stamp控制PASS；pytest缺失导致首跑exit1已记录，未安装/shim、未跑全suite/native。正常准入FAIL reprocess仍自动发旧尾set_state x20（修复x2）及后续resume，FAIL_REPRODUCED_LOCAL；S1/S2最低按applied成功推进依赖、失败未知不放写、实际准入同stamp状态来源。旧段release/晚trusted checkpoint未变不重测，不扩RPC/防御矩阵。

新文档报告accepted run fl_native_20261112T020634Z_4148249有门准入/partial与放写，但reprocess未执行、记账卡头、收尾double free；目标缺所引原件目录，只DEVELOPER_REPORTED，串行化后run未独立确认。S2并行归档现原件保留负结果，S1/S2下一唯一900s actual修复→原生重估/内部地图→接回/E2尾段或具体首断点；逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+实际命令原件。S3研究无新增/旧范围纠正/参数仍停，不等其收口、不全表升分。三既有Cron单owner无复制，当前remote执行/意见接收UNCONFIRMED；仅本地提交、push拒绝未解除不重试/绕过、private保护。

## 61. repair-f3核3dec39a：原生成功通道有原件；全宿主第二事件矩阵须交付（仅本地）

[核验](review_20261112_3dec39a/README.md)两新归档各25SHA一致，022158Z真实重放416group、state命令各OK/内部地图更新/接回局部支持；两run仅单trigger、detection off、host_poses、repair应用0，无E2，不能作actual修复整链完成。旧正常FAIL依赖/旧尾/段release/晚checkpoint未修，直接复用反例不重测；上run double free保留未定位。

最新用户直接强调所有宿主第二事件矩阵，覆盖旧“不扩多宿主矩阵”的单宿主交接；S1下一认领五命名宿主矩阵及分工，S2先复用MM-LINS历史双事件、ORB多次原生恢复、LIVO双拒绝原件，并给独立FAST-LIO2/LIO-SAM未执行项真实原因/具体接口BLOCKED或NOT_STARTED，不能把无记录猜成不能跑。每行E1→接回→E2/尾段、状态/命令/source/input/run/证据，原生自身与actual修复分开；现授权预算/超范围具体报告、不造通用checkpoint/无限矩阵。S3门旁支、参数继续停、不等门收口；A/B只局部、不新总分。

本机只Git原件核验，无host/bag/测试/调参，远端当前执行/意见接收UNCONFIRMED。三任务单owner、private保护，本地白名单提交、push拒绝未解除不重试/绕过，不称开发收到。

## 62. 最新顺序：先非FAST-LIVO2四宿主各跑一次第二事件（仅本地）

用户2026-11-12再次纠正偏回仅FAST-LIVO2，直接要求先跑其余宿主。[执行任务](NON_FASTLIVO2_SECOND_EVENT_TASK_20261112.md)明确S1/S2下一优先MM-LINS、FAST-LIO2、LIO-SAM、ORB-SLAM3四项，各实际E1→输入继续→E2/尾段；不等LIVO全部问题修完、不用历史摘要代新执行、不以完整事务适配挡原生机制测试。现有已启动任务原预算安全收尾后转向，不擅自停未知进程，不再新开LIVO轮次替代。S1实际分工/owner/执行回执待确认，S3研究旁支及参数停不变。

逐项PASS/FAIL/BLOCKED及命令/source/input/run/事件stamp/原件/尾段；未启动给NOT_STARTED真实原因，不猜环境或算法不能跑。FAST-LIO2与MM前端共享身份明示、不冒两次独立执行。审阅侧顺序交接错误已纠正，本机不代跑；本地提交不等收到/开工，push拒绝未解除不重试/绕过，private保护。

## 63. repair-f3核751a226：保存既有LIVO双事件局部成果，不替代四宿主先跑（仅本地）

[原件核验](review_20261112_751a226/README.md)024337Z受控run有E1partial accepted/reprocess316group/set_state/resume，E2refused/restore/resume及E2关闭后28帧；25SHA一致、状态动作OK，接受局部原生接回/E2，不充actual修复（repair应用0/detection off/host_poses）。cp晚于边界/旧normal缺陷未修、人口计数端点明确，不新防御矩阵或全表评分。

本增量发布早于用户明确四宿主优先，不称其为MM-LINS/FAST-LIO2/LIO-SAM/ORB本批交付；下一仍先各实际一次E1→继续输入→E2尾段，S1/S2逐项自检状态/实际命令原件/具体BLOCKED或NOT_STARTED原因，不等LIVO修完、不起新LIVO轮次、不等S3门研究。当前远端接收/执行UNCONFIRMED，本机仅Git原件核验无host/bag/tests，独立review本地提交、push拒绝未解除不重试/绕过，private保护。

## 64. 接收最新审阅：四宿主第二事件优先；实际环境清点与分工

审阅 `0ee5f3f`/`6e959e9`/`1f1527b` 已合入 main（`0e23548`）。任务
`docs/NON_FASTLIVO2_SECOND_EVENT_TASK_20261112.md`：先各跑一次 MM-LINS、FAST-LIO2、LIO-SAM、ORB-SLAM3
的第二事件，再回 FAST-LIVO2。以下为 S1 本机实际清点，不是任务发布。

| 宿主 | 本机实际资产（已核实） | 已知缺口 |
|---|---|---|
| MM-LINS/SC-PGO | `~/mmlins_ws` 已构建（`aloam_velodyne/alaser{Mapping,Odometry,PGO}`、`fast_lio/fastlio_mapping`）；`~/run_mmlins.sh` 一键脚本；`~/datasets/mmlins/campus_*(.bag)` | 无两事件触发接口；E1/E2 只能按声明时间窗观察宿主自身行为 |
| FAST-LIO2 | 无独立工作区；仅 `~/MM-LINS/FAST-LIO` 源码 + `mmlins_ws` 内 `fastlio_mapping` | 与 MM-LINS 前端**同源同二进制**，必须标 `SHARED_EXECUTION`；独立构建尚未验证 |
| LIO-SAM | `~/catkin_ws/devel/lib/lio_sam/lio_sam_imageProjection` 已构建；`params_mmlins.yaml`（`velodyne_points`/`imu_raw`）；`hall_01.bag`（351 s，3511 云帧）、`campus_1(2)-003.bag` | hall 需 remap `/camera/imu`→`imu_raw`；无 slam_recovery 接线 |
| ORB-SLAM3 | `~/ORB_SLAM3/build/libORB_SLAM3.so`、`Examples/Monocular-Inertial/mono_inertial_tum_vi`；`~/orb_slam3_results` 有 hall_01 单目惯性 59 s 结果与 ROS 节点配置 | 已知反复 lost/重建；无 slam_recovery 接线 |

分工（实际 owner，非"正在执行"）：**S2 先 MM-LINS、再 FAST-LIO2（SHARED_EXECUTION）；S1 先 LIO-SAM、再 ORB-SLAM3。**
每项按任务 §4 交 PASS/FAIL/BLOCKED/NOT_STARTED + 实际命令/source/input/run/事件 stamp/原件/尾段。
当前四项均为 **NOT_STARTED**（本行写于 11:4x，任务刚接收、尚未起进程）。

## 65. 四宿主矩阵进度：LIO-SAM 实际跑完（宿主失效），其余待跑

以下为 S1 本机实际运行/归档。

| 宿主 | 状态 | 实际证据 |
|---|---|---|
| **LIO-SAM** | **已跑完一项：宿主原生 FAIL；slam_recovery NOT_IMPLEMENTED** | `docs/review_20261112_four_host/lio_sam/`：campus_1(2)-003（`1fb5d827…`）260 s 连续输入，1120 条 odometry；E1 [50,70) 正常（最大步长 0.571 m），130.1 s 起发散（>1 m 步 85 次、最大断流 3.201 s），E2 [190,210) 含 535 m 单步，尾段仍跳、终点 z=625.95 m，未恢复 |
| MM-LINS | 运行中（S2 发起） | 巡检时 `run_mmlins.sh campus_12_fl.bag` 进程在跑，尚无新提交/归档 |
| FAST-LIO2 | NOT_STARTED | 本机无独立工作区，只能以 `mmlins_ws/fastlio_mapping` 做 SHARED_EXECUTION（S2 负责） |
| **ORB-SLAM3** | **已跑完一项：宿主原生 FAIL；slam_recovery NOT_IMPLEMENTED** | `docs/review_20261112_four_host/orb_slam3/`：全序列 351.65 s，80 次地图初始化（E1 窗 4、E2 窗 6、尾段 3），最终 Atlas 1 图 0 关键帧，`exit=139`；窗口计数由 `mnFirstFrameId` 精确映射 times.txt，非按墙钟估算 |

LIO-SAM 运行器问题教训（已写进归档 README）：先单独起 `roscore` 会让 `roslaunch` 报
`run_id ... does not match declared run_id`，节点起不来、录制为空；改为让 roslaunch 自己持有
master 后 20 s 探针录到 124 条 odometry。前两次空跑不构成运行证据。

## 66. repair-f3核088906a：两宿主负尝试原件局部接受，继续余下两项

[审阅](review_20261112_088906a/README.md)接受LIO1120CSV负结果本机复算、ORB rawlog80初始化/0KF/exit139；非LIVO任务已有真实执行，不称宿主恢复成功。两声明实际上运行开始后/分析前，LIO时间窗以首输出非已绑定bagstart，ORB times未归档故window4/6/3仅开发报告。当前支持连续输入两观察窗的失败，不证两独立故障及E1恢复后E2响应；沿已有原件补runner/时钟/事件来源，不新跑矩阵追成功、不猜算法根因。

S2下一交MM-LINS（开发报告运行中）与FAST-LIO2（NOT_STARTED/shared前端范围明示）实际结果或具体命令BLOCKED，S1集成，S3研究/参数暂停不变；两已跑宿主保障并行，不挡余下两项、不回LIVO。逐项自检状态+命令/source/config/input/run/原stamp/尾段/失败证据，NOT_IMPLEMENTED修复层与原生层分列。前push限制已解除并由main接收review1f1527b；本轮review提交推送、private保护，本机无host/bag/tests，不全表升分，接收新意见另待回执。

## 69. repair-f3核f48b23f：四命名项已尝试，下一真实测量接线复用旧组件

[核验](review_20261112_f48b23f/README.md)余下MM/backend与改版frontend各另跑一次、原件15SHA和gap/tail算术一致，单独frontend rawlog两睡眠/两建图；共享实现非共享同一次运行、不是独立原版FAST-LIO2验证。原生re_slam/继续输入存在，不接受开发§66“所有宿主无恢复能力”；四项共同缺的是slam_recovery测量修复接线，LIO/ORB负结果/观察窗限保留，不重跑追成功，matrix不是公平修复收益表。

S1/S2后继有限实际修复范围给真实回执/产物/原生map接回E2或首断点，不机械重回修LIVO全部问题；文档转述选INJECTION不充本会话授权。缺publisher/scan原件身份属已核接口事实，但现有point_mixture_filter和完整记录导出/C3可复用，不能说仓库没有测量修复器或让用户从零选以挡开工。沿旧正常来源/FAIL依赖最低修，累计received不等本次应用stamp；注入标签/原云不得作为部署生产者反演，oracle明确、真实质量缺证据UNAVAILABLE。自检状态/命令/source/input/点人口/applied/native同stamp/E2尾段，S3门旁支参数停不变、不全表评分。本机未跑host/bag/tests/算法，未merge分叉main，只review增量提交推送/private保护，收到新意见待回执。

## repair-f3 / 18baefd增量：测量替换接受，修复失败与E2缺口保留

[核验与最低交接](review_20261112_18baefd/README.md)接受run043602Z_79001的60帧声明损坏、25条修复云received/applied、382group原生重放及内部map/接回，17新列示SHA一致、实际driver SHA匹配目标；在线修复接线不再NOT_IMPLEMENTED。但+0.0029m未消除+0.5m，ICP未收敛、质量/因果未确认；只一触发，无E2，不报首次有效整链完成。常速incumbent是初值不是独立GT，开发“吸收偏差”解释与初值改善预期不当已证定论。

本机8cloud test及有限actual driver/client控制，未代跑host：原坏云+delta pose通过的候选若再施加同delta到测量会重复补偿（identity z1.5→门z1→新云配同pose z.5）；E2累计旧received25、本次0仍synced；full提交后同步失败仍commit_closed→resume；零发布仍reprocess。正成功入口通过，反例不冒充本次归档已发生。S1最低本次人口receipt/成功依赖与共享生命周期集成，S2唯一物理修复/符号/候选一致及native真实完整状态，不灌旧尾；无需新RPC/阈值或全防御矩阵。

下一唯一有限主线：实际去偏→原生状态/map→接回→第二事件/尾段或首断点；自检逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+实际命令/原件/完整人口/失败/质量。四宿主前批尝试不重开，S3门旁支与旧参数暂停不变。7.17ms窗口/kf134/598帧/stale protocol集中旁支更正，不重跑迎合文字；A/B局部推进不全表升分。独立review正常SSH提交推送、分叉main未merge、不改算法/private保护；实际接收及后继运行待开发回执。

## repair-f3 / 2f1f59b增量：估计进展接受，传输与失败接回不当成功

[审阅](review_20261112_2f1f59b/README.md)新37列示SHA一致；incumbent初值run044445门拒绝/未发布/restore-resume，解耦run045238估计median+0.40/MAD0.05、施加−0.40合理，host仅20/26 received、0applied/0reprocess、sync失败仍rearm-resume后发散。两run各一事件，无E2，无独立收益。队列20原patch支持工程解释但drop具体层未独立证，不机械超过20必丢。

S1最低native成功依赖与失败公开一致；S2按已派分批流控复用现通道、本次增量/stamp及实际应用，再保持修复测量/候选/native状态同定义。candidate尾set_state来源局部改进不等原生重估：target实际decide/producer合成反例证明旧坏云门见world0，改新云后同pose world−.5。新估计器无支持0被计入median亦本机确认，但本run26帧全n_valid≥27，不作首因；少支持标UNKNOWN，不扩防御矩阵。11cloud tests通过、无ROS/bag/算法修改；旧累计receipt/可信cp范围未关闭不重复重测。

下一唯一有限实际修复→native完整state/map→接回→E2尾段或首断点；允许真实拒绝/失败，不能为保旧accepted候选绕评价新测量。逐项自检状态/命令/原件/完整人口/独立质量/失败，truth只评价、旧门不降、S3旁支参数停、不重开四宿主矩阵。A/B局部推进不全表评分，正常SSH独立review提交推送、不合main/private保护；实际接收/后继执行待开发回执。

## repair-f3 / 64bfed1增量：分批/人口冻结接受，实际支持不同不报收益

[核验](review_20261112_64bfed1/README.md)四run source绑定、本轮70列示SHA一致，32/32及冻结23/23received/applied、实际native重放/内部map接回接受，旧20/26首断点在这些run局部解除。freeze23个candidate pose stamp全一致，但815vs692group，起点差1.268s/终点5.334s/跨度4.066s，地图不归因；set_state ACK差4.7cm为命令pose，不独立重估质量。deferred87/81/147/148、wait关闭/ABORTED rearm及失败诊断保留，四run各一事件无E2、不报有效整链完成。

本机actual publisher非零baseline/批次停止与tracking冻结PASS，None基线当0时E2旧25/新0仍sync FAIL，最低取得有效本次baseline、不默认为0。新测量/旧坏云candidate及candidate尾灌状态源码未修，S1成功公开/native依赖与同stamp集成、S2物理一致产物/有限native实际修复→接回/E2或断点优先；sham同批次不保证重放支持相同，按实际stamp核、不无限对照循环代主线。自检逐项状态/命令/原件/独立质量/失败，冻结门不降/旧参数停/S3研究、不重开四宿主矩阵。一般文档计数/区间及框架延期，A/B局部推进不全表评分。独立SSH review推送、不合main不改算法/private保护；实际接收待回执。

## repair-f3 / d193680增量：terminal生效但全人口与后缀接回失败

[核验](review_20261112_d193680/README.md)三run59列示SHA一致，旧sham23应用、新terminal两driver绑定target/实际库匹配f27d构建hash；整体build ABI失败不隐去。新两臂candidate pose stamps同、实际终点与payload同，起点差约1s/开段snapshot晚trigger2.933及1.934s；23received但applied7/12、dropped16/11，不能写23/23应用或可信trigger checkpoint。三run无E2，HEALTHY/尾段输入非恢复完成，map差不归因。

新host skip451/509已消费group后仍clear整个replay buffer，source与原件支持接回人口缺口；需保后缀native按序追赶到input边界或显式拒绝，不单为A/B端点对齐删除连续状态输入。S1最低实际应用人口/native成功公开依赖、S2可信完整checkpoint/产物/后缀与接回，按戳arm只是受控开发方案不等自动迟检测。旧物理候选/source来源问题未修不重测，不新RPC/阈值/防御矩阵。下一唯一有限真实修复→native state/map→catch-up→E2尾段或第一接口断点，自检逐项状态/命令/原件/失败未知/质量，S3参数停/研究、不重开四宿主。A/B局部复核不总分，独立review SSH推送、不合main不改算法历史/private保护；实际接收待回执。

## repair-f3 / 用户UNAVAILABLE取证要求：不能再只打印标签

[任务](UNAVAILABLE_DIAGNOSTIC_TASK_20261112.md)由用户2026-11-12直接提出。核最新e82d900现_record_diag仅nis/source/map点数且2000条截断，要求S1复用计算入口：逐帧support比例/分母/失败reason及mask，当前raw与最终effective NIS/旧值来源年龄/参考3m点数/局部面残差/coverage分支，scan/pose/当时参考版本身份；每UNAVAILABLE保存实际采样点/参考及原row mapping，summary全paired流式、不刷全图、不事后用新map造原因。S2现输入/宿主预算检测on有限归因，交代码分支计数/连续段/正常边界与不可用复算或具体BLOCKED；native恢复/E2并行、S3参数停/研究。诊断不得变计算/门值、truth只评分，原件缺项UNKNOWN，自检逐项状态/命令/原件/成本。不升A/B总分，不说任务发布即已执行。新main的v3/A-B运行尚未完整审，不继承旧缺陷为已确认当前失败；本机不改算法/代host，独立review SSH推送/private保护，实际认领待开发回执。
