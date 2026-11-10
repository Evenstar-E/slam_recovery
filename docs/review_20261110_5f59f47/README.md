# 5f59f47：ICP已接入决策代码，实际运行证据和固定窗口仍需对应

2026-11-10。目标 `5f59f47d22242140f5e65ecc4a5966e182f1a853`，基线a2e721e，三笔增量。已读协议/评分表、核本会话三自动任务和旧Windows PID25412不运行，忽略stop.md；保护私人handoff，不改算法/门、不代跑ROS。

**部分实现推进：不再称在线候选路径根本没有调用ICP。**新分支真实调用build_icp_candidate，记录每帧detail，失败不替换回host poses；回调只请求，主循环service执行决策，避免耗时动作全留在订阅回调中。已有原生恢复/测量重处理/内部状态地图写回、Mode3后续候选/终态/重武装仍未接，不能把Python求解器调用当完整宿主恢复。

## 1. 本机实际接线核验与报告边界

[最小probe](live_integration_probe.py)在固定目标实际Python loop/node上，用现有合成cloud及直接quarantine入口，4帧ICP返回4个ITERATION_LIMIT pose、实际gate仍Mode3，detail有4行；未mock算法/准入。退出0确认调用接线，不是ROS/净收益或原生恢复成功。

```sh
python -B -W ignore docs/review_20261110_5f59f47/live_integration_probe.py
```

开发日报报告一次shutdown丢记录、23帧逐帧ICP约13s/帧、30s预算产3/23、七次run相同22时间戳而pose差max.0903m。**本增量没有这些尝试的receipt/summary/candidate/icp_detail或跨run原对照**，只能接受执行方报告，不独立确认该成本/缺记录根因、原运行实际sample数或成员相同。现有旧host-pose收据不替代新尝试原件。下一实际交付复用已有原产物提供小型入口，不为补字段另跑。

### 6000缓冲点不等6000点ICP，不能凭此要求重测

runner仍scan_cap6000，但 `_icp_candidate()`调用默认ICP_CONFIG，`reregister_frame()`首先调用 `sample_scan()`，上限2000。本机真实函数6000点输入→IcpResult.scan_points=2000，平面控制CONVERGED。因此当前代码不存在“直接用6000点优化所以耗时约3倍”的证据；日志打印buffer长度不是solver输入数。若原尝试跑了不同source，需原身份/detail证明，不能由6000字段猜偏离，再要求先跑一趟2000。

新增budget在**帧之间**检查，不中断一帧ICP，超预算后还生成各帧BUDGET_EXHAUSTED结果；这是软预算，不承诺30s硬墙钟。两项既有candidate assembly函数通过，极小正预算控制保留缺失状态、无候选。预算截断保持authoritative pending，3帧不足可合法WAIT，不降低最少证据门制造接纳。

## 2. 两个限定问题：不扩线程防御框架

### 固定窗口随service调度变化（正常时序反例）

新 `on_pair()`越deadline后继续append，直到主线程service才置decided。主循环2Hz且无截止snapshot；所以“固定2秒人口”实际随普通调度延迟变动。

复用上述probe，同一输入时戳3.0/3.1/3.2s、同一episode deadline3.0s：逐帧service候选1帧/t_decision3.0s；待3.2s再service候选3帧/t_decision3.2s。两种pending均完整为1/2/3，没有丢帧。**确定性的人口窗口定义变了，不是随机SLAM逐数不同。**这也不证明原七次运行不同成员，原对照尚未交。

最低处理二选一沿既有实验范围：首次达到deadline冻结候选输入/时间，后来帧继续归pending；或明确本次按service时刻做变长窗口、不得和旧固定2秒比较混称同实验。后台ICP时冻结输入/参考与状态提交入口须有明确责任，不要求通用并发/异常框架，本机没有声称已实测多线程错提交。现t_decision记录的是选取输入的时戳而非几十秒ICP完成时刻，后继端到端延迟需区分，不以该字段证明即时完成。

### 新A7“已清除”标签不成立（同一已知producer问题）

新summary写 `A7_V2_GAUGE_CLEARED`并称旧标签过时，但本轮core/node/FIM producer未改；已知world ridge仍在。只因本次新增已清除主张，本机复用[旧actual node probe](../review_20261110_21fa650/a7_node_cov_probe.py)，内存仅替换目标SHA、旧档案不变，固定source blobs核过：相同cloud/world y0→20m，info_after均62.98293、NIS均.335222，cov .513614→.469490，**Mode3→Mode2**，冻结门未改。

最低解除不是重写transport/再造测试：沿旧S3固定基正则最小修；解除前保留实际producer未通过的范围，不把18项gate契约测试当整个producer已通过。旧anchor transport与两处时间包络仍接受，不因这个问题重开它们。该标签不是无关日志：会把未解除评价问题包装为准入可用于科学效果的前提。

## 3. 段级刚体ICP建议：可以探索，但不是不变实验

日报建议将逐帧ICP换一次段刚体（合并/代表3–5帧求一个变换作用全部pose）。它减少调用次数是合理成本假说，但仍只有建议，没有实现/净收益证据。**即使六个数值常数不动，状态自由度、损失人口、代表帧选择与修复假设已改变**，不能说§9实验整体没变；一个刚体不能表达段内不同漂移。最小声明其针对的结构/成本假设和复用模块，先核现原件实际2000采样/成本，不自动启动新扫描或为3/23不足降门。

不以本机小fixture用时推远端真实性能；也不由报13s直接证明逐帧方法永久不可行。真实测量过滤/deskew/velocity/bias重估与宿主内部地图恢复仍是另一层，段刚体sidecar不能代替。

## 4. 下一唯一主线与自检

- **S1集成/S2宿主：**新ICP调用直接复用，固定当前输入/决策范围，提供已有尝试原件及第一实际宿主checkpoint/reprocess/internal state-map writeback接口实现。接真实Mode3等待段后续证据/候选、有限终态与重武装，交一次恢复→接回输入→E2；不能继续仅成本/非确定性说明或更换候选粒度替代接口。
- **必要并行S3：**旧actual producer固定基正则，解除前不宣称A7 cleared；共享driver/manager入口写入责任由S1确认。窗口snapshot是当前正常接线的最小一致性，不扩生产线程安全矩阵。
- **Codex/KITTI/后继比较：**沿工具核真实运行、独立候选质量，后继不挡接口准备。随机实验总体趋势/量级/失败范围允许差异，负结果保留；新source身份、时间窗口和确定性gauge不豁免。远端当前branch/未提交/正在运行及收到意见仍未直接确认。

主要缺口仍工程恢复接口/生命周期；新ICP接线及成本尝试报告是部分推进，参数偏离尚未证明，不臆测换算法必然成功。A7评价依赖未解除；本轮局部映射A6候选、A12成本/调度、A7及B11范围，完整A10/B11不升档、不重算全表。

[local_checks.json](local_checks.json)：PASS为source绑定、真实4帧ICP分支、6000→2000实际采样、两既有assembly函数（5.568s）、预算状态控制、3Python AST/runner bash -n。窗口反例退出0=问题复现，A7旧producer反例FAIL=新cleared主张未满足。新driver pytest suite仍BLOCKED（已知缺pytest，不安装/伪造/重复），ROS/原bag/七run对照未本机验证，旧完整回归NOT_APPLICABLE。

下一实际交付按REVIEW§10.12给PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令、source/host/input/config/预算与实际人口、持久原产物。报告限制随真实交付处理，不另造收到/标签/FIM日志周期，不调冻结门，不无限调参/重跑。
