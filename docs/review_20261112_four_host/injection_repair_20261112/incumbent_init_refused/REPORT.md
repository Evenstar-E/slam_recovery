# 第二次尝试：incumbent 初值 —— 候选被拒，修复未发布

同一 bag、同一绝对戳 `1627785276215170145`、同一 relay 窗口 `[1627785276208000000,
1627785282215170145)`、同一 margin 4.0、同一 `candidate_source=icp_reregistration`。只改了
ICP 初值：从宿主位姿改为 trusted-map 常速外推（incumbent），候选位姿 = `ΔT_inc · incumbent`。

## 1. 结果

| 项 | 值 |
|---|---|
| run | `fl_native_20261112T044445Z_85628` |
| 驱动源码 sha | 见 `recovery_node_source.sha256`（提交 `e472410`） |
| 候选 | `MODE3_SOFT_BRIDGE_WAIT`，**refused** |
| before / after | 3.1341 / 6.3645（信息量过线：≥ 2×3.1341 = 6.2682） |
| Wilson / holdout | **0.2855**（< 0.55） / 0.6969 |
| committed / deferred | 0 / 19 |
| 生命周期 | `wait_limit_closed` → `rearm` → resume；终态 HEALTHY |
| 原生命令 | hold → **restore**（拒绝路径）→ resume；`reprocesses=0`，**没有发布修复** |

## 2. 发生了什么

初值换成 incumbent 后，ICP 不再"看不见"偏差：修正量从宿主位姿下的 **0.027 m** 变成
**0.815 m**（旋转 0.357°）。但这次拟合**没有收敛**：

- `status = ITERATION_LIMIT`，20 次迭代用尽；
- `icp_inliers = 706`（宿主位姿那次是 1352），残差 0.053 m；
- 常数速外推的初值离真实位姿约 0.8 m，而 ICP 的对应门限是前 10 次 **0.5 m**、之后 0.25 m
  （`pose_reregistration.py:13, 40-49`）——初始偏移大于门限，大量点在第一轮就找不到对应，
  修正量停在半路。

候选位姿 `ΔT_inc · incumbent` 因此既不是宿主位姿（已对齐）、也不是真实位姿，paired-benefit
的 Wilson 只有 0.2855，门拒绝。拒绝路径不发修复（只有 accepted 才发），所以本轮**没有
`bias_z` 可报**，也没有 `repair_received/applied`。

## 3. 与第一次（宿主位姿初值）对照

| 项 | 第一次（043602Z） | 本次（044445Z） |
|---|---|---|
| ICP 初值 | host_poses | incumbent |
| ICP 修正 | 0.027 m / 0.216° | **0.815 m / 0.357°** |
| inliers | 1352 | **706** |
| 状态 | ITERATION_LIMIT | ITERATION_LIMIT |
| 门 | accepted（Wilson 0.9023） | **refused（Wilson 0.2855）** |
| 修复 | 25 条，bias 0.0029 | 未发布 |

结论：incumbent 初值确实让偏差变得**可见**（修正量放大约 30 倍），但单次刚体拟合在 0.5 m
对应门限下收敛不了，候选位姿不满足 paired benefit。这是新的、具体的断点，不是"仍然无效应"。

## 4. 下一步最小修法（未实施）

两条都可做，建议 (b)，因为它不改变已被接受的门候选：

1. **让 incumbent 初值的 ICP 收敛**：前若干轮把对应门限放宽到 ≥1.0 m（或先做一次粗配准再细化）。
   改的是 `IcpConfig.gate_near_m` / `gate_far_m` / `gate_switch_iter`，属于修复生产者参数，
   不是门/阈值。
2. **解耦候选与偏差估计**：候选仍用宿主位姿初值的 ICP（已 accepted，Wilson 0.90）；偏差只用
   incumbent 位姿下的**一维 body-z 搜索**（或取 incumbent 拟合修正的 body-z 投影）估计，然后按
   该 bias 发布修复云。这样门看到的候选不变，修复仍用独立位姿估计偏差。

## 5. 能/不能声称

- 能声称：incumbent 初值把 ICP 修正从 0.027 m 放大到 0.815 m，偏差在该初值下可见。
- 不能声称：bias ≈ 0.5（本轮没有发布修复，没有测到）；任何修复效应；任何修复收益。
- 门/阈值/σ 未动；宿主 0 行改动；relay 与第一次相同（窗口与移位参数一致）。

## 6. 文件

`receipt.json`、`run_summary.json`、`candidates.jsonl`、`candidates_detail.jsonl`、
`icp_detail.jsonl`、`relay_frames.jsonl`、`host.log`、`lifecycle_events.json`、
`native_checkpoint_events.json`、`host_control/`、`launch_pair.sh`、`recovery_node.log`、
`machine_load.txt`、`recovery_node_source.sha256`。
