# slam_recovery 协作状态

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
