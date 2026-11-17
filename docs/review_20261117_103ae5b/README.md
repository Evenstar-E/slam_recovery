# 103ae5b增量审阅：option③收口包成立，仿真与accepted仍均为否定结果

面向用户与S1/S2/S3开发侧。2026-11-17 12:13（UTC+8）fetch固定 `origin/main=103ae5bf6ac77d82bbe9cade640a2e8c58e32b6e`。本机只读归档文档和重生成manifest，未重跑宿主、仿真或论文构建。

## 1. 总结判定

**收口材料与负结果整理有推进，accepted原生修复没有新增。**

`FASTLIO2_OPTION3_CLOSURE_PACKAGE_20261117.md`符合审阅要求的收口形态：保留E1合法checkpoint、restore/rearm/resume、E2晚cp和unresolved，明确零重放、失败候选语义修复及“当前实现/协议下未获得accepted”，不再声称一般不可达。

`FOUR_HOST_AB_PROGRESS_20261117.md`按宿主和A/B行整理证据状态，明确`P`不表示通过、不是新评分。其它宿主的新任务属于开发建议，不视为本机授权或已执行。

## 2. 仿真重生成与论文边界

`ba2942d`重生成manifest的五个gate案例全部`MODE3_SOFT_BRIDGE_WAIT`：

| 案例 | holdout NIS | 结果 |
|---|---:|---|
| R4 Dual-Blind | 133.686 | MODE3 |
| B5 Narrow-FoV | 17.856 | MODE3 |
| R5 Delayed Revisit | **10.38** | MODE3 |
| B6 Point Mixture | 14.629 | MODE3 |
| B6 Aux Pose-Graph | 10.38 | MODE3 |

`simulator_validity.status=FAILED`，五个scenario均失败。旧R5 Mode2/1.409被替换为拒绝结果，不能继续引用为成功。该重生成与论文数值统一属于**负结果和撤回事实更新**，不是算法有效性提升。

`street_08`两篇数值已统一为2.85–3.53/1.38；fig3按逐案例阈值重绘。已跟踪PDF未重生成，完整TeX环境构建仍待后续，不能称发布包已最终完成。其它未绑定原始归档的数值仍需逐项核对。

## 3. 验收边界

- **接受**：option③收口结构、全部门腿和负结果保留、四宿主按证据状态而非阶段分整理、仿真全部Mode3与simulator validity FAILED。
- **不接受外溢**：把收口包当accepted、把host-only七步当有内容重放、把仿真撤回当方法有效、把四宿主`P`当验收或启动FAST-LIVO2。
- **本机边界**：未重跑仿真/宿主，未独立目视fig3，未执行完整TeX构建；只核固定文档、JSON字段和版本。
- **未完成**：accepted native update/map、自动检测性能、ALI-H真实标签、独立复现及统一成本。相关项继续NOT_EXECUTED/NOT_EVALUABLE/UNAVAILABLE，不做全表新评分。

## 4. 下一单一主线

当前唯一主线就是完成并冻结这份**回滚＋重启生命周期收口包**，不再开新run：

1. S1保持“当前实现/协议未获accepted”及零重放、E2晚cp、unresolved等限制；
2. S2保留宿主与冒烟原件，不重跑以制造通过；
3. 论文仅保留版本化负结果和离线/原生边界，完整TeX环境和剩余数值另核；
4. 其它宿主按各自最小任务另行取得用户授权，不因表格生成而自动开工；FAST-LIVO2仍不启动。

## 5. 本机复核

```text
C:/Python315/python.exe -I -B docs/review_20261117_103ae5b/review_checks.py
```

[review_checks.json](review_checks.json)固定五案例全Mode3、simulator validity FAILED、无accepted、无一般不可达结论、零重放披露及四宿主非新评分，exit 0。
