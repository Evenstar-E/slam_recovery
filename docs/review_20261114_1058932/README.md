# 1058932增量审阅：option①未按冻结契约执行，checkpoint跨事件覆盖构成状态安全反例

面向用户与S1/S2/S3开发侧。2026-11-14 20:32（UTC+8）fetch固定 `origin/main=105893283b566d1043f75d1b2977479b80836f98`，前一已审版本为 `9c52e6e30962e1d8fa652e2d665cf205c45f9b5a`。新增运动先验多尺度方法、自然/注入两次run及`campus_2_fl`一次run。

开发记录称用户选择option①+②；不是本会话直接收到的授权，本审阅只核已归档实现和结果，不追加run。本机只读Git源码/原件并运行标准库断言，未执行ROS、宿主、候选算法或重建。

## 1. 总结判定

**有真实方法和运行增量，但accepted原生修复仍未达成；option①不能按当前原件宣布“冻结方法已确认失败”。**

原因不是增加工程门，而是两个直接影响功能与科学结论的反例：

1. 实现把冻结声明要求排除的`ITERATION_LIMIT`帧全部或大部分放进候选；
2. 注入run中第二事件snapshot在第一事件restore前覆盖了可变checkpoint，E1实际恢复到晚于其边界32.50秒的未来状态。

option②的新序列run只完成E1拒绝，E2因宿主休眠及90秒终止未触发，不能称两事件结果。

## 2. 反例一：候选包含冻结契约明确排除的未收敛帧

冻结文件[MOTION_PRIOR_METHOD_20261114.md](../four_host/fastlio_recovery_20261113/MOTION_PRIOR_METHOD_20261114.md)写明：

> 配准未收敛/无对应/无先验位姿的帧不进入候选。

但当前`build_motion_prior_candidate`实际为：

```python
if res.status in ("CONVERGED", "ITERATION_LIMIT"):
    poses[kf_id] = res.pose
```

归档ICP与候选人口直接对应：

| run／事件 | 候选帧 | 其中ITERATION_LIMIT | CONVERGED | 结论 |
|---|---:|---:|---:|---|
| 自然E1 | 21 | **20** | 1 | 大部分候选按冻结契约不应存在 |
| 自然E2 | 19 | **19** | 0 | 整个候选都由未收敛帧组成 |
| 注入E1 | 40 | **40** | 0 | 整个候选都由未收敛帧组成 |
| 注入E2 | 0 | 0；41帧TOO_FEW_CORRESPONDENCES | 0 | 无候选，记`no_repaired_poses` |

因此2/21、1/19、9/40是**当前实现**的负结果，不是冻结方法的确认性结果。最低解除是按已冻结契约排除未收敛帧；不能看结果后改冻结文本来容纳现有实现。若开发希望保留未收敛候选，应作为另一方法重新冻结并由用户选择。

## 3. 反例二：E2 snapshot在E1 restore前覆盖checkpoint

`two_event_v9g_prior_injected` 的`native_checkpoint_actions`顺序为：

| action序号 | 动作 | checkpoint stamp / frame |
|---:|---|---|
| 3 | E1 snapshot | `1711548075973547264` / frame 1760 |
| 5 | E2 snapshot | `1711548108373620736` / frame 2084 |
| 6 | **E1 restore** | **`1711548108373620736` / frame 2084** |

E1没有restore到自己的snapshot，而是restore到E2刚写入的checkpoint。相对E1声明边界晚 **32.500372397秒**，原件也标为：

```text
LATE_AFTER_BOUNDARY
UNSUPPORTED_AT_OR_BEFORE_QSTART
```

即使第一个snapshot本身也已晚边界0.100298925秒，后续覆盖是另一个独立问题：`valid=1`只说明宿主接受了一个有效checkpoint，**不说明恢复的是本事件合法状态/地图**。

最低解除不是通用框架扩张，而是当前事件关联的最小修正：

