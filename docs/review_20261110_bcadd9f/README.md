# bcadd9f：首段时间包络局部修正，另一条准入检查仍拒绝同一运动

2026-11-10。目标 `bcadd9f6a03846589ef5a3ae73309c977f6d97c4`，基线0bdd1f4；一笔开发提交，仅driver、transaction node及相关测试，无新原生运行。已读AGENTS、评分标准、REVIEW§10与最新历史，核本会话三自动任务/旧owner不运行；忽略stop.md，保护私人handoff，不改算法/阈值、不代跑宿主。

**主线交付未增加，必要评价旁支部分推进。**接受首个committed run的包络现在使用anchor自身时间，而不是两候选帧时间。不能据此关闭全部边界时间问题；原生内部恢复/重处理/地图写回以及真实Mode3续处理/重武装/E2未改。

## 实际核验

源码新增 `boundary_jump_within_envelope(jump, elapsed, bound)`，仍为既有 `.5 + 2m/s * elapsed` 速度包络，node继续标BOUND_ONLY。driver传入旧trusted anchor的timestamp。本机复用三个开发helper控制：1.2506m/2.329s通过，1.2506m/0s、7m/2.329s拒绝，均PASS。不把包络内位移称已证实正常运动，也不称独立几何连续性。

开发明确承认原候选信息量4.63低于tau_info25，不能靠本fix承诺Mode2，接受此范围。提交/注释仍有“任何移动平台永远拒绝”等过强概括，沿[上一版本的限定](../review_20261110_0bdd1f4/README.md)，不为措辞单独重跑。

### 正常集成反例：同一距离被另一检查再次按固定0.5m拒绝

- node `evaluate_and_commit_candidate()` 的首段检查已使用 `reentry_anchor_ts_ns`，但 `_measure_paired_evidence()` 仍将候选首帧与旧anchor直接相减；`core.py:521` 对该 `reentry_pos_jump_m` 再以固定 `max_reentry_jump_m=.5` 判FAILED。
- 本机[boundary_integration_probe.py](boundary_integration_probe.py)直接调用真实node，默认冻结阈值，复用既有400点fixture，连续匀速运动且各body scan变换后为同一world cloud；没有mock support/FIM/holdout/paired/gate。直接trigger仅控制事件入口，不作在线检测证据。
- 连续0.3m/s，anchor→首帧2.328956843s：raw jump=.698687m，**segment_boundary_ok=true、paired approved=true，却仍evidence_status=FAILED**，reason为paired-benefit FAILED，MODE3。
- 0.1m/s控制：raw=.232896m，同样boundary_ok/paired通过，evidence_status=PASSED。两例cov约.513614仍高于默认.5，因此均不接纳；该控制只定位重复raw-distance拒绝，**不声称完整gate正控制或修完必Mode2**。A7旧正则范围不因此重新立项。

运行：

```sh
python -B -W ignore docs/review_20261110_bcadd9f/boundary_integration_probe.py
```

退出0表示反例复现与控制符合预期，不是生产fix完成。source SHA绑定目标core/node/fim，实际模块路径已打印；结果见[local_checks.json](local_checks.json)。

## 最低解除及下一唯一主线

**只统一已存在的两处时间/边界定义。**首段包络与传给core的reentry评价必须用一致的物理量/时间支持；不能一处BOUND_ONLY放行、另一处把经过时间的运动叫瞬时跳变。沿已有反例加对应调用适配即可，不提高0.5、不删core检查、不把原1.25m直接改成0或默认paired全通过；包络不等独立运动证据。有限研究能力边界如实声明，不为此引入新估计器/防御框架。

- **主线S1集成/S2宿主：**继续实际checkpoint/测量重处理/内部状态地图写回，加真实Mode3续候选/有限终态/重武装，交一次恢复→接回→第二事件或第一具体宿主接口断点。已有订阅/ICP组件/已验收A5/A9直接复用；边界旁支不串行阻塞接口准备。
- **最小保障S3/由S1指定接口写入责任：**贯通当前边界时间定义；A7固定基正则沿旧scope并行。不改info25等门、不继续σ扫描。
- **Codex/KITTI/四策略：**独立集成验证和后继准备，不挡原生接线；实际checkout/编辑/运行/最新意见接收仍未直接确认。

当前首要阻塞仍工程接口/生命周期，边界评价是数学/评价次要依赖；没有新参数规律或不可恢复信息证据，不猜参数/算法是首因。此次不升完整A7/A10/B11，也不重算完整A/B总分。

## 自检与交接要求

PASS：固定源码身份、三个helper控制、真实node两速度集成反例、probe语法/结果归档。FAIL：较大连续运动仍触发另一raw-distance evidence拒绝。BLOCKED：新driver pytest suite缺既有pytest环境，本机不装、不伪造、不重复已知导入失败；开发的fake node会清quarantine，不能证明真实Mode3再武装。NOT_APPLICABLE：新ROS运行、原68/ICP13全套重跑、完整评分。

开发随下一实际交付给PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令、source/host/input/config、全部人口与证据路径。此处是同一已给问题的未贯通范围，不另扩永久检查清单或“收到意见”周期；下一仍回用户优先的实际恢复/接回/E2。
