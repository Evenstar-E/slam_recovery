# 6e2b87c增量复核：错误结论已撤回，失败ICP候选克隆实现缺陷已修

面向用户与S1/S2/S3开发侧。2026-11-17 10:26（UTC+8）fetch固定 `origin/main=6e2b87c16383d2c6351543089cdcc78eab5fc244`。本提交包含源码修正与文档撤回，无新宿主run。

## 1. 复核结论

**接受实现级修正和两处撤回；accepted原生修复没有新增，A/B不按测试数量提升。**

- 文档已明确撤回“0.5m重入是唯一绑定约束”和“与真实运动结构互斥”，并改为当前实现/协议下未获得accepted，和审阅意见一致。
- v9i E1被正确记录为重入时间包络通过，实际还失败信息增益和holdout；v9j两事件也明确为重入通过、Wilson与holdout失败。
- v9i只作为另一序列的限定paired-benefit证据，不再被包装成accepted或地图净收益。

## 2. 失败ICP语义修正核对

`NativeClosedLoop._icp_candidate`现在仅在状态属于 `CONVERGED / ITERATION_LIMIT` 时生成候选；其它失败状态：

```text
poses = {}
_last_icp_delta = None
candidate_suppressed = true
frames_candidate = 0
```

因此`TOO_FEW_INLIERS / TOO_FEW_CORRESPONDENCES / LOST_CORRESPONDENCES / REFERENCE_TOO_SMALL`等失败不会再通过`delta @ inits`克隆成candidate=incumbent。该改动直接覆盖v9j E1缺陷路径，且不改变冻结门、ICP常数或宿主二进制。

新增回归固定了`REFERENCE_TOO_SMALL`时空候选和`candidate_suppressed=true`；它与v9j的状态不同，但走同一个新增失败分支。**接受源码级关闭，不要求为此扩异常矩阵。**

开发侧报告测试291→292全绿属于其实验记录。本机两次检查均确认当前Python没有`pytest`，因此**未独立执行该回归，也未安装依赖**；不把开发测试数当成本机实测或原生accepted证据。

## 3. 尚未关闭的主线边界

- 本提交没有新宿主run，修复后的失败语义尚未在真实FAST-LIO run中复验；
- v9j及此前负结果保留，不把历史candidate=incumbent改写成有效候选；
- 没有新的accepted测量修复、native update/map、完整输入归宿或自动检测；
- ALI-H真实M/I、独立校准/标签仍缺，继续NOT_EVALUABLE；
- option③仍是当前实现/协议下停止并收口，不是科学不可达或恢复成功。

局部实现缺陷关闭可记为工程保障，A4/A6/A9/B2/B11未因此完整闭合，不做全表新评分。

## 4. 下一单一主线

仍按option③完成**诚实、可核的回滚＋重启生命周期收口包**，不再开新run：

1. 保留撤回后的全门腿与v9i/v9j限定口径；
2. 保留E1合法cp、E2晚cp、unresolved segment和负结果；
3. 若未来用户重新授权候选方法复验，再使用本次失败语义修正，不通过降门制造accepted。
