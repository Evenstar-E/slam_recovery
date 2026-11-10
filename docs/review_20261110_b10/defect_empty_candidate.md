# 缺陷记录：空候选被报成"位姿非法"（2026-11-10）

## 现象

hall01 确认运行 `054753Z_3075620`（`--candidate-source icp_reregistration`）：

- `_icp_candidate` 返回**空位姿集**，原因是 `REFERENCE_TOO_SMALL`（`reference_points_used = 0`）：
  触发发生在运行早期，可信图里还没有参考点；
- `evaluate_and_commit_candidate` 收到 `repaired_poses = {}`；
- gate 给出的拒绝理由是：

```
Refused Mode 2 atomic commit: Rejected candidate due to non-finite (NaN/Inf) state/bias
or invalid SE(3) pose shape
```

## 为什么这是一个缺陷

**这个理由指向了错误的层。** "位姿 shape 非法"描述的是一份**存在但畸形**的候选；
而实际情况是**候选根本没被造出来**——参考点为空，ICP 没有可对齐的对象。

两者的运维含义完全不同：

| 情况 | 该做的动作 |
|---|---|
| 位姿畸形 | 检查候选生成/变换链 |
| 参考为空 | 等可信图长起来，或者不要让检测在参考就绪前启动 |

按现在的文案，排查者会去查位姿构造，而真正的原因（触发太早、参考还没建立）不会出现在
gate 的理由里，只出现在 `icp_detail.jsonl` 的 `status` 字段——那是个旁路文件，不是门的一部分。

## 触发条件

不是 hall01 特有。任何"候选构造在造出位姿之前就失败"的路径都会走到这里：

- `REFERENCE_TOO_SMALL`、`NO_FRAMES`、`SCAN_TOO_SMALL`、`NO_VALID_NORMALS`、`BUDGET_EXHAUSTED`
  全部返回空位姿集（`BUDGET_EXHAUSTED` 只影响未处理的帧，不会整体为空，除非预算在第一帧前就用尽）；
- `host_poses` 路径不会出现（那条路径总是有位姿），所以这个缺陷只在 `icp_reregistration` 上暴露。

## 同一个缺陷的第二个面：`info_after = 0.0000`

空候选取平均得到零矩阵，于是 `weak_dir_info_after = 0`，比值 `0.000`。
**这个 0 不是"信息很低"，是"没有候选"。** 现在的记录无法把两者区分开——
`paired_benefit_status = MISSING` 是唯一的暗示。

## 建议（未实施，等裁决）

1. gate 的拒绝理由应区分"候选为空"与"候选畸形"：空候选直接报
   "no candidate was produced"，并带上构造侧的状态（`REFERENCE_TOO_SMALL` 等）；
2. 记录侧应让 `weak_dir_info_after` 在空候选时为 `null` 而不是 `0.0`，与"测出来是零"分开。

## 现状

- 未修改 gate、未修改记录格式（B10 期间不动判据）；
- 两趟 hall01 的 `icp_detail.jsonl` 与 receipt 已归档在
  `native_loop_hall01_{host,icp}_*`；
- 本记录只是把"真实原因在哪一层"写清楚，供后续统一修。
