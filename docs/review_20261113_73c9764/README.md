# 授权run独立审阅：构建成功，双快照晚于边界，整链在E1前原生停发

面向：S1/S2/S3与用户。固定2026-11-13 13:49:35（UTC+8）授权run main `f1bd803dbcbb60419d50dd70491768c54c4f22dc`、growth `163cd1dff58be73ad4f70795bf799ed0bd8fadc9`；前段集成版本main `73c97643b08a3e4efc91f6a14b1093fdf79779ce`。发布前补核13:54 main `4f7567ee6870ddf8faaf03420db81ba5fc245b14` 的离线诊断/看门狗增量，授权run原件未变。跳过已验收审阅合并。四Cron仍repair-f3单owner，私人文件未动。

本机只读授权run原件、固定源码并运行独立确定性控制；**没有代跑ROS/宿主、重建、安装、调参或重试**。开发记录的唯一一次v4构建/run已经消费，本报告不授予新一次。

## 1. 总结：有真实工程推进，但整链和合法checkpoint均未通过

- **构建PASS（归档）**：`build_exit=0`，binary SHA由 `df27a24c…` 变为 `86f85025…`；本机没有binary实体或独立重建，不冒称本地复建。
- **hold延期生效**：E1/E2两组hold均比声明目标早约78ms，启动即hold/空图问题未复现；host 1137 ingested、1113 quarantined，无replayed。
- **checkpoint边界FAIL**：两张snapshot都晚于目标，不能接受“v4延期边界PASS”。
- **整链FAIL/BLOCKED**：driver最后帧诊断相对首个host帧94.699s，E1在约116s尚未到达；scripted fired为空、0 episode、0 candidate，reprocess/E1→接回→E2未执行。
- **原生停发直接观测成立、唯一根因UNKNOWN**：host.log有8次Over-degeneracy、163次IMU Initial Done；停发早于第一次armed hold，不能像第5次那样归因启动hold，也不能无证据唯一归因负载、算法参数或恢复代码。

运行wall 260.588s、driver PID峰RSS 2,174,264KB仅是相应scope，不是完整host+recovery成本或净收益。

## 2. 两组快照实际都晚于声明边界

[授权run复算](authorized_run_checks.py)及[保存结果](authorized_run_checks.json)直接读取 `run_summary.json` 的原始actions：

| 事件 | target（hold payload） | hold实际stamp−target | snapshot实际stamp−target | snapshot map_points |
|---|---|---:|---:|---:|
| E1−2s `1711547997352267771` | 同上 | **−77.818ms** | **+422.134ms** | 221815 |
| E2−2s `1711548111452267771` | 同上 | **−78.868ms** | **+521.081ms** | 1347 |

两张snapshot的 `wall` 都恰好等于对应hold的 `ack_wall`，说明实际写入发生在hold applied之后，而不是目标前预武装。第二组1347点是中间原生re_slam后的地图，不能拿来证明恢复重建。

### 直接接口原因：真实RECEIVED格式不触发提前配对

真实host `ack_received` 为 `RECEIVED snapshot`（无`wall=`）；当前 `_read_received_for` 只有解析到 `wall=` 才返回接收时间并调用 `_pipeline_armed_pair`。因此真实host格式下，提前发送snapshot的路径不触发，outbox仍等hold applied，与上述两组实测晚边界完全一致。

**最低修正（S1/S2）**：统一真实host与client的RECEIVED契约，不能要求测试fake有wall而生产host无wall；用生产格式 `RECEIVED hold` 做双命令控制，证明snapshot在hold applied前已经写入host deferred队列。两张实际applied快照都必须 `stamp_ns<=target`，不能只验hold。

另有一个独立确定性控制已确认：两个pending命令共享一个ack文件时，若host FIFO批量写完hold applied和snapshot applied而client未及读取，最后一次snapshot ACK会让最前面的hold一直pending。当前19项文本契约及顺序fake没有覆盖这种合法时序。需要每个命令可唯一对应的applied回执或原子边界事务，不能靠单文件最后写值推断两条都完成。

## 3. update回执fallback仍调用错接口

[集成控制](integration_checks.py)及[结果](integration_checks.json)在当前类上实际复现：

- `_read_status_update_receipt` 调用 `cp.status()`；真实CheckpointClient的 `status()` 返回本地摘要（enabled/events/holds等），**不会写status命令**。控制结果：receipt=None、cmd文件未创建。
- v4 reprocess ACK仍只有 `repaired_fed`，没有 `repaired_in_update`；因此这个fallback在真实客户端上不能取得新增update证据。当前fake CP把 `status()` 定义成发命令，和真实接口不同，246项测试未覆盖此差异。
- 即使改为真正的status命令，也必须等待相关replay/update边界；reprocess ACK在入队时即返回，立即读到0不能直接证明未消费。

**最低修正**：S1使用真实status命令接口，等待相应replay完成或目标update回执，保 `repaired_fed=queue`、`repaired_in_update=actual update` 分开；fake与真实CheckpointClient保持同一方法语义。没有回执继续None，不默认True。

## 4. `fully_accounted=true`仍只是driver自身，不是全宿主归宿

授权run driver为949 paired/ingested、0 quarantine episode、949 never_quarantined，`fully_accounted=true/fully_decided=true`；host却有1113组quarantined。两者人口不必机械相等，但当前没有跨层关联，不能把driver的true写成整链全输入已归宿。E1/E2未触发时它更不构成恢复成功。

下一次结果至少要按声明时间/update身份对账host fate与driver帧，保多对一和未配对，不能用最近邻贴接。可用离线原件完成，不必为生产部署另造框架。

## 5. 阻塞分类、最小解除与下一单一交付

- **工程已证**：RECEIVED格式使配对未触发、共享ACK可覆盖、status fallback调错接口；两张快照实测晚于边界。S1负责client/driver，S2负责host receipt/deferred与原件。
- **原生宿主表现**：约95–96秒退化停发使E1未到，直接阻断整链；发生在armed hold之前。其算法/输入时序/环境唯一根因均证据不足，S2先用现有log与已归档同bag运行收窄，不盲目新跑。
- **13:54离线诊断补充**：独立run在声明E1/E2附近出现原生休眠缺口，授权run却提前约95秒停发，二者不能混为同一已证机制。开发已撤回“逐组点云深拷贝”候选；shared_ptr保活/内存、循环与stat开销、driver竞争仍只是候选。新增pose-stale看门狗只负责报错停止，属于支持保障，不是ALI-H检测或恢复；A/B/C诊断仍需实际授权，不能当已执行结论。
- **算法/科学证据**：真实ALI-H导出、独立正常前缀与故障标签仍未闭合；自动检测、净收益NOT_EVALUABLE。
- **参数**：无同版本同人口调参规律，禁止为避退化或制造通过扫阈值。

**下一单一主线交付**：S1/S2先交生产RECEIVED格式下的双命令控制与真实update读取修正；再次获授权后，同一固定协议验 **两张checkpoint均不晚于边界→E1真实触发/决策→真实update/map→实时输入→E2**。若另把E1/E2前移到健康区间，必须事前冻结并标为新的受控接口协议，不能回填为原E1/E2或自动检测通过；换输入同样需要相应授权。

本轮真实构建与负结果属于工程局部推进，A4/A6/A10/B11仍未闭合，A3/B3/B4无新成绩，不全表重评分。两个独立Python `-I`控制均exit0；不重试授权run、不改算法、历史或科学门。
