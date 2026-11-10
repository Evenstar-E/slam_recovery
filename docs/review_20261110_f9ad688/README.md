# f9ad688：重复边界拒绝解除，停止重开这一局部问题

2026-11-10。目标 `f9ad688b42cca607a35b766634b0e7a5a3a5f9f9`，基线bcadd9f。一笔开发增量，core/node/正常路径测试，无新原生运行。已读AGENTS、评分标准、REVIEW§10及最新项目历史，核本会话三自动任务与旧owner未运行；忽略stop.md，保护私人handoff。不改算法/阈值、不代跑宿主。

**接受局部修正：上一轮较大连续运动通过segment包络、却再次被raw-distance证据拒绝的问题已解除。**这是必要评价旁支完成一个限定范围，不是原生恢复、接回或第二事件完成。

## 1. 本机实际验证

新CandidateMap保存 `reentry_elapsed_s`；node用旧anchor→候选首帧时间差填充；core的reentry evidence采用与segment一致的 `.5 + 2m/s * elapsed` 包络。未提供时间或elapsed=0仍保留固定.5。已有GateThresholds数字未改，但从裸距离改为时间包络是评价定义修正；它仍是**BOUND_ONLY**，不能将包络内位移包装为独立连续性/安全证明。

- 新3项ReentryEvidenceLegTest、既有commit evidence coverage与A7契约/transport相关回归：本机 **35/35 PASS，1.322s，0FAIL/ERROR**。不是pytest，未安装或伪造环境。
- 复用[上一轮真实node集成fixture](../review_20261110_bcadd9f/boundary_integration_probe.py)，不改旧档案；只在内存更新目标SHA和预期FAILED→PASSED。固定目标core/node/fim身份核过，打印目标module路径。
- 连续0.3m/s、2.329s：raw jump .698687m，boundary_ok=true、paired approved=true、**evidence_status现在PASSED**；0.1m/s控制同样PASSED。之前重复拒绝范围关闭，不再开新边界测试框架。
- 两例info_after约62.983，但cov .513614仍高于默认.5，均保持Mode3/accepted=false。因此这是边界证据正控制，不是完整准入正例；35项相关测试通过也不解除旧实际producer world正则问题。原真实候选info4.628<tau_info25限制仍成立，开发已明确承认，不承诺修后通关。

复用命令：

```sh
python -B -W ignore docs/review_20261110_f9ad688/run_checks.py
```

本轮实际运行的是同等inline命令，随后保存[复用runner](run_checks.py)，并做文件语法/JSON检查；不是声称又重跑第二遍35tests。详细读数见[local_checks.json](local_checks.json)。原ICP13/全核心不机械重跑，已知driver pytest缺环境不重复失败。

## 2. 主线与旁支交接：不再停留在边界修正

**原生恢复交付本轮未增加。**driver仍缓存host pose作候选，未接真实测量重处理/宿主内部状态地图恢复写回；真实Mode3决定后仍锁定episode，尚无续候选/终态/重武装。最新可核实际run仍为0接纳、E2零、最终WAITING；这是0bdd运行归档，不是本版本重跑的结果。

- **主线S1集成/S2宿主执行：**复用已接受接线/manager/ICP组件，现在交一次实际checkpoint→测量重处理/状态地图写回→准入或真实拒绝→接回输入→E2。若缺接口，给第一具体宿主文件/函数断点和最小实现。勿继续仅改边界注释、σ、字段或测试数量。
- **可并行最小数学依赖S3：**旧实际node固定基正则问题沿既有反例处理，不重写正确transport，不扩大门/epsilon；已解除的重复raw-distance范围直接复用。此依赖不串行阻塞宿主接口准备。
- **Codex/KITTI/四策略旁支：**沿现有工具独立核新集成，后继准备不挡这一次原生运行。远端当前checkout/未提交清单/运行中任务/本轮意见接收仍需直接回报，不从commit推正在执行。

主阻塞仍工程接口/生命周期实施，必要评价依赖部分解除；没有新参数上限或不可恢复信息证据，不臆测参数/算法首因。继续用户要求的单一完整交付，不为局部PASS升完整A7/A10/B11或重算全表。

## 3. 自检与下一验收

PASS：目标源码身份、35相关unittest、复用两速度node集成/三helper控制、runner语法/结果JSON。BLOCKED：已知pytest环境，新宿主接口/E2仍未交。NOT_APPLICABLE：本机ROS、ICP重跑、全核心和完整A/B评分。

开发下一实际交付按REVIEW§10.12给PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令、source/host/input/config、完整帧人口/缺失和原证据路径；拒绝/失败保留、不调门制造Mode2。不要单独交“收到”“已修边界”文档周期；下一实质证据应是原生恢复/持续运行或具体接口解除。
