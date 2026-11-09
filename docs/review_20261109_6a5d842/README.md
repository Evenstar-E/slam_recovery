# 复核 · 6a5d842（对台账 §9.11 十二问的答复）

**范围**：`6a5d842` "docs: answer the twelve review questions with reproducible evidence"，新增 4 文件 / +301 行（答复文档、探针脚本、探针输出、台账 2 行）。
**方法**：逐题读答复；**实际运行** `probe.py` 并比对 `probe_results.json`；复核 SHA256、行号、manifest 数字、论文 tex；`python -B -m unittest discover -s slam_recovery/tests` → **22/22 PASS**。

## 结论

**答复质量高，逐题可验证，Accept。** 十二题没有回避：能证的就实测，证不了的就直说"无法复现"或"仓库里没有来源"。这一点比前几轮任何一次提交都好。

但这次答复同时也确认了两件事，都比台账原本列的问题更重：

1. **一个 P1 级缺陷**：在线节点的配对收益检验，参考集里包含了候选自己的扫描（§三）。开发侧自己把它列为"优先修复哪一项"，我独立确认了代码路径。
2. **论文已经承认核心增量未被测出**：受控仿真里"只隔离"和"验证后准入"的污染率**都是 0%**（§四）。新摘要已经把这句话写进去了。

---

## 一、逐题验收

| 题 | 答复 | 我的独立核验 |
|---|---|---|
| 1 street_08 失败几项 | 两项失败、一项通过；TD-01 可关闭 | ✅ 期刊稿、提交包稿、RSS 稿三份 tex 均已改为 "passes the boundary-jump criterion ... both fail" |
| 2 4 帧还是 8 帧 | 以节点分段规则为准；两份文档 SHA256 `6ab89c90…c0a70c`，**都仍带 1857 行矛盾** | ✅ 实测两份 hash 完全一致；第 1857 行矛盾确实仍在 |
| 3 测试何时补 | 建议下一次门控补丁补永久回归；本轮用探针 | ✅ 复跑探针：0.40 与恰好 0.50 通过，0.5001 拒绝；7 关键帧配 4 帧通过、8 关键帧配 7 帧被拦、配满 8 帧通过 |
| 4 是否取 max | **应改**；给出 base=10 + large=8 的反例 | ✅ 探针输出 `8_keys_8_matched_base_10` → `approved: true`，反例成立 |
| 5 键名 | 建议统一 `required_paired_frames` | ✅ 与台账 TD-05 一致 |
| 6 0.92 / Wilson 0.0 来源 | **找不到共同来源**；给出两代归档 | ✅ 探针读取 `75e0ee5`/`6d1f7e4` → 0.188 / 0.0000；`00080c1` → 4.519 / 0.8061 |
| 7 加不加跨帧判别 | **建议加**，并给出世界固定注入的设计 | ✅ 与台账 TD-10 一致；当前注入确为机体系固定 |
| 8 intensity | 建议暂不启用；仅换强度后全部输出不变 | ✅ 探针 `all_outputs_identical_after_changing_intensity: true` |
| 9 低于 30% | 受控检查：200 点估 20.2% 全留；400 点估 40.5% 全删并误删 5 个真实点 | ✅ 与探针输出逐项一致 |
| 10 何时停修 | 无在线尾段判据；建议"进入快、退出慢"两段式 | ✅ 代码确无退出判据（与 TD-12 一致） |
| 11 2 秒余量 | 固定；风险取决于**起点估晚多少**与历史保留量 | ✅ `manager.py` 确为 `onset − margin` |
| 12 三项指标 | 覆盖率为 0/未定义口径缺失；给出 P7 局部计时；混淆矩阵分母缺失 | ✅ P7 计时 0.0565/0.0628、0.0032/0.4616、110.82/120.37 ms 与 manifest 完全一致 |

**核验通过的数字**：22/22 测试；两份 `SLAM_RECOVERY_RESEARCH.md` 的 SHA256 均为 `6ab89c90879c…c0a70c`；仿真污染率 B0 `0.4325`、B4 `0.0`、B6 `0.0`。

---

## 二、答复本身值得肯定的地方

1. **可复现**：每条结论都有探针输出或 manifest 引用，不是"已修复"三个字。
2. **敢说没有**：第 6 题直接写"没有找到这对数的共同来源"，第 12 题直接写"无法据此填满四格"。这比编一个来源强得多。
3. **主动降级结论**：第 8 题指出当前注入用了人为强度分布，"直接据其高亮报警很容易学会辨认注入器"——这是对自己方法的有效性质疑。
4. **自己在第 6、9 题里区分了"估出的污染比例"与"真实点身份"**，没有把受控小样例的误删率冒充真实场景指标。

---

## 三、P1：配对收益的参考集包含候选自身扫描

这是本轮最重要的发现。开发侧在"优先修复哪一项"里描述了它，但没有给出代码位置和影响范围。我独立确认如下。

**代码路径**（`slam_recovery/sim/transaction_manager_node.py`）：

