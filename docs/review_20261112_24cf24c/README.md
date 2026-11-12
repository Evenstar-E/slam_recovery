# 24cf24c增量核验：ALI研究原件已到，真实运动导出两次失败仍待环境证据

面向：开发S1/S2/S3与独立复核者。固定目标 `24cf24cbea76d08011e3933b3b11c48dd7588b7b`，比较已验 `be35af983639cf97354c13b09fad79845754b491`；2026-11-12 18:25 UTC+8 fetch。AGENTS、A/B标准、REVIEW§10必读未变复用；四实际Cron含08:53截止报告仍repair-f3单owner，不重复建任务。用户15小时连续推进/中文重大阻塞/无Codex指令已合main，不把历史Codex配置当现人力；私人handoff保护，忽略stop.md，不合main不改算法/历史/冻结门。

## 1. 本轮真实研究组件与资格证据增加，自动检测效果没有新实证

新增 `docs/ali_h_v1_research/` 的shadow实现、现402/544原件分析、自测、T2输入契约/校验器与评价协议。旧被指出“研究产物没有上传”在本目标已解除；不继续机械记未发布/未实施。共享slam_recovery源码未变、无新motion trace/原生运行归档，因此不宣称已解I、已分类真实NORMAL/SUSPECT或已接入自动检测。

[隔离reader](check_archive.py)/[结果](archive_checks.json) Python-I读目标Git字节，**不执行研究/归档脚本或远端host**：

| 检查 | 独立读回结果 |
|---|---|
| 五项manifest产物 | 5/5 bytes与SHA一致，shadow A652502B/B891001B，T0 A30986B/B40475B，T1 3906B |
| 实现身份 | ali_h_v1.py SHA与manifest一致；新增T2源码有Git身份，不冒这些新增文件已包含在旧五项manifest内 |
| 逐帧身份/旧判决/来源/分数 | A402/B544逐行run/key/pose戳/scan戳与旧原件同，保存status/source/reference/fraction/score一致 |
| 块人口/上下文/缺项 | A90/B119个0.5s块，按pose戳分块和MIXED/缺证据分类复算一致；不是把946帧当独立同run人口 |
| 保存shadow状态 | UNKNOWN402/402、544/544，scope NONE、I0；缺独立正常校准/label保留 |
| 自测记录 | T1六项、T2 prep十一项保存PASS、failed0；本机只读记录，**NOT_EXECUTED**，不把保存结果当本机已运行 |

旧UNAVAILABLE A307/B412内M原量28/137、T278/274，仍缺真实I/独立正常参照。原量finite/fresh不等健康资格，全UNKNOWN是缺项结论不等方法无效或零风险。保存开关不变性仅原字段/同一归档观察器控制，不证明生产manager/native命令完全不变。旧输入没有改，不重审旧NIS/轨迹/59损坏人口。

## 2. 两次trace失败：真实结果尚未可核，最小环境诊断不等需要用户选模型

目标COLLAB§119/121报告 `100744Z_326380`、`101116Z_329791` 两次启动FAIL，host出现image_transport package/plugin错误，pose0/paired0/scan598，新库691d7334、driver a4aaa58b；这些run的receipt、host日志、部署patch或trace未入目标，记 **DEVELOPER_REPORTED**，本机不独立验收根因或运行成本。

同runner source环境下rospack插件查询成功，仅支持“查询进程可发现插件”；不能独自证明宿主实际fork环境、插件加载依赖/资源解析或具体启动路径。根因 **UNKNOWN**，当前候选为工程环境，不算法/阈值失败。S1已要求进程fork前ROS_PACKAGE_PATH/ROS_HOME并在证据到前不第三次重跑，这个最小停止单条失败重试是合理的，**不暂停整个15小时任务**。

最低S2保两失败run的实际命令、receipt/host错误、运行库/config身份和宿主进程继承环境/现插件定位结果，沿现环境最小修正，不安装/改认证/删资产来绕过。若普通路径问题可解，继续原批准有限导出与同版本trace开关对照；两次启动失败不当有效的off/on检测对照。若必须超预算、安装新依赖、改用户范围或确实无法继续，立即中文重大阻塞告知最小选项，只停该部分；本轮尚无独立证据证明需要用户作重大决定，不制造虚假的重大阻塞确认。

正常低support校准与独立标签是另一依赖，不会因为成功产I就自动拥有。S1/S3应现在确认现资料可支持的正常/异常范围和出处；找不到则明确NOT_EVALUABLE。若已证明现授权内无法取得必要证据，按15h任务中文阻塞记录说明需要哪种输入/证据、成本/选项，不能只等trace成功后才发现校准仍无。

## 3. 源码独立审阅

只读审阅已完成，主会话再核目标源码并做[三个最小正常控制](run_checks.py)/[结果](local_checks.json)，exit0代表反例成功复现，**不是目标代码通过**。只编译内存中的已读目标函数/常量，不调用归档CLI、自测或写其产物；构造证据不冒真实trace误分类。

