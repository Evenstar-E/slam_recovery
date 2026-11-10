# A7 — 坐标/切空间统一（独立证据准入的前置条件）

日期 2026-11-10。基线 `a01169d`（`exp/trace`）。**没有启动任何宿主运行**；以下全部是离线单元测试与离线反例。

## 1. 问题

`evaluate_four_mode_gate` 在 `slam_recovery/core.py` 计算

```
D = v^T Λ_before v          info_after = v^T Λ_after v
```

`v = segment.weak_direction_6d`、`Λ_before = segment.info_before_6x6`、`Λ_after = candidate.info_after_6x6`
三个量的**参考系与块顺序都没有声明**。这个标量只有在三者同系、同序时才是"沿某个物理方向的information"；
否则它仍是一个漂亮的有理数，且不会产生任何报错。

这不是假设。修复前的 `slam_recovery/sim/transaction_manager_node.py` 里：

* `weak_dir` / `fim_6x6` 来自 `compute_6dof_point_to_plane_fim(scan_body_xyz)` → **本帧 body 系**；
* `info_after` 来自 `pts_w = pts_b @ R_k.T + t_k` → **world 系**；
* 两者在 gate 里直接相乘。

## 2. 改了什么

### 2.1 显式声明（`slam_recovery/core.py`）

```python
TangentFrame(frame="world"|"body", order="rot_trans"|"trans_rot", anchor="world"|"scan:<id>")
```

`anchor` 是必填的：body 系是逐帧的，只写 `"body"` 不能标识一个基。三个字段一起参与相等比较。

* `QuarantineSegment.weak_direction_frame` / `.info_before_frame`：**缺失即抛 `MissingTangentFrame`**，
  在 `__post_init__` 里，因此一个没有声明坐标系的 segment 根本无法存在。
* `CandidateMap.info_after_frame`：缺失时 gate 入口抛 `MissingTangentFrame`。
* `trigger_quarantine(...)` 的两个 frame 是**必填 keyword-only**：所有生产者都必须填。

### 2.2 伴随搬运（`core.py`）

```python
adjoint(T, order)            # Ad_T，T 把点从 A 映射到 B
transport(v, T, order)       # v_B = Ad_T v_A
transport_information(L, T)  # L_B = Ad^-T L_A Ad^-1
```

规定 `v'^T Λ' v' == v^T Λ v`，由 `TestTransportAlgebra.test_the_profiled_scalar_is_invariant`
在 20 组随机 SE(3)/SPD 上以 1e-9 精度固定。

### 2.3 gate 入口的拒绝

* `weak_direction_frame != info_before_frame` → `TangentFrameMismatch`
* `candidate.info_after_frame != weak_direction_frame` → `TangentFrameMismatch`

gate 自己**不选**参考系：它没有对应的 transform，猜一个只会得到一个无法证伪的数。搬运是生产者的责任。

### 2.4 生产者的声明

| 生产者 | 声明 | 依据 |
|---|---|---|
| `sim/transaction_manager_node.py` | segment `body[scan:<kf>]` + `anchor_pose_world`，candidate `world[world]`（info 与 cov 同基） | 见 §6 |
| `run_s1_s2_*`、`run_four_arm_*`、`review_20261109_bbc3dcb/probe.py` 等走 node 的调用 | `world[world]` | 它们经 `evaluate_and_commit_candidate` 构造 world 系候选 |
| `e3_orbslam3/*`（两个脚本） | `body[ref_scan]` | FIM 由 `compute_6dof_point_to_plane_fim(pts_ref)` 直接算出 |
| `run_e1` / `run_e2` / `real_bags` / 各单测 fixture | `body[<tag>]` | 合成矩阵，声明的是**设计参数化**，不是测量 |

node 的改法是**搬运而不是改门限**：在 `trigger_quarantine` 之前用该关键帧的 pose 把
`weak_dir` 与 `fim_6x6` 搬到 world 系一次（`transport` / `transport_information`）。因此

