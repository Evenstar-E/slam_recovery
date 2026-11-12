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

## 66. 四宿主第二事件矩阵完成（各一次实际运行）；无恢复能力是共同结果

S1 复核 S2 原始件并独立复算（main `fb59682`）。四项均已实际运行，均为**宿主原生行为**，
slam_recovery 层四项一律 `NOT_IMPLEMENTED`（未现造接线）。

| 宿主 | 输入/事件 | 实际结果 | 状态 |
|---|---|---|---|
| MM-LINS/SC-PGO | `campus_12_fl`（`a924b5f9…`，469.4 s）；E1/E2 = 首个 IMU + 115.99/230.09 s（manifest 历史休眠起点，声明观察非注入） | 前端两次停发 **23.7 s / 26.8 s**、重建回原点（跨间隔 **60.56 / 71.11 m**）；PGO 两次停 **38.5 / 41.4 s**、跨间隔仅 **0.749 / 0.485 m**（本机按 header 剔除 0 戳占位后复算，与报告一致）；`Issleeping` 2×true、间隔 113.90 s；尾段 PGO 227 s / 967 条 | 原生 **PASS** |
| FAST-LIO2 | 同一 bag/戳；**SHARED_EXECUTION**：唯一 `fastlio_mapping` sha `59674a8f…` 即 MM-LINS 前端，无独立工作区 | 停发 **23.8 / 26.9 s**、跨间隔 **60.56 / 71.13 m**（本机独立复算一致）；`Isbuilding` 2×true；尾段 239.3 s / 2126 条 | 原生 **PASS**，独立实现验证 **NOT_APPLICABLE** |
| LIO-SAM | `campus_1(2)-003`（`1fb5d827…`）260 s；E1=[50,70) E2=[190,210) 尾段 | E1 正常；**130.1 s 起发散**（85 次 >1 m、断流 3.201 s）；E2 窗含 535 m 单步；尾段终点 z=625.95 m，未恢复 | 原生 **FAIL** |
| ORB-SLAM3 | `hall_01` 全序列 351.65 s；E1=[190,220) E2=[300,330) 尾段 | **80 次地图初始化**（E1 4、E2 6、尾段 3），Atlas 终态 1 图 0 KF，`exit=139`；复跑 74 次同模式 | 原生 **FAIL** |

共同结论：MM-LINS/FAST-LIO 前端在两次事件处靠**自有 re_slam 重建**存活；PGO 保持全局图。
LIO-SAM/ORB-SLAM3 在同等"连续输入 + 两事件"下不存活。**没有任何一项具备原生恢复写回/接回**；
四项的 slam_recovery 修复链均为缺口，不得把第一层结果写成修复效果。

身份缺口（如实）：MM-LINS 两个二进制 mtime（10-30 / 11-05）早于运行的源码 HEAD `2ef0169`，
本机无构建记录把它们绑到该 HEAD；可核的是运行时的二进制 sha。LIO-SAM/ORB 同样只绑定二进制 sha。

## 67. 修复测量缺口定位（无运行、无实现）：纯位姿修正不可能变成测量修复

S1 复核 S2 `54f5027`（合入）。`docs/review_20261112_four_host/REPAIR_GAP.md` 三条原因均已对到行，
本机逐条核对成立：

| # | 原因 | 代码位置（本机核对） |
|---|---|---|
| 1 | 驱动从不发布修复点云 | `recovery_node.py` 全文件只有 status publisher（:1768）；唯一发布者 `inject_repaired_scan.py:60`，受控 run 未启动它 |
| 2 | `reprocess` 重放原始扫描 | `LIVMapper.cpp:943` 用 `replay_buffer_` 原样；`:956` 仅在队列非空时 `applyRepairedScan`；`applyRepairedScan` 首行 `if (repaired_clouds_.empty()) return false`（:728）——`repairs applied=0` 是必然，不是匹配失败 |
| 3 | 候选是位姿不是测量 | 候选 `ΔT @ inits`（`pose_reregistration.py:296`），`CandidateMap` 只有 `repaired_poses`（`core.py:304-320`），门 NIS 用原始 `scan_buffer_body` |

**语义结论（S1 认可）**：设修复位姿 `T' = ΔT·T`，把世界点重新表达回修复后 body 系得 `T'⁻¹ΔT·T·p = p`，
body 点云不变；而宿主 `applyRepairedScan` 替换的正是 body 系测量。所以纯位姿"修复"即使发云，
也只让 `repair_applied` 计数非零、估计不变。真正的测量修复必须改变几何（去动态点、纠去畸变或
已知损坏修复），该生产者在仓库里不存在——这是需要用户先定的语义，不是驱动 bug。

**最小接线（待用户定语义后实施，本轮未做）**：驱动保留 scan header stamp 与原始 PointCloud2
（`_on_scan` 有 stamp、`_dispatch` 未传），新增修复云 publisher，header 用原始 scan stamp；
轮询 status ack 的 `repair_received` ≥ N 再发 `reprocess`；顺序 hold → 发布/确认 → reprocess →
set_state → resume。宿主最小 0 行（`repaired_clouds_` 64 条上限是唯一硬限制）；manager 0 行。

## 68. 用户决定：先做"已知损坏修复"（受控注入）作为实际修复测量

2026-11-12 用户选定：**已知损坏修复（受控注入，INJECTION）**，不做去动态点，也不现在收口。

含义与边界（S1 定，交 S2 实现）：
- 损坏是**声明式**的：受控 run 用 relay 把 bag 的 `/velodyne_points` 转到宿主，在声明窗口内对
  每帧施加已知的系统性偏差（例如 z 方向 +0.5 m），窗口外原样透传；损坏参数与戳逐帧落盘，
  标 `INJECTION`。
- 修复是**测量级**的：驱动/修复生产者对同一损坏帧用可信参考地图做点面配准，估计并去掉该偏差，
  产出 body 系修复点云（保持 `x,y,z,intensity,time,ring` 布局与原 header stamp），经
  `/native_recovery/repaired_scan` 送入宿主。
- 顺序：hold → 发布修复云并轮询 `repair_received` ≥ N → `reprocess`（`apply_repairs=true`）→
  `set_state`（最后接受位姿）→ rearm/`commit_closed` 后 `resume`。
- 宿主 0 行改动（`repaired_clouds_` 64 条上限对 32 帧候选够用）；驱动与修复生产者约 150–200 行 + 单测。
- 能声称：修复测量进入宿主重放、`repair_applied>0`、地图由修复测量重估；**不能**声称真实世界
  修复收益（损坏是自己注入的），也不改门/阈值/σ。

## 69. 声明损坏修复的传输链走通，但估计器没看到偏置（首轮否定结果）

S1 复核 S2 `6fc0fc2`（合入，176 测试通过）。run `fl_native_20261112T043602Z_79001`：

| 项 | 实际值（本机复核） |
|---|---|
| 损坏 | relay 599 帧中 **60 帧移位 +0.5 z**，539 帧原样；候选 25 帧全在移位集合内（`relay_frames.jsonl`） |
| 门 | Mode 2 accepted 3.134→7.299，Wilson 0.9023，holdout 0.4285，committed 25 |
| 修复传输 | 发布 25 → `synced=true` → `reprocess #1: 382 frames …, repairs applied=25 queued=0, map 18032 voxels`；`[NATIVE_REPAIR] applied … points≈5900` 逐帧可见 |
| **否定结果** | `repair_publish.bias_z_m = 0.0029`（不是 0.5）；ICP 修正 **0.0269 m / 0.216°**、`ITERATION_LIMIT` 未收敛（残差 0.0502） |

原因（成立）：损坏是统一 body-z 平移，宿主 LIO 把它吸收成位姿，在**宿主位姿**下损坏云与干净地图已经对齐，
点面配准没有信号。旁证：同戳本 run 触发位姿与无注入 run `022158Z` 相差 `[0.72,0.48,-0.03] m`，而 ICP 修正仅 0.03 m。

**不能声称**：修复改变了估计、0.5 m 被扣除、任何修复收益。**能声称**：声明损坏、字节级移位、
25 条修复云发布/接收/应用/重放替换与命令顺序全部成立。

**下一步（已派 S2）**：配准初值改用门已有的 incumbent（trusted 外推）位姿，`bias≈+0.5` 才可见；
约 15 行 + 单测，再跑一次同声明受控 run；若效应出现，再补一次"同管线关掉修复发布"的对照以隔离效应。

## 70. incumbent 初值让偏差可见（0.027 → 0.815 m），但拟合不收敛、候选被拒

S1 复核 S2 `bc7bd98`（合入，177 测试）。run `fl_native_20261112T044445Z_85628`，同 bag/戳/窗/margin，
只改 ICP 初值为 incumbent：

| 项 | 实际值 |
|---|---|
| ICP | 修正 **0.815 m / 0.357°**（宿主位姿那次 0.027 m），`ITERATION_LIMIT`，inliers 706（上次 1352），残差 0.0535 |
| 候选 | before 3.1341 → after 6.3645（信息量过线 6.2682），但 Wilson **0.2855** → `MODE3_SOFT_BRIDGE_WAIT` **拒绝** |
| 修复 | 未发布（只有 accepted 才发），无 `bias_z`、无 `repair_received/applied`；原生命令 hold→restore→resume，终态 HEALTHY |

断点判定：**不是"仍无效应"，而是"效应可见但 0.8 m 初值超出 ICP 0.5 m 对应门限"**，拟合停在半路，
候选位姿既不等于宿主位姿也不等于真值。

**S1 决定采用 S2 的方案 2（解耦）**：候选继续用宿主位姿初值（已 accepted、Wilson 0.90），
偏差另用 incumbent 位姿下的一维 body-z 搜索估计（点面残差最小），按该 bias 发布修复云；
**不改 `IcpConfig`、不改门/阈值/σ/宿主**。约 15 行 + 单测，再跑一次同声明受控 run。

## 71. 解耦偏差估计合理（+0.40 m），但 26 条修复云只到 20 条，重放被正确拦下

S1 复核 S2 `7e1eb0c`（合入，180 测试）。run `fl_native_20261112T045238Z_92133`：

| 项 | 实际值 |
|---|---|
| 偏差估计 | 26 帧逐帧 body-z 一维搜索：median **+0.40**、MAD 0.05、逐帧 0.25–0.55；`|0.40−0.5|=0.10 ≤ 0.15`（运行前声明） |
| 门 | Mode 2 accepted：3.1341→6.8216，Wilson 0.9057，holdout 0.3882，committed 26 |
| 传输 | 发布 26；宿主 ack `repair_received=20 repair_applied=0 repair_dropped=0`；`synced=false` |
| 结果 | `_repair_gate` 拦下 `reprocess`（无 `reprocess #`、无 `[NATIVE_REPAIR] applied`）；wait 超时→rearm→resume；终态 HEALTHY |

根因：宿主 `/native_recovery/repaired_scan` 订阅队列 20（`LIVMapper.cpp:320-321`），26 条一次性发布，
回调处理前的 6 条在传输层丢失（`repair_dropped` 只统计宿主内部队列）。

**旁证（原生效应，不是修复）**：损坏窗口内宿主发散到 `state_pos≈(-1823,1488,-1387)`、
`voxels=582146`，resume 后仍继续发散；修复未重放，所以这段发散未被纠正。

**下一步（已派 S2）**：分批发布 + 回执流控（每批 ≤20，等累计 `repair_received` 到位再发下一批，
全部到位才发 `reprocess`；超时则不发并记录），不靠固定 sleep；宿主 0 行、门/阈值不动。

## 72. 修复测量首次真正进入宿主重放：32/32 送达并应用；对照尚未干净

S1 复核 S2 `76c06b8`（合入，185 测试）。

| 项 | 修复 run `045944Z_96435` | 对照 dry-run `050645Z_102106` |
|---|---|---|
| 门 | Mode 2 accepted 3.1341→6.8326，Wilson 0.9220，holdout 0.3700 | accepted 3.1341→7.3491，Wilson 0.8947 |
| 偏差 | median **+0.45**、MAD 0.05、32 帧 | +0.40 |
| 传输 | 4 批 10/10/10/2，累计回执 32，`synced=true` | 不发布，`published=0` |
| 宿主 | `repair_received=32 applied=32 dropped=0`；`reprocess #1: 676 frames … repairs applied=32`；**32 行** `[NATIVE_REPAIR] applied`；地图 22334 voxels/417461 points | `repair 0/0`；重放 529 帧；地图 20427/373515 |
| 顺序 | hold → 4 批发布 → receipt 32 → reprocess(9.0 s) → set_state → rearm 后 resume | 同前但无发布 |

**不是干净 A/B**（S2 如实报，S1 认可）：两次 episode 帧数 **32 vs 23**、重放跨度 676 vs 529 帧，
决策落在不同帧集（2 Hz service tick 决定何时跑决策），地图与 `state_pos` 差约 1.15 m 不能全归因于修复。
能干净比较的只有计数：`repairs applied=32 vs 0`。**不能声称修复收益或轨迹结论。**

**S1 决定**：先做**候选帧集冻结**（deadline 到达时冻结 episode 帧集，之后到达的帧只进隔离段/延迟集），
使同一输入下候选人口与重放跨度确定，再跑一对同声明修复/对照。属驱动侧约 10 行 + 单测，
不改门/阈值/σ/宿主，也不改决策时刻。

## 73. 候选人口冻结生效（23/23，同一冻结戳）；重放跨度仍差 5.3 s，A/B 仍不可归因

S1 复核 S2 `54d4ef2`（合入，189 测试）。`docs/.../freeze_ab/{repair,control}/`：

| 项 | repair | control |
|---|---|---|
| 冻结 | `frozen_at_ns=1627785280281185627`，23 帧 | 同一戳，23 帧 |
| 门 | accepted 3.1341→7.3427，Wilson 0.8947，holdout 0.4185 | accepted 3.1341→7.3482，Wilson 0.8947，holdout 0.4091 |
| 偏差 | +0.40（MAD 0.05） | +0.35（MAD 0.05） |
| 修复 | 23/23 received/applied，synced | 0/0 |
| 重放 | **815 帧 / 27.14 s** | **692 帧 / 23.08 s** |
| 重放后地图 | 24503 voxels/473187 | 21870 voxels/418979 |
| set_state | 7.706,5.651,−0.366 | 7.725,5.608,−0.370（差约 6 cm） |

原因（已定位、S1 认可）：repair 在决策后要先完成分批发布+回执才发 `reprocess`，宿主从最后快照捕获到
命令应用时刻，repair 的缓冲区多覆盖约 5.3 s/123 帧（多在损坏窗口外）；起点还差 1.27 s（快照周期）。
因此地图差异**不能归因于修复**；能干净比较的是人口、门、修复计数与 set_state（差 6 cm，与同一候选一致）。

**下一步（S1 决定）**：跑**sham 对照**——同样分批、同样回执、同样时序，但发布未修正的损坏云（零平移），
两次重放跨度应对齐，唯一差别是云是否修正。若跨度仍不一致，停并报原因。门/阈值/σ/宿主不动。

## 74. sham 对照：唯一测量差别确认（逐帧 z 差 0.40 m），重放跨度仍差 4.33 s

S1 复核 S2 `1301c41`（合入）。sham run `052437Z_114016`：23 条按 10/10/3 发布、`synced=true`、
`repair_received/applied=23/23`、发布平移 **0.0**（未修正损坏云）、`repairs applied=23`。

| 项 | repair（`050?` freeze_ab/repair） | sham |
|---|---|---|
| 冻结 | 同戳 23 帧 | 同戳 23 帧 |
| 门 | 7.3427 / Wilson .8947 / 23 committed | 7.3321 / .8947 / 23 |
| set_state | 7.706,5.651,−0.366 | 7.702,5.648,−0.365（差 3 mm） |
| 逐帧云 z 差 | 0.40 m | 0 |
| 重放 | 815 帧 / 27.14 s | 686 帧 / 22.81 s（差 **4.33 s**） |
| 地图 | 24503 voxels/473187 | 21744 voxels/408xxx |

**跨度不固定的根因**：决策之后到 `reprocess` 应用之间的墙钟计算（门评估+逐帧偏差搜索+分批发布/回执）
随负载变化，而宿主从快照一直捕获到命令应用。5.3 s 不是分批的固定代价（sham 只差 4.33 s）。

**S1 决定（需要最小宿主改动，已批准）**：
1. 宿主 `reprocess` 接受可选终止戳 payload，重放只到该戳（默认空＝现行为），并记录 `replayed/truncated`。
2. 驱动在开段时先发 `hold`（保持紧急），紧接着发 `snapshot`，使捕获起点固定在触发帧；决策后发
   `reprocess <frozen_at_ns>`，重放区间两端都确定。
3. 实验声明改为**损坏窗口从触发戳开始**（不再提前 4 s），避免损坏帧进入 checkpoint 地图而无法被修复；
   旧 run 与旧声明保留。
4. 重编宿主必须归档新二进制 sha、host diff 与构建日志；随后跑 repair/sham 一对，核对两端一致后再比地图。

## 75. 终止戳宿主改动生效：终点逐位对齐，起点仍随积压漂移（开段快照更差）

S1 复核 S2 `56a73d1`（合入，191 测试）。

| 项 | repair | sham |
|---|---|---|
| `reprocess` | 34 帧 [279.215 .. **280.281185627**] `truncated=451` | 64 帧 [278.215 .. **280.281185627**] `truncated=509` |
| 修复消费 | 7 条 | 12 条 |
| 快照应用 | 触发+2.933 s（frame 252） | 触发+1.934 s（frame 242） |
| 地图 | 17322 voxels | 17283 voxels |

- 宿主改动（本轮唯一）：`reprocessCheckpoint(..., end_stamp_ns)` + payload 解析 + 日志 `replayed/truncated/end_stamp`；
  增量 diff 87 行、完整 `deployed_host_v2.diff` 在干净 `0d2c034` 上可 apply；新库 `liblaser_mapping.so`
  sha **`f27d1730…`**（已在本机核对，`strings` 含 `truncated=`），`fastlivo_mapping` 仍 `0d7e23de…`；
  构建退出码 1 但宿主目标已 `Built target laser_mapping`，失败在无关 target（`BUILD.md` 有记录）。
- 终点对齐成功；**起点仍不一致**：开段 snapshot 走命令通道，积压时落在触发后 1.9–2.9 s，两次差约 1 s。
  S2 的判断成立——本轮"开段立即快照"比滚动快照更差，起点落在触发之后，候选前段没进重放（23 条修复只消费 7/12 条）。

**S1 决定（最后一项宿主改动）**：`hold`/`snapshot` 支持可选应用戳，由宿主在"第一个 `lio_time ≥ 戳` 的组处理之前"
执行；驱动在启动阶段按脚本触发戳预排 `hold <stamp>` 与 `snapshot <stamp>`，撤掉开段 snapshot。
这样 checkpoint 与捕获起点都钉在触发帧，`reprocess <frozen_at_ns>` 钉终点；随后 repair/sham 一对应两端逐位一致。
门/阈值/σ 不动；损坏自注入，不声称真实修复收益。

## 76. 干净 A/B 达成：重放区间两端逐位一致，唯一差别是测量是否被修正

S1 复核 S2 `bec959a`（合入，192 测试；测试已按新语义更新）。

| 项 | repair | sham |
|---|---|---|
| 开段 snapshot（声明戳武装） | stamp `1627785276215170048`、frame 221 | **同一 stamp、同一 frame** |
| 重放区间 | [1627785276.281966925 .. 1627785280.347787857]，`replayed=124` | **逐位相同**，`replayed=124` |
| `end_stamp` | `1627785280381185627` | 相同 |
| 修复 | 发布 23（10/10/3, synced），`repairs applied=23 leftover=0`，shift −0.40 | 发布 23，`applied=23 leftover=0`，shift 0 |
| 偏差估计 | +0.40（MAD 0.05） | +0.40（MAD 0.05） |
| 门 | accepted 3.1388→7.2960，Wilson .8947，23 committed | accepted →7.2986，Wilson .8947，23 |
| `set_state` | 差约 1.1 cm | — |
| 重放后地图 | **17811 voxels / 335054 points** | **17316 / 328516** |

宿主改动（本轮唯一）：`hold`/`snapshot` 可带应用戳，主循环在第一个 `lio_time ≥ 戳` 的组处理前执行；
控制线程只入队并回 `OK <cmd> deferred stamp=…`。增量 diff 203 行、完整 `deployed_host_v3.diff` 1627 行，
均 `git apply --check` 通过；新库 sha **`9c0330be…`**（本机核对），`fastlivo_mapping` 仍 `0d7e23de…`。

**归因（按审阅 5e97501 缩小）**：冻结人口、门、重放区间、修复计数与修复云平移一致，但这只是**一对**
受控对照，不是"其余状态完全相同"：开段 snapshot 本身就有前缀差异（voxels/nodes/points
15905/33641/308821 vs 15902/33624/308223，`state_pos` 差约毫米），且 resume ack 落在不同后继消费边界。
因此可声称：**匹配时间支持的全量测量替换在宿主重估中执行，并观测到地图差异**（17811/335054 vs
17316/328516）；不能把全部 495 voxels/6538 points 与 resume 后状态差断言为唯一由修正造成，也不声称
正确几何或真实修复收益。损坏为自注入，不外推自然故障或成功率。门/阈值/σ 未动。

**声明常量溯源（如实）**：`REPLAY_END_GRACE_NS = 100 ms` 是在观察到"无 grace 时最后一组修复云匹配
不上（22/23）"之后加的；它只加在重放终点、两臂一致，不接触门/阈值。

## 77. 归档收口：v3 部署记录 + 证据链 + SHA 校验；本阶段完成项

S1 复核 S2 `5a86af9`（合入，193 测试）。无新运行。

| 项 | 实际状态 |
|---|---|
| v3 部署记录 | `DEPLOYED_CODE.md` §8：完整 patch `deployed_host_v3.diff` 1627 行 / `46648b4c…ab28`，库 sha `9c0330be…00db`；增量 v1→v2 87 行、v2→v3 203 行，均在各自上一版树上可 apply，v3 完整 patch 在干净 `0d2c034` 上可 apply；明确"可执行文件 `0d7e23de…` 未变、行为在库" |
| 证据链 | `docs/review_20261112_four_host/README.md` §0：11 行 run（含拒绝/丢帧/跨度不一致的几组），每行 run id / 驱动 sha / 库 sha / 损坏声明 / 关键证据 / 能-不能声称 |
| SHA 校验 | 5 个 SHA256SUMS 全部 `sha256sum -c` 通过，0 FAILED（four_host 230 项 + accepted_chain 3 run + native chain_run） |
| 测试 | 客户端测试按新语义统一（开段只发幂等 hold、带戳 payload、`OK … deferred` 作为 receipt），193 通过 |