- 每个episode绑定不可变checkpoint身份并restore该身份；或
- 若宿主只能保存一个checkpoint，在E1判决/restore完成前禁止E2 snapshot覆盖；无法取得合法cp时明确`NO_ROLLBACK`，不能恢复未来状态。

在该反例未修正前，v9g不能作为合法两事件恢复链证据。其E2全部无对应点也不能单独归因候选算法，因为checkpoint/状态时序已被混淆。

## 4. option②实际到哪里

`two_event_v9h_seq2_turn`：

- E1实际触发，38个配对帧中4个改善，incumbent 1735.841119→candidate 1704.070419，Wilson 0.048140，拒绝；
- ICP为`ITERATION_LIMIT`，修正0.452542m/1.561018°；
- E1 checkpoint虽仅晚约0.000589秒，仍为`LATE_AFTER_BOUNDARY`；
- E2声明存在但未触发，宿主休眠后90.16秒无位姿，driver以`HOST_HIBERNATION_TIMEOUT`结束，`run_mode=CONTROLLED_TRIGGERS_NOT_FIRED`。

因此本次只能记**新序列E1候选负结果＋E2 NOT_REACHED**。不能推断宿主永远不会到E2，也不能把driver提前终止包装成两事件闭环。

另纠正一处记录：v9g relay实际为**2350条frame记录、60条shifted**，summary也是2350/60；开发文本的2352/61把window和summary两行计入了帧数。这不改变+0.5m注入实际发生，但应按真实分母报告。

## 5. 版本绑定状态

| 检查项 | 状态 | 影响 |
|---|---|---|
| 运动先验方法实现与真实run | **PARTIAL** | 有代码和运行，但候选包含冻结契约排除的未收敛帧 |
| accepted测量修复→native update/map | **FAIL／NOT_EXECUTED** | 三run accepted=0、repair clouds=0、reprocess=0 |
| 可信checkpoint与状态安全 | **FAIL（有反例）** | E1 restore使用E2 checkpoint，晚E1边界32.50秒 |
| option①科学结论 | **证据不足** | 当前run未按冻结候选契约执行，不能宣布方法已确认失败 |
| option②两事件 | **FAIL／E2 NOT_REACHED** | 仅E1拒绝；宿主休眠与90秒终止先于E2 |
| 自动检测 | **NOT_EXECUTED** | 全部scripted、detection off |
| ALI-H真实M/I与性能 | **BLOCKED／NOT_EVALUABLE** | 本轮无新增 |
| 实时能力 | **NOT_EXECUTED** | 0.5×；长ICP耗时只作诊断，不设资源开工门 |

本轮直接关联A4/A6/A9/A10、B2/B11：状态安全和真实accepted链未闭合。不能仅因增加方法、序列和测试数量提升A/B总分；不做全表重评分。

## 6. 最小解除与下一单一主线

**下一唯一主线仍是合法的accepted测量修复→原生update/map→接回→后继事件→输入归宿。** 在再次判定option①/②或转option③前，先消除上述两个混淆：

1. **S1**修正episode↔checkpoint绑定，保留v9g现有action序列作为负例；
2. **S1**使候选实现符合已冻结的“未收敛帧不进入候选”，不改科学门、不事后改协议；
3. **S2**在修正后仅执行实际获授权的有界复验，保留本次负结果；option②若复验须覆盖声明E2，不以90秒终止代替E2结果；
4. **S3**继续独立评价，真实M/I与标签缺口不阻塞原生功能修正。

这些修正针对实际状态/地图安全和科学协议一致性，不是CPU、内存、冒烟或可选工程门。没有新授权时只交代码/离线证据，不自行增加run。

## 7. 独立复核命令

```text
C:/Python315/python.exe -I -B docs/review_20261114_1058932/review_checks.py
```

[review_checks.json](review_checks.json)固定上述候选状态、action顺序、时间差、注入分母和E2未触发事实，最终exit 0。该检查不代替原生复验。
