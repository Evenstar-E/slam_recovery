# A7补验与OFF增量：限定最小解除，结束无假设机制排障

日期2026-11-10。A7源码目标 `4255cbe601263e458e772c08f9fce83bc36307e3`（aa42031/b571b9f/56ae4e4）；追加OFF归档目标 `f415c87ac582b0384679721e3a735ab12e6a0772`（56aa1ae/f415c87）。两版本A7源码相同，已核。只读审阅/局部代码执行与归档核读，无ROS/bag原生运行，无算法修改。私人handoff不发布。

## A7结论：有实质实现增量，整体尚未闭合

接受显式TangentFrame、混frame/anchor/order拒绝、伴随矩阵及information transport公式。真实FIM producer默认Jacobian为[(p×n)^T,n^T]，与当前rot_trans左/空间twist伴随符号一致。node使用触发帧pose搬运该body信息/弱方向，candidate world点FIM在共同world原点平均；不要误改成onset/checkpoint pose。

目标源码核心**60/60 tests本机PASS（主会话2.030s）**。新增negctl能抓旧混系且新契约例通过，但仅纯平移弱方向、candidate covariance固定0.1I，不能验同物理协方差的全局重表达。存在两个普通合法平移即触发的错判；不是恶意输入、极端资源异常或人为故障注入。

### 1. 搬运后重新单位化weak direction破坏信息二次型不变性

`slam_recovery/core.py:408-415`重新按world欧氏长度单位化v。正确transport应保持v_B^T L_B v_B=v_A^T L_A v_A；Ad含平移并非正交，重新单位化实际再除||Ad v||²。

本机重复项目真实默认FIM producer：rng0生成400点，before=0.5cloud、after=0.8cloud。producer弱向量为旋转方向[0.77557,-0.52541,-0.34990,0,0,0]。按正确公式搬运信息/协方差，所有辅助门证据相同且协方差均小于0.5：

| world y平移 | before信息 | after信息 | covnorm | mode |
|---:|---:|---:|---:|---|
| 0m |19.0337|48.7263|0.02305|MODE2 |
| 2m |4.8858|12.5075|0.12136|MODE3 |

翻转来自信息单位化，物理场景没变。独立审阅还用真实node FIM/holdout/paired/candidate路径得到同类0m/2m翻转；固定detector报警仅用于控制事件入口，无原生数据。本机保存的最小脚本直接调用producer和gate，未冒称完整native实测。

### 2. world原点下协方差谱范数不平移不变，缺协方差坐标契约

`core.py:517/583-587`将after covariance谱范数和固定sigma_tol比较；node :637-645由world FIM求逆，before propagated norm仍body。P'=Ad P Ad^T正确重表达后的普通谱范数可随原点改变。CandidateMap有info_after_frame但没有cov_after_frame。

独立于问题1：合法纯trans-x弱方向，SPD信息diag[60,60,60,30,5,5]，P=L^-1，world y平移0m/5m后before=20、after=30完全相同，covnorm0.2→0.628026，MODE2→MODE3。删v单位化仍不能解决cov问题。独立node候选例也在0m/7m得到相同NIS/PASSED与不同mode。

命令：`python -B -W ignore docs/review_20261110_4255cbe/a7_gauge_probes.py`。两项反例已本机再次复现，不编辑算法。脚本成功是错判存在的确认，不是A7验收通过。

### 最小解除与范围

冻结一个有明确原点和尺度的评价切空间/度量。可把触发scan body anchor及T_world_anchor保留，将candidate information和covariance一起搬回该固定body基，在原body单位弱方向与同基norm下比较；等价显式transported metric方案也可。不仅删单位化、不仅换frame字符串、不调门限救成绩。

加真实producer产生旋转弱方向的非零平移例，以及正确covariance搬运跨阈值例；同物理配置的before/after/cov门指标和mode应不变。只阻断依赖A7的候选准入实验，不要求重跑已有ON/OFF trace。aux未明确frame时在不用aux的当前范围排除即可，不扩无关路线。

E3新body[ref_scan]声明仍覆盖多帧各自原点FIM直接平均，独立AST复核得到共同基与直接平均差异；属于旧producer加新标签未闭合。当前事务/trace不消费该E3效果时延期，不为它重跑主线或另开修审循环。

## OFF追加交付：接受执行记录，不接受完全排除trace的结论

两OFF原receipt已入仓，状态OK，各800 odom，库同为b5255dd3，与ON20df3d3f分开。四receipt输入/config/script/exe SHA相同，rate1/drain40，planned kill明确。结果JSON的各output SHA与receipt一致；OFF trace_file为null，符合不开trace。

**原四输出bag仍仅/tmp远端路径，本机没有重新计算OFF统计。** 归档OFF-OFF欧氏互差max729.0016m、p95 580.586m、330/800超过1m；ON-ON max355.1595m、p95 343.0163m。它与此前CSV1766条STATE的max单坐标309.7062m不同人口/度量，不是互相纠错，不能直接混表。

`TRACING_IS_NOT_THE_MECHANISM`/“run variance, not tracing perturbation”过强。支持的有限结论是：**OFF条件下也观察到严重运行分歧，trace开启不是该现象出现的必要条件；其贡献、放大/抑制和完整根因仍未确定。** 两重复不足以确定方差分布、效应不存在；ON/OFF是不同build，跨buildpair仅参考。无GT/ATE，仍不知道哪一趟贴近参考。别用中位1.7cm掩盖尾部米级分歧。

到此有足够证据结束本轮无假设“排除trace/分组”循环，不要求新增无限重复、默认构建或全状态日志才能承认现有观察。保存现负结果与UNKNOWN，回到限定修复/原生适配；若重复不稳确实阻断目标结果，开发主会话给预算内一个有区分力的适配方案，不继续逐字段排除。

## 三会话下一任务包与自检

| 分类 | 单一交付 | 依赖/验收 |
|---|---|---|
| 主线事务会话 | A5/A9正常路径帧归宿/后续时间与两事件闭合，准备限定native接回 | 原反例+正partial retry；不因A7/trace旁支停所有工作 |
| A7并行会话 | 固定评价切空间，联合transport info/cov及方向度量 | 上述两普通gauge反例通过；用于下一准入试验前必须解除 |
| 主会话集成/消费旁支 | 结束本轮trace排除法，保留ON/OFF观察和UNKNOWN，确定native最小接口/执行顺序 | 不再以PGID/恶意CSV/生产完备性扩大阻断；E3延期到实际消费 |

A7实现属于A7/B2保障进展，ON/OFF观察属于A2/A11/B6/B8证据增量；不做完整新A/B评分，不据60tests宣称工作包3分或修复收益。开发側交接前逐项PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令/证据、主线真实推进和调整分工；不为收窄一句话再交纯“接受意见”。
