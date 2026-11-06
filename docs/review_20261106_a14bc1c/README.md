# slam_recovery 复审 · 2026-11-06

**结论：建议修改后再将当前投稿包作为系统验收证据。** 最新提交让读者能分别追踪 LiDAR 和相机的处理步骤。但图 1 的时间曲线缺实测来源，图 2 混合了可选设计与已执行路径。沿着图中的“验证 → 提交”检查，另有两条可以用几行输入触发的安全缺口。

审阅版本为 [`a14bc1c`](https://github.com/Evenstar-E/slam_recovery/commit/a14bc1c327a037fa607661fbb2cb5015a5be17cf)。其直接改动是架构绘图代码、重新导出的图片及投稿 PDF。另核验了前一笔 [`8a2a541`](https://github.com/Evenstar-E/slam_recovery/commit/8a2a54119a7686cb3455138d9abc404c3ecfafed) 的修复。下文分别注明新改动和继承问题。本轮运行了 Python 测试和受控反例，查看了仓库交付的 PDF。原始 bag、宿主程序和传感器硬件未重跑。

## 本次交付的图

### P1 · 图 1 把生成的时间曲线标成 hall_01 实验轨迹

图上标有 `M2DGR hall_01 [120–140 s]`。正文图注据此描述 NIS 越过门限、回滚时刻和 MM-LINS 零次报警。生成器实际先按时刻划分故障区，再用固定随机种子和两组均值生成 NIS、协方差曲线；140.4 秒的原子提交标记也是直接画在指定位置。本次重新发布了这张图，数据生成逻辑来自较早版本。它能解释检测原理，但读者无法用该图核实这次运行何时报警或提交。建议从同一 run 的时间戳、NIS、协方差、报警与提交日志重画；若保留示意图，应在图内和图注标明“合成示意”，撤去实测事件时刻的归因。[曲线与事件标记](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/slam_recovery/experiments/generate_paper_figures.py#L376-L429) · [论文图注](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/paper_main.tex#L49-L53)

### P2 · 图 2 的对称连线混淆了宿主能力和已验证路径

在投稿 PDF 第 5 页，点面残差和视觉重投影残差都用实线进入同一个更新框。框内虽有 `joint or single-host`，但图头列了五个宿主（含 FAST-LIVO2），图注列出四个，读者无法从箭头判断哪个宿主实际用了哪条路径。蓝色“取局部平面、视觉路标”反馈线只接到视觉残差框；标作 `LiDAR ↔ Vision ↔ IMU` 的虚线接入 LiDAR 和相机，却没有接入 IMU。仓库展示的 ORB 灰盒路径有明确方向，用 LiDAR 里程计相对运动补视觉轨迹。建议保留两条并列泳道，把可选连接单列图例，为已执行的桥接标方向和宿主，把地图反馈分别接回对应残差。这样既能解释对称设计，也能指出哪些箭头已经跑通。[绘图连线](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/slam_recovery/experiments/generate_paper_figures.py#L254-L321) · [实际桥接入口](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/slam_recovery/experiments/e3_orbslam3/evaluate_e3_orbslam3.py#L190-L205) · [论文图注](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/paper_main.tex#L172-L175)

## 随当前版本交付的执行与评测问题

| 优先级 | 发现、触发条件及影响 | 修改后的验收条件 |
|---|---|---|
| P1 | **缺少安全证据的候选可以提交。** 同一候选在几何量合格时，显式传入 Wilson 下界 0、重入位置差 99 m 会被拒绝；省略这些字段则提交，关键帧 42 进入可信状态。构造器把配对收益、Wilson 下界、位置跳变默认设为 `True / 1.0 / 0.0`，在线节点构造候选时省略了三项。前一笔修复已能识别显式坏值，仍未区分缺测和通过。[默认值](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/slam_recovery/core.py#L171-L185) · [在线调用](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/slam_recovery/sim/transaction_manager_node.py#L247-L258) | 由调用者传入有来源的配对结果和交界测量。缺失、明确失败、真实有效三种输入分别验证，只有第三种能在其余门通过时改变可信状态。 |
| P1 | **最后一帧撤销后，验证仍能读到旧点。** 只保留一个可信关键帧，再触发覆盖它的回滚，实测可信位姿数为 0、体素数为 0，而验证参考仍返回 `[[10, 0, 0]]`。原因是关键帧点集映射非空时才刷新公开给验证器的列表；下次评估会把旧点并入参考。前一版“尚有幸存帧”的回归已通过。[刷新逻辑](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/slam_recovery/sim/transaction_manager_node.py#L119-L131) · [下游读取](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/slam_recovery/sim/transaction_manager_node.py#L209-L222) | 每次同步都重建派生列表，空集合也写回。分别测撤销最后一帧、部分撤销，检查下一次验证实际收到的参考点。 |
| P1 | **`room_dark_01` 的 9.478° 使用了辅助里程计的姿态。** 旋转评测直接读取辅助 bag 的 `/Odometry` 四元数，再把结果登记为 `Ours_B6_LiDAR_Anchored_Orientation`。论文据此报告 ORB 从 11.480° 改善到 9.478°。桥接函数产出修复的 XYZ 和坐标对齐参数，评测未消费逐帧 B6 输出姿态。这不能建立论文中 B6 姿态改善的归因。[评测输入](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/slam_recovery/experiments/run_hard_negative_and_rot_ate_benchmark.py#L284-L293) · [指标命名](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/slam_recovery/experiments/run_hard_negative_and_rot_ate_benchmark.py#L344-L348) · [论文表述](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/paper_main.tex#L338) | 单列“辅助 LiDAR 姿态”基线。在共同时间支集上从实际发布的 B6 位姿计算旋转误差；若 B6 只输出平移，旋转结果标为缺测。 |
| P2 | **每次确认健康帧都复制全部历史因子。** 每帧只增加一个因子，250 帧的撤销记录已保留 31,125 个历史因子引用，500 帧为 124,750 个，符合 `n(n−1)/2`。这是前一笔修复新增的撤销开销；此处测的是引用数，未测宿主 RSS 或实机 OOM。[保存历史](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/slam_recovery/quarantine/manager.py#L54-L71) · [撤销使用](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/slam_recovery/quarantine/manager.py#L147-L161) | 对只追加的因子记录旧长度或追加差量。继续保证重复关键帧和偏置精确回滚，并用相同输入长度序列检查撤销记录保持线性增长。 |

## 已复核的改进与复现入口

- 仓库现有 **18/18 项单元测试通过**。上一轮的零报警探针替换推理输出后调用实际统计函数 600 次，三个序列的事件召回均为 0。统计现已响应真实报警输出；该反例检验计数逻辑，未测模型在真实数据上的召回。
- 复核了四类输入：缺失四元数返回 `UNAVAILABLE` 和空指标，NaN 加计偏置与 2×2 位姿均被拒绝，更改分类器输出偏置会改变模型摘要，场地外点到有界几何的距离为正。上一轮的同键位姿存在性、全撤销偏置以及部分撤销体素探针也通过。各结果只覆盖对应输入。
- 在仓库根目录运行 `python -B -m unittest discover -s slam_recovery/tests -v`，再运行 `python -B docs/review_20261106_a14bc1c/probe_boundaries.py`。后者只在内存中构造候选和两帧事务，固定检测决定以隔离地图记账，输出两种提交结果、全撤销参考和撤销记录引用数。[复现脚本](probe_boundaries.py) · [上轮探针](https://github.com/Evenstar-E/slam_recovery/blob/a14bc1c327a037fa607661fbb2cb5015a5be17cf/docs/review_20261105_followup/audit_local.py)

建议先补齐候选提交证据，并修复空地图回滚。两项反例通过后，从同一份宿主执行日志导出检测时序、修复位姿与地图变更，验证论文图表能追溯到同一次执行。
