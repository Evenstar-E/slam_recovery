# e82d900审阅：受控检查点与全量替换通过，连续接回与自动检测仍待交付

- 面向用户、开发S1/S2与独立复核者。
- 目标 `e82d90041c090dcb8a9df6402ebfdb98f465a0b8`，比较 `d193680aa6f3bb7945e8bf01fdd2d8932819c49c`。本轮SSH fetch成功；review HEADddd0fb7，未merge main、private未提交handoff保护。
- AGENTS、A/B标准及REVIEW§10已读并复用未变内容；实际三Cron由repair-f3持有，无旧owner双写，20min/忽略stop.md的用户直接要求优先。旧参数暂停，不重开四宿主矩阵。本机不改算法/代host。

## 1. 新主线成果：前轮晚快照/部分应用在本次受控范围局部解除

| 项 | 实际证据与状态 |
|---|---|
| 运行身份 | repair `055727Z_148998`、sham `055931Z_151459`；driver SHA各匹配b42544e及target，实际加载库9c0330be匹配新构建记录；输入/config/可执行文件hash同 |
| 提前按戳hold/snapshot | 主循环在第一个达到声明戳的测量组处理前执行；两snapshot stamp1627785276215170048、frame221，deferred apply组时刻1627785276.281966925，late66.797ms。PASS实际应用，不是只收deferred ACK |
| 修复测量全量替换 | 两臂同23个candidate pose stamps、同23个published scan stamps；repair shift−0.40，sham0；各received/applied23、leftover0、同124group。PASS限定替换/原生重放；旧7/12部分应用不继承到该run |
| 重放时间支持 | 两实际起止均 `[1627785276.281966925,1627785280.347787857]`，payload end1627785280381185627；起止/数量一致接受；+100ms是事后观察22/23后新增并在两臂共用的工程常量，不称未见结果预注册 |
| 地图输出 | repair17811vox/335054点、sham17316/328516，差495vox/6538点。支持实际替换在宿主重估中执行及观测到差异，不等正确几何/净收益 |
| 接回尾段 | resume执行、决定后317/300配对帧；截断后缀399/372仍skip+clear，未证完整catch-up；不是有效持续恢复PASS |
| E2及自动检测 | 两run各一episode/decision、detection off，E2 NOT_EXECUTED；两事件旧024337Z是raw replay/受控接口，不补本次实际修复E2 |

两者最终HEALTHY伴wait_limit_closed与ABORTED rearm；deferred人口/未解决段保留。native失败诊断repair0/sham21，不能以门/终态均通过称全流程无失败，也不把21直接解释为全部重放失败。native完整state/map等价未独立验，质量指标仍UNAVAILABLE。不报首次实际修复有效整链/E2完成。

## 2. “唯一差别是测量修正”的主张需缩小，非要求随机逐值相同

本机读取**发表修复前**的deferred snapshot应用原log，两者时刻/frame相同，但：

| snapshot字段 | repair | sham |
|---|---|---|
| voxels/nodes/points | 15905 / 33641 / 308821 | 15902 / 33624 / 308223 |
| state_pos | 6.192556,3.582319,0.107959 | 6.192642,3.580536,0.103953 |

这不是hash错配或必须逐位一致的新增验收门。随机原生运行允许这样的前缀差异、总体效应需看量级/趋势/失败范围；本轮只有一对、没有完整checkpoint状态/map字节或运行级不确定性，故**不能把全部495/6538及resume后state差断言唯一由修正造成**。接受这是匹配时间支持的受控对照、组件作用观察，不接受“全其他状态相同”的事实描述。无需为了追逐值一致无限再跑；已有数据报告差异与限定即可。

尤其resume ACK发生在不同后继消费边界，且candidate尾set_state主动覆盖pose，不能把resume状态差或set_state接近当独立重估/物理收益。测量是否有效可在声明注入范围做独立离线评价，自注入本身不禁止受控效应验证；只是不能外推真实自然故障或自动恢复。当前没有合法质量/共同支持评价，地图点数不是正确几何数。

## 3. 连续输入仍有已证首断点：固定评估区间不等完成接回

v3部署patch仍原样保留`reprocessCheckpoint`的end之后continue与末尾`replay_buffer_.clear()`/capture=false。本次实际truncated399/372，都是在此前native live消费后存入buffer的后缀；restore后只重推124group便清空后缀。新提前checkpoint和100ms终点补偿解除此前部分修复，却**未解除已消费输入在回退后的重推归宿**。

前轮source-bound反例[1,2,3,4]已消费→bounded到2→clear3/4→下个live5仍适用，本轮不重造/代跑host。不能拿后续paired317/300证明3/4也已重推。S2最低复用现buffer保后缀，原生state/map按序catch-up到实际接回边界；或显式拒绝不支持的回溯/不称持续接回完成。S1只按实际应用、追赶、公开状态一致推进成功与resume，不以OK/deferred或计数替代。

