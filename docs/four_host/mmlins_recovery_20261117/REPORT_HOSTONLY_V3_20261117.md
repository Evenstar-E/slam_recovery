# host-only 复现 run（v3）报告：无 hold 时不复现崩溃，空休眠地图路径也未触发

**性质**：无 driver、无任何恢复命令的原生 run；判据见 `../PREREGISTRATION_HOSTONLY_V3_20261117.md`（run 前写定）。

## 1. 身份与结局

| 项 | 值 |
|---|---|
| 命令 | `tools/run_host_only_mmlins.sh /tmp/mmlins_hostonly_v3_20261117 campus_12_fl.bag 470` |
| 输入 | `campus_12_fl.bag` sha `a924b5f9…`，`PLAY_RATE=0.5`，无 driver（`recovery_commands=NONE`） |
| 后端 | `alaserPGO` sha `cc99d2ea…`（含修法 A 守卫） |
| 结果 | 13:23–13:39，`RUNNER_EXIT=0`，**`pgo_alive_at_exit=1`** |
| 录制 | 958 s，12120 条：`/Odometry` 4189、`/aft_pgo_odom` 7927、`/Issleeping` 2、`/Isbuilding` 2 |

## 2. 宿主原生行为（与旧报告一致）

- `/Odometry` 覆盖 bag 0.31–469.41 s，两段休眠闸口：**116.31→140.01 s（23.7 s）** 与
  **230.21→257.01 s（26.8 s）**——与 `mmlins_campus12_20261112/REPORT.md` 记录的 23.7 s / 26.8 s
  逐项一致；
- `Issleeping` 2 条、`Isbuilding` 2 条，`pgo.log` 有 2 轮 `Whether to sleep…/Whether to start…`；
- 前端 161 次 `IMU Initial Done`。

## 3. 判据逐条对照（预登记 §3）

| 判据 | 实际 |
|---|---|
| PGO 结束时存活 | **是**（`pgo_alive_at_exit=1`，`/aft_pgo_odom` 7927 条到 bag 尾） |
| `skipping sleeping map N` 出现 | **否，0 条** |
| 无 skip 且不崩 | **命中该条**：本次既证明不了守卫被触发，也证明不了该路径原生可达 |

## 4. 结论（收窄）

- **无 hold 条件下不崩溃**，且**空休眠地图路径没有被走到**（守卫零次触发）。
- 因此：**不能**把 v2 的 SIGABRT 归为「宿主原生、与接线无关」；
  也不能声称修法 A 已被验证有效——它在这条 run 里根本没被走到。
- 结合三次 run：v1（1.0×，有 hold，无崩）、v2（0.5×，有 hold，E1 后崩）、v3（0.5×，无 hold，无崩），
  目前能说的只有：**崩溃只在「有 hold + 0.5×」这一次出现，单次、未复现**。归因仍是 `UNKNOWN`。

## 5. 下一步要回答的两个问题（都需新 run 授权）

1. **崩溃是否复现**：用同速率、同一 driver（含 hold）重跑一次，看修法 A 是否让 PGO 活下来。
   若再次崩溃且守卫未触发，说明根因不在 `performSimilarClosure`，需要栈回溯或 core dump。
2. **stale 判据与回放速率不匹配**：v3 证明该宿主原生就有 23.7 s / 26.8 s 的 bag 时间断口，
   0.5× 下等于 47 s / 54 s 墙钟，`--pose-stale-sec 15` 必然误杀。要么按速率换算该参数
   （须在预登记中声明为 bag 等价），要么改用 1.0× 并接受检查点落在边界之后。

## 6. 不声称

- 不声称修法 A 有效或无效（零次触发）；
- 不声称崩溃是原生缺陷（无 hold 时不崩）；
- 不声称崩溃由接线引起（单次、未复现、无栈回溯）；
- 不声称整链有任何进展：本 run 没有 driver，没有隔离、判定、写回或接回。