* `weak_dir_info_before` 不变（二次型在伴随搬运下不变，这是恒等式，不是近似）；
* `weak_dir_info_after` **会变**，因为它此前是 body 弱方向 × world information 的混系积，
  现在是同一物理方向上的真实投影。**这是行为变化，需要在下一次宿主运行时重新读取结果**；
  门限 `GateThresholds` 一个都没有动。

残余项（未在本次解决，明确记录）：node 在 world 系 FIM 上叠加的 `aux_or_loop_info_6x6`
自身没有 frame 声明。若它是相对里程计信息（body 系），则仍是混系。这项需要生产者给出依据后才能声明。

## 3. 反例测试（修前 / 修后）

同一物理构型：`v` 沿 trans-x，`Λ_before` 在 x 上 20，`Λ_after` 在 x 上 30、y 上 5；
世界系重表达 `G = Rz(45°) + (3,-2,1.5)`。

**修前**（临时 worktree `/tmp/wt-a7-prefix` @ `a01169d`，脚本 `negctl_a7.py`）：

```
w1: MODE2_ATOMIC_COMMIT accepted=True  info_after=30.0  gain=+10.0
w2: MODE3_SOFT_BRIDGE_WAIT accepted=False info_after=17.5  gain=-2.5
same_decision: false
```

同一个物理配置，仅仅换了一个世界系的写法，决定从"原子提交"翻转成"软桥等待"。

**修后**（同一脚本，同一文件）：

```
mixed_declaration: refused TangentFrameMismatch
    candidate info_after is in world[world]/rot_trans but the weak direction is in
    body[scan:7]/rot_trans: the profiled information would mix two bases.
w1: MODE2_ATOMIC_COMMIT accepted=True info_after=30.0
w2: MODE2_ATOMIC_COMMIT accepted=True info_after=30.0
same_decision: true
```

修前的单测无法被收集（`ImportError: cannot import name 'MissingTangentFrame'`），所以行为证据由
`negctl_a7.py` 在两棵树上各跑一次给出，而不是靠 AttributeError 充数。

`python -m unittest slam_recovery.tests.test_a7_tangent_frames -v` → 11 passed。

## 4. 映射到 A7 验收项

| 验收项 | 状态 | 证据 |
|---|---|---|
| 统一前后 FIM、协方差和弱方向的坐标/切空间 | **完成**（`aux_or_loop_info_6x6` 除外，见 §2.4 残余项） | `TangentFrame` + `transport` / `transport_information`；三个量都必须声明 |
| 全局坐标重表达不改变决定 | **完成** | `TestGlobalReexpression`：mode/accepted/info 逐位相同（1e-9） |
| 修前代码上反例失败 | **完成** | 修前 `same_decision=false`（MODE2→MODE3）；修后 `true` |
| 用独立评价验证有害拒绝和有益接纳 | **仍缺** | 需要离线独立标签（每帧的成功/失败判据来自 GT 或独立参考），不是本次能自证的 |

最后一项不能用本仓库自带的 gate 结果来替代：那正是"用被检验的对象检验自己"。
它需要 `A7` 之外的独立标签集，与 NIS/ATE 的离线评估一起做；在此之前该项记为
`MISSING`，而不是"通过"。

## 5. 复现

```bash
python -m unittest slam_recovery.tests.test_a7_tangent_frames -v
python -I docs/review_20261110_a7/negctl_a7.py .            # 修后：same_decision=true
python -I docs/review_20261110_a7/negctl_a7.py <prefix-tree> # 修前：same_decision=false, exit 1
```


## 6. 第二次修订：gauge 反例（2026-11-10，审阅 `docs/review_20261110_4255cbe/`）

第一次修订的两个缺陷，都是**普通合法平移**就触发：

1. **搬运后重新单位化**。Ad 含平移时不是正交变换，world 里的 `v` 不再单位长；gate 又按
   world 欧氏长度除一次，等于再除 `‖Ad v‖²`。
