# 最新代码更改审阅报告（Commit `6d1f7e4`）与 Gazebo / Isaac Sim 实时仿真实验方案

> **更新日期**：2026-11-05  
> **审阅仓库**：`git@github.com:Evenstar-E/slam_recovery.git`  
> **审阅版本**：`6d1f7e47fe329d58fd8d82db7c2273209e082b63` (`Address second-round review: remove unsupported P8/blend variants, enforce trajectory-dependent 6D FIM & holdout NIS, unify manifests and LaTeX`)  
> **文档内容**：
> 1. 最新代码更改（`a306f0f -> 6d1f7e4`）逐项核查结果（已解决项 vs. 剩余细节问题）  
> 2. 当前版本对冲击顶会（RSS / IEEE T-RO / ICRA / IROS）的成熟度评估  
> 3. Gazebo / Isaac Sim 实时闭环仿真实验设计方案（补齐真值三维地图污染率、受控相变与 R4/R5 反事实重访闭环）

---

> **当前执行优先级（2026-11-09）**：以本文第十部分为最新交接协议，启动固定条件下的 **测量修复 → 原生宿主状态重估 → 地图重建**。远端开发侧实现/运行，本机会话交接/审阅。前九部分保留为历史讨论，不据其旧阈值、旧实验数字或发表判断宣布系统闭环。停止为解释单个 NIS 值反复调整协议；先完成一条可复现的真实修复链。

## 第一部分：最新代码更改（`6d1f7e4`）深度审阅报告

在最新提交 `6d1f7e4` 中，仓库针对第二轮审阅指出的 8 项阻断级问题进行了果断且实质性的“做减法”与重构。经逐文件静态取证与 LaTeX 完整编译核查，**此前最严重的硬编码伪造章节与 JSON/正文反转矛盾已基本消除**。

### 1.1 本次提交已确认解决的 8 项关键问题（Verified Resolved）

1. **彻底删除了无真实运行支撑的第 VII-F 节（Phase/Pareto）与第 VII-G 节（SuperOdometry）**
   - 物理删除了硬编码脚本 `run_phase_and_pareto_analysis.py` 及其生成的 `fig6_phase_transition_and_pareto_sensitivity.{pdf,png}`。
   - 物理删除了无源码/日志支撑的汇总文件 `p8_phase_transition_and_pareto.json`、`p8_superodom_comparison.json` 和 `p8_outdoor_transition_benchmark.json`。
   - 消除了由此引发的 `room_dark_01` 旧版 ATE（`0.1800 m` vs `0.2154 m`）、`hall_01` 走廊退化 FAST-LIO2 ATE（`65.34 m` vs `7.4435 m`）以及 `OFFLINE_CONSTRUCT` 与 `REAL_HOST` 标签冲突。
2. **移除了 E2 消融实验中的线性拼接伪造变体（B1、B3、B7）**
   - 在 `slam_recovery/experiments/run_e2_ablation_matrix.py:112-208` 中，删除了此前用 `0.85 * d_deg + 0.15 * d_rep` 人工混合的 `construct_variant_trajectory` 函数。
   - 图 2（`fig2_b0_b7_ablation_matrix.pdf`）与 `e2_ablation_b0_b7_and_r4_r5.json` 现仅保留有轨迹支撑的 5 个核心变体（`B0`、`B2`、`B4`、`B5`、`B6`），且 `generate_paper_figures.py:102-210` 改为直接从 JSON Manifest 动态读取数据绘图。
   - 统一了 LIO-SAM B0（`5.9644 m`）、B5（`5.9954 m`, $G=-0.0055$）和 B6（`1.5139 m`, $G=+0.7883$）在 Manifest、表 II 与图 2 图注中的数值。
3. **`compute_6dof_point_to_plane_fim` 真正接入了测量噪声方差 $\sigma_{\mathrm{meas}}^2$**
   - 在 `slam_recovery/validation/fim_and_holdout.py:72-76` 中，修复了此前忽略 `sigma_meas_m` 的问题，现通过 `inv_var = 1.0 / max(float(sigma_meas_m) ** 2, 1e-6)` 计算 `fim_raw = inv_var * (J.T @ J) / float(len(p_valid))`，并支持叠加辅助里程计先验信息矩阵 `aux_odom_info_6x6`。
4. **E3 的 Holdout NIS 接入了候选轨迹的相对位姿扰动 $\Delta T_{\mathrm{cand}}$**
   - 在 `evaluate_e3_orbslam3.py:87-152` 和 `evaluate_room_dark_01.py:91-150` 中，新增了 `compute_candidate_holdout_nis_and_fim`：不再向 `compute_disjoint_holdout_point_to_plane_nis` 传入恒等阵 `np.eye(4)`，而是加载时间窗内的多帧真实 VLP-32C 点云，计算候选修复轨迹相对于独立健康 LiDAR 里程计的帧间位姿增量偏差 `trans_err`，构造 `delta_T` 变换奇数号留出点云（`scan_xyz[1::2]`）并针对偶数号训练点云（`scan_xyz[0::2]`）拟合平面计算点到面残差。
5. **修复了 `room_dark_01` 在 Manifest 中被门控拒绝但正文写为成功提交的反转错误**
   - 在叠加跨模态相对运动信息矩阵后，`manifests/e3_orbslam3_b6_room_dark_01.json:38-44` 中的 `weak_dir_info_after = 143.54 >= 25.0`、`holdout_nis = 1.1585 <= 2.5`，门控输出 `"gate_decision": "MODE2_ATOMIC_COMMIT"`、`"atomic_commit_accepted": true`，与论文表 III（第 350 行，`0.2154 m` ATE，$G=+1.0882$）及第 357 行正文完全对齐。
6. **对齐了引言贡献点、E1 正文与 Limitations 的表述**
   - 引言贡献点（`paper_main.tex:74-79`）与结论（`paper_main.tex:365-366`）已同步收窄为 `keyframe-level transactional recovery framework` 和 `operational screening condition`。
   - E1 正文（`paper_main.tex:250`）已同步修正为 `sklearn GBDT + IsolationForest` 和 `0.951 segment IoU`，与表 I 完全一致。
   - Limitations（`paper_main.tex:363`）诚实说明了当前事务管理器工作在关键帧位姿图与 rosbag 边界，尚未在 C++ 内部就地回滚 `ikd-Tree` 指针或 GTSAM `ISAM2` 边缘化先验。
7. **Campus 实验脚本接入了 `xyz_rev` 的评估比较**
   - `run_campus_and_overhead_benchmark.py:80-91` 现在计算了 `e2e_rev = float(np.linalg.norm(xyz_rev[-1] - xyz_rev[0]))` 并在 `hold_nis <= 2.5` 时纳入候选比较。
8. **LaTeX 提交包可一键编译通过**
   - `paper_submission_package/paper_main.tex` 已无语法错误，完整执行 `pdflatex -> bibtex -> pdflatex -> pdflatex` 生成 7 页 IEEEtran PDF，无未定义引用（仅第 117 行混合模型公式有 `12.4pt` 轻微超宽，将其改为 `split` 即可彻底消除）。

---

### 1.2 最新代码中仍需注意的 5 个残余技术问题（Remaining Technical Gaps）

尽管代码与论文的一致性已大幅提升，但从严格的代码审计角度看，`6d1f7e4` 仍存在以下 **5 个实现层面的薄弱点**，必须在后续实验迭代或仿真补充中解决：

1. **图 3（Gate 验证）和 B5/B6 的部分指标仍含有人为构造常数**
   - 在 `run_e2_ablation_matrix.py:131-132, 196-197` 中，`fl_b0_ate = 7.2760`、`lio_b5_ate = 5.9954` 以及 B5 的 `trusted_map_pollution_ratio = 0.5000`、`false_commit_rate = 0.500` 仍是直接赋值的字面量。
   - 在 `run_e2_ablation_matrix.py:218-285` 中，用于生成图 3 的 5 个门控案例（`gate_cases`）使用的是合成墙壁点云（`pts_single_wall`, `pts_full_room`）和手工指定的平移扰动向量（如 `T_drifted_b5[:3, 3] = [0.35, 0.28, -0.12]`），且第 266、276、281 行包含了 `8.42`、`* 1.15`、`65.00` 等硬编码/比例缩放数字。
2. **E3 的 Holdout NIS 评估的是“同帧奇偶点自配准 + 相对辅助轨迹差”，而非独立重投影/跨帧配准残差**
   - 在 `evaluate_e3_orbslam3.py:125-133` 中，`train_pts` 和 `hold_pts` 来自**同一帧** LiDAR 扫描的奇偶索引（它们在真实物理空间中的相对位姿严格为 $\mathbf{I}_4$）。代码把候选轨迹与辅助 LiDAR 里程计的位移差 `trans_err = d_cand - d_aux` 塞进 `delta_T` 去扰动同一帧点云的奇数点。
   - 这本质上是在用点云表面法向量作为权重，衡量 **`xyz_candidate` 与 `aux_in_host`（同一个用于构造 B6 桥接的辅助源）有多接近**，而不是用真正未参与桥接求解的独立传感器或跨帧点云配准来检验 `xyz_candidate`。由于 B6 本身就是用 `aux_in_host` 插值出来的，`d_cand - d_aux` 天然接近 0（仅差一个线性分摊的边界闭合差 `closure_err`），这会导致 B6 的 `holdout_nis` 天然偏小。
3. **Wilson 序列检验中仍残留人为偏置项**
   - 在 `evaluate_e3_orbslam3.py:390-401` 和 `evaluate_room_dark_01.py:291-301` 中，仍然存在 `inc_step_err = np.linalg.norm(d_inc - d_aux, axis=1) + 0.04` 以及用 `inc_step_err * 1.25` 评估 B5 的写法。应当直接使用真实残差，去掉 `+ 0.04` 和 `* 1.25`。
4. **“可信地图污染率”目前仍是轨迹关键帧位置误差代理，而非三维体素地图污染率**
   - `compute_pollution_ratio_via_manager`（`run_e2_ablation_matrix.py:63-110`）统计的是 `mgr.trusted_poses` 中关键帧位置误差 `pos_err[k] > 0.80 m` 的比例，并未检查点云地图体素（Voxel / ikd-Tree）相对于真实环境表面的几何畸变。
5. **仍缺冻结测试集（Held-out Test Split）与真实在线闭环 R0–R5 实验**
   - 目前主实验仍集中在 `hall_01`、`room_02`、`room_dark_01` 三个开发序列上；且位姿图桥接（LIO-SAM B6、ORB-SLAM3 B6）均为离线轨迹图重放（`OFFLINE_CONSTRUCT`）。

---

## 第二部分：为什么需要补充 Gazebo / Isaac Sim 实时仿真实验？

针对上述残余问题（尤其是**问题 1 的硬编码门控案例、问题 4 的真值三维地图污染率、问题 5 的在线闭环与 R4/R5 反事实对照**），在 **Gazebo 或 NVIDIA Isaac Sim** 中补充一组**实时在线闭环仿真实验**具有极高的学术性价比。

### 2.1 顶会审稿人（RSS / T-RO / ICRA）对 SLAM 仿真的评判准则

- **审稿人反感的仿真用法**：用简单的射线仿真代替真实数据集去宣称“传感器前端能抗真实雨雾/塑料袋”。（这一部分你已经有 M2DGR 和室外 Campus 的真实数据支撑，不需要靠仿真证明。）
- **审稿人高度认可的仿真用法**：
  1. **拥有 100% 精确的稠密三维环境网格真值（Ground-Truth 3D Mesh）**：可以直接计算持久化点云地图中偏离真实墙面超过阈值（如 $\tau_{\mathrm{map}} = 0.15\,\mathrm{m}$）的**真实污染体素比例（True 3D Map Voxel Contamination Ratio）**，彻底替代目前用轨迹误差充当的污染率代理。
  2. **严格受控的反事实重放（Exact Counterfactual Replay for R4 vs. R5）**：在录好的真实 rosbag 中，机器人轨迹无法更改；而在仿真器中，可以让机器人在前 40 秒经历**完全相同的退化区段**，随后一条分支继续盲走不回头（**R4：验证系统保持 Mode 3/4 绝不错误提交**），另一条分支在 60 秒时转弯重访起点触发回环（**R5：验证系统从 Waiting 状态被新证据唤醒，通过真跨帧点云 Holdout 检验并完成 Mode 2 原子提交**）。
  3. **真正的实时 ROS 在线节点闭环（`REAL_ONLINE_SIM`）**：将 `TrustedMapTransactionManager` 封装为实时订阅/发布 ROS 话题的在线节点，在仿真器实时运行 LIO-SAM / FAST-LIO2 的同时完成在线延迟提交缓冲、在线隔离与在线因子图更新，消除对 `OFFLINE_CONSTRUCT` 的质疑。

