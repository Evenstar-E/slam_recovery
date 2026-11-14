# 7e66ecd增量审阅：E2控制生命周期闭合，真实修复仍卡在候选质量

面向用户与S1/S2/S3开发侧。2026-11-14 19:07（UTC+8）fetch固定 `origin/main=7e66ecdb2b575fa0b7b8f2db2c0d1587fd26f654`；前一版本为 `d9e4f34c251a526f3c0aa2cd4beb5a4dc074f6ea`。本会话repair-f3单独持有20min/2h/日报任务，无旧repair-3e活owner双写。

本机只读Git原件和源码，执行标准库清单脚本；**未代跑ROS/宿主、未重建、未修改算法、参数或冻结科学门**。开发侧的三次run及build均为归档实测，不是本机独立复现。

## 1. 总结判定

**有实证推进，但只推进到受控双事件生命周期闭合；真实accepted测量修复仍未达成。**

第三次run `two_event_v9b_rearm_authorized` 的两个scripted事件均实际触发并形成判决，E1拒绝后能够rearm，E2的Mode 3等待按20秒墙钟限制关闭、rearm并resume；退出 `final_state=HEALTHY`、`quarantine_open_at_exit=false`。这关闭了上一轮“E2永不结束、checkpoint必被re_slam失效”的旧断点。

但 `HEALTHY` 的来源是**安全放弃未解决段并重武装**，不是测量修复成功。E2仍被门拒绝，repair clouds与reprocess均为0；因此不能把开发任务中的“A1达成”外溢为A/B评分表的完整闭环、全输入恢复或论文净收益通过。

## 2. 现在E2具体卡在哪里

### 主断点：整段单刚体ICP候选不可信

固定第三次run的[candidate](../four_host/fastlio_recovery_20261113/two_event_v9b_rearm_authorized/candidates.jsonl)、[ICP原件](../four_host/fastlio_recovery_20261113/two_event_v9b_rearm_authorized/icp_detail.jsonl)及[run_summary](../four_host/fastlio_recovery_20261113/two_event_v9b_rearm_authorized/run_summary.json)：

- 候选模式为 `single_rigid_transform_for_the_segment`，`ITERATION_LIMIT`，20次后 `icp_converged=false`；
- 给出旋转 **2.912867°**、平移 **3.463195m** 的整段修正；
- 仅 **1/11** 帧改善，Wilson下界 **0.020547**；
- candidate平均残差 **194.705429**，高于incumbent **186.594305**；
- 最终 `MODE3_SOFT_BRIDGE_WAIT`、`accepted=false`。

所以当前不是“阈值太严导致好修复被误拒”的证据，而是**候选没有显示收益且拟合未收敛**。同一binary/bag下，E1在第二、第三次run的改善数由9/13变为3/12，也支持候选不稳定；该跨run比较只针对E1，不冒充E2重复统计。

### 独立边界：E2 checkpoint仍晚于隔离起点

E2 restore ACK已为 `valid=1 frame=2091`，但snapshot实际时间比声明边界晚 **200,143,352ns（0.200143352s）**：

```text
checkpoint_check=LATE_AFTER_BOUNDARY
rollback_support=UNSUPPORTED_AT_OR_BEFORE_QSTART
```

因此`valid=1`只证明宿主成功恢复到该checkpoint，**不证明它合法覆盖整个隔离段**。这是下一accepted链仍需修正的时间边界，不是CPU、内存或实时性问题。

### 收尾性质：92个frame refs未解决，并非修复/重放完成

E2等待超时关闭的lifecycle原件列出 **92个`raw_frame_refs`** 为`frames_unresolved`，`unresolved_segments=1`；最终因 `INPUT_STALE` 结束，不是排空到完整尾段。driver同时给出 `fully_decided=true`，只代表其自身按episode候选判决分类，不能覆盖lifecycle中明确保留的未解决段，更不能称这些输入已修复、重放或进入地图。

该口径矛盾应由S1在后续结果中明确并列报告；它属于功能结果诚实性，**不作为新增工程开工门**。

## 3. 版本绑定验收

| 检查项 | 独立状态 | 版本化证据与限制 |
|---|---|---|
| 两事件控制生命周期 | **PASS（仅限受控生命周期）** | 第三次run fired 2/2、decisions 2、E2 wait-limit close→rearm→resume，final HEALTHY且无开放quarantine；scripted，非自动检测 |
| E1/E2 restore宿主ACK | **PASS（valid=1）** | 两次restore均valid=1，旧`checkpoint_invalidated_by_re_slam`断点已关闭 |
| E2合法完整checkpoint | **FAIL** | E2晚边界0.200143352s，`UNSUPPORTED_AT_OR_BEFORE_QSTART` |
| accepted测量修复→native update/map | **FAIL／本run NOT_EXECUTED** | E1/E2均拒绝，repair clouds=0、reprocess=0；没有真实accepted修复链 |
| 全输入恢复/拒绝后追赶 | **FAIL／catch-up NOT_IMPLEMENTED** | E2 92个refs unresolved、1个unresolved segment；fully_decided不能外溢为已恢复 |
| 自动检测 | **NOT_EXECUTED** | `detection_enabled=false`，两次均为绝对stamp scripted触发 |
| ALI-H真实M/I与性能 | **BLOCKED／NOT_EVALUABLE** | 本提交没有真实M/I、独立标签或同人口评价新增，不用ICP/NIS代替 |
| 实时性 | **NOT_EXECUTED** | 全部run为0.5×，只作功能证据；不据此设资源放行门 |
| 干净环境完整复现 | **证据不足** | binary/bag SHA固定；run的driver仍写`d9e4f34+`，不是完整不可变source身份，不影响上述原件事实但不称完整复现 |

本轮可记FAST-LIO受控A2/A10生命周期证据增加；A4/A5/A6/A9/B2/B11仍未完整闭合，A3/B3/B4无新有效成绩。**不做全表重新评分，不把16/36、11/36沿用到7e66ecd。**

## 4. 最小解除与下一单一主线

**下一唯一主线是：在合法E2边界上产生真实accepted测量修复，进入原生update/map，再接回并完成第二事件与输入归宿。**

当前首先需要解决候选生成方法，而不是调门：

- S1基于第二、第三次run提出“逐帧或带运动先验重配准”的最小方法方案，说明它如何区分当前单刚体病态假设及预期代价；按既有规则，方法替换由用户选择后再实施，第四次授权run保留，不自行扩实验矩阵。
- S2保持v9宿主及现有hold/publish/restore原件，不把宿主restore失败继续当作当前根因。
- 不调低paired-benefit或冻结科学门，不仅凭增加迭代次数制造接受；没有同版本同人口参数规律就不启动参数扫描。
- ALI-H缺标签只限制检测性能主张，不阻塞上述原生功能链。资源与实时性继续后置。

若用户选择“本序列两事件均不可信、接受安全拒绝”作为结论，则必须同时保留候选未收敛、E2晚边界和92个unresolved refs，不能把安全拒绝包装成实际恢复成功。

## 5. 独立复现命令

```text
C:/Python315/python.exe -I -B docs/review_20261114_7e66ecd/review_checks.py
```

结果见[review_checks.json](review_checks.json)。脚本只读取固定Git对象并断言上述事实，最终exit 0。初次检查中的手算迟到值及binary注释文本比较断言失败属于本机检查脚本错误，修正后通过；宿主原件未改变。未执行任何归档宿主代码。
