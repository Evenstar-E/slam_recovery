# A7专项：固定gate评价基通过，node协方差producer仍随原点翻门

日期2026-11-10。固定目标 `21fa6506f8b1c63f95b135f7052b2fb84ea7c9c3`；重点70f745a/bcede15。只读源码与内存正常路径probe，不修改算法/阈值，不运行ROS/bag或原生宿主，不重跑全核心测试。全核心由主会话负责。

## 1. 已解除的旧范围

实际命令：`python -B -W ignore docs/review_20261110_a7/a7_gauge_probes_fixed.py`。

本机结果：真实默认FIM producer的旧弱方向反例，world y=0/2m时before19.033712348、after48.726302051、cov0.023053432057，均Mode2；正确搬运的对角协方差例world y=0/5m时cov均0.2，均Mode2；旋转30度加非零平移例指标/mode同样不变。旧gate层的world重新单位化与直接world covariance norm问题已在固定anchor body评价基解除。

`_into_basis`的信息与协方差搬运方向正确，node触发段保存本帧body弱方向/FIM及anchor_pose_world，candidate显式声明info/cov基。独立比较c82aae5/21fa650的GateThresholds AST完全相同，**没有改冻结门**。不能仅因文档数值与本机数值略不同重复宿主；本机实际值如上。

## 2. 实际node路径尚未闭合：world单位阵正则改变物理协方差

位置：`slam_recovery/sim/transaction_manager_node.py:640-648`，特别是

```python
info_after = np.mean(fims_after, axis=0)       # world基
cov_after = np.linalg.inv(info_after + np.eye(6) * 1e-3)
```

gate把此cov搬回anchor并不能消除**构造时**已加入的world单位阵正则。若A=Ad(T_world_anchor)，理想information满足Lw=A^-T Lb A^-1；加world epsilon I再求逆，搬回后是`(Lb + epsilon A.T @ A)^-1`，不是`(Lb + epsilon I)^-1`。含平移的A不正交，世界原点改变等效先验/正则，物理场景不变而cov改变。

`slam_recovery/validation/fim_and_holdout.py:80`自身也加world `1e-6 I`；应在同一个固定评价基/正则契约下处理，不另扩生产级框架或新的问题矩阵。fixed gauge脚本先在body构cov后搬world，绕过真实node这一步，所以其PASS不能证明实际candidate producer闭合。

## 3. 正常实际node反例（不是小数误差）

脚本：[a7_node_cov_probe.py](a7_node_cov_probe.py)；结果：[a7_node_cov_results.json](a7_node_cov_results.json)。实际执行命令：

```text
python -B -W ignore docs/review_20261110_21fa650/a7_node_cov_probe.py
```

执行exit0表示**翻门反例已复现**，不是A7 PASS。保存结果时仅将stdout写到上述JSON；不修改实验归档。

脚本入口核core、node、fim producer Git blob与固定21fa650一致，避免加载兄弟旧包或混用源码。工作树HEAD核为29894f3，但上述源码blob严格绑定21fa650；结果JSON保存各blob。

场景：`rng0.normal(size=(400,3)) * .16`的同一cloud；trusted key0独立参考；candidate keys1–4与参考同物理扫描/位姿；incumbent仅x偏移0.12m。使用**默认OnlineRecoveryTransactionNode、默认GateThresholds**。仅世界原点y=0→20m，参考/候选/anchor一同搬运，物理数据不变。

**detector入口控制：**直接调用真实`tx_mgr.trigger_quarantine`设置固定事件，before SPD与纯trans-x弱方向为显式fixture；不运行detector、不说明检测准确率。之后support、holdout NIS、paired benefit、FIM producer、candidate/gate和事务提交均走真实node实现，未mock验证结果、未伪造PASSED。没有aux信息。

| world y | before信息 | after信息 | posterior cov norm | holdout NIS | mode/accepted |
|---:|---:|---:|---:|---:|---|
|0m|20|62.98292984059509|0.5136136651945151|0.3352223643752276|MODE3 / false|
|20m|20|62.98292984059506|0.4694900053022529|0.3352223643752263|MODE2 / true|

两次paired真实结果均4/4改善、approved=true、Wilson0.5964785398205344、reentry0。NIS和information不变，cov跨默认sigma_tol0.5，拒绝变接纳；不是无实质影响的小数差。默认门：tau_info25、tau_val_nis2.5、sigma_tol0.5、sigma_bridge4、Wilson0.55、reentry0.5m、duration1s。

## 4. 最小解除和主线范围

在固定anchor基构造/聚合information，加**原有**正则并求cov；或把正则作为同一信息对象正确transport。direction/info/cov保持同一锚点与度量，沿旧公式/工具，不改epsilon或门限来救例子，不新增第二估计器或大参数矩阵。

接受gate层修复的局部进展；真实producer的准入gauge结论仍未完全成立。**仅阻断依赖此cov的准入科学结论，不阻断原生接口实现、有限探索运行或其他已有效的trace证据。**原生接线仍最高优先，不能因为此最小修复再停全部开发。E3多帧/aux契约继续既定延期，不展开新机制或故障空间。

本次无算法文件修改、无提交；仅生成本目录审阅probe/结果/报告，由主会话整合提交。
