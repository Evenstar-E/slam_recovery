# 0edc3d7：开发已恢复，协方差局部修复接受，重武装尚未贯通

2026-11-10。目标`0edc3d76a43ddbed396eaf2dd2733f48d4ecffc4`，跳过新合入的旧审阅/Auto-Review；真正新开发为04b7dd1、a1a371d、915213f、e1e845a、0edc3d7。已读AGENTS、评分标准、REVIEW§10，核既有任务归属；旧PID25412此轮不存在（此前曾被ssh复用），私人handoff未公开。不改算法/门、不运行ROS/原bag，不扩防御矩阵。

**有实质源码与开工回报，不能再称开发一直没有恢复。**本轮增加的是A7候选评价和A9/A10拒绝后生命周期组件，不是原生内部恢复/接回/E2运行；A4/A6/A8原生写回、B11完整链未交。无完整重评分。

## 1. 已恢复的责任与第一宿主断点

开发main实际采用用户“恢复原生、参数仍停、1研究＋2主线”至19e53b2；S1交三笔实现，S2回报`/tmp/wt-sim`、exp/m0-updated@b515ed5，S3回报`/tmp/wt-fourarm`、exp/gate-method-research@19e53b2及研究预算。这是开发侧实际回报而非本机在线工作树/进程核验，实际当前状态不能从16:20快照推断。

S2给出此前缺少的具体断点：当前FAST-LIVO2工作树无restore/checkpoint入口，`_state`、voxel map和LidarMeasures为内部状态；已有handleLIO、BuildVoxelMap/UpdateVoxelMap，但缺真实快照和从快照重放。无ServiceServer不等于所有恢复实现都必须ROS service；本机只接受具体实现缺口，不把它解释成技术不可行。其双事件包/900s预算仅计划，尚无新原件，不报已经跑完。

**用户较新05f7fc5转向交接仍有效**：S1/S2收尾当前具体任务/运行并保存产物后，立即核已有FAST-LIO2/MM-LINS/FAST-LIVO2实际接口，按最低真实新增工作选择一个宿主验证两事件。不继续绑定FAST-LIVO2全部问题；研究S3不阻挡。main此轮尚未含05f7fc5，最新接收/实际转向待回报。

## 2. A7旧producer模式翻转局部解除，不重开

新node先将平均world FIM搬到触发anchor body基，在该基添加原`.001I`并求逆，candidate两矩阵声明同frame；0edc3d7保留只有body segment才声明body的分支。科学门/epsilon未调，不重写正确transport。

本机60项受影响unittest（10模块）全部通过、1.058s，明确加载目标core；不是开发83全套的本机复跑。复用21fa650实际node原cloud/原参数/原case函数，在新source上绕过旧pin/main：

| world y | before/after | posterior covariance | mode |
|---|---|---:|---|
| 0m | 20/62.98293 | .513613665 | Mode3 |
| 20m | 20/62.98293 | .513539494 | Mode3 |

旧.513614→.469490、Mode3→2反例现不翻判，**这一本轮要求的局部范围接受，直接复用**。inner FIM world`1e-6I`残差仍约7.4e-5，本轮接受已声明的量级限制，不因非零残差扩通用gauge/更多平移扫描；不能说严格全部坐标不变量已证明，实际准入质量也未证明。旧cov>.5依旧有记录，不用新“实测.02–.11”覆盖它。

## 3. 有限终态有实现，但三个正常入口问题仍影响E2/帧安全

`wait_limit`默认None保留旧行为，关闭等待段存unresolved、rearm、detector.reset，方向合理。新单测能证明helper和报警关闭时的node继续路径，但未覆盖actual loop的无参考分支、真实报警和原先撤销帧。以下均使用实际loop/node/manager，不是恶意输入/假设并发；`lifecycle_probes.py`只构造正常输入，不改门/生产参数。

### 3.1 检测UNAVAILABLE时，等待期限不被处理

