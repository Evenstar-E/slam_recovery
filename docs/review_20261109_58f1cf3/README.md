# M1/M2增量验收 58f1cf3

范围3876ec7..58f1cf3，两笔、9文件。主审有界评价、统一pose_lookup、过滤计数和213行runner；大JSON仅核协议/关键记录，不声称逐bag重跑。41/41主测试PASS、两shell bash -n PASS；AST提取当前bounded_metrics+local_plane_residual，用受控暴力NN验证旧100m反例现在nn/patch unsupported=1。未运行真实ROS/清理脚本。

## 通过与实际进展

- 无界plane仅保留辅助，有界NN/邻域质量拒绝远点，旧P1“远点零残差被当正确表面”关闭。supported tails+unsupported同时报，不能只引用tails。
- pose配对统一20ms nearest/75ms插值/缺测，C3缺46/446，公共400帧。旧402数不混用。
- 全分辨率过滤审计取原row mask而非独立抽样长度差；同源clean proxy与sidecar重建地图限制仍保留。
- runner新增独立目录、trap、参数dump与收据；历史C3记RETROSPECTIVE_PARTIAL，未伪装成新receipt执行。
- 归档patch unsupported C2 .0593 vs C3 .0931支持当前proxy/共同帧下接近而非达到上限；不是独立GT效果或M3净收益。

## P2：runner输出验证只影响收据，不影响shell退出码

fl_run_isolated.sh:208-213只检查文件非空就STATUS=OK/exit0；真正消息数量/可解析性在write_receipt :86-110中计算，可能写FAIL但on_exit :143仍返回原0。非空坏bag或零odometry文件会“shell成功/receipt失败”，违反明确失败契约。write_receipt失败也不影响原退出状态。

将有效输出判据作为运行成功条件，receipt写入失败同样非零；允许诊断partial但不标成功。host在drain期间退出未再次检查，recorder非零也未阻止OK。记录进程正常停止/计划终止与意外失败区别。

## P2：清理测试只打印、不assert

test_fl_run_cleanup.sh打印runner rc并打印端口/receipt状态，无rc==3断言，端口仍开放也不会非零，receipt缺失只echo FAIL。该脚本最终rm成功可返回0。必须assert失败码、端口关闭、receipt.status=FAIL且所有受管PID退出，否则不能叫通过回归。

trap只有EXIT，缺显式INT/TERM处理；不要以注释“default still fire”当跨启动方式保证。roscore子进程树也需确认，仅父PID kill不证明其所有子节点清理。实际cleanup回归应保留run与pid检查。

## P2：hash仍在退出时采集

write_receipt :111-120哈希输入/config/binary/script并读revision是在结束时，不是启动前快照；前后文件变化会把执行配置与结束磁盘身份混用。启动前记录身份、实际加载ROS params、执行路径，结束保存输出hash并核查源是否变化。smoke证明新工具有用，但不能补齐旧C3执行缺项。

## 非阻断过滤审计来源补强

filter_audit :425-434逐序next输出，只比row sha/count不比exact header ns和layout，也未检查输出额外frames；bytes相同但header改动可绑定PASS。按ns join核对record字段/时间与额外/缺失帧。当前归档598/598绑定不据此宣布发生错配。mask身份新工具保留，和旧C3输出区别明确。

## 下一步

评价缺陷已修，停止围绕旧无界数值追解释；先把runner负例变成真正失败断言与启动收据，原输出可继续有界重算，不因日志重跑全部host。M2历史来源限制和46缺帧保留；M3补只隔离同区域净正确几何，独立reference不可得则proxy声明到底，不宣称部署闭环。
