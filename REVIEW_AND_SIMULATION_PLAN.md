# 最新代码更改审阅报告（Commit `6d1f7e4`）与 Gazebo / Isaac Sim 实时仿真实验方案

> **更新日期**：2026-11-05  
> **审阅仓库**：`git@github.com:Evenstar-E/slam_recovery.git`  
> **审阅版本**：`6d1f7e47fe329d58fd8d82db7c2273209e082b63` (`Address second-round review: remove unsupported P8/blend variants, enforce trajectory-dependent 6D FIM & holdout NIS, unify manifests and LaTeX`)  
> **文档内容**：
> 1. 最新代码更改（`a306f0f -> 6d1f7e4`）逐项核查结果（已解决项 vs. 剩余细节问题）  
> 2. 当前版本对冲击顶会（RSS / IEEE T-RO / ICRA / IROS）的成熟度评估  
> 3. Gazebo / Isaac Sim 实时闭环仿真实验设计方案（补齐真值三维地图污染率、受控相变与 R4/R5 反事实重访闭环）

---

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