**本阶段可交付结论**（全部有原件，限制如实）：
1. 受控两事件整链：接受+写回与拒绝+放写各一次，同一 run，终态 HEALTHY（`024337Z`）。
2. 四宿主矩阵：MM-LINS/FAST-LIO2 原生 PASS（前端休眠重建、PGO 保持全局图），LIO-SAM/ORB-SLAM3 原生 FAIL；
   四项 slam_recovery 均 `NOT_IMPLEMENTED`。
3. 实际修复测量进入原生重估：声明注入 0.5 m body-z 损坏 → 偏差估计 +0.40（容差内）→ 分批回执
   23/23 送达并应用 → 重放区间两端逐位一致的 repair/sham 干净 A/B；地图 17811/335054 vs 17316/328516。
4. 边界：损坏自注入，不声称真实修复收益；`commit_closed→resume` 仍不可达；在线自动链仍 BLOCKED 在上游检测。

## 78. repair-f3核088906a：两宿主负尝试原件局部接受，继续余下两项

[审阅](review_20261112_088906a/README.md)接受LIO1120CSV负结果本机复算、ORB rawlog80初始化/0KF/exit139；非LIVO任务已有真实执行，不称宿主恢复成功。两声明实际上运行开始后/分析前，LIO时间窗以首输出非已绑定bagstart，ORB times未归档故window4/6/3仅开发报告。当前支持连续输入两观察窗的失败，不证两独立故障及E1恢复后E2响应；沿已有原件补runner/时钟/事件来源，不新跑矩阵追成功、不猜算法根因。

S2下一交MM-LINS（开发报告运行中）与FAST-LIO2（NOT_STARTED/shared前端范围明示）实际结果或具体命令BLOCKED，S1集成，S3研究/参数暂停不变；两已跑宿主保障并行，不挡余下两项、不回LIVO。逐项自检状态+命令/source/config/input/run/原stamp/尾段/失败证据，NOT_IMPLEMENTED修复层与原生层分列。前push限制已解除并由main接收review1f1527b；本轮review提交推送、private保护，本机无host/bag/tests，不全表升分，接收新意见另待回执。

## 79. repair-f3核f48b23f：四命名项已尝试，下一真实测量接线复用旧组件

[核验](review_20261112_f48b23f/README.md)余下MM/backend与改版frontend各另跑一次、原件15SHA和gap/tail算术一致，单独frontend rawlog两睡眠/两建图；共享实现非共享同一次运行、不是独立原版FAST-LIO2验证。原生re_slam/继续输入存在，不接受开发§66“所有宿主无恢复能力”；四项共同缺的是slam_recovery测量修复接线，LIO/ORB负结果/观察窗限保留，不重跑追成功，matrix不是公平修复收益表。

S1/S2后继有限实际修复范围给真实回执/产物/原生map接回E2或首断点，不机械重回修LIVO全部问题；文档转述选INJECTION不充本会话授权。缺publisher/scan原件身份属已核接口事实，但现有point_mixture_filter和完整记录导出/C3可复用，不能说仓库没有测量修复器或让用户从零选以挡开工。沿旧正常来源/FAIL依赖最低修，累计received不等本次应用stamp；注入标签/原云不得作为部署生产者反演，oracle明确、真实质量缺证据UNAVAILABLE。自检状态/命令/source/input/点人口/applied/native同stamp/E2尾段，S3门旁支参数停不变、不全表评分。本机未跑host/bag/tests/算法，未merge分叉main，只review增量提交推送/private保护，收到新意见待回执。

## 80. repair-f3 / 18baefd增量：测量替换接受，修复失败与E2缺口保留

[核验与最低交接](review_20261112_18baefd/README.md)接受run043602Z_79001的60帧声明损坏、25条修复云received/applied、382group原生重放及内部map/接回，17新列示SHA一致、实际driver SHA匹配目标；在线修复接线不再NOT_IMPLEMENTED。但+0.0029m未消除+0.5m，ICP未收敛、质量/因果未确认；只一触发，无E2，不报首次有效整链完成。常速incumbent是初值不是独立GT，开发“吸收偏差”解释与初值改善预期不当已证定论。

本机8cloud test及有限actual driver/client控制，未代跑host：原坏云+delta pose通过的候选若再施加同delta到测量会重复补偿（identity z1.5→门z1→新云配同pose z.5）；E2累计旧received25、本次0仍synced；full提交后同步失败仍commit_closed→resume；零发布仍reprocess。正成功入口通过，反例不冒充本次归档已发生。S1最低本次人口receipt/成功依赖与共享生命周期集成，S2唯一物理修复/符号/候选一致及native真实完整状态，不灌旧尾；无需新RPC/阈值或全防御矩阵。

下一唯一有限主线：实际去偏→原生状态/map→接回→第二事件/尾段或首断点；自检逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+实际命令/原件/完整人口/失败/质量。四宿主前批尝试不重开，S3门旁支与旧参数暂停不变。7.17ms窗口/kf134/598帧/stale protocol集中旁支更正，不重跑迎合文字；A/B局部推进不全表升分。独立review正常SSH提交推送、分叉main未merge、不改算法/private保护；实际接收及后继运行待开发回执。

## 81. repair-f3 / 2f1f59b增量：估计进展接受，传输与失败接回不当成功

[审阅](review_20261112_2f1f59b/README.md)新37列示SHA一致；incumbent初值run044445门拒绝/未发布/restore-resume，解耦run045238估计median+0.40/MAD0.05、施加−0.40合理，host仅20/26 received、0applied/0reprocess、sync失败仍rearm-resume后发散。两run各一事件，无E2，无独立收益。队列20原patch支持工程解释但drop具体层未独立证，不机械超过20必丢。

S1最低native成功依赖与失败公开一致；S2按已派分批流控复用现通道、本次增量/stamp及实际应用，再保持修复测量/候选/native状态同定义。candidate尾set_state来源局部改进不等原生重估：target实际decide/producer合成反例证明旧坏云门见world0，改新云后同pose world−.5。新估计器无支持0被计入median亦本机确认，但本run26帧全n_valid≥27，不作首因；少支持标UNKNOWN，不扩防御矩阵。11cloud tests通过、无ROS/bag/算法修改；旧累计receipt/可信cp范围未关闭不重复重测。

下一唯一有限实际修复→native完整state/map→接回→E2尾段或首断点；允许真实拒绝/失败，不能为保旧accepted候选绕评价新测量。逐项自检状态/命令/原件/完整人口/独立质量/失败，truth只评价、旧门不降、S3旁支参数停、不重开四宿主矩阵。A/B局部推进不全表评分，正常SSH独立review提交推送、不合main/private保护；实际接收/后继执行待开发回执。

## 82. repair-f3 / 64bfed1增量：分批/人口冻结接受，实际支持不同不报收益

[核验](review_20261112_64bfed1/README.md)四run source绑定、本轮70列示SHA一致，32/32及冻结23/23received/applied、实际native重放/内部map接回接受，旧20/26首断点在这些run局部解除。freeze23个candidate pose stamp全一致，但815vs692group，起点差1.268s/终点5.334s/跨度4.066s，地图不归因；set_state ACK差4.7cm为命令pose，不独立重估质量。deferred87/81/147/148、wait关闭/ABORTED rearm及失败诊断保留，四run各一事件无E2、不报有效整链完成。

本机actual publisher非零baseline/批次停止与tracking冻结PASS，None基线当0时E2旧25/新0仍sync FAIL，最低取得有效本次baseline、不默认为0。新测量/旧坏云candidate及candidate尾灌状态源码未修，S1成功公开/native依赖与同stamp集成、S2物理一致产物/有限native实际修复→接回/E2或断点优先；sham同批次不保证重放支持相同，按实际stamp核、不无限对照循环代主线。自检逐项状态/命令/原件/独立质量/失败，冻结门不降/旧参数停/S3研究、不重开四宿主矩阵。一般文档计数/区间及框架延期，A/B局部推进不全表评分。独立SSH review推送、不合main不改算法/private保护；实际接收待回执。

## 83. repair-f3 / d193680增量：terminal生效但全人口与后缀接回失败

[核验](review_20261112_d193680/README.md)三run59列示SHA一致，旧sham23应用、新terminal两driver绑定target/实际库匹配f27d构建hash；整体build ABI失败不隐去。新两臂candidate pose stamps同、实际终点与payload同，起点差约1s/开段snapshot晚trigger2.933及1.934s；23received但applied7/12、dropped16/11，不能写23/23应用或可信trigger checkpoint。三run无E2，HEALTHY/尾段输入非恢复完成，map差不归因。

新host skip451/509已消费group后仍clear整个replay buffer，source与原件支持接回人口缺口；需保后缀native按序追赶到input边界或显式拒绝，不单为A/B端点对齐删除连续状态输入。S1最低实际应用人口/native成功公开依赖、S2可信完整checkpoint/产物/后缀与接回，按戳arm只是受控开发方案不等自动迟检测。旧物理候选/source来源问题未修不重测，不新RPC/阈值/防御矩阵。下一唯一有限真实修复→native state/map→catch-up→E2尾段或第一接口断点，自检逐项状态/命令/原件/失败未知/质量，S3参数停/研究、不重开四宿主。A/B局部复核不总分，独立review SSH推送、不合main不改算法历史/private保护；实际接收待回执。

## 84. repair-f3 / 用户UNAVAILABLE取证要求：不能再只打印标签

[任务](UNAVAILABLE_DIAGNOSTIC_TASK_20261112.md)由用户2026-11-12直接提出。核最新e82d900现_record_diag仅nis/source/map点数且2000条截断，要求S1复用计算入口：逐帧support比例/分母/失败reason及mask，当前raw与最终effective NIS/旧值来源年龄/参考3m点数/局部面残差/coverage分支，scan/pose/当时参考版本身份；每UNAVAILABLE保存实际采样点/参考及原row mapping，summary全paired流式、不刷全图、不事后用新map造原因。S2现输入/宿主预算检测on有限归因，交代码分支计数/连续段/正常边界与不可用复算或具体BLOCKED；native恢复/E2并行、S3参数停/研究。诊断不得变计算/门值、truth只评分，原件缺项UNKNOWN，自检逐项状态/命令/原件/成本。不升A/B总分，不说任务发布即已执行。新main的v3/A-B运行尚未完整审，不继承旧缺陷为已确认当前失败；本机不改算法/代host，独立review SSH推送/private保护，实际认领待开发回执。

## 85. repair-f3 / e82d900增量：受控完整替换通过，连续接回及诊断待交

[核验](review_20261112_e82d900/README.md)两run41SHA一致/target driver/新库绑定，按戳snapshot时刻frame同、replay两端124group同、23stamp人口及23全应用接受，旧晚cp/部分应用该范围解除。修复前snapshot地图及state不同，不要求随机逐值一致，但单对不能宣称唯一因素/全部map和resume差归因；质量UNKNOWN。v3仍skip+clear后缀399/372、无catch-up，单事件/detection off、尾帧不是E2，deferred ACK非应用且预置仅首脚本戳。S1成功依赖/真实人口、S2物理一致产物及后缀追赶→接回E2或能力断点优先，S3研究/参数停，非无限单事件A/B。

用户诊断任务ddd0fb7晚于target发布，现main无实现不说开发已无视；S1实际认领共享逐帧取证、S2检测on有限分支/样本复算，native并行不调门。逐项自检状态/实际命令/原件/失败/质量/未知，A/B局部推进不总分。本机1receipt test/control无host/bag，独立review SSH推送、不合main不改算法/private保护，实际接收待回执。

## 86. 接收用户新的 UNAVAILABLE 逐帧取证任务（S1 认领共享诊断）

审阅 `5e97501`/`ddd0fb7` 已合入（`8419cbf`）。新任务 `docs/UNAVAILABLE_DIAGNOSTIC_TASK_20261112.md`：
用户直接要求弄清 UNAVAILABLE 的**实际分支原因**，逐帧打印两个指标及其计算相关量；不改检测策略/阈值/模型。

S1 认领的部分（共享诊断，默认不改变计算与决定）：
- 复用现有 `_frame_has_reference_support`（半径 1.0 m / 60% / 200 确定性抽样）与 LiveNis 的计算结果，
  在**同一次**计算里旁路记录：support 的 sampled/within/fraction/pass、实际抽样索引、点级 body/world 坐标
  与原始 row 映射；NIS 的 trusted_total、3 m 内参考数、prev_scan 来源与点数、current/train/query 数、
  sigma、attempted/computed、raw 数值类别（finite/inf/nan/not_computed+reason）、effective NIS 及其
  source（computed/carried_forward/unavailable）与沿用值的来源/年龄；holdout 的 k=8 邻居、面中心/法向、
  残差、(r/σ)²、r<2 m、coverage、all/clipped 分支与均值/rms/分位数。
- 流式写 `availability_frames.jsonl`（每 paired frame 一行），**不受 2000 条 summary 截断**；检测 off 记
  `DISABLED`，不沿用旧 detector 状态冒充本帧判断；status 必须能由 `support_pass` 与 `nis_present` 重算。
- 计算与决定不变（开关前后逐值一致的小控制），不新增阈值/置信层，不把相关点当独立样本做显著性。

S2 的部分：在现有宿主/输入与预算内跑**一次检测 on** 的有限诊断，交每帧原件与原因计数；本次实现完成后再派。

## 87. UNAVAILABLE 逐帧诊断已实现（S1，默认不改变计算/决定）

`c35b162`，202 测试通过。新通道 `--availability-log <path>` → `availability_frames.jsonl`，每 paired frame
一行、无 2000 条上限、逐行 flush：

- **support**（同一次 `_frame_has_reference_support` 计算）：reason（empty_reference/missing_scan/
  missing_pose/invalid_pose/empty_scan/ok）、radius、threshold、sampled/within/fraction/pass、
  query_stride、每个样本的 row/body/world/within_1m；
- **NIS**（同一次 `LiveNis.measure` 计算）：reference source（node_map/prev_scan/none）与 trusted_total、
  3 m 内数、prev_scan 点数、选中参考点数、current/train/query 采样、sigma、attempted/computed、
  raw_kind（finite/inf/nan/not_computed+reason）、effective NIS、source（computed/carried_forward/
  unavailable）、沿用值来源 kf/stamp/age；holdout 的 train/holdout stride、k、coverage、all/clipped
  分支、均值/rms/分位、每点邻居 ID/质心/法向/特征值/残差/卡方/是否 <2 m；
- **身份**：kf、pose/scan stamp、dt、scan frame_id、T_wb、manager state/version/keys/active segment；
  `status_from_conditions` 由两个布尔重算；检测 off 记 `DISABLED`，不沿用旧 detector 状态。
- **采样节省**：UNAVAILABLE 帧保留全部点级样本；AVAILABLE 帧保留声明的前 20 个（记 points_total）。
- **不改变决定**：新增测试跑同一 12 帧，开/关日志对比 diag、detection_counts、records 完全一致；
  另有 support fraction 与布尔一致、carried_forward 的 age/kf、2500 行不截断等测试。

下一步（S2）：用现有宿主/输入跑**一次检测 on** 的有限诊断，交每帧原件与按原因计数；本任务不新开参数/矩阵。

## 88. S3 可用性源码审计：UNAVAILABLE 主要是**支持谓词**结果，不是 NIS 缺失

S1 复核 S3 `4e18de9`（合入）。基准 `eeedb7f`（node hash 5877388c）；源码引用检查 41/41 PASS。
本机重跑 `availability_source_audit.py --scan-tmp` 结果与其归档一致（口径见下）。

| 项 | 实际 |
|---|---|
| 判决式 | `available = bool(supported) and value is not None`（当时 recovery_node.py:1100） |
| 支持侧失败点 | ref 空（377）、scan/pose 缺（383）、pose 非法（386）、scan 空（389）、比例 <60%（200 点、1 m、分母=实际抽点数，392-395） |
| NIS 侧失败点 | 无参考（484-494）、current<10（504）、非有限（507）、无沿用值（517-527） |
| 归档统计（其快照） | 21 个 detection-on run、4128 帧 UNAVAILABLE；**4107 帧 NIS 已算出且有限**；`carried_forward=0`；唯一 21 个例外=每个 run 首帧（ref 空且无 NIS）；空 reference 1656 / 比例不足 2472 / 歧义 0 |
| 一处纠正 | `carried_forward` **单独不会造成 UNAVAILABLE**（value 非 None）；真实问题是支持通过时检测器把旧 NIS 当本帧证据，status 看不出来 |
| E2 窗口（run 3349738） | [42,52] s（各自首帧为原点）83 帧全 UNAVAILABLE、83/83 NIS computed、83/83 prev_scan、map_points 36k–90k ⇒ 分支只能是 60% 比例测试 + 3 m 邻域 <30 点；该窗口 NIS 是 prev_scan 自比较，不是独立证据 |
| 版本关系 | S3 基准早于 S1 的 `c35b162`/`8bbef74`；其"字段审查"对应实现前清单。S1 实现已补 support 比例/分母/mask/点级证据与 NIS raw/沿用/branch 字段（§87） |
| 重跑差异 | 本机重跑时 `/tmp` 多出一个 S2 新 run（`20261112T065500Z`），聚合变为 22 run/4435 帧；**归档 json 绑定其快照**，不以本机重跑数字替换 |

仍 BLOCKED：比例数值、参考快照身份、kf26–64 二次空 reference 原因、与漂移的因果——正是 `--availability-log`
要交的原件。S3 另列了 3 个候选选项（诊断分解/双参考支持/位姿-地图分解），只列未实现，留待用户选择。

## 89. 检测 on 诊断原件：UNAVAILABLE 主导原因是支持比例，不是 NIS 缺失

S1 复核 S2 `040fd24`（合入，203 测试）。run `fl_native_20261112T065500Z_187992`：`--detection on`、
非 scripted、无注入；驱动 sha `93f69356…`（= `c35b162`）、宿主库 `9c0330be…`、bag `c3e905da…`；终态 HEALTHY。

| 项 | 实际（本机从 gz 原件复算） |
|---|---|
| 行数 | **402 = paired 402**，无 2000 截断；`status != status_from_conditions` **0 处** |
| 支持 | `empty_reference` **22**（5.47%）、比例 <0.60 **285**（70.90%）、通过 95（23.63%） |
| NIS | `computed` **401**（99.75%）、`not_computed:no_reference` **1**；`carried_forward` 0；inf/nan 0 |
| 联合 | support F & NIS T 306；F & F 1；T & T 95 |
| 连续段 | 0–21（22）、53–117（65）、118–156（39）、157–170（14）、171–179（9）、180–182（3）、183–198（16）、199–401（203）；早期两段合计 87 帧 |
| 复算（反例） | kf53：200 抽样、within 39 → 0.195，NIS 300/300、mean χ² 10.156722 = 报告；kf157：63/200 → 0.315、NIS 403.642606、valid 23/300、coverage 0.077；两者 status 重算 UNAVAILABLE |
| 复算（正常） | kf22 只保存 20/200 与 20/300，子样本复算 0.75 vs 0.88、0.889 vs 18.281 —— 任务允许的固定预算缺项，已记录 |

**结论**：本段 UNAVAILABLE 是**支持谓词比例不足**（285/307），不是 NIS 缺失（401/402 有有限 NIS，含 prev_scan）。
`carried_forward`、缺 pose/scan 两类分支本 run **NOT_EXERCISED**；精确最近距离诊断 **NOT_EXECUTED**
（不把首个命中距离当全局最近）；比例为何持续 <0.60 **UNKNOWN**，不从 unsupported 推漂移。
检测/阈值/门/模型未改。

**版本说明**：S2 运行时 `reason` 字段把"已评估但未过阈值"也写成 `ok`；S1 随后（`8d6e4ed`）改为
`fraction_below_threshold` 并加测试，原件仍按 pass=false 计数，语义不受影响。

## 90. 用户选中"位姿-地图分解"；每帧支持比例增加预测位姿对照（S1 已实现）

依据 §89：UNAVAILABLE 主导原因是支持比例不足（285/307），而 NIS 401/402 都算出了有限值。
两种解释：宿主位姿已偏离冻结的可信地图，或参考地图不覆盖该扫描。

实现（`90029ab`，205 测试）：availability 行新增 `support_under_predicted_pose`——用可信位姿序列最后两帧
做匀速外推（平移；旋转取最后位姿）得到的位姿，对同一帧、同一参考再做一次**完全相同的**支持评估并记录
reason/fraction/pass 与点级证据。只写诊断，不进入任何决定；有外推与字段测试，决定不变测试仍通过。

判读规则（运行前声明）：
- 预测位姿下 fraction 明显恢复（越过 0.60 或显著高于宿主位姿），说明**位姿漂移**；
- 两种位姿下都低，说明**参考地图覆盖不足/过期**，与位姿无关；
- **预测语义（审阅 4740d94 纠正）**：`_predicted_pose` 用最后两帧位置差/时间差外推、旋转取最新值；**没有外推时间上限**，且只有一帧 trusted 时返回最后位姿（不是 null，预测位姿不可用为 null 的说法不适用于 1 帧情形）。因此判读只能说"同帧同参考下支持对位姿敏感"，不能称漂移量；记录需带基准 key/时间/速度/horizon。

下一步（S2）：用同一输入再跑**一次**检测 on 的有限诊断，交按上述二分的原因计数与连续段；不改检测/阈值/门。

## 91. 位姿-地图分解结果：两套位姿都低是主体（301/480），短时预测只救回 50 帧

S1 复核 S2 `ab51d60`（合入，205 测试）。run `fl_native_20261112T070801Z_197026`：同 bag、检测 on、
非 scripted、无注入、`AVAILABILITY=1`；本 run paired 544（上一 run 402，人口随负载变化）。

| 项 | 实际（本机从 gz 复算） |
|---|---|
| 形状 | **544 行 = paired 544**；`support_under_predicted_pose` 非空 **480（88.2%）**，null 64（0–20、23–65，trusted_poses 空，按规则不判读） |
| 联合计数（480） | **both_low 301**、both_pass 82、only_host_low 50、only_pred_low 47 |
| 状态 | UNAVAILABLE 412 / AVAILABLE 132 |
| 分段 | 预测位姿救回：147–173（host 0.025→pred 0.48）、228–280（0.025→0.515）、396–462（0.0→0.505），共 50 帧过阈值；两套都低：26–86、179–191、298–368、373–394、520–543 等，共 301 帧 |
| 跨 run 对照 | 上一 run 的 53–117 戳段在本 run 有 37/65 帧 AVAILABLE（host 中位 0.75）；本 run 199–401 段 host 中位 0.12、pred 0.185——**同一输入时间线的可用性依赖该 run 当时的地图状态**，行索引不可跨 run 套用 |

