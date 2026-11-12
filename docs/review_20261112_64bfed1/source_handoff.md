# 64bfed1新接线局部核验

目标 `64bfed115f7d2058bbfe076caf103491036560c1`，比较 `2f1f59bfdab1203a7ef6eb3eb2e72eb345a7b8cb`。本文件只记录源码/本机小控制，不冒充本次宿主原件结论；完整本轮结论见随后README。

[控制脚本](run_checks.py)、[实际结果](local_checks.json)：`C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_64bfed1/run_checks.py` exit0。目标Git源码内存加载，其他package无目标差异；未跑ROS/host/bag、未装依赖、未改算法。新frame_freeze/repair_sync test modules因导入pytest辅助未执行，复用小actual-target controls；未改cloud helper/11旧测试不重复。

运行器语法：PowerShell调用PATH的bash实际为WSL入口、未安装发行版，exit1未执行检查；未安装WSL，改用现有Git Bash工具执行`git show 64bfed1:slam_recovery/ros/run_native_loop.sh | bash -n` exit0。仅语法检查，不运行宿主脚本。

## 已局部解除

- 非零baseline25、本次25条发布，10/10/5批按35/45/50等待，final50才sync，header顺序和减bias字节保持；actual publisher/gate，估计和receipt模拟。旧“全部都直接期待N”在有效baseline路径局部解除。
- 第二批receipt失败时停在20条、不发后5、gate不放行；不等native公开/恢复失败链验收。
- `_track_episode`在deadline crossing冻结21帧，后24帧不再加候选；首次pending wall不被覆盖。相同输入stamp两实例一致。只支持此候选入口，不等原生host replay区间冻结或完整pending归宿已核。

## 新baseline fallback正常反例

`recovery_node.py:1454–1456`读baseline超时/返回None，`base=int(baseline or 0)`继续发。E1旧host cumulative25、E2当前收到0，本次发25条时等待10/20/25均可被旧计数满足，final25等于错误base+published，于是synced=true/gate_proceed=true。本机actual publisher/gate用模拟status返回与延迟新云确认；**不是声称四个归档运行已发生此错配**。code-review low提出该候选，本机复核后确认。

最低解除：None仍UNKNOWN，不默认为0；先取得成功的本次baseline，再沿现批次增量及scan身份等待。只复用现status，不新RPC/防御框架。E2累计计数不因新批次功能默认全通过。

## 与后继实际修复的边界

`evaluate_and_commit_candidate`仍先处理旧损坏scan和pose（:1551），随后才估计/发布新修复云（:1608）；:1625写candidate尾，不是修复云原生重估状态。前轮物理不一致与成功依赖反例source未修，本轮不机械重测。sham/一致时序对照最多帮助区分传输成本，不能自动证明旧候选适用于新测量或set_state与native state/map同逻辑时刻。

若后继做sham，先声明固定source/input/scan人口/checkpoint与实际重放时间支持；只有实际支持一致才能作效应归因，不要求随机轨迹/门值逐数一致。生效与成本/差异的真实结果按原件决定，未知UNKNOWN。冻结候选人口不能自动冻结host缓冲到命令执行时刻，也不能把“同计数”当同stamp。
