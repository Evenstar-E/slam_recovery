# 70531be审阅：UNAVAILABLE已定位到实际分支，几何原因与恢复闭环未闭合

- 读者：用户、开发S1/S2/S3与独立复核者。
- 目标 `70531bef27467519e370ac4819609398f1933533`，比较 `eeedb7fed53a91905b77bb38705a73aaae4927f3`；跳过已验收审阅和纯旧merge。本轮已读AGENTS、评分标准、REVIEW§10和PROJECT_HISTORY相关入口。忽略stop.md按用户直接裁决，旧参数保持暂停。
- Cron实际由repair-f3持有：20min审阅/2h总结/每日归档，无活跃旧repair-3e owner；不重复建立任务。本机review分支未merge main、未改算法/远端宿主，私人handoff未stage。

## 1. 先报实际交付：用户诊断要求从认领进入实现和有限运行

S1新增旁路AvailabilityRecorder、同次support/NIS计算细节及runner环境入口；S2实际运行 `fl_native_20261112T065500Z_187992`。检测on，三组scripted列表均空、无relay注入；不是detection off或预置事件的运行。S3只做旧源码/归档分析，未实现替代判据；旧sigma/κ/floor调参未恢复。

| 检查项 | 状态与实际证据 |
|---|---|
| 原件完整性 | PASS：13/13列示SHA一致，gz与解压JSONL SHA均匹配sidecar；402行与paired402、summary402逐帧一致，kf0–401、pose/scan戳各唯一递增，status由两个布尔重算零差 |
| 驱动身份 | PASS：记录SHA `93f69356…` 与run版本c35b162和目标driver Git bytes均一致；支持reason后继8d6e4ed语义修正不改布尔 |
| 宿主/输入身份 | receipt记录bag/config/binary与库 `9c0330be…`，后者匹配已核v3构建声明。当前档无实际库/bag实体和host.log，不称本机再次核实进程加载或完整native state/map |
| 全人口边界 | 全paired记录PASS，不等全消息均检测：606pose/598scan，402paired，204/196未配对；配对率66.34%/67.22%，最大dt39,959,192ns，在声明40ms内。未配对不混入307 UNAVAILABLE分母 |
| 真实在线触发 | PASS限定路径：kf23/119/172实际QUARANTINED，三候选均MODE3拒绝；restore/resume各3次ACK，重武装3次。没有独立故障标签，召回/误报/起点准确度UNKNOWN |
| 实际测量修复 | NOT_EXECUTED：actual node repair_publish=false、log off；receipt的repair_publish="1"是runner环境值且无relay时不会启用实际publisher，不冒作已发布。accepted/commit/reprocess/repair_applied/set_state均0 |
| 原生失败与终态 | 15snapshot成功、14snapshot_ack_timeout；HEALTHY来自wait_limit_closed→ABORTED/rearm，未解决人口70/60/44。wiring all_ok不是无失败或恢复成功 |

开发运行命令原件：`AVAILABILITY=1 WAIT_LIMIT=2.0 bash slam_recovery/ros/run_native_loop.sh /tmp/fastlivo/hall01_two_event_v1.bag --detection on --candidate-source host_poses --sigma-meas-m 0.884 --drain 20`。receipt planned kill after drain；node runtime94.328s、peak RSS1,008,996KB是记录值，非整宿主峰值或诊断增量开销测量。压缩12,812,124B、解压46,896,127B，不凭文件条数宣称低成本实时链。

## 2. 已回答“为什么本次UNAVAILABLE”：支持条件失败，不主要是缺NIS

| 实际分支 | /402 paired | /307 UNAVAILABLE | NIS情况 |
|---|---:|---:|---|
| 参考为空 | 22（5.47%） | 22（7.17%） | 21仍以prev_scan新算有限NIS；首帧无NIS |
| 参考非空但1m内支持比例<0.60 | 285（70.90%） | 285（92.83%） | 全部新算有限NIS |
| 支持通过 | 95（23.63%） | 不适用 | 全部新算有限NIS且实际送入step_frame |

raw finite/computed401、not_computed/no_reference1、carried_forward0、inf/nan0。联合 false/true306、false/false1、true/true95、true/false0；**306 = 285比例失败 + 21空参考但有NIS**。开发REPORT§3表正确，但§6将306全部写成比例不足错误，最低在后继说明更正，不覆盖原件/不重跑宿主。NIS来源node_map123（95可用+28不可用）、prev_scan278（全不可用）、none1。

关键反例是**新算出了较大NIS但support失败，仍不送检测器**：kf157支持63/200=0.315，node_map57点、NIS403.6426057098469、valid23/300、coverage0.0766667，最终UNAVAILABLE。末帧支持0/200、prev_scan NIS794.1427615586034，而manager标签HEALTHY；这证明记录中的前置排除，不证明位姿漂移或检测器本体对它判正常。

连续不可用段0–21、53–117、157–170、180–182、199–401；最后203帧从1627785286344705820到1627785306575157404。22+65=87只是此run两个不连续段的算术，不充历史E2“87帧”同一人口/同一事件；S3跨21run/15source的汇总及/tmp历史83帧分析属开发归档分析，本机未取得那些/tmp原件，不冒新独立复核/同版本趋势。

## 3. 接受内部复算，不能把它升级为实际参考几何和因果已复现

独立reader核285个有参考UNAVAILABLE的完整200点mask与分母；306个有NIS UNAVAILABLE的完整300残差，按原coverage分支复算。134帧用clipped、172帧用all，不一律平均所有300点。mask/coverage/chi²/mean/RMS/分位匹配，NIS最大算术差2.274e−13；24,120个support/holdout查询交集可用已存centroid/normal重算残差，最大差7.106e−15。22空参考无support样本、首帧无NIS，不能笼统说每个UNAVAILABLE均有200/300点。

