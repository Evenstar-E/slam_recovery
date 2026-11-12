# be35af9增量核验：ALI-H已认领，旧数据缺I成立，真实导出需先对应残差空间

面向：开发S1/S2/S3与独立复核者。固定目标 `be35af983639cf97354c13b09fad79845754b491`，比较已验 `d86e57df09c076e531cb2e4edabdc70daac6b668`；2026-11-12 18:05 UTC+8 fetch。先读AGENTS、A/B标准、REVIEW§10，未变复用；实际三周期任务及08:53一次截止报告由repair-f3持有，无旧owner双写，用户忽略stop.md优先。私人handoff未动、不合main不修算法/历史/冻结阈值。

## 1. 实际推进与证据层次

main新增是S1的认领、接口确认和研究结果报告，无slam_recovery实现改动/新host run归档。接受**开发侧实际回执与研究进展报告**，但不把它们全当本机独立实测或自动检测改善：

| 项 | 开发回报 | 本机可核范围 |
|---|---|---|
| S3认领 | r26534-58，`/tmp/wt-ali`、exp/ali-h-v1，T0/T1、0host研究预算 | 目标COLLAB§115有明确S1转交回执，已不再笼统写“没人认领”；远端实时worktree/process本机NOT_READ |
| T0/T1实施 | S3 commit8c5b082，9研究文件，全部UNKNOWN/6tests PASS | **DEVELOPER_REPORTED**；目标main没有docs/ali_h_v1_research，正常SSH ls-remote指定研究分支exit0空，当前fetch无8c5b082对象，故本机未读/未执行实现、自测和shadow |
| I缺项 | 旧402/544行无IMU内部preupdate；输入bag虽有IMU原始流，没内部预测 | 旧档观察字段本机独立核成立；bag话题计数和远端mat_pre/out现文件仅DEVELOPER_REPORTED，不代读bag或远端 |
| 真实接口 | pre/out已有，协方差未导出；S1/S2拟一次build+两短off/on对照 | 只接口/预算报告，**NOT_EXECUTED**；目标没有新pre/out/cov文件/新宿主patch或运行，不能说I已解决 |
| 审阅采纳 | 更正静止/独立参考必须同轨迹/唯一干预归因，§114认可原件 | 接受解释收窄，纯旧review合入不重复评分/归档核 |

目标还未合入2c838c7的15小时任务和13002e6最新原生核验；最新“不中断/中文重大阻塞/无Codex”用户要求优先，S1应获取现review入口并继续实际交付，不仅按旧shadow待选择条款等待。没有新用户决定或真实重大阻塞时，不因常规阶段/字段修正停全任务。不能把“凭据恢复/内联认证”转述当本机用凭据授权；本机仍只现SSH、不使用/复述PAT。

## 2. 本机旧档资格复算：缺真实I，不是参数门限能补

[隔离reader](check_evidence.py)/[结果](evidence_checks.json)从固定target读取已保存原件，Python-I，不运行S3/归档脚本、host/bag：

| 完整人口 | A（065500Z） | B（070801Z） |
|---|---:|---:|
| paired | 402 | 544 |
| AVAILABLE / UNAVAILABLE | 95 / 307 | 132 / 412 |
| 支持不足（按数值字段） / 空参考 | 285 / 22 | 351 / 61 |
| 缺NIS | 1（包含在空参考内，**非额外第三个互斥人口**） | 1（同样包含） |
| UNAVAILABLE里fresh node_map原量 | 28 | 137 |
| UNAVAILABLE里fresh prev_scan原量 | 278 | 274 |
| UNAVAILABLE里无fresh原量 | 1 | 1 |
| 可见真实I字段 | 0 | 0 |

A旧support.reason中285仍写ok，真实fraction低于.6；reader保原标签同时从reference_points/fraction派生原因，不将旧标签冒判据。M原量占不可用人口28/307≈9.1%、137/412≈33.3%，只表示来源数量，**finite/fresh不等qualified健康证据**。

ALI-H当前NORMAL要求真实I与M/T共同相容，故在这些旧档输入上NORMAL结构上限0成立（不代表物理上不可能正常）。独立正常校准缺，SUSPECT资格亦未取得；全UNKNOWN是符合缺项的可预期边界，不算方法解决/新自动检测性能。目标自测6PASS、shadow UNKNOWN402/544仍记开发报告，待上传原件；本机没有拿HEALTHY、无注入或预测作真值。后继新I trace不能贴回旧run，应在新同trace同时跑旧方法和ALI-H。

## 3. 导出前最低数学对应：测量innovation S不能直接给位姿eI

