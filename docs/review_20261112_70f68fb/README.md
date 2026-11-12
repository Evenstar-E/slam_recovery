# 70f68fb增量审阅：原件缺口局部解除，原生接纳与可信检查点仍未闭合

- 读者：用户、开发主会话S1、原生宿主执行S2、门研究S3与独立复核者。
- 取证时间：2026-11-12 10:05–10:20（UTC+8）；目标 `70f68fbc3450569677659e8220d34fa2e3abaa4b`，比较 `ebf76f59993d9d2b965f0d8e29f9a6cb0d237296`。
- 本地工作树HEAD `305820052f8d34bf6b2f7d833d6ee74d400cc4c4`，独立分支 `review/repair-f3-handoff-20261110`；未merge/checkout目标。新目标生产模块与选定测试直接从Git blob在内存加载，其他package依赖经版本差异/工作树检查为未变。实际blob及SHA见[结果](local_checks.json)。
- 既有20分钟、两小时、每日任务仍属repair-f3，无可见repair-3e旧owner，不新增自动化。按用户指令忽略stop.md；算法、真实宿主由远端开发负责，旧参数任务暂停。

## 1. 本轮结论：部分推进，未完成实际修复整链

本轮不是“无增量”：`46d129d`公开实际部署补丁及旧受控运行原件，`62f294b`纠正部分门研究，`70f68fb`补接纳闭段的release事件。这些局部进展保留；不能再沿用旧“新宿主源码/受控run原件全缺”的结论。

但用户主线**实际测量修复→原生状态重估/内部地图写回→接回真实输入→第二事件及尾段**仍未验收。归档是旧d356逻辑的两次拒绝，不是70接纳release修后运行；repair_received/applied、reprocess、set_state均未在该链执行。新release补丁本机正常反例复现FAIL。

## 2. 可接受的局部解除与证据边界

### 2.1 实际部署源码公开

目标[deployed_host.diff](../review_20261110_native_checkpoint/deployed_host.diff)为1501行，Git blob `81b41945577f27238a944ae924c823e5de29c2cc`，实算SHA256 `b12ae153b242f0147b9646b2b460bee330ef23563d2f4cb8f9024f6cceea4036`。源码确有：

- hold控制初始建图、UpdateVoxelMap及mapSliding（433、447–464、940–952）；
- repair topic预处理、匹配替换以及replay估计前apply入口（491–661、751）；
- state/传播状态/voxel map/IMU跨帧量复制恢复、plane/子树复制、三朵cloud深拷贝（664–707、1107–1113、1402–1447）；
- 独立接收线程写received、主线程应用后写OK/FAIL（870–987、1012）。

配套native_checkpoint.h/.cpp哈希与DEPLOYED_CODE一致。接受“实现源码已公开”，不由此确认修复匹配正确、全状态等价或实际修复成功。普通正lio_time分支实际按group end前0.2s内最新repair匹配，并非一般严格scan-ID匹配；本受控run修复计数为0，匹配正确性仍UNKNOWN，不为潜在范围另扩大实验。

### 2.2 旧双拒绝运行原件可以核验

归档目录：[chain_run_fl_native_20261110T115717Z_3390402](../review_20261110_native_checkpoint/chain_run_fl_native_20261110T115717Z_3390402/)。只读核验目标Git blob：SHA256SUMS列26/26文件字节哈希一致；events/lifecycle与summary数组逐值一致。这是归档内部一致性，不是独立签名或源码→binary可重复构建证明。

receipt/source哈希将run绑定旧d356/c2b193c/ebf相同driver `09b495acd9f631d515485e8b997217f5700fc6f163ee43a7b73d6c1488ccce52`；70目标driver为 `fa3474edccdc56418cead767c37477399060ea3faada18e8a1e2c5094be07e7a`。binary/lib/config/bag哈希已记录，但实际字节未随包提供，全树重建本次未执行，独立构建绑定UNKNOWN。

原件支持：

- detection off、host_poses、预声明两个受控trigger；两候选均Mode3拒绝，accepted=0；
- 两组OK hold→restore→resume、两次wait_limit_closed→rearm；58/86帧unresolved，不能当恢复成功帧；
- 544 ingested、末尾kf543、wall约103.053s、终态HEALTHY无开放隔离；E2关闭后仍101诊断帧，持续输入/尾段事实有支持；
- 37快照尝试=30记OK+7 snapshot_ack_timeout，superseded=0、failures=7；其中最后timeout的残留ack证明后来仍应用，timeout不等宿主已取消/永久未apply；
- received时间是接收记录；ack_wall是driver观察OK时间，不是宿主精确apply时刻。旧毫秒级LIO原件未归档，旧慢LIO/超时唯一根因仍UNKNOWN。