### 2.2 仿真平台选型对比：Gazebo vs. Isaac Sim

| 评估维度 | **Gazebo (Classic 11 / Gazebo Fortress)** | **NVIDIA Isaac Sim (Omniverse)** |
|---|---|---|
| **ROS 1 宿主兼容性** | **极高（首选）**。仓库中的 FAST-LIO2、SC-PGO、LIO-SAM、ORB-SLAM3 均基于 ROS 1；Gazebo 的 `velodyne_simulator`（含 `ring` 和 `time` 字段）与 `realsense_gazebo_plugin` 可直接驱动全部四个宿主，零格式兼容障碍。 | 需要通过 ROS 1 Bridge 或 OmniGraph 转换 RTX LiDAR 点云格式（需补齐 Velodyne 24 字节 point step 中的 `ring` 与相对 `time` 字段，否则 LIO-SAM 曲率提取会报错）。 |
| **传感器退化模拟能力** | 擅长：**几何长走廊（动态移动/隐藏墙体）、近场物理遮挡板（在雷达前挂载可调张角 $\theta_{\mathrm{occ}}$ 的旋转遮挡罩）、时间戳延迟、IMU 噪声注入**。 | 擅长：**物理级光线追踪（RTX）**，可逼真模拟自然暗光散粒噪声、相机动态模糊、体积雾（Volumetric Fog）及半透明材质多回波。 |
| **地面真值导出** | 原生发布 `/gazebo/model_states`（1000 Hz 零误差 6-DoF 位姿）且场景 `.dae/.stl` 网格可直接导出为高精度参考点云。 | 原生提供 USD Stage 精确网格与高帧率位姿真值。 |
| **开发周期** | **2～3 天**即可完成场景搭建、ROS 节点闭环与 S1–S3 实验采集。 | **1～2 周**（主要耗时在 USD 资产配置与 RTX LiDAR 自定义点云 Layout 适配）。 |

**推荐决策**：
- **主力定量实验用 Gazebo（ROS 1 Noetic）**：用 2～3 天快速跑通全部实时在线闭环定量实验（S1–S3），拿齐 100% 真实的轨迹、6D FIM、跨帧点云地图和 3D Mesh 污染率数据。
- **可选高颜值视觉展示用 Isaac Sim**：若本地有 RTX GPU 工作站，可用 Isaac Sim 录制一段 30 秒的暗光+体积雾走廊实时恢复视频（放入补充材料 Video Attachment 并截取 Fig. 1 概念图）。

---

## 第三部分：Gazebo / Isaac Sim 实时仿真实验详细设计方案

在仿真环境中，只需构建 **1 个模块化标准测试场**，运行 **3 组核心实时实验（S1、S2、S3）**，即可补齐当前论文全部证据短板。

### 3.1 仿真测试场设计（`recovery_arena.world`）

构建一个 $40\,\mathrm{m} \times 25\,\mathrm{m}$ 的“8”字形室内外混合测试场，包含四个功能区：
- **Zone A（高信息锚定区，$t \in [0, 15]\,\mathrm{s}$）**：布置正交货架、立柱与高纹理标定板，三轴平面法向量均匀分布（$\lambda_{\min}(\Lambda_u) \approx 33.0 \gg \tau_{\mathrm{info}}$）。
- **Zone B（参数化退化走廊，$t \in [15, 35]\,\mathrm{s}$）**：
  - **几何退化开关**：走廊两侧横向隔墙可通过 Gazebo Model Plugin 按实验配置动态移除，形成纯平滑纵向长走廊（$\lambda_{\min}^t \to 0.4$）。
  - **物理遮挡罩开关**：在机器人 Velodyne 雷达外侧 $r_{\mathrm{bag}} = 0.40\,\mathrm{m}$ 处挂载一个无质量半圆柱碰撞/反射壳体，其水平遮挡张角 $\theta_{\mathrm{occ}}/2\pi \in \{40\%, 60\%, 75\%, 88\%, 94\%\}$ 由 URDF/Xacro 参数精确控制。
  - **光照控制开关**：顶部点光源强度可在线阶跃或斜坡衰减（模拟进入全黑房间）。
- **Zone C（恢复过渡区，$t \in [35, 50]\,\mathrm{s}$）**：重新出现结构化几何特征与正常光照。
- **Zone D（反事实分叉口，$t \in [50, 70]\,\mathrm{s}$）**：
  - **路径分支 R4（不重访）**：沿直道驶向未知新区域，无任何历史地图交集；
  - **路径分支 R5（闭环重访）**：右转绕回 Zone A，与 $t \in [5, 12]\,\mathrm{s}$ 的可信关键帧形成强几何回环。

---

### 3.2 三组核心实时仿真实验矩阵

#### 实验 S1：真实在线 R4 vs. R5 反事实事务生命周期验证（替换 `run_e2_ablation_matrix.py` 中的合成 `gate_cases`）

- **实验目的**：在完全真实的在线 ROS 节点中证明“回滚不能凭空造信息（R4 安全等待/拆图）”与“新独立证据唤醒事务并完成原子提交（R5）”。
- **运行配置**：
  - 机器人搭载 VLP-32C + D435i + 200 Hz IMU，在线运行 `FAST-LIO2 / LIO-SAM` + `slam_recovery_ros_node`。
  - 在 Zone B 同时开启 **平滑长走廊 + 关灯（双模态退化）**。
  - 分别执行轨迹 R4（直行不回头，5 个随机种子）和轨迹 R5（第 55 秒重访 Zone A，5 个随机种子）。
- **真实的跨帧 Holdout 验证实现（消除同帧奇偶点自配准缺陷）**：
  - 将隔离窗口内每第 $5k$ 帧的完整点云扫描设为 **Holdout Scan Set $\mathcal{S}_{\mathrm{hold}}$**（完全不参与因子图重优化）；
  - 当候选修复轨迹 $X_{\mathrm{cand}}$ 生成后，用 $X_{\mathrm{cand}}$ 的绝对位姿将 $\mathcal{S}_{\mathrm{hold}}$ 中的点云变换到世界系，直接与检查点可信地图 $\mathcal{M}_{\mathrm{trusted}}$（以及重访锚点帧）计算**真实的跨帧点到面配准 NIS**。
- **输出指标与图表**：
  - 替换论文 Fig. 3，使图中的每一个柱状图（$\Delta J_v$、跨帧 Holdout NIS、门控模式）均来自 S1 的真实在线节点日志。

#### 实验 S2：基于 Ground-Truth 3D Mesh 的真实三维体素地图污染率与延迟提交缓冲实验

- **实验目的**：用无可辩驳的三维几何真值证明 $\Delta t_{\mathrm{margin}} = 2.0\,\mathrm{s}$ 延迟提交环形缓冲区对持久化地图的保护作用。
- **地图污染率严格定义**：
  设仿真环境导出的精确静态表面网格为 $\mathcal{G}_{\mathrm{GT}}$，系统在时刻 $t$ 已永久提交到可信地图中的点云体素集合为 $\mathcal{V}_{\mathrm{trusted}}(t)$（体素分辨率 $0.10\,\mathrm{m}$）。定义**真实三维可信地图污染率（True 3D Trusted-Map Voxel Contamination Ratio）**为：
  $$\mathrm{Contam}_{3\mathrm{D}}(t) = \frac{1}{|\mathcal{V}_{\mathrm{trusted}}(t)|} \sum_{v \in \mathcal{V}_{\mathrm{trusted}}(t)} \mathbb{I}\!\left(\min_{g \in \mathcal{G}_{\mathrm{GT}}} \|v - g\|_2 > \tau_{\mathrm{map}}\right), \qquad \tau_{\mathrm{map}} = 0.15\,\mathrm{m}.$$
- **对比变体**：
  - `B0`（原始宿主，无隔离）；
  - `B2`（MM-LINS 连续 $N_\kappa=10$ 帧确认后休眠，$\Delta t_{\mathrm{margin}} = 0\,\mathrm{s}$）；
  - `B4`（本文 $\Delta t_{\mathrm{margin}} = 2.0\,\mathrm{s}$ 延迟提交隔离，不修复）；
  - `B6`（本文延迟提交隔离 + 验证后原子提交）。
- **预期核心结果**：清楚展示 B2 在确认延迟期内将 $N_\kappa$ 帧漂移点云永久写入睡眠子地图导致 $\mathrm{Contam}_{3\mathrm{D}} > 15\%$，而 B4 与 B6 在整个退化期间保持 $\mathrm{Contam}_{3\mathrm{D}}(t) < 0.5\%$。

#### 实验 S3：受控物理遮挡角 $\theta_{\mathrm{occ}}$ 在线扫描（可选，用于恢复相变分析）

- **实验目的**：如果你希望在论文中保留“单模态点云剥离可修复性边界（Direct IEKF vs. Feature LOAM）”这一亮点结论，绝对不能用手写数组，而应在 Gazebo 中通过 URDF 参数真实设置 $\theta_{\mathrm{occ}}/2\pi \in \{40\%, 60\%, 75\%, 88\%, 94\%\}$ 五档物理遮挡罩，每档真实跑完 LIO-SAM 和 FAST-LIO2 并保存 10 个 rosbag / 轨迹 manifest。

---

## 第四部分：下一步行动路线图（Action Plan）

1. **立即可做的代码微调（半天内完成）**
   - 修复 `paper_submission_package/paper_main.tex:116` 的混合模型单行公式轻微超宽（改为 `split` 环境，消除最后 1 个 `Overfull \hbox`）。
   - 修改 `evaluate_e3_orbslam3.py` 与 `evaluate_room_dark_01.py`，将 Holdout NIS 从“同帧奇偶点 + 相对辅助轨迹差”改为**“留出帧点云经候选轨迹变换到可信锚点帧的跨帧点到面残差”**，并删掉 Wilson 检验中的 `+ 0.04` 和 `* 1.25` 人工偏置。
   - 修改 `run_e2_ablation_matrix.py:218-285`，使图 3 的 5 个门控案例直接读取真实实验 manifest 中的 FIM 与 Holdout NIS，不再使用脚本内硬编码的 `8.42`、`65.00` 和 `* 1.15`。
2. **搭建 Gazebo 实时闭环实验（2～3 天完成）**
   - 在 Ubuntu + ROS 1 Noetic 环境中创建 `slam_recovery_sim` 包，包含 `recovery_arena.world` 和实时在线节点 `transaction_manager_node.py`。
   - 跑通实验 S1（R4 vs. R5 反事实闭环）与实验 S2（基于真值 3D Mesh 的体素污染率），将生成的真实 manifest 和点云污染对比图增补进论文第 VII 节。
3. **补齐 M2DGR 冻结测试集（2～3 天完成）**
   - 在未调参的测试集序列（至少 `hall_02`、`room_dark_02`、`street_08`）上跑通 B0、B2、B6，彻底满足研究方案中的开发/测试隔离协议。

---

## 第五部分：针对最新提交（`00080c1` & `fb9e655`）的增量验收结论与 4 条最终收口意见

> **验收日期**：2026-11-05  
> **验收对象**：`00080c1`（S1/S2 三维网格体素仿真、跨帧点面 Holdout NIS、零字面常数 E2、留出测试集 `hall_02` 盲测）与 `fb9e655`（6 个有界反例 R1–R6 完整修复与回归测试集）。

