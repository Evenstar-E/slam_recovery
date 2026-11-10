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
| `sim/transaction_manager_node.py` | segment `world[world]`，candidate `world[world]` | 见下 |
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
