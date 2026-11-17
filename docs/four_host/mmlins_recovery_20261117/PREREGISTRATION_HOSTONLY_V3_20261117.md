# 修法 A + host-only 复现 run：预登记（2026-11-17，run 前写定）

**用户决定**：2026-11-17「A 授权」——采纳 `PGO_CRASH_ANALYSIS_20261117.md` §4 的**修法 A**，
并授权一次 host-only 复现 run。

## 1. 代码改动（修法 A）

`SC-PGO/src/laserPosegraphOptimization.cpp::performSimilarClosure()`：遍历休眠地图时，若该图的
`scmanager.polarcontext_invkeys_mat_` 为空，则**跳过**它——压入哨兵检测结果 `(-1, 0.0f)` 与
哨兵距离 `1e9`，保持 `similar_mapindexes` / `detectResult_sleepmap` 与 `SleepMapList` 下标对齐；
哨兵不可能赢得最小值，也不可能触发合并（`detectResult.first > 0`）。

同时打印 `[NATIVE_RECOVERY] similar-closure: skipping sleeping map N with no keyframes`，
让「是否真的走到这条路径」留下原件。

**未改**：门阈值、ICP、估计器、噪声模型、关键帧间距、`act_change/act_reset` 的地图管理语义
（空地图仍会被 sleep，只是不再被拿去建树）。

## 2. run 声明

| 项 | 值 |
|---|---|
| 命令 | `tools/run_host_only_mmlins.sh /tmp/mmlins_hostonly_v3_20261117 campus_12_fl.bag 470` |
| 输入 | 同 v2：`campus_12_fl.bag` sha `a924b5f9…`，`PLAY_RATE=0.5` |
| 差异 | **不启动 slam_recovery driver**，因此**没有任何 hold/snapshot/restore/resume 命令** |
| 保留 | 同一 `native_recovery_dir` 参数（通道打开但无命令）、同 bag、同速率、同前端二进制 |
| 后端 | 新二进制 `alaserPGO` sha `cc99d2ea…`（含 A 的守卫） |

## 3. 判据（run 前写定）

| 观察 | 含义 |
|---|---|
| 结束时 `alaserPGO` 存活且有 `/aft_pgo_odom` 输出 | 无冻结条件下不再崩溃 |
| `pgo.log` 出现 `skipping sleeping map N` | **空休眠地图在无 hold 时也会出现**——证明该路径是原生可达的 |
| `pgo.log` 无 skip 行且不崩溃 | 无 hold 时不产生空休眠图；本次不能证明守卫被触发，也不能证明原生可达 |
| 仍然崩溃 | 守卫未覆盖该路径（可能不是 `performSimilarClosure`），需重新定位 |

## 4. 本 run 不能说明什么

- 不说明 hold 条件下是否还会崩——本次没有 hold；要回答那个问题需要另一条 run 授权；
- 不说明整链能否成立：没有 driver，就没有隔离、判定、写回或接回；
- 不说明宿主性能或实时性：0.5× 回放。

## 5. 结果

（run 后填写。）
