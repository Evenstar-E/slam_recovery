# eeda122增量核验：参考地图已保存，静止与320秒归因不成立

面向：开发S1/S2/S3与独立复核者。固定目标 `eeda1224da57fa9d380811f4009cb954615286c7`，比较已验 `26ba3a3f907c4ff6f29a32feb8e3540a7bd31de8`；2026-11-12 17:05 UTC+8 fetch所得。跳过旧审阅合入，不重新验收旧原生run。AGENTS、A/B标准、REVIEW§10已读；实际三Cron owner仍repair-f3，无旧owner双写，未新建自动任务。用户忽略stop.md优先，旧参数任务继续暂停；本机不改算法、不代跑远端宿主、不合main、不公开private handoff。

## 1. 本轮成果与范围

**支持旁支有实际交付，原生恢复主线结果未增加。** 新 `fl_native_20261112T083858Z_263020` 是无注入、无scripted、detection off的地图保存运行，不是新自动恢复或修复后E2。接受保存地图的真实产物及工具收窄，不能据其HEALTHY/wiring all_ok认定地图质量或独立正常标签。

- [隔离归档核验](check_archive.py) / [结果](archive_checks.json)：Git目标原件11/11 SHA一致；归档driver SHA `4742dbc1…` 与目标源码一致，配置副本SHA与receipt一致，库声明为已验v5 `9e7d8cdf…`。没有重读远端bag/库实体，不把hash声明当独立原生状态等价验证。
- binary PCD实际13,493点、216,070 bytes；host原件记录raw 2,498,791点及downsampled 13,493点保存成功。raw仅远端路径/hash，**NOT_READ**。保存后日志末行为 `terminate called without an active exception`：产物已保存与优雅完整退出分开，后者未通过核实。
- 新SAVE_WAIT先SIGINT等保存再TERM/KILL，默认0保旧分支；目标脚本 `git show eeda122:slam_recovery/ros/run_native_loop.sh | bash -n` exit0。仅语法/源码核，不本机执行退出流程或宿主。
- [最小源码控制](run_checks.py) / [结果](local_checks.json)：全部package从目标Git bytes加载，7相关unittest PASS（1.280s）；实际裁20/200样本fraction1而全人口.1现退出主表、列partial；同pose仅换参考仍翻0→1但reading保持cause UNKNOWN；非单位host pose上单SE(3)复合与known-prefix刚体计算PASS。Scipy缺，ICP测试 **NOT_RUN**，不安装/替身、不冒8项全过。

## 2. 必须纠正的实际证据解释，不据错误归因重跑宿主

### 2.1 “位姿全程小于1米、近静止”与同档原件矛盾

目标COLLAB§111写全程 `|p|<1m`、第100帧约零，因此怀疑位姿保存分支。实际749行 `lidar_poses.txt` 的XYZ列：

| 量 | 本机原件复算 |
|---|---:|
| x范围 | 0.002225–8.808419 m |
| y范围 | -0.121540–8.833413 m |
| z范围 | -0.380372–0.288689 m |
| 最大位置范数 | 11.987540 m |
| 范数超过1m | 724/749行 |
| 最大范数行（0-based312） | t=1627785285.078785，p=(8.577013,8.372015,0.212898) |
| 末行 | t=1627785315.523715，p=(1.576706,1.134459,-0.021749) |

这是**同一原件读数冲突**，不是随机运行逐值一致性要求。静止诊断FAIL；不能凭它安排pcd_save位姿分支排查或重做clean pass。PCD的x/y范围约[-64,87]/[-79,55]m也不直接与约12m移动范围冲突：扫描可以看到远处，地图范围不等传感器移动范围。几何一致性与根因仍UNKNOWN，不能反向宣布这张图已经有效。

### 2.2 时间与消费人口要分层，“bag320秒”尚无证据

- 位姿日志支持 `1627785261.403843–1627785315.523715`，跨度 **54.119872s**。末行比既有诊断run最后配对戳 `1627785320.909073830` 早 **5.385359s**；这说明该位姿文件不覆盖那个完整诊断尾部，不自动说明bag只播一部分、native停止点或地图尾部缺失原因。
- 当前recovery收到597 pose/598 scan，paired396，未配对201/202；配对末戳 `1627785305359041929` 又早于宿主位姿文件末行。recovery接收、40ms配对、native消费、PCD贡献是不同人口，396不证明bag只播放前60秒。
- REPORT声明bag59.99s，receipt duration_s=0；COLLAB§111“bag320s”未提供bag start/end原件。绝对epoch戳末尾约320秒不能当持续320秒。当前598scan接收也与旧完整输入run的598相容；仍不能替代实际bag及native消费完整性核。

