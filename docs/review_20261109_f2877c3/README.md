# M1/M2 增量验收 f2877c3

范围ea527d4..f2877c3，3笔、11文件，约11k新增行（大部分JSON）；重点审run_fixed_input_repair_c0c3.py 814行、C0–C3报告/来源、完整记录过滤与地图评价，另读ns归因增量。独立读代码与报告两路复核。本机41/41主测试PASS、冻结/共同支持集合检查、局部平面100m反例实测。未在本机运行ROS/真实bag，也未声称归档host重跑已独立复现。

## 总结

接受真实过滤导出与OFFLINE_NATIVE_REESTIMATION方向的实质推进，不再把它仅当单NIS诊断。C3归档从raw→filtered bag→FAST-LIVO2 output→重建点云的链已经出现。但“达到oracle ceiling”“真实建图恢复闭环完成”尚不通过：评价是clean-proxy条件一致性，运行来源未完整冻结，C3缺44/446帧，未与只隔离做同区域净正确几何比较。

## 通过与进展

- builder :769-780 按point_step原字节记录rows[keep]选择，保留顺序/time/ring/padding/header与bag t；其他topic raw消息透传。比XYZ-only修复输入正确。
- 分帧过滤不看oracle时间窗/clean输入；归档598帧，200帧主要剥离、398帧不剥离、189/200 repairable=false；原生宿主重跑不等于门控可观测性通过，已应区分。
- 固定ns集合446/252/132和raw missing20，对照公共402帧并列44个C3缺pose；不隐藏缺失总数。
- 四控制明确oracle与离线重估标签，healthy-prefix对齐，不调用全程GT拟合来制造地图收益。

## P1（评价主张）：无界点面分数不等于地图表面准确度

:129-142 对全clean参考取8NN拟合无限平面，all tail不限制邻域半径/平面质量。实测当前函数（AST提取原逻辑，暴力NN替代KD查询）：参考是原点附近0.2m平面patch，query=(100,0,0)，返回plane residual=0，nearest reference distance=99.9m。远处切向错位可表现成零误差。

well子集带radius<.30/RMS<.02，是条件支持质量，不独立验证远处表面；“well tail>.5=0”尤其是经过近距离筛选的结果。不能称“真实表面”，hall_01 proxy也非GT。要求同时报受限NN距离/局部有界patch距离、unsupported比例，冻结区域并对错误平移/转角做反例。保留点面一致性作为辅助；不要删除现有数据，但撤回仅凭该tail宣布oracle ceiling。

## P2：对照时间配对不一致

:451-453 C1/C2用最近clean key但无最大间隔/插值/缺测；C3 :487-490用50ms nearest，而C0有20ms nearest/75ms插值。相同402 key不保证相同pose timestamp误差。固定同一配对协议，参考无合格pose记缺测；报告实际dt和姿态插值。C3 44帧missing单列正确，但公共402结果条件于C3存活，另报整个冻结446上的服务完整度，不叫全总体成功。

## P2：运行记录在measure时生成，不是实跑时消费链

:277-337 host revision/config/binary hash在measure时读取，命令/端口隔离方式是硬编码。实际runner /tmp/fl_run_isolated.sh未提交也未hash。该记录是审计快照，不证明先前host加载同一配置并消费指定filtered bag。下一次运行把runner入库，启动前记录输入/配置/binary/hash和ROS参数，结束记录输出hash/进程退出与消息覆盖；结果链接原run receipt。现记录不判伪造，只未完成可复跑来源链。

## P2：过滤数量与schema错误

:600-606及:661-664先用各自独立15k/range裁剪的数组长度差作removed_points/fraction；:730-736只修窗内fraction，旧C3仍显示removed_points1,504,773/fraction.24955。全分辨率filter report是8,974,676/30,173,449=.297436（全bag总体不同，不能直接替换cohort分母）。按原点ID/记录计数为各cohort分别汇总，不相减独立抽样长度。

此外/tmp/filtered_bag_report.json缺失但C3bag存在时_meta.real_filter未定义，:734无条件索引会KeyError；checked-in report不是自动fallback。应显式缺证据并终止成功报告或使用hash匹配sidecar。

## 完整点记录仍缺original point identity

过滤byte rows保留好，但未导出keep-index/mask，sidecar仅t三位小数和计数。重复记录下不能独立恢复原point ID。M2应保存exact scan ns+original row index清单/mask hash，绑定源bag与输出，至少对零删除、字段/time/header不变做回归。

## 非阻断/范围限定

- well_constrained_query_fraction所有臂.94045来自固定reference query，是不同量；真正arm point well fraction为.369/.643/.936/.908。不是数值计算bug，但必须名字/分母清楚。
- 轨迹支撑只查24NN排除own-frame，可能漏更远但在半径内的other-frame点；missing pose排除所以zero gap不是446全覆盖。
- 恢复map是由截取每帧250点重建的sidecar，不是host emitted map。先称离线重建链可行，再接native map接口。
- C1/C2与评分proxy同源，C3虽不借oracle运行，clean proxy仍不构成真值；coverage来自clean随机40k query并与同源控制相关。
- unfiltered重跑窗内translation .028m有用，但未比较rotation/最终map且窗后.488m，不宣布host完整确定性。

## 里程碑判定与下一步

M0：冻结集合已核；M1：诊断有实质结果但地图准确度主张需修评价；M2：归档原生重估链进展可接受，执行来源/原点身份/正确地图评分未完；M3：只隔离净收益和验证准入未完成。

优先一次性补：runner+runtime receipt、统一pose配对、bounded geometry评分与错误候选回归、完整点mask计数。不要为每个文字又重跑全部算法；先用已有输出重算独立评价，确有运行身份缺口再做一条短smoke+正式冻结运行。没有新增学习模型必要性证据，暂不扩宿主。