正常边界kf22报告176/200=.88与NIS18.280525，但只留20/200、20/300：子样本15/20=.75与均值.889422无法复现全样本。其缺项已诚实披露，**边界正常样本完整复算仍未交**，没有预算记录不能称已证明不可保存；无需重跑全部实验，后继仅留少数完整边界样本即可。

关键未闭合项：
- support当时参考坐标/snapshot ID/hash、cache key/刷新戳/age未保存；manager trusted_version是元数据，不等实际滞后cache身份。原件中within布尔能验算比例，但无法独立重算点到参考的几何距离。
- NIS只留sampled-train nn_ids、面中心/法向/特征值，没有实际train/参考坐标与prev_scan来源戳，不能独立重建KNN/PCA；保存平面再算残差不等独立验证平面来自正确参考。
- [transaction_manager_node.py:423](../../slam_recovery/sim/transaction_manager_node.py#L423)的row指传入scan数组。实际[cloud_to_xyz](../../slam_recovery/ros/recovery_node.py#L2141)先去非有限行，再[_on_scan](../../slam_recovery/ros/recovery_node.py#L2215)截到scan_cap。target-bound正常控制12原点/cap4实际保原row0/3/6/9，却写row0/1/2/3；**这是取证身份缺口，不是support判决计算错误**。最低复用已有finite/stride索引映射，不重建producer。

所以当前已证“哪些分支、多少帧、实际support/NIS是多少”，尚不能确定“比例为何降低：参考覆盖、参考年龄、状态/地图偏移还是其他几何条件”。补快照也不自动建立漂移因果；无独立位姿/覆盖证据仍UNKNOWN。不放宽60%/1m、不自动采用S3双参考/预测方案。

## 4. 在线多次拒绝不等实际修复后的E2

三次trigger依次1627785264272873640、1627785273879016399、1627785282080349922；三次候选均无commit，paired benefit通过也没有通过最终gate。后两次在线拒绝→restore→重武装路径确实执行，不能说本次没有后继事件；但**未发生首次测量修复，故不充用户要求的修复后E2**。first_alarm_ts_ns在三episode重复首段值，不能当后两段新报警戳；评价用已存各自trigger/onset并声明字段范围。

本轮无host恢复patch改变，已核v3后缀skip+clear问题与candidate物理一致/成功公开依赖未解除；不重测旧控制，不把这次诊断当修复链首成功报告。

## 5. 本机实测与执行限制

- [archive reader](check_archive.py)/[结果](archive_checks.json)：独立代理实际 `python -I .../check_archive.py --repo D:/REPAIR/slam_recovery_upstream --output .../archive_checks.json` exit0，仅Git bytes/gzip/stdlib算术，不执行归档analyze/source-audit脚本。本机已读其全部reader与结果；未重复代理原件工作。探索初次缺points_saved KeyError/exit1，修reader按实际完整样本后最终PASS。
- [source control](run_checks.py)/[结果](local_checks.json)：`C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_70531be/run_checks.py` exit0，全部slam_recovery模块从精确版本Git bytes内存加载，不拿旧工作树冒target。实际node12帧跨延迟提交边界：9UNAVAILABLE/3AVAILABLE，base/target/no-log/log的diag、NIS、counts、records及trusted状态一致；底层detail开关等值。不是所有真实运行路径逐值不变证明。
- 8项相关unittest PASS0.043s，含2500条无截断及carried来源年龄；两项fake-loop测试依赖pytest未跑，无安装/shim。首辅助脚本误取tx_mgr不存在属性exit1，仅修辅助后通过；先前1.1s控制全为不可用，最终改为2.75s覆盖真实可用边界，最终结果为准。
- 正常原row反例已复现；target runner Git Bash `bash -n` exit0。code-review low本轮无额外finding，不当全部正确性通过。无ROS/bag/host或调参执行。

## 6. 分类、最低解除与下一单一主线

**主线不转成无限日志项目**：S1/S2继续交同次物理一致实际修复→native完整state/map→保已消费后缀按序追赶→接回→E2/尾段，或具体首断点。已有23全量替换/按戳接口直接复用，四宿主前批不重开；S1成功公开和共享代码单写，S2宿主/产物与有限run。恢复整链首次实际完成仍立即单独报用户。

**可并行且仅阻断诊断强主张的最小保障**：S1在现取证入口保当时reference/cache身份和必要坐标/原row映射，少数完整正常边界；每帧大图按hash复用、沿实际预算保存或明确BLOCKED，不建通用框架。S2在下一既有授权运行随附这些原件；现记录不能事后用新地图伪造旧参考，不要求为修数字或逐值一致再开单事件矩阵。若已有足够独立原因证据直接交，不自动新起诊断run。

**旁支/延期**：S3返回既定A/B/C门研究专用，当前新选项只是提出、未选择/未部署；旧参数仍停。306数字、runner环境/actual flag、first_alarm显示等随后继集中更正，不为文档重跑宿主。未配对消息保完整性限制，确切错配/丢失层UNKNOWN，不凭高负载猜唯一根因或加新同步模型。

开发下次逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+实际命令/原件：全paired与未配对人口、同次参考/原点身份、support和KNN/残差复算、真实开关不变范围、自动触发独立质量/未知、native applied/catch-up/E2、质量/成本/失败。不实施/未运行明确NOT_IMPLEMENTED/NOT_EXECUTED。

A3/B3真实检测路径与分支取证局部推进；A1/A11/A12诊断追溯局部推进但参考/点身份与全部消息/成本仍有限。A6/A8/A9/A10及B4/B11实际修复整链未增加，不给新总分。不改历史/冻结科学门；仅独立review白名单提交SSH推送，发布不等开发已收到新意见。
