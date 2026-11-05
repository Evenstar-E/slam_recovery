# slam_recovery 最新版本复审：23fbe6d

日期：2026-11-05。审阅提交：`23fbe6d2b42c3068f98d037144ad5c98be91458e`。
相对上次本地/已发布状态 `d5bd4df3fe747a3148e138d6ccb3fbdc116001d0`，拉取了 12 个提交；94 个文件变化。原审阅通过正常 fast-forward 获取代码，未修改被审源码；审阅和反例先在 clone 外保存。本目录按用户随后明确授权发布，算法代码保持不变。

## 结论

**有实质进步，但“100% 最终验收通过”的结论不成立。** 上次六个具体反例已有针对性修补，当前 17 项仓库测试全部通过。新版本增加了地图日志、因果注意力特征、三维合成场景和更多实验记录。不过，几个最亮眼的指标没有由所声称的系统行为产生：检测召回率写死、正常残差人工生成、仿真恢复直接使用真值位姿、部分姿态误差实际是路径方向代理。同时，位姿回滚还没有与点云地图回滚绑定。

这不等于“项目没有价值”或“所有旧实测都是假的”。这里判断的是**当前具体结论与生成代码是否匹配**，不推断主观意图。仓库原生宿主日志和保存轨迹仍有价值，但本地缺少对应完整 ROS/bag 环境，未重新验证这些物理运行。此次新增 C++ 宿主接线没有出现在该提交区间中。

## 本轮验证范围

- 原测试命令：`python -X utf8 -B -m unittest discover -s slam_recovery/tests -v`，17/17 通过。
- 本地补充审查：9 组有界反例全部复现问题，见 [结果 JSON](audit_results.json)、[脚本](audit_local.py)。
- 9 组结果是“复现缺陷”，不能当作“9 项恢复验收通过”。
- P9 反例使用合成输入与“永不报警”推理替身，执行原评测函数，专门检查统计逻辑；不冒充真实 bag 或模型测试。
- 未播放 bag、训练新模型、构建 ROS、重算远端全量 ATE；本次仅发布既有复审及小型证据。
- 源码/文件 SHA 与原审阅状态另见 [来源及发布清单](provenance.json)。

## 上轮问题哪些真正改善了

| 上次反例 | 当前变化 | 本轮判断 |
|---|---|---|
| R1 checkpoint 哈希漏 keyframe 身份 | 哈希加入 keyframe ID 与数组形状 | 对原反例已修复 |
| R2 迟检后污染状态未撤销 | 新增 promoted_history，撤销迟检区间的 pose/factor ID | 简单追加场景改善；重复 key、全撤销 bias、实际体素仍有缺口 |
| R3 NaN 位姿被提交 | 位姿、信息阵、协方差、holdout 检查有限值 | 原 NaN 位姿反例已修；bias、SE(3) 形状未覆盖 |
| R4 分块谱漏掉耦合弱方向 | 加入完整 6×6 最小特征方向 | 对原构造反例已修复 |
| R5 大残差被筛掉 | 不再用原 2m 截断把坏点从统计中去掉 | 对原反例已修复；不代表所有留出独立性已解决 |
| R6 只提交位姿 | 增加 factor ID / bias 可选字段 | 接口增加；默认拼 factor ID 与实际因子/状态事务仍不同 |
| E3 先提交后 Wilson | E3 先算收益证明，再传入 candidate | E3 调用顺序改善；通用接口仍默认批准，其他入口可绕过 |
| 新模型说明不明确 | manifest 已写明 frozen attention readout、半合成特征 | 披露有进步，不能再称完全未说明；但召回统计依旧错误 |

## 按优先级列出的发现

### F1 [P1] P9 的 100% 检出率不依赖实际报警

