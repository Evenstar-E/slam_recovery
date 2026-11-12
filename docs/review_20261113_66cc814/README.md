# 66cc814增量审阅：v10导出源码推进，消费者与真实I资格尚未接通

面向：开发S1/S2/S3与独立复核者。固定2026-11-13 00:25:55 UTC+8 fetch主线 `66cc8146909329ef4bc712cd0728dc4cb4dfd0f4`，比较e351a0b；宿主原件 `exp/online-v2@eb2630ef10f827626ee1eaad87fa7ddc39cc825c`，比较1fde521/v9。跳过已验与Auto-Review/纯审阅合入。AGENTS/A-B标准/REVIEW§10及历史§88已读；四Cron仍repair-f3单owner，其他本机会话waiting/idle，无旧owner双写。忽略stop.md、用户直接暂停优先。只源码、归档与有限reader控制，不算法修改、ROS/bag/构建/调参或安装；现review分支、SSH、私人handoff保护。

## 1. 接受范围与本轮结论

**真实I取证的源码准备有所推进；没有新bag数据、合格I、ALI效果或原生恢复结果。**

| 检查项 | 状态与证据 | 接受范围／下一动作 |
|---|---|---|
| T2机读资格及数学元数据 | PASS（保存产物读取） | i_qualification=INCOMPLETE/UNKNOWN，完整Jinv约定已更新，504明确数值行而非合格I。t2_join数值逐字未变，不重跑已验SE3控制 |
| 尾段47/51口径 | PASS（本机算术） | pose相对首pose≥54s为47行，尾块成员51，其中4行早于54s；两数是不同定义而非同分母矛盾。解除旧数字说明缺口，不更改完整人口/UNKNOWN |
| v10同行post pose7 | PASS_SOURCE | StateEstimation后_state写trace，增加xyz+四元数，与该行abs_ns/idx/grp/phase共享来源；实际100列数据NOT_EXECUTED，has_out=0行不能称完成post更新 |
| v10 LIO-only pre/out | PASS_SOURCE，唯一配对NOT_VERIFIED | 只handleLIO写，pre在StateEstimation前、out在更新后；handler混写来源局部解除，但独立文件仍只有rel_s，无idx/grp/phase，空点早退也只有pre。最低绑定实际同一更新，不按行zip/近邻猜 |
| v10构建/启动探针 | PASS_ARCHIVE限定范围 | FAST-LIVO2子目录laser_mapping与fastlivo_mapping两目标Built；5份probe均alive25s，库SHA一致69dc8ac5…；不全workspace构建、独立重建、尾稳定或完整二进制身份核验 |
| 当前T2消费者读取100列 | FAIL_REPRODUCED_LOCAL | 两个已读parse_trace都把正常v10宽100行标malformed，详见§2；仅阻本次新导出的消费，不阻旧92/93档或其余合法native工作 |
| v10协方差资格 | NOT_AVAILABLE_FOR_E_I | 只增加body/right声明，没有修改混合状态扰动或导出残差Sigma，不能用字段文字升级成eI协方差，详见§3；单位权路线仍可推进 |
| 新真实I/恢复/检测效果与成本 | NOT_EXECUTED／NOT_EVALUABLE／UNAVAILABLE | 本轮无新bag/trace/receipt或同人口正常标签结果，不将准备、探针或全UNKNOWN计为效果 |

[有限核验脚本](run_checks.py)/[实际输出](local_checks.json)，命令 `C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261113_66cc814/run_checks.py` exit0。只标准库fixed Git blob读取；解析器控制在内存执行已读函数、StringIO提供一行声明宽度，不执行归档CLI或创建假run。exit0是检查/反例完成，不是两个目标reader通过。

A1/A11与A3/B3有取证准备及机读诚实资格推进，A2/A12有局部构建/探针档；A4/A5/A6/A10/B2/B4/B11没有新恢复闭合，真实I和性能仍未验。未复核全表，不报新总分。

## 2. 本次实证最小接线断点：100列导出未被现reader接受

`66cc814:docs/ali_h_v1_research/t2_run.py:90–110` 的parse_trace要求len(f)==vec_start+78（v8为93）；`t2_join_upgrade.py:25–41` 仅接受92/93列。v10在原93列后追加7个post pose标量，合法完整行应为100列。普通header加100个数字控制均得到0 rows、malformed=[{line:2,ncols:100}]；失败发生在值解析前，不是人为恶意格式或数值问题。本轮没有实际v10 trace，不能说真实run已被删除或误分类。