目标§116拟导出Pminus/Pplus(rot+pos6×6)、vec6、H_T_H6×6、R摘要，以及 `S=H Pminus H^T+R`，随后称“逐点面残差的6维聚合/ALI-H sI用S”。目前只有文字规划，**本机不指控实际代码已经错误**；但照此直接代入会错配残差空间。

- ALI-H §3定义的 `eI=Log(inverse(DeltaT_IMU_preupdate)*DeltaT_host_observed)` 属声明SE(3)切空间（通常6维），米/弧度/顺序/基须同一。
- 若H把6维状态映射到m个点面残差，S是**m维测量innovation covariance**；不能只因为H_T_H为6×6就把S说成6维pose covariance。H_T_H是信息型量，也不是S。
- 若只做 `vec` 某个6维压缩统计，需要明确压缩/线性化映射、配套压缩协方差与该统计的含义；压缩后的S不能默认适配另一6维pose Log残差。真实测量r可以在自身测量空间评分，但要另名/声明，不冒IMU运动一致性。
- pre/post共享滤波先验与同一测量，Pminus和Pplus不独立，不能简单相加当eI协方差。可导出真实已有量，不为此新造独立惯导或强行导出巨大稠密m×m矩阵。

**最低解除**：S1/S2/S3在现导出接线中明确“实际残差向量/起止时间、frame/tangent/order、Sigma对应来源/映射、有效rank”。若没有合适eI covariance，先保带单位平移/旋转残差并沿真实正常条件经验校准，协方差归一量NOT_AVAILABLE；不补单位阵/假卡方，不把所有可用工作停掉等推导。不是要求改模型/新阈值或扩矩阵。

每次pre/out实际对应需要绝对戳/阶段和早退has_out；不能单靠行号或重复相对t配对，也不能把跨restore/reprocess/reset的状态差误读为普通IMU-LiDAR同窗冲突。原生已有replay可能多次出现同时间戳，沿现run/phase身份区分，未能对应的输入missing/UNKNOWN。导出预算off/on两有限run属于开发所报最小开关控制，不自动追加第三轮；随机差异按趋势/效应/失败范围报告，不强求逐决定/逐位相同。保持source/input/library/物理时间对应不豁免。

## 4. 下一唯一交付与分工：继续，不新停止或重复研究

**当前15小时目标：真实ALI证据→同人口shadow→有可核结果后有限自动检测接线。**

- **S3（研究已认领）：**先把现9文件/8c5b082或修订HEAD及SHA通过现GitHub分支发布；修bytes/块数命名/checksum是旁支收尾，不能只报告“六测试”。随后同新trace完成资格/校准/标签及误报漏检延迟错误NORMAL/UNKNOWN时长与成本。正常低支持参照/独立标签仍不可得时保INCOMPLETE/NOT_EVALUABLE，若已证必须改变数据/方法/预算，则立即按15h模板中文重大阻塞告知用户，其他未阻塞工作继续。
- **S2（接口已确认/导出未执行）：**沿一次现预算实际导出，上述残差/cov对应与绝对时间/早退/phase是本次数据有效性的最低保障；及时复制不会被下次trunc的原件/hash。已有mat pre/out适用则先复用，不每次推迟到全部instrument完美。
- **S1（共享集成）：**获取中文15h入口、确认实际S3/S2执行状态与预算，单写driver/manager/检测动作；同时复用v6合法scripted cp，收口正常拒绝后input归宿/成功依赖，不用新ALI掩盖原生问题。不存在Codex辅助，不分派/等待Codex。
- **S4：**现周期及截止报告继续，只有实际证据才验收；不代远端实现/host，也不从缺上传推定方法或权限根因。upload/字段收尾可并行，不串行挡有限原生开发。

没有证据证明调sigma/κ/floor能补I或独立标签，不恢复旧手调/新门，不clean-map矩阵。开发当前T2因待trace BLOCKED属可解除依赖；不是已证需要用户选择的全面重大阻塞，本机不制造需确认的重大阻塞单。若真实证据不可获得/超预算，则按用户要求立即中文GitHub记录，不能静默停夜间任务。

下一交付自检逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+实际命令/输出原件+受影响结果+下一动作：raw/source/fresh/time/calibration/label/rank/phase、完整消息/paired/缺测、shadow不改旧动作、有限自动接线与native归宿/持续运行、风险UNKNOWN成本/负结果。未做NOT_IMPLEMENTED/NOT_EXECUTED；A3/B3资格研究局部认识增加，性能/原生自动链/净收益未闭合；A4/A6/A10本轮无新run，沿d86核验不重评全表/历史总分。

命令 `C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_be35af9/check_evidence.py` exit0。只新增真实回执/资格复算与导出有效性最低意见，中文review白名单SSH提交推送、不合main、不覆盖历史/private/开发日报、不安装或新任务重复Cron。
