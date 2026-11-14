# 9c52e6e增量审阅：逐帧与注入偏置均为真实负结果，但“无可改善量”未获证明

面向用户与S1/S2/S3开发侧。2026-11-14 19:50（UTC+8）fetch固定 `origin/main=9c52e6e30962e1d8fa652e2d665cf205c45f9b5a`，比较前一已审 `7e66ecdb2b575fa0b7b8f2db2c0d1587fd26f654`。新增实质提交为 `2004e4e`（逐帧候选及第4次run）和 `2c6a930`（两次注入偏置run及incumbent初值接线）；`9c52e6e`只补协作记录。

开发记录称用户选择逐帧候选及注入偏置实验；这些选择不是本会话直接收到的指令。本审阅只核已归档结果，不据此追加run或授权。repair-f3持续任务单owner，无旧repair-3e双写；本机未代跑ROS、重建或修改算法/参数/科学门。

## 1. 总结判定

**部分推进：候选方法与受控注入人口得到真实运行和有价值负结果，但accepted测量修复→原生update/map仍未发生。**

三次新run均为scripted，合计6个候选全部拒绝，repair clouds=0、reprocess=0。它们可以区分当前候选在哪些人口上失败，不能证明自然事件信息不可恢复，也不能把安全放弃未解决段称为修复成功。

开发侧“事件本身没有可改善量”“不是候选实现问题”“两种候选都没能超过incumbent”的总括结论**不接受，原件存在直接反例**。

## 2. 关键反例：逐帧E2平均残差实际改善5.217%

第4次run `two_event_v9c_perframe_authorized` 的E2原件：

| 指标 | 值 |
|---|---:|
| 改善帧 | **5/11** |
| incumbent平均残差 | 338.028180 |
| candidate平均残差 | **320.392278** |
| 相对平均改善 | **5.217288%** |
| Wilson下界 | 0.242090 |
| 最终判决 | `approved=false`，`wilson_sequential_benefit_lower_bound_failed` |

因此正确结论是：**出现了平均改善信号，但逐帧一致性证据不足，冻结门拒绝。** 不能改写成“没有可改善量”或“candidate没有超过incumbent”。安全拒绝可以保留，科学门不能降低；但拒绝结果本身不证明真实误差为零，也不证明另一种方法无效。

E2 checkpoint在该run仍为 `LATE_AFTER_BOUNDARY / UNSUPPORTED_AT_OR_BEFORE_QSTART`，上一轮指出的合法边界缺口没有被第4次run关闭。

## 3. 注入偏置run的实际贡献与边界

两次relay原件各有60条`shifted=true`帧记录，`dz=0.5`，支持声明的body z +0.5m受控注入实际执行。自然事件负结果与注入人口应分开，不能混合评价。

| run／E1 | 初值与ICP | 门证据 | 独立判定 |
|---|---|---|---|
| `v9d_injected` 196s移动段 | host init，`CONVERGED`；修正1.288m/1.223° | 7/40；770.695532→756.930383，略有改善但Wilson 0.097755 | 当前候选未达门；不能据此称注入误差不存在 |
| `v9e_turn` 52s转弯段 | incumbent init，`ITERATION_LIMIT`；修正0.374m/0.551° | **0/40**；1437.607276→1571.076462，更差 | 该窗口和当前实现下明确负结果 |

`2c6a930`实际修正了single-rigid路径未把incumbent传给`_icp_candidate`的接线，说明此前不能排除实现因素；修正后的v9e仍为负结果，才把结论限定到**当前实现＋该窗口**。v9d与v9e同时改变窗口和初值，不是同版本同人口的参数效果比较，不能据此总结“host/incumbent初值哪个更好”。

两次注入run的E2均为声明的**clean second event**，不是第二个独立注入故障。它们证明受控生命周期可以继续，不证明两次独立真实故障恢复。

所有三次run仍以超时关闭未解决段后rearm：v9c有1个、v9d/v9e各有2个`unresolved_segments`；v9d最终`HOST_HIBERNATION_TIMEOUT`，其余`INPUT_STALE`。`HEALTHY`与`quarantine_open_at_exit=false`不代表未解决输入已修复、重放或进入地图。

## 4. 版本绑定状态

| 检查项 | 状态 | 证据与限制 |
|---|---|---|
| 逐帧候选真实实现与运行 | **PASS（实现/执行），FAIL（accepted）** | `2004e4e`及v9c原件；E1 1/13、E2 5/11，均拒绝 |
| 注入偏置真实生效 | **PASS（受控注入记录）** | 两run各60条+0.5m shifted帧；这是relay日志证据，不是独立轨迹/地图收益 |
| accepted测量修复→native update/map | **FAIL／NOT_EXECUTED** | 三run accepted=0、repair clouds=0、reprocess=0 |
| 合法checkpoint | **PARTIAL** | v9e两次均AT_OR_BEFORE；v9c E2及v9d两次仍LATE，valid=1不能覆盖时间边界 |
| 全输入恢复与完整尾段 | **FAIL** | unresolved segments仍存在；安全rearm不等于历史输入恢复 |
| 自动检测 | **NOT_EXECUTED** | 三run `detection_enabled=false`，绝对stamp scripted |
| ALI-H真实M/I、标签与同人口性能 | **BLOCKED／NOT_EVALUABLE** | 本轮无新增，不用ICP或NIS替代 |
| 实时能力 | **NOT_EXECUTED** | 0.5×功能run，不转成资源开工门 |

本轮增加的是A6/B4/B11相关的候选失败诊断和受控生命周期证据，未闭合真实修复、状态重估、地图重建及净收益。A3/B3自动检测没有新增。不做全表重评分，不沿用旧16/36、11/36。

## 5. 最小解除与下一单一主线

**下一唯一主线仍是：在已声明注入偏置人口上产生可验证的accepted候选，真实进入native update/map，再接回、处理后继事件并闭合输入归宿。**

在申请任何新run前，S1应先用现有两次注入的已知+0.5m标签做**离线oracle评价**：报告候选实际估计的偏置方向/幅值、相对incumbent和注入真值的误差，以及失败帧，不用候选自身残差证明正确。若原件没有足够candidate/scan导出，明确缺项，不伪造数值；再由用户决定是否授权一次有界oracle/native复验。

- **算法**：当前证据支持“候选改善不稳定、当前single-rigid实现不足”，不支持“信息不可恢复”或“所有候选方法无效”。方法替换仍按用户选择，不自动扩新模型。
- **工程**：incumbent初值接线已修；下一次必须把source/driver身份、完整candidate导出与原生update回执绑定。该项服务主线，不另设工程开工门。
- **参数**：没有同窗口、同人口、只改一个参数的效果/代价规律，不扫描ICP次数、Wilson门或相对增益门。
- **责任**：S1候选与集成，S2真实宿主/后续实际获授权run，S3可复用注入标签做独立评价；ALI-H缺项不阻塞原生accepted链。

## 6. 独立复核命令

```text
C:/Python315/python.exe -I -B docs/review_20261114_9c52e6e/review_checks.py
```

[review_checks.json](review_checks.json)记录固定Git原件的断言结果，exit 0。脚本不执行宿主、候选算法或注入relay，不将本机JSON检查冒称独立原生复现。