**最低S3/S1**：沿已有按名/块字段parser支持已声明pose7尾块，保留vec6/Ppre/Ppost及缺项/截断口径，并真正读取这份同行post供新路径使用；只对现声明schema做一个正常100列控制，复用旧92/93，不扩泛化兼容矩阵。不要仅把100列放行却仍用外部旧pose关联，或把合法新行默认为NO_DATA。消费者可与S2有限导出并行准备，不因此停全部主线。

## 3. 导出改进不能单靠声明补物理与统计资格

v10 `src_LIVMapper.cpp:607–654,773–784` 的LIO-only pre/out源顺序正确；前置Process2后state_propagat=_state也提供了复用实际pre的入口。**允许沿真实同次pre/post直接形成残差，不要求一定导出final solution或继续反推旧vec**。但当前两份额外文件只有rel_s，不能唯一跨live/replay、重戳、空点早退与两个更新组配对；最低将所用pre绑定trace已有idx/group/phase同一更新（例如同一行保存pre，或额外文件写相同key），没有关系则INCOMPLETE，不新建通用关联系统。inlinepost源码改进接受，但未运行前不称v8或v10真实配对已经通过。

原 `src_voxel_map.cpp.v10` 与v9逐字相同，vec仍最终solution之前取，数学旧修正直接复用；四个其他源码文件亦未变。common_lib.v10:178–193仍R*Exp(drot)、pos+=dpos：旋转body右扰动与世界加性平移混合。新增trace头“BODY(IMU) tangent space…Use them as e_I covariance”没有产生对应Log残差的转换/相关性模型。**最低继续cov NOT_AVAILABLE、单位权可走**；若以后需要s的物理意义才补真实映射与相关性，不Ppre+Ppost、换frame字符串或把声明本身当证据。这是既有缺项在新header仍未解除，不新造协方差防御门。

T2_I_ELIGIBILITY将总体I收窄为INCOMPLETE/UNKNOWN可接受；其表内v8 carryover“PASS单扫描”、post“PASS时间join”仍超出已核来源范围。n_scans计新pop的raw而carryover在cur/next，未证明完整点成员；grp/首末戳非唯一所用更新。现无新数据，不把这些子PASS提升为有效物理I或推独立性，随实质后继收窄即可，不为文案重新跑旧矩阵。

新stdout/state人口仍531行UNKNOWN/120块，tail两口径有实证说明；BLOCKED正常/标签不等未知正常化。新目标未改变native恢复选择/完整IMU/capture缺口、失败ACK支持误判或旧手调暂停，勿因研究准备忽略原生主线。

## 4. 唯一下一主线、并行保障与责任

**现单宿主/授权预算内：完整且≤qstart的检查点＋可重放历史→物理一致实际修复测量→原生状态/地图重处理→全部后继输入归宿；不能支持的范围明确拒绝。** 研究同时用新真实输入给一次有资格结论的同人口shadow，不能无限只导出/更改声明。用户15h窗至08:53仍有效，“今晚未跑/明天第一run”是开发安排，不是用户暂停或延期；实际远端连续执行状态UNCONFIRMED，未阻合法工作继续。

| 分类 | 责任、最小工作与验收 |
|---|---|
| 主线 | S1唯一共享集成/S2真实宿主：完整旧cp、必要IMU/capture及实际恢复/输入归宿；保留半程已交，后半仍未交，复用既有受控重处理而非新框架 |
| 必须先做，仅新I消费与资格 | S3/S1接100列reader与同行post；S2/S3绑定真实pre同更新；cov保持不可用即可，不强求协方差前置。一个现schema正常控制＋真实同run原件，未知明确保存 |
| 可并行 | S2沿现预算新导出随run保存两LIO文件/trace/完整source/binary/library身份；S3已有正常/标签材料核及shadow，现授权声明注入只离线，不重复问抽象A/B/C、不增Codex前置 |
| 集中延期 | 一般ASan/尾因果、非必要日志/兼容/文案；只实际影响当前执行/状态/评价的最小问题先做，不无限诊断/测试或恢复sigma/κ/floor |

S2 v10实现/构建/探针实交与S1集成确认；新bag/数据及S3 reader部署/实际研究回执未交，不把派工当完成。下次逐项自检**PASS/FAIL/BLOCKED/NOT_APPLICABLE＋命令/输出原件＋影响/下一动作**：owner/HEAD/预算/input/source/binary/library，cp/qstart/IMU/capture/全部pending与后继，修复对象/未修/误改/未知，pre/post真实key/phase/空行/截断/全人口、正常校准标签/UNKNOWN与成本。NOT_IMPLEMENTED/NOT_EXECUTED/NOT_EVALUABLE保留，科学门不降。

本次导出源码与资格收口、新schema正常失败构成实质增量，现review分支中文SSH白名单发布；不修改生产算法、不代host，不合main/改历史/private/开发日报，不另造重复两小时总结。
