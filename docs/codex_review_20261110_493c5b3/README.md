# Codex 局部验收报告：493c5b3（仅供参考）

**本报告来自 Codex。该轮报告供参考，不是对当前 main 的正式验收或方法变更批准。**

- 固定审阅版本：[`493c5b3d056e5050af1a0fe915a1f749b3a81dd8`](https://github.com/Evenstar-E/slam_recovery/commit/493c5b3d056e5050af1a0fe915a1f749b3a81dd8)，2026-11-10 14:07:36，香港时间。
- 发布分支：`codex/review-493c5b3-reference-20261110`，以被审版本为基底；没有修改生产源码、阈值或 main。
- 发布时查到 main 已更新至 [`99e4eb0`](https://github.com/Evenstar-E/slam_recovery/commit/99e4eb03f18faf0f30c9c7c6a0f0438edb3c002a)（18:51:10）。该提交记录了原生回退和双事件状态机缺口；Codex 本轮只读了这次更新的记录，**没有独立验收其实现、测试或运行结果**。
- 因此，正文中“没有宿主恢复接口”等结论仅适用于 `493c5b3`；后续修复须根据新版本另行核验，不能把历史结论直接当成当前缺陷。

## 阅读入口

1. [完整验收报告](REVIEW.md)：通过项、问题、证据边界、A/B 评分项映射与下一主线建议。
2. [原轮独立探针结果](acceptance_results.json)：保留原始字节。
3. [可移植复验入口](acceptance_probes.py)与[原历史正常路径夹具](fixtures/normal_paths_original.py)。
4. [来源与打包变更](PROVENANCE.json)、[发布文件清单](MANIFEST.json)。
5. [打包后的复验结果](packaging_check.json)：仅验证相同小探针在仓库相对路径下仍可运行，不是新原生实验。

## 本轮结论

A5/A9 已测正常事务路径和 A7 坐标不变性修复通过。原生接线与拒绝记录属于实际进展，但完整恢复闭环、独立门控收益及泛化没有通过本轮验收。

主要意见：逐帧各自弱方向信息量的样本最大值，不构成候选在固定触发方向的信息量上界；“三分之二帧数学不可达”的论证不足。检测不可用时的可信准入、目标事件触发、候选独立质量标签和宿主接回仍需按各自证据验收。建议供开发侧参考，不据此直接删除判据或降低科学门。

## 复验范围与命令

原轮环境：Python 3.12.14、NumPy 2.3.5。核心 unittest 的 74 个测试通过，另一个模块因缺 pytest 导入失败；没有宣称完整测试套件通过。

在本分支仓库根目录，使用已有 NumPy 的 Python：

```sh
python -B docs/codex_review_20261110_493c5b3/acceptance_probes.py --output codex_493c5b3_probe_new.json
```

入口会拒绝覆盖既有输出，并检查被测源码与固定版本之间没有已跟踪差异。请使用干净 checkout；这不是抵御任意本地篡改的执行沙箱。没有 ROS/bag/构建/真机实验，不要求安装新依赖。矩阵反例不证明实际候选有益；UNAVAILABLE 探针不代表真实污染率。

打包仅调整路径、输出位置和来源检查，没有修改测试断言或生产算法。历史夹具原样保留，运行时仅适配源码根和新版必需的 identity anchor 参数。

> every auto review needs read and plan to work on main line according to this table

适用的[主线进度标准](../MAINLINE_PROGRESS_STANDARD_20261109.md)保持不变；本包是局部审阅，没有重新计算全部 24 项总分，也不授权恢复自动化或执行实验。