### 5.1 已通过验收的里程碑（Pass ✅）

1. **6 项有界反例（R1–R6）100% 闭环并固化为单元测试**（`slam_recovery/tests/test_atomic_commit.py:160-212`）：
   - **R1（Checkpoint Keyframe ID 与 Shape 哈希绑定）**：`Checkpoint.compute_hash()` 已将 `f"kf:{int(k)}:shape:{arr.shape}:"` 纳入 SHA-256，消除篡改关键帧 ID 的哈希碰撞；
   - **R2（迟检 $\Delta t_{\mathrm{det}} > \Delta t_{\mathrm{margin}}$ 的 Undo-Log 撤销回滚）**：`TrustedMapTransactionManager` 新增 `promoted_history` 撤销日志，当 `t_q_start` 早于已晋升帧时，自动从 `trusted_poses` 与 `trusted_factors` 中剥离污染帧并退回隔离队列，同时恢复 IMU 零偏；
   - **R3（非有限值 `NaN/Inf` 拦截）**：`evaluate_four_mode_gate()` 入口强制检查 `repaired_poses`、`info_after_6x6`、`cov_after_6x6` 与 `holdout_nis` 的 `np.isfinite()`，含 `NaN/Inf` 的候选分支一律打回 Mode 3/4；
   - **R4（旋转-平移 6D 耦合弱方向检测）**：`analyze_decoupled_information()` 增加了完整 $6\times 6$ 矩阵特征分解，当 $\lambda_{\min}(\Lambda_{6\times 6}) < \min(\lambda_{\min}^r, \lambda_{\min}^t)$ 时准确捕获跨块耦合退化方向；
   - **R5（Holdout 残差截断与内点覆盖率联锁门控）**：`compute_disjoint_holdout_point_to_plane_nis()` 新增 `inlier_coverage < 0.70` 约束，若超过 $30\%$ 的留出点残差达到或超过 $2.0\,\mathrm{m}$ 截断阈值，则禁止截断分母，直接返回全量未截断均方残差；
   - **R6（Mode 2 原子提交同步更新因子与偏置）**：`CandidateMap` 新增 `repaired_factor_ids` 与 `repaired_bias_acc/gyr`，Mode 2 提交时同步更新 `trusted_poses`、`trusted_factors` 和 IMU 零偏。
2. **E3 跨帧点面 Holdout NIS 与无偏 Wilson 检验落地**（`evaluate_e3_orbslam3.py:117-162, 414-433`）：
   - 彻底移除了单帧奇偶点 + `aux_in_host` 代理残差，改用相隔 5 帧的真实点云对 $(\mathcal{S}_{k-5}, \mathcal{S}_k)$ 仅按候选轨迹相对位移 $\Delta p_{\mathrm{cand}}$ 变换后的点到面配准 NIS，并删除了 `+0.04`/`+0.05` 与 `*1.15`/`*1.25` 人工偏置常数。
3. **留出测试集 `hall_02` 零微调盲测补齐**（`evaluate_hall_02.py` & 论文表 II、表 III）：
   - 在冻结开发集超参数下完成了 `hall_02` 四宿主清洁基线、88% 塑料袋遮挡（FAST-LIO2 $4.53\to 0.28\,\mathrm{m}$、MM-LINS $4.03\to 0.24\,\mathrm{m}$、LIO-SAM $3.42\to 0.24\,\mathrm{m}$）与 ORB-SLAM3 严重暗光（窗口 RMSE $1.84\to 0.61\,\mathrm{m}$）评测。

---

### 5.2 截稿前需收口的 4 条具体改进意见（Action Required ⚠️）

#### 意见 1：将 Wilson 序列收益与重入连续性检查正式并入 `validate_and_resolve()` 门控内部（消除“先提交字典、后算 Wilson”的顺序倒挂）
- **现状与问题**：在 `evaluate_e3_orbslam3.py:412-432` 中，脚本先调用了 `val_report = tx_mgr.validate_and_resolve(candidate=cand)`（此时若满足 FIM 与 Holdout NIS，`trusted_poses` 字典已被原地修改且状态已置为 `HEALTHY`），随后在第 421–432 行才计算 `evaluate_paired_sequential_benefit()`。后验 Wilson 拒绝无法撤销已发生的字典合入。
- **收口方案**：在 `CandidateMap`（`slam_recovery/core.py:171`）中增加可选字段 `paired_benefit_approved: bool = True`（或 `wilson_lower_bound` 与 `reentry_pos_jump_m`），并在调用 `validate_and_resolve()` **之前**完成 `evaluate_paired_sequential_benefit()`，将其作为 Mode 2 原子提交的前置必要条件。

#### 意见 2：在 `compute_6dof_point_to_plane_fim()` 中同步应用 R4 的 6D 耦合弱方向逻辑
- **现状与问题**：虽然 `slam_recovery/health/detector.py:59-81` 的 `analyze_decoupled_information()` 已经修复了 R4（同时检查 $6\times 6$ 全矩阵最小特征值），但 `slam_recovery/validation/fim_and_holdout.py:83-94` 中的 `compute_6dof_point_to_plane_fim()` 仍只计算 `fim_u[:3, :3]` 与 `fim_u[3:, 3:]` 两个 $3\times 3$ 对角块，并将 `weak_6d` 仅填入前 3 维或后 3 维。
- **收口方案**：在 `compute_6dof_point_to_plane_fim()` 和 `evaluate_e3_orbslam3.py:152-159` 中统一加入 `vals_6d, vecs_6d = np.linalg.eigh(0.5 * (fim_u + fim_u.T))` 判断，确保检测端与验证端的 6D 弱方向定义完全一致。

#### 意见 3：清理 `run_s1_s2_simulation_experiments.py` 中的 3 处人为缩放系数，并在论文中精准界定 `ONLINE_SIM_3D_MESH` 的物理性质
- **现状与问题**：
  1. `run_s1_s2_simulation_experiments.py:231` 对 B5 的三维体素污染率硬乘了 `0.5 *`（`0.5 * arena.compute_3d_voxel_contamination_ratio(voxels_b5)`），理由是“一半宿主污染、一半宿主不污染”，容易被审稿人视为人为系数；
  2. `run_s1_s2_simulation_experiments.py:240, 257, 271` 在 R5 与 B6 中手工传入了对角矩阵 `aux_or_loop_info_6x6=np.diag([30, 30, 30, 22.0, 22.0, 22.0])`；
  3. `transaction_manager_node.py:213` 将 `cov_after_6x6` 乘了 `0.05`（`cov_after * 0.05`）以匹配均值归一化 FIM 的尺度。
- **收口方案**：
  - 分别独立报告 `B5_FAST_LIO2` 与 `B5_LIO_SAM` 的三维体素污染率（或直接报告未乘 `0.5` 的原始单模态盲目提交污染率），去掉 `0.5 *`；
  - 将 `compute_6dof_point_to_plane_fim` 的信息矩阵尺度与 `sigma_tol` 物理对齐，使 R5 在重访 Zone A 柱面与端墙时完全依靠真实点面雅可比 $\sum J_i^\top R_i^{-1} J_i$ 自然跨过 $\tau_{\mathrm{info}}=25.0$ 和 $\Sigma_{\mathrm{tol}}=0.50$，无需手工传入对角矩阵和 `* 0.05`；
  - 在 `paper_main.tex` 第 VI-E 节和图 2/图 3 图注中明确标注 S1/S2 为 **解析三维网格光线采样仿真（Analytical 3D-Mesh Ray-Sampling Simulation, Provenance: `ONLINE_SIM_3D_MESH`）**，与真实宿主 rosbag 实验（`REAL_HOST` / `INJECTION`）严格区分。

#### 意见 4：在 `docs/review_20261105/README.md` 顶部标注 R1–R6 已解决状态
- **现状与问题**：`d5bd4df` 提交的 `docs/review_20261105/README.md` 记录的是 `fb9e655` 之前的旧版缺陷。若不加状态说明，外部读者浏览仓库时会误以为 R1–R6 尚未修复。
- **收口方案**：在 `docs/review_20261105/README.md` 顶部添加醒目的版本演进说明，逐条指出 R1–R6 及跨帧 Holdout NIS 已在 `00080c1` 与 `fb9e655` 中完成修复并由回归测试集验证。

---

## 第六部分：实验矩阵完备性体检、待补实验清单与最新提交 `135629c` 验收报告

> **更新时间**：2026-11-05  
> **验收版本**：`135629cec083b7c6d39f04d94751ec39dde368a5`（`Integrate FAST_LIVO2 shared core: SpatialMutationLog CoW journal, Proposition 2 identifiability, and 48-Cell PhysicsGuidedCausalTransformer`）

### 6.1 最新提交 `135629c` 的代码侧逐行验收（Code Audit Report）

在 `135629c` 中，仓库将 `FAST_LIVO2_SHARED_CORE_EXTRACTION.md` 提出的三大核心架构落地为代码、单元测试、真实 bag 实验（`p9` manifest）并同步更新了论文 `paper_main.tex`。逐项核验结论如下：

#### 1. 通过验收的核心模块（Pass ✅）
- **`SpatialMutationLog` & `MutationRedoImage`（[`slam_recovery/quarantine/spatial_mutation_log.py`](slam_recovery/quarantine/spatial_mutation_log.py)）**：
  - 完整实现了空间地图的 First-Write Before-Image 写时复制（`before_images`）、新增键零拷贝记录（`inserted_keys`）以及双分支原地重放镜像（`capture_mutation_redo` / `consume_mutation_redo`）；
  - 在 `hall_01` 真实点云构建的 $20\,\mathrm{cm}$ 全局体素地图（$|M|=594,979$ 体素，隔离窗脏集 $|\Delta M_{\mathrm{dirty}}|=82,219$ 体素，占 $13.8\%$）上实测：全图深拷贝快照耗时 $1771.38\,\mathrm{ms}$，而 `SpatialMutationLog` 回滚耗时仅 **$92.83\,\mathrm{ms}$（$19.08\times$ 加速）**，且回滚后键值 100% 精确一致。
- **命题 2 正交补空间可辨识度 $\mathcal{I}_\perp(s \mid H)$ 与 48-Cell 球面几何编码（[`slam_recovery/health/spherical_cells_and_identifiability.py`](slam_recovery/health/spherical_cells_and_identifiability.py)）**：
  - 严格实现了 $s_\perp = (I - H(H^\top H)^\dagger H^\top)s$ 与 $\mathcal{I}_\perp(s \mid H) = \|s_\perp\|_2^2 / \|s\|_2^2 \in [0, 1]$；
  - 在 `hall_01`、`room_02`、`hall_02` 真实扫描帧上验证：完整多墙面扫描 $\mathcal{I}_\perp = 0.8545 \sim 0.9078$（可辨识），塑料袋剥离后仅剩 12% 窄扇区时 $\mathcal{I}_\perp$ 骤降至 $0.0676 \sim 0.0907$，长走廊纵向失明与伴随移动塑料袋平面平移时 $\mathcal{I}_\perp = 0.0000$（与 6-DoF 刚体位姿完全共线，数学上证明单模态内环参数拟合不可辨识）。
- **`PhysicsGuidedCausalTransformer` + `ConditionalRecoveryHead`（[`slam_recovery/diagnosis/causal_transformer.py`](slam_recovery/diagnosis/causal_transformer.py)）**：
  - 实现了零数据集统计拟合的物理单位 `arcsinh` 压缩（`PHYSICAL_UNITS_12D`）、纯因果历史中位数差分 $\tilde{\delta}_t$、48-Cell 置换不变池化、2 层因果相对距离偏置注意力（$M=64$ FIFO 缓存）以及链式法则起点年龄头 $\log P(\tau_{\mathrm{age}}=k\Delta\tau) = \log\sigma(a_t) + \log\operatorname{softmax}(u_t)_k$；
  - 严格执行了冷启动解析回退（`past_ready == False` 时无缝回退 `SignatureMatrixRouter`）与权重 SHA-256 冻结（`c5a65870...`），单步推理 P50 仅 $618.5 \sim 642.7\,\mu\mathrm{s}$。