位置：[run_identifiability_and_transformer_real_bags.py:412](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/run_identifiability_and_transformer_real_bags.py#L412)、[同文件:475](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/run_identifiability_and_transformer_real_bags.py#L475)。

触发隔离的条件是 `g_act[t_i] && g_age[t_i] >= 2.80`，直接使用故障标签和真实故障年龄，没有使用模型报警；输出又直接写 `event_detection_recall: 1.0`。原因识别按故障后半段所有预测类别的并集统计命中，没有处罚额外的错误类别。

**反例：** 将全部 600 次推理替换为概率 0、类别 UNKNOWN，原评测仍对三个序列输出 recall=1.0。所以不能据此接受“新地点全部检出”或把关联的漏污染帧数作为自动检测闭环结果。

此外，点云的空间统计确实来自真实扫描，但 NIS、LOSO、lag 等是按故障类别和斜坡幅值生成；采样后时间重新设为每步 0.20s，不沿用输入扫描时间。manifest 已标注半合成，这一点应保留，但结果只能作为受控特征原型。参见 [特征生成:262](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/run_identifiability_and_transformer_real_bags.py#L262)。

**最小修复：** 真值只用于事后匹配事件；记录实际报警时间、未报警事件及 clean 报警。先要求永不报警模型 recall=0，再重算当前数据，暂不扩大模型。

### F2 [P1] 近墙负例的“基线 100% 误报 vs 本方法 0%”不是公平实测

位置：[run_hard_negative_and_rot_ate_benchmark.py:111](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/run_hard_negative_and_rot_ate_benchmark.py#L111)、[同文件:130](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/run_hard_negative_and_rot_ate_benchmark.py#L130)。

在 `is_near_wall = nf_ratio >= nf_frac_thresh` 内，又用 `contam_r >= 0.15 or nf_ratio >= nf_frac_thresh` 计数“基线错误剥离”。后半条件必为真，因此选中的每个负例都被计成基线错误，与过滤器真实输出无关。

本方法的 NIS/LOSO 则从预设低值分布随机采样，没有从这些扫描的宿主预测和残差读取。因此它证明的是“给正常残差时规则不触发”，并没有证明正常贴墙时系统自己能得到正常残差。

保存报告确有 room_02 76/76、hall_02 62/86 的负例统计，但这些分母不能修复上述比较逻辑。真实几何点云与模拟健康特征应分开标记，不能整体标作 REAL_HOST_AND_INJECTION 的真实误报对照。

**最小修复：** 两方法都依据实际输出计数，同次宿主运行提取 NIS/LOSO；阈值保持冻结。

### F3 [P1] 撤销位姿后，污染点云仍在地图和验证参考中

位置：[transaction_manager_node.py:133](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/sim/transaction_manager_node.py#L133)、[同文件:222](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/sim/transaction_manager_node.py#L222)。

节点仅处理 `new_keys = current_keys - previous_keys`，没有处理被删除 key 的体素/点云。迟检撤销发生于 tx_mgr.trusted_poses，`voxel_store` 与 `committed_map_points` 没有同步撤销。恢复更新已有 key 的位姿也不会触发其点云重新放置。

**反例：** 使用固定健康决定隔离账务行为，keyframe 2 的污染位姿已被撤销，属于它的体素仍存在；其 x=100m 的点仍能被 `get_trusted_map_points()` 返回，进入后续验证参考。

SpatialMutationLog 本身新增了 before-image/redo，但普通节点 quarantine 路径没有把 generation/rollback 与 pose 事务关联起来。S1/S2 的 B5 手动 begin/rollback 演示不等于在线生命周期完成。

**最小修复：** 为 pose、体素贡献、验证点集建立同一事务边界；撤销和已有 key 替换都更新地图。先用这个四帧反例验证，再考虑全序列。

### F4 [P1] 通用提交门仍允许缺失证明和无效状态

位置：[core.py:183](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/core.py#L183)、[core.py:250](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/core.py#L250)、[manager.py:198](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/quarantine/manager.py#L198)。

- `paired_benefit_approved` 默认 True。Wilson 下界与重入位置跳变字段不参与通用判断；OnlineRecoveryTransactionNode 构造候选时未计算配对收益证明。
- **反例：** Wilson 下界为 0、重入跳变字段为 99m，仍提交并声称“通过 paired Wilson sequential checks”。
- **反例：** 合法位姿加 NaN IMU bias 被提交；2×2 的有限矩阵也可作为所谓 SE(3) 位姿提交。
- `repaired_factor_ids=None` 时用 `keyframe_id*10` 生成 ID，只匹配测试命名约定，不代表恢复了实际因子、边和后验状态。
- 提交先替换位姿，再逐字段更新 factor/bias，未形成完整的先验证、再一次替换状态的流程。

**最小修复：** 缺证据默认待验证；验证证明绑定 candidate/parent/source/验证端点。校验完整状态、形状和刚体约束；由真实修复器提供因子与 bias，不猜 ID。E3 正确传证明的路径要保留。

### F5 [P1] 迟检“undo log”仍不是可恢复的旧状态日志

位置：[manager.py:128](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/quarantine/manager.py#L128)。

当前记录的是更新后的 delta，撤销时直接 pop key，而非保存并恢复被覆盖的健康值。

- **反例：** keyframe 1 先健康写 x=1，再写坏 x=30。撤销第二次更新后，keyframe 1 整个消失，而非恢复 x=1。
- **反例：** 所有 promoted delta 被撤销后，pose 为空，但原污染 bias=[0.7,0.7,0.7] 保留，未恢复初始零 bias。
- `restore_checkpoint` 未同步历史/待提交队列；后续再次报警的生命周期需要专门核验。

**最小修复：** 用覆盖前状态或可重建的健康 checkpoint＋有序日志恢复，包含空历史边界；随后验证恢复后继续运行、再次报警。不要仅扩充“追加不同 key”的单次样例。

### F6 [P1] S1/S2 主要是 oracle 演示，不能作为自动恢复系统收益

位置：[run_s1_s2_simulation_experiments.py:202](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/sim/run_s1_s2_simulation_experiments.py#L202)、[同文件:266](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/sim/run_s1_s2_simulation_experiments.py#L266)、[同文件:326](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/sim/run_s1_s2_simulation_experiments.py#L326)。

R5、B6 候选直接传入 `quar_poses_gt`；B0/B1/B3 则用人为设定的漂移，不是分别运行相应 SLAM/修复算法。NIS 按是否在退化区间赋 3.6/1.02。部分最终 mode 直接填写常量而不是汇总各 seed 的返回值。其价值是检查“正确答案送入门后如何表现”，不能据此证明系统自己能找到答案。

提供的 `transaction_manager_node.py` 是 Python 状态类，没有实际 rospy 订阅、发布或 spin 接线；.world 文件存在也不代表本脚本实际通过 Gazebo/ROS 驱动宿主。

还有几何评测误差：所谓精确 mesh 距离把有限墙面当无限平面。**反例：** 点 (1000,3,1000) 在 40×25m 场地之外，却被算成距墙 0m。柱面距离也未限制高度。

**最小修复：** 现有结果标注 oracle/解析场景门控演示；用真实 candidate pose 产生地图，mode 来自实际 report，GT 只用于评测；有限几何距离需符合实际场景边界。

### F7 [P1] 新增“旋转 ATE/RPE”中混入路径方向代理，并会把缺测变成零误差

位置：[trajectory_eval.py:265](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/evaluation/trajectory_eval.py#L265)、[同文件:279](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/evaluation/trajectory_eval.py#L279)、[同文件:304](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/evaluation/trajectory_eval.py#L304)。

四元数缺失时，代码从位移弦构造 yaw；GT 无姿态时计算路径切向角，丢掉最高 5% 角误差。没有足够移动片段则返回零数组；没有 RPE 配对时用 ATE 数组乘 0.5 代替 RPE。

**反例：** 估计和 GT 都无姿态、位置静止，全部 rotation ATE/RPE 返回 0.0，而非不可测。P10 还对若干输入主动传入全零四元数以进入这种代理分支。

有效四元数路径也通过评测段拟合 world 和 sensor-to-Mocap 旋转；这一校准应有明确固定策略，不能与独立外参验证混淆。

**最小修复：** 缺姿态则正式 rotation ATE/RPE=UNKNOWN；另报路径转向代理并保留全尾部；真实姿态评测使用已声明的时序、坐标与外参。

### F8 [P2] 模型冻结哈希不覆盖完整模型；当前骨干不是端到端训练

位置：[causal_transformer.py:97](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/diagnosis/causal_transformer.py#L97)、[同文件:258](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/diagnosis/causal_transformer.py#L258)、[同文件:313](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/diagnosis/causal_transformer.py#L313)。

48-cell MLP、注意力 Q/K/V 与相对位置偏置保持初始化，训练只更新 ridge 输出头。manifest 已诚实注明这一点，应称“固定随机注意力表征＋学习读出”，不能据此推断训练 Transformer 的收益。

哈希仅包含三个 W，不含三个输出 bias、编码器/注意力参数或配置。**反例：** 只改 b_act，输出概率从 2.06e-9 变为 0.999999998，哈希完全不变。

类别头也未用 active_prob 作统一激活约束；规则类别始终并入，因而模型不能撤销规则本身的误报。是否合理取决于明确的动作合同，当前不能据“低 active probability”自动推断无故障动作。

**最小修复：** 冻结完整参数、预处理、规则与配置，明确 healthy/unknown/cause 的一致接口。先证明特征与报警有实际贡献，不必立刻换大型模型。

## 其他应保留的证据边界

1. **E2 消融仍是混合来源表。** B1 用轨迹增量乘 0.985，B3 裁剪轨迹步长代替真实重新求解；B4 隔离外使用 B6 已修复增量。其 OFFLINE_CONSTRUCT 标注是进步，但不能称同一个在线恢复器的真实关闭模块消融。hall_01 ATE 与独立合成场景三维污染率放在一行，也不构成同次运行地图/轨迹联合收益。见 [run_e2_ablation_matrix.py:136](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/run_e2_ablation_matrix.py#L136)。
2. **E3 改用跨扫描几何评分，比直接比辅助位姿更好。** 但修复仍用同一 LiDAR odometry，评分扫描未证明未参与该 odometry 估计；同一 odometry 姿态还用于旋转扫描。恢复对齐使用修复区间后 45s，适合延迟离线恢复，不可冒充在区间结束时即可在线决策。见 [evaluate_e3_orbslam3.py:103](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/e3_orbslam3/evaluate_e3_orbslam3.py#L103)、[同文件:214](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/e3_orbslam3/evaluate_e3_orbslam3.py#L214)。这说明统计独立性未证，不是否定跨扫描几何本身。
3. **可辨识性公式与走廊可观测性不是一个结论。** P9 令 `s_planar = normals[:,0] = H[:,3]`，自然得到投影残差为零，即该人为误差与平移耦合；不能由此推出走廊运动方向已经失去约束。`longitudinal_observability_collapsed=True` 是常量，而记录的 translation Gram 最小特征值为 109–132。应分别测试位姿可观测性与故障参数可辨识性，保留该代数检查作为单元 sanity check。见 [P9:114](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/run_identifiability_and_transformer_real_bags.py#L114)、[P9:193](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/experiments/run_identifiability_and_transformer_real_bags.py#L193)。
4. **CoW 的有界演示不是全系统内存已受控。** 节点持续保存 scan_buffer_body、committed_map_points，manager 持续保存 promoted_history；get_trusted_map_points 先 vstack 全部点再限为 2000。这会随序列长度增长并产生临时全量拷贝。本轮没有测 RSS，不能声称已发生 OOM，但与旧项目的内存风险机制相似。CoW 15.1× 是完整复制与局部 rollback 两段的计时比较，不是端到端加速。见 [transaction_manager_node.py:88](https://github.com/Evenstar-E/slam_recovery/blob/23fbe6d2b42c3068f98d037144ad5c98be91458e/slam_recovery/sim/transaction_manager_node.py#L88)。

## 与之前项目相比，当前最值得保留什么

值得保留的方向：明确的原因分类、未知/等待/拆图动作、故障参数与位姿耦合分析、局部写日志、可替换的宿主接口。它们比在单个序列上不断放宽小门槛更有组织性。

仍未解决的共同问题：候选状态和历史地图未保证一致，验证参考可能已受污染，候选生成与验收使用相关信息，指标改善有时来自评测构造而不是原生执行。新仓库更易理解、开发速度快，不等于已经超过旧项目的物理实验证据强度。

## 建议下一步：收敛成一个可证实的闭环

1. **先修评测，不重训。** 使永不报警模型 recall=0；hard-negative 统计来自实际报警/剥离；缺失姿态返回 UNKNOWN；oracle/半合成与物理运行分表。
2. **把一个宿主的 pose＋地图＋验证参考绑成同一事务。** 只覆盖迟检、已有 key 更新、再次报警、接受/拒绝四类生命周期，不先扩其他宿主。
3. **做一个真实同输入、同终点的 clean/fault/恢复对照。** 候选不能用 GT；同时报告实际检测、真实执行、污染、覆盖、轨迹，验证只隔离不写图的方案不会凭低污染伪装恢复收益。
4. **闭环成立后再冻结模型和上新地点。** 对开发过的数据不重新贴“未见”标签；完整参数哈希与时间/点/验证来源绑定。

以上是建议，**本轮未实施算法修复或启动新物理实验**。原审阅曾按要求仅保存在本地；本目录依据用户后续“上传复审报告”的明确授权发布。



## 复现本次有界审查

在仓库根目录、Python 与 NumPy 可用时执行：

```bash
python -X utf8 -B docs/review_20261105_followup/audit_local.py
```

脚本不需要 bag、ROS 或 GPU，仅运行原单元测试及九组有界探针，会更新本目录的 audit_results.json 与 upstream_tests.txt。审阅依据是固定的 23fbe6d 源码，文中源码链接均固定到该提交。若后续代码修复使反例不再复现，脚本可能返回非零；它是审查复现工具，不应作为要求缺陷永远存在的 CI 通过条件。

原始本地证据不被发布副本覆盖。发布只做链接转换、审阅阶段与发布阶段说明、脚本仓库根路径适配，以及日志中的本机绝对路径替换。文件清单和两种源码哈希口径见 provenance.json。
