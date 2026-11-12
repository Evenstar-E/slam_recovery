# 26ba3a3增量核验：独立参考工具可测试，未新增恢复或根因证据

读者：用户、开发S1/S2/S3与独立复核者。目标 `26ba3a3f907c4ff6f29a32feb8e3540a7bd31de8`，比较已验 `5f54a449650e203a1c1d3bba29486a8476fb53ae`。2026-11-12 16:37 UTC+8 fetch恢复成功；必读AGENTS、PROJECT_HISTORY相关最新阶段、评分表和REVIEW§10已读，未变内容复用。三自动任务actual owner repair-f3、无旧owner双写，用户忽略stop.md优先；review分支/private未提交handoff保护，不合main不改算法。

## 1. 最新增量：研究旁支组件，不是新原生结果

新增independent_reference.py与相关tests，读PCD并对旧availability保存body样本按T_wb投影后做同1m/60%支持；可选ICP重配。S1§103报告独立参考已派S2一次无注入clean-map pass，target没有新PCD/receipt/评分运行结果，当前只是DEVELOPER_REPORTED分派，实际完成UNKNOWN。不把215tests或工具标题当定位根因/改善自动检测。

“用户选独立参考诊断”仅仓库转述，本会话没有该项直接选择证据，不据它扩大实验授权；用户最新直接授权为ALI-H v1隔离测试（b7ad580已SSH推送），新目标早于该发布，不指控开发忽略。S1应确认并保持S3单研究、S1/S2 native分工，不把S2整轮改成另一诊断矩阵；如远端另有真实用户授权，按实际范围/预算交付并声明。本机不代跑clean地图/算法。

## 2. 两个正常评价问题，最低改解释与分母，不重跑宿主

[实际小控制](run_checks.py)/[结果](local_checks.json)加载全部target package Git bytes，5相关unittest PASS1.225s；Scipy未安装，ICP测试NOT_RUN，不安装/shim，不冒全部6项通过。

1. **同位姿只换参考就翻支持，不能归因位姿错误。** 保存body点与T不变，对远参考fraction0，对覆盖该扫描的参考fraction1；summarise却解释“pose placement is the likely failure”。事实只支持“新参考与同pose扫描更一致”，旧地图缺覆盖/对齐差都可解释，不能排除参考原因。producer doc“separates those two cases”过强。最低中性命名host-reference-low/new-reference-pass，原因UNKNOWN；只有另有独立位姿/覆盖证据才进一步归因。ICP在同一参考上优化再测支持是拟合后的相容性，不是独立质量证据，更不能把本次拟合分数当未经拟合的判决。

2. **裁20/200样本仍进入全帧主联合统计。** 正常边界/AVAILABLE旧数据只保前20点，score_rows虽flag trimmed，summarise仍将其independent_pass作为主表frame分类。具体200点首20近参考、后180远：保存子样本fraction1，真实全200fraction.1；summary仍both_pass1。最低主表只用完整原抽样分母，裁样本另列partial_sample/NOT_EVALUABLE与缺项，不能静默把20当200。无需重跑完整宿主；已有全样本UNAVAILABLE先核，少数完整正常边界随下一已授权产物补。

独立run地图有自己的world gauge和消费/ROI/可见范围。当前score_rows直接使用原run T对新图比距；实际用前必须复用现有健康前缀单SE(3)/时间外参协议并冻结变换及共同支持，不能只因同bag就认world同。可选每帧ICP不能替代这种公平对齐。target尚未交跨run评分，不宣称真实已错评；这里是已核接口的使用限制，不要求新估计器/通用框架。

code-review low另指出ASCII字段COUNT展开解析边界；当前目标宿主声明binary标量XYZ，未有该输入实际使用证据，集中兼容旁支，不升主线阻断、不扩格式矩阵。

## 3. 14:37–16:37两小时判断与当前单一交付

**结论：部分推进，有真实原生执行证据，完整科学恢复未完成。** 这两小时从e82d900的124组重放/后缀被清到v4全捕获后缀原生重推，再到v5成功suffix不再灌旧candidate末pose，随后同实例实际23修复云应用→接回→E2拒绝→尾段；最终080914Z保39paired/4.65064s尾段。详见已发布[5f54原生核验](../review_20261112_5f54a44_native/README.md)，不重审/复制新总分。

- 首工程断点：final cp虽早E2 trigger67.8ms，仍晚quarantine_start3.932198216s，触发前武装不等隔离起点前可信状态。最低绑定实际恢复历史与所声明隔离起点/保后继input归宿，或显式拒绝不支持回溯。不调margin或再移E2戳追HEALTHY。旧collect失败/未知仍写set_state的70控制未修，保现反例/成功依赖，不重复测旧范围。
- 算法/评价依赖：candidate旧坏云准入与新测量/真实native重估物理一致仍未闭合；59shift只23修、36未修及未解人口保留；独立净收益UNKNOWN。UNAVAILABLE直接分支已定位，参考覆盖/位姿/历史原因未分离；ALI-H设计及独立参考工具不是已解决自动检测，观测证据不能冒正常真值。
- 参数：没有同版本同人口的参数变化规律/效益代价与改善上限证据证明调参能解除上述缺口；旧sigma/κ/floor继续暂停，不盲调门。工程时间边界问题不靠调参数掩盖。
- 次要环境：宿主目标库已built/有运行hash声明，整体vikit ABI测试构建失败保留但不是本轮native主阻塞；本机DNS现已恢复，不能把暂时fetch失败猜作远端停工。

S1共享接口/成功依赖集成，S2真实host/合法cp与input追赶，责任由既有交付可确认；本轮最低修复的新直接认领/实际运行仍待回执。S3保持唯一方法研究，ALI-H v1接收与执行尚无可核main回报，不能写已开始。下一唯一native交付：**合法可信隔离边界检查点→物理一致修复/完整原生state-map重估→完整接回/后继事件尾段，或明确不支持范围**；复用已验buffer/suffix/skip，不扩防御/阈值/单测。

自检要求随下一实交：PASS/FAIL/BLOCKED/NOT_APPLICABLE+命令/原件/source-input-library、cp实际边界、全部修复/未修/后缀/未配对人口、native失败UNKNOWN依赖、E2/尾段、独立质量/成本与缺项；未做NOT_IMPLEMENTED/NOT_EXECUTED。A2/A6/A10两小时局部推进，A4/A8/A9/B2/B4/B11等未闭合；新独立参考工具只A3/B3/A11支持组件，不新全表评分。只提交本轮实质评价增量，既有两小时成果不另造重复报告；SSH review推送、不合main/改历史/生产算法/private。

命令：`C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_26ba3a3/run_checks.py` exit0。无ROS/bag/远端宿主/新调参/归档脚本执行。