1. **SE(3) Log平移错误（t2_input_check.py:123–126）。** e_i取SO(3) log后拼原translation，漏rho=J(omega)^(-1)t。普通Rz(.2rad)+t(.1,0,0)输出平移(.1,0,0)，契约应(.099666444,-.01,0)。同一个已匹配切空间的构造cov下分数.05 vs100.049933，能改变条件分位判决；现selftest207–220恰把错误平移写成预期。最低复用现SE(3)工具/公式修Log及这个控制，不换阈值抵消。
2. **整块缺测仍跨空窗累计（ali_h_v1.py:216–256、260–266）。** block_summary只遍历有行块，classify不检查block_id相邻；块10与12各M ALARM、11无行时，12输出SUSPECT；I+T NORMAL同例输出NORMAL_CONSISTENT。显式插missing11则12正确UNKNOWN，证明是完整缺块问题而非一般缺证据已处理。最低声明首末时间人口内补NO_DATA/UNKNOWN块并断开dwell、保last_suspect；仅这一个10/12控制，不大缺测矩阵。T0无校准全UNKNOWN不因此作废，但弃权时长不能漏整块。
3. **READY不证明cov与残差同切空间（t2_input_check.py:32–35、59–84、110–142）。** validator允许left/world、没有P_frame对应；e_i固定inv(pre)post右残差，s_i直接用传入P。其自己的left/world manifest被READY接受。普通pre Rz(pi/2)、post world x增1m、left/world平移cov diag(100,1,1)时直接评分1，正确转换到右残差切空间后.01。真实caller未交付，不能宣称实际运行已经漏转换；最低显式各P/vec/frame/扰动/参数化与eI对应、实际转换或只接受真正匹配约定，其余INCOMPLETE/NOT_AVAILABLE。Pminus/Pplus状态块也不凭usable=true就当eI协方差，真实来源仍须接线证据。

来源/上下文分校准、T-only不判NORMAL、显式missing不清last_suspect等静态符合设计；但真实dt/age/coverage/rank范围、phase/早退/join人口与校准标签仍待真实接线。三问题只阻受影响分类/计分结论，环境最小解除及现trace导出可并行，不要求全部工程完备再开工。内部审阅代理曾误调forked code-review，违反其只读不再委派的窄任务要求；已披露，主会话亲自核上述源码和反例，不把代理/skill摘要当实测证据，不新增远端Codex角色。

## 4. 下一单一交付与分工

**当前目标：有效真实I trace及同人口ALI/旧方法结果，证据支持后有限自动检测接线；不是另一份协议。**

- **S2工程/宿主：**首先解除实际启动断点并保失败证据，沿现一次有限导出范围保存可用pre/post/绝对戳/phase/真实bias与cov声明，time/order/残差空间匹配；无合适eI covariance只交单位残差NOT_AVAILABLE，不直接Pminus+Pplus、S/H_T_H冒Sigma。
- **S3研究：**复用已上传实现/旧T0，不重复全UNKNOWN研究；现trace前完成必要正常范围/label出处确认和实际T2 join/缺测分母准备。拿到新trace后同一新run两方法，报漏检误报延迟错误NORMAL、UNKNOWN数量/时长/最长区间/成本；不把另一run内部I贴回旧402/544。
- **S1共享集成：**单写检测入口/状态动作，复用已验v6/scripted边界、suffix/skip/受控E2，原生自动cp/拒绝后input归宿/成功依赖还须实际有效。工程失败不扩宿主/数据矩阵、不手调门追截止；有重大阻塞按中文GitHub模板，否则继续未阻塞任务。
- **S4审阅：**四Cron保持、截止中文报告，无Codex辅助前置；仅核来源/正常缺陷/实际结果，不代ROS/算法或绕权限。

必需先做旁支仅启动能力和本次残差/时间/校准对应，source/hash/字段收口可并行，未变旧测试/无关ABI/格式兼容集中延期。自检逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+实际命令输出原件+影响+下一动作，所有失败/缺项UNKNOWN/未配对/label/资源纳入，未做NOT_IMPLEMENTED/NOT_EXECUTED；不以201tests、T2协议或全UNKNOWN作为自动检测完成。

A3/B3新增实现/资格组件，主检测效果未闭合；A2/A6/A10无本轮新可核原生run，A4/A8/A9/B2/B4/B11沿既有范围，不重评分全表/历史总分。旧sigma/κ/floor继续停、既有科学门不降；未取得交付不是根因证据。

## 5. 实际命令与范围

`C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_24cf24c/check_archive.py` 最终exit0。初reader把块字段误当channels、又误以为逐帧calibration同块恒定，均只修自写reader按已存schema/数值派生，不改目标数据或判据。仅读研究JSON及固定旧原件，不执行研究自测、host、ROS、bag、新调参/归档脚本，不安装依赖。

`C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_24cf24c/run_checks.py` exit0，三个正常反例复现；无native/参数/归档CLI执行。

本轮有真实研究原件/接口进展、三个正常分类准备问题与启动缺口，中文review白名单SSH提交推送，不覆盖开发日报/历史/private，不合main不改算法。不重复造规则/空报告；最小修正由开发执行，不因一般修正要求用户暂停夜间工作。
