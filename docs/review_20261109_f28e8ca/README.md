# 主线/旁支验收 f28e8ca

范围8dfe639..f28e8ca，两笔、6文件。完整读191行审计与115行fixture及归档。实际运行oracle-audit测试11/11 PASS（含静态源码断言、转写分支，非11个真实producer/host回归）；有file ResourceWarning不影响结果。未运行真实bag或layout重算。研究镜像核对一致。

## 旁支进展接受，主线未新增native对照

归档599帧同layout/count、199差异帧和row fraction，与exact oracle定义相容，是有价值的输入身份检查。审计诚实记录FAIL guards，而不是把测试全绿冒充producer已修。现shape异常/缺clean pose/输出身份问题属于尚未触发本档的健壮性项，前轮已报，不再扩台账。

本轮未交付actual-filter vs exact-oracle native重估，也未新测弱方向/有效匹配。主线仍是该一次对照与空间信息；请不要继续仅审计旧producer然后写口径修正。

## 解释限定

“无重排”只能排除同multiset纯重排，不排除同时改值+重排；已知injector保存row order和layout组合证据有力，严格identity仍以source/index生成记录为准。common frames计数未报告各bag缺帧，不能把公共集PASS当全流覆盖。现归档无明显错身份，非要求因此重跑host。

“400外窗帧稀释A->B/B->C”需按条件326帧实际分区：完整bag有400 healthy，但指标集合未必包含这些400帧。准确说全条件集合混合退化与恢复尾段，需单列in-window/尾段，不引用完整bag400当测量分母。D->E也混合窗口，足以说明条件集pose差，不能定位失效发生的时间/因果。

fixture多为锁定缺陷文本，producer修改后会红，并不验证正确替代逻辑；后续改pure helper，测试正确/错误输入的行为，避免把这些原样加入修复后的永久CI。旁支集中修四个guards和时间分区即可，不因11tests重新跑所有宿主。

## 下一轮分工和自检

主线：固定room源、prefix/config，对actual-filter与exact oracle-removal实际原生重估；信息矩阵/空间分布先从mask与现有cloud算，必要新run只一项变化。oracle诊断不声称部署。旁支：fail-closed、pose公共可用集合、内容hash与分窗指标随run同批提交。

开发侧先§10.12 PASS/FAIL/BLOCKED/NA+命令证据自检，报告主线交付/资源阻塞与旁支安排；无真正阻断就不等全部文字清完才运行。今晚日报记新增身份审计但未推进native因果对照，已有room负结果保留，不因guard未触发撤回全部数值。