**判读（按预先声明的规则，并收窄）**：50 帧仅宿主席不达标、预测位姿达标 ⇒ **短时位姿漂移**可解释；
301 帧两套位姿都不达标 ⇒ **不能用短时预测位姿解释**，指向参考覆盖（或预测本身失效），**根因仍 UNKNOWN**，
不能据此宣布"参考覆盖不足即为唯一原因"。47 帧预测反而更低，不判为漂移（可能外推失效）。
AVAILABLE 132 的构成（审阅 4740d94 纠正，本机复算一致）：82 both_pass + 47 only_pred_low（预测失败但宿主席通过）+ 3 无预测但宿主席通过 = 132；host 支持通过总数恰好 132。**此前写成"82 与 132 的差是 NIS 门"是错的**——480 个有预测帧的 `nis_present` 全为真，差异来自 only_pred_low 与无预测帧。

检测/阈值/门/模型未改；分解只写诊断。S3 早前列的选项（双参考支持 / 位姿-地图分解 / 诊断分解）中，
分解已完成；若要继续查 both_low 的 301 帧，下一步应做**双参考支持**（restore 前快照 vs 当前可信地图）。

## 92. 用户暂停可用性诊断；选项页已整理，转回原生主线

按用户 2026-11-12 决定：暂停继续跑可用性诊断，先把证据与候选整理成 `docs/AVAILABILITY_OPTIONS_20261112.md`
（A 诊断分解已完成、B 双参考支持、C 位姿-地图分解已完成；三条结构方向保持现状/参考刷新/门结构变更）。
本页不实现、不改门/阈值/检测，交用户选。

已确认事实：UNAVAILABLE 是支持谓词结果（4107/4128 有有限 NIS）；诊断 run 比例<0.60 占 285/307；
分解 run `both_low 301 / only_host_low 50 / only_pred_low 47 / both_pass 82 / null 64`；同输入不同 run 可用性不同。
根因仍 UNKNOWN，不做因果外推。

主线回到原生：下一步按审阅 §3 的首断点——**被截断的已消费后缀在 restore 后没有被重推**（`truncated=399/372`），
S2 做最小修（重放覆盖全部捕获组，或显式拒绝回溯并声明不支持），然后再谈 E2。

## 93. S3 复核选项页：事实 5 方向纠正、both_low 收窄；原件报告同步注记

S1 复核 S3 `e9a809c`（合入）。本机独立复算确认其纠正：

| 项 | 实际 |
|---|---|
| 事实 5（原写反） | 上一 run（402 帧）行 53–117 **65/65 UNAVAILABLE**；本 run（544 帧）**同戳窗口 37/65 AVAILABLE**（本机按 pose_stamp 映射复算一致） |
| 事实 2 补充 | 21 个检测 on run / 15 个源哈希；4107/4128 的 21 个例外正是每 run 首帧（空参考且无 NIS），避免读成"所有 UNAVAILABLE 都有 NIS" |
| 事实 6 补充 | `map_points` 36 354–90 809 非空 ⇒ 只能是 60% 比例分支；`prev_scan` 意味着 3 m 内 <30 trusted 点；E2 run 未入库，按 sha256 绑定 |
| 选项 B 收窄 | "两条都低 ⇒ 覆盖确实不足"改为"只排除当前地图单独冻结，不能区分覆盖不足/几何退化/两套位姿都错" |
| §5 口径 | "70–90%"改为分支计数：旧归档 2472/4128≈60%、诊断 run 285/307≈92.8%，其余空参考 |
| NIS 可比性 | UNAVAILABLE 多用 prev_scan、AVAILABLE 用 node_map，数值不可直接比；被排除的异常证据强度 UNKNOWN |

同步修正原件口径：`review_20261112_availability/predicted_pose/REPORT.md` 顶部加 S1 注记（数字不变，
both_low 只说明短时预测解释不了，147 帧里仅 50 帧预测位姿通过）。可用性继续暂停；原生后缀 catch-up 由 S2 进行中。

## 94. 后缀重推成功（v4）：572 帧全部重放，state/map 追到边界；新断点 set_state 回拨 15 s

S1 复核 S2 `f696059`/`c02526d`（合入）。宿主 v4：增量 67 行、完整 `deployed_host_v4.diff` 1625 行、
新库 sha **`c0833d9f…`**（本机核对）；`reprocess` 不再截断重放，`end_stamp` 只限制修复云匹配。

run `fl_native_20261112T072902Z_207524`（同声明）：
- `reprocess #1: 572 frames … replayed_within_end=124 replayed_suffix=448`，区间 [276.281966925 .. 295.292295218]（比截断版多 14.94 s）；
- `repairs applied=23 queued=0 leftover 0`；地图 **21257 voxels/379069 points**（截断版 17811/335054）；
- reprocess ack `state_pos=3.167535,6.145446,-0.110570` = 边界状态；**随后 `set_state` 写回候选末帧
  `7.050962,5.921306,-0.446735`（280.28，差约 3.9 m / 15 s），而地图停在 295.29** ⇒ 状态与地图不同步。

结论：审阅 §3 的"已消费后缀重推"断点**已解除**（448 帧后缀按序重推）；新断点是**set_state 在全量重放后回拨**。
最小修法（S1 决定并派工）：宿主在 reprocess ack 暴露 `replay_suffix=`（日志已有），驱动在后缀 >0 时**跳过 set_state**；
约 10 行宿主 + 10 行驱动 + 单测，再跑一次同声明受控 run 验证 resume 时 state/map 同一时刻。
门/阈值/σ 未动；可用性诊断保持暂停。

## 95. repair-f3 / 70531be增量：诊断分支接受，参考几何因果及修复E2未闭合

[核验](review_20261112_70531be/README.md)S1实现/S2检测on065500Z新原件13SHA一致，402paired全行一致、95可用/307不可用；22参考空+285比例不足，401新算finiteNIS/1无NIS，carried/nonfinite0。306有NIS且support失败包括21空参考，不是306比例不足，后继更正REPORT§6不重跑。kf157 support.315/NIS403.6426前置排除真实，mask/残差内部复算接受，但reference/cache坐标身份未存/KNN不可独立重建/正常边界裁20点不可全复算；post-cap row非原row，target正常反例12原点cap4写0/1/2/3实际0/3/6/9，最低复用finite/stride映射。

三次真实online拒绝/restore/resume和后继重武装接受，实际repair off/0commit/reprocess/applied、14snapshot超时、HEALTHY/wiring非恢复成功；有后两事件路径但无首次修复，不补用户repair后E2。历史87不同身份不合并；S3/tmp跨版本统计仅开发分析。本机12帧9不可用/3可用target/base/log输出与trusted状态同、8test PASS.043s、Git Bash语法PASS，无host/bag/算法参数；pytest辅助两项未跑不装。A3/B3局部取证进步不总分。

S1可并行最小补当时reference/cache身份与必要坐标、原row和少数完整正常边界，S2下一已有预算run随附或具体缺项，不新起诊断矩阵/事后造旧参考；只挡诊断强因果，不把日志挡全部native。S1/S2唯一主线继续物理一致修复→native完整state/map→保后缀追赶→接回/E2或首断点；已验23替换复用、v3后缀/成功依赖未改不重测。S3回既定门研究专用/旧参数停，选项不自动实施；逐项自检状态/实际命令/原件/失败/成本/质量UNKNOWN，不调冻结门。独立review SSH提交推送、不合main不改算法旧历史/private保护，开发新意见接收另待回执。

## 96. repair-f3 / 4740d94增量：预测支持不是独立因果标签，开放终态如实保留

[核验](review_20261112_4740d94/README.md)070801Z新run14SHA/gz/raw及target driver绑定，544paired/480预测完整mask通过；61空参考+351比例不足、132可用/412不可用，301双方低/82双方过/50仅host低/47仅pred低/null64。132=82+47+3无预测host过，不是NIS差；REPORT HEALTHY与三原件WAITING_FOR_EVIDENCE/open=true相反，8拒绝/restore8/resume7/reprocess0真实保留，未修复/E2。预测提高只证明support敏感性，不唯一证明漂移，两者都低不能排除共源pose/外推失效；147段长仅50跨门，分段null/有效人口和191/54标签需集中更正，不为文字重跑。

source预测无horizon界/一trusted返回last非null，kf21原件及actual-method控制确认；最低记录已有key/戳/预测T/horizon、同次reference/cache与原row，旧缺项未修不重测，不先加预测器/阈值。12帧9不可用/3可用base/target/log输出同，全部package Git bytes加载、-I archive reader无host/bag，pytest辅助新test未跑不安装。跨run人口不同不唯一归因负载；S3旧/tmp统计不新同版本证据。仓库“用户选中”仅开发转述无本机直接选择证据，不自动批准双参考或部署替代策略。

S1/S2唯一主线继续物理一致实际修复→native完整state/map→保后缀catch-up→接回/E2或首断点，已验替换复用，v3后缀/成功依赖未改；诊断补元数据/真实分母与因果限定可并行只挡强诊断主张，不继续日志矩阵代native。S3回既定门A/B/C研究专用、旧参数停；自检逐项状态/命令/原件/失败/成本/质量UNKNOWN，A3/B3局部观察不总分。独立review SSH提交推送、不合main不改算法历史/冻结门/private保护；target早于fe56883发布不指控忽略，新意见接收待实际回执。

## 97. set_state 回拨修复（v5）：后缀重放后不再写回旧位姿，state/map 同边界

S1 复核 S2 `cbbdeda`（合入，206 测试）。宿主 v5：`checkpointStatus()` 暴露 `replay_within_end/replay_suffix`
（取上次重放计数，不新算；缓冲 512→768）；增量 49 行、完整 `deployed_host_v5.diff` 1632 行，均 apply 通过；
新库 sha **`9e7d8cdf…`**（本机核对），可执行文件仍 `0d7e23de…`。

驱动：reprocess 后等待 ack（≤90 s），解析 `replay_suffix`；**>0 跳过 `set_state`** 并记
`native_writeback_skipped={reason:"replay_suffix",replay_suffix:N}`；ack 缺失/无字段同样不盲写，记 null；=0 保持原行为。

run `fl_native_20261112T074154Z_215075`（同声明）：

| 项 | 实际 |
|---|---|
| reprocess | 454 帧 [276.281966925 .. 291.358868361]，`replayed_within_end=124 replayed_suffix=330`，`repairs applied=23 leftover 0` |
| 地图 | 20625 voxels / 380221 points |
| 命令 | `native_checkpoint_events` 只有 reprocess 与 resume（**无 set_state**） |
| 状态 | reprocess ack `5.796264,7.677180,0.181549`；resume ack `5.761748,7.652826,0.182390`，差约 **3.6 cm**（上一版 3.9 m / 15 s 回拨消失） |
| 终态 | HEALTHY、`quarantine_open_at_exit=false` |

边界：后缀数随负载变化（本 run 330 vs 上一 run 448），但 `within_end` 124、修复 23/23 不变；
门/阈值/σ 未动；可用性诊断暂停；损坏自注入，不声称修复收益。
诊断侧同轮更新（§98）：预测基准/参考身份/边界帧全样本。

## 98. 诊断按审阅收窄并补齐：预测基准、参考身份、边界帧样本

审阅 `4740d94` 指出两处真实错误与三处缺项，S1 已修：

1. **§91 的 AVAILABLE 构成写错**：实为 82 both_pass + 47 only_pred_low + 3 无预测但宿主席通过 = **132**；
   此前"82 与 132 的差是 NIS 门"不成立（480 个有预测帧 `nis_present` 全真）。
2. **`predicted_pose/REPORT.md` 终态写错**：原件为 **WAITING_FOR_EVIDENCE、open=true、resume 7/8**，
   报告原写 HEALTHY，已按 receipt/run_summary/lifecycle 更正。
3. **预测语义收窄**：`_predicted_pose` 是最后两帧位置差/时间差外推、旋转取最新、**无时间上限**；
   仅 1 帧 trusted 时返回最后位姿（不是 null）。判读只能说"同帧同参考下支持对位姿敏感"。
4. **补齐记录**（`90c95b5`）：`prediction` 块（mode last_pose/velocity、基准 key/stamp、速度、horizon、
   16 维 predicted_T）；`reference` 块（cache_key[version,nposes]、refresh_ns、点数、sha256——每次刷新算一次，
   不是每帧）；`boundary` 帧（与前一帧状态不同）保留全部点级样本；参考 hash 与点数随行保存。
5. 未改预测器本身、未加新阈值/防御；下一轮诊断如需再跑，由用户决定（当前暂停）。

## 99. 主线达成（受控+注入）：同一实例"修复写回 → 接回 → 第二事件 → 尾段"

S1 复核 S2 `b2efe95`（合入，206 测试）。run `two_event_v5_20261112`，宿主 v5（库 `9e7d8cdf…`，本机核对），
驱动 `0a38e952…`；损坏只在第一窗口（触发 1 起 6 s）。

| 项 | 事件 1 | 事件 2 |
|---|---|---|
| 触发 | `1627785276215170145`（kf 146） | `1627785308048271418`（kf 422） |
| 决策 | +4.27 s | 312.255 |
| 门 | **Mode 2 accepted**：3.1388→7.3114，Wilson .8947，committed 23 | **Mode 3 refused**：22.064→18.216（Wilson .8954 本身过线，信息增益不过 2×） |
| 原生 | hold → 发布 23（synced）→ reprocess 497 帧 [276.282..292.826]（within 124 / **suffix 373**，repairs 23，leftover 0）→ **无 set_state**（suffix>0 跳过）→ 关闭 289.417 → rearm → resume | hold → restore（ckpt `1627785309656085248` frame 863）→ resume |
| 关闭 | wait_limit_closed → rearm v102 | wait_limit_closed → rearm v246 |

- 触发 1→2 **276 帧**；第一次关闭→触发 2 **186 帧**；触发 2→bag 末 **122 帧**；`candidates.jsonl` **2 行**；
  `lifecycle.events` **4 条**；终态 **HEALTHY**、`open=false`；holds 3 / resumes 2 / restores 1 / reprocesses 1。
- **新发现（如实）**：第二事件 restore 使用的 checkpoint 戳 `309.656` 晚于第二触发 `308.048` **1.6 s**
  （滚动 snapshot 命令在触发前发出、宿主积压后于触发后才应用）——回滚只到 segment 内 1.6 s 处，
  不是完整回退；这正是审阅多轮保留的"checkpoint 不晚于可信隔离边界"断点。
- 边界：预排武装 hold/snapshot 只针对 `min(stamps)`，第二事件走滚动 checkpoint；门/阈值/σ 未动；
  可用性诊断暂停；损坏自注入，不声称真实修复收益或恢复成功率。

## 100. 武装 checkpoint 修复成立：第二段 restore 戳早于触发 58 ns；但第二段尾部差 0.47 s

S1 复核 S2 `8b378b6`（合入，209 测试）。驱动改动：开段先 `expire_pending(0.0)` 再发幂等 hold（pending 快照记
superseded）；**每个 scripted 戳各预排一次** `hold <stamp>`+`snapshot <stamp>`；**scripted run 关闭滚动快照**
（根因：滚动快照在触发前发出、触发后才应用，会覆盖武装 checkpoint；上一 run 的 308.590 即此）。

run `fl_native_20261112T080204Z_228057`：

| 项 | 实际（本机核对） |
|---|---|
| 武装快照 | `snapshots=2`，无滚动快照；第一段 reprocess/resume ack stamp `1627785276215170048` |
| **第二段 restore** | `stamp_ns=1627785308048271360`，比触发 `1627785308048271418` **早 58 ns** —— 目标成立 |
| 第一段 | Mode 2 accepted（after 7.3024，Wilson .8947）、`repairs applied=23`、within 124 / suffix 313、地图 20154/375577、**无 set_state**、close→rearm→resume |
| 第二段 | 触发 308.048、决策 312.25、Mode 3 拒绝、restore 用武装 checkpoint；`wait_offset=7.335 s` ⇒ 关闭应在 **321.383**，bag 最后帧 **320.909**，**差 474 ms**；退出 `WAITING_FOR_EVIDENCE / open=true` |
| 结论 | checkpoint 目标成立；两项目标（restore 戳 + 第二段完整关闭）**未在同一 run 同时成立** |

可用最晚戳：关闭 = 触发 + margin 4 + wait_offset 7.335 + wait 2 = 触发 + 13.335 s ≤ 320.909 ⇒ 触发 ≤ 307.574。
考虑尾部余量，S1 要求 S2 用 **≤306.4 s 的戳**（关闭后至少约 10 帧尾段）再跑一次；不重制 bag、不改门/阈值。

## 101. 主线整链在同一实例内完整成立（受控 + 声明注入）：写回→接回→第二事件关闭/rearm→尾段

S1 复核 S2 `b201f25`（合入，209 测试）。run `two_event_final_20261112`，宿主 v5 库 `9e7d8cdf…`（本机核对）。

| 项 | 实际（本机核对） |
|---|---|
| 声明/命中 | 两戳 `1627785276215170145`、`1627785306371636152`（kf 405，306.3716 s），`declared_ns` 与 `fired ts_ns` **逐位一致** |
| 事件 1 | Mode 2 **accepted**（3.1388→7.3001，Wilson .8947）；`repairs applied=23`；reprocess 503 帧 [276.282..293.026]（**within 124 / suffix 379**）；地图 21578 voxels/403642 points；**无 set_state**；close 289.149 → rearm → resume |
| 事件 2 | Mode 3 **拒绝**（22.064→19.616）；restore stamp `1627785306303834368` **早于触发 67.8 ms**；close **316.258** → rearm v232 → resume(`trigger=rearm`) |
| 快照 | `snapshots=2`（只有两次武装快照），`superseded=0` |
| 尾段 | 关闭→bag 末 **39 帧 / 4.65 s** |
| 终态 | **HEALTHY、`open=false`**；`lifecycle.events` 4 条；`candidates.jsonl` 2 行；holds 4 / resumes 2 / restores 1 / reprocesses 1 |
| 尾部预算 | 本 run 第二段 `wait_offset=1.284 s`（上一 run 7.335 s），提前的戳留出余量，"差 0.47 s"未复现 |

**这是主线目标的完整受控证据**：同一实例内实际修复测量进入宿主重放（23/23）、状态与地图停在重放边界、
接回后第二事件开段→决策→关闭→rearm→resume、尾段保留、终态 HEALTHY。

**边界（不得越过）**：损坏为自注入（INJECTION），不声称真实自然故障的修复收益或恢复成功率；门/阈值/σ 未动；
detection off（受控接口测试），不是自动检测链；可用性诊断仍暂停；`commit_closed→resume` 仍不可达（partial 接纳）。

## 102. 归档收口：v1→v5 版本链、终点 run、全仓 SHA 校验 0 失败

S1 复核 S2 `6faa695`（合入，209 测试），无新运行，宿主运行保持冻结。

| 项 | 实际 |
|---|---|
| 版本链（`DEPLOYED_CODE.md` §9） | v1 1501 行/`b12ae153…`/库 `0eacffe1`；v2 1528/`2ffc5f6e`/`f27d1730`；v3 1627/`46648b4c`/`9c0330be`；v4 1625/`f025329c`/`c0833d9f`；v5 1632/`e444adac`/`9e7d8cdf`；每版列出"解决的断点/当时仍缺" |
| 驱动侧收尾单列 | 开段先 expire 再 hold、每戳预演武装、scripted 关滚动、终止戳 +100 ms grace、`replay_suffix>0` 跳过写回 |
| 终点 run | `two_event_final_20261112`（`080914Z_233068`）标为断点链终点；更早 run（拒绝/丢帧/跨度不一致/尾部不足）全部保留 |
| SHA 校验 | 全仓 7 个 SHA256SUMS 全部通过，**0 失败** |
| 未闭合项 | 已写入 `review_20261112_four_host/README.md`：真实自然故障修复（现为注入）、自动检测链（UNAVAILABLE 暂停/根因 UNKNOWN）、`commit_closed→resume`（partial，wait+rearm 放写）、第二事件武装 checkpoint 仅声明戳、无 GT 质量评价 |

**本轮主线完成项**（可引用的实际证据）：
1. 受控 + 声明注入的同一实例整链：修复测量进入原生重放（23/23）→ 状态/地图停在重放边界 → 接回 →
   第二事件关闭/rearm/resume → 尾段 39 帧 → 终态 HEALTHY；
2. 四宿主第二事件矩阵各一次实际运行（MM-LINS/FAST-LIO2 原生 PASS，LIO-SAM/ORB 原生 FAIL；修复链均 NOT_IMPLEMENTED）；
3. 纯位姿修正不改变 body 点云、修复传输/门控/回执/串行化/终止戳/后缀重推/set_state 回拨等断点的逐项解除；
4. UNAVAILABLE 取证与选项页（暂停，待用户选）。

## 103. 用户选"独立参考诊断"；工具已实现，S2 跑干净地图 pass

既有原件补充分析（无新运行，写入选项页 §7）：隔离期可信地图确实冻结（6 个 QUARANTINED 段
`trusted_keyframes` 首末不变；全 run 增长转换几乎都在 HEALTHY），但 **HEALTHY 状态 166 帧里 152 帧仍
UNAVAILABLE**（fraction 中位 0.09）——支持失败不是隔离期独有，更像宿主位姿与可信地图不一致；
短时预测只救回 50 帧。根因仍 UNKNOWN。

按用户选择实现独立参考工具（`f2befe9`，215 测试）：
- `slam_recovery/validation/independent_reference.py`：读 PCD（binary/ascii）→ 用 availability 行保存的
  body 样本 + `T_wb` 对**另一 run 的地图**做同一 1 m/60% 支持测试；可选 ICP 对齐（种子=宿主位姿），
  报告对齐修正量、对齐后 fraction、both_low / host_low_independent_pass 计数；
- 测试：带 intensity 字段的二值 PCD、both_low 与反转结果、trimmed 行、gzip、known-offset ICP 恢复；
- 边界：独立地图仍来自同一传感器/宿主，若两图同向漂移，both_low 仍不能完全分离覆盖与位姿。

已派 S2：同 bag、detection off、无注入、无 scripted、开 `pcd_save_en`（用副本 config 并记 sha）跑一次
干净地图 pass，归档 PCD/receipt/config sha；S1 随后离线评分现有 544 行并交分段落结论。

## 104. repair-f3 / c416a68增量：448后缀原生重推通过，set_state实际覆盖边界状态仍FAIL

[核验](review_20261112_c416a68/README.md)新072902Z原件本轮23SHA一致、driver未变target绑定/库c0833d9f匹配build声明；572group=124within+448suffix通过原生IMU/mapping，map21257/379069、23received/applied/leftover0，旧skip+clear捕获后缀断点本范围解除。572含286LIO（226有点/60空）及286VIO，不冒全非空scan/全state等价。实际reprocess边界state[3.167535,6.145446,-.110570]之后仍set_state写candidate key161@280.281的[7.050962,5.921306,-.446735]，重放末295.292晚15.0111s，两ACK差3.904389m且map计数同，旧来源问题实跑确认，不瞬时GT误差。

