# slam_recovery 审阅、旧项目比较与图示重绘

> **【状态更新 Status Update — Resolved in Commits `00080c1`, `fb9e655`, `135629c` & Latest Closure】**  
> 本目录记录的是针对早期提交 `4b140b9` / `6d1f7e4` 的静态代码审计与 6 个有界反例（R1–R6）。在随后的提交中：  
> 1. **反例 R1–R6 已全部在核心代码中修复**，并通过回归测试 `test_r1_to_r6_audit_counterexamples_resolved`（见 [`slam_recovery/tests/test_atomic_commit.py`](../../slam_recovery/tests/test_atomic_commit.py#L160)）及 `audit_review.py --summary`（6/6 `reproduced: false`，17/17 单元测试通过）验证；  
> 2. **E3 跨帧点面 Holdout NIS 与前置无偏 Wilson 检验**已并入 `CandidateMap` 与 `evaluate_four_mode_gate()` 内部（消除先提交后检验的顺序倒挂），且 `compute_6dof_point_to_plane_fim()` 已同步 6D 耦合特征分解；  
> 3. **S1/S2 解析三维网格光线采样仿真（`ONLINE_SIM_3D_MESH`）**已移除全部人工缩放系数（`0.5 *`、`* 0.05` 及手工对角矩阵），并直接接入 `SpatialMutationLog` 写时复制体素日志；  
> 4. **主消融矩阵 B0–B6（含 B1 在线投影、B3 同数据回滚、纯后端 GNC 对比）、E-Gap 1 近墙正常通行 Hard-Negative 负例测试（FPR = `0.00%`）、E-Gap 4 旋转误差 $\mathrm{ATE}_{\mathrm{rot}}$ (deg) 以及留出测试集 `hall_02` 零微调盲测**均已完整落盘。

审阅日期 2026-11-05。拉取版本 `4b140b949d217de56aaf992f6684e23ad2355a30`，算法主要来自父提交 `6d1f7e4`。比较对象是旧仓库 `fast_livo2_shared_cursor` 的 `abf13a36cfcec92a9c893cd3dc6331ce61c9562e` 发布快照，以及其封存的 10 月 30 日研究结论。

上传时已正常合并并保留远端 `0cb5bc6`、`afd6290` 新增的核心思想提炼文档。这两个提交仅改变该文档，本审阅的代码基线不变；不将其设计论述视为新增算法已实现或验证。

**结论是值得借鉴它的模块组织、故障分类和等待新证据的策略，但当前还不能把它当作已经完成安全闭环的替代系统。** 新仓库的多个好结果混合了原生宿主运行、离线轨迹构造、合成特征实验与直接赋值。它与旧项目的实际原始输入回放、地图重建证据不在同一层级，暂时不能按误差数字排名。

本轮完成源码与调用链审阅、原有 13 项测试、6 个有界反例，以及 7 张可复现图示。没有播放 bag、重训、编译 ROS、修改算法或验收门槛。历史图片、manifest 和论文原始结果保持原样。按用户后续要求，报告与图包上传本仓库；图 1 参照 FAST-LIVO2 架构图风格重新绘制，保留实际实现与未完成交接的边界。

## 新旧项目的异同

| 方面 | 之前的 FAST-LIVO2 研究 | 当前 slam_recovery | 判断 |
|---|---|---|---|
| 核心目标 | 迟检后的 LiDAR 尺度故障与历史地图恢复 | 多种退化的隔离、诊断与可验证恢复 | 共同点都是“发现异常不等于立即采用修复” |
| 宿主 | FAST-LIVO2 原生状态、地图与历史输入 | 继承 MM-LINS 的 FAST-LIO、SC-PGO，加 Python 研究层；其他宿主主要有实验脚本与结果 | 新仓库覆盖更广，但统一原生适配未闭合 |
| 选择器 | 因果 Transformer、后续证据融合、几何验证与有界 proposal | NIS/CUSUM、旋转/平移信息谱、跨模态统计、规则签名路由；GBDT/IsolationForest 作为对照 | 新主路由是规则式；代码中的“HMM”实际上是连续窗口计数状态机 |
| 故障假设 | 主线集中于测距尺度偏差，另有视觉探索 | 几何退化、近场污染、时间偏移、回环异常、辅助视觉退化与 UNKNOWN | 区分“缺信息”和“有偏信息”是实质启发；当前未实现旧项目尺度 q 的同等估计链 |
| 恢复动作 | 估计 q/起点/停止，从 checkpoint 重处理原始输入，重做去畸变、状态与地图更新；后期独立优化原型未完成回接 | RANSAC 平面过滤、辅助位置轨迹桥接、前后端位移增量混合、时间戳偏移估计 | 多个被称为“因子图修复”的函数实际只处理 xyz 数组 |
| 事务深度 | 有原生 checkpoint/journal、候选分支与历史回放；完整一致交接仍有未解决部分 | `trusted_poses` 字典、因子 ID 和部分 bias 的 Python checkpoint；提交仅合并位姿 | 新 API 更精简，但不等价于原生地图、协方差和后端先验的联合事务 |
| 地图评测 | 实际导出地图相对 clean LIO 参考的距离、污染与覆盖；不是外部 GT | 多处“地图污染率”是关键帧位置误差代理，部分直接赋值，另有报警前截断统计 | 新仓库尚不能以这些污染率证明三维历史地图修复 |
| 轨迹评测 | 共同端点差、稀疏测量、留出与六弦等明确分层；部分序列无真值 | ATE/位移差、不同缺帧补全和对齐策略混用 | 需统一端点、坐标、缺帧分母和指标定义；当前 `rpe_trans_rmse_m` 没使用姿态 |
| 泛化证据 | exp04/07/16 已反复开发，不能算 unseen | hall_01、room_02、room_dark_01 为开发数据；E1 为生成器合成流 | 换宿主或换随机种子不等于冻结方法后的新地点泛化 |
| 成本 | 原生快照与回放曾造成明显内存和时间压力 | 局部模块轻，但 checkpoint 列表深拷贝、成对点距离仍有成本 | 0.0599 ms 路由耗时不能代表全 SLAM+修复开销 |

旧项目最新负面结果必须保留：固定同一对应后训练代价下降，但留出匹配率 `2.981% → 2.617%`、共同端点位置差 `0.23418 → 0.25067 m`、速度差 `0.10307 → 0.11067 m/s`。这证明旧系统也没解决“优化目标改善，但实际效果恶化”。新仓库不能靠更宽的指标命名跳过同一个问题。

## 已核实的重要问题

以下为当前版本的代码事实及可运行反例，不推断数据编写者的主观意图。更详细的机器记录见 [audit_results.json](audit_results.json)，复现程序见 [audit_review.py](audit_review.py)。

### 1. 迟检会让坏状态留在可信图，checkpoint 时间标签不代表真实历史内容

`trigger_quarantine()` 只分离当前 `provisional_queue`，随后用**当前** `trusted_poses` 创建一个标注为旧时刻的 checkpoint；没有恢复之前保存的历史状态。[源码](../../slam_recovery/quarantine/manager.py#L106)

反例 R2 设置真实起点 10 s、报警 14 s、延迟提交 2 s。触发后 10、11、12 s 的坏位姿仍在可信字典。新 checkpoint 的标签为 8 s，内容却包含 9–12 s 的状态。原测试只覆盖报警延迟短于缓存的情况。

应明确缓存保护边界，并用时间戳绑定的历史快照和撤销日志处理超出边界的污染。不能仅把当前状态贴上一个更早的时间。

### 2. 提交门没有完整检查候选内容，也不强制执行全部验证

R3 中只把候选位置的一项改成 NaN，保持信息和残差标量“良好”，`validate_and_resolve()` 仍接受并把 NaN 写进可信字典。实际 E3 还将三维位置数组放入名为 `repaired_poses` 的字段，而其他测试用 4×4 位姿矩阵。[数据结构](../../slam_recovery/core.py#L169) · [提交实现](../../slam_recovery/quarantine/manager.py#L150)

提交仅更新位姿与版本，不携带候选的新因子集合、bias、完整状态协方差、点云地图或后端先验。R6 确认提交后新增位姿而因子 ID 保持旧值。这是 API 能力边界，不能称为完整原生原子恢复。

另外，E3 先调用 `validate_and_resolve()` 实际合并字典，之后才计算 Wilson；最终 JSON 把两个布尔值相与。**后验报告拒绝不会撤销已经发生的字典提交。** 应把全部验证做成只读阶段，再执行一次受控提交。[hall_01 调用](../../slam_recovery/experiments/e3_orbslam3/evaluate_e3_orbslam3.py#L375)

### 3. 留出分数会丢弃最差观测，未同时约束覆盖

`compute_disjoint_holdout_point_to_plane_nis()` 直接去掉点面残差 ≥2 m 的点，然后只对剩余点求均值。[源码](../../slam_recovery/validation/fim_and_holdout.py#L132)

反例 R5 的 160 点中，120 点距平面 3 m，40 点距平面 1 mm。函数返回 `0.00015625`，远低于门槛，而 75% 坏点没有进入分母。该分数本身不检查覆盖，不能单独证明整体改善。

它更准确的名称是“截断后内点残差除以测量噪声方差”，尚未包含状态和参考平面不确定度构成的完整创新协方差 S。建议固定验证点身份，报告残差、失配率和覆盖，并在同一检查里共同判断。

### 4. “不同点 ID”仍可能共用修复依据

E3 用健康 LiDAR 辅助轨迹构造视觉候选，又把候选与该辅助轨迹的增量差用于同帧奇偶点面的评分。因此接近辅助源的候选天然占优，不能将其当成独立的新运动证据。[源码](../../slam_recovery/experiments/e3_orbslam3/evaluate_e3_orbslam3.py#L87)

桥接的坐标拟合还使用故障段结束后 45 s 的轨迹，并启用 Sim(3) 尺度拟合。这属于可说明的离线条件能力，不能称为故障结束时已具备的因果在线结果；“不用 GT”也不等于“不用未来”。[桥接实现](../../slam_recovery/experiments/e3_orbslam3/evaluate_e3_orbslam3.py#L177)

Wilson 比较也有人为非对称量。当前 hall_01 对 incumbent 加 `0.05`，B5 使用该量乘 `1.15`；room_dark 使用 `+0.04` 和 `×1.25`。并且窗口高度相关，普通 Wilson 比例下界不自动拥有任意时刻有效的序贯保证。[hall_01](../../slam_recovery/experiments/e3_orbslam3/evaluate_e3_orbslam3.py#L387) · [room_dark](../../slam_recovery/experiments/e3_orbslam3/room_dark_01/evaluate_room_dark_01.py#L288)

仓库自己的最新审阅报告已指出其中部分问题，但 hall_01 的实际常数是 `+0.05 / ×1.15`，不是其文档所写的 `+0.04 / ×1.25`。本轮以源码为准。

### 5. 信息谱、增益和先验不能成为“保证通过”的数字

当前只比较信息矩阵的两个 3×3 对角块。R4 构造对称正定矩阵，其旋转、平移块最小特征值均为 50，完整六维最小特征值只有 `0.001`。分块判断会漏掉旋转—平移耦合弱方向。**如果后面的协方差确实是完整矩阵逆，协方差门可能拦住它；本反例并不表示所有下游门必然误接受。** [源码](../../slam_recovery/health/detector.py#L30)

`pose_graph_repairer.py` 的信息量使用位移增量外积后再加 `25 I`；这会把最小特征值直接抬至至少 25，且不是由因子残差 Jacobian 推得的状态 FIM。E3 也加入固定对角辅助信息量，须给出其噪声、单位及相关性依据。[源码](../../slam_recovery/repair/pose_graph_repairer.py#L103)

当前点面信息使用 `/M` 平均归一化，和总信息求和含义不同。旋转、平移尺度及先验相加必须保持统一。信息增益适合检查缺约束；有偏观测修正可能降低虚假的信息量却提高准确度，因此“增益必须 >0”不能成为所有修复类型的普适必要条件。

### 6. 关键帧身份未纳入 checkpoint 哈希

哈希按关键帧键排序，却只写入 pose 值、不写键本身。R1 将唯一键 1 改成 99 后哈希不变。[源码](../../slam_recovery/core.py#L125)

应纳入键、数组形状、dtype、frame、时间、版本等明确序列化语义。现有测试只篡改矩阵值，没覆盖身份错配。

### 7. 一些实验不能支撑图中暗示的结论

| 证据 | 当前实际含义 | 不能据此声称 |
|---|---|---|
| E1 检测 100% 等结果 | `build_window_stream()` 按故障类型手工指定 NIS、LOSO、协方差等分布，GBDT 也在生成流上训练；manifest 已标 SYNTHETIC | 在真实 bag 上优于 Transformer，或已获得未见场景泛化 |
| B4 “隔离、不修复” | 区间内使用平均位移，区间外直接用 B6 repaired 增量 | 只改变隔离功能的干净消融 |
| B2 两宿主列 | 同一个 MM-LINS ATE 被填入 FAST-LIO2 与 LIO-SAM 两列 | 两套宿主各自产生了相同结果 |
| E2 污染率 0 | 循环在报警时 break，仅统计报警前已提交关键帧；B4/B6 共用同一值 | 恢复后全三维地图零污染 |
| B5 污染率 / false commit | 多个字面常数，缺完整事件分母 | 实测错误提交概率 |
| Campus 最优终点差 | 遍历不同长度历史快照，再选首尾距离较小者；NIS 未通过也可保留原快照进入比较 | 固定完整终点、独立在线 Mode2 的恢复收益 |
| RPE 字段 | 位置数组在全局对齐后，间隔 10 个匹配样本的位移差；丢弃了姿态 | 标准 SE(3) 相对位姿误差；不足 10 点退化成 ATE 也不应同名 |

源码入口 [E1](../../slam_recovery/experiments/run_e1_detection_benchmark.py#L49)、[E2](../../slam_recovery/experiments/run_e2_ablation_matrix.py#L143)、[Campus](../../slam_recovery/experiments/run_campus_and_overhead_benchmark.py#L73)、[轨迹评测](../../slam_recovery/experiments/evaluation/trajectory_eval.py#L107)。

### 8. 模块名称比实际实现更完整

- `JointHealthDetector` 没有 HMM 转移/发射概率或滤波递推，是 CUSUM 加连续窗口计数。
- 点“混合模型”当前实现是固定种子 RANSAC + 平面/距离掩码，没有三分量后验的学习或 EM 更新。
- “GNC 因子撤销”函数没有调用真实因子图优化器或删除宿主 factor；它对前后端位移增量算权重，再累加 xyz。`gnc_mu_init` 与 `gnc_Div_factor` 没有驱动 GNC 迭代。
- `StandardFrame` 与 `BackendDelta` 数据类存在，但 C++ 主循环中未见完整 Python 事务调度桥。部分 manifest 提及的外部宿主补丁/命令和完整运行环境没有一并进入仓库。

这些原型仍有研究价值，但论文、流程图和函数命名应把“设计目标”与“当前实现”分开。

## 真正可迁移的启发

**第一，先区分缺信息与错误信息。** 走廊中缺一个运动方向的约束，与大量点匹配到错误近场表面不是同一个问题。前者需要等待、补采或可信辅助；后者可能靠校正物理观测模型恢复背景约束。旧项目不应把所有异常都翻译成尺度 q。

**第二，保留“有限等待”和“拒绝”作为完整动作。** 允许多检查几次可疑情况，同时保护主地图。等待应由新证据或状态变化唤醒，并有期限、内存与尝试次数预算，避免沿用已失败的同一证据反复回放。

**第三，将动作参数与实际执行效果接起来。** 可以用新仓库的窄接口组织旧项目的原生执行器，例如候选输出原因、q、起点、停止条件、输入与 checkpoint 身份，执行器输出完整状态/地图/轨迹和失败原因。只有改变了可执行动作并重建实际地图，才谈恢复收益。

**第四，把“修复证据”和“验收证据”分开。** 一个最小合同应包括拟合点/因子集合 A、独立验证集合 B、最终评测 C，记录共享参考地图和辅助状态引入的相关性。对所有 proposal 统计漏修、错误干预、失配与拒绝，避免把“不输出”伪装成安全或覆盖提升。

理论上，同一固定线性化和对应下，非放大权重不能凭空增加无约束方向的信息；这不排除正确去偏、重新匹配和非线性重处理带来实际收益。该边界可以帮助收窄论文问题，不能作为“同数据历史恢复永远没用”的论据。

## 建议的最短下一步

1. **先修完整性，不扩模型。** 修迟检历史状态、候选有限值/身份/形状、先验和位姿提交边界，并把 Wilson 等全部验证置于实际提交之前。用本轮反例做接受测试，不播放 bag。
2. **清理证据口径。** 删除或明确降格所有手工性能常数和 oracle/离线构造指标。把 HMM、GNC、地图污染、RPE 改成实现能支持的名称；补一个入口命令、固定依赖和真实宿主补丁。
3. **只接一个宿主、一种故障。** 在 FAST-LIO/既有 LIO 上完成“原始故障输入 → 有界候选 → 重处理 → 停止 → 地图/轨迹同终点导出”。对照不修、只过滤未来、历史恢复；加入一个正常近墙的污染误判负例。
4. **证据齐全后再扩展。** 用真实三维参考或仿真静态 mesh 计算地图距离、污染和覆盖，轨迹用可靠 GT、同评测端点；同时记录 clean 干预、延迟和全程内存。满足联合收益后冻结方法，才使用未参与规则开发的新地点。

本轮并未启动上述修改或实验。旧数据集已按用户要求归档/删除，若恢复物理实验，需先恢复所需的一条输入；不自动重新下载全部数据。

## 图示交付

[查看全部 7 张图与图注](FIGURES.md)。每张都有 PNG、PDF、可编辑文字的 SVG。`redraw_figures.py` 使用仓库相对路径；数值转录表为 [plotted_values.csv](figures/plotted_values.csv)，来源与输出 SHA 为 [manifest.json](figures/manifest.json)。

原 Fig.1 的随机信号曲线不再作为 hall_01 实测展示。原 Fig.3 的合成/常数门控案例改为代码顺序流程图。原 Fig.2、Fig.5 的数值保留并标注来源与限制。原 Fig.4 的截断柱与不同终点快照不在新图中复用为恢复证据。未补齐 GT 的原轨迹图不伪造重画；原始图片仍完整保留。

## 复现与范围

```sh
python -B docs/review_20261105/audit_review.py
python -B docs/review_20261105/redraw_figures.py
python -B docs/review_20261105/verify_artifacts.py
```

审阅测试使用 Python 3.12.14 / NumPy 2.3.5。绘图使用独立依赖目录，Matplotlib 3.10.7，具体版本及源码 SHA 见 manifest。脚本也可在具备 NumPy/Matplotlib/Pillow 的常规 Python 环境运行。中文字体优先 Microsoft YaHei；缺少时应安装合适中文字体并改配置。

图包 manifest 的文本来源 SHA 使用 CRLF→LF 规范化，以支持 Windows/Linux 检出；PNG/PDF/SVG 输出使用实际文件字节 SHA。`audit_results.json` 的历史源码 SHA 保留首次 Windows 检查时的原始字节记录。文档目录的 `.gitattributes` 固定文本为 LF，不改变算法目录的 Git 属性。

本轮原有测试 13/13 通过；6/6 小型反例复现的是上述缺陷或 API 限制，**不是 6 项算法恢复通过**。未运行端到端实验，未重算仓库报告的 ATE，未确认原外部数据、真值坐标或外参。旧项目 `paper_ready=false` 不因本轮文档工作改变。

图形流程采用 scientific-visualization 技能，软件方法来源为 Timothy Kassis, Vinayak Agarwal, Yuhuan He, Darshil Patel, Aubrey M. Brueckner. *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*, 2026. [arXiv](https://arxiv.org/abs/2609.00065)。此引用仅说明制图工作流，不支持 SLAM 算法有效性结论。
