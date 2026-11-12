# f48b23f审阅：四项运行尝试已交，共享前端与修复缺口按范围记账

- 读者：用户、开发主会话S1、宿主执行S2及独立复核者。
- 取证：2026-11-12 12:25:49 SSH fetch成功；目标 `f48b23f66707e9491350c1c62972fbf542f94fa3`，基线088906a，review工作树46fdbf9。无新production改动，只报告/运行原件/修复缺口分析；未merge目标，保护private未提交handoff。
- AGENTS/A-B/REVIEW§10与实际任务owner已核，三既有Cron属repair-f3，无旧owner，不双写；用户直接指令优先、忽略stop.md，旧参数仍停。

## 1. 主线交付：余下两项有真实运行，不能夸大共同结论

MM-LINS/SC-PGO与FAST-LIO共享前端单独运行原件已交，不再NOT_STARTED。两者是**两次实际启动/录制**，同输入但后端是否开启不同，不是重复读取同一bag冒两次执行；同时使用同一个MM-LINS改版FAST-LIO二进制，**不是独立原版FAST-LIO2验证**。

本批四个命名项都有执行尝试，保留LIO-SAM、ORB之前的失败；四项的slam_recovery测量修复接线仍NOT_IMPLEMENTED。运行覆盖进展有实证，恢复成功/公平多宿主有效性不因此通过。

| 项 | 本轮结果与可核边界 |
|---|---|
| MM-LINS/SC-PGO | 两次前端停发/局部重建，PGO随后继续，E2后PGO227.018s/967条；原生多事件机制支持，不是测量修复或GT质量通过 |
| FAST-LIO2命名项 | 共享前端另跑一次，无PGO；rawlog两次过度退化/两次建新图、E2后239.318s/2126条；支持该改版前端机制，独立原版FAST-LIO2未执行 |
| LIO-SAM | 已归档失败、E2观察窗发散，沿088906a复算，不重跑 |
| ORB-SLAM3 | 之前rawlog失败；本轮另一次74初始化同模式为开发报告，repeat原log/times未公开不独立验窗口 |

**纠正目标COLLAB§66“无恢复能力是共同结果／没有任何一项具备原生恢复写回接回”**：MM-LINS改版前端确有re_slam原生重建及继续输入；准确共同缺口是**没有接入slam_recovery实际测量修复链**，不是所有宿主原生能力不存在。两失败宿主与MM两项输入/事件不同，也不能叫同条件性能比较。“PASS”仅指声明原生机制及尾段执行，不是正确地图恢复/无损运行。前端回原点的60/71m跨断流差不是物理运动或ATE。

## 2. 本机核验范围

实际inline `python -I`从目标Git对象只读SHA256SUMS/analysis/events/runner logs与少量frontend日志，exit0。[摘要](local_readback.json)、[同操作复现reader](check_records.py)（包装reader未另外运行）。15/15清单文件哈希一致；清单不覆盖LIO/ORB及远端大bag，不能写全目录所有原件已核。

从summary原ns/pos复算：

- MM frontend gaps23.699415/26.799199s，跨gap位置差60.556911/71.110834m；PGO gaps38.499598/41.399305s，差0.749237/0.484981m；尾段227.017538s。
- 单独frontend gaps23.799380/26.899189s，位置差60.562744/71.132109m；尾段239.317980s。
- 两事件offset115.99/230.09s与首IMU绝对stamp加法正确。两sleep flag墙钟间隔与声明间隔相近只支持间距，不独立绑定绝对事件时点；低运动窗是开发从输入IMU提取的佐证，本机未读输入bag，不等独立故障GT。
- frontend rawlog:6/312 `Over-degeneracy has happened`，:309/664 `construct a new map`，支持实际发生两次机制；run.log确认两个独立回放/录制完成。

原输入/输出bag、配置/二进制字节不在本机，未独立重算这些哈希或整轨迹；只核归档算术与rawlog。报告只列部分截断SHA，而analysis内没有完整binary/output哈希，若将来做独立复现，最低补现已有完整hash/配方，不为此重跑宿主。/path已排除作事件对齐，其壁钟字段产生巨大tail诊断值不作为真实尾段。

## 3. 测量修复缺口：接受接线定位，撤掉“仓库不存在”结论

目标REPAIR_GAP及COLLAB§67前三条当前在线路径定位可接受：RosDriver仅status Publisher；scan stamp/完整PointCloud2在_dispatch前丢掉；host_poses或ICP候选只产pose，原生replay修复队列为空。因此旧受控run repair应用0不需继续猜匹配/σ是唯一原因。

但**“真正改变测量的生产者在仓库不存在”是错误的范围扩大**：