S1已决定派ACK suffix/driver跳旧pose但target未实施；下一最小保native完整重估边界和成功依赖→接回→修复后E2尾段或首断点，不复制pose/newRPC/阈值扩展。59shift仅23发布、36未修含最后修复后18，suffix原始测量非干净；单scripted/detection off/E2未跑，HEALTHY经waitclose/ABORTED，snapshot8超时/整体build ABI失败保留。S2后缀真实成果接受，不重复v3控制，旧物理候选与成功来源保范围。

诊断选项收窄/方向更正可并行，开发声明暂停及“用户选”仅转述，本机无新直接指令不批准双参考；S3维持门研究专用/旧参数停，不无限诊断代native。-I原件reader最终exit0，初逗号解析失败仅修自写reader，无host/bag/algorithm；driver未变不重跑旧tests。A5/A6/A10局部推进不全表评分，自检逐项状态/命令/原件/人口/失败/质量/成本UNKNOWN；独立review SSH提交推送/private保护不合main不改历史冻结门，target早于d442793发布不指控忽略，接收新意见待回执。

## 105. repair-f3 / 70e3e7c增量：受控实际修复后E2已执行，可信回退/未知依赖仍FAIL

[核验](review_20261112_70e3e7c/README.md)两v5新run40SHA一致、实际driver e39b2b8/0a38e952非随后诊断target c33c0094、库9e7d8cdf绑定build。074154Z真实23应用/454=124+330suffix/无set_state，ACK差实际4.225cm；074744Z E1修复23/.40→原生497=124+373suffix/map20838/379892→无旧pose灌回/resume边界XYZ同→E2拒绝restore/resume→关闭后17paired/1.725149s。首次实际修复后同实例受控E2执行已即时单报用户，不抹执行也不称全部验收成功。

E2无注入/detection off、滚动cp晚trigger1.607814s/晚隔离起点5.607814s，可信完整回退未过；真实两ABORTED rearm/未解决106,143/59shift仅23修复保人口。新collect None/FAILED ack仍实际target decide发送set_state，与“缺ACK不盲写”不符；成功suffix正例skip已通过，普通未知失败依赖最低停尾命令/不公开成功，不扩防御矩阵/newRPC。S1共享成功依赖/物理一致，S2合法历史cp及input归宿→接回/E2或显式不支持，复用已验后缀/skip，不无限单事件。

诊断最新补reference缓存元数据/预测基准/正常边界全样本只源码组件，未新on运行、参考坐标/raw行仍缺；用户本轮问UNAVAILABLE如何解决，已明确答：分支定位已完成，支持门/处理策略未改、物理根因未知，非已修。不自选方法/调门，S3既定研究参数停。-I archive及target Git bytes方法控制PASS/FAIL反例如实，无host/bag；pytest辅助新tests未跑不装。A/B局部进步不总分、自检状态/命令/原件/实际版本/全人口/失败未知/质量成本，review白名单SSH推送补012899f/private保护不合main不改历史，接收新意见待回执。

## 106. repair-f3 / 用户授权ALI-H v1设计与有限隔离测试（2026-11-12）

用户直接要求“设计一版，并行接着做自动审阅，设计好通过GitHub给开发侧测试”。[ALI-H v1](ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md)已设计：低支持/弱信息与健康观察分开，NORMAL_CONSISTENT/SUSPECT/UNKNOWN加scope；M地图/T邻帧/I真实preupdate运动冲突按来源和旧support上下文条件校准，预测不当正常独立证据、默认LOSO/sync/零bias不充观测，缺项/校准外/carried保持UNKNOWN。不改旧1m/60%、sigma/κ和准入门；新0.5s块/.95/.80/20块是一次冻结探索配置，不扫描追成绩、非有效概率。

本次直接授权仅此方法隔离实现/有限测试，先shadow不改变旧检测/manager/native，生产部署另需用户确认，不扩双参考/数据宿主矩阵或恢复旧参数任务。本机只设计/审阅；S3保持唯一研究角色，在已有门研究时段安排并回实际预算/branch/认领；S1共享接口单写、S2继续native，先复用已有402/544行原件和必要最小synthetic控制，有明确缺项才复用原生trace或至多一次预算内有限导出。完整人口/标签/误报漏检延迟/弃权/资源与负结果，缺I或健康低支持参照明确UNKNOWN，不把改名当解决。

20min/2h/日报actual owner repair-f3保持、未新增任务；新main5f54a44的armed/final原生E2独立并行核验，不凭完成标题验收。方案DESIGNED/NOT_IMPLEMENTED/NOT_EXECUTED，S1/S3实际接收待回执，发布不冒运行；A3/B3计划非新评分。SSH独立review提交推送/private保护不合main不改历史冻结门。

## 107. repair-f3 / 5f54a44原生增量：双事件尾段接受，检查点需对齐隔离起点而非仅trigger

[核验](review_20261112_5f54a44_native/README.md)新armed/final34原件SHA一致、341全manifest完整性核；实际b1bce5e driver与target四changed entry AST一致，整source不同诊断merge不冒最新全实跑。armed修复23/437=124+313suffix/无set_state但E2未close/resume/open；final修复23/503=124+379suffix/map21578/403642/无set_state→接回→E2拒绝restore/close/ABORTED rearm/resume→39paired/4.65064s尾段，受控执行接受，不自动恢复/GT收益或全部状态等价。

实际cp晚隔离起点：两E1约4s，armed E2 3.999999942s，final E2 3.932198216s，早trigger67.8ms只解除晚trigger范围；最低实际应用历史cp不晚quarantine_start并保input归宿，或明确拒绝回溯不支持，不调margin/重新框架/无限移E2戳。旧collect未知失败写回/物理候选仍未改不重测，59shift仅23修/未解101,138保人口。总结final before20.3222非22.064/Wilson0、superseded0非1等集中更正不重跑。

S1共享成功依赖/可信边界、S2下一合法历史恢复→完整接回后继尾段或能力断点；S3按新用户ALI-H v1有限shadow研究授权且旧参数停、既有研究预算顺序回执，native不等研究。availability旧state交叉不真值/唯一pose因果，论文受控限定保留。-I reader/source控制PASS，早reader断言只修辅助，无host/bag，build目标成功整体ABI失败不抹。实际automation owner无双写，16:29DNS失败不冒remote latest，A/B局部不总分、自检状态/命令/原件/人口/失败/质量成本UNKNOWN，review SSH推送/private保护不合main不改算法历史冻结门，接收新意见待回执。

## 108. repair-f3 / 26ba3a3与两小时总结：独立参考仅研究组件，真实主线部分推进

[核验](review_20261112_26ba3a3/README.md)新PCD/独立支持工具5相关test target Git bytes PASS，Scipy ICP未跑不装；target无新PCD/receipt/评分运行。正常pose不变只换参考fraction0→1不证明pose错；裁20/200保存点fraction1/真全样本.1仍入主both_pass，最低完整分母/partial单列、中性解释与现prefix gauge/共同支持，不能每帧ICP自拟合冒独立评价。ASCII COUNT兼容候选不声明binary input主阻断。S1§103派S2clean pass仅开发转述认领/用户选，本机无新直接选择不扩授权；ALI-H v1用户已直接授权隔离shadow研究b7ad580优先，实际接收待回执，S3唯一研究角色不占S2整轮诊断。

14:37–16:37结论部分推进：后缀真实重推/成功skip旧pose/修复后同实例E2与39尾帧原生证据接受，不日志或test数；首工程cp晚隔离起点及UNKNOWN/FAIL依赖仍未过，算法/评价物理候选/全损坏人口/独立净收益未知，参数无同版本同人口规律/上限证据可解、旧sigma/κ/floor停。目标库运行/整体ABI测试失败次要；DNS恢复fetch最新26ba3a3，不猜远端停工。S1成功依赖/共享集成、S2合法历史cp/完整input归宿→实际修复接回后继尾段或显式不支持，复用已验suffix/skip不扩框架；S3既定研究/native不等。自检状态/命令/原件/全人口/失败/质量成本UNKNOWN，A/B局部不总分，只新评价增量提交SSH不重复2h空报告/private保护不合main不改算法历史冻结门。

## 110. 独立参考工具按审阅收窄；干净地图 pass 已在本机产出 PCD（待 S2 归档）

审阅 `26ba3a3`（合入）两点已修：
1. **命名不归因**：`host_low_new_reference_pass` 只说明"同 body 点、同 T_wb 在新参考里命中、在旧参考里不命中"，
   `summarise.reading` 明确 cause UNKNOWN；per-frame ICP 标为 **fitted compatibility**，不当未拟合判决。
2. **裁样本不进主表**：`summarise` 主计数只用完整抽样帧，`points_total > saved` 的帧归入
   `partial_sample_not_evaluable` 单列；新增测试覆盖。
3. 另加 `estimate_se3`（跨 run 单 SE(3)/匹配前缀，Umeyama）与测试；ICP 仍只作局部拟合量，不替代公平对齐。
   对同一 bag 的两次运行，两者都从同一起始帧的单位位姿出发，起始 gauge 相同，漂移按每帧对齐处理并标注。

本机状态：S2 的干净 pass 已产出 PCD（`Log/pcd/all_raw_points.pcd` 40 MB、`all_downsampled_points.pcd` 216 KB、
`lidar_poses.txt`），但尚未提交归档/receipt，故本轮**不评分、不宣称结果**；等 S2 交付 SHA 与配置后再离线评分。

## 111. 干净参考地图 pass 已交付，但作为独立参考**不可用**（S1 离线评分负结果）

S1 复核 S2 `dafbd50`（合入，217 测试）。归档 `review_20261112_availability/reference_map_20261112/`：
PCD raw 2,498,791 点 / downsampled 13,493 点、config 副本 `refmap_m2dgr.yaml`（只改 pcd_save）、
runner 加 `SAVE_WAIT`（SIGINT 后才走 `savePCD()`）——这些均成立。

**S1 离线评分（现有 predicted_pose 544 行 × 该地图）暴露三个不可用原因**：
1. **覆盖窗口只有约 54 s**（lidar_poses 1627785261.4–1627785315.5），报告写"跑完整 bag（59.99 s）"
   与 bag 320 s 不符；`run_summary.paired=396`，说明该 pass 只处理了前 60 s；
2. **`lidar_poses.txt` 的位姿近似静止**（全程 |p| < 1 m，第 100 帧 0.001/-0.009/0.399），
   而地图范围 ±80 m——位姿日志与地图不一致，无法用它建立跨 run gauge（匹配前缀 Umeyama RMS 3.51 m）；
3. 用该地图对窗口内 302 个全样本帧做同一支持测试：**before/after per-frame ICP 均 0 通过**
   （aligned median 0.0、correction median 0、ICP 找不到对应点）——与"扫描/地图不在同一覆盖"一致，
   **不能据此对诊断 run 下任何覆盖/位姿结论**。

因此本轮**不宣称独立参考结论**；工具本身（PCD 读取、gauge、ICP、裁样本分离）已按审阅修正并有测试。
下一步：S2 重做 clean pass（完整 bag、确认位姿日志随轨迹移动、地图范围与诊断 run 轨迹匹配）后再评分；
若位姿日志仍静止，先查 `pcd_save` 的位姿写出分支，不拿不符数据硬评。

## 112. 独立参考**不可用（BLOCKED）**：干净 run 与诊断 run 的宿主轨迹本身分叉

S1 复核 S2 `0188b0b`（合入，217 测试）。重做后的 clean pass 三个问题前两个已解决：
`rosbag play` 播到 59.981/59.994 s `Done.`、`paired=544`、`lidar_poses` 819 行到 320.909；
位姿随轨迹移动（x 0–8.8 m），与诊断 run 同帧一致（kf 22：1.3605,−0.1215 逐位相同）；
用 clean PCD 对 kf22 的 20 个样本 20/20 within 1 m（median 0.25 m）——地图/gauge 无问题。

**但独立参考作为诊断基准不成立**：两个 run 的宿主轨迹在约 15 s 后分叉到 30–40 m——
诊断 run kf157 位姿 (−25.78,−18.47)、kf228 (−19.93,−10.40)，clean run 同时刻 (6.80,4.56)、(6.75,8.77)，
对 clean PCD 的 within 1 m 为 0%。诊断 run 自己的 snapshot 也确认它去过 (−19.55,−10.40,−1.67)。

**原因（S1 判断）**：诊断 run 是 `detection on`，恢复循环自身在动作（hold/restore/resume 改变宿主
状态与地图）；clean pass 是 `detection off` 且无动作。**只要有干预，就没有"同一轨迹"的无干预参考**；
这不是地图 bug，也不能用一次无动作 pass 做同一轨迹基准。

**结论**：选项①（诊断 run 自己的 PCD＝非独立）、②（固定/回放宿主位姿＝新运行设计）、③（GT，本机无）
都需要新决定；按"仍不可用就停"结束独立参考线，**不追加第三次 clean pass**。
能保留的事实：kf22 型正常帧确实被 clean 地图覆盖（20/20），后期帧不被覆盖是因为诊断 run 自己走开了。

## 113. v6 边界 checkpoint：两段 checkpoint 都早于各自隔离起点，终版两事件 run 通过

S1 复核 S2 `584604c`（合入，217 测试）。宿主 v6：`snapshotCheckpoint()` 的 `cp_stamp_` 改为"最后一个
已处理组"的 lio_time（33 行增量、完整 `deployed_host_v6.diff` 1638 行、新库 sha **`ca9126c4…`**，本机核对，
可执行文件仍 `0d7e23de…`）；驱动武装戳改为 `声明戳 − margin`（= manager 的 `t_q_start`）。

run `fl_native_20261112T092251Z_291996`（终版）：

| 项 | 实际（本机核对） | 判定 |
|---|---|---|
| 第一段 `t_start` | `1627785272215170145` | — |
| 第一段 reprocess stamp | `1627785272199251712` | **早 15.9 ms ≤ t_start** ✔ |
| 第二段 `t_start` | `1627785302371636152` | — |
| 第二段 restore stamp | `1627785302359221248` | **早 12.4 ms ≤ t_start 且早于触发** ✔ |
| 第一段 | Mode 2 accepted、`repairs applied=23`、within 244 / suffix 550、重放 794 帧 [272.266..298.692]、地图 27805/564227、**无 set_state** | ✔ |
| 第二段 | Mode 3 拒绝 + restore，close→rearm→resume；关闭 319.184，尾段到 320.909 | ✔ |
| 终态 | HEALTHY、`open=false`；2 行候选；4 条 lifecycle | ✔ |

审阅多轮保留的"checkpoint 不晚于可信隔离边界"断点**就此解除**（两段均满足）。`within_end` 由 124 增至 244
是因为重放从 `t_start` 起覆盖确认窗口；修复云仍只匹配候选窗口的 23 帧。门/阈值/σ/检测未动；
可用性诊断暂停；损坏自注入，不声称修复收益。

## repair-f3 / eeda122：新参考图归档接受，静止与320秒归因需原件纠正

[核验与下一交付](review_20261112_eeda122/README.md)：11SHA一致、目标driver/config副本绑定、无注入/detection off地图确保存raw2,498,791/downsample13,493点，退出末terminate异常保留。新partial主分母/中性cause/单gauge工具7相关test本机PASS，Scipy ICP未跑不装；SAVE_WAIT只bash语法/源码核，不代host。支持旁支真实交付，原生恢复主线未增加。

目标§111静止原因FAIL：同档749pose行最大|p|11.98754m、724行>1m、x/y最大8.808419/8.833413。地图范围不等移动范围，不能据此查pcd_save输出分支或重做clean pass。pose54.119872s/诊断尾前5.385359s只证明时间支持不足；396paired/598scan不证明bag截断，320s无bag起止证据/不能读epoch尾数为duration。302帧0pass/ICP/gauge RMS3.51仅DEVELOPER_REPORTED且score命令/输出/健康prefix单变换/共同支持未归档，独立参考有效性UNKNOWN；先复用现有证据纠正与绑定，不本轮新授权重跑、不因诊断串行挡native。

S1证据解释/共享成功依赖单写，S2原生合法隔离起点cp→物理一致修复/完整state-map重估→全部input归宿/后继尾段或显式不支持；复用已验suffix/skip/受控E2，不重复旧反例或扩门参数。ALI-H设计合main不等认领或实现，S3唯一研究角色先按已授权T0资格/缺项回真实预算/branch/进展，缺I与低support正常参照保UNKNOWN/native不等。逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令原件/版本人口/失败质量成本；A/B局部不总分/三Cron无双写，review SSH白名单提交推送/private保护不合main不改算法历史冻结门。

## repair-f3 / 用户明确交给开发：ALI-H真实数据验证的单一交付

