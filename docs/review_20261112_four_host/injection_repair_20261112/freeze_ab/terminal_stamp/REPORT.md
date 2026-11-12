# 终止戳 + 开段快照：终止端对齐了，起始端仍随宿主积压漂移（停，报因）

同声明的一对：repair / sham，损坏窗口改为**从触发戳开始**，宿主支持 `reprocess <end_stamp>`，
开段时 `hold` 后立即 `snapshot`。运行前声明见 `../PLAN_terminal_stamp.md`。

## 1. 终止戳按预期工作

| 项 | repair | sham |
|---|---|---|
| `reprocess` 行 | `34 frames replayed over [279.215 .. **280.281185627**]`，replayed=34 truncated=451 | `64 frames replayed over [278.215 .. **280.281185627**]`，replayed=64 truncated=509 |
| 终止戳 | `end_stamp=1627785280281185627` | 同一值 |

**终止戳逐位一致**，`truncated` 计数与非空 payload 都生效；空 payload 的旧行为由单测保留。

## 2. 起始端仍不一致

| 项 | repair | sham |
|---|---|---|
| 冻结 | 同一戳、23 帧 | 同一戳、23 帧 |
| 门 | accepted 7.3076 / Wilson 0.8947 / committed 23 | accepted 7.3052 / Wilson 0.8947 / committed 23 |
| bias / 发布 / synced | +0.40 / 23 / true | +0.40 / 23 / true（shift 0） |
| **开段 snapshot 应用戳** | **279.149**（触发 +2.933 s，frame 252） | **278.149**（触发 +1.934 s，frame 242） |
| 重放窗口起点 | 279.215 | 278.215 |
| 重放帧 / 应用修复 | **34 / 7** | **64 / 12** |
| 重放后地图 | 17322 voxels/324279 | 17283 voxels/325824 |

原因：**开段快照不是触发帧地图**。`hold`/`snapshot` 是命令通道，宿主在它处理到的下一个帧边界
上应用；本机 bag 回放有**积压**，宿主处理到的帧时间比触发戳晚 **1.9–2.9 s**，而且随负载在两次
之间差 **1.0 s**。重放窗口是 [快照应用时刻, 冻结戳]，所以起点跟着漂；候选 23 帧里只有起点之后
的部分进了重放（repair 7 帧、sham 12 帧），`repair_received/applied` 是 23/23，但只有部分能在
重放里被消费。

这也说明本轮"开段立即快照"的改动在积压时**比原来的滚动快照更差**：滚动快照至少在触发之前，
能覆盖全部候选帧；开段快照落在触发之后，反而丢掉了候选的前段。

## 3. 停止与选项（按"不一致就停"，不追加运行）

要让起点也逐帧一致，需要让 checkpoint 的时刻与触发帧解耦于宿主积压。三个选项：

1. **回退开段快照**，保留滚动快照 + 终止戳：起点是触发前的最后一个滚动快照（最多早一个周期
   2 s），两次的相位差最多 2 s；终止端已对齐。简单，但起点仍非严格一致。
2. **在触发前固定 bag 偏移处快照**（例如触发−2 s，由驱动在 pose 流上触发）：命令提前发出，
   积压 <2 s 时可落在确定帧附近；仍受积压影响，但可测。
3. **宿主侧按声明戳 checkpoint**（需要状态历史/回退，改动更大，超出本轮 10–15 行预算）。

## 4. 能/不能声称

- 能声称：终止戳实现正确（两次终止戳逐位一致、截断计数正确、旧行为保留）；冻结人口与门一致。
- 不能声称：两端重放窗口一致；地图差异的归因；任何修复收益。
- 宿主改动仅限终止戳（约 20 行 + 编译）；门/阈值/σ 未动；损坏为自注入。

## 5. 文件

`repair/`、`sham/` 各含：`receipt.json`、`run_summary.json`（含 `frame_freeze` 与
`repair_publish`）、`candidates.jsonl`、`candidates_detail.jsonl`、`icp_detail.jsonl`、
`relay_frames.jsonl`、`host.log`（含 `replayed/truncated/end_stamp`）、`lifecycle_events.json`、
`native_checkpoint_events.json`、`host_control/`、`launch_pair.sh`、`recovery_node.log`、
`machine_load.txt`、`recovery_node_source.sha256`。
宿主改动与构建见 `../../../host_change_terminal_stamp/BUILD.md`。
