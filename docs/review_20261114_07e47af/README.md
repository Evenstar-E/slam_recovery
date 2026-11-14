# 最近两小时主线总结：部分推进，首次paired-benefit通过但仍无accepted原生修复

面向用户与S1/S2/S3开发侧。窗口按实际fetch时间固定为 **2026-11-14 19:24–21:24（UTC+8）**，起点main `2004e4e8a3d5b7cd8762791327830963c4f85ceb`，终点 `07e47af8286a2801f967a5bdbb5e9e6764ae881a`。同时完成最新main增量审阅。

已读AGENTS、PROJECT_HISTORY、A/B标准和REVIEW§10。repair-f3单独持有20min/2h/日报任务，无旧repair-3e活owner双写。以下只使用新增提交、开发归档run和可获取源码/原件；本机未代跑ROS/宿主、未修改算法、未新起调参或大实验。

## 1. 总结判定

**部分推进。**

两小时内出现了真实候选方法、注入人口和新序列运行，最新run首次在本FAST-LIO宿主真实链上取得高Wilson的paired-benefit结果。这是有意义的候选/门证据，不再只是生命周期或日志推进。

但最终目标仍未达成：**所有候选均未accepted，repair clouds=0、reprocess=0，没有真实测量修复进入原生update/map。** 自动检测、ALI-H真实M/I、净收益和完整两事件恢复没有闭合。

## 2. 窗口内实际交付

| 版本／run | 实际结果 | 主线解释 |
|---|---|---|
| `2c6a930`：v9d/v9e注入偏置 | 两run各60帧+0.5m注入；E1分别7/40、0/40，均拒绝；修single-rigid incumbent初值接线 | 真实受控负结果，不是accepted链；不同窗口/初值不能当参数比较 |
| `375e1be`＋`3e18238`：运动先验多尺度 | 自然2/21、1/19；注入9/40、E2无候选 | 有真实方法实现，但未按冻结契约排除未收敛帧，且注入run发生跨事件checkpoint覆盖，不能宣布方法确认失败 |
| `1058932`：campus_2_fl | E1 4/38拒绝；宿主休眠后90秒终止，E2未触发 | 新序列只产生E1负结果，E2 NOT_REACHED |
| `07e47af`：campus_1_2_fl，host_poses | E1 36/41、Wilson 0.770；E2 41/41、Wilson 0.938 | paired-benefit首次显著通过，但最终均未提交；host_poses不是实际修复器 |

这些交付说明候选比较链已能区分“常速incumbent”和“移动窗口宿主位姿”，但不能把宿主自身位姿胜过常速外推直接称为测量修复或地图净收益。

## 3. 最新run的完整门证据：0.5m重入不是唯一约束

开发文本称E1/E2都被0.5m重入连续性界拒绝，并提出“静止窗口＋注入偏置”可同时满足收益和连续性。原件与源码不支持这个充分性判断。

| 门腿 | E1 `cand_0000` | E2 `cand_0001` |
|---|---|---|
| 改善帧／Wilson | 36/41，0.769922 | 41/41，0.938086 |
| candidate状态 | `paired_benefit_status=PASSED` | `paired_benefit_status=FAILED` |
| 重入时间 | 4.199651s | 15.400101s |
| 源码时间包络 `0.5+2Δt` | 8.899303m | 31.300203m |
| 实际重入距离 | **4.089475m，PASS** | **74.664804m，FAIL** |
| 弱方向信息要求 | 18.231571 < **36.037668**，FAIL | 31.068320 < **54.883795**，FAIL |
| holdout NIS要求≤2.5 | **2293.048515，FAIL** | **38.593832，FAIL** |
| checkpoint | LATE_AFTER_BOUNDARY | LATE_AFTER_BOUNDARY；armed lead −1.782s |
| 最终 | Mode 3，未accepted | 边界连续性拒绝，未accepted |

因此：

1. **E1的重入并没有失败**，4.089m在4.20秒运动包络内；其最终Mode 3还包含信息增益和holdout失败。
2. E2的74.66m确实超过时间包络，但即使解决重入，信息增益和holdout仍然失败。
3. “静止＋注入”至多针对重入条件，**没有证据表明会同时解决`tau_info_kappa=2`和`tau_val_nis=2.5`**，不能作为accepted的充分方案，更不能为了过门选择容易窗口后外推一般有效性。

完整计算见[review_checks.json](review_checks.json)。

## 4. 仍未完成与阻塞归因

### 算法／科学证据

- 当前ICP候选多次未收敛且改善不稳定；运动先验run的候选人口又不符合冻结契约，不能据此证明信息不可恢复或方法无效。
- 最新host_poses候选证明移动窗口中常速incumbent可以被显著优于，但不证明测量污染被修复；信息增益和holdout仍是实际科学门断点。
- 没有独立GT/合法参考证明净收益，不能把candidate/incumbent残差比0.68或0.06直接当地图准确率或ATE。

### 工程／原生集成

- 冻结方法写明未收敛帧不进入候选，实现却接受`ITERATION_LIMIT`：自然E2和注入E1候选全部由未收敛帧组成。
- v9g第二事件snapshot在第一事件restore前覆盖checkpoint，E1恢复到晚自身边界32.500372397秒的未来状态，属于实际状态/地图安全反例。
- 最新run两次checkpoint均晚边界；E2武装lead为−1.782秒。option②前一run的E2则因宿主休眠与90秒终止未到达。

### 参数

没有同版本、同人口、单参数变化的效果/代价与改善上限证据，不启动ICP次数、Wilson、信息增益、holdout或重入阈值扫描，不降低冻结科学门。

## 5. 最小解除、责任与下一单一主线

责任按实际交付确认：S1负责共享候选/集成，S2负责真实宿主和已执行run；S3本轮没有新的ALI-H真实数据交付。远端进程状态不由Git推断。

**下一唯一主线交付：一次所有适用门腿和checkpoint边界均合法的accepted测量修复，真实进入native update/map，随后接回并处理后继事件与输入归宿。**

在申请新run前，最小工作为：

1. **S1**修正episode↔checkpoint不可变关联，禁止第二事件覆盖尚待restore的第一事件cp；无合法cp明确NO_ROLLBACK。
2. **S1**使候选实现符合已冻结“未收敛不进入候选”，不事后改协议容纳结果。
3. **S1/S2**给最新run逐项PASS/FAIL门腿表，纠正“E1重入失败、只剩0.5m约束”的误诊；新实验必须说明如何处理信息增益和holdout，而不只控制重入。
4. **S2**只在实际授权后做有界复验；**S3**可并行独立评价，ALI-H缺项不阻原生功能修复。

这些是最小功能正确性和科学协议修正，不是资源或工程放行门。自动检测继续与scripted区分，未做保持NOT_EXECUTED；ALI-H性能保持NOT_EVALUABLE。不全表重评分，不沿用旧16/36、11/36。

## 6. 本机复核

```text
C:/Python315/python.exe -I -B docs/review_20261114_07e47af/review_checks.py
```

脚本读取固定Git原件、候选首帧/锚点时间及门字段，最终exit 0；未执行归档宿主或候选算法。私人handoff及本地未提交材料未纳入提交。
