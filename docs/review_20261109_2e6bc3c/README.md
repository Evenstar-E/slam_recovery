# 主线/旁支验收 2e6bc3c：room_02独立确认阻塞

范围5bc4530..2e6bc3c，一笔、6文件（大部分逐帧JSON）。完整读331行确认脚本、blocked结果、两run receipt与runner配置覆盖diff；本机Python AST/shell语法通过，JSON身份/状态核对。未本机ROS/bag实跑，未独立确认来源比较探针。

## 主线：有过滤/native运行推进，独立效果仍BLOCKED

新filtered receipt status OK、sources unchanged，790odom约57.98s；filtered bag/hash与输出记录一致。clean候选试跑使用noimg配置且单列，不混称same-config确认结果。BLOCKED结果未含伪造arms/地图数，接受不补指标的处理。

此次不是无改善有效实验轮次，也不抹掉hall_01条件proxy收益。独立确认尚不能通过；主线下一步必须解除输入来源而非继续改评价或新增模型。

## 最小解除与证据范围

零header stamp交集证明当前exact join不成立，不自动证明两文件一定来自不同物理采集（仍需检查header时间重写、原始/转换布局与裁窗）。逐点差0.67–0.94m也不能单凭索引比较不同扫描就断定物理不同；点顺序/采样、相邻帧运动和deskew都影响它。当前合理结论是“对应clean输入身份尚未验证”，不是已穷尽所有来源。

优先追查现有room02_inj43转换sidecar/历史运行生成命令和source hash，按原始源重新导出clean同窗口、图像/IMU一致记录；若源确实缺失，拿已验证完整原始数据重新生成一对clean/injected，并作为新协议版本先冻结输入，不能悄悄替换旧确认。可复用工具与已运行输出，输入改变则相应native运行重做，旧run留记录不计新协议结果。

## 旁支（非另起循环）

run_room02_confirmation.py目前不直接生成BLOCKED JSON：所有输入先_sha_file，零common导致no diff后SystemExit称“not injected”；checked-in详细blocked来源诊断没有对应保存的比较脚本/机器输出。下次预检集中实现明确MISSING/NO_COMMON_STAMPS/UNVERIFIED_SOURCE状态并归档比较命令、header范围/字段与hash。不要为补这段文字单独跑全host。

健康区读取固定/tmp/filtered_bag_report.json尚无身份绑定，易吃到hall_01/旧run sidecar；独立确认可执行前使用房间专属sidecar+input/outputhash/exact ns。原始primary只写count/hash，raw→pose失败列表未全导出；后续预注册总体和missing保留。上述代码路径现BLOCKED未输出效果，不宣称当前结果因此错误。

## 分工与自检

主线数据/实验角色恢复source身份并生成可验证clean/injected配对，然后执行预注册同帧确认；若无法获取源明确BLOCKED及可执行替代版本，不只再提交“来源缺失”措辞。工程旁支完善预检状态、sidecar和receipt链接，不扩多宿主。先§10.12自检PASS/FAIL/BLOCKED/NA附命令/证据，报告actual新run与未测效果。

同源clean proxy仍非独立GT；noimg候选只能用于来源诊断，不能悄悄改变已冻结host配置来报成功。今晚日报记离线过滤与重估已执行、独立确认被来源阻塞，创新泛化未证明。
