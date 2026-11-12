# 被截断后缀的重推：重放覆盖到边界，但 `set_state` 把状态又拉回去

同声明受控 run（kf 132 绝对戳、margin 4.0、损坏窗口从触发戳起、声明戳 hold/snapshot、
`--detection off`、`candidate_source=icp_reregistration`）。宿主改动见
`../host_change_suffix_replay/BUILD.md`（增量 67 行，完整 v4 1625 行，新库 `c0833d9f…`）。

## 1. 重放后缀：成立

| 项 | 本次（v4） | 上一轮（v3，截断） |
|---|---|---|
| `reprocess` 行 | **`replayed_within_end=124 replayed_suffix=448`**，总 572 帧 | `replayed=124`，`truncated=399` |
| 重放区间 | **[276.281966925 .. 295.292295218]** | [276.281966925 .. 280.347787857] |
| 修复 | `repairs applied=23`、leftover 0 | 同 |
| 重放后地图 | **21257 voxels / 379069 points** | 17811 / 335054 |
| 重放后 `state_pos` | **3.168, 6.145, −0.111**（边界 295.29 处） | 7.697, 5.721, −0.030（280.35 处） |

后缀 448 组用原始测量按顺序重推，终止戳只限制修复云匹配；修复仍是 23/23，没有后缀组误吃
修复云。**重放的状态与地图确实按序追到了捕获边界**（295.29），比截断版多覆盖 14.94 s。

## 2. 断点：`set_state` 把状态拉回候选末端

| 命令 | `state_pos` | 地图 |
|---|---|---|
| reprocess（重放到 295.29） | 3.168, 6.145, −0.111 | 21257 / 379069 |
| **set_state（写接受候选的最后帧 280.28）** | **7.051, 5.921, −0.447** | 21257 / 379069 |
| resume | 7.318, 6.075, 0.201 | 21257 / 379069 |

`set_state` 用的位姿是冻结候选的最后一帧（280.28），而重放已经推进到 295.29；两者相差约
**3.9 m**、15 s。结果是：重放把 state/map 都带到了实际边界，随后 `set_state` 又把 state 回拨到
15 s 前的候选末端，地图却停在 295.29——**状态与地图不同步**。run 最终仍 HEALTHY，但"接回后
native state 按序追到实际边界"这一条**只在 set_state 之前成立**。

这是本轮改动引入的新冲突：`set_state` 原本是为截断重放设计的（重放停在候选末端，写回同一
位姿）；重放覆盖后缀后，宿主自己的估计已经到达边界，再写旧位姿就是回退。

## 3. 最小修法（未实施，等决定）

1. **后缀 >0 时跳过 `set_state`**：全量重放后宿主状态已由自身估计推进到边界，写回候选末端
   反而制造 3.9 m 的跳变。驱动需要知道后缀是否被重放：宿主可在 reprocess ack 的
   `checkpointStatus()` 里加 `replay_suffix=`（本次日志已有该值），驱动解析后跳过 `set_state`。
   约 10 行宿主 + 10 行驱动 + 单测。
2. 或宿主在 reprocess ack 里直接返回重放末端的位姿（`state_pos` 已经是），驱动用该位姿做
   `set_state`（同值，等于不写）；这需要定义"接受位姿"与"重放末端位姿"的关系，语义更绕。

按任务要求，本轮只做了"验证后缀是否被重推"的一次 run；发现的是 `set_state` 回拨，而不是
修复云边界冲突。门/阈值/σ 未动，检测诊断暂停，未顺手改检测。

## 4. 能/不能声称

- 能声称：后缀组被重推，重放覆盖 [276.282 .. 295.292]，state/map 到达实际边界；修复计数
  23/23、leftover 0。
- 不能声称：接回后 native state 在 set_state 之后仍停在边界——它被回拨到候选末端，状态与地图
  不同步；持续接回未完成。
- 不声称修复收益；损坏为自注入。

## 5. 文件

`receipt.json`、`run_summary.json`、`candidates.jsonl`、`candidates_detail.jsonl`、
`icp_detail.jsonl`、`relay_frames.jsonl`、`host.log`（`replayed_within_end/suffix`、
`NATIVE_REPAIR applied`、各命令 ack 的 `state_pos`）、`lifecycle_events.json`、
`native_checkpoint_events.json`、`host_control/`、`launch_pair.sh`、`recovery_node.log`、
`machine_load.txt`、`recovery_node_source.sha256`。