纠正旧§50/§52与INDEX中的帧数解释：`consumed_after_first_decision=368`不能叫E1 decision→E2 trigger区间帧数；按原stamp该区间217帧、E1 decision后至末尾385帧。保留原数字，不改历史文件，只在本增量纠正口径。INDEX的t0与scripted首帧基准不同，15.082/42.426与14.678/42.022不混用。

## 3. 必须先做的最小保障：三个具体正常断点

### 3.1 接纳依赖尚未applied就发送resume：FAIL_REPRODUCED_LOCAL

目标recovery_node.py:1292–1299连续异步reprocess/set_state，service:1317在pending检查之前消费commit_closed，:1347–1350再发resume。共享cmd只有一格。

[本机控制](run_checks.py)用实际70 driver/client、模拟完整合法准入报告：旧host位姿x10/20，候选修复x1/2，两key准入。decide返回pending `[reprocess,set_state]`，物理cmd已是set_state，payload仍旧尾x20而非修复尾x2。下一次service在无任何reprocess applied ack时再写resume，pending成为 `[reprocess,set_state,resume]`，物理cmd=resume；即使提供OK resume，FIFO头仍等待reprocess，poll不完成。

这是普通慢宿主尚未取cmd的合法调度，不是恶意输入/假设并发；模拟gate不代表部署接纳实测。旧partial准入来源问题保留，不重跑全部旧例。

**最低解除（S1/S2）**：现通道真实single-in-flight；按实际applied成功推进reprocess及后继release，失败/未知不推进依赖动作。禁止旧ep.frames尾或deferred尾冒充已准入原生状态；实际修复必须支配deskew/估计/内部地图，直接灌ICP位姿不是替代。无需新RPC/通用事务框架。

### 3.2 旧关闭事件释放新隔离：FAIL_REPRODUCED_LOCAL

本机实际70 manager完成full commit发commit_closed，之后串行调用正常trigger_quarantine打开新段，driver _open_episode写hold；下一_apply_lifecycle不检查当前active段身份，消费旧close而写resume。输出：旧段 `quar_1_1500000000`，新active段 `quar_2_6000000000`，pending `[hold,resume]`，最终cmd=resume且新active仍在。

**最低解除（S1）**：release只作用于对应已关闭段，不能释放当前新active隔离；复用现segment/event信息、普通串行正反控制，不扩锁框架或并发矩阵。旧rearm同类问题按历史范围保留。

### 3.3 E2恢复检查点位于待隔离段之内：ARCHIVE_CONFIRMED

这是本次新原件直接暴露的可信恢复断点，不是源码猜测：

| 时间/对象 | 原始ns |
|---|---:|
| E2 quarantine start（lifecycle:84） | 1627785301425840378 |
| E2 trigger（candidates.jsonl:2） | 1627785303425840378 |
| 最后snapshot及restore ack共同stamp（events:260–285） | 1627785304425766144 |

检查点比trigger晚0.999926s，比隔离起点晚2.999926s；snapshot ack的hold=0、points=697947，restore确实回到同一较晚stamp。因此OK restore证明接口应用，不证明待隔离段地图贡献已撤掉。本次不测这些点的污染质量，不称697947点全是错误。

部署snapshot实现只复制宿主当前state/map并覆盖唯一cp（diff:664–678），没有按driver可信截止时刻选择历史检查点。正常宿主领先driver即可出现。

**最低解除（S1/S2）**：把宿主checkpoint与实际trusted/隔离截止点绑定，选择不晚于该逻辑边界的一致state/map；现接口若不支持指定回溯，明确拒绝该恢复范围/交实际断点，不能把较晚restore列可信保护PASS。沿已有有限checkpoint机制实现所需最小时间归属，不要求无限历史缓存。

## 4. 新tests、未选review候选与范围控制

实际命令：

```text
python -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_70f68fb/run_checks.py
```

exit=0；目标 `TestAcceptedCommitReleasesTheHold`两项本机PASS，实际用时0.007s。它们证明full commit发close、拒绝不发close；不证明宿主依赖顺序安全。两个正常反例均FAIL_REPRODUCED_LOCAL；exit0表示脚本核到预期反例，不表示产品PASS。

未运行全suite、ROS、原bag、真实host、新参数/模型实验。目标client新增fakehost测试未运行（不为Windows rename兼容改生产代码）。code-review提出的detector旧报警延续、bag-end finish及旧precondition VALIDATING候选本轮不升级新必修清单：尚无本轮限定实测、部分是旧范围；可沿真实运行具体断点复核，不为每项扩测试矩阵。

