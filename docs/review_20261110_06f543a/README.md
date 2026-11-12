# 06f543a：主线未增加，研究控制对象需纠正

2026-11-10，main固定`06f543a4679caecbc6043636f79b29dafa4584df`，比较f2bbbb5。新增main只有DAILY追加42行：hold/测试/输入归档回报和撤回C2集成方向，无生产代码/新原生运行。研究单独固定`2449c0b4fe8039b8cccfdcc643af96fc08bf821f`，比较90df80e新增P1/P2及C2警告。协议、评分和既有Cron归属核过，旧owner无进程；本机不改算法/门、无ROS/原bag/新方法实验，私人文件保护。

## 主线与已接受范围

main对hold测量、126测试、sidecar的叙述不增加原生链；沿上一版[已发布核验](../review_20261110_f2bbbb5/README.md)，hold新宿主patch/log仍缺、命令单in-flight/ack归属/全接纳解除契约/实际评分子集仍未修，源码不变不重跑。A4/A6原生入口历史局部接受，不抹去，也不从日报叙述升A8/A9/A10/B11。实际修复注入→原生写回→同时间线接回→E2仍未交。

撤回C2集成方向与已复现坐标差一致，可保留为开发处置：不集成、不基于该版重导floor。不是本用户已选其他门/授权C3生产实现。本文不为已知C2问题再跑旋转矩阵；开发补对应脚本/小JSON原件即可，旧结果保留。

## P1：数值重算有研究增量，但精度与对象须限定

提交5个触发scan重算，旧before四位小数一致、脚本容差5e-4相对；不是“逐位复现”。scan匹配差5.39/23.19/5.50/21.00/20.90ms，不是header等于trigger。历史输入receipt可复用，但新结果未绑定实际bag/scan hash/加载producer版本，不能仅文件名证明全链身份。最低沿已有运行记录说明精度、实际配对和来源，不为措辞重跑整包。

本机核JSON算术：旧固定方向在新矩阵的缩放跨度约12.137倍，支持C2不是统一全局缩放；各producer自弱向跨度约223倍是另一对象。alignment cos最低.8792对应约28.45°，不能写“仅几度/方向几乎没变”或据没有预声明容差称方向稳定PASS。before变动不证明candidate after/before比值必改变，也不能推出κ必失效；正确是旧校准**不能无条件移植，真实两端仍BLOCKED**。

保留after缺字段BLOCKED，不用所有隔离scan/旧hostpose拼同名量。f2输入sidecar尚不是verified/holdout评分集，按既有最低归档要求自然补齐。旧producer的逐帧FIM不能直接用于新producer重算；逐帧矩阵便于旧版诊断，但新函数仍需相应scan/pose/实际评分人口与anchor。

## P2：自弱向恒等不等于生产门固定方向恒等

脚本statistics每个info重新选最小特征向量v，然后比较vᵀΛv与λmin；r=1和24/24是同一数学量的必然结果。没有比较生产固定trigger方向与candidate矩阵，也没有直接比较m排序。报告/main“门v就是候选最弱特征向量，子空间退化为现标量”不成立。

复用b5554ef已发布正常SPD例、在本版actual gate：固定触发tx；candidate diag(300,300,300,100,38.8889,38.8889)，实际after=100，candidate λmin=38.8889，Mode2 accepted。反例不证明真实bag有该候选，只否定一般恒等推论。另同固定投影100的两个SPD矩阵，只把另一轴信息1换4，F2-A m分别1/0，证明全方向条件与固定投影可不同；不证明新门有独立净收益。

**可保留的更窄结论**：m_after=0等价λmin≥2，是全谱最小值阈值；在同一基、且P=Λ⁻¹精确成立时，它等价现covariance范数腿，不是现固定方向信息腿。actual candidate cov还含评价基ridge/输入关系，不能忽略关系不加限定直接称完全相同。Loewner是可研究的不同矩阵条件，但不是“唯一没有自我否定的形态”；未比较候选质量不能选型。F3仅概念描述，没有给可执行的似然假设、证据相关性与具体界限，不能称完整冻结实现；归档缺序列BLOCKED接受，不把detector NIS当准入证据。

P2 gauge控制旋转加平移，却比较两基各自λmin，没有回固定anchor/物理方向；混合rot/trans的谱对平移一般不不变，不能将这一字段差全部归因C2体素。纯旋转C2问题已另有正常证据，不混两者。JSON reading称排序不同与24/24矛盾，开发已指出，集中修解释即可，不额外跑宿主。

## 最低下一步与分工

S1/S2唯一主线仍选定宿主实际修复→内部写回→接回→E2：沿f2最低正常修与已有预算，附实际部署patch/现log、自检PASS/FAIL/BLOCKED/NOT_APPLICABLE、完整帧/失败/尾段/成本。不要为P1/P2重开floor/κ/模型矩阵。S3专用研究只纠正控制对象、精度/基与结论，保持同candidate比较/独立质量BLOCKED，复用主线自然产物；参数手调仍停、未选方法不部署。研究不作主线前置。

本机命令：`python -B -W ignore docs/review_20261110_06f543a/research_controls.py`，sourcepin与归档算术PASS，旧SPD例复用PASS；上述一般恒等结论FAIL；原生链/方案效益BLOCKED；ROS/原bag/full suite/完整A/B重评分NOT_APPLICABLE。零退出表示控制核验，不是方案有效性通过，无完整总分变化。
