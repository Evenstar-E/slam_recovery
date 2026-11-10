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
