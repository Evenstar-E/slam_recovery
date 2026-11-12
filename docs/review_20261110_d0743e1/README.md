# d0743e1：修复测量注入受控交付，完整链仍未完成

2026-11-10，main固定`d0743e13b05c2535673de79739f0e3db1a0a9bd5`，比较e2db4b3。新增98f1e28注入工具/诊断脚本/报告及d074日报归档；跳过merge/旧审阅。必读协议、评分和既有Cron归属已核，旧owner无进程；私人文件保护。本机不改算法/门、不跑ROS/原bag，不新起调参/模型矩阵。

## 1. 主线增量如实接受，不能升级为算法修复或两事件

新增`inject_repaired_scan.py`将已知scan作z平移并保持header后送repair topic、`smoke_repair.sh`直接调用checkpoint/reprocess；明确CONTROLLED_INTERFACE_TEST。作为接口探针有价值，不是实际过滤/算法修复，不是检测成绩；人工变换不证明修复有益。开发报告20条发布、10条替换、10条未匹配，426重放group、地图/state变化，保留部分命中和失败，不要求制造全部成功。

本机known-layout helper字节控制PASS：项目既有24-byte x/y/z/intensity/time/ring布局，只改z的8–11字节、其余20字节及header保持。不扩通用PointCloud2兼容矩阵；输入整点身份可复用旧布局工具。AST与bash -n通过，不是ROS/宿主执行证明。

## 2. 实际宿主部署与运行原件仍未归档

本提交仍仅README/旧host diff/.cpp/.h，没有repair subscriber/`applyRepairedScan`/hold实际新版patch，没有原ack/log/result、完整binary/config receipt。host diff与e2/adff完全相同，sha256仍`f5efce7160e45933f84b23c365f08b9a51798aeb9c201c4e48a5ba026e2c2f21`，其中reprocess没有applyRepairedScan。Python recovery_node也未变，不解析新counter，只能保存原ack字符串；不能从文字称run_summary结构化匹配计数已经验收。

因此10/20及426group和宿主map/state读数是**开发实测报告，未独立核原件**；不否认实际做了实验，也不判其造假。最低随下一实质交付保存已有实际worktree diff、inject stamps/完整ack/log/result与source/input/config/binary绑定即可，沿历史重复提出的同一原件任务，不要求重跑矩阵。126测试是开发报告，不是本机复跑、不证明注入运行。

## 3. 匹配与时间边界：不由周期推绝无串帧

反推begin约9ms误差/20ms匹配窗/100ms周期是报告；实际合并组/原始成员戳缺失时，周期不证明身份无歧义。main已给最小改法：保留真实raw header作为键、记录组成员与匹配/替换/未匹配归属，方向合理，接受为待做最低解除，不再另设计匹配框架。10未匹配原因UNKNOWN，不能自动归因LIVO合并；实际运行LIO/LIVO配置也须原receipt支持。即使将来组包含多scan，修复单scan应替换对应成员而非整组合并云丢掉其余健康测量。

injector按启动wall time选40…44s，不按消息时间；只有准确rate与启动偏差关系才近似bag20…22s。脚本默认duration26/rate.5播放52wall秒，发送reprocess前固定sleep24+28也52秒，且另有ack成本，通常接近/超过播放结束。报告重放到bag27.7s不匹配脚本默认26s，可能实际DUR不同，**证据不足不猜**。最低提供实际命令/消息戳与receipt，不看默认值改写历史窗口。

这直接复用旧包尾无group不poll控制正常问题：当前已发布host patch仍如此，新部署可能修但未交，不能宣称该点闭合。脚本只看任意非空ack、未传播FAIL/NO_ACK，打印式诊断退出码不算PASS；沿已有ack人工自检即可，不要求新自动验收框架。

## 4. 不删除已有失败数据；归因不由同进程自动成立

新smoke脚本启动`rm -rf "$OUT"`：再次使用默认/tmp/repair_smoke会清掉前次host/inject/odom原件，违反保留失败和在手产物要求。最低要求OUT新空运行目录或拒绝既有目录，不自动清旧数据；本机没有执行脚本或删除任何远端文件。这是正常重复实验的数据保护，不是恶意参数防御。

开发提出同实例/同checkpoint/同buffer先无修复后修复重放，是更合适的局部对照方向，避免不同实例初始状态混入。但两轨迹之差不自动“即修复效应”：旧宿主MP多线程/重复重放、未恢复可变量仍可能造成差异。沿已有记录确认两次输入/快照等价、公开有不确定性；复用现无修复重放观察量级，不要求逐位同值/新大重复矩阵。证据不足就UNKNOWN，不新增fallback/生产完整性框架。

## 5. 下一唯一主线及A/B范围

S1最低集成仍为已发命令single in-flight/匹配ack、trustedstamp与实际评分子集归档、完整成功释放/partial保持隔离；source本轮未变，不重跑旧控制。S2先随当前运行保存actual hold+repair patch与已有原件，按真实header成员归属完成修复测量替换；让**实际修复测量支配宿主原生重估与内部map/state**并证明接回后新帧继续建图/E2。不把ICP姿态直接灌_state代替原生重估，不把受控shift称算法修复。CONTROLLED_INTERFACE_TEST可以先核机制，最终自动链仍待交；失败按原budget保存、具体接口断点报回，不无限绑定宿主。

S3门研究独立按旧最低纠正并行，参数任务继续停、生产门不改，不让新阈值/研究先全部完成再接线。本机只核字节/源码和归档，未代跑host、未开新算法；完整流程首次真正完成单独汇报，不等日报。

本轮A6测量注入方向有受控开发报告、工具实现增量；A4/A7/A8/A9/A10完整验收与B4/B11仍未闭合，不给最新完整总分。PASS_LOCAL为helper/AST/bash语法；BLOCKED为实际新版host/source/run身份、20帧完整匹配归属、真实修复写回/接回/E2与独立效果；FAIL源码为正常重复目录覆盖旧证据；NOT_APPLICABLE为ROS/原bag/126全suite/调参/完整A/B重评分。主要工程接线/执行证据，算法效果及10未匹配归因UNKNOWN。

下一实质交付仍给PASS/FAIL/BLOCKED/NOT_APPLICABLE、实际命令和同source/host/input/config、完整人口/尾段/失败/成本，不以测试数或累计接口条数代替运行。复现本机控制：`python -B -W ignore docs/review_20261110_d0743e1/run_checks.py`，退出0只表示known-layout字节和部署范围核验。
