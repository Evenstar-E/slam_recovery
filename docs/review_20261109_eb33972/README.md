# 主线/旁支验收 eb33972：2×2输入构造阶段

范围dc714e9..eb33972，7笔、21文件（约8.8k行，多数JSON）。完整读163行builder、199行index audit、210行verifier，规则/测试/清单关键项；本机17/17 single-factor规则测试PASS、20 oracle规则测试OK含2 expected failures（不是20全通过）。另AST提取真实verifier、mock短消息流复现尾部漏验。无真实bag/host重跑，不修改算法。

## 主线推进：机制实验输入已具备，未获机制运行结果

接受O/O+F/O−B/O+F−B的index-level构造方向：窗外复制actual filtered，窗内四格数量1186220/1187485/1162613/1163878与归档expected一致，组合格actual bytes校验记录599帧（199内、400外）零失败。两次/格与ATE1m判据明确。FNR生产字段正确分母已落实，健康注入分母无值记null。

但这轮只有输入构造及保障，无四格native状态结果。下一主线直接运行四格至少两次，保留sameprefix/config/outside policy和启动收据，报告全部服务总体与公共支持，按预注册协议检验O是否正常/组合是否稳定复现/单因素是否失败。若组合不复现旧actual，不自动判interaction或某单因素无效。

## 旁支P2：frames_complete漏多余尾部（已复现）

verifier :104-108以filtered流结束作为全部结束，不检查injected/各arm iterator是否还剩消息。实际当前源码mock：参考2帧（1内1外），四臂各3帧、额外300ns扫描；main返回0且frames_complete=True。最低修复：检查各流同时EOF/多余消息并写typed failure，补无bag负例。当前归档599 counts不据此判包错误；修复应随下一运行输入check集中提交，不触发全host重跑。

其余保障集中：前置side/Bag打开发生try外，失败仍可无receipt；元数据inside未比较_dense与原step/layout，非scan IMU/image字节未由verifier检查（builder透传，来源可串旧audit）。sidecar缺某window frame时被解释outside，而窗口从side.files定义，须独立ns window+sidecar身份门禁。来源JSON已有hash但builder未主动校验加载NPZ与source hash对应，run前绑定。它们影响未来输入保障，当前未证明已触发。

## original index的证据边界

有序值子序列在重复row下可有多个合法映射；greedy earliest不是数学唯一原index，背景multiset匹配也不等于同位置clean identity。已知injector保持row order，优先按same-index clean差异/真实exported keep-index，重复值计数必须保留。现归档match无异常，不由此推翻1265/23607全部计数；实验对小数量行敏感，最终2x2应精确绑定生成mask而非仅存在有序映射。

## 分工与自检

主线角色运行四格重复并回传状态/地图效果；旁支角色在相同交付中加EOF、preflight、metadata与index来源负例。真实input validity需先解除，日志措辞和额外审计不等全部做完才启动。按§10.12先自检PASS/FAIL/BLOCKED/NA+命令/证据，不把expectedFailure计通过，不把建包计因果已证。当前mainline阶段完成“输入准备”，不是恢复模型新收益。

大JSON本机只核关键schema/总数/来源标签，未检查外部8个run或全部bytes。今晚日报记2x2准备与尚未运行，独立GT/在线部署/泛化仍开放。
