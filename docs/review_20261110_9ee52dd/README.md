# 9ee52dd：替换段episode局部解除，旧rearm仍会释放新隔离

2026-11-10，固定main `9ee52dde35af9a2ba020c54b74b09a3ba7756c95`，比较1b8a449。新增第三次wait2负运行报告、466f1a3 episode身份检查、cbf6600 runner记账修复；无actual新版宿主patch/raw运行原件。先读AGENTS、A/B标准、REVIEW第十部分，复用历史；4既有Cron未复制、peer无repair-3e，私人handoff保护。本机不修生产算法、不跑ROS/原bag、不调参。

## 主线变化与证据边界

开发run `fl_native_20261110T110042Z_3345912`报告wall104.0s、wait2；两个段在bag+2.8/+9.5s打开并关闭/rearm，均早于已知注入+14.6s。报告rearm后2.198s支持恢复/63 AVAILABLE/node_map113，但第三段+15.9s没有episode，370帧UNAVAILABLE，真实E2仍未处理。接受新增负运行与具体断点，支持恢复较此前有局部变化；不把两个提前报警段叫两个真实故障恢复，不把2秒称独立已验证最佳预算。缺自然退化标签时“提前报警”与“健康段假警报率”分开，wait2结果不授权后续手调扫描。实际修复→原生写回→接回→E2仍未完成，host_poses仍非算法修复。

## 1. episode身份比较接受，但不修复旧decision与释放顺序

新`after is not None and after is not before`确覆盖同调用替换段。复用已发表stale-decision正常控制，通过actual loop并供应固定NIS10/独立支持，目标source已绑定：旧WAIT两次高NIS积累后2s到期，reset/rearm再消费旧QUARANTINED decision；新segment产生且episode1，本机局部PASS。manager仍QUARANTINED而detector HEALTHY/dwell0，旧fresh-decision缺陷未解除，不重开新状态机。

同一控制加**模拟宿主命令记录器**：on_pair开新episode→`cp.hold()`；紧接正常service→`_apply_lifecycle()`消费旧rearm→`cp.resume()`，命令顺序[hold,resume]，新active quarantine仍存在、模拟host不再held。**FAIL_REPRODUCED_LOCAL**，不是原生地图污染实测，也不是仅由文件ack竞态猜测：即使模拟ack全部正确，该释放顺序仍错。独立成立于合法同帧替换，不可只补episode便宣布隔离安全。

最低S1沿既有生命周期接线，使旧段rearm不能释放已经打开的当前隔离段（按当前active归属/状态消费事件），保持新段hold；同时复用旧fresh-decision最小修，reset后不继续消费旧决定。无需RPC/事件总线重构。解除条件：替换段仍有episode和后续决策，但旧rearm不释放新隔离；未开新段时正常resume仍可达。旧unresolved provisional晋升、ack命令归属与accepted旧pose/partial/失败顺序source未改，沿已发任务修、不再重复全测试。

开发新增测试在首个`if __name__ == '__main__': unittest.main()`之后，直接执行该文件不会发现后面的新class；新测试还在方法内import含pytest的模块，本机未安装pytest，不假称执行了开发新测试或131全suite。本机按现真实node/loop构造独立控制，4项不依pytest的lifecycle测试PASS（0.043s）。最低把唯一main guard置末、复用可导入夹具；属测试入口收尾，不为条数扩矩阵、不阻挡真实运行。

## 2. runner两项记账修复局部接受，FAIL结果不得升格

runtime_pgid.txt原本在真实host载入library时记录；新增wiring优先用这份存活期记录，避免退出后getpgid=None。本机从目标heredoc提取变化片段，以saved12345/deadhost模拟核选出12345，PASS_LOCAL。这里只证明共同进程组接线，不证明宿主状态恢复。write_receipt末尾exit0现在表示JSON写成功，JSON里的FAIL仍保留，on_exit仍检查整体STATUS!=OK并退出非零；静态/AST核PASS。正常文件写失败仍抛错，不会被这一exit0吞掉。旧receipt保留FAIL方向接受，不要求洗成OK。

`bash -n slam_recovery/ros/run_native_loop.sh`退出0，仅语法，未执行runner/删除/宿主。actual新receipt/raw运行原件未交，不称已独立复现身份或完整流程。

## 下一唯一交付与自检

S1先最低修fresh-decision与旧rearm释放新段，维持旧正常帧/命令/写回归属任务；S2在原900s预算、wait2不再扫描的固定配置下交实际修复测量驱动原生重估/内部地图写回→接回→E2或第一具体断点。若先host_poses编排运行，如实单列为控制，不能提前宣称恢复成功；不为单NIS反复调门。S3研究独立、旧参数暂停、生产门不改。actual host patch/已有run_summary/receipt/log及stamp归属随下一实质交付归档；命名/测试guard集中旁支，不制造收到规则循环。

自检命令：`python -B -W ignore docs/review_20261110_9ee52dd/run_checks.py` exit0，PASS_LOCAL为4测试、replacement episode、runner表达式；FAIL_LOCAL为同帧旧decision和[hold,resume]释放新段；BLOCKED为actual修后原生隔离/E2/真实修复链；NOT_APPLICABLE为ROS/原bag/开发131全suite/调参/完整A/B重评分。脚本exit0表示各预期观察已核，不表示产品无缺陷。开发下次按PASS/FAIL/BLOCKED/NOT_APPLICABLE附命令/原件，分别给episode/新旧段释放/真实事件/修复来源/E2及尾段，不用131或段数代成功。

A9/A10编排局部推进，A8/B2仍具体隔离风险；B4/B11未闭合，不提升完整总分。首次真正完整原生链完成仍单独报告，目前未到。前push携带rm-rf OUT被拒未解除，记录只本地提交，不重试/换工具/peer代推；remote review仍3965299，未提交或公开私人handoff。
