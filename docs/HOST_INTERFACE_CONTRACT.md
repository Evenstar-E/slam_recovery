# 宿主接口记录：链条优先，工程诊断不设放行门

面向：S1/S2/S3与独立审阅。根据用户2026-11-13最新直接裁决，首要任务是**把真实链条跑通**，不是先证明工程、算力、内存或接口文档完备。此前本文件中的“契约前置”“未过冒烟不得进入整链”和硬件预算门不再作为研究原型的开工或复验条件。

**已有授权的v7构建和整链run直接执行：不附加启动退出型`--require-contract`，不以七步冒烟、CPU/RSS、回调耗时、内存、看门狗或接口检查数量阻止放bag。其余已授权输入、事件戳、窗口和停止预算不变。**

## 1. 唯一主线与当前交付

当前只看同一次真实运行的：

**E1实际到达→宿主原生接管或修复动作→后继输入继续→重武装→E2实际到达→尾段与退出状态。**

v6两次run已交E1 takeover、abandon/rearm和final HEALTHY，但E2未到达；这不是完整二事件通过。下一次运行应直接针对E2和尾段取得结果，不再先围绕工程门空转。E1未修复、E2未到、宿主停发等都按实际结果报告，不能用协议、测试数或HEALTHY替代链条。

ALI-H和自动检测沿已有实现并行接入、评价；科学判据用于判断结果，不设为允许运行的新工程门。无标签或参考时相应性能写NOT_EVALUABLE，但不因此停止原生链条。

## 2. capabilities.json是运行证据，不是启动许可

```json
{
  "commands": {"snapshot": "YES|NO|PARTIAL", "restore": "...", "hold": "...",
                "reprocess": "...", "set_state": "...", "measurement_relay": "..."},
  "checkpoint_excludes": ["imu_preintegration_cache", "deskew_cache"],
  "semantics": {
    "apply_stamp": "YES|NO",
    "ack_levels": ["deferred", "applied"],
    "checkpoint_validity": "until_re_slam|run",
    "publish_gating": "isPublish|always",
    "profile": "native_recovery|legacy"
  }
}
```

文件和字段用于解释实际行为。缺失、PARTIAL或语义不完整时保留`UNDECLARED/PARTIAL`及实际ACK，**不再仅因声明不全而在启动前退出**。不得伪造能力或把queue计数写成update结果；这与是否允许继续跑链条是两件事。

## 3. 只限制具体不安全动作，不卡整链

| 实际情况 | 动作级处理；其余链条继续 |
|---|---|
| host不支持reprocess | 不发该命令，记NOT_SUPPORTED；继续观察原生接管和后继输入 |
| host不支持restore或cp已被re_slam失效 | 不回滚旧图，记拒绝原因；不得伪称恢复成功 |
| 宿主正在休眠/重建 | 让宿主原生策略先执行，不与其抢地图；记录是否恢复发布 |
| apply_stamp缺失或实际cp晚于边界 | 保留真实时间和限制，相应“合法cp”主张不通过；不把整个run改写成未运行 |
| queue与update回执不一致 | 分开记录，不把入队写成真实重估；不以字段补齐作重新运行前置 |

只有实际输入身份错误、状态/地图安全会被破坏或当前用户明确停止时，才限制对应动作或运行。**性能不足、成本偏高、接口不漂亮、可选检查未做均不是开工门。**

## 4. 冒烟与工程检查改为按需诊断

- 七步冒烟不是进入整链的前置；已有ctrl2结果可复用，不要求每个新版本先重复。
- 不与整链共用单槽cmd/ack并发冒烟；确有具体接口失败时，才在已有授权内做单独、最小的诊断。
- `--require-contract`在本轮不作为退出开关；契约问题只记录，不阻止bag启动。
- 单元测试、源码断言和文档检查用于解释变更，不以数量作为允许运行或主线完成的条件。

## 5. 算力、内存和时间成本只测量，不设阈值

`bench_frame_cost.py`、CPU/RSS、pose/scan callback、积压和吞吐均为**REPORT_ONLY**。本任务不使用`--max-core-fraction`或任何隐含等效阈值阻止运行，也不要求先降采样、调参或优化到某个核占比。

已有成本数据可用于解释宿主时序，但不预先当作阻塞根因。只有实际run显示成本已经导致具体输入丢失或宿主停发时，才在后继诊断中处理；未阻的下一次链条运行不等待该分析完成。

## 6. 以宿主原生机制为主并如实验收

- 使用FAST-LIO自身的`re_slam`、`Issleeping`、`Isbuilding`和发布状态，不照搬FAST-LIVO2机制；
- `reprocess=PARTIAL`只称有限原生缓冲重放；宿主接管、真实修复和安全拒绝分别记录；
- E1 takeover+rearm不等于E2通过；原生停发导致E2不可达要写BLOCKED/NOT_EXECUTED，不事后移动事件冒充原协议通过；
- 保留实际source/config/input、原命令、事件、状态转换、输出和退出原因。成本未知写UNAVAILABLE，不新增预算门；
- 冻结科学评价标准不用于制造通过，也不转化为工程开工门。四宿主最终需求和FAST-LIVO2后置不变。