## 5. 门研究旁支：实质纠正，但A/B未闭合

比较研究remote `3e9f947`→目标70：9文件真正修正均来自 `62f294b`；其他大量研究文件是旧branch首次入main，不算新实验。

- A/B源码、JSON和专属文档原样：A旧absolute基线漏正gain/P与独立候选缺口，B重复sigma²归一/生产CUSUM衰减遗漏/O背景包输入问题没有解除。不能按合并宣称A/B验证完成。
- C/Part2分离纯旋转、纯平移、完整SE3，信息搬回同anchor、固定方向不再重新单位化；旧混合控制原数保留。两扫描所测变换下仍有非协变反例，不是普遍修复收益。
- 24扫描行未变；r=1、24/24改为tautology_check。新增真实gate函数的合成SPD控制：固定tx投影100、candidate自身λmin38.8889，Mode2 accepted，撤回fixed/own混淆。谱与cov腿等价限同基、SPD、P=Λ⁻¹。
- Part1保留核心数值，改精度与解释：5/5误差在5e-4内，最大相对差1.561e-5；7.57°–28.46°方向夹角不再判稳定PASS。旧κ不能无条件移植；真实新after/两端分离/判决比较仍BLOCKED。

非主线阻断的小纠正集中延期：hall纯平移文档3.1e-8而JSON3.10490575e-7；旧producer≤3.5e-16漏room旋转3.648e-16；SPD reading保留旧舍入叙述但数值abs_diff=0；Part1“两个”20–23ms实际三个，容差吻合不能唯一证明归档producer。无需为文字再跑bag。S3仅补既有A/B逻辑/人口缺口和上述一致性，不开B-v3/大矩阵，不自动部署未选门；旧参数任务继续停。

## 6. A/B局部变化、下一唯一主线及自检

| 行ID | 本轮变化 | 仍缺 |
|---|---|---|
| A2/A4/A6 | actual部署源码与旧受控原件局部公开、核内部一致性 | source→binary独立构建、可信时间点状态/map、actual修复apply |
| A9/A10 | 双拒绝接口、持续输入/E2尾段原件可核；full commit closed事件两test通过 | 接纳后原生动作依赖/新段保护、真实修复后E2 |
| A8/B2 | 两正常release反例和E2晚检查点断点已证 | 最低顺序/段归属/可信边界解除 |
| A7/B5 | fixed/own与坐标控制认识纠正 | A/B公平有效基线、真实独立候选/质量 |
| B4/B11 | 未新增实际修复净收益/完整在线链 | 同次actual修复→原生重估/地图→接回/E2及成本 |

不发布新全表总分，不自动沿用历史A16/36或B11/12。本轮是源码/原件与局部机制推进，不是恢复成功率增加。

**下一唯一主线**：S1/S2复用已接受checkpoint、deep-copy、received/applied及生命周期组件，最低解除上述实际顺序/时间/段归属断点；在既有900s预算内交一次实际修复测量支配原生重估/内部地图→接回真实输入→E2及尾段，或具体宿主文件/函数首断点。拒绝机制与actual修复分别记账；首次真实完成立即单独告用户，不等门研究或日报。

主要已证阻塞为工程编排/可信时间归属；算法首因UNKNOWN，参数改善上限无新增证据、继续暂停。远端当前任务执行/后期本地意见接收UNCONFIRMED，不向无关peer代派/代跑。

开发侧下一实际交付先自检，每项提供PASS/FAIL/BLOCKED/NOT_APPLICABLE、实际命令和原件路径：

1. checkpoint逻辑时刻≤实际可信/隔离边界，state/map/input一致，未支持回溯显式拒绝；
2. single-in-flight及applied成功依赖，失败/未知不继续，旧close不释放新active；
3. 修复点记录/scan/group/stamp真实进入deskew、估计、内部地图，候选/准入/deferred人口一致；
4. 同实例接回/E2/尾段输入输出/地图/缺帧/成本，受控与自动、拒绝与成功分别列；
5. 独立质量及oracle/proxy边界，完整人口与负结果保留，缺GT/原件UNAVAILABLE。

## 7. 记录与发布

本轮确有实质增量，保存本目录并仅追加PROJECT_HISTORY/COLLAB本次变化，不改旧数字、旧报告或开发源码。保护私人handoff，不stage/提交/提供Codex/公开；不合main、不删实验资产。

此前push权限拒绝尚未解除；只本地白名单提交，不重试受限推送、不换工具/peer/Artifact外发绕过。remote review最后可核仍3965299，不称开发收到本次意见。本机检查不代替远端自检或真实宿主验收。