#### 2. `135629c` 代码侧新发现的 3 处需要修正的技术瑕疵（Must Fix Before Submission ⚠️）
1. **`run_e1_detection_benchmark.py:270` 对 Method 6 人为清空了 `mgr.promoted_history.clear()`**：
   - 在 `simulate_map_buffer_tail_pollution()` 第 269–270 行，为了展示 Method 6（固定 2s 缓冲）无法回滚超出 2s 的慢斜坡帧，代码写了 `rollback_onset_ns = w.t_start_ns - int(2.0 * 1e9)` **并紧接着调用了 `mgr.promoted_history.clear()`**。
   - 实际上，因为 `trigger_quarantine(estimated_onset_ns)` 内部计算的是 `t_q_start = estimated_onset_ns - confirmation_margin_ns`，如果 Method 6 没有起点回溯头，它的点估计就是 `estimated_onset_ns = w.t_start_ns`（即 $\hat{\tau}_{\mathrm{age}} = 0$），传入 `trigger_quarantine(estimated_onset_ns=w.t_start_ns)` 后自然得到 `t_q_start = w.t_start_ns - 2.0s`！根本不需要、也不应该手工清空 `mgr.promoted_history.clear()`，直接传入 `estimated_onset_ns = w.t_start_ns` 即可自然体现固定 2s 回滚与自适应 $\hat{\tau}_{\mathrm{age}}$ 回滚的真实差异。
2. **`causal_transformer.py:97-117` 的底层注意力投影矩阵未参与梯度更新（Extreme Learning Machine / Random Feature Projection 形态）**：
   - 在 `PhysicsGuidedCausalTransformer.fit()`（第 200–260 行）中，闭式岭回归更新的是顶层输出头 `W_act`、`W_age`、`W_cause`，而 48-Cell MLP（`W_sp1, W_sp2`）和两层 `RelativeAttentionBlock` 的 `W_Q, W_K, W_V, W_O` 保持为固定随机正交/高斯投影特征（Reservoir / Random-Feature Causal Attention），且在第 181 行将 `rep[-1] = ramp_slope` 覆写了 `h2` 的最后一个维度。
   - **修改建议**：
     - 将 `ramp_slope` 作为独立维度拼接到 `rep`（`feat_dim = 80 + self.d_model + 1`），不要覆写 `h2[-1]`；
     - 在论文与文档中要么明确表述为 **“Closed-Form Ridge-Readout Causal Relative-Attention Reservoir / Network”**（凸显无需 GPU、秒级确定性闭式训练的优势），要么补上对 `W_Q, W_K, W_V` 的端到端 BP 微调。
3. **`run_identifiability_and_transformer_real_bags.py:254-281` 的 `build_real_bag_window_stream` 混合了真实点云特征与合成标量公式**：
   - 该函数前半部分（第 224–253 行）确实从真实 M2DGR bag 点云提取了 48-Cell 球面张量 `cells_48` 和真实点到面雅可比特征值 `min_eig_t, min_eig_r`，但后半部分（第 261–281 行）在 `in_fault` 期间用公式覆盖了 `min_eig_t`、`nis_mean` 和 `loso_p`。
   - **修改建议**：保留真实点云在 `inject_plastic_bag_near_field_occlusion` 和走廊裁剪后直接算出的真实 `min_eig_t, min_eig_r`（不要在第 263/267 行用常数公式覆盖它！），并在 manifest 中将这部分诚实标注为 `SEMI_SYNTHETIC_ON_REAL_SCANS`。

---

### 6.2 实验矩阵完备性体检与待补实验清单（Completeness Roadmap）

对照 RSS / IEEE T-RO 顶会标准，从 **退化种类、宿主覆盖、同类方法对比、消融与数据集** 四个维度列出当前状态与待补实验清单：

| 维度 | 已完成的覆盖（Current Coverage） | 仍需补齐的实验缺口（Remaining Gaps to Fill） | 优先级 |
|---|---|---|---|
| **1. 退化种类覆盖**<br>*(Degradation Taxonomy)* | 已覆盖 5 类正交机理（`GEO_DEGEN`, `MEAS_CONTAM`, `SYNC_DRIFT`, `LOOP_OUTLIER`, `AUX_DEGEN`）、$3\times$ 并发复合退化、以及 `135629c` 新增的 $4.0\,\mathrm{s}$ **慢斜坡退化（Slow-Ramp）**。 | **待补实验 E-Gap 1（近墙/窄门正常通行 Hard-Negative 负例测试）**：<br>在 `room_02` / `hall_02` 正常贴近真实墙面（距离 $<1.5\,\mathrm{m}$）转弯时，统计 RANSAC 近场平面剥离器的**误触发率（False Positive Rate = 0%）**，证明联合 NIS/$D_{\mathrm{LOSO}}$ 门控不会误杀真实近场承重墙。 | **P0（高）** |
| **2. 同类方法对比**<br>*(SOTA Baselines)* | 已对比：<br>- MM-LINS (T-IV 2025)<br>- ORB-SLAM3 Atlas (T-RO 2021)<br>- Zhang et al. 特征值法 (ICRA 2016)<br>- NIS / CUSUM / Raw-GBDT | **待补实验 E-Gap 2（补齐 B1 在线方向投影/X-ICP 风格基线 & B3 同数据纯回滚基线）**：<br>1. 在主消融表 E2（Fig. 2）中补齐 **`B1: Online Directional Projection / Remapping (Mode 1 Only, Zhang/X-ICP style)`** 与 **`B3: Rollback Only on Same Corrupted Data (Proposition 1 verification)`**，使 B0–B6 连续完整；<br>2. 增加 **纯后端 GNC（Backend-Only GNC without Quarantine）** 在连续 20s 塑料袋遮挡与 100ms 时间失步上的失效对比，证明前端隔离不可替代。 | **P0（高）** |
| **3. 宿主 SLAM 覆盖**<br>*(Host Systems)* | 已覆盖 4 大异构宿主：<br>- FAST-LIO2（IEKF 直接法）<br>- LIO-SAM（GTSAM 因子图特征法）<br>- MM-LINS（多地图 LIO）<br>- ORB-SLAM3（多地图 VSLAM） | **待补实验 E-Gap 3（提升主宿主空间地图回滚的原生闭环度）**：<br>1. 将 `SpatialMutationLog` 直接接入 `OnlineRecoveryTransactionNode` 的体素地图维护中，使 S1/S2 与 `hall_01` 体素地图回滚共用同一套 CoW 事务引擎；<br>2. （Stage 2 目标）在 1 个 C++ 主宿主（FAST-LIO2 或 LIO-SAM）中接通在线点云地图回滚接口，减少对 `OFFLINE_CONSTRUCT` 的依赖。 | **P1（中）** |
| **4. 数据集与指标完备性**<br>*(Datasets & Metrics)* | 开发集：`hall_01`, `room_02`, `room_dark_01`<br>测试集：`hall_02` + 4 条室外 `Campus` | **待补实验 E-Gap 4（旋转误差指标与额外留出序列）**：<br>1. 在 `trajectory_eval.py` 中补充 **旋转均方根误差 $\mathrm{ATE}_{\mathrm{rot}}$ (deg)** 与完整 $\mathrm{SE}(3)$ RPE，强化 `SYNC_DRIFT`（快速转弯去畸变扭曲）的说服力；<br>2. 在 `room_dark_02` 或室外 `street_08` 上再补一组零微调盲测。 | **P1（中）** |
| **5. 前序 4 项代码收口**<br>*(Code Closure)* | 已在 `fb9e655` 解决 R1–R6。 | **待补代码 C-Gap 1–3**：<br>1. 将 Wilson 检验移入 `validate_and_resolve()` 门控内部（消除 E3 先提交后检验顺序倒挂）；<br>2. 在 `fim_and_holdout.py` 中同步 6D 耦合特征分解；<br>3. 清理 `run_s1_s2_simulation_experiments.py` 中的 `0.5 *` 与 `* 0.05` 缩放系数，以及 `run_e1_detection_benchmark.py:270` 的 `promoted_history.clear()`。 | **P0（立即）** |

---

## 第七部分：针对最新提交 `4d1e333` 的自动验收报告与最后 2 处精细打磨指令

> **更新时间**：2026-11-05  
> **验收版本**：`4d1e333`（`Address all 135629c code audit items and complete E-Gap 1-4 benchmarks`）

### 7.1 已通过验收的 8 项重大修复与实验补强（Pass ✅）

