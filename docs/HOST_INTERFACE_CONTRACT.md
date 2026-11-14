# 宿主接口契约（能力声明 + 语义 + 冒烟 + 资源预算）

本文件是"能力契约前置"的落地：driver 不再假设某个宿主的实现，而是要求 host 在
`<checkpoint-dir>/capabilities.json` 里声明它能做什么、这些命令意味着什么；缺声明即拒绝，不猜。

## 1. capabilities.json 结构

```json
{
  "commands": {"snapshot": "YES|NO|PARTIAL", "restore": "...", "hold": "...",
                "reprocess": "...", "set_state": "...", "measurement_relay": "..."},
  "checkpoint": {"eskf_state": true, "eskf_cov": true, "ikdtree_points": true,
                  "time_cursor": true},
  "checkpoint_excludes": ["imu_preintegration_cache", "deskew_cache"],
  "partial_notes": {"reprocess": "buffer replay; repaired clouds substituted by header stamp"},
  "semantics": {
    "apply_stamp": "YES|NO",              // hold/snapshot 可否带未来时间戳排队
    "ack_levels": ["deferred", "applied"],// deferred=已入队，applied=已执行
    "checkpoint_validity": "until_re_slam|run", // re_slam 后 cp 失效
    "publish_gating": "isPublish|always", // 休眠期间是否停发 /Odometry
    "native_reset_under_hold": "deferred|immediate", // driver 持有 map 时 host 是否仍 re_slam
    "profile": "native_recovery|legacy"
  },
  "hold_scope": "map_writes+native_reset",
  "checkpoint_invalidated_by": "re_slam (host-native reset); a new snapshot is required afterwards",
  "snapshot_refused_after_host_reset": "until the host publishes odometry again"
}
```

规则：
- **只有字面 `YES` 视为支持**；`PARTIAL` 必须带 `partial_notes` 说明限制；缺失/损坏 = `UNDECLARED`（不当作支持）。
- `semantics.apply_stamp=NO` 时 driver **不得**预武装边界命令，只能立即下发，并在 run 里记
  `arming_mode=NOT_SUPPORTED_IMMEDIATE_ONLY`（checkpoint 可能晚于声明边界，不能称合法边界）。
- `semantics.ack_levels` 必须含 `applied`；client 收到 `deferred` 只记 armed、保持 pending，超时记 `deferred_not_applied`。
- `checkpoint_validity=until_re_slam`：host 在 `re_slam` 后必须使 cp 失效并拒绝 restore（具名原因）。
- `publish_gating=isPublish`：driver 订阅 `Issleeping/Isbuilding`，休眠/重建时释放 hold、不 restore/reprocess；
  休眠期不以普通 STALE 判据误杀（用 `--host-hibernation-max-sec`）。
- `native_reset_under_hold` 必须为 `deferred`，否则 `--require-contract` 启动前拒绝。语义是**对称共存**：
  driver 不持有 map 时，host 的原生 `Issleeping`/`re_slam` 优先（driver 放弃该段，记 takeover）；
  driver 持有 map 时，host 仍可观察并上报退化（照常发 `Issleeping`、照常置 `isPublish=false`），
  但**不得**执行 `re_slam`——否则会清空 driver 即将回放的 checkpoint，两边互相破坏。
  host 在 `status` 里以 `deferred_resets=N` 记录被推迟的重置次数；driver `resume` 后原生策略立即恢复，
  若届时仍退化，host 按自己的规则重新计数并在两帧后 `re_slam`（不改变原生阈值）。

## 2. driver 侧拒绝（不猜）

| 情况 | 行为 |
|---|---|
| `--require-contract` 且无 capabilities.json | 启动前退出码 2，不跑 bag |
| `--require-contract` 且 `contract_problems()` 非空 | 退出码 2，日志列出缺项 |
| `native_reset_under_hold` 缺失或非 `deferred` | 同上：启动前退出码 2 |
| accepted 但 `reprocess` 非 usable | 不发 reprocess、不发布修复云，记 `reprocess_unsupported` |
| refused 但 `restore` 非 YES | 不发 restore，记 `restore_unsupported` |
| `set_state` 非 YES | 不发写回，记 `set_state_unsupported` |
| `apply_stamp=NO` | 跳过预武装，记 `arming_mode=NOT_SUPPORTED_IMMEDIATE_ONLY` |

## 3. 每宿主先做有界接口冒烟（再谈整链）

顺序固定、每步保存 ack：
1. `status` + `capabilities`（确认声明与文件一致）；
2. `hold` → `map_writes=held`；
3. `snapshot`（已知帧）→ `applied` 带真实 `stamp/frame`，`map_points>0`；
4. `restore` → **同 stamp/frame**；
5. relay 发布一帧修复云 → `repair_received` 增长；`reprocess` → `repaired_fed/repaired_in_update`；
6. 宿主休眠/重建信号 → driver 释放 hold、记 `host_native` 事件；
7. 收尾 `final_state=HEALTHY`、`quarantine_open_at_exit=false`。

FAST-LIO 的 ctrl2（120 s）与 A/B（260 s×2）是本协议的实例；未过冒烟的宿主不得进入整链。

## 4. 资源成本（诊断项，不是门槛）

`python3 -I slam_recovery/tools/bench_frame_cost.py --rate 10`

- **定位：诊断，不阻塞。** 用户 2026-11-13 决定：优先把整链跑通，不以硬件算力预算卡正常流程；
  该测量只作为每次 run 的成本记录，默认 `status=REPORT_ONLY`、退出码 0。
- 只有显式给出 `--max-core-fraction` 时才作为可选的硬门槛（用于以后需要封顶时）。
- 背景数据（保留作判读依据，不作放行条件）：FIM ≈ 63–82 ms、NIS ≈ 11–12 ms，合计约 0.6–0.9 核 @10 Hz；
  v5b（~1 核）时宿主首次休眠 66 s，v6（~0.5–1 核）时 105–111 s，无 driver 基线 115.8 s。成本会影响宿主时序，
  但不能因此停住主线；需要时再降载。

## 5. 以宿主原生机制为主

- 用 host 的 `re_slam`/`Issleeping`/`Isbuilding` 作为恢复信号，不模拟 FAST-LIVO2 的 `replay_buffer_`/八叉树；
- `reprocess=PARTIAL` 只称"有限原生缓冲重放"，不称完整恢复；
- 不在 host 不支持时用 driver 侧补丁"假装"具备该能力（如伪造 replay 语义、伪造完整 cp）。