旧坏云candidate先准入后才产新云、candidate尾set_state覆盖native完整状态、baseline None当0的正常反例source未改，保留但不重复测整旧台账。后继应交物理一致新测量/对应重估状态，不为保旧Wilson通过把不同物理候选搬入成功。

## 4. 提前arm与deferred ACK的准确范围

- `OK hold/snapshot deferred`是**接收并安排**，不是完成应用；本次应用由native deferred apply日志证实。client会把此ACK记ok并清pending，不能只用events.ok当全state/map已恢复。
- main仅对`min(scripted_trigger_stamps_ns)`预排一次；在线检测和第二个scripted事件没有同样提前checkpoint保证，open仅幂等hold。code-review low指出该边界，经目标source/control确认；不把删除晚snapshot判成必须恢复旧错误入口，也不要求在线预知异常时刻。最低声明受控首次保证与在线/后继能力界限，第二事件用合法可信checkpoint/不支持则拒绝，不能由本对run直接外推E2。
- 新100ms终点补偿避免本次最后测量group未覆盖，支持此次23全量匹配，不将100ms称一般所有输入适用的科学阈值或偷偷改门。

## 5. 本机实际检查

[原件reader](check_archive.py)、[结果](archive_checks.json)：`C:/Python315/python.exe -I -B D:/REPAIR/slam_recovery_upstream/docs/review_20261112_e82d900/check_archive.py` exit0，41/41本轮changed清单SHA一致；核source/加载库、完整candidate与published stamp列表、snapshot原字段、实际重放/应用/后缀及生命周期。不执行归档脚本、不读远端bag/binary或重建host。

[源码控制](run_checks.py)、[结果](local_checks.json)：`C:/Python315/python.exe -B -W ignore D:/REPAIR/slam_recovery_upstream/docs/review_20261112_e82d900/run_checks.py` exit0，target Git blob内存加载、其他package源码无目标差异。1项新deferred receipt测试PASS0.040s；actual client stamped hold/snapshot payload及收据串行PASS，actual episode opening仅hold、100ms常量与v3后缀skip/clear核。receipt控制不冒native应用实验。

其余多命令checkpoint test因Windows fake-host rename已存在cmd.done边界未跑；repair_sync导入pytest辅助未跑，不装/shim；未变旧cloud/freeze测试不重跑。host构建log仍有Built target laser_mapping与vikit ABI Error/整体失败，不称全构建PASS；部署可apply为开发报告，本机未独立重建。v3 patch SHA核为46648b4c082fd52ee74ea1e8677d2ad756de66473a73c936912d01d669d1ab28。

## 6. 最新UNAVAILABLE诊断任务与下一单一交付

用户明确要求的[逐帧及点级取证任务](../UNAVAILABLE_DIAGNOSTIC_TASK_20261112.md)已以ddd0fb7独立review发布；目标e82d900早于该交接（14:12 vs14:21），**不能指控开发无视尚未送达的任务**。目标无任务文件、_record_diag仍缺support比例/raw失败/样本、2000截断，未有检测on新原件；当前只说尚未在可核main实现，实际接收待S1回执，不等远端一定没做。

S1集成用户诊断、复用现计算不改变检测/阈值，S2一次现预算检测on归因或具体原件无法回推的缺项；native修复/E2并行，S3研究专用、旧参数停。诊断必须交真实每帧两个条件及计算相关量、旧值来源/年龄、当时点/参考身份与分支计数，不只打印UNAVAILABLE或单NIS。

**原生下一唯一主线**：复用已接受全量测量替换和时刻接口，交物理一致的实际修复→完整native state/map→保后缀追赶→接回→E2尾段，或实际不支持范围/首断点。不再无限预置单事件A/B代替未知起点自动链，四宿主前批边界保留、不重新跑失败追成功。

开发自检逐项**PASS/FAIL/BLOCKED/NOT_APPLICABLE+实际命令和原件**：source/input/config/library，检查点同stamp完整性/支持界限，真正修复候选与应用人口/丢弃，后缀catch-up/native成功依赖/接回E2，质量/完整人口/成本/失败未知，检测on/非oracle及UNAVAILABLE诊断原件；未做明确NOT_EXECUTED/NOT_IMPLEMENTED，UNKNOWN如实。不降冻结门、不做新大参数/防御矩阵。

A2/A4/A6/A12受控checkpoint/全部替换局部推进，旧晚snapshot该范围解除；A5/A8/A9/A10连续输入与物理状态、A3/B3自动检测及B4/B11完整链仍未闭合，不全表升分。仅独立review增量提交SSH推送，不合main、不改算法/历史、不公开private；发布不等开发接收/执行。