1. **`C-Gap 1`（Wilson 序列收益与重入连续性门控前置）**：
   - `CandidateMap`（[`slam_recovery/core.py:183-185`](slam_recovery/core.py#L183-L185)）新增了 `paired_benefit_approved: bool = True`、`wilson_lower_bound` 与 `reentry_pos_jump_m`；
   - `evaluate_four_mode_gate()`（[`slam_recovery/core.py:282`](slam_recovery/core.py#L282)）已将 `bool(candidate.paired_benefit_approved)` 作为 Mode 2 原子提交的硬性条件；
   - `evaluate_e3_orbslam3.py`（第 415–436 行）与 `evaluate_room_dark_01.py` 均已改为**先计算 `evaluate_paired_sequential_benefit()`，再构造 `CandidateMap` 并调用 `validate_and_resolve()`**，彻底根除了“先提交字典、后算 Wilson”的顺序倒挂。
2. **`C-Gap 2`（验证端 6-DoF 耦合弱方向统一）**：
   - `compute_6dof_point_to_plane_fim()`（[`slam_recovery/validation/fim_and_holdout.py:85-98`](slam_recovery/validation/fim_and_holdout.py#L85-L98)）与 `evaluate_e3_orbslam3.py:151-158` 已同步加入 `vals_6d, vecs_6d = np.linalg.eigh(0.5 * (fim_u + fim_u.T))`，当 `min_6d < min(min_r, min_t)` 时提取完整 6D 耦合弱方向向量。
3. **`C-Gap 3`（消除 `promoted_history.clear()`、`h2[-1]` 覆写与 S1/S2 缩放系数）**：
   - [`run_e1_detection_benchmark.py:265-273`](slam_recovery/experiments/run_e1_detection_benchmark.py#L265-L273) 删除了 `mgr.promoted_history.clear()`，直接传入 `estimated_onset_ns = w.t_start_ns`，完全依靠 `TrustedMapTransactionManager` 原生逻辑体现固定 2s 缓冲与自适应 $\hat{\tau}_{\mathrm{age}}$ 的差异；
   - [`causal_transformer.py:120, 180`](slam_recovery/diagnosis/causal_transformer.py#L180) 将 `ramp_slope` 独立拼接为第 113 维特征（`feat_dim = 80 + 32 + 1 = 113`），并在论文与 manifest 中明确表述为 `Closed-Form Ridge-Regularized Readout` 與 `SEMI_SYNTHETIC_ON_REAL_SCANS`；
   - [`run_s1_s2_simulation_experiments.py:255-267`](slam_recovery/sim/run_s1_s2_simulation_experiments.py#L255-L267) 与 [`transaction_manager_node.py:219`](slam_recovery/sim/transaction_manager_node.py#L219) 删除了 `0.5 *`、`* 0.05` 和 R5/B6 Point-Mixture 的手工对角阵，并在论文第 VI-E 节和图 2/图 3 图注中明确标注为 `Analytical 3D-Mesh Ray-Sampling Simulation (ONLINE_SIM_3D_MESH)`。
4. **`E-Gap 1`（近墙/窄门正常通行 Hard-Negative 负例测试）**：
   - 新增 [`run_hard_negative_and_rot_ate_benchmark.py`](slam_recovery/experiments/run_hard_negative_and_rot_ate_benchmark.py) 与 `p10` manifest：在 `room_02`（76/76 帧近场点占比均值 $79.87\%$）与留出集 `hall_02`（62/86 帧近墙）上，纯几何 RANSAC 近场过滤的误剥离率达 $100.0\%$，而本文 NIS/$D_{\mathrm{LOSO}}$ 门控下的误报率与误剥离率均为 **$0.00\%$**。
5. **`E-Gap 2`（补齐 `B1` 在线方向投影、`B3` 同数据纯回滚与纯后端 GNC 对比）**：
   - 在 E2（[`run_e2_ablation_matrix.py:140-241`](slam_recovery/experiments/run_e2_ablation_matrix.py#L140-L241)）和 S2 中完整补齐了 `B1` 与 `B3`，使图 2 形成连续完整的 `B0–B6` 消融链；同时验证了无前端隔离的纯后端 GNC 在 20s 塑料袋遮挡下几乎无效（$6.1254\,\mathrm{m} \to 6.1065\,\mathrm{m}, G=+0.0032$）。
6. **`E-Gap 3`（`SpatialMutationLog` 接入在线事务节点）**：
   - [`transaction_manager_node.py`](slam_recovery/sim/transaction_manager_node.py) 已内置 `self.voxel_journal = SpatialMutationLog()`，并在 B5 验证被拒时直接调用 `rollback_mutation_journal()` 回滚试写体素。
7. **`E-Gap 4`（完整 $\mathrm{SE}(3)$ 旋转误差 $\mathrm{ATE}_{\mathrm{rot}}$ / $\mathrm{RPE}_{\mathrm{rot}}$ 评测）**：
   - [`trajectory_eval.py`](slam_recovery/experiments/evaluation/trajectory_eval.py) 新增了基于四元数/切向旋转对齐的 `evaluate_rotation_ate_rpe_deg()`，并在论文中报告了 `hall_01`、`hall_02` 与 `room_dark_01` 的旋转精度恢复。

---

### 7.2 最后 2 处“公式痕迹”微调指令验收结果（All Resolved in Commit `c2be378` ✅）

开发侧在提交 `c2be378`（`Complete final 2 polish items from commit 8c370a3 auto-review`）中已完成最后两项微调，经逐行代码核查确认 **100% 通过最终验收（Final Sign-Off Passed）**：

1. **微调指令 1 已闭环（[`run_hard_negative_and_rot_ate_benchmark.py:267-359`](slam_recovery/experiments/run_hard_negative_and_rot_ate_benchmark.py#L267-L359)） ✅**：
   - 已彻底删除 `1.42 * dt_in`、`np.hypot` 和 `+ 6.85` 手工公式；
   - 改为直接从 `hall_01_geodegen_comparison.mcap` 和 `hall_01_plasticbag_comparison.mcap` 读取真实宿主退化与修复轨迹，调用 `evaluate_rotation_ate_rpe_deg()`（结合 `_estimate_planar_heading_rotations()` 切向航向角构造）计算真实旋转误差：LIO-SAM 在 `GEO_DEGEN` 下 $\mathrm{ATE}_{\mathrm{rot}}$ 从 $75.449^\circ$（Max $157.35^\circ$）恢复至 **$4.653^\circ$（$G_{\mathrm{rot}}=+0.9881$）**，在 `MEAS_CONTAM` 下从 $86.233^\circ$ 恢复至 **$3.716^\circ$（$G_{\mathrm{rot}}=+1.0011$）**，并已同步更新 `p10` manifest 与 `paper_main.tex`。
2. **微调指令 2 已闭环（[`run_identifiability_and_transformer_real_bags.py:379-427`](slam_recovery/experiments/run_identifiability_and_transformer_real_bags.py#L379-L427)） ✅**：
   - 已彻底删除 `+ 0.40` 字面常数；
   - 改为直接实例化并运行 `TrustedMapTransactionManager(confirmation_margin_ns=int(2.0 * 1e9))`，通过 `step_healthy()` 与 `trigger_quarantine()` 实测 `trusted_poses` 中残留的慢斜坡污染帧数（固定 2s 规则残留 `2.0` 帧 vs. Causal Transformer `0.0` 帧），并已同步更新 `p9` manifest。

---

## 第八部分：对称多模态架构升级后的最后两项实验扩充任务（Action Items for Dev Side 🚀）

> **更新时间**：2026-11-06  
> **背景说明**：系统架构图（`fig0_system_architecture`）已升级为 **IMU + LiDAR + Vision 三路平权对称架构**。为使实验部分与该对称多模态架构 100% 呼应，并彻底打消审稿人关于“直接用紧耦合 LIVO（如 FAST-LIVO2）是否就能自体免疫退化”以及“恢复层内部各子组件各自贡献多大”的疑问，请远端开发侧完成以下两项高价值实验扩充并合入仓库与论文。

### 8.1 任务一：新增第 5 宿主 **`FAST-LIVO2`（紧耦合 LiDAR-Inertial-Visual Odometry）** 的退化与可验证恢复对比实验

#### 1. 核心科学问题与实验动机
审稿人看到我们的多模态架构图后必然会问：*“如果直接使用 SOTA 紧耦合激光-视觉-惯导系统 **FAST-LIVO2**，当单一模态退化时，其 ESIKF 是否已经能靠另一模态自然维持精度，而无需延迟提交隔离（Quarantine）与事务恢复？”*
我们要通过实测证明：**紧耦合 LIVO 在跨模态污染传导下反而存在独特的脆弱性（Shared-Map & Shared-State Cross-Contamination）**，而接入我们的事务恢复框架后能实现显著救回：
- **脆弱性机理 A（近场遮挡污染共享体素深度图，`MEAS_CONTAM`）**：在 `FAST-LIVO2` 中，视觉子系统（Sparse Direct Photometric Alignment）依赖 `VoxelMap` 中的激光平面提供像素深度先验。当 88% 塑料袋近场遮挡或局部点云畸变发生时，若无前端隔离，错误的近场平面直接写入 `VoxelMap`，导致视觉跟踪投射到错误深度上，视觉不仅无法拯救激光，反而被污染的 `VoxelMap` 一起带崩！
- **脆弱性机理 B（剧烈暗光/频闪或时间偏移污染共享 ESIKF 状态，`AUX_DEGEN` / `SYNC_DRIFT`）**：当进入 `room_dark_01`（自然暗光/剧烈明暗切换）或发生传感器时钟失步时，未隔离的异常视觉光度梯度或去畸变残差通过紧耦合卡尔曼增益直接污染共享的 IMU 零偏 $(b_a, b_g)$ 与速度状态。

#### 2. 具体实验要求（落入代码、Manifest 与论文表 II / 表 III / 图 4）
1. **评测序列与工况（至少覆盖以下 2～3 个代表性工况）**：
   - **工况 1**：`hall_01` $[120, 140]\,\mathrm{s}$ 88% 塑料袋近场遮挡（`MEAS_CONTAM`）—— 对比 `Native FAST-LIVO2 (B0)` vs. `FAST-LIVO2 + Ours Quarantine & Mixture Strip / VIO Bridge (B6)`；
   - **工况 2**：`room_dark_01`（真实自然暗光 + 遮挡，`AUX_DEGEN + MEAS_CONTAM`）或 `hall_01` 走廊退化（`GEO_DEGEN`）—— 对比 `Native FAST-LIVO2 (B0)` vs. `FAST-LIVO2 + Ours (B6)`；
   - **工况 3（可选加分）**：留出测试集 `hall_02` $[45, 65]\,\mathrm{s}$ 上的零微调盲测。
2. **指标与产物要求**：
   - 记录 `Clean ATE`、`Degraded B0 ATE`、`Window RMSE`、`Ours B6 Repaired ATE`、同宿主恢复比例 `Same-Host G`、旋转误差 $\mathrm{ATE}_{\mathrm{rot}}$ (deg) 以及明确的 `Provenance Tag`（`REAL_HOST` / `INJECTION` / `OFFLINE_CONSTRUCT`）；
   - 生成独立可验证的 JSON Manifest（如 `slam_recovery/experiments/manifests/p11_fastlivo2_fifth_host_benchmark.json`）及评测脚本；
   - 将 **FAST-LIVO2** 正式作为第 5 个宿主写入论文 **Abstract、Introduction 贡献点、Section IV-C、Table II（Main Results）与 Fig. 4**，形成 **FAST-LIO2（滤波 LIO）+ LIO-SAM（因子图 LIO）+ MM-LINS（多地图 LIO）+ ORB-SLAM3（多地图 VSLAM）+ FAST-LIVO2（紧耦合 LIVO）** 的五宿主大满贯矩阵！

---

### 8.2 任务二：整理并新增 **内部细粒度组件消融实验（Component-Level Ablation Study）**

目前我们已经有了事务生命周期级的 **B0–B6 宏消融（Macro-Ablation，图 3）**。为进一步证明检测器、因果网络特征工程与四模式门控 $\mathcal{D}(t)$ 内部每个子设计的必要性，请新增一个专门的细粒度组件消融脚本与汇总表（保存至 `slam_recovery/experiments/manifests/p12_component_level_ablation.json`，并在论文 Section V-C 或新增小节中报告）：

#### 1. 子表 A：检测与诊断层特征/模块消融（Detector & Causal Network Component Ablation）
在开发集 `hall_01` 与留出集 `hall_02`、`room_02`、`room_dark_01` 上定量对比以下 5 个递进变体：
1. **`w/o Physical-Unit & Causal Past-Median Normalization`**（直接输入原始未归一化特征）：验证跨场景泛化诊断准确率从 `1.000` 跌至 `0.400`；
2. **`w/o 48-Cell Spherical Azimuth-Elevation Encoder`**（仅用全局 12D 标量统计，去掉 32D 球面空间池化特征 $s_t$）：定量展示在局部扇区遮挡（`MEAS_CONTAM`）与走廊退化（`GEO_DEGEN`）早期区分度及起点回溯 MAE 上的退化；
3. **`w/o Factorized Onset-Age Head (`ConditionalRecoveryHead`)`**（退化为固定 $\Delta t_{\mathrm{margin}}=2.0\,\mathrm{s}$ 回滚）：验证 $4.0\,\mathrm{s}$ 慢斜坡退化下起点 MAE 从 `0.18–0.27 s` 恶化至 `0.80 s`，可信地图泄漏污染帧从 `0.00` 升至 `2.00` 帧；
4. **`w/o NIS / LOSO Innovation Consistency Gate`**（退化为纯几何 RANSAC 近场过滤）：验证在 `room_02` / `hall_02` 正常近墙通行（Hard-Negative）上产生 `76.3%`（58/76 帧）真实墙面误剥离，而加上 NIS/LOSO 门控后误剥离率为 `0.00%`；
5. **`Full Physics-Guided Causal Network + Signature Floor (Ours-Full)`**：全指标最优。

#### 2. 子表 B：四模式验证门 $\mathcal{D}(t)$ 内部三判据消融（Mode 2 Verification Gate Criterion Ablation）
在候选修复分支集合（包含 `R4` 无证据分支、`LIO-SAM B5` 窄扇区发散分支、`ORB-SLAM3 B5` 开环跳变分支、`R5` 闭环重访分支及各宿主 `B6` 正确修复分支）上，定量对比去掉 $\mathcal{D}(t)$ 中任一子判据时的 **错误提交率（False Commit Rate）** 与 **最终轨迹 ATE 恶化量**：
1. **`Gate w/o Weak-Direction FIM Gain ($\Delta J_v \ge \tau_{\mathrm{info}}$ removed)`**：仅查残差不查信息增益，导致走廊/盲区欠约束分支被误提交；
2. **`Gate w/o Cross-Scan Disjoint Holdout NIS ($D_{\mathrm{holdout}} \le \tau_{\mathrm{val}}$ removed, using in-sample training residual only)`**：导致过拟合局部单墙面的跑偏分支（如 LIO-SAM B5 / R4）混过门控；
3. **`Gate w/o Coverage Lock (`inlier_coverage >= 0.70` removed)`**：验证 R5 反例（75% 留出点漂移 $>2.0\,\mathrm{m}$ 被截断隐藏）导致的漏网风险；
4. **`Gate w/o Paired Wilson Lower Bound & Re-entry Continuity Gate`**：验证“均值改善但尾部重入位置跳变 $>0.5\,\mathrm{m}$”的候选（如 ORB-SLAM3 B5 开环拼接，ATE $6.56\,\mathrm{m}$）混入可信图；
5. **`Full Unified Gate $\mathcal{D}(t)$ (All 4 Criteria Enforced)`**：错误提交率 `0.0%`，100% 精准放行真实修复分支并拦截所有退化/伪修复分支。


---

## 第九部分：2026-11-06 技术讨论汇总与技术债台账

> **⚠️ 阅读要求（Codex / 开发侧）**
>
> 本部分**不是验收结论**，而是一份**待回答的技术质询 + 技术债台账**。
> 请逐条阅读，并在下一次提交的 commit message 或新建的 `docs/review_*` 目录中，**逐条回答 §9.11 的 12 个问题**；不要只回复"已阅"。
> 每个条目都给出了**证据位置**（文件:行号）与**可验证的验收标准**。凡本轮无法复现的结论，请直接写明"无法复现"及原因，不要默认接受。

### 9.1 代码验收状态（截至 `09f9960`）

**已确认为真修（非翻默认值）：**

| 缺陷 | 修法 | 核验依据 |
|---|---|---|
| 缺测即通过 | 三字段改 `Optional[None]`；新增 `evidence_status ∈ {PASSED, MISSING, FAILED, NOT_APPLICABLE}`，仅 PASSED 进 Mode 2 | `core.py`；在线节点 `_measure_paired_evidence()` 真的逐帧算 NIS |
| 撤销最后一帧仍读旧点 | 去掉 `if self._kf_map_points:` 守卫，空集也写回 | 有断言覆盖 |
| 旋转归因错位 | 改名 `Aux_FASTLIO2_LidarInertial_Orientation`；新增 `Ours_B6_Orientation = UNAVAILABLE` | 承认 B6 只发平移 |
| 回滚日志 O(N²) | `prev_factor_len` + 截断，每帧 O(1) | 因子表只追加，截断即精确 before-image |
| G 除零哨兵 | 返回 `None`；`E_clean > E_degraded` 时同样返回 `None` | 六个调用点已迁移，manifest 落 `null` |
| None 格式化崩溃 | `_fmt_g()`（两处） | 全库扫描已无残留 `:+.4f` |
| 重入门限双值 | `wilson_validator.py:57` 统一到 0.50 | 全量 manifest 扫描：18 条 reentry 记录中仅 street_08 的 0.4042 落在 `(0.35, 0.50]`，无判决翻转 |
| 样本量过薄 | ≥8 关键帧要求 n≥8 | Wilson 手算：n=3→0.5258，n=4→0.5965，**n=8→0.7472** |
| B0 硬编码 `G: 0.0` | 改名 `recovery_ratio_G_by_definition` | 无代码消费旧键 |

**测试 22/22 PASS**（`python -B -m unittest discover -s slam_recovery/tests`）。

### 9.2 技术债台账（Technical Debt Ledger）

| ID | 级别 | 问题 | 证据位置 | 验收标准 |
|---|---|---|---|---|
| TD-01 | ~~**P1**~~ **CLOSED** | 论文称 street_08 候选"三项同时被拒"，但第三项 `0.4042 ≤ 0.50` 是**通过** | `paper_submission_package/paper_main.tex:393` | 已由 `c1163c8` 改为 "passes the boundary-jump criterion ... both fail"，三份 tex 均已同步（PDF 正文未独立核验，见 `docs/review_20261109_6a5d842/`） |
| TD-02 | P2 | 同一研究文档自相矛盾：540 行写自适应样本量，1857 行仍写 `min_paired_observations=4` | `SLAM_RECOVERY_RESEARCH.md` 及 `paper_submission_package/` 镜像 | 两处表述一致 |
| TD-03 | P2 | 两项行为变更**零测试**：0.85/0.04 在 0.35 与 0.50 下行为相同；无 ≥8 关键帧用例 | `slam_recovery/tests/test_atomic_commit.py` | 新增 0.40 m 重入用例 + 8 关键帧自适应用例 |
| TD-04 | P2 | `required_paired` 直接取值而非 `max(...)`：`min_paired_observations=10` 时大候选反而只需 8 | `transaction_manager_node.py:266-270` | 改为 `max()`，或证明非默认基线的使用场景不存在 |
| TD-05 | P3 | `last_paired_evidence` 失败分支用 `min_paired_observations`、成功分支用 `required_paired_frames` | 同上 `:275` / `:307` | 统一键名 |
| TD-06 | P3 | B5/hall_01 行写 `0.92 m` / Wilson `0.0`，manifest 实为 **4.519 m** / **0.8061** | `SLAM_RECOVERY_RESEARCH.md:1636` vs `e3_orbslam3_second_host_benchmark.json` | 按 manifest 校正或标注历史版本来源 |
| TD-07 | P3 | S1/S2 manifest 重跑后必多 `required_paired_frames` / `candidate_keyframes`，不再 byte-identical | `sim_s1_s2_counterfactual_and_3d_voxel_benchmark.json` | 重跑并更新，或注明字段扩展 |
| TD-08 | P2 | 论文表述为 3 项混合模型，实现为确定性 RANSAC，未拟合分布 | `repair/point_mixture_repairer.py:14` | 论文措辞与实现对齐，或真做 EM |
| TD-09 | P2 | `intensity` 已计算但**从未使用**；注入袋点强度为 200 | 同上 `:42`；`injection/injectors.py:111` | 纳入判别，或说明弃用理由 |
| TD-10 | P2 | 判别器**无时间维度**：真墙与袋子在单帧几何上不可分 | 同上（逐帧独立处理） | 引入跨帧一致性判据 |
| TD-11 | P2 | 污染占比 < 30% 全保留，形成盲区 | 同上 `:90` | 改为逐点后验权重（软权重） |
| TD-12 | P2 | **无隔离退出判据、无迟滞**：无法判断"污染减弱到可以恢复" | `quarantine/manager.py`（无相关逻辑） | 不对称迟滞 + 尾段滑动验证 |
| TD-13 | P2 | `confirmation_margin` 固定 2.0 s，慢于 2 s 的爬升会漏 | `quarantine/manager.py:32,144` | 用 `ramp_slope` 自适应 |
| TD-14 | P2 | 只有 `trusted_map_pollution_ratio`，**无地图覆盖率指标** | `run_e2_ablation_matrix.py:213` 等 | 新增修复段体素覆盖率 |
| TD-15 | P2 | **无真实实时闭环证据**，真实宿主多为 `OFFLINE_CONSTRUCT` | manifests | 端到端 P50/P99 延迟 + ≥10 min 连续运行 |
| TD-16 | P2 | 门控判决质量仅 n=1（street_08 一次拒绝） | — | 混淆矩阵：真阳性/假阳性/假阴性/真阴性 |

> **2026-11-09 状态更新（`6a5d842` → `5262f86` → `9bfa153`）**
>
> **已关闭**：TD-02（1857 行改写为"4 只是下限"）、TD-03（新增 2 条测试，**25/25 PASS**）、TD-04（`:268` 改为 `max(...)`，两分支均写 `required_paired_frames`）、TD-05（键名统一）、TD-06（改为 manifest 的 4.519 / 0.8061 / `reentry_position_discontinuity_exceeded`）、TD-07（S1/S2 已重跑，仅 4 个字段变化）。
>
> **已实测确认、仍开放**：TD-08（论文称 mixture、实现为 RANSAC）、TD-09（仅改强度输出不变）、TD-10（无时间维度）、TD-11（200 点估 20.2% 全留，400 点估 40.5% 全删并误删 5 个真实点）、TD-12（确无在线退出判据）、TD-13（固定 2 s 余量）、TD-15、TD-16。
>
> **新增 P1-A｜配对收益参考集含候选自身扫描**：`transaction_manager_node.py:340-346` 把候选非留出扫描拼进参考集，`:378` 传入，`:264` 对全部可配对帧打分 → 4/5 的样本自证。详见 `docs/review_20261109_6a5d842/README.md` §三。**本轮两笔未触及。**
>
> **新增 P1-B｜仿真与真实注入的遮挡模型不同**：仿真为"移除扇区"（无假点），真实注入为"替换成近场薄板"（88% 假点）。节点重建地图用的是原始 `scan_buffer_body`（`:99`），且从不调用滤波器，因此在替换模型下"提交修复后的原始扫描"会把假墙写进地图。**B4 = B6 = 0% 只在移除模型下成立**，不能外推到真实塑料袋。详见 `docs/review_20261109_9bfa153/README.md` §三。
>
> **新增事实**：真实注入的 12 帧全部 `geometrically_repairable = False`（`min_bg_eigenvalue` 0.90–7.99 < 15），点级剥离只是预处理，恢复实际来自双端锚定桥接；近墙误剥离 58/76 = 76.3%（旧 6.58%），已在论文中如实写入。

### 9.3 指标与证据体系

- `G = (E_deg − E_rep)/(E_deg − E_clean)`；**G ≈ +1 是"回到 clean 水平"，是天花板，不是 SOTA 超越**。
- 负 G 有两类：真实失败（`room_dark_02` 三条臂，受 Prop 1 限制）与算错（分母为负/为零，已修）。
- **最强证据不是性能，是拒绝**：`street_08` LIO-SAM 退化 333.29 m → 候选 337.06 m（比不修还差），门控以 Wilson 0.4626 拒绝，落入 Mode 3，可信地图未污染。（注：早期此处把 NIS 4.4145 也列为拒绝依据；§13.18 的 σ 标定表明该 NIS 项在未标定尺度下不可解释，干净数据本身即 2.85–3.53 > 2.5，判决由尺度无关的 Wilson 承担。）
- 但该证据 **n=1**，缺**判决质量混淆矩阵**、**假阳性率**与**保守代价**。

### 9.4 架构叙事：项目漂移与主线回归

原始目标是**即插即用的鲁棒性模块**；多轮审稿驱动的 P1/P2 修复后，主线滑向"四模式门控决策表"。局部每步都正确，合起来丢了主线。

**门控不是偏题，而是"即插即用"的准入条件：**

```
即插即用 = 接口统一（能插进去）
         + 准入契约（插进去不会更差）   ← 门控
         + 修复能力（插进去确实更好）
```

**建议主线（一句话）：**

> 一个宿主无关的地图鲁棒性层：模块重建退化区段的轨迹与测量，并只在独立证据证明该重建优于不修时提交；当修复无法被验证时，按代价递增降级（等待 → 隔离 → 请求重观测）。

**代价递增的动作阶梯：**

| 级 | 动作 | 改变什么 |
|---|---|---|
| 1 | 在线重加权 | 不改地图 |
| 2 | 验证后原子提交 | 改地图（可回滚） |
| 3 | 软桥接等待 | 买时间 |
| 4 | 硬休眠 / 分图 | 隔离地图 |
| 5 | **请求重观测** | **改变机器人行为** |

第 5 级是 Prop 1 的建设性对偶：**回滚无法创造可观测量，但运动可以。**

**行为层的两条硬约束：**（a）模块**不命令**机器人，只发布重观测请求，否则破坏插拔性；（b）bag 无法验证（轨迹固定），必须仿真或真机——这与"仿真非必需"的旧判断相反，因为动作空间变了。行为层属于 active SLAM / informative planning 社区，**应作为第二篇论文**。

### 9.5 污染点判别：当前实现与四个弱点

| 判据 | 参数 | 位置 |
|---|---|---|
| 近场 | ≤ 25 m 进候选 | `point_mixture_repairer.py:45` |
| 共面 | 80 次确定性 RANSAC，厚度 0.05 m | `:59` |
| 过原点 | 平面到原点 ≤ 5 m | `:70` |
| 整扇区剥离 | `expected_sheet_r = ortho_d/|cos|`，容差 20 cm | `:82` |
| 比例门槛 | 污染 < 30% 全保留 | `:90` |
| 可观测性 | 剩余点 FIM 最弱特征值 ≥ 15 | `:100` |

**四个已确认弱点：**
1. **完全没有时间维度** —— 真墙与袋子在单帧几何上不可分。
2. **`intensity` 算了但从未使用** —— 注入袋点强度 200，是现成的强信号。
3. **论文叫"混合模型"，实现是 RANSAC** —— 未拟合分布，表述比实现更"统计"。
4. **30% 以下是盲区** —— 小幅度污染不删，只靠门控兜底。

**安全逻辑（必须写进论文）：**

```
点级识别（启发式，必然出错）→ 候选修复 → 独立验证（负责抓错）→ 提交 / 拒绝
```

**识别器提出假设，门控负责证伪。** 误删真墙 → 剩余点约束不住 → NIS 崩 → 拒绝；漏删假墙 → 假点参与重建 → NIS 超限 → 拒绝。错误的后果被下一级接住，这才是判据可以粗糙的原因。

### 9.6 视觉路径：问题性质与 LiDAR 相反

| | LiDAR 污染 | 视觉低光 |
|---|---|---|
| 失效形态 | 有信息，但**是假的** | **没有信息** |
| 识别粒度 | 点级 | **区间级** |
| 修复动作 | 剥离假点 + 重建位姿 | **整段换数据源** |
| 实现 | `point_mixture_repairer.py` | `repair_keyframe_bridge_with_lidar_aux` |

- 视觉自己救不了自己，借健康的 LiDAR-惯性相对运动，两点边界锚定到 ORB 世界系。
- **B6 视觉分支只发布平移，无逐帧四元数**（已标 `UNAVAILABLE`）。
- 全部标 `OFFLINE_CONSTRUCT`，本质是跨模态替换，不是视觉内部清理。

### 9.7 双模态全失效与 IMU

**能救多少是算出来的，不是猜的。** `QuarantineSegment.propagated_cov_norm` → 门控 `sigma_bridge = 4.00`（`core.py:218`）：

| 条件 | 判决 |
|---|---|
| 时长短 且 ‖P_prop‖ < 1.0 | Mode 1 在线重加权 |
| ‖P_prop‖ < 4.00 | Mode 3 软桥接等待 |
| ‖P_prop‖ ≥ 4.00 | **Mode 4 硬休眠 / 分图** |

IMU 提供相对运动 Δ，不提供绝对位置；误差随间隔二次增长。**过阈值自动降级，不硬撑。**

**与 SuperOdometry（Zhao et al., IROS 2021, CMU）的区别：**

| | SuperOdometry | 本项目 |
|---|---|---|
| 角色 | 估计器（信任隐含在协方差里） | 准入层（候选仍须验证） |
| 是否拒绝自己的输出 | 不会 | **会** |
| 适用范围 | 一个系统 | 任意宿主 + 任意模态组合 |

一句话：**SuperOdom 让 IMU 说了算；我们让 IMU 说话，但不许它一个人说了算。**

### 9.8 污染的时间尺度：慢增强与慢减弱

**缓慢增强 —— 已有数据（E1 slow-ramp，16 窗口 ≈ 3.2 s）：**

| 方法 | onset MAE | 泄漏帧 |
|---|---|---|
| MM-LINS 协方差判据 | 3.767 s | 22.83 |
| NIS 固定阈值 | 3.007 s | 16.03 |
| Ours 规则 | 2.02 s | 0.43 |
| **Ours 因果 Transformer** | **0.615 s** | **0.17** |

机制不是预测，是**回溯撤销**：`t_q_start = onset − 2 s`，反向弹出 `promoted_history` 并用 before-image 逐位恢复（`manager.py:144-163`）。

**限制**：2 s 是固定预算；坡比 2 s 慢得多时，更早的污染帧已提交且不在撤销范围内。**建议**用已在计算的 `ramp_slope`（`causal_transformer.py:188`）自适应设置 margin。

**缓慢减弱 —— 目前完全没有。** 全代码库无隔离退出判据、无迟滞。不能用健康检测器判（它刚被骗过）。正确做法：**不对称迟滞**（进入快/敏感，退出慢/特异）+ **尾段滑动验证**（取最后 K 帧修复，算对 onset 前地图的留出 NIS，连续 N 帧通过才关闭）。附带收益：隔离区间自动缩短，修复负担下降。

### 9.9 地图层面的三个问题

**三段式：** 之前冻结在 checkpoint（不改）→ 中间轨迹重建 + 污染剥离（改）→ 之后与锚点连续（衔接）。**这是"提交前修复"，不是"事后清理"** —— 污染从未进入可信地图，因此不需要猜哪些点是坏的。

**被扔掉的点，三类三种命运：**

| 点 | 能救吗 | 办法 |
|---|---|---|
| 袋面点（世界系静止） | 可作**短时约束**，过期后丢弃 | 时间一致性判别 + 窗口 |
| 袋面点（体坐标系静止） | 零信息，无可救 | 整体剔除 |
| 被挡住的背景 | 单帧救不回，**跨帧能补** | 修好轨迹后重投影前后健康帧 |
| **扇区误删的真实点** | **能救、该救** | 软权重替代 20 cm 粗带剥离 |

**关键洞察**：遮挡阴影随运动扫过，最终缺的只是"任何视角都没看到的部分"。**修复不只是把坏帧变好，它让前后健康帧重新变得可用。**

⚠️ 现有注入是**体坐标系固定**的（`injectors.py:95-111`），因此"短时约束"这条路在当前数据上**无法验证**，需新建世界系固定的遮挡注入模型。

**两条红线：**
1. **禁止生成模型补图**：幻觉几何比空洞危险得多（空洞 → 保守绕行；假墙 → 诱导碰撞）。
2. **补 coverage 指标**：现在只有 `pollution_ratio`（假的进了多少），没有体素覆盖率（真的留下多少）。审稿人必问"这么保守是不是把地图搞空了"。用现有体素账本即可计算，不需重跑。

### 9.10 论文与发表定位

| 叙事 | 落点 |
|---|---|
| "学习式修复框架，ATE 降低 X%" | **被拒 / 弱接收**（G 接近 1，是天花板不是超越） |
| "SLAM 地图状态的事务语义" | ICRA/IROS 稳，RA-L 可冲 |
| 上者 + 实时闭环 + 判决质量表 | RA-L 稳，T-IV/T-IE 可投 |

**审稿人四问：**（a）与鲁棒后端的区别——必须主动划界（区间级准入 vs 单次优化内压异常值）；（b）**在线吗？延迟多少？**（最致命）；（c）**只拒绝了一次，凭什么可信？**（第二致命）；（d）学习模块消融——建议把 Transformer 写成可替换实现。

**"实时"的及格线：** 单机端到端闭环 · 每段 P50/P99（不是均值）· 连续 ≥10 min 且含真实退化事件 · 1.0× 回放或真传感器 · Mode 3 最坏等待上界。最小代价路径：ROS relay 节点（订阅点云 + 宿主里程计，滚动缓冲），不改宿主 C++ 即可拿到真实闭环数据。

**实时带来的新贡献：** 在证据尚未充分、但决策不能无限等待的约束下，"不提交"是唯一安全的选择。可画一张别人没有的图：**允许等待时间 vs 错误提交概率 / 地图连续性**。

### 9.11 需要开发侧逐条回答的 12 个问题（Answer Required）

**Codex 验收答复（2026-11-06，审阅版本 `5e2cf69`）**：[12 个问题的逐题答复与依据](docs/review_20261106_5e2cf69/README.md) · [验证脚本](docs/review_20261106_5e2cf69/probe.py) · [实测结果](docs/review_20261106_5e2cf69/probe_results.json)。

1. `paper_main.tex:393` 的 "refused on all three measured criteria at once" 是否会在下一次提交中改为 "two of three"？若不改，请说明该句在 `0.4042 ≤ 0.50` 的前提下如何成立。
2. `SLAM_RECOVERY_RESEARCH.md` 的 1857 行与 540 行矛盾，以哪一版为准？镜像文件是否同步？
3. TD-03 的两条测试（0.40 m 重入、≥8 关键帧）何时补、补在哪个文件？
4. `required_paired` 是否改为 `max(...)`？若保持现状，请给出 `min_paired_observations > 8` 的合法使用场景。
5. `last_paired_evidence` 的键名是否统一为 `required_paired_frames`？
6. `:1636` 的 `0.92 m` / Wilson `0.0` 来源是哪份 manifest？若为历史版本，请明确标注版本与日期。
7. MEAS_CONTAM 判别是否会引入**时间一致性**（世界系静止 vs 体坐标系静止）？是否需要新建世界系固定的注入模型来验证？
8. `intensity` 是否会参与判别？若弃用，请给出理由。
9. 30% 以下的小幅度污染如何处理？是否改为逐点后验权重？
10. 隔离的**退出判据**是否存在？若不存在，是否采用"不对称迟滞 + 尾段滑动验证"？
11. 2.0 s 的 `confirmation_margin` 是否会随 `ramp_slope` 自适应？若不是，请说明慢于 2 s 的爬升如何保证不漏。
12. 能否提供（a）修复段**体素覆盖率**、（b）真实宿主**端到端延迟 P50/P99** 与（c）门控判决的**混淆矩阵**？

---

## 第十部分：固定条件下的测量修复 → 状态重估 → 地图重建（当前开发交接）

**日期**：2026-11-09。**分工已由用户明确**：远端开发侧实现、运行真实宿主；本机会话提交任务、审阅源码与回传证据。此任务不是要求本机代跑 ROS，也不是宣布已有恢复闭环。

> **Codex need to read and answer in detail.** 请先答复 M0 的具体宿主、输入、协议和阻塞条件，再按里程碑实现并提交代码/实验。不要只改措辞，不要以单测总数、单个低 NIS 或提交信息替代真实运行证据。若缺输入、标定、独立参考或宿主接口，直接报告 BLOCKED/UNAVAILABLE。

### 10.1 主线与停止条件

目标是**真正修复退化区段**：清理不可信测量、用可用证据重新估计状态、撤销错误贡献并重建地图。隔离/验证是支持修复的机制，不是任务最终产出。

当前隔离结果有价值，但 A3 与只隔离 A1 相同、没有修复准入，不能证明修复新增收益。单个 NIS 反复解释不能替代这条链。旧表述“插入任意宿主绝不变差”“会议稳”“ROS relay 即等同原生地图回滚”均不作为当前承诺；验证只能降低错误准入风险，兼容范围按实际适配接口声明。

**阶段完成定义**：至少一个固定宿主/序列上，存在可追溯的 **原始消息 → 实际过滤消息 → 宿主重新估计 → 地图贡献** 运行链，并独立评估它相对原生和只隔离的准确度/完整度变化。结果可以失败，但必须真实、可解释；失败不算恢复成功，链未执行不算实现闭环。

### 10.2 第一实验：复用已有运行链，不再扩矩阵

优先复用远端已运行的 **FAST-LIVO2 + hall_01 固定窗口**，相机、IMU、宿主配置与初始化保持一致。仅研究测量修复对状态和地图的作用，不推断视觉贡献。若远端确认 FAST-LIO2 更易建立可复現输入链，可在 M0 说明替代；同一比较中不能换宿主或配置。

- 冻结绝对注入窗，保留已发现的实际窗与名义窗区别；统一 header 时间、传感器外参与完整 SE(3)。
- 从相同健康前缀启动各次原生运行。首版可全 bag 离线重跑，明确标 **offline measurement-filtered native rerun**；这不是 native checkpoint/在线局部回滚。
- 不只记录文件名：记录原始/转换/过滤输入 hash、host 实际消费的 input hash、配置文件 hash、host revision、运行命令、结果 bag hash。
- 固定 scan ID/原点 index 或 ray ID、预热/退化/恢复尾段、评价区域、公共时间支持。缺输出单列，不按各臂结果重新挑容易帧。
- 评分参考不进入实际过滤/状态估计。hall_01 的位置 GT 不等于姿态 GT；参考 clean-run 姿态须叫 proxy/oracle estimate，不能称完整真值。

### 10.3 C0–C3：先拆解恢复能力，不与准入四臂混淆

| 控制 | 构图测量 | 位姿/状态来源 | 要回答的问题 |
|---|---|---|---|
| C0 原始损害 | 固定污染扫描 | 对该输入实际运行的原生宿主 | 损害基线 |
| C1 位姿控制 | 同一污染扫描 | 明确标注的高质量参考 SE(3) | 仅修位姿是否仍留下假几何 |
| C2 信息上限 | 污染扫描按 exact injection mask 去除假点 | 同一参考 SE(3) | 已测到的剩余信息最多能恢复什么 |
| C3 实际恢复 | 无 oracle/GT 的实际算法过滤/降权 | **实际宿主原生重新运行并更新状态** | 我们的方法实际修回多少 |

C1/C2 是离线 oracle 诊断，不计为部署修复；C2 **只删除被替换的回波，不用干净背景点填洞**。无测量的背景无法由过滤生成；回访/新增视角另列实验。

C3 不允许直接沿用 C0 轨迹、拼接 clean/GT 轨迹或线性混合轨迹。需重新 deskew、滤波/优化，产生真实宿主状态输出；若速度/偏置不可导出，明确能力边界。

保留完整 PointCloud2 记录：按 keep mask 选择 x/y/z/intensity/**ring/time**，维护 header/point_step/row_step，不把 XYZ-only 云冒充原生重处理输入。IMU与图像保持逐消息一致，除非另行预注册传感器故障实验。

### 10.4 里程碑与交付

| 里程碑 | 远端交付 | 本机验收重点 |
|---|---|---|
| **M0 协议冻结** | 新实验 manifest schema、宿主/窗口/输入hash链、运行脚本/配置、指标与支持规则；未运行记 PENDING | 输入和参考身份、oracle边界、共同条件；不要看完结果再改协议 |
| **M1 上限诊断** | C0/C1/C2，原点身份与oracle mask，地图准确度/覆盖及缺测 | 判断观测缺失、测量污染、状态误差的作用；参考不是完整GT时保留限定 |
| **M2 实际修复链** | C3 filtered bag → native host rerun → full SE(3) → rebuilt map；每步来源、过滤计数与实际配置 | 测量确实进入宿主，宿主确实重估，构图使用相应修复测量而非原始污染buffer |
| **M3 修复净收益** | 同输入原生/只隔离/无条件修复准入/验证修复准入四策略，固定区域同时测准确度与完整度 | 验证准入比只隔离净恢复多少正确几何；A3=A1只能证明未恢复，不包装增量 |
| **M4 后续扩展** | native局部checkpoint/replay、实时链、合法/错误回环及其他宿主 | 只有第一条链被证明后才扩矩阵；慢速回放不称实时 |

**先冻结 M0 再运行**。不预写成功数字。C0–C3 是修复构成诊断，M3 四策略才是准入消融，两类表不能互相替代。

### 10.5 复用实现与已知防错点

- `prepare_m2dgr_for_fastlivo.py::convert_cloud`：复用原生记录布局、IMU/图像透传和 sidecar；新增过滤应保持整条点记录。
- `injection/injectors.py::inject_plastic_bag_near_field_occlusion`：保存其 exact mask 与原点 ID，只作 C2 标注/评分；算法 C3 不读注入mask。
- `repair/point_mixture_repairer.py::filter_self_consistent_near_field_contaminants`：首版确定性实际过滤基线。该函数是几何启发式，不是学习概率模型或状态估计器；正常近墙误删需测。
- `run_four_arm_same_input.py`：复用 SE(3)、slerp、消息配对、严格 JSON、hash 和构图工具；**不要复用旧 archived-pose 臂来冒充 native重估**。
- `fastlivo2/mapping_m2dgr.launch`：核对真正加载的 host package 文件及 camera YAML，不仅哈希仓库模板。
- `verify_four_arm_independent.py`：复用字段感知解析、空间近邻与独立统计，保持新 hash 绑定 cache；标注实际点/帧预算。
- 轨迹评价核查 `evaluate_fastlivo_result.py` prefix 对齐后调用 `evaluate_trajectory` 是否又做全程拟合；禁止二次全程对齐却称冻结 prefix。地图和轨迹评价使用预注册健康对齐协议。
- Python `Checkpoint` / `SpatialMutationLog` 可验证表示层事务，但**不等于宿主 C++ filter/tree 全状态回滚**。首版从同一健康prefix原生重跑与未来在线恢复分别验收。

### 10.6 评价协议：不能用准确度换空图，也不能用coverage掩盖假图

1. **测量修复**：污染存活、真实背景误删、正常窗误干预；注入标签仅用于评分。原始/保留/删除数量及ID可追溯。
2. **状态**：共同时间支持的平移ATE/RPE；只有可靠姿态GT时报告旋转误差。输出缺失、关联间隔及外参分别报告，不用更好覆盖的臂占便宜。
3. **地图准确度**：同区域的双向距离/分布/尾部，实际局部空间邻域与质量检查。不能用无支持处的远平面外推评判，也不能让未知几何进入可信地图。
4. **地图完整度**：固定独立可见参考表面、同区域覆盖及相对只隔离的净正确几何。无GT表面则明确 `clean_proxy_agreement`，披露对齐误差和分辨率敏感性；clean pose与同源clean proxy的循环对照不能当独立效果。
5. **安全与事务**：wrong commit/missed recovery及分母、干净数据误干预、pending跨重试、每片段依赖与边界。速度包络仍叫 BOUND_ONLY，不当作独立相对运动证据。
6. **资源**：端到端阶段耗时、队列积压、内存、消息覆盖；0.5×回放只说明离线可运行，不说明实时。统计时间/空间相关性使用块/运行级评估，不能把点数当独立样本数。

没有独立参考或观测不足允许 UNKNOWN/UNAVAILABLE，不能造几何/填数字。首次验收先确认链真实执行，收益结论按数据决定，不规定一定提高多少。

### 10.7 NIS 整改降为支持任务，不再主导项目

- 不再通过放大 sigma、提高门限、看结果重新选 key 来恢复 Mode 2。
- 评分应先解决局部空间参考、邻域半径、平面质量/混合与缺证据；限制查询计算，不把全图只剩600点当通用验证。
- 校准区间/评测区间分离；实际参考/query/key身份、预算和来源版本化。经验RMS归一化不自动构成卡方模型。
- 若保持不同观测总体，只报告敏感性，不硬分解污染份额；保留旧诊断但不无限重跑同一18.07。

### 10.8 可选新模型：只有基线证明缺口后再做

候选方向是**时序测量可靠性 + 可观测子空间的窗口重估**：比较world-fixed与body-attached解释，输出可信/污染/未知；结合IMU、可靠LiDAR与可用视觉在隔离窗重估pose/velocity/bias。短时静止、沿平面运动及错位姿可使两解释不可分，未知不硬删。不得用候选自产地图证明自己。

这只是下一模型假设，不是已有贡献。不立即新增Transformer/GNN；若C2可恢复、C3失败，先从受控对照判断是否过滤或重估瓶颈，再决定模型复杂度。若C2也无足够观测，进入辅助模态/独立重访，不靠生成补图。

### 10.9 开发侧下一次必须回答

1. M0采用哪一宿主、输入和实际绝对时间窗？能否提供实际运行输入→输出hash关联？
2. 原点/ray ID与exact mask如何保存，过滤是否保留ring/time？
3. C1/C2参考pose来源及姿态真值边界是什么？地图参考是否与它同源？
4. C3何处调用原生重估，如何证明输出不是C0/clean轨迹复制？
5. 共同支持、缺输出、准确度、完整度和干净窗误干预如何冻结？
6. 当前BLOCKED条件是什么，下一次提交推进哪个里程碑？

### 10.10 自动审阅的方向与防止循环

每5分钟检查开发增量，优先审 M0–M3 修复链与真实运行证据；跳过本会话 `[Auto-Review]`，无开发增量不提交空报告。不自动修算法、不覆盖未提交代码、不改写历史。

输入真实性、状态/地图错误提交属于阻断；不影响实验的日志/措辞集中清理，不因每次文字变化重跑全实验。每轮报告完成/未完成、实测/归档和审阅范围。**局部bug关闭不等于端到端闭环通过。** 超出本轮scope的既有问题保留，不不断扩写新台账。

周期审阅仅当前会话存活时有效，7天自动过期；远端长期运行由开发侧自动化负责。下一阶段第一优先级是实际修复证据，不是增加提交数、宿主数或归因段落。

### 10.11 每轮交接必须划分主线与旁支（用户要求，2026-11-09）

**此规则适用于今后每次任务交接与审阅意见。** 本机会话负责明确目标、提出分类与验收依据；开发侧必须结合实际代码、实验与资源情况调整分工，不能只逐条消化审阅意见而停止研究主线。

- **主线**：本轮唯一优先里程碑与科学问题，列明要交付的代码/运行证据/结果、完成条件及当前未验证项。任务成果不能用修了几个小bug或测试总数替代。
- **旁支**：来源记录、测试、日志、可复现工具和表述等保障工作，注明其中哪些必须先做、哪些可并行、哪些集中延期；不要把全部旁支都标成主线阻断。
- **允许阻断主线的旁支**：已证实会破坏输入身份/时间/标定一致性、状态或地图安全、评价有效性、合法运行或基础执行能力的缺陷。明确失败场景、受影响实验、最低修复量与解除条件。
- **不默认阻断的旁支**：不改变当前实验输入与判决的日志命名、重复说明、汇总字段、审计覆盖完善和文档措辞。集中处理，优先复用有效输出，不因它们重跑整个宿主。
- **分类不是固定不变**：开发侧可根据新证据把旁支提升为阻断，或把审阅侧误列的阻断降为非阻断；必须给具体依据。改分类/模型/协议需显式说明，不看结果悄悄改变支持集或成功标准。

**开发侧每轮回复模板：**

| 分类 | 工作与交付 | 执行分工/顺序 | 阻塞关系与依据 | 验收与状态 |
|---|---|---|---|---|
| 主线 | 一个明确里程碑及问题 | 负责人或自动化角色、下一步 | 只列真正依赖 | 完成/部分/未完成；实测/归档 |
| 必须先做的旁支 | 最小保障修复 | 谁做、解除后怎样回主线 | 具体失败场景 | 解除条件及测试 |
| 可并行旁支 | 不影响当前主结果的保障项 | 谁做、何时合并 | 不阻断 | 本轮/集中后续 |
| 延后旁支 | 非必要改进 | 推迟原因与返回条件 | 不阻断 | 暂缓，不冒充已完成 |

每次另用两句话说明：**本轮主线推进了什么；是否因旁支偏离主线、下一轮如何调整。** 若只有旁支更新，要直说主线没有推进。没有真实阻断依据时，不要求完成所有旁支才能开始下一阶段；人员/代理数量由开发侧按需要安排，不为模板机械扩充多代理。

**当前任务分工入口**：新提交若包含 M3 结果，主线首先验收固定区域下实际修复相对只隔离的净几何收益/代价，再依结果决定模型路线；旁支集中收口 runner/point-ID 与来源测试。若 M3 尚未可靠执行，主线是跑实该比较。不要继续无限解释单个 NIS 或仅修改审计措辞。这里不是对尚未审阅的最新结果作通过判断。

**每轮主线推进要求（用户追加，2026-11-09）**：每个有开发增量的交接周期必须以一个可验证主线交付为目标，先报告主线证据与未完成项，再将工程问题交给旁支并行或集中解决。仅修日志/审计/字段不能算完成该周期目标；开发侧需说明如何调整分工并回到主线。若存在真实阻断，报告 BLOCKED、失败证据、最小解除工作与返回主线的条件，不为了满足“推进”而虚报结果。无开发增量的轮询不要求制造推进或空提交。

**自动化状态**：用户已明确要求恢复，本机每5分钟审阅任务已重新启动，优先本节主线/旁支协议。任务仅当前会话存活时运行、7天自动过期，可按用户要求随时停止；不授予本机会话修改远端算法的权限。





