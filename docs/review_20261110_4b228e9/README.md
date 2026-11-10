# 主线/旁支验收 4b228e9（恢复后首轮）

范围833cdb5..4b228e9，21笔、32文件、约2.5k新增行。读AGENTS/A-B标准与交接第十部分，忽略stop.md（用户直接要求）。重点完整审T3a patches、hall稳定性/轨迹协议及来源关键字段；不宣称逐外部bag重跑或全部表重新评分。9/9 schema tests、25/25身份审计fixtures本机PASS，文档file ResourceWarning保留。PAT未使用/保存，现有SSH可fetch。

## 主线实质推进与未完成

新增T3a原生控制与hall四次运行、hall同400帧GT252匹配轨迹补证是主线归档进展。T3a新build四次BAD/BAD/GOOD/GOOD说明此执行改动未使结果稳定；hall未注入100–160窗四次unsupported .2282–.2790、NN support1可描述该场景较窄离散，不能作为过滤修复repeat成功。不同参考（hall5cm体素proxy vs room完整proxy）影响unsupported水平与离散，不移植阈值；不宣布room数据集独有根因。

## A/B映射（局部复核，非全表加分）

- A2执行身份/A11共同集合，B6机制/B8重复稳定性：增加归档控制，仍局部条件证据；不提升到3。新shared library历史receipt未绑定，维持未闭合。
- B4净修复：hall轨迹与原proxy效果可并列有限正结果；GT仅252/400条件帧，缺46/446，成本/同步敏感性仍诊断；不提升完整通过。
- A3/A4/A6/A8/A10及B5/B11原生在线闭环未本轮验证，不重新评分。历史16/36与11/36不自动继承当前总分。

## 主要验收限制：T3a并未实现“确定measurement grouping”

src_LIVMapper.cpp.t3a.diff使用AsyncSpinner(1)，main保持sync_packages并在失败后wait_for20ms；无ready predicate，det_mtx并非callback更新buffer的锁，callback notify也不固定lidar/image/IMU分组。唤醒/timeout和到达顺序仍随调度变化，改动还把原单线程spinOnce/处理改为callback与处理并发。未读完整远端宿主源码，不能断言发生数据race，但必须核共享buffer/state锁。

归档r1/r2 init_iter37/73、first_pkg时间不同，说明测量消费/初始化还没相同。结论应“该唤醒/并发改动未稳定”，不能说已移除wall-clock phase后排除S3。下一主线先输出确切group/sample IDs与初始化样本，再用消息时间的确定分组或回放屏障做单因素控制；不同时改IMU init窗口。如果无法安全适配宿主，BLOCKED并进行工程/机制复审，不无限加wait机制。

## 归档机器字段相互矛盾

room02_T3a_enriched_results顶层same_mode=true、criterion.verdict=S3_ACCEPTED_AS_SEED仍在，而four_runs_same_build BAD/BAD/GOOD/GOOD。build_comparison文字说“两build内samecriterion满足”也与buildB四次split矛盾。旧A仅两次局部接受可保留历史，但权威current verdict应不支持稳定，明确build/library身份，抽取器不应拿旧True。属旁支结果一致性修复，随下一主线交付，不单发文字循环。

## 下一主线与旁支

主线：实际group/IMU初始化消费身份trace与最小安全确定分组对照；冻结source/config/input/rate、准确receipt包含executable+实际加载liblaser_mapping.so/依赖，比较分组相同与否、state首差和服务/地图指标。T3旧库hash缺口不强行补成PASS。

旁支：当前verdict字段、library receipt门禁、同步规则命名集中处理。run_raw_vs_repaired time_sync写nearest75ms，而调用pose_lookup为nearest20ms或bracket75ms，应与实际一致；schema全key约束只保护结构，不验证数学/独立参考，不靠key测试数量加进度。

开发侧每轮先§10.12自检PASS/FAIL/BLOCKED/NA+证据，再报告主线实际交付与旁支分工。今日日报实际23:35任务，昨日审阅侧日报失期须补档注明编写日期，不装作按时完成。新结果不自动恢复在线/任意传感器/泛化主张，不以原型分数许诺发表。
