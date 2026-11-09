# 增量验收 e45e1ee

范围df0a0a5..e45e1ee：0254804、e45e1ee。2026-11-09。完整阅读新增归因探针和缓存修复；41/41主测试通过。另从源码AST提取缓存函数（未替换函数逻辑，只避开本机缺失的ROS/scipy顶层依赖），执行开发侧9个缓存测试，9/9通过。未播真实bag，未独立重跑完整复算；不能标全流程50条实测。

## 缓存与复算修复：通过

源hash+参数+版本cache键、缺源提前失败、输入hash不匹配退出路径已落地。结果JSON入库、非零查询的NN对照、全量proxy单独bootstrap和条件采样限定均为有效改进。原basename陈旧缓存反例对应缺陷关闭。

## P2：归因探针没有形成所声称的固定查询、去污染对照

probe_c_good_attribution.py:61-71仅删除range[4.0,4.6]壳层。注入器产生的是倾斜平面，r=4.30/max(abs(dir·normal),0.25)，袋面回波可到17.2m，不集中于4.3m球壳。

本机用真实injector、seed2构造5000点的受控输入：4433个袋点中，壳层删除后仍有4149个（约93.6%）保留。不是实场误删率，但直接证明该操作不是完整袋面剥离。因此filtered中分数未降，不能否证真实点过滤修复的价值；该操作还会删同壳层真实点。

此外filtered缩短数组后，评分器重新按长度stride选最多300查询；clean用最近clean keyframe自身点集，其timestamp无显式门限。四组不是同一射线/查询ID，仅关键帧数相同。应使用已知注入mask的oracle removal先做机制诊断，和实际filter分开，固定匹配的ray/point ID并报告变化；无一一匹配时说明统计量比较的范围。

## P2：诊断统计不能等同gate NIS18.07的成因

探针对全部445个quarantine keyframe取median，并不使用gate可提交259帧中的strided52 holdout及mean，也不应用相同支持选择。clean control未必处于可信reference覆盖内；低支持查询会外推局部平面。clean median16.2说明当前诊断协议下clean观测也有高残差，不足以确定gate18.07的原因是reference floor，更不能排除污染贡献。

保持不同控制的观察数字，但将“reference floor, not occluder”改为“该全区间协议下clean控制仍有较高残差，因果未分离”。要定因果，在同一固定holdout key/query集分别改观测、pose、reference预算/邻域，报告mean与全部支持/缺测；未做内部budget sweep前不归因budget。clean controls属于oracle诊断，非可部署恢复结果。

## 非阻断项

_cache_is_valid仅验证meta，未验证starts/pts/stamps的schema与内容一致性；现测试的valid fixture甚至starts仅覆盖一scan而stamps有两项。损坏npz拒绝测试通过不等于所有payload损坏都拒绝。后续可加形状/单调offset/schema检查，不因这一健壮性项重跑真实算法。

关键帧bootstrap仍是条件抽样误差，保留已加限定。独立复算非修复净收益。建议先修实验设计而不是继续解释median百分比；此轮不修改算法、不否定未独立重跑的实场归档数值。