**最低解除**：先复用当前bag info/start/end、native实际分组/末消费戳及保存时间，声明现有共同支持/缺尾，不重播来修文字。只有这些证据明确指出必要缺测、且现有授权预算允许，才补一次最小缺口；本审阅不新授权clean-map重跑。

### 2.3 报告的评分负结果尚缺可复算原件

S1报告302完整样本帧before/after ICP均0通过、gauge RMS3.51m，但目标没有对应score输出/实际命令、source与reference绑定、匹配健康prefix/单变换、逐帧缺测与共同支持清单。本机仅核地图和位姿几何及synthetic工具，不独立重跑这次真实评分；上述数字记 **DEVELOPER_REPORTED**。

不接受用已反证“静止”作为这些负分的解释，也不把UNKNOWN改成参考有效。最低先归档现有评分原件与单一冻结prefix变换，解释覆盖/分辨率/时间支持；每帧ICP只能另列fitted compatibility，不以同bag、起始单位pose推定整段同gauge或用逐帧拟合当质量评价。producer doc和REPORT仍称“修正量说明位姿偏差”等，随已有报告集中中性更正，不因此重跑完整宿主。

## 3. 主线/旁支、责任与下一单一交付

| 分类 | 最小工作与边界 | 责任确认/验收 |
|---|---|---|
| **唯一原生主线** | 合法隔离起点前完整可信cp→物理一致修复/真实native state-map重估→完整输入接回与后继事件尾段；不支持范围显式拒绝 | S1共享driver/manager/成功依赖单写，S2真实宿主历史cp/运行；既有分工有交付，新最低修复认领/执行仍待回执 |
| 评价前必须做，不阻native研发 | 更正静止/320s归因，绑定已运行评分命令/原件/共同支持与prefix gauge；没有证据保UNKNOWN | S1证据解释、S2现有时间/保存原件；不要求诊断全部闭合才推进native |
| 可并行研究 | 用户ALI-H v1有限shadow测试：先T0旧402/544资格/缺项、真实I及低支持健康参照可用性；缺项UNKNOWN | 设计已合入main，只证明文件发布；S3实际认领/branch/预算/实现和测试结果**尚无回执**。保持1研究+2native，不占S2整轮诊断 |
| 集中延期 | ASCII COUNT兼容、其他未影响当前binary输入的格式/措辞扩展 | 不加矩阵/新防御框架/测试条数目标、不安装缺依赖 |

主线代码未变：合法quarantine_start前cp、collect未知/失败依赖、候选与实际修复测量物理一致、完整损坏/未修人口、独立净收益仍按[5f54核验](../review_20261112_5f54a44_native/README.md)和[70e3核验](../review_20261112_70e3e7c/README.md)范围保留；不重测旧反例，不抹已验suffix重推/skip旧pose/受控修复后E2与39尾帧。UNAVAILABLE生产支持门/处理策略未改，物理原因未解决；ALI-H不是已经测试或上线。

下次随实际交付按 **检查项 / PASS、FAIL、BLOCKED、NOT_APPLICABLE / 命令与输出或原件 / 受影响主线 / 下一动作**自检：source/input/library/config、cp与实际隔离边界、native成功/失败依赖、所有修复/未修/后缀/未配对归宿、E2/尾段、独立质量/缺测/成本。未做写NOT_IMPLEMENTED/NOT_EXECUTED，不只给测试总数或“已自检”。

A3/B3/A11支持组件局部修订接受，A2仅新增非恢复地图运行身份核验；A4/A8/A9/B2/B4/B11没有本轮新增闭合证据。不重评全表、不继承历史总分。此增量属于工程/评价旁支，原因不能归入调参；没有同版本同人口参数规律/改善上限证据，不恢复旧sigma/κ/floor。真实执行负结果、缺尾、UNKNOWN和退出异常均保留。

## 4. 本机实际命令

- `C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_eeda122/check_archive.py` exit0；仅读取目标Git原件，不执行归档脚本/远端bag。
- `C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_eeda122/run_checks.py` exit0；研究源码target-bound有限控制，无ROS/native运行。
- `git -C D:/REPAIR/slam_recovery_upstream show eeda122:slam_recovery/ros/run_native_loop.sh | C:/Program\ Files/Git/bin/bash.exe -n` exit0（PowerShell经调用运算符运行Git Bash）。

仅发布本轮证据与最低交接，独立review分支按既有授权SSH提交推送；不覆盖历史/开发日报，不stage私人handoff。不重复制造两小时总结或规则提交。