2026-11-12用户要求通过GitHub交接[ALI-H §10任务](ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md#10-用户明确交接的下一单一交付真实数据验证-ali-h)：先分别核旧402/544行真实通道/缺项/校准，HEALTHY非正常真值；优先复用真实IMU preupdate与LiDAR update状态，缺导出由S1/S2确认一次最小已有预算导出，不造零bias/占位、不换地图无限解释；交同trace同人口旧方法/shadow漏检、误报、延迟、错误NORMAL、UNKNOWN数量/时长/原因与成本。新run内证据不能贴回旧run冒同步；缺标签NOT_EVALUABLE，不降首版或旧阈值强二分。

S1分发/确认owner branch HEAD预算并单写共享接口，S3唯一research执行，S2现trace/必要最小导出，保持1研究+2native/旧参数停；本机不算法/host，自动审阅继续、不重复建任务。不自动暂停原生开发，研究不直接接入实际检测/地图提交；一次有限真实结论交用户后再决定生产动作。逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE及命令原件/人口/缺项，发布不等认领/开工。交接fetch fafbaf1新地图redo/分叉仅开发报告，另审不作为本任务已证明因果或新重跑许可。

## repair-f3 / fafbaf1：新地图尾部通过，干预因果/参考规则需限定

[核验](review_20261112_fafbaf1/README.md)新085719Z 12SHA一致、play Done/819pose/544paired到诊断同末戳/native819、downsample15647/raw2889123保存接受；detection off/no恢复动作、44snapshot/6timeout/末terminate，不新增原生恢复结果。旧REPORT加后续说明但原清单未变10/11（仅REPORT），集中版本化补来源、不动历史/重跑。

同戳位置差真实：kf157/228未注册差39.903/32.923m，各全200保存样本距新图0/200；kf22仅20/200裁样本20命中非全帧或gauge真值。完整544差最大80.002m、首>1m kf46，不精确15s起点/GT漂移。diag v3库9c0330be/driver43c65a9d/config47a1bfd9 vs新v5 9e7d8cdf/4742dbc1/94ffa5db，bag/binary同不单一干预控制；8restore/7resume是候选机制非已证唯一因果。独立图需同场景合法注册/覆盖而非相同估计轨迹，复制诊断pose造图不能当独立位姿参考；当前有效性UNKNOWN，不再clean矩阵。

S1原因/人口限定只阻相关评价结论，S1/S2合法cp/成功依赖及物理native整链继续；S3用户105b5be ALI-H§10真实数据交付优先旧402/544资格/真实I/同人口风险与UNKNOWN成本，不等独立地图；新target未含最新任务，不指控忽略/不冒认领或测试。1研究+2native/旧参数停，逐项状态/命令原件/source input library/人口/失败质量成本自检，A/B局部不总分；Python-I reader无host/bag/ICP/参数，三Cron单owner，review白名单SSH/private保护不合main不改算法历史。

## 114. 合入 fafbaf1 审阅并更正 §111/§112；ALI-H §10 任务已分发

S1 合入审阅分支 `6f89e38`（含 `4455294`/`105b5be`/`6f89e38` 三提交；§110–§113 与审阅侧段落并存，冲突按两侧都保留
解决）。审阅只改文档，无 `slam_recovery` 实现改动；本机按原件复算下列数字，全部与审阅一致。

### 114.1 本机复算（REAL_HOST 归档原件，不经归档脚本）

| 检查 | 本机结果 |
|---|---|
| 重做 clean pass 位姿 | `reference_map_20261112_redo/lidar_poses.txt` 819 行，`1627785261.403843–1627785320.909074`，sha `443da1cd…` ✔ |
| 重做 clean pass 地图 | `all_downsampled_points.pcd` 250,534 B / 15,647 点，sha `f1367c1c…` ✔ |
| 同戳未注册位置差 | kf22 `0.000000`（文本精度内）、kf157 `39.903317 m`、kf228 `32.923310 m`；544 对中首个 >1 m 为 kf46 `1.761249 m`，最大 kf173 `80.002159 m` ✔（诊断 `T_wb[3,7,11]` vs 重做位姿，记录坐标，非 GT） |
| 首版 clean pass 位姿 | 749 行；x `0.002225–8.808419`、y `−0.121540–8.833413`、z `−0.380372–0.288689`；最大 `|p| 11.987540 m`，724/749 >1 m ✔ |

### 114.2 更正

1. **§111 第 2 条作废**：首版 clean pass 的位姿**不是**近静止（最大 11.99 m）。据此安排的 `pcd_save`
   位姿写出分支排查不再成立；地图范围 ±80 m 与约 12 m 移动不矛盾（扫描可见远处）。几何一致性原因 UNKNOWN。
2. **§112 "独立参考不可用（BLOCKED）" 收窄为 UNKNOWN**：独立参考只要求同一物理场景、合法坐标注册与可见/评价
   覆盖，**不要求复制待评价运行的估计轨迹**。本机复算确认两 run 轨迹确有分叉（最大 80 m），但这是"记录坐标差"，
   不是已注册 ATE 或已证位姿错误；当前图是否可作独立参考仍是 UNKNOWN，不是"原则上不可用"。不允许把诊断
   `T_wb` 以 `set_state` 写进参考来造同轨迹（那是自参考 proxy，不是独立评价）。
3. **分叉原因 UNKNOWN**：诊断 host 库 `9c0330be…`(v3) vs 新地图 `9e7d8cdf…`(v5)，driver `43c65a9d…` vs
   `4742dbc1…`，config `47a1bfd9…` vs `94ffa5db…`，另有 detection on/off、sigma `.884/.12`、drain 20/60。
   "detection on 的 hold/restore/resume"只是合理候选，不是已分离的唯一原因。
4. **旧 `reference_map_20261112/REPORT.md` 追加 §6 导致原清单 10/11（仅 REPORT 失配）**：原历史 checksum 保持
   与当时版本绑定，修正走"补版本化清单/外部追加说明"，不改历史、不为文档 hash 重跑宿主。

主线状态不变：boundary checkpoint（v6）与 §113 的受控两事件结论仍然有效；本次更正只影响"独立参考"这条
评价旁支的解释，不影响原生 `suffix`/`skip`/受控 E2 与 39 尾帧证据。

### 114.3 任务分发（不写"已执行"）

- `docs/ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md` §10（用户 2026-11-12 明确交接的 ALI-H 真实数据验证）
  随本 merge 进入 main；状态仍 **DESIGNED / NOT_IMPLEMENTED / NOT_EXECUTED**。
- 已把 §10 单一交付（T0 旧 402/544 资格与缺项 → 至多一次最小真实 I 导出 → 同人口旧方法/shadow 对照）
  分发给 S3（r26534-58，唯一研究执行），并向 S2（r11070-c3）确认宿主真实 IMU preupdate/update 创新导出点与
  现 trace 是否可复用。**认领/预算/新 branch 以 S3/S2 实际回报为准**，本文件不代填。

### 114.4 本轮巡检的宿主与推送状态（2026-11-12 17:43 CST）

- **无活动宿主运行**：近 40 分钟内无新 run 目录、无新 `receipt.json`；最新 run 仍是已核的
  `fl_native_20261112T092251Z_291996`（17:25）。宿主侧残留 3 个旧进程（`roslaunch fast_lio` 自 11-05、
  两个 `roscore` 自 11-09/11-10），非本轮启动，未处置、未据此调参或重跑。
- **S2/S3**：截至 17:43 无新交付/求助消息回到本机；两会话状态为 busy（已在本轮收到 ALI-H 分发与 trace 接口询问），
  **认领与执行仍记 UNCONFIRMED**，不写成"正在执行"。
- **推送**：本机 main `0eec9e1` **尚未推送**——本机无 credential helper、`.git/config` 无凭据，按规则不从会话记录取
  PAT；远端 `slam_recovery/main` 仍 `d86e57d`，审阅分支 `6f89e38`。凭据可用后即推。

## 115. S3 认领 ALI-H v1 T0/T1，I 通道经本机核对为 NOT_AVAILABLE；main 已推送

S3（r26534-58）2026-11-12 回执认领，本机逐条核对如下（只核原件，不代跑）：

| 项 | 实际值 |
|---|---|
| S3 worktree | `/tmp/wt-ali`，`git worktree list` 可见；branch `exp/ali-h-v1`，HEAD `0eec9e1` |
| 顺序/预算 | T0 → T1 在既有 S3 研究时段内（0 宿主 run、0 参数矩阵）；T2 仅在 T0 指出可解除缺项且 S1/S2 确认一次最小导出后做，否则 BLOCKED |
| 实现位置 | `docs/ali_h_v1_research/` 独立模块；不写 manager/recovery 共享代码（共享接口单写仍在 S1） |

**I 通道 NOT_AVAILABLE 的证据（本机复核，与 S3 结论一致）**：
- `availability_frames.jsonl.gz` 顶层键无任何 IMU 字段；`nis` 子键仅为 LiDAR holdout（`selected_reference_source`、
  `raw_kind`、`sigma`、`effective_nis`、`trusted_total` 等）；`support` 子键为 `radius_m/reason/reference_points/
  threshold_fraction`。`support_under_predicted_pose` 是可信位姿匀速外推，不是 IMU preupdate。
- 输入 `hall01_two_event_v1.bag` 实际话题只有 `/camera/color/image_raw`(888)、`/handsfree/imu`(8599)、
  `/velodyne_points`(598)，**无 `imu_prop_odom`**，因此不能离线重建 I。
- 宿主侧确有该量：`LIVMapper.h:125/131` 的 `imu_propagate`/`imu_prop_odom`/`pubImuPropOdom`，及 `:231` 附近
  checkpoint 内的 pre-integrator 跨帧值（`cp_last_imu_`/`cp_last_prop_end_time_`）；导出属"至多一次最小导出"，
  待 S2 回接口与预算，不由 S3 自行开始。

**推送**：main `d86e57d..468e649` 已推送（内联认证，`git config --list --local | grep -c ghp_` = 0），
远端 `slam_recovery/main` 现与本地一致（`rev-list --left-right --count` = 0/0）。

S3 承诺 T0 完成后先报中间 HEAD；本轮不把"已认领"写成"已执行"，T0 结果仍记 NOT_EXECUTED。

## 116. S2 回 ALI-H trace 接口，S1 核实并批准一次最小导出

S2（r11070-c3）确认宿主已有 ①②、③需最小 instrument。本机逐条核过源码与运行时产物：

| 断言 | 本机证据 |
|---|---|
| `fout_pre`/`fout_out` 已落盘 | `Log/mat_pre.txt` 2515 行、`Log/mat_out.txt` 2253 行（mtime 17:24，属 `092251Z` run） |
| 列结构 | 19 列（time, euler°, pos, vel, bias_g, bias_a, inv_expo）＋mat_out 第 20 列 feat 数 |
| 写入点 | `LIVMapper.cpp:469–472`（`handleLIO` 开头，`StateEstimation` 前）、`:622–625`（函数尾） |
| 两文件每次 trunc | `initializeFiles` 中 `fout_pre.open(...,std::ios::out)`/`fout_out.open(...)` 同处 |
| 协方差仅内存 | `DIM_STATE=19`；`_state.cov` 打印在 `LIVMapper.cpp:394–396` 被注释，无落盘 |
| 同键 | t=0.36 的第二行 pos `-0.00249287 -0.00252392 -0.00015602` 与 S2 样例一致 |

**S1 批准的导出范围（一次，不追加）**：
- 字段：`P⁻`(rot+pos 6×6)、`P⁺`(6×6)、`vec`(6)、`H_T_H`(6×6)、`effct_feat_num`、`R_inv` 摘要、
  **测量空间 `S = H·P⁻·Hᵀ + R`**（ALI-H §3 的 `s_I` 用 innovation covariance，`H_T_H` 不是 S）；
  另加**绝对戳**列与 `has_out` 标记（早退帧只有 pre，按时间键配对不起静默失配）。
- 控制：同一 build 跑 trace off / trace on 两次，同 bag、同 config、同触发，各用新 run 身份；报告帧数/决定/
  lifecycle/终态位姿一致性，有差异如实报。
- 预算：1 次重建 + 2 次约 60 s 运行，产物 ~2–4 MB，窗口=整段 bag。
- 归档纪律：`mat_pre/mat_out/trace_cov` 每次 run 后立即复制并算 sha256（下次运行 trunc）。
- 边界：S 是逐点面残差在单一线性化点的 6 维聚合，不能与 VIO/NIS 阈值互比；量级随 `cov_acc/cov_gyr` 变；
  首两行为 IMU 初始化占位需剔除。

状态：S2 **接口确认已完成**；导出**尚未开始**（等 S2 实施与回执），故记 NOT_EXECUTED。S3 的 T2/T3 在拿到
同一份新 trace 前保持 BLOCKED/UNKNOWN，不把 IMU 状态贴回旧 402/544 行。

## 117. S3 的 ALI-H T0/T1 已核（本机复算一致），三处修正后定稿；T2 等 trace

S3 交付：branch `exp/ali-h-v1`、HEAD `8c5b082`（基于 `0eec9e1`），仅新增 `docs/ali_h_v1_research/`
9 个文件（`ali_h_v1.py`/`selftest.py`/`manifest.json`/`shadow_A.jsonl`/`shadow_B.jsonl`/`t0_A.json`/
`t0_B.json`/`t1_selftest.json`/`REPORT.md`），未改旧归档、未写共享代码、0 宿主。

**本机独立复算（读 S3 的 JSONL，不执行其脚本）**：

| 项 | Run A | Run B |
|---|---:|---:|
| 旧 AVAILABLE / UNAVAILABLE | 95 / 307 | 132 / 412 |
| `insufficient_support` / `empty_reference` / `nis_unavailable` | 285 / 22 / 1 | 351 / 61 / 1 |
| UNAVAILABLE 中 M 有证据 / 仅 T / 都无 | 28 / 278 / 1 | 137 / 274 / 1 |
| `channels.I.present` | 0 | 0 |
| shadow 状态 | UNKNOWN 402/402 | UNKNOWN 544/544 |
| T1 | 6/6 PASS，`failed: 0` | — |

结论（证据资格，不是分类器失败）：NORMAL 需"真实 I + M 或 T"，I 在两归档中为 0，故 **NORMAL 结构上限 0，与参数无关**；
SUSPECT 因无独立确认的正常前缀而无法校准。能进入 M 分支的旧 UNAVAILABLE 为 9.1%（A）/33.3%（B），其余只有 T。

**已要求 S3 修正（不影响上述数字，只影响定稿）**：
1. REPORT 写"shadow 输出 550 KB + 752 KB"与实际 `652,502`/`891,001` B 不符，改实际 bytes。
2. T1.6 的 `state_counts: {UNKNOWN: 90}` 实为块数（402 帧↔90 块），字段名需改为 `block_counts` 并写明换算。
3. `manifest.json` 缺 shadow/t0/t1 产物 sha256，需补实际 digest。

**T2/T3**：接口侧已由 S2 确认（见 §116），但**导出尚未执行**，S3 保持 BLOCKED。拿到 trace 后必须在新 trace 上同时算
旧方法与 ALI-H，不得把旧 402/544 行与新 trace 拼接；缺独立正常前缀则记 `INCOMPLETE`，不以 HEALTHY/trusted 充真值。

## 118. ALI-H T0/T1 定稿核验并合入 main

S3 修正后 HEAD `062d71e`（`exp/ali-h-v1`，仍未推送）。本机核对三项修正全部成立：

| 项 | 实测 |
|---|---|
| 文件大小 | `shadow_A.jsonl` 652,502 B、`shadow_B.jsonl` 891,001 B（与 REPORT 一致） |
| 产物 digest | `1123e016…`/`343f9811…`（shadow）、`99f276be…`/`e9638d5f…`（t0）、`8cb75947…`（t1）与 manifest `artifacts` 一致 |
| T1.6 口径 | `real_trace_frames: 402`、`real_trace_blocks: 90`、`frame_to_block` 说明、`block_counts` 与 `state_counts_frames` 分开 |

已 `--no-ff` 合入 main（`ce8062e`），仅新增 `docs/ali_h_v1_research/`，未动共享代码。本机测试
`python -m unittest discover`：**201 tests OK**（与本次合入无关的历史计数差异：此前记录的 217 来自不同发现口径，
本次按仓库标准 discover 重跑为 201，无测试文件被删除）。

T0 数字与结论不变（见 §117）：NORMAL 结构上限 0、全部 UNKNOWN 是证据资格结论。T2/T3 继续 BLOCKED，
等 S2 的最小 trace 导出。

## repair-f3 / d86e57d：两事件真实cp早隔离起点，拒绝后历史归宿仍未验

[核验](review_20261112_d86e57d/README.md)新092251Z/23SHA/source target/v6库绑定，scripted trigger-margin及前已处理组cp，真实apply early E1 15.918433ms/E2 12.414904ms，具体晚边界断点解除。E1修23/原生794=244+550/map27805,564227/无set_state→接回→E2拒绝restore/关闭rearm/resume/尾17,1.725149s接受，受控/detection off/E2无注入非自动收益。未解128/160、59shift23修36未修保留；E2无第二reprocess，fullpatch resume只map_hold=false，消费历史/健康后缀归宿与时间连续性UNKNOWN，未来输出不充追赶。

S1/S2最低复用buffer/重推明确拒绝与需追赶input/IMU视觉归宿，或不支持范围显式拒绝；不重放已拒污染/不重做时间边界旧FAIL。旧失败UNKNOWN写回/物理候选范围保不重测，S3用户ALI-H同人口真实验证继续，旧参数停。changed test及正常10s-margin4s控制PASS/no源码新review发现，laser_mapping Built/整体ABI failed保；status负延迟只字段旁支，来源人口/失败质量成本自检，A/B局部不总分/Python-I不host/private保护。用户17:53新15h连续执行与重大阻塞中文GitHub确认任务另发布，不冒本target已认领新要求。

## repair-f3 / 用户15小时任务：不停普通失败，中文告知重大阻塞，先真实ALI再自动检测

用户17:53直接要求持续15h至2026-11-13 08:53 UTC+8，[执行入口](OVERNIGHT_ALI_AUTODETECTION_TASK_20261112.md)优先：S1分发/集成/实际预算和运行owner，S3独立ALI-H真实资格shadow同人口评价，S2现运动trace/必要一次最小导出及原生自动检测接线验证。用户同轮明确暂时没有Codex分支会话辅助，不再给Codex分派或等待其复核，本机S4独立审阅；既有历史分工不当现可用人员。具备真实结果后有限实验接线获准继续，默认生产部署/改科学门/选新模型/超预算不自动批准，旧参数停/1研究+2集成宿主，UNKNOWN不充正常。保已验v6边界/suffix/skip，必要拒绝后输入归宿/成功依赖同期收口，不换图无穷诊断。

重大阻塞立即中文文件/提交GitHub，附ID/版本命令原件/影响/最低解除/需用户确认的最小选项；只停阻塞部分、不删负结果，实际用户GitHub提交确认后恢复。S4三Cron已挂、会话存活限定，无gh/认证评论读取不冒正在看Issue或已收到；建议用户在仓库阻塞记录commit确认，S1沿现可读渠道同步出处。截止中文结果含漏检误报延迟错误NORMAL/UNKNOWN区间与成本/实际自动动作及未解决范围，自检状态而非test数。发布不等实际接收开工，下一实交回真实owner branch/HEAD/预算；不造收到周期、不承诺所有问题必然解决，review SSH中文提交/private保护不改算法历史。

## repair-f3 / be35af9：认领与缺项接受，研究原件待发布、I导出先对应残差空间

[核验](review_20261112_be35af9/README.md)S3已明确认领exp/ali-h-v1/8c5b082九研究文件、S2现pre/out接口与导出方案回报；main未含文件、remote研究分支空/本机无对象，T1六PASS/shadow全部UNKNOWN记DEVELOPER_REPORTED，先现产物上传SHA不重做。旧402/544 raw资格本机-I复算U307/412、M28/137/T278/274/none1/1/I0，空22/61内各缺NIS1不额外加；finite非qualified/NORMAL结构上限0、不能调门补I或label。

§116计划测量S=H Pminus H^T+R不能直接作SE3 eI协方差，H_T_H非S/6维压缩需对应映射、pre/post相关不能简单相加。S1/S2/S3最低同time frame/tangent/rank residual-Sigma定义，缺cov用单位残差/条件经验校准，保NOT_AVAILABLE不假概率/不新模型/巨大矩阵；导出phase/replay早退与绝对戳归宿同核。同新trace旧方法/shadow风险误报漏检延迟错误NORMAL/UNKNOWN时长成本才下一实交。

S3上传研究/配对评价、S2一次现预算真实导出、S1共享集成与原生最小归宿并行，最新15h任务2c优先、不凭未合推忽略，旧参数停/无Codex/1研究+2集成。暂只是可解除trace依赖，不新全面重大阻塞；真缺证据/超范围立即中文GitHub选择，未阻工作继续。逐项状态命令原件/source人口/label失败质量成本，不test数/全UNKNOWN假安全；本机不算法/host，A/B局部不总分，三周期+截止单owner，review中文SSH/private保护不合main历史冻结门。

## 119. 15 小时任务已获取并分发；一次 trace run 因环境 FAIL；导出残差空间按审阅更正

### 119.1 用户新任务（2026-11-12 17:53–11-13 08:53 UTC+8）

审阅分支 `2c838c7` 发布 `docs/OVERNIGHT_ALI_AUTODETECTION_TASK_20261112.md`：15 小时内完成 ALI-H 真实数据验证、
推进有限自动检测接线、交一次明确结果或中文重大阻塞；中文提交/报告；普通失败不停整体任务；无 Codex 辅助。已合入 main（`4e66f39`）。

### 119.2 本机观察到的宿主运行（只记录，未干预、未重跑）

`fl_native_20261112T101116Z_329791`（18:11 起，scripted 两事件 + `--repair-publish`，detection off）**已结束，status FAIL**：
- `host.log` 末：`[rospack] Error: package 'image_transport' not found` → `image_transport::Exception: No plugins found!`，宿主启动即 terminate；
- `wiring.json`：`pose_messages: 0`、`scan_messages: 598`、`paired: 0`；recovery 写 0 候选；
- `receipt.inputs.runtime_library_sha256` = `691d7334…`（≠ v6 的 `ca9126c4…`，为重建库）。
判定：环境/插件路径类普通失败，不是检测或写回逻辑失败；已把原件位置回报 S2，由其做最小诊断，S1 不重跑。

### 119.3 导出残差空间更正（S1 批准内容修正）

审阅 `5e05826` 指出、本机同意：`H` 将 6 维状态映射到 m 个点面残差，`S = H·P⁻·Hᵀ + R` 是 **m×m 测量空间**协方差，
`H_T_H` 是信息阵，二者都不是 ALI-H `e_I`（6 维 SE(3) 切空间）的协方差。批准内容更正为：

| 导出 | 要求 |
|---|---|
| `P⁻`/`P⁺` 位姿块 | 6×6；声明状态顺序、旋转参数化、扰动左/右、body/world |
| `vec` | 6；同上声明 |
| `effct_feat_num` | 实际参与点数 m |
| 测量空间统计 | 单独命名（mean/median/chi2、维度 m），**不得称 S、不得当 e_I 协方差** |
| 时间/身份 | 绝对戳 + `has_out` + run/phase（replay 可能重复同戳） |

禁止：`P⁻`+`P⁺` 相加当 e_I 协方差；无协方差时补单位阵或造假卡方。无协方差则交带单位权残差并标 `NOT_AVAILABLE`。

### 119.4 旧档标签不一致（本机复算）

Run A（402）中 285 个 UNAVAILABLE 帧的 `support.reason` 仍是 `ok`（fraction 低于阈值却未更新原因字段）；
Run B（544）为 `fraction_below_threshold` 351。S3 的 `insufficient_support` 是派生值，与审阅结论一致；
后续引用须注明该字段在旧 Run A 中不可直接当判据。

## 120. S3 的 T2 输入契约已核并合入；真实 T2 仍等 trace

S3 HEAD `63b9029`（`exp/ali-h-v1`，只动 `docs/ali_h_v1_research/`），本机核对：
- `REPORT.md` §2.1 已写明 Run A 的 285 帧旧 `support.reason` 仍为 `ok`、`insufficient_support` 为派生值
  （`pass==false && reference_points>0`），Run B 的 351 帧旧字段为 `fraction_below_threshold`；与 §119.4 一致。
- 新增 `T2_INPUT_CONTRACT.md` + `t2_input_check.py`：只接收 `P⁻`/`P⁺` 6×6 位姿块、`vec` 6、`effct_feat_num`、
  更新前/后位姿与绝对戳；**显式拒绝** `S` 与 `H_T_H` 当 6D 协方差；必须声明 state order/旋转参数化/扰动
  左右/frame/外参/bias 来源，缺项 `INCOMPLETE`；无协方差则单位权 + `NOT_AVAILABLE`。
- `t2_prep_selftest.json`：11 项、`failed: 0`（含 S 拒绝、旧 run id 拒绝、e_I 手算、秩亏协方差、单位权）。

已 `--no-ff` 合入 main，测试 `python -m unittest discover` 通过。真实 T2 **仍 NOT_EXECUTED**，等 S2 trace。

## 121. T2 协议已预注册并合入；两次 trace run 同因 FAIL，环境证据待补

S3 HEAD `0d929f2`（`exp/ali-h-v1`）新增 `docs/ali_h_v1_research/T2_PROTOCOL.md`（155 行）：写定于看到任何新 trace
结果之前，冻结 0.5 s 块 / u≥0.95 / u≤0.80 / ≥20 块 / 两相邻块、**不扫参数**；定义 `scan_stamp_ns` 精确 join、
`NO_AVAILABILITY_ROW`/`NO_TRACE_ROW` 单列进分母、三状态最小证据、校准与评价分离、错误与 UNKNOWN 口径、停止条件
（含拿 `S`/`H_T_H` 当协方差即 STOP）。已 `--no-ff` 合入 main，201 tests OK。

**宿主侧（本机观察，未干预）**：`100744Z_326380` 与 `101116Z_329791` 两次 run **同一失败**——
`pose_messages: 0`、`scan 598`、`paired 0`，`host.log` 均为 `[rospack] Error: package 'image_transport' not found`
→ `image_transport::Exception: No plugins found!`；两 run 同库 `691d7334…`，driver `a4aaa58b…`（≠归档 run 的 `4742dbc1…`）。
本机按 runner 相同方式 source 后复现：`ROS_PACKAGE_PATH=/home/R26534/fast_livo2_ws/src:/home/R26534/mm/ros/share`，
`rospack plugins --attrib=plugin image_transport` 正常返回，说明失败在**进程环境**而非插件缺失。已要求 S2 在宿主
fork 前记录 `ROS_PACKAGE_PATH/ROS_HOME`，并**在拿到该证据前不进行第三次重跑**；本轮仍记 NOT_EXECUTED。

**补**（S3 `98abad4`，已核并合入）：`T2_PROTOCOL.md` §1.1 与 §5 已把 join 规则改为
`last_lio_update_time` ↔ `scan_stamp_ns` 精确相等，trace 必须同时导出 `scan_header_stamp` 与
`last_lio_update_time`；偏移非常数或只给 header 戳 → `INCOMPLETE:join_key_unresolved`；契约与
`t2_input_check.py` 同步，11/11 仍 PASS。

## 122. v7 trace 身份已核；宿主启动崩溃定位为进程内内存损坏；S1 批准诊断构建 A

S2（r11070-c3）回报，本机逐项核对：

| 项 | 实测 |
|---|---|
| 驱动 | `/tmp/wt-sim`，branch `exp/m0-updated`，HEAD `584604c`；未提交：`run_native_loop.sh` 的 `TRACE_COV` 与 rospack 预热 |
| v7 改动 | 4 文件 +145/−5（`LIVMapper.{h,cpp}`、`voxel_map.{h,cpp}`）；diff 归档在 `docs/review_20261112_four_host/host_change_trace_cov/trace_cov_v7.diff` |
| 当前库 | `0308c216…`（v6 为 `ca9126c4…`；首次构建 `691d7334…`），可执行文件仍 `0d7e23de…` |
| 两次 FAIL | `100744Z_326380`/`101116Z_329791` 均为 trace-off 尝试，0 帧，**不构成 A/B 证据** |
| `Log/mat_pre.txt`/`mat_out.txt` | **已 0 字节**（被失败启动 trunc），不可复用 |
| 可用位姿旁证 | `last_good_pose/M2DGR_room_02.txt` 1127 行、sha `7cd8a90f…`、`…263.142320–…320.909074`；仅 P⁺、无协方差、无帧号，不作 trace |

**崩溃定位（S2 最小诊断，本机未复跑）**：不经过 runner 直跑二进制、`env -i` 最小环境、预热 rospack 缓存后仍崩；
同 shell/ROS_HOME 下 `image_transport` 探针正常；LD_PRELOAD 显示进入 OpenCV 初始化后 ROS 变量返回 NULL（`environ`
指针未变），`OMP_NUM_THREADS=1` 时 terminate 变 SIGSEGV。判定：**宿主进程早期内存损坏**，与 trace 代码无关
（崩溃发生在第一帧 LIO 前）。

**S1 批准的下一步（诊断构建 A）**：恢复 v6 源码快照增量重建（≤3 min）→ 只做启动探针（不跑 bag/不起 play/检测关，
存活 ≥10 s）→ 记录新库 sha、`ROS_PACKAGE_PATH/ROS_HOME/LD_LIBRARY_PATH`、探针输出。若 v6 也崩，先回报证据，
再执行已批准的 B（`catkin_make clean` 全量重建，≤15 min）；若 v6 通过而 v7 崩，按四文件逐块二分（先 `voxel_map.cpp`）。
**不批准 C**（跳过 image_transport publisher，改宿主输出）。探针期间不跑 bag，不产生新 run 身份。

## 123. 拒绝回退后的输入归宿：driver 现在显式记录"只回滚、不重放"（S1 实现）

审阅 `13002e6` §3 指出的最小原生缺口：E2 restore 后 `resume` 仅释放 map hold，302–311 s 已消费输入的归宿
没有显式记录，容易把"restore+resume"读成完整历史恢复。S1 在 driver 侧做最小记录（**不改变任何控制行为**）：

- `decide()` 拒绝分支在 `cp.restore()` 后写 `ep.meta["restore_disposition"]`：
  `scope=STATE_AND_MAP_ROLLBACK_ONLY`、`checkpoint_stamp_ns=trigger−confirmation_margin`、`decision_ts_ns`、
  `interval_ns=[checkpoint, decision]`、`consumed_input_in_interval=NOT_REPLAYED`、
  `subsequent_input=CONTINUES_FROM_RESTORED_STATE`、`catch_up=NOT_IMPLEMENTED`。
- 该 meta 已随 `run_summary.quarantine.episode_detail` 落盘（现有结构，不新增 schema 文件）。
- 新测试 `test_repair_sync.py::test_a_refusal_records_that_the_consumed_interval_was_not_replayed`
  （拒绝路径 1 次 restore、0 次 reprocess、字段与区间正确）。全量：**202 tests OK**。

这**不是**追赶实现：不做历史重放、不扩大缓存、不改阈值。它只把"拒绝区间内的输入未重放"从隐含变成可核字段；
真正的重放/接回能力仍需 S2 宿主侧与新的受控 run 证据。本轮无宿主运行，NOT_EXECUTED。

## repair-f3 / 24cf24c：T0原件可验收，真实导出重复启动失败先保最小环境证据

[核验](review_20261112_24cf24c/README.md)研究源码/validator/协议已上传，五产物hash+code一致，402/544 shadow逐行旧身份分数/90,119块人口来源一致，全UNKNOWN/真实I0/normal标签缺项接受，不再记未上传；T1六/T2 prep十一保存PASS本机未执行，无共享算法改动/新真实trace或自动运行，不效果或主线恢复成功。

两次trace startup image_transport报错/pose paired0仅S1报告，失败日志收据/新库patch未上target，不根因实证；rospack查询成功不等宿主fork环境有效。S2先失败原件/真实进程环境最小修正，证据前不第三次盲重跑，其余15h工作继续，S3现在确认正常校准/label范围、复用实现准备同新trace对照。现可解除依赖不自动全面重大阻塞；真需用户选择/超授权或证据不可得，立即中文GitHub按模板告知，未阻工作继续。S1共享检测/native归宿单写，1研究+2集成/无Codex/参数停，四Cron单owner，完整人口风险UNKNOWN成本/命令原件逐项自检，A/B局部不总分/review SSH/private不合main改算法历史。

源码主会话正常控制实际复现：SE3 Log漏平移Jacobian（.2rad/.1m输出(.1,0,0)非(.0996664,-.01,0)）；整块11缺行而10/12ALARM/NORMAL跨gap累计；left/world READY但P无frame绑定、右eI直接用P同场景score1而搬运.01。S3最低修Log/空块断dwell保last_suspect、S1/S2/S3实际cov扰动frame对应，不以阈值补偿；真实caller还未交，不指控实际host已错判/T0全UNKNOWN无效，不阻现trace环境最小解除。只读代理误fork审阅流程已披露，主会话亲核源码和三控制，无host/算法修改或新Codex角色。

## 124. 审阅在 ALI-H 实现中复现三个真实缺陷；S1 本机复现其中两个并退回 S3

审阅 `febf68d`（已合入 main `2b60ec3`）对 `docs/ali_h_v1_research/` 做了独立只读复算，指出三个缺陷。S1 本机复核：

| # | 缺陷 | 本机复现 |
|---|---|---|
| 1 | `e_i()` 的平移漏 `V⁻¹`：返回 `[so3_log(R), D[:3,3]]`，正确应为 `ρ=J_l(ω)⁻¹t` | `Rz(0.2)`+`t=(0.1,0,0)` → 正确 `(0.099666444, −0.01, 0)`，现实现 `(0.1, 0, 0)`；selftest 把错值写成预期 |
| 2 | 整块缺测仍跨空窗累计 dwell | 块10 M=ALARM、块12 M=ALARM、无块11 → 复现输出块12 `SUSPECT`（应 UNKNOWN）；`block_summary` 不补空块、`classify_blocks` 不检查相邻 |
| 3 | validator 的 READY 不证明协方差与残差同切空间 | 代码可核：`e_i` 固定算右残差，manifest 声明 `left/world` 仍可 READY，`s_i` 直接用传入 P；未声明转换 |

影响：缺陷 1/3 影响一切 T2 计分，缺陷 2 影响 SUSPECT/NORMAL 的持续性与 UNKNOWN 时长；**T0 的 UNKNOWN 结论不受影响**
（它是缺项结论，不依赖分类路径）。已要求 S3 修实现与 selftest 预期、补空块、明确 frame/perturbation 对应，并**现在就确认
现有资料可支持的正常/异常范围与出处**；若现授权内拿不到，按 15h 任务写中文重大阻塞（选项 A/B），不等 trace 才发现。

**宿主侧**：本机无新 run、无进程；两次 FAIL（`100744Z`/`101116Z`）仍只在本机 `/tmp` 与开发回报中，未入仓库，
按审阅记 DEVELOPER_REPORTED；诊断构建 A 的探针证据未到。

## 125. 诊断构建 A 结果：故障非 v7 独有，v6 本身在 teardown 也 stack smash；批准 B1 二分

S2 的探针（无 bag）已在 `host_change_trace_cov/probe_*` 归档，本机抽核：`probe_v6` 尾行 `*** stack smashing detected ***`、
`probe_v6min`/`probe_v7` 尾行 `No plugins found!`，与 S2 报告一致。

| 探针 | 库 | 结果 |
|---|---|---|
| `probe_v6`/`v6b`/`v6_default2`/`v6_omp1`/`v6_omp4` | `ca9126c4…`（与部署**逐字节相同**） | 5/6 通过（20–25 s），但**通过者也在 teardown smash** |
| `probe_v6min`（`env -i`） | `ca9126c4…` | FAIL rc=134 @14 s，`No plugins found!` |
| `probe_v7` + 三次复跑 | `0308c216…` | **4/4 FAIL**（3–15 s 内），同位置 |

结论修正：**不是 v7 独立引入**——v6 重建与成功 run 的库逐字节相同，仍会失败（1/6）；**v7 把失败率放大到 4/4**。
同一二进制同一 env 症状在 rospack 错误 / terminate / stack smash 之间变化 → 进程内内存损坏或竞态，不是配置或缓存。

S1 决定：批准 **B1 二分**（先 `voxel_map.{h,cpp}`、再 `LIVMapper.h` 成员去掉 `pnh`、最后只 `pnh` 读取；每步 5 次探针，
预算 ~5 min）；**B2 暂不批准**（v6 可复现且仍偶发，clean 重建大概率无收益）；新增一次性 **ASan 构建**定位既有 stack smash
（本机无 gdb/valgrind，core 落 `/tmp/core-file/`，预算 ≤10 min，产物不用于正式 run）；**R 启动探针门控重试**批准，
但须 B1 之后、off/on 同协议同 k、每次 run 前 5 次探针且通过率 ≥4/5。22:00 前若仍无可稳定运行的 v7，按 15h 规则提交
中文重大阻塞（A 修宿主缺陷 / B 降级为无 trace 有限结果 / C 换宿主），不无限二分。

## 126. ALI-H 三缺陷已修并本机复现验证；「无独立正常参照/标签」重大阻塞已登记（待用户确认）

S3 HEAD `72284f7`（`exp/ali-h-v1`），本机独立复现：

| 缺陷 | 修正前 | 修正后（本机实测） |
|---|---|---|
| D1 SE(3) Log 平移 | `(0.1, 0, 0)` | `(0.09966644, −0.01, 0)` ✔（`ρ=V⁻¹t`） |
| D2 缺块 dwell | 块12 = SUSPECT | 块12 = UNKNOWN；块 8/9→NO_DATA(10)→11 也给 UNKNOWN 且 `last_suspect_block=9` ✔ |
| D3 切空间 | left/world 也 READY | 协方差可用须 `perturbation=right`、`frame=pre_body`，否则 INCOMPLETE ✔ |

自测：T1 **7/7**、T2 prep **14/14**、TO 帧数不变（A 402/90 块，B 544/120 块，多出的 1 块是补齐的 NO_DATA）。
已 `--no-ff` 合入 main，仓库测试 **202 OK**。

**重大阻塞（已按 15h 模板中文登记）**：`docs/ali_h_v1_research/重大阻塞记录.md`，ID
`ALI-B2-NORMAL-LABELS-20261112-01`，状态等待用户确认。本机核实其依据成立：
- 402/544 两份 receipt 的 `injection` 均为 `NONE`、`sigma_meas_m=0.884`——无注入不是正常真值；
- `reference_map_20261112_redo` 为 `detection_enabled=false`、`sigma=0.12`，无逐帧 availability，不能借分布；
- `B5_B7_STATUS.md` 归档扫描无「身份+决定+独立标签」记录；KITTI reserve 未下载。

影响：`NORMAL_CONSISTENT`/`SUSPECT`、误报、漏检/延迟、错误 NORMAL 一律 `NOT_EVALUABLE`；T0/T1/契约/协议与
「UNKNOWN 区间 + 资格」可继续。选项 A（用户给独立正常前缀+事件标签）/ B（授权自注入标签仅离线 + 独立确认正常前缀）/
C（不新增数据，只交资格/UNKNOWN）。**S1 不代替用户选择**；trace 依赖单列 `ALI-B1`，仍由 S2 处理。

## 127. 合入两小时总结；join 规则增加"扫描身份"限制；宿主无新运行

审阅 `15e74fc` 发布 `docs/MAINLINE_CHECK_20261112_1837.md`（两小时总结），已 `--no-ff` 合入 main。其要点与本机状态一致：
受控原生边界有实证进步（cp 早隔离起点 15.918/12.414 ms、23 修复、794 组重放），但自动检测效果、拒绝后历史归宿、
真实 I trace 仍未闭合。

**新的使用限制（已转给 S3 修订预注册协议）**：`scan_stamp_ns`（header 精确 ns）与 `last_lio_update_time`（更新/分组
末时刻）是不同物理量；头/末戳不等或 offset 非恒定**不**证明无法关联，恒定 offset 也**不**证明同一扫描。最低要求：
导出原始 scan 身份 + native group/update/phase 对应，join 须"身份对应 + 时间对应"两条同时成立，缺一记
`join_key_unresolved`；不得删变 offset 数据凑人口、不得 nearest 猜帧。

**宿主**：本机无 `fastlivo_mapping`/`recovery_node`/`rosbag play` 进程，无新 run 目录（最新仍是两次 FAIL 的
`100744Z`/`101116Z`）；S2 的 B1 二分/ASan 结果未到，记 NOT_EXECUTED。

## 128. B1 定位到 `LIVMapper` 新增 `ofstream` 成员的布局变化；修复后探针 5/5；批准 R

S2 的 B1 结果（本机核归档）：`probe_b1b_1` 在启动期 `No plugins found`；`probe_v7s_1..5` 的 `result.txt` 均为
`PASS alive 25s`，但 `host.log` 末尾**仍是 `stack smashing detected`**；当前 `devel/lib` 库 sha `007c3bdc…` 与回报一致；
`LIVMapper.h` 相对 v6 只多 `bool trace_cov_en` + `long trace_cov_rows`，`ofstream` 移到 `LIVMapper.cpp` 文件级 static。

| 步骤 | 组合 | 通过/5 |
|---|---|---|
| v6 基线 | — | 5/6 |
| B1a | v6 + `voxel_map.{h,cpp}` | 5/5 |
| B1b | v6 + `LIVMapper.h` 成员（含 ofstream） | **0/5** |
| B1b1 | 只加标量成员 | 5/5 |
| B1b2 | 只加 `ofstream` 成员 | **1/5** |
| 修复 | v7 全量 + 文件级 static 流 | **5/5** |

结论：触发点是**类布局变化**放大了既有的启动期内存故障，不是 v7 逻辑本身；修复只恢复布局，**底层损坏未修复**
（所有通过探针在 teardown 仍 smash）。已批准 S2 按 R 开始 off/on 两次：同一 build `007c3bdc…`、同 bag/config/触发、
同 k、每次 run 前 5 次探针 ≥4/5、结束后立即复制 `mat_pre/mat_out/trace_cov` 并算 sha256、报告两次帧数/决定/lifecycle
一致性；run 中途 smash 则该次数据无效；任何一次启动失败即停下先做 ASan（≤10 min）。

## 129. trace-off 对照 run 成功落地（布局修复后）；等 trace-on

`fl_native_20261112T111325Z_435333`（19:13–19:15，S2 按 R 执行）：`status OK / all wiring checks passed`，
库 `007c3bdc…`（布局修复后的 build），driver `a4aaa58b…`，detection off，scripted 两事件。

| 项 | 实测 |
|---|---|
| paired | 536 |
| E1 | 23 帧候选；`replay_suffix=651`，`native_writeback_skipped`（正确，宿主已越过候选窗口） |
| E2 | 拒绝 + 1 次 restore；生命周期 2×`wait_limit_closed` + 2×`rearm` |
| 终态 | `HEALTHY`、`open=false`、trusted kf 260、cp failures 0 |
| 归档 | `host_logs/mat_pre.txt` 与 `mat_out.txt` 已复制，sha 与 `Log/` 一致（`3e03ffb6…`） |

`episode_detail` 中无 `restore_disposition` 属预期（该字段在 main 后续提交，S2 的 driver 仍是 `a4aaa58b…`），
不影响 trace run。此 run 记为 trace 开关的 **off 基线**；trace-on 尚未开始，T2 仍 BLOCKED。

## 130. trace off/on 两次 run：off 有效、on 无有效 replay；发散读数需按 replay 段判读

S2 按 R 完成两次 run（同 build `3b26365f…`、各 5 次探针 5/5）：

| | trace-off `112254Z_445825` | trace-on `112753Z_454009` |
|---|---|---|
| 状态 | OK / wiring passed | OK / wiring passed |
| paired | 544 | 544 |
| 门 | accepted 1（committed 23）/ rejected 1 | 同左 |
| 原生 | replay 244 within + 439 suffix，repairs applied **23**，无 set_state | replay **0 within + 151 suffix**，repairs **0 / dropped 23（spans=0）** |
| 终态 | HEALTHY / kf 285 | HEALTHY / kf 227 |
| trace | 无 | 968 行（6 表头 + 962 数据），sha `88866357…`，`idx 0..961`、`has_out=1` 895、`phase=1` 76、`grp_idx 0..1770` |

**读数更正（S1 复算）**：S2 报告的"host pos"列错位——`mat_out` 列为 `time, euler°(3), pos(3), …`，其数值首项是偏航角。
按 `pos=v[4:7]` 复算：off 首段最大 179 m、**replay 段 7–23 m 正常**；on 首段最大 **1998 m**，且只有 76 行 phase=1、
无完整 replay。首段发散是受注入污染、设计上要被回滚的那一段，真正的判据是回滚后的 replay 段。

**判读**：on 这次不是"宿主运行期不稳定"，而是 **trace-on 下修复匹配失败（`spans=0`，23 条修复全丢）**，replay 重放
未修复数据所以发散未终止；同 build 的 off run `spans>0`、修复 23 条，构成对照。最可疑机制是 trace 每行 `std::endl`
逐行 flush 改变扫描分组/span 采集时序。已要求 S2：① trace 改缓冲写入后重跑一次；② 核对 E1 reprocess 使用的
checkpoint 是否为其 armed stamp（其报告称落在"第二段 checkpoint frame 552"，若属实优先级高于 trace）。
**B（盲重跑）与 C（重大阻塞）暂不采用**，等这两项结果。

## 131. 缓冲 trace 修复后 run 通过本机核对；phase 列不可用、尾段发散；要求 availability 配对与原件上传

S2 按"缓冲写入"修复后重跑 trace-on：`fl_native_20261112T113855Z_464306`，库 `49f2f941…`，driver `a4aaa58b…`。

| 项 | 本机核对 |
|---|---|
| receipt | `OK / all wiring checks passed`，paired 544，终态 HEALTHY/open=false/kf 293 |
| E1 reprocess | stamp `1627785272199251712`、frame 163（= E1 checkpoint，回到 off 的行为） |
| 修复 | `repair_applied=23 / dropped=0`（旧 on 为 0/23、`spans=0`） |
| replay | 244 within + 400 suffix；replay 段中位 \|p\| **8.3 m**（旧 on 363 m） |
| trace | 1213 行（5 表头 + 1208 数据），sha `55a75615…` |

**仍存问题（已退回 S2）**：
1. **`phase` 列不可用**：replay 前 489 行中 431 行 `phase=1`；追平后 398 行中 388 行仍为 1。可靠身份是 `grp_idx`——
   1208 行里 322 个 `grp_idx` 各出现 2 次、两次 `abs_ns` 完全相同；S3 将用 `grp_idx` + 出现序号做身份。
2. **尾段发散**：`mat_out` 在 t≈54.1 s 后 \|p\| 从 ~3 m 跳到 206 m，末行 **519.9 m**；发生在 E2 restore（rel≈41.3 s）
   之后十几秒，终态仍报 HEALTHY。解释清楚前，该 run 只能用于 trace/修复/replay 段证据，**不能用于"连续接回正常"**。
3. **无 availability 日志**：目录中没有 `availability_frames.jsonl`，S3 的 T2 join 无法进行。已批准在 `49f2f941` 上再跑一对
   **off/on 且都开 availability**（同 bag/config/触发/k、新 run 身份、5 次探针 ≥4/5）。
4. **原件未入 Git**：审阅 `8676ad7` 将上述全部记为 DEVELOPER_REPORTED，要求上传布局 diff、探针输出、off/on receipt 与
   `host_logs`+SHA。已要求 S2 推到远端分支（非 main）。

## 132. 更正 §131 的 phase 误读；归档已推送；availability 采用 detection-on

1. **phase 列更正（S1 读数错误）**：trace 列序为 `idx(0) rel_s(1) abs_ns(2) grp_idx(3) scan_first(4) scan_last(5)
   has_out(6) phase(7) eff(8) …`。§131 中"431/489 行 phase=1"实为 `has_out`；正确统计：**`phase=1` 共 322 行，
   恰为第 489–810 行（replay 窗口）**，`has_out=1` 1087 行。`phase` 与 `grp_idx` 均可靠，S3 可按名取列。
2. **归档已推送**：S2 在 `/tmp/wt-sim` 分支 `exp/trace-cov`（提交 `70732b9`，253 文件/~2.3 MB）包含 v6/v7/v7u 快照、
   `trace_cov_v7u.diff`、构建日志、全部 probe 目录、off/on/无效 on 三个 run 的 receipt 与 `host_logs`+SHA。
   已由 S1 用内联认证推到 `Evenstar-E/slam_recovery`（远端新建分支 `exp/trace-cov`，`.git/config` 无 token）。
3. **尾段发散解释接受**：replay 窗口 489–810（rel 11.19–32.61）→ E2 为 restore 无 replay → live 在回滚地图继续，
   `catch_up=NOT_IMPLEMENTED`；`mat_out` 于 rel≈54 s 起发散到 519.9 m 与该机制一致。结论限定：该 run 支持
   trace/修复/replay 段证据，**不支持"连续接回正常"**。
4. **availability 决策：采用 `--detection on`**。旧 402/544 归档本身为 `detection=on`；detection off 的 availability
   只有 `status=DISABLED` 且 `support` 为 null，无法做旧方法对照。已批准 S2 在 `49f2f941` 上跑
   **detection on + AVAILABILITY + TRACE_COV off/on 各一次**（同 bag/config/k、新 run 身份、5 次探针 ≥4/5）；
   detection on 下若出现脚本外自动触发，照实记录。S3 拿到后先核 run id/build/input 与 `status` 非 DISABLED。

## 133. S3 的 T2 契约已对齐实际 trace 列与 detection-on，本机核过并合入

S3 HEAD `65f54d5`（`exp/ali-h-v1`）。本机核对：
- 列名对齐：`idx/rel_s/abs_ns/grp_idx/scan_first_ns/scan_last_ns/has_out/phase/eff/vec6/Ppre/Ppost/mat_pre/mat_out`
  （`REQUIRED_EXPORTS` 与实际 trace 一致）；`grp_idx` 作物理扫描身份、`phase=1` 为 replay 窗口、`has_out=1` 才可算 I。
- detection/availability 校验：`detection="off"` → `INCOMPLETE`（`detection-off availability has only DISABLED rows`）；
  `availability.status_not_disabled=false` → `INCOMPLETE`；`support_non_null=false` → `INCOMPLETE`。
  合法 manifest（detection on + availability 正常 + 无协方差）→ `READY_UNIT_ONLY`。
- §1.4：块不跨 phase；E2 后 rel≈54 s 的发散单列 `POST_E2_NO_CATCHUP`，不进入 NORMAL/SUSPECT/错误率。
- 自测 T2 prep **18/18 PASS**，真实 T2 仍 `NOT_EXECUTED`。

已 `--no-ff` 合入 main，仓库测试 202 OK。T2/T3 继续 BLOCKED（等 detection-on 配对 run 与 `ALI-B2` 用户选择）。

## 134. detection-on 配对 run 落地：T2 输入可用；join 改为"跨度包含"；归档已推送

S2 在 `49f2f941` 上完成 detection on + availability + trace 的 off/on 各一次，本机核对：

| | off `115203Z_476840` | on `115734Z_483777` |
|---|---|---|
| paired | 544 | 532 |
| gate | accepted 0 / rejected 5（全 Mode3） | accepted 1（committed 42）/ rejected 5 |
| 脚本触发 | 两个都触发 | 只触发第二个 |
| 终态 | HEALTHY / kf 112 | **WAITING_FOR_EVIDENCE** / kf 60 |
| availability | 542 行 | **531 行（351 AVAILABLE / 180 UNAVAILABLE，support 531/531 非空）** |
| trace | — | 1047 行（5 表头 + 1042 数据），sha `8c0d6a24…`；`phase=1` 156、`has_out=1` 975 |

**join 实测（S1 复算）**：`scan_stamp_ns` 与 `scan_last_ns` 精确相等仅 1/531；但 **531/531 满足
`scan_first_ns ≤ scan_stamp_ns ≤ scan_last_ns`**——语义是"合并组包含该扫描"，多对一。已要求 S3 用跨度包含、
`grp_idx` 记身份、`abs_ns` 记时间，未落入任何跨度的记 `NO_TRACE_ROW` 并进分母，不用 ±1 ms 近似。

**用途限制**：on run 被接受段 `repair_applied=0 / dropped=42`（detection on 抬高负载、命令迟到，reprocess 落 frame 552），
因此该 run 不能用于"修复收益"结论；per-frame 证据不受影响。S1 已向 S2 提出新方向：宿主**单 checkpoint 槽**可能被
自动触发的新快照覆盖，是"脚本段 armed checkpoint 丢失/迟到落错 frame"的同一根因，优先于再补 trace run。

**归档**：`exp/trace-cov` 已推至 `ffd4b13`（含两次 detection-on run 的 receipt/run_summary/wiring/
`availability_frames.jsonl.gz`/`host_logs`/SHA256SUMS），`.git/config` 无 token。

## 135. 单 checkpoint 槽根因确认；S1 实现驱动侧 checkpoint 校验；下一轮走纯在线触发

S2 定位（本机看 `run_summary.lifecycle.native_checkpoint_actions` 与 ack 原文一致）：宿主**只有一个 checkpoint 槽**
（`cp_state_/cp_state_propagat_/cp_map_`，`snapshotCheckpoint()` 无条件覆盖，命令不带身份）；延迟命令队列是三个 deque、
FIFO，没问题；**自动触发段不拍自己的快照**（`_open_episode` 只做 `expire_pending` + `hold`），所以拒绝时 restore 到槽里
最新那份——在 scripted 混合 run 里就是 E1 的 armed 快照（frame 163）；迟到时该槽已被 E2 快照覆盖，reprocess 于是落在
frame 552（`repair_applied=0 / dropped=42`）。这统一解释了 `115203Z` 全拒、`115734Z` 只触发第二个戳、以及修复全丢。

**S1 实现（driver 侧，行为不变）**：新增
- `_checkpoint_expectation(ep)`：scripted 段期望戳 = `trigger − confirmation_margin`；在线段返回 None（不臆造）；
- `_record_checkpoint_check(ep, action)`：从 ack 解析 `stamp_ns=`/`frame=`，写 `ep.meta["checkpoint_check"]`
  = `{expected_stamp_ns, actual_stamp_ns, actual_frame, status: MATCH/MISMATCH/EXPECTED_UNKNOWN}`；
- `run_summary.lifecycle.checkpoint_checks` 汇总各段结果。
- 测试：`test_a_restore_on_a_different_checkpoint_is_marked_as_a_mismatch`（MATCH 与 MISMATCH 两例）、
  `test_an_online_segment_has_no_expected_checkpoint_stamp`；全量 **204 tests OK**。

**决定**：暂不做 (a) 多槽身份化（host+协议 ~100 行、需重过版本链）；不采用 (c) 抑制自动段（会改变验证面）。
下一轮验证用**纯在线触发**（无 scripted）的 detection-on run：滚动快照提供槽，每段的 `checkpoint_check` 如实记录
回滚点与期望是否一致；混合模式下的 `115203Z`/`115734Z` 自动段结论按"回滚到非本段 checkpoint"标注，不再用于收益统计。

## 136. 纯在线自动链 run 落地：5 段自动触发、1 段接受且修复 42 条生效；scan_first 为哨兵需更正

**run `121127Z_497953`（S2，新 driver `19496a7`、库 `49f2f941…`、无 scripted、detection on、trace+availability）**，本机核对：
`status OK`、paired 529、终态 HEALTHY/open=false/kf 182；门 **accepted 1（Mode2，committed 11）/ rejected 3 / errored 1**；
`checkpoint_checks` 5 段全 `EXPECTED_UNKNOWN`（在线段期望值按设计未知）；被接受段 **`repair_applied=42 / dropped=0`、
replay 759 within + 615 suffix**——首次"自动检测→接受→修复→replay"全链路真实生效；trace 1574 行（5+1568）、
sha `435fff50…`、`has_out=1` 1439、`phase=1` 682；availability 194 AVAILABLE / 335 UNAVAILABLE。
归档已推：`exp/online-trace`（`7814502` runner + `e991eaf` run）。

**缺陷（未修，只定位）**：`cand_0004` 报 `RuntimeError: No active quarantine segment to validate`（ep4，41 帧候选，
决策时该段已不在 `active_quarantine`）。在修复前，纯在线的拒绝/接回统计须标注"含 1 段未决"。

**S1 更正（重要）**：`scan_first_ns` 在 `115734Z` 与 `121127Z` 的 trace 中**全部为 `-1` 哨兵**（1042/1042、1568/1568）。
此前 §134 的"531/531 落在 `[scan_first, scan_last]` 内"因此**不成立**（`-1 ≤ ts` 恒真）。有效的 join 是 S3 实现的
"上一个不同的 `scan_last` < `scan_stamp_ns` ≤ 当前 `scan_last`"；`scan_first` 要么补实现、要么在文件头标为不可用。
另：`115734Z` trace 最后一行只有 53 列（应 92），疑似退出未 flush 完整，已让 S2 查；S3 按 1041/1042 可解析处理。

**S3 的 T2（输入 `115734Z`）**：I 通道可用（504 行、Ppre 秩 6）、M 444 / T 86；120 个 0.5 s 块全 UNKNOWN；
51 行尾段单列 `POST_E2_NO_CATCHUP`；NORMAL/SUSPECT/误报/漏检/延迟/错误 NORMAL 因缺独立正常参照与标签
（`ALI-B2`）全部 `NOT_EVALUABLE`；该 run 的修复为 `applied=0/dropped=42`，不用于修复收益。成本 1.97 s / 218 MB。
S1 已更正 `e_I ≈ −vec6` 只在小增量成立（本批 |e| 最大 1.545），要求以 `mat_pre/mat_out` 的 `Log(inv(pre)·post)` 为主结果。

## 137. 纯在线缺陷已修（driver 跳过已关闭段）；S3 的 T2 改用精确 e_I；scan_first 确认为该模式写 0

**S1 修复（driver，10 行量级）**：`Episode` 增加 `segment_id`（开段时记录），`decide()` 在评估前检查
`tx_mgr.active_quarantine` 是否仍是该段：若已关闭（wait-limit 关闭后决策仍在队列），写
`ep.meta["decision_skipped"]="SEGMENT_CLOSED_BEFORE_DECISION"` 并跳过，**不再抛 `RuntimeError` 计成 errored**。
两个测试（已关闭段跳过且不调用 gate/restore；活动段仍正常评估），全量 **206 tests OK**。

**S2 的只读定位（已核，接受）**：
- `scan_first_ns` 恒 `-1` 的原因不是读错：写入点 `LIVMapper.cpp:2079` 取 `lidar_frame_beg_time`，而 m2dgr 配置下该值为 0
  （源码注释 `:824`），trace 把非正值映射为 -1。**该列当前不可用**，join 只能按"上一个不同 `scan_last` < stamp ≤ 当前 `scan_last`"。
  最小修法约 4 行 + 一次重建/run，暂缓（join 已有可用替代）。
- 末行截断是 SIGTERM 杀死缓冲写、停在行中间：`113855Z` 1207×92+1×44、`115734Z` 1041×92+1×53、`121127Z` 1568×92（无截断）。
  读取端规则：**丢弃列数 <92 的行并计入 `TRUNCATED_ROW`**；S3 已照此实现（1/1042）。

**S3 的 T2 更新（`975aa5a`）**：
- `TRUNCATED_ROW=1` 进分母，可解析 1041/1042；
- e_I 改为按 `StatesGroup::operator-` 的精确式：`vec6=[Log(R_postᵀR_pre), pos_pre−pos_post]`，`e_I=[−w, −R_preᵀv]`，
  用 `M2DGR_room_02.txt` 的 post 四元数（975 行，时间差 ≤512 ns）；`−vec6` 只作对照。精确 vs 近似：`|e|` 范数相同，
  平移方向差中位 0.0096 m、最大 2.64 m，475/504 行 >1%；`s` 中位 73.0 vs 66.9。
- 多对一结构：590 个不同 `scan_last` 中 295 个由 2 个 `grp_idx` 共享；trace 每组行数 1:217/2:276/4:37，availability 1:296/2:117。
- 结论不变：M 444、T 86、I 504（秩 6）、120 块全 UNKNOWN、51 尾段行单列、分类/错误率 `NOT_EVALUABLE`。
- 待 S2 确认：`M2DGR_room_02.txt` 是否为 `state_` 的 post 位姿、且与 trace `abs_ns` 同帧（S3 按顺序对齐）。

## 138. `M2DGR_room_02.txt` 语义已确认（P⁺、LIO 路径、同帧）；trace 分支已推送

S2 回答、S1 核源码（`LIVMapper.cpp:603` 的 `pose_output_en` 块位于 `StateEstimation` 之后，写 `last_lio_update_time`
+ `_state.pos_end` + `_state.rot_end` 四元数，只有 LIO 路径写）：

- `host_logs/M2DGR_room_02.txt` = **P⁺（更新后）位姿**，body→world，列 `abs_time_s x y z qx qy qz qw`；
  与 trace 的 `abs_ns` 同源同帧，实测时间差 ≤512 ns（double 秒量化/ulp，不是漂移）。
- 与 `Log/pcd/lidar_poses.txt` 不是同一份（后者用 `measures.back().lio_time`、仅 `pcd_save_en` 时写）；pre 位姿在
  `mat_pre.txt`（含 VIO/LIO 双写，handler 不可区分）。
- 对应规则：**按时间 join，不按行序**；只对 `has_out=1` 的行用 `P⁻/P⁺/vec`（`121127Z` 有 5 个戳在 pose 有、
  trace `has_out=0`）；replay 也写进两份文件，用 `phase` 区分。

S3 因此可解除 `PENDING_POSE_SOURCE_CONFIRMATION`，但须按上述三点重算。归档推送：`exp/trace-cov` → `290aae8`
（含 BUILD.md 的 `scan_first` 哨兵与截断行说明），`exp/online-trace` 远端 `e991eaf`；`.git/config` 无 token。

## 139. 审阅对真实 trace 的独立读回：join 仅机械匹配、约定为混合；批准最小导出修复

审阅 `fa35519`（已合入 main `c96d756`）独立读回三个 run 的 trace/availability，结论与本机一致并更严：

- **join 未成立**：`scan_first` 全 -1 → 有效跨度 0/531；"上一个不同 `scan_last` < stamp ≤ 当前 `scan_last`"在实际数据里
  产生 296,310 条候选边、530/531 多义、1035 个 trace 行机械涵盖多条 availability。属机械匹配，**不是 source membership**。
  已要求 S3 把 join 标 `HEURISTIC_UNPROVEN`，结论条件于该映射，全部 531 行/多义行/`NO_TRACE_ROW` 单列。
- **约定是混合的**：归档源码 `include_common_lib.h.v7u:173–204` 显示 `rot=R*Exp(delta_rot)`（右 body 增量）、
  `pos=p+delta_pos`（世界加性）。S3 的 `e_I=[−w,−R_preᵀv]` 数学上等价于 `Log(T_pre⁻¹T_post)`，可保留，但报告须写明
  "源约定混合、平移显式转到 pre-body"，不得沿用"统一 body SE(3)"；协方差只能 `READY_UNIT_ONLY/NOT_AVAILABLE`。
- **`mat_pre/mat_out` 不是按行号同键的 SE3 文件**（LIO/VIO 双写、无 group/idx/phase 表头）；最终 v7u 完整 patch/源码
  未入 Git，绑定只能停在候选。

**S1 决定（调整上一轮"暂缓"）**：批准 S2 做**最小导出修复**——`scan_first` 在 `lidar_frame_beg_time<=0` 时回退到合并组首帧
header、并新增每组扫描成员数/首末；同一 build 顺带修截断（整行拼 `std::string` 一次写、runner teardown 先 SIGINT）；
一次纯在线 run 验证；同时上传 v7u 最终补丁与完整源码快照。预算 1 次重建 + 1 次 run。

**S3 的 T2 补充（已核并合入）**：UNKNOWN 108 块/54.0 s（单段）+ 12 块/6.0 s（`POST_E2_NO_CATCHUP`）；
I_s 中位 70.39（p90 413.8、max 5953.3）、|e| 中位 0.01827；M 444 / T 86 / neither 1，AVAILABLE 351 全 M。

## 140. S3 已把 join 降级为 HEURISTIC_UNPROVEN、e_I 写明混合约定；s_I 降为诊断量

S3 `8c60b76`（已合入 main），本机核对：
- `T2_PROTOCOL.md`/`T2_RESULTS.md` 均标 `HEURISTIC_UNPROVEN`，写清"每行/块/统计条件于该映射"，分母 531 保留、
  `NO_TRACE_ROW` 与多义行单列；审阅复算规模（296,310 边 / 530/531 多义 / 1035 行）与本机复算（295,779 / 529/531 / 1037，
  边界规则差异）并列。
- e_I 源约定写明为混合：`rot=R*Exp(d_rot)`（body 右增量）、`pos=p+d_pos`（world 加性）；精确 `e_I=[-w,-R_preᵀv]`
  显式把平移转回 pre-body；`Ppre/Ppost` 是混合约定块，**不作 e_I 已验证协方差**，只允许 `READY_UNIT_ONLY/NOT_AVAILABLE`。
- `s_I` 降为**诊断量**（`status=DIAGNOSTIC_ONLY_MIXED_CONVENTION_NOT_A_CHI2`）；I 主量改为单位权 `|e_I|²`
  （p50 3.34e-4、p90 3.69e-3、max 2.387）。
- 数值与人口未变：M 444 / T 86 / I 504；UNKNOWN 108 块/54.0 s + `POST_E2_NO_CATCHUP` 12 块/6.0 s；分类与错误率 `NOT_EVALUABLE`。

小请求（已发 S3）：在 `t2_summary.json` 的 `join` 里加 `status="HEURISTIC_UNPROVEN"`，便于机器读取与后续升级对照。

## 141. v8 导出修复生效（scan_first 真实、n_scans、无截断）；checkpoint 校验改为边界语义并修 ACK 迟到

**S2 的 v8（库 `1239f35f…`，`host_build_v8.log`，完整源码 `.v8` + `trace_cov_v8_full.diff` 366 行已入仓）**：
- `native_scan_first` 在 `lidar_frame_beg_time<=0` 时回退到合并组首帧 `frame_header_time`；
- 新增 `n_scans`（每组包含几条原始扫描）；
- 行写入改 `ostringstream` 一次写出；runner teardown 先 `kill -INT` 再 TERM。

**新 run `124217Z_521833`**（本机核对）：`status OK`、库 `1239f35f…`、driver `62c165d1…`（`a372557`）、paired 444、
门 **accepted 0 / rejected 2 / errored 0**、终态 HEALTHY/kf 238；trace **736 数据行、全部 93 列、`scan_first` 无 -1**、
sha `3728c94c…`；availability 444（**88 AVAILABLE / 356 UNAVAILABLE**）。
**覆盖不足如实记录**：bag 播满 59.98 s，但宿主只处理到 **rel 49.1 s**（上次为 59.8 s / 529 paired），
触发 2 段（上次 5 段）；本次数据在 0–49.1 s 内自洽、membership 证据完整，但**全程覆盖不成立**。

**S1 修复（driver，回应审阅 §3.1/§3.2）**：
- `_record_checkpoint_check` 不再在命令发出时复制标量（那时 ack 尚未到达，导致 `actual_stamp` 恒为 null）；
  改为持有 action 引用、状态 `PENDING_ACK`，在 `build_summary` 里 `_finalize_checkpoint_checks()` 从最终 ack 解析；
- 判定改为**边界语义**：scripted 边界 = `trigger−margin`、在线边界 = 该段 `quarantine_start_ns`；
  `actual ≤ boundary → AT_OR_BEFORE_BOUNDARY`（宿主复制"边界前最后已处理组"，构造上不会相等），
  `actual > boundary → LATE_AFTER_BOUNDARY`，无 ack → `NO_ACK`。不再用精确相等，也不加模糊容差。
- 新测试 3 条（边界前后、在线 qstart、ACK 迟到后补记），全量 **207 tests OK**。

**审阅 `646d4f2` 同时指出**（已接受）：ep0/ep1 实际 restore 晚隔离起点约 3.9 s（`ACK cp − qstart`），属**非可信回退**，
不能因改纯在线就认为回退合法；ep3 修复 42 条扫描全部落在声明注入窗**之后**，不能称"注入测量已修回"，
需 S1/S3 说明修复对象（点测量错误 vs 状态误差被转成点偏置）与正常后继误干预。

## 142. v8 join 升级完成（真实跨度包含）；本机复算与 S3 一致

S3 `5115387`（已合入 main）基于 v8 run `124217Z_521833` 升级 join。本机独立复算（读 run 原件）：

| 项 | 本机结果 |
|---|---|
| trace | 736 行、93 列、`n_scans` 全为 1、`scan_first==scan_last` **736/736**、`has_out=1` 669 |
| availability | 444 行（88 AVAILABLE / 356 UNAVAILABLE） |
| 跨度包含（`first−512 ≤ S ≤ last+512`） | **217 行 1 组、227 行 2 组、0 行未匹配** |
| 旧机械规则 vs 真实组 | 一致 **222/444**、不一致 222、无未匹配 |

`join.status` 在 v8 run 上为 `TRUE_SPAN_CONTAINMENT_WITH_512NS_QUANTIZATION`；v7 `115734Z` 因 `scan_first` 仍为 -1
保持 `HEURISTIC_UNPROVEN`，两 run 不混用。227 行的多对一来自**同一 scan 戳对应两条 LIO trace 行**（`n_scans=1`），
按实际关系保留、不拆组。

人口限制照实：本 run 只到 rel **49.11 s**、paired 444、2 段全拒 0 accepted，**不是 60 s 完整覆盖**，拒绝分布与
上次（5 段/1 accepted）不同；修复收益结论仍需区分"点测量错误 vs 状态误差"。

## 143. 在线路径的 checkpoint 回退被证为不支持：实测晚 qstart 3.77–4.23 s；已加机器可读标注

S2 用新 driver（`8d9cd0d`）跑纯在线 `125406Z_533623`（detection on、无 trace/availability、库 `1239f35f…`、paired 544、
accepted 0/rejected 4/errored 0、终态 HEALTHY）。本机核对 `checkpoint_checks` 与回报一致：

| ep | boundary（qstart） | actual cp | 晚 | 状态 |
|---|---|---|---|---|
| 0 | `1627785261507921600` | `1627785265275036928` | **+3.77 s** | LATE_AFTER_BOUNDARY |
| 1 | `1627785270114168549` | 同上（复用） | −4.84 s | AT_OR_BEFORE_BOUNDARY |
| 2 | `1627785288459063196` | `1627785292292419072` | **+3.83 s** | LATE_AFTER_BOUNDARY |
| 3 | `1627785302541834497` | `1627785306775187456` | **+4.23 s** | LATE_AFTER_BOUNDARY |

**结论（负结果，已写进代码与文档）**：在线路径下 rolling snapshot 每 2 s 发出，但宿主在**下一个已处理帧边界**才应用快照，
播放 backlog 下"发出"与"应用"相差数秒，槽里的状态时间戳因此晚于隔离起点。ep1 的 AT_OR_BEFORE 只是复用了 ep0 那份，
不是机制上正确。**当前配置不支持"回滚到不晚于 qstart 的检查点"**；要支持必须给在线 snapshot 带 `apply_stamp=qstart`
（与 scripted 同机制）或做带身份的 keyed checkpoint。

**S1 实现**：`_finalize_checkpoint_checks` 现在同时写 `rollback_support`：LATE → `UNSUPPORTED_AT_OR_BEFORE_QSTART`、
AT_OR_BEFORE → `WITHIN_DECLARED_BOUNDARY`、其余 `UNKNOWN`。207 tests OK。

**S3 同步**：trace 读取改按列名（v7 92 列 / v8 93 列共用）；`T2_JOIN_UPGRADE.md` 写明本 run `phase` 全 0、无 replay，
227 行多对一是**同 scan 戳的两条 live 行**而非 live+replay，可进逐帧资格人口但仍不拆组；v7/v8 并列表已建。
归档已推：`exp/online-v2` → `45d0fee`（远端新建）。

## 144. 在线回退负结果已归档；C′（保留 K 份带戳 checkpoint）只批"保留+报告"一半

S2 `8ca5575`（分支 `exp/online-v2`，已推）新增
`docs/review_20261112_four_host/ONLINE_ROLLBACK_NEGATIVE_20261112.md`：四段边界数据、结论、修复语义口径，以及
三个方向的评估——A（在线 snapshot 带 `apply_stamp`）无效（宿主不能按 stamp 回到过去）；B（episode-id keyed）
只解决身份不解决时间；**C′**（保留最近 K 份带时间戳 checkpoint，按"不晚于 S 的最新一份"选择）才是可能路径。

**S1 决定**：今晚只批准 C′ 的**低风险一半**——环形保留 K 份（默认 K=1，行为与现状一致）、ack/状态报告每份
stamp/frame/voxels/points/内存、**不修改 restore/reprocess 的选择语义**；driver 侧新增只读字段列出某段 qstart 之前
可用份数与最近一份 stamp。验证用 K=3 的纯在线 run（trace/availability 关、探针 5/5），只回答"能否找到 ≤ qstart 的
合法快照、内存代价、帧数/决定是否与 K=1 一致"。

**不启用**按 stamp 选择 restore（需 v9 与版本链，明天做）；若 K=3 下合法候选覆盖率为 0，则 C′ 也不成立，须报负结果
并重新考虑（更频繁 snapshot 或外部状态历史）。恢复语义一旦启用，回滚更远、`replay_suffix` 变大，代价须在明天量化。

## 2026-11-12 Codex 回复：ALI-B2 先核材料、条件式 B、后续 A、当前 C

用户在本 Codex 对话直接要求“你给一个你认为最合理的回复然后提交到github上，标注好信息”。
Codex 据此发布 [ALI-B2 路线回复](ali_h_v1_research/CODEX_REPLY_ALI_B2_20261112.md)，并向重大阻塞记录追加索引；
本次为文档交接，供参考，未运行宿主/注入/重放，未改自动化和科学门。

建议：当前按 C 如实报告资格与 UNKNOWN；S3 先核已有正常参照及已声明注入的实际证据，条件齐备且具体操作在现授权内时做有限 B，随后补 A 的真实场景验证；已有合格 A 则优先 A。
不把路线建议发布写成数据条件通过或用户无条件批准新运行。新的超范围动作仍须具体许可；已有明确授权步骤不再泛问 A/B/C。
原生恢复/接回/第二事件不因 ALI 标签缺项自动暂停；现有分工不变，不增等待 Codex 的执行前置。

发布前核到 `846d121`：承认 v8 对应关系升级的开发记录，保留其 49.11 s/444 paired 覆盖限制；旧 v7 未证明映射与正常参照/标签缺项分别记账。本轮未独立复算 v8，未调整 A/B 评分。开发接收/执行仍待实际回执。

## 145. Codex 的 ALI-B2 回复合入（属建议，不是用户批准）；summary 崩溃已修；K=3 首测结果

**Codex 回复**（远端 main `4b5e63c`，已合并）：`docs/ali_h_v1_research/CODEX_REPLY_ALI_B2_20261112.md`，记录用户原话
"你给一个你认为最合理的回复然后提交到github上，标注好信息"。**这只是建议与工作交接，不是用户对 A/B/C 的选择**；
`ALI-B2-NORMAL-LABELS-20261112-01` 状态**仍为等待用户确认**，S3 的分类/误报/漏检继续 `NOT_EVALUABLE`。
其内容与我们的判断一致：当前按 C 如实交付；先核已有材料（正常参照/事件依据/输入对应/覆盖/授权五问表）；
条件齐备后做一次预先声明机制的有限离线对照（B）；真实场景需 A 的独立证据。不新增运行授权。

**S1 修复（S2 报告的真实崩溃）**：`build_summary` 中 `ep.meta.get(...)` 在**未决策的段**上抛 `AttributeError`
（`Episode` 构造时无 `meta`），整个 summary 写不出、run 判 FAIL（`130945Z_560715` 即死于此）。已改为 `getattr`，
并新增回归测试 `test_summary_survives_an_episode_that_never_decided`；**208 tests OK**。

**C′ 低风险半（S2，库 `18e039e1…`、`host_build_v9c.log`）**：`~cp_history_k` 私有参数默认 1（与 v8 一致），
环形存储与计数全为 `LIVMapper.cpp` 的 file-static，**类布局与 v8 逐字节一致**（S2 先试成员版：启动探针 5/5 SIGSEGV，
改 file-static 后 5/5 PASS——再次验证"任何布局变化都会唤醒既有启动期内存故障"）；restore/reprocess 选择逻辑未改。
K=3 run `131213Z_563253`：paired 341、accepted 0/rejected 1、终态 HEALTHY；环形工作正常（`hist_bytes` 2.0→239 MB 估算）。
**但该 run 后段宿主地图失控**（frame 478→514：voxels 323k→453k、points 1.7M→2.4M、RSS 峰值 6.97 GB），
属已知运行期不稳定，**本次不能作 K=3 vs K=1 的干净内存对照**。
**唯一一段的候选分析**：边界 `…261.507921600`，实际用 `…264.873980928`（+3.36 s，LATE）；当时环形里有
`261.470954/frame 2` 与 `263.142319/frame 27`，**前者 ≤ 边界、是合法候选**，但早 3.68 s 且只是第 2 帧——
即 C′ 能找到合法快照，代价可能是回滚到极早期。多段覆盖率需在宿主不发散的 run 上统计。

归档：`exp/online-v2` → `f5212e5`（已由 S1 推送）。

## 146. 宿主可执行文件身份已变（重链，非代码改动）；v9 补丁入 Git；ASan 推迟到明天

**必须记录的溯源变更**：S2 尝试 ASan 构建时，`catkin_make` 在重链前删掉了旧的 `fastlivo_mapping`，链接因
"unsafe runtime search path" 失败；恢复时发现默认链到系统 libstdc++（GCC 11，缺 `GLIBCXX_3.4.32`），改用
`-L/home/R26534/mm/ros/lib` + `-L…/Sophus` 重新链接成功。本机核对当前部署：

| 项 | 现值 | 先前值 |
|---|---|---|
| `fastlivo_mapping` | **`6dd71953…`**（重链） | `0d7e23de…`（已删、无法还原） |
| `liblaser_mapping.so` | `18e039e1…`（v9c，未变） | 同 |

后果：**从此以后所有 receipt 的 `host_binary_sha256` 都会是 `6dd71953…`**；这不是代码改动，但**可执行文件的链接环境
（libstdc++ 来源）也与早先 run 不同**，因此今晚之后的 run 与早先 run 不能按"同一二进制"直接比较，须在报告里声明。
启动探针恢复后 5/5 PASS。

**ASan 推迟到明天**：真要做得让可执行文件与库同为 ASan 构建（或正确预加载 libasan）+ 新 libstdc++ 链接，约 20–30 min，
超出 ≤10 min 预算；S2 建议先备份可执行文件再动链接环境，采纳。

**运行期 map 膨胀的判读（S2 提出、S1 批准明天做）**：这次 K=3 run 是 frame 478 后 voxels 323k→453k，更像 LIO 匹配
退化后大量点写入地图（数值/几何问题），未必与启动期"环境被写坏/stack smashing"同源。明天先用**只读增长率判据**
（触发前 30 s 的 voxel/point 增速 + effective feature 数）区分"匹配退化"与"内存损坏"，再决定是否需要 ASan。

**v9 补丁**：`exp/online-v2` → `86bdf86`（`trace_cov_v9_full.diff` 465 行 v6→v9 + 5 文件完整快照），已由 S1 推送。
工作分支 `exp/online-v3` 从 `main@c915197` 建立、尚无提交。

## 147. 更正 §145 的 C′ 候选数字：合法候选只早 37 ms，不是 3.68 s

S2 更正并给出解析脚本 `docs/review_20261112_four_host/analyze_cp_candidates.py` 与
`cphist_fl_native_20261112T131213Z_563253/cp_candidates.txt`。本机核对该文件：

| ep | 边界 | 实际使用 cp | 状态 | 合法候选 | 候选−边界 |
|---|---|---|---|---|---|
| 0 | `1627785261507921600` | `1627785264873980928`（f53） | LATE | `1627785261470954240`（f2） | **−36.97 ms** |

原 §145 的"早 3.68 s"是把"实际使用的 checkpoint（264.874 s）"拿去减候选，混了两个量。**更正后**：C′ 在这一段
**存在时间上非常接近边界的合法候选**（37 ms），"早期 rolling 太稀疏导致时间不可用"的说法不成立；候选是 frame 2
只是因为该段在 run 开始 0.43 s 就触发、地图仅 4834 voxels——真正要评估的代价是**回滚后需重放的帧数与地图体量**，
不是时间偏移。明天的多段统计须同时记 `delta_s`（候选 vs 边界）与"候选 frame 与实际 frame 差"。

**补（S2 `53f5c2a`，已推）**：`analyze_cp_candidates.py` 与 `cp_candidates.txt` 增加 `cand_bytes`（候选体量估算）
与 `frame_gap`（实际 cp 与候选的帧差）；本轮 f2 候选 `cand_bytes=2,036,096`、`frame_gap=51`。
`BUILD.md` §8/§9 已写 `cp_history_k` 默认 1 的等价说明、布局/file-static 结论、37 ms 更正与可执行文件重链声明。

## 148. 审阅接受 37 ms 更正；但 K=3 run 的 driver 来源对不上（receipt ≠ main ≠ 工作树）

审阅 `164777d`（已合入 main）独立算得 hist frame2 比 qstart 早 **36,967,360 ns（−36.97 ms）**，与 §147 一致；
同时给出当前 C′ 的两条硬限制：
1. **历史条目不是可用的完整旧检查点**：`src_LIVMapper.cpp.v9:17–43,1002–1068` 的 `CpHistoryEntry` 只保存
   state/propagat/map/stamp/frame，**没有 `cp_last_imu`、`last_prop_end_time`、`acc_s_last`、`angvel_last`，也没有旧
   snapshot 的 replay capture**；snapshot 把旧 map move 进 history 后便 `replay_buffer_.clear()`。`restoreCheckpoint`
   与 v8 逐字相同、仍用当前槽。即"只保留+报告、不改选择语义"属实，但**要启用历史恢复必须先补齐配套状态与可重放区间**。
2. **来源对不上**：K=3 run `131213Z_563253` 的 `receipt.inputs.recovery_node_source` = `7cfcccf7…`，
   而 main 的 `recovery_node.py` = `c5efdd73…`、S2 工作树 = `a6c0380c…`（本机实测，三者互不相同）。
   该 run 不能算"c915 修后的原生验证"，须补实际执行源码/diff 后才能引用。

另：审阅指出 `restore_disposition.checkpoint_stamp_ns` 仍用 `trigger−margin` 而非实际 ACK，属已知口径问题（§85 已记）。
探针记录：v9=4 FAIL/1 PASS、v9b=5 FAIL、v9c=5 PASS——不能笼统说"任何布局变化必崩"，但 v9c 的稳定性仍只是启动探针层面。

## 149. K=3 run 的 driver 来源已查明并归档（8d9cd0d + 本地 getattr 绕过 = 7cfcccf7）

S2 `1fde521`（`exp/online-v2`，已推）归档 `docs/review_20261112_four_host/run_provenance_131213/`：
`recovery_node.executed.py`（本机实测 sha `7cfcccf7…`，与 receipt 逐字节一致）、`driver_patch.diff`（8d9cd0d→执行版，
21 行，仅 `checkpoint_checks` 的 getattr 绕过）、`run_native_loop.diff`（未提交的 `CP_HISTORY_K` 传递，31 行）、SHA256SUMS。

结论：该 run 执行的是 **`8d9cd0d` 的 driver + 本地绕过**，不是 `c915197`；S2 上一条"已切到 main@c915197"指的是之后的状态。
因此 `LATE_AFTER_BOUNDARY` 的计时结论仍有效（绕过只影响 summary 里 `ep.meta` 读取），但**该 run 不能标为"c915 修复后的验证"**。
S2 工作树当前基于 `8d9cd0d`，`recovery_node.py` 无未提交改动，`run_native_loop.sh` 有 `CP_HISTORY_K` 未提交改动；
明天第一个 run 前会切到 `main@05fd0a2` 并重记执行文件 sha。

C′ 限制与"布局敏感"表述已按 S1 要求收窄（不推广成"任何布局变化必崩"），并写进 BUILD.md §10。

## 150. 日报合入；`exact_e` 漏 SE(3) 平移 Jacobian（S1 复现，退回 S3）

审阅侧日报 `231de75`（`docs/daily_reports/2026-11-12-review.md`）已合入 main。其核心分层与我们的记录一致。
其中一条技术指摘经本机复现成立：**`t2_run.exact_e` 漏了 SE(3) Log 的平移 Jacobian**。

```
Tpre=I, Tpost=Rz(0.2)+t(0.1,0,0)
t2_run.exact_e     → [-0, -0, 0.2, 0.1, -0, 0]
t2_input_check.e_i → [0, 0, 0.2, 0.09966644, -0.01, 0]
diff               → [0, 0, 0, -0.00033356, -0.01, 0]
```

`exact_e` 返回的是"相对变换的旋转 + body 平移"，缺 `ρ = V(ω)⁻¹ t_body`；而 `t2_input_check.e_i` 是对的——
两模块不一致。已要求 S3 二选一（加 `V⁻¹` 并统一，或改名为 `relative_tangent` 并同时给真 Log），重跑 T2（1.97 s），
并把现有 `s` 中位 70.39 / `|e|` 中位 0.01827 标为"修正前"。另：`vec6` 在最终 solution 前保存、同次 pre/post 与
carryover 成员未证，记为 `NOT_VERIFIED`，不据它推 `e_I` 的物理意义。

## 151. `exact_e` 的 SE(3) Jacobian 已补，T2 重跑；本机复核一致

S3 `be8b955`（已合入 main）：`t2_run.exact_e` 改为先取 `rot=-w`、`t_body=-R_preᵀv`，再乘 `so3_left_jacobian_inv(rot)`，
与 `t2_input_check.e_i` 统一。本机复现同一例子：两者现在都给 `[0, 0, 0.2, 0.09966644, −0.01, 0]`。

重跑 T2（1.97 s）本机核对：`|e|` p50 **0.01826778**、p90 0.0607463、max **1.54511**；`s`（诊断量）中位 **70.31**
（旧无 `V⁻¹` 的 70.39 已标"修正前"）、p90 414.2、max 5955.1；phase0/1 中位 67.06/870.68；精确 vs 近似平移差中位
0.00948 m、max 2.645 m、475/504 行 >1%。文档已在 `T2_RESULTS`/`T2_INPUT_CONTRACT`/`T2_PROTOCOL` 补 `V(ω)⁻¹` 与修正日期；
`vec6` 标 `NOT_VERIFIED`（最终 solution 前保存、同次 pre/post 与 carryover 未证）。
人口与状态不变：M 444 / T 86 / I 504、120 块全 UNKNOWN、分类与错误率 `NOT_EVALUABLE`。

## 152. 审阅关闭 SE(3) 数学缺陷；仅剩 meta 文案待收口

审阅 `220c617`（已合入 main）独立执行了三个已读函数，复现 `rho=(0.09966644423259238, −0.01, 0)`，确认旧 `(.1,0,0)`
反例关闭；修正后保存值（`|e|` 中位 0.01826777741136127、max 1.545105747222006；`s` 中位 70.3133963953216、max 5955.053067343836）
与归档一致。其保留的限定与本记录一致：`vec6` 在最终 solution 前保存 → `NOT_VERIFIED`；协方差 `NOT_AVAILABLE`；
504 不是 504 个合格独立 I 证据；120 块全 UNKNOWN；无正常校准/标签 → 分类 `NOT_EVALUABLE`。

**剩余小项（S3，非阻塞）**：`t2_summary.json` 的旧 meta 字符串仍写 `e_i_convention`（漏 `V⁻¹`）与
`pose_source_status=CONFIRMED_POST_POSE_TIME_JOIN`；应随下次实质提交更新为与当前实现一致，避免机器读取时与正文冲突。
审阅也指出 RESULTS 里夹有旧"精确 I/跨度可用/尾 51"陈述，随同一提交收口，不为文案重跑数据。

## 153. I 资格收口为 INCOMPLETE/UNKNOWN；meta 与尾段口径已更正

S3 `932c07f`（已合入 main），本机核对：
- `_meta.e_i_convention` 现为完整表述（混合约定 + `rot=-w`、`t_body=-R_preᵀv` + `so3_left_jacobian_inv`）；
- `_meta.pose_source_scope` 注明 `CONFIRMED_POST_POSE_TIME_JOIN` 只对 v8 `124217Z` 成立、v7 仍 `HEURISTIC_UNPROVEN`；
- `_meta.i_qualification = INCOMPLETE/UNKNOWN`；新增 `T2_I_ELIGIBILITY.md`：source scan（v8）PASS、update 阶段 PASS、
  post 用 M2DGR P⁺ PASS；**pre 位姿 INCOMPLETE**（`mat_pre` 由 VIO/LIO 双写、无 handler 标签，`state_propagat` 未单独导出）、
  **`vec6` INCOMPLETE**（`voxel_map.cpp` L510 保存、L519 才 `state_ += solution`）、**协方差 NOT_AVAILABLE**；
- `T2_RESULTS` 加入修正前后两栏；尾段行数写明：按 pose≥54 s 为 **47 行**、按尾段块为 **51 行**（边界块含 4 行 <54 s）。

结论：`I_present=504` 是数值行数，**不是 504 个合格独立 I 证据**；解锁需 S2 提供最终 solution 位姿、带 handler 标签的
pre/post，以及声明切空间的协方差。

## 154. 真实 I 的三条导出已实现（v10，未跑 bag）；本机核对并推送

S2 实现（库 **`69dc8ac5…`**，可执行文件仍 `6dd71953…` 未重链；`host_build_v10.log` 两个 target 均 Built；启动探针
**5/5 PASS**），本机核对：

1. trace 行尾新增 7 列 `pose_x/y/z qx/qy/qz/qw`（`StateEstimation` 后、`_state` 定稿处），与同行 `abs_ns`、`Ppost6x6` 同帧；
   行宽 93→100；`vec6` 仍是更新前量、语义不变。
2. 新增 `mat_lio_pre.txt` / `mat_lio_out.txt`，只在 `handleLIO()` 写（源文件 `LIVMapper.cpp:359–360` 已核），
   共享的 `mat_pre/mat_out` 保持原样。
3. trace 文件头声明：协方差为 19 维状态中 rot+pos 的 6×6 块、**body(IMU) 切空间、右乘 SO(3) 增量**、pos 世界系；
   只有该约定下可作 `e_I` 协方差，否则 `NOT_AVAILABLE`。

归档：`exp/online-v2` → **`eb2630e`**（`*.v10` 五个源码快照 + `trace_cov_v10_full.diff` 493 行 + BUILD.md §11），已由 S1 推送。
**今晚未跑 bag**；明天第一个 run 会带出这些字段。跨今天的 run 与早先 run **不可按同一二进制比较**
（库 `69dc8ac5…`、可执行文件 `6dd71953…`、链接环境已变）。

## 155. 审阅复现 v10 消费缺口（100 列被两个 parser 判 malformed）；已退回 S3/S2

审阅 `480a038`（已合入 main `b3540f0`）本机复现：`t2_run.py:107` 要求 `len(f)==vec_start+78`（v8 的 93 列）、
`t2_join_upgrade.py:38` 只接受 92/93；v10 在 93 列后追加 7 个 post pose 标量 → 合法行 100 列，**现在会被判
malformed、0 rows**。这是本轮实证的最小接线断点（失败发生在值解析前，不是格式恶意）。

已要求：
- **S3**：两个 parser 接受 92/93/100、100 时按名解析尾部 `pose_x…qw`；新路径优先用同行 post pose，不再回落外部
  `M2DGR_room_02.txt`；加一个 100 列正常控制；并把 `T2_I_ELIGIBILITY.md` 中两处子 PASS 收窄——v8 carryover 的
  "PASS 单扫描"（`n_scans` 计新 pop 的 raw、carryover 在 cur/next，完整点成员未证）与 post 的"PASS 时间 join"
  （grp/首末戳不唯一对应所用更新）改为 `INCOMPLETE/ASSERTED_NOT_VERIFIED`。
- **S2**：`mat_lio_pre/out` 只有 `rel_s`，无法唯一配对 live/replay、重戳、空点早退与两个更新组；最小修法是每行加
  `idx/grp_idx/phase` key，或把 pre pose 直接写进 trace 同行。

审阅同时确认：v10 的 inline post pose 源码正确（`StateEstimation` 后写 `_state`）、构建与 5/5 探针档案限定通过、
协方差仍 `NOT_AVAILABLE_FOR_E_I`（声明文字不产生转换/相关性模型）。

## 156. v10 消费缺口已修：两个 parser 接受 92/93/100，同行 post pose 优先；资格两处收窄

S3 `f90a748`（已合入 main），本机核对：
- `t2_run.parse_trace` 与 `t2_join_upgrade.parse_trace` 按表头名接受 92/93/100；100 列时 `Ppost6x6` 之后的 7 个
  `pose_x…qw` 解析为 `pose_tail`；`python -I t2_run.py selftest100` 输出 `status=PASS, rows=1, malformed=[]`，
  `qw=0.92736185` 与输入逐位一致；
- 100 列路径**用同行 post pose 算 e_I，不再回落 M2DGR**；仅 92/93 旧行用 M2DGR 且只作交叉核对；meta 增
  `pose_source`/`same_row_post_pose_rows`；
- `T2_I_ELIGIBILITY.md`：v8 post → `ASSERTED_NOT_VERIFIED/INCOMPLETE`、v8 carryover → `ASSERTED_NOT_VERIFIED`
  （`n_scans` 只计新 pop raw、carryover 在 cur/next）；`mat_lio_*` 无 key 前不用于 I 资格。

v7/v8 数值与人口未变；分类/错误率仍 `NOT_EVALUABLE`。等 S2 的 v10 trace + `mat_lio_*` key。

## 157. v11：同一行 pre/post 配对（行宽 107）与带 key 的 `mat_lio_*`；开跑前置=消费端支持 107

S2 `c5bc057`（`exp/online-v2`，已推），本机核对：库 **`81b35f92…`**、可执行文件仍 `6dd71953…`（未重链）；
`LIVMapper.cpp:368` 头已含 `pose7 pre_pose7`；5 个启动探针全 `PASS alive 25s`；归档含五个 v11 快照 +
`trace_cov_v11_full.diff`（514 行 v6→v11）+ BUILD §12。

- **同一行 pre/post**：`pose7`（更新后）之后新增 `pre_pose7`（`StateEstimation` 前捕获），行宽 **100 → 107**；
  一行即"一次更新"的完整配对，不再需要行间 zip/时间近邻；早退帧也有 `pre_pose7`。
- **`mat_lio_pre/out` 加 key**：每行前加 `idx grp_idx phase`，可精确配对（仅作交叉核对）。

**风险与前置**：S3 的 parser 目前只接受 92/93/100，**107 会再次被判 malformed**。已要求 S3 加 107 档与 107 正常控制，
并优先用同行 `pre_pose7`/`pose7` 算 e_I（`vec6` 仅对照）。S2 已承诺：在 S1/S3 明确回"parser 已支持 107"之前不开跑，
且 run 结束后先本地按列名自检 107 可解析，失败先修 parser 不重跑。

## 158. 消费端已支持 107 列（v11 前置解除）；pre 资格标记为 PENDING_v11_RUN

S3 `129b184`（已合入 main），本机核对：
- 两个 parser 按表头名接受 **92/93/100/107**；`selftest107` 与 `selftest100` 均 `PASS`（`pose`/`pre_pose` 各 7 值逐位一致）；
- v11 路径直接用同行 `pre_pose7`/`pose7` 算 `e_I=Log(inv(pre)·post)`（含 `V⁻¹`），**不再依赖 `vec6`**；`vec6` 仅对照；
  100 列用同行 pose+vec6；92/93 旧行才回落 M2DGR 且只作交叉核对；meta 增 `same_row_pre_post_rows`/`same_row_post_pose_rows`；
- `T2_I_ELIGIBILITY`：pre/post 对 v11 标 **`PENDING_v11_RUN`**（真实 run 且同帧配对验证后升 `PASS_SAME_ROW`），
  v7/v8 仍 `INCOMPLETE`/`ASSERTED_NOT_VERIFIED`；`vec6` 仍 `NOT_VERIFIED`；协方差 `NOT_AVAILABLE`、I 主量单位权。

**S2 的开跑前置（"parser 已支持 107"）现已满足**。
