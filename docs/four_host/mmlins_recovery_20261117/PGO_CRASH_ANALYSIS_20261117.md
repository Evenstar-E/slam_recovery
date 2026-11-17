# v2 中 `alaserPGO` SIGABRT 的静态定位（2026-11-17）

**性质**：**静态代码追查**，不含任何新 run。结论是「崩溃路径可复现地存在于源码里」，
以及「本次冻结让这条路径更容易被走到」。没有运行证据能证明这次崩溃就是这一条路径，
因为崩溃现场没有栈回溯（`exit -6`，只有断言文本）。

## 1. 现场

v2（`two_event_mmlins_v2_20261117/`）：

```
alaserPGO: .../KDTreeVectorOfVectorsAdaptor.h:61: ... Assertion `mat.size() != 0 && mat[0].size() != 0' failed.
[alaserPGO-1] process has died [exit code -6]
```

时间 12:45:52，E1 resume（12:44:59）之后 53 s，E2 hold（12:48:32）之前 2 分 40 秒。
`pgo.log` 在此之前有两轮 `Whether to sleep the currently active map` / `Whether to start a new
active map`。

## 2. 代码路径（逐行）

1. **休眠处理器不检查地图是否为空**：`SC-PGO/src/laserPosegraphOptimization.cpp:862`
   `Mapmanager.act_change();` 直接把当前 `ActiveMap` 推进 `SleepMapList`；
   `include/mapmanager.hpp:73-76` 的 `act_change()` 只有 `SleepMapList.push_back(ActiveMap);`，
   没有 `keyframeposes.empty()` 之类的判断。
2. **新地图是空的**：`process_map_surveillance()` 在 `isMapbuilding` 时调用
   `Mapmanager.act_reset()`（`laserPosegraphOptimization.cpp:900`），
   `mapmanager.hpp:78-81` 新建一个空 `MapmanagerType`，其 `scmanager` 没有任何描述子。
3. **相似回环遍历休眠地图**：`performSimilarClosure()`（`laserPosegraphOptimization.cpp:677-707`）
   只用**当前活动图**做门限：`if (SleepMapList.empty() || ActiveMap->scmanager.polarcontext_invkeys_mat_.size() < 2) return;`
   ——**没有检查每个休眠地图自己的描述子数**。
4. **在空矩阵上建 KD 树**：循环里对每个休眠图调用
   `similar_detectLoopClosureID(...)`（`laserPosegraphOptimization.cpp:688`），
   该函数在 `include/scancontext/Scancontext.cpp:362-366` 用
   `polarcontext_invkeys_to_search_.assign(polarcontext_invkeys_mat_.begin(), ...end())`
   然后 `std::make_unique<InvKeyTree>(...)`；
   它只检查了**入参** `Curr_Key`/`Curr_polarcontexts` 是否为空（:355），
   **没检查 `this->polarcontext_invkeys_mat_`**。空矩阵进入构造函数即命中
   `KDTreeVectorOfVectorsAdaptor.h:61` 的 `assert`。

即：**「活动图在没有任何关键帧时被 sleep」→ 下一个关键帧到达后 `performSimilarClosure` 遍历到这张空图 →
断言崩溃。**

## 3. 与本次接线的关联（只说机制，不判因果）

`pgo_hold` 冻结的是关键帧插入（`process_pg()` 里的 `continue`）。冻结期间前端照常发布，
它的 `Issleeping` 也可能照常到达 PGO；于是「活动图为空 → 被 sleep」在冻结期间**明显更容易发生**：
地图在被释放前本来就没有机会长出一个关键帧。

这解释了为什么同一份源码与二进制在 v1（1.0×、无 E2 后端参与）跑满 468 s 未崩，而 v2 崩在
E1 释放之后。但**没有栈回溯，也没有最小复现**，所以本条仍是「机制上可能的路径」，
不是「已证实的成因」。

## 4. 两个最小修法（都未实施，等用户选择）

| 方案 | 改动 | 风险 |
|---|---|---|
| A. 跳过空休眠图 | `performSimilarClosure()` 循环里对 `polarcontext_invkeys_mat_.empty()` 的休眠图压入哨兵值并跳过（保持 `similar_mapindexes` 与 `SleepMapList` 下标对齐） | 只在空图存在时生效；非空时行为完全不变 |
| B. 不 sleep 空图 | `process_map_surveillance()` 在 `act_change()` 前判断 `ActiveMap->keyframeposes.empty()`，为空则不推进休眠列表 | 可能改变地图管理与回环候选集合，影响面比 A 大 |

两者都不改门阈值、不改 ICP、不改估计器。**A 更小**，但都需要用户同意后再改宿主源码并重建。

## 5. 不声称

- 不声称已定位本次崩溃的根因：没有栈回溯、没有最小复现、没有 A/B 对照 run；
- 不声称崩溃与 `pgo_hold` 有因果：只能说机制上更易触发；
- 不声称修好 A 就能让 v2 的整链成立：v2 还有 driver 早停（stale 判据 vs 回放速率）与门两次拒绝。