```python
# :340-346  参考集 = 冻结可信图 + 候选自身的非留出扫描（用候选位姿变换）
train_world_list = [trusted_map_pts] if len(trusted_map_pts) > 0 else []
for k in train_kfs:
    T_k = repaired_poses[k]
    train_world_list.append((pts_b @ T_k[:3, :3].T) + T_k[:3, 3])
train_world = np.vstack(train_world_list)

# :378  这个参考集被直接传给配对收益检验
paired_ok, wilson_lb, reentry_jump = self._measure_paired_evidence(
    repaired_poses, incumbent_poses=..., reentry_anchor_pose=..., reference_world=train_world)

# :264  参与打分的帧是"全部可配对关键帧"，不是只留出帧
paired_keys = [k for k in keys if k in self.scan_buffer_body and k in incumbent_poses]
```

`_measure_paired_evidence` 内部对 incumbent 与 candidate 用的是**同一个** `ref_pts`。于是对于每个 `train_kf`：

- 候选自己的点云**已经在参考集里**（由候选位姿变换过去）；
- `compute_disjoint_holdout_point_to_plane_nis` 用最近邻拟合局部平面，邻域里就包含该点自身；
- 该点的残差天然接近 0，而 incumbent 在同帧的残差不会。

结果：`holdout_stride=5` 下，**4/5 的参与帧被系统性地判为"候选改善"**。只有第 5 帧是真正独立的。Wilson 下界因此在结构上偏高。

**影响范围**：
- 受影响：`OnlineRecoveryTransactionNode`，即 S1/S2 的全部门控判决，以及任何在线部署。S1/S2 manifest 里的 `improved_fraction: 1.0` 就来自这条路径。
- 未受影响（但另有问题）：E3 脚本直接调用 `evaluate_paired_sequential_benefit`，传入的是自己算的 NIS 序列，不经过这个 `train_world` 构造。该路径本轮未审。

**修法**（与开发侧建议一致，需补一条）：
1. 配对参考改用**冻结的 onset 前可信地图**，不再拼入任何候选扫描；
2. 或对每一帧从参考集中剔除该帧自身及其时间邻域，并**记录两侧扫描 ID**；
3. 加一个反例：候选自贴生成的地图在自己帧上很好、在独立扫描上变差——修好后这个反例必须被拒。

**为什么是 P1**：论文把 Wilson 下界写成"候选逐帧改善的统计证据"。如果 4/5 的样本是自证的，这个统计量不能支撑该结论。开发侧说"还不能量化它改变了几次判决"——这个量化正是修完之后必须补的。

---

## 四、论文侧已经发生的变化（比台账更重）

`c1163c8` 重写了摘要与贡献列表，措辞从"我们恢复"变成"我们扣留"。关键两句：

> Quarantine alone and quarantine with verified admission both report zero contamination; **their map coverage and incremental admission benefit remain unresolved**.

> The outstanding experiment is a single-host, same-input comparison of native mapping, quarantine alone, unconditional admission and verified admission.

我核对了对应的 manifest：

| 臂 | 3D 体素污染率 |
|---|---|
| B0 不保护 | **0.4325** |
| B1 在线投影 | 0.432 |
| B3 同数据回滚 | 0.4325 |
| **B4 只隔离** | **0.0** |
| **B6 验证后准入** | **0.0** |

**也就是说，受控仿真里 B4 与 B6 完全相同。** 唯一能区分"验证准入"与"只隔离"的证据，只剩下 street_08 的一次拒绝——而那次拒绝依赖的配对统计，正是 §三 里被污染的路径。

这不是新问题，是台账 TD-14/TD-16 的合并结论，但现在有了硬证据：**当前实验设计无法证明门控比"只隔离"更好。**

新摘要把它写成"待解决的实验"，这是诚实且正确的处理。但它同时意味着：这篇论文现在的贡献是**containment（扣留不可信写入）**，不是 **recovery（验证后恢复）**。用户需要明确接受这个定位降级，或者补那个 matched experiment。

---

## 五、未独立核验的项

1. **两份 PDF 的正文**：本机无 `pypdf`/`PyPDF2`，PDF 对象流压缩无法用正则提取。答复称已核对期刊 9 页与 RSS 4 页 PDF；我只核对了三份 `.tex` 源文件，PDF 内容**未独立确认**。
2. **真实序列回放**：本机无 bag 数据，未重跑宿主。答复也声明"此次没有回放传感器数据"。
3. **泄漏对历史判决的实际影响**：未量化，与开发侧结论一致。

---

## 六、建议顺序

1. **修 P1（配对参考泄漏）**，并补"自贴地图"反例；这是唯一能让 Wilson 证据重新有效的改动。
2. **补 matched experiment**：同一输入、同一宿主，四臂对比（原生 / 只隔离 / 无条件准入 / 验证后准入），同时报**污染率**与**覆盖率**。这是新摘要自己点名的实验，也是论文能否从 containment 升回 recovery 的唯一路径。
3. 修 TD-02（1857 行，两份文档 hash 相同，一起改）。
4. 补 TD-03 的两条永久回归（探针已验证规则，直接转成断言即可）。
5. TD-04 改 `max()`、TD-05 统一键名——这两条是几行代码。
6. 之后再谈世界固定注入（TD-10）与逐点软权重（TD-11）：它们的价值取决于第 2 步测出来的覆盖率增量。

---

## 复现

```sh
python -B -m unittest discover -s slam_recovery/tests -v    # 22/22 PASS
python -B docs/review_20261106_5e2cf69/probe.py             # 与 probe_results.json 逐项一致
```

本机未播 bag、未重跑宿主；PDF 结论未独立核验，其余数字均来自实测或 manifest 直读。
