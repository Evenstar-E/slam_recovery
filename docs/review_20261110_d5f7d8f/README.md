# d5f7d8f：进程内对照负结果保留，重放保真度仍待同版本原件

2026-11-10，固定main`d5f7d8f81a0aa8522d943649301aecd4fb636e82`，比较930563d。真正增量为538afa4控制重放诊断脚本/报告及日报撤回结论，无新公开宿主patch、Python准入/写回源码未变。已读协议/评分和历史入口，核本会话Cron及旧owner无进程；私人handoff保护。仅静态核、归档算术与原分类表达式的单个合成时间边界控制，未跑ROS/原bag/修复算法、未调门或启动新模型。

## 主线变化：有新的开发负观察，不是闭环完成

报告同实例、同checkpoint、426个group/相同区间先control再treatment，12条替换、8条未匹配；这是较前轮更有区分力的接口探索。保留所有失败、承认归因未闭合，接受撤回“repair_effect_measured PASS”的审慎方向，不抹去实际探索。

本机核报告算术：x差14.231m，voxels差6565，points差46369。数值来自开发报告，actual新版`reprocess_control`/缓存保留/替换源码、host log/ack、matched stamp及完整source/input/config/binary receipt仍未交；host diff与930保持完全相同，sha256仍`f5efce7160e45933f84b23c365f08b9a51798aeb9c201c4e48a5ba026e2c2f21`。旧diff不识别control命令，不能独立确认两次原生输入/状态等价，不能把脚本退出0算PASS。

## 1. 撤回效果PASS正确，但不能从旧运行量级判本次重放失真

日报把control x−12.644与“前几轮live x7.2/3.45附近”比较，随后称control没复现live。这些是其他版本/运行/时间支持，正是此前不应混用的对象；目前没有本实例本次重放末stamp的live终态。**重放保真度UNKNOWN/BLOCKED，不能写已证明FAIL或从此定位二次积分/restore遗漏根因。**它们可以作为待检查假设，不是实测根因。

z+1m产生x14m不要求线性响应；非线性估计和几何退化可耦合，单看轴/量级不证明重放故障，也不证明纯注入破坏效应。README仍写“替换路径到估计器可测/14m破坏效应”，与main撤回范围不一致，应统一为控制/处理终态差、效应归因未证。

最低沿已保存同一次运行补出**同末stamp**的live（restore前）、control、treatment与checkpoint/buffer身份。若同版无修复control确已偏离live，再沿现恢复/重放入口查一个具体断点；不预先修所有假设缓存、不强求随机过程逐值一致、不新起大重复矩阵。若原件无法取到直接BLOCKED；受控接口实验仍可按预算收尾，不把旁支全部完备变两事件永久前置。

## 2. 新脚本分类的是发布全集，尚非8条未匹配帧归宿

脚本heredoc读取`inj_stamp.txt`的**全部20发布戳**，按最后snapshot cp和最后replay hi分类，没有读matched/applied/drop逐戳清单。结果可支持“发布戳相对checkpoint/重放末端的范围”，不能单由这份JSON推出“8条未匹配都属于某细类”。需先绑定同次control/treatment原件，区分received/applied/未匹配人口，沿已有20条精确戳分类，不新增宽匹配窗。

另：变量lo记录却不用于inside，inside条件是cp≤stamp≤hi，不是lo≤stamp≤hi。若cp到首个重放group之间存在正常时间空隙，位于空隙的修复也标inside_replay_window；它可叫checkpoint后的时间范围，但不能宣称实际有组可替换。最低改标签/按已有group成员戳记归属；无组/组已消费/过滤原因留UNKNOWN，不能用时间范围代替实际匹配。cp缺失时结果亦须说明UNKNOWN，不假定全部inside。

本机执行`python -B docs/review_20261110_d5f7d8f/run_checks.py`退出0：从目标git blob只提取原分类表达式，设cp=10s、重放[12,14]s、发布[9,11,13,15]s，脚本inside=[11,13]s，确把首帧前空隙11s标inside；cp缺失时inside=[9,11,13]s。这是正常时间边界的**合成诊断反例**，不是本次8条未匹配的真实原因。结果见[local_checks.json](local_checks.json)，语法核`bash -n slam_recovery/ros/smoke_repair.sh`退出0，未执行整个shell。

merged计数定义可接受为开发解释：累计每组成员总数与multi>1次数零不矛盾；actual source/count原件未交，累计反例语义收口即可，不升级为每个修复成员身份证明。若同一次运行累计范围确实覆盖目标窗，multi=0可排除其中多成员组；目前缺该范围/原件绑定，不从计数名称单独推断。

## 下一唯一主线与最低保障

S1/S2仍交**实际修复测量→原生状态重估/内部地图写回→同时间线接回→第二事件**。S2随下一实质交付提交已运行新版host patch/已有完整log/receipt与同stamp三终态，先判本次control是否复现live，不拿旧实例比较；按已有匹配戳细分8缺测，不猜。S1复用930写回旧pose/deferred尾/失败继续set_state与f2命令归属等最低正常修，本轮source没变不重跑。这些是当前实际入口问题，不扩通用框架。S3专用门研究独立、参数继续停、生产门不改，不挡主线。

自检：PASS_LOCAL为bash -n及报告算术、版本范围；BLOCKED为actual宿主部署/同stamp重放保真度/匹配归属/独立效应/完整接回E2；源码分类标签与效应解释需最小纠正，不虚构实际运行失败；NOT_APPLICABLE为ROS/原bag/129全suite/旧回归/完整A/B重评分。A6/A10工程实验有开发负结果报告，A4/A8/B2/B4/B11仍未闭合，不提升完整总分。首次真实整链完成仍单独汇报。

发布仍受此前携带`rm -rf OUT`开发脚本的push权限限制：此轮只本地提交，没有再试push、换工具或请求peer代推；远端review仍3965299。实际开发改新空目录/拒绝覆盖旧证据或用户明确相关权限前，不称已送达。本机未执行诊断脚本/删除旧产物。