位置：recovery_node.py on_pair→_ingest_without_detection（约605/636）；新timer只放step_frame约250。同hall ICP的空可信参考，wait_limit1s，后续真实on_pair输入2/4/8s均UNAVAILABLE，状态仍WAITING、lifecycle events为空。期限超过8倍也没关闭。

最低解除：在所有配对输入共享的生命周期入口检查已声明期限，独立于检测可用性；未知参考仍UNAVAILABLE，不能伪造健康NIS或开放准入。沿现helper处理，无需新线程/定时服务框架。

### 3.2 reset/rearm之后仍使用reset前的报警决定

位置：transaction_manager_node.py约245先detector.step，250后reset/rearm，261继续读取旧decision。等待期间两帧NIS10，期限到的第三帧：先记录close/rearm，马上按旧QUARANTINED重开同旧onset段；manager QUARANTINED而detector HEALTHY/dwell0，segment ID亦与旧段相同。不是新E2的重新检测。

最低解除：先完成终态/重武装，再对当前输入按清空后的detector建立新决定/新dwell，不消费旧decision/onset。actual NativeClosedLoop还用`before is None and after is not None`识别新episode，close后同帧重开时before非空、旧ep.decided仍真；接线时按实际段生命周期识别新episode，不仅计manager重武装日志。不扩大状态框架。

### 3.3 被记作unresolved的旧provisional帧在rearm后重新晋升

位置：manager.py maybe_close_waiting_segment约500清active，但未处理provisional_queue；step_healthy约144会晋升整个旧队列。正常key7@.1s先provisional、E1@.5s撤入隔离，close@2s把7归档为unresolved，rearm后key8@3s输入，**7及factor7重新进入trusted**。这与“不提交旧段、可信图不变”的新契约相反。

最低解除：终态后保持该段provisional测量归unresolved/不得走健康晋升，保留实际数据和归档，不删除原测量，不添加repair marker代替它。复用同一旧帧及正常新帧控制即可验；这是本次持续链前必要安全修，不是全异常防御任务。

runner仍未接`--wait-limit-sec`且默认0，若执行侧走原run_native_loop.sh须在限定运行前接入并声明实际等待预算；这只是当前能力调用，不为挑结果调等待值或追加扫描。当前没有新宿主写回，不因node rearm称原生接回完成。

## 4. 空/畸形数值区分接受，不能解释错误输入层

core对空CandidateMap和畸形pose分别reason，after/gain未测null；三个新测试通过，candidate_record的_f能序列化None。局部报告修正接受，不扩schema工程。但node可从非空wrapper候选筛成0committable，不能都称“repairer返回空”。旧hall真实wrapper23hostpose/无参考→node筛空事实保持；solver失败仍封装旧hostpose的源码未改，沿既有最小失败语义随主线集成，不只改文案。

## 5. 下一唯一主线与自检

S1收尾必要生命周期正常修/已接受协方差并保存结果，S2收尾当前宿主具体断点/实现；随后立即按05f7fc5已有接口选择转向，在选定单宿主跑原生写回→接回→E2。已有A5/A9、transport、时间边界局部成果直接复用，不再把它们重开。若先受控接口测试，诚实标CONTROLLED_INTERFACE_TEST，不充自动链；完成一次真实完整链后单独向用户报告。

S3门研究独立继续，参数手调仍停，生产门不擅改，研究不作为宿主前置。主要仍原生工程接口/生命周期，当前三正常问题给最低修；算法独立质量/信息极限UNKNOWN，不新增模型/参数矩阵。下一实质交付给PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令、source/host/input/完整人口与原件，不交纯收到。

本机PASS：60相关unittest、旧producer正常例局部解除、空/畸形区分；FAIL：本节三个正常生命周期反例；BLOCKED：原生restore/writeback/E2暂无运行原件；NOT_APPLICABLE：ROS/原bag、完整83项/pytest、调参、模型实现、全表评分。`python -B -W ignore docs/review_20261110_0edc3d7/lifecycle_probes.py`退出0表示复现缺陷，不是fix通过。合并协作表同号追加冲突时保留用户转向和开发执行快照两者，未覆盖在手源码/私人文件。
