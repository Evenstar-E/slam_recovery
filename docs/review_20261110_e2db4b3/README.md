# e2db4b3：旋转证据补齐，固定方向仍被重新单位化

2026-11-10，main固定`e2db4b3cfc2edda324c98a94e651f57888364719`，比较06f543a；main只有日报追加13行，无原生代码/运行。研究固定`3e9f9475b9baac9545bf0857fdc1c8e455585e5b`，新增rotation_control脚本/JSON、Loewner定义和reading修正。协议/评分/既有任务归属已核，旧owner无进程，私人文件保护；不改算法/门，不读原bag、不重跑宿主/旧生命周期/完整suite，无新参数或模型实现。

## 局部接受

研究补齐此前只在Markdown的两来源rotation_control与Loewner定义原件；reading不再与r1/24排序矛盾。这是研究证据封装改善，不是新原生链或独立门效益。C2不集成/不据该版重导floor保持，与既有纯旋转正常例一致；不为新百分比重新开旋转矩阵。旧固定trigger≠candidate自弱向问题仍见[前轮核验](../review_20261110_06f543a/README.md)，脚本主体未纠正，不再复跑同SPD门例。

## 新fixed_direction列不是纯旋转同物理二次型

`_rotation_control.one`在0°用identity，非0°却调用`se3(deg,[2,-1,.5])`，同时移动原点；随后transport(v0,G)又除其Euclidean范数。Ad含平移的转/平移耦合，不一般保范数。对旋转分量非零的direction，再单位化改变参数化尺度，不能声称“只让矩阵变”。

本机`fixed_direction_control.py`只核exactSPD transport，不运行点云producer：Λ=diag(10,20,1,40,50,60)，v=rz，G=z旋转30°+同脚本平移[2,-1,.5]；ΛG按已接受正确transport_information精确搬运，完全没有采样缺陷：

| 读法 | 投影 |
|---|---:|
| 原同物理方向 | 1 |
| 同时正确搬运v/Λ、不再单位化 | 1.000000000000016 |
| 研究搬运后重新单位化 | .16666666666666766 |

纯旋转控制范数1、投影1；加平移搬运后方向范数√6，重新单位化会把投影除6。**本例只否定一般fixed物理方向控制声明，不证明归档room/hall全部百分比由单位化造成**；若某帧恰好纯translation弱方向则没有这个范数效应，但其非零平移仍改变轴对齐体素分箱，不是隔离纯朝向。

因此日报“room20%/hall495%都是旋转敏感度”限定不足。最小纠正：要测纯旋转就固定translation=0，物理direction随同旋转；要测完整SE3就不将Ad搬运方向重新单位化，或明确声明变成了不同Rayleigh尺度，并回同anchor比较。复用既有扫描/小control纠正这一处即可；本机不另跑bag，不改变已正确生产transport，不把证据补齐当新模型矩阵。

Loewner定义保存接受为研究定义；共同anchor/同candidate fullΛ缺失仍BLOCKED，不称部署或确认。其全谱floor仍有基/量纲限制，沿前轮说明不自动宣布κ/floor新校准成功或启动重导。

## 主线与下一交付

A/B完整验收不提升。本轮原生主线无新执行；S1/S2沿f2已发布最低命令归属、完整接纳解除、trustedstamp、实际部署patch/原件等正常问题，下一唯一交付仍**实际修复测量→原生内部状态地图写回→接回→第二事件**，不是追新旋转百分比。S3独立纠正此控制与旧研究归因，参数手调继续暂停、C2不集成，不要求主线等待门研究。

开发下一实质交付给PASS/FAIL/BLOCKED/NOT_APPLICABLE、命令与同source/host/input/config/完整人口/尾段/失败/成本原件；首次真实完整流程完成仍立即单独报告。本机sourcepin/算术PASS；新fixed二次型一般声明FAIL；方案有效性/真实两事件BLOCKED；ROS/原bag/fullsuite/完整总分NOT_APPLICABLE。

命令：`python -B -W ignore docs/review_20261110_e2db4b3/fixed_direction_control.py`。退出0表示数学控制核验，不是新方案通过。