- `slam_recovery/repair/point_mixture_repairer.py:23–35,105–117`已有 `filter_self_consistent_near_field_contaminants`，产生keep mask改变测量人口；这是已有近场污染几何启发式，非万能去动态/偏差修复器。
- `docs/review_20261109_bbc3dcb/run_fixed_input_repair_c0c3.py`实际调用该filter、按完整原始点记录筛行；M2_point_id_fix记录ring/time/header/原点索引/598帧身份链，已有C3过滤→原生离线重估归档及正负结果。
- 准确缺口是**已有离线修复产物没有接入当前在线driver/host链**，而不是从零发明修复器。若新z系统偏差任务不在旧filter能力内，先写具体不适用原因、复用完整记录/身份/runner，不回头重造已验工具，也不把旧负结果改为新正结果。

公式 `(ΔT T)⁻¹ ΔT T p=p`对同时改变世界点和pose后的坐标重表达成立；只能说明这种纯pose/gauge变换不改变body测量，不能当一般刚性测量偏差或测量修复“不可能”的证明。缺map publisher是工程接口事实，未证明几何信息不可恢复；算法首因/正确修复能力仍UNKNOWN。

## 4. 新方案记录与三个正常执行限制

f48b23f仓库转述“用户选定已知损坏INJECTION”；本会话未收到这条直接选择，记为**开发侧报告的选择**，不据此新增本机实验/模型权限或擅改冻结协议。无需让用户重复授权已明确四宿主任务，四项结果如上单列。

对该方案本轮未实现/未测试，不扩新矩阵；只沿已证正常断点提出最低要求：

1. **receipt不是exact帧入队证明**：repair_received累计值>=N可能包含E1旧计数，且不证明queued未drop/匹配成功。复用原scan stamp、同候选/准入/deferred人口，按本次增量与实际应用stamp/点记录确认。有限预算内做一组真实输入控制，不造通用RPC。
2. **继续set_state旧尾会抹原生重估**：当前源仍`ep.frames[-1][2]`，REPAIR_GAP方案照抄；已有FAIL依赖/partial来源反例不关闭。最低按applied成功推进，保持原生重估状态与地图同逻辑时刻；不得用旧/deferred位姿灌状态充实际修复成功。无需新增框架。
3. **必须验修复而非已知标签反演**：注入参数/原始干净云/精确mask只能离线评分；若生产者直接读已知shift并反向应用，应标oracle/controlled intervention，不称算法估计恢复。同rigid shift经独立可信参考配准需与pose误差区分，缺可辨性UNKNOWN，不默认可观测。保持完整time/ring与raw scan stamp、冻结门，修复后用与求解分离的合法证据复核，不用旧原始云评价新修复云并直接套旧gate通过结论。

这些限定实际新交付的主张，不要求本机改算法或在这轮先完全部通用设计；已有预算下可以真实失败，但不能只靠repair_applied>0宣布修复成功。当前snapshot可信时刻限制沿旧证据，未修不机械重测。

## 5. 下一单一交付与自检

四个命名执行尝试已归档，不再重复发派任务/重跑两失败宿主追成功，也不自动安装独立FAST-LIO2。独立原版FAST-LIO2项当前缺构建，明确未执行及工作区事实即可，不能用NOT_APPLICABLE改写“未执行”。

**下一单一主线交付：在开发侧报告选定的有限损坏范围内，复用已有组件交一次实际修复测量→原生重估/内部地图→接回→E2，或具体接口首断点；选择/范围/执行状态由S1给实际回执，不能只再发“需要决定”文档循环。** 四宿主结果与能力限制保留，不能因本批已跑就宣布论文主线完成或机械又修LIVO全部问题；沿既定宿主事实说明选择，不挑有利ATE。

S1集成/实际产物一致，S2测量产物与host限定运行，S3门研究/旧调参停。自检逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE+实际命令/原件：真实损坏与修复来源、scan/点布局/准入人口、入队/应用身份、applied成功依赖、native完整状态与地图同stamp、接回/E2尾段/成本、独立评价及失败。未实施写NOT_IMPLEMENTED、未知UNKNOWN，不按文档行数/测试数升分。

A2/A9/A10原生观察矩阵局部进展，B7失败范围/机制认识保留；四宿主修复层A6/B4/B11仍未闭合，B10不同输入非公平主表，不全表新评分。本机无ROS/bag/tests/算法实验。

## 6. 发布

只保存本增量并追加历史/协作，工作树与main分叉而未merge，旧开发§66–68未覆盖；相对两版本明确。沿独立review提交/SSH推送，不合main、不删资产、不发布private。前push阻断已解除，remote review46fdbf9，开发是否已读本次意见待真实回执。