2. **协方差没有坐标契约**。`cov_after` 由 world FIM 求逆，谱范数不平移不变，却和一个固定
   `sigma_tol` 比较。

改法（只改评价基准，不改任何门限）：

- 评价切空间**冻结在触发帧的 body 基**：segment 保留 `weak_direction_frame=body[scan:<kf>]`
  与 `anchor_pose_world`（T_world_from_anchor）。
- 候选的 **information 与 covariance 一起**搬回该 body 基（`transport_information` /
  `transport_covariance`），再与原 body 单位弱方向、同基谱范数比较。
- 单位化只在 body 基内进行（刚体、正交），不再发生在经过含平移伴随的坐标里。
- 新增 `CandidateMap.cov_after_frame`，与世界系候选必须提供的 `anchor_pose_world`；
  缺一即 `MissingTangentFrame` / `MissingAnchorPose`，不是默认。

### 复现（命令 + 结果）

```bash
# 1) 审阅侧原脚本：在修后代码上停在 MissingAnchorPose（旧契约不再静默出数）
PYTHONPATH=. python -B -W ignore /tmp/a7rev/a7_gauge_probes.py
# 2) 同一 physical fixture、新契约：
python -I docs/review_20261110_a7/a7_gauge_probes_fixed.py
# 3) 负控（两写法 + 无 anchor 拒绝）：
python -I docs/review_20261110_a7/negctl_a7.py .
```

**口径**：下表是**同一个 fixture、同一个现象**，不是同一组数字。绝对值取决于本机的
numpy/BLAS 与随机流，审阅侧与我在同一 commit 上得到过不同的绝对量。可迁移的是**现象与机制**：
2 m 平移使 world 弱向量范数变成 2.01、信息被除约 4 倍、mode 翻转；5 m 平移使 cov 谱范数
0.2 → 0.628、mode 翻转。

| 场景 | 修前（本机） | 修后（本机） |
|---|---|---|
| 真实 producer，world y 平移 0 m | before 20.0239，after 51.2612，cov 0.021666，MODE2 | 同左 |
| 真实 producer，world y 平移 2 m | before **4.9464**，after **12.6627**，cov 0.114340，**MODE3** | before 20.0239，after 51.2612，cov 0.021666，**MODE2** |
| 对角例，world y 平移 0 m | before 20，after 30，cov 0.2，MODE2 | 同左 |
| 对角例，world y 平移 5 m | cov **0.628026**，**MODE3** | cov 0.200000，**MODE2** |
| 真实 producer + 绕 z 转 30° + 平移 (0.5, 2, -1) | — | 与 0 m 例一致（1e-6/1e-9），MODE2 |

审阅侧在 `4255cbe` 上独立跑出的是 before 19.0337 / after 48.7263 / 弱向量
`[0.77557,-0.52541,-0.34990]`；本机同一 commit 是 20.0239 / 51.2612 / `[0.66195,-0.48780,-0.56909]`。
两者**现象一致、绝对值不同**，所以这里只主张现象。

**一条限定**：本脚本的协方差例是**往返**（body→world 用 `transport_covariance`，门再
world→body 搬回来），构造上必然不变，**单靠它抓不到伴随写错**。非往返检查是另一件事——
把点云真正变换到 world、用 producer 重新算 FIM 再求逆，与搬运后的协方差比较，相对误差 1e-4
（信息侧 1.5e-8）。该检查由审阅侧加入，不在此脚本里；我不把它记成自己的证据。

两个反例在修后 **mode 与门指标都不再随平移变化**；第三个是审阅要求的"真实 producer 旋转弱方向
+ 非零平移"新例，同样不变。

### 仍未验收

- 审阅侧要用**同一脚本**独立复现；本文只报我的运行结果，不代替他们的复现。
- E3 的 `body[ref_scan]` 声明仍是旧 producer（多帧各自原点 FIM 直接平均）加新标签，
  未闭合；当前事务/trace 不消费它，按审阅意见延期。
- `aux_or_loop_info_6x6` 仍无 frame 声明。
