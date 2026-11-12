# T2 开跑前的三处修正：复现与执行输出（2026-11-12）

对象：审阅 `febf68d` 提出的三个缺陷。全部在 T2 真实数据之前修；T0 的 UNKNOWN 资格结论不变，
但 T2 的计分与 UNKNOWN 时长现在建立在修好的实现上。**未跑宿主、未改旧归档、未改共享代码。**

## D1. SE(3) Log 平移漏了 `V(ω)⁻¹`

- 位置：`t2_input_check.py::e_i`。
- 复现输入：`Rz(0.2)` + `t=(0.1,0,0)`。
- 修正前：`e = (0, 0, 0.2, 0.1, 0, 0)`——平移直接取 `t`。
- 修正后：`e = (0, 0, 0.2, 0.099666444232592, -0.01, 0)`，即 `ρ = V(ω)⁻¹ t`；
  `V⁻¹ = I − 0.5·hat(ω) + c·hat(ω)²`，`c=(1−(θ/2)cot(θ/2))/θ²`，小角用 `I − 0.5W + W²/12`。
- 回归控制：selftest 断言 `|e[3] − 0.1| > 1e-4`，旧错误值会直接 FAIL。
- 执行：`python -I …/t2_input_check.py selftest` → `rotvec+V^-1 translation recovered PASS`。

## D2. 整块缺测仍跨空窗累计 dwell

- 位置：`ali_h_v1.py::block_summary` / `classify_blocks`。
- 修正前：`block_summary` 只遍历有行的块；`classify_blocks` 只看 `prev_verdict`，块 10、12 两个
  ALARM（中间没有块 11）会在块 12 输出 **SUSPECT**。
- 修正后：
  - `block_summary` 在首末块之间补齐 `NO_DATA` 块（`n_frames=0`，三通道 `NO_DATA`）；
  - `classify_blocks` 在 `block_id != prev+1` 时清空 `prev_verdict`（dwell 断开），`last_suspect` 保留；
  - `NO_DATA` 块本身输出 `UNKNOWN`、原因 `NO_DATA_BLOCK`。
- 复现输出：块 8、9 ALARM → 块 9 `SUSPECT`；块 12 ALARM（跨空窗）→ **UNKNOWN**；
  8、9 ALARM → NO_DATA(10) → 11 ALARM → 11 **UNKNOWN**，`last_suspect_block=9`；
  `block_summary` 对帧 8、12 补齐 `[8,9,10,11,12]`，9–11 为 `NO_DATA`。
- 执行：`…/ali_h_v1.py selftest` → `T1.7 dwell does not cross a missing block PASS`。

## D3. validator 的 READY 不证明协方差与残差同切空间

- 位置：`t2_input_check.py::check_manifest`。
- 问题：`e_i` 固定是 `inv(pre)·post` 的 **right / pre_body** 残差，但旧 validator 只要求声明
  `left/right`、`body/world` 就 READY；`s_i` 直接把传入 P 当 `e_I` 协方差，左扰动/世界系可差数量级。
- 修正后（协方差可用时）：
  - `declarations.perturbation == "right"`；
  - `covariance.perturbation == "right"`；
  - `covariance.frame == "pre_body"`；
  任一不满足 → `INCOMPLETE`（不实现转换，也不把 S/H_T_H 当 6×6 位姿协方差）。
  协方差不可用 → `READY_UNIT_ONLY`，只给单位权 `e_I`，不宣称卡方概率。
- 执行输出（`t2_prep_selftest.json`，14/14 PASS）：
  - `left perturbation is refused PASS`；
  - `covariance in another frame is refused PASS`；
  - `missing covariance frame is refused PASS`；
  - 原 `valid manifest is READY`、`S rejected`、`old run id rejected` 仍 PASS。

## 副作用：T0 块数

`block_summary` 补齐空块后，Run B 从 **119 → 120 块**（1 个 `NO_DATA` 块），Run A 仍 90 块；
T0 的 402/544 帧 UNKNOWN 结论与通道证据计数不变。REPORT §1/§2.4 已同步。

## 复现命令

```bash
python -I docs/ali_h_v1_research/ali_h_v1.py t0
~/mm/micromamba run -p ~/mm/ros python -I docs/ali_h_v1_research/ali_h_v1.py selftest
~/mm/micromamba run -p ~/mm/ros python -I docs/ali_h_v1_research/t2_input_check.py selftest
```

结果：T0 完成；T1 **7/7 PASS**；T2 prep **14/14 PASS**；真实 T2 仍 `NOT_EXECUTED`。
