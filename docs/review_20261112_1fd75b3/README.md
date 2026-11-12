# 1fd75b3增量：trace负结果与尾段限制，真实扫描关联仍未成立

面向：开发S1/S2/S3与独立复核者。固定目标 `1fd75b3c061995011a85cec31cb0309255493787`，比较已验 `aaf7e284974877c9196ebd68a94e1c075e3cee93`；2026-11-12 19:45:53 UTC+8 fetch。AGENTS/A-B标准/REVIEW§10未变复用，四Cron仍repair-f3单owner、无旧owner双写；忽略stop.md/noCodex/旧参数停，私人handoff保护，现SSH，不算法/ROS/历史/冻结门。跳过78de840/8676ad7旧审阅与纯merge。

## 1. 本轮仅新增开发运行回报，尚无可获取的原生原件

实际增量COLLAB§130–131；`git diff --name-only aaf7e28 1fd75b3 -- slam_recovery docs/ali_h_v1_research docs/review_20261112_four_host`为空，Git树无112254Z/112753Z/113855Z、trace_cov或probe新档。以下保 **DEVELOPER_REPORTED**，本机未读取这些真实run原件/运行宿主，也不称远端没有运行。

| 开发回报 | 必须保留的范围 |
|---|---|
| 同库3b26365f的off112254Z与on112753Z，各544paired/1接纳1拒绝 | off实际修23/replay244+439；on修0/丢23/spans0/replay0+151。即使wiring OK和门决定相同，也不证明原生行为不变或完成修复 |
| 缓冲写入on113855Z，换库49f2f941、driver a4aaa58b | 报修23/丢0/replay244+400，说明一个新尝试恢复部分行为；新库与旧off不同，不能拼成同build不变性通过 |
| phase异常、重复grp_idx/abs_ns | 不能按现phase选择校准/replay区间或按出现序号直接证明原扫描身份 |
| 尾段记录位置范数末519.9m，终HEALTHY | 没有GT/注册ATE，不将位置范数称真实轨迹误差；开发已明确不能用于连续接回正常，接受这个负结果边界，不据replay局部读数掩盖尾段 |
| 无同run availability、原件未入Git | T2实际join/真实I资格未验，不能用旧402/544贴入；新同49f2f941的availability off/on为开发安排非本机代跑/追加矩阵授权 |

**主线结果尚无新增可独立验收的推进**；新负回报增加研究认识与执行依赖，不把它删掉，也不按日志数量计恢复成功。上一轮研究三修正/关联声明资格继续有效，无源码变化不重跑构造控制或946帧。

## 2. 正常路径的最小解除

### 2.1 关联：grp_idx＋出现序号仅是trace行位置，不是source scan身份

报告322个grp_idx各两次且同abs_ns，只证明日志存在重复组记录，不能单独识别原生首次处理/重放/追平，也不能证明它与availability指向同一条原始扫描。当前phase又不可用，S3不能直接把第一次/第二次定义成live/replay作校准或效果人口。原生已有一组多scan的能力，组序号不是扫描序号。

最低S1/S2/S3沿本次导出实际source scan成员关系和现checkpoint/reprocess事件绑定身份与执行阶段；组到扫描允许真实多对一，重复同戳不静默删、保NO_TRACE/NO_AVAILABILITY与未知phase。若目前仅有grp_idx/出现序号，写**行身份可定位、原扫描/执行phase对应未解**，先交资格/UNKNOWN，不nearest猜关联、不新通用时间框架。日志已有可核关系时先复用，不为补文档多跑一轮。

### 2.2 因果：缓冲修正后改善是候选机制，不证明逐行flush是唯一根因

old off/on同build回报支持trace开关相关的行为差异候选，但差异还包括E1使用的实际cp/捕获span及随机线程分组。buffered run改变库且实际E1 checkpoint恢复为早cp，未控制相同cp/span之前不能唯一归因std::endl，也不能排除宿主运行不稳定。最低先当前三run原件对照实际cp应用戳/事件顺序、capture范围、source scan membership、repair匹配/drop及phase；后继已安排的同build off/on完整交付再评价开关影响，不另外增加参数/宿主矩阵或追逐每次相同数量。成功与失败run都保留。

### 2.3 尾段：replay段并非完整评价人口

受注入首段不是GT正常真值、可单列污染阶段；但若需评价正常代价/持续服务，不可只保replay的较好片段。E2 restore后十几秒才出现大位置记录变化，先核现日志输入时间/坐标/状态、事件与缓存/后继归宿，不从相对时间推定restore是唯一根因。最终HEALTHY/ACK/点数不作独立健康证明。开发已把该run限trace/修复/replay组件接受；完整接回持续运行与效果仍UNKNOWN/未通过，不硬将“正常”写入标签。

## 3. 阻塞、分工与唯一下一交付

**下一单一交付：同一已选库、同输入/配置、带availability及实际scan-group-phase关系的有效真实I trace与完整资格/UNKNOWN人口结果；正常校准与事件标签可用后恢复完整风险评价，有证据再有限自动接线。**

- S2按现有限安排完成真实导出并上传已有三次run/布局patch/probe原件、receipt和SHA；不为审阅重跑已完成旧off，不用系统盘替远端实验存储，不安装/删资产/换宿主扩授权。
- S3不采用未经证实的grp_idx出现序号作物理身份/phase；复用已验研究组件，逐项报NORMAL_CALIBRATION/EVALUATION_LABELS缺项与新trace时间人口，UNKNOWN时长含空窗，不重算旧全UNKNOWN。
- S1共享集成、实际cp/捕获/拒绝input归宿与成功依赖仍负责；现buffered run不能关完整持续运行项。元数据ACK时间收口和上传可并行，只有已证破坏当前关联/执行/评价的最小对应先做。
- S4自动审阅/2h/日报/截止保持，不代算法/host/noCodex。记录因果和上传不是新主要研究任务，下一直接交数据/实际行为。

ALI-B2正常参照/标签文件与用户确认状态本增量未变；尚未收到实际用户确认，不代选A/B/C，亦不重复新阻塞ID。只停被无独立参照/标签阻塞的效果评价，未受阻工作继续。原声明注入仅离线评价已授权，新来源/超预算或降级范围待用户决定；确认来源须用户真实commit/原文，不从S1“approved”推授权。若当前原生/信息依赖已证现范围确不能继续且需新决定，立即追加中文重大阻塞，不等截止。

本轮自检最小要求：PASS/FAIL/BLOCKED/NOT_APPLICABLE、实际命令/输出原件/影响/下一动作；同build/source/input/config、actual cp应用与capture、修复应用/丢弃、live/replay/尾段与全部未配对/未知phase、正常校准/事件标签/UNKNOWN时长、失败与资源成本。原生trace开关行为变化列FAIL/未知，不能以门接纳数相同或wiring all_ok替代；未实施/未运行/不能评价分别保NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE。

A2/A6/A10有新开发尝试回报未原件验收，A1/A11关联仍缺实际关系，A3/B3真实性能未验证；A4/A5/A8/A9/B2/B4/B11完整项未闭合，局部不重评分全表。中文增量仅新负结果/关联及因果限制，现review SSH白名单发布，private/开发日报不动、不合main/历史/算法/科学门。
