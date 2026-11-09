# 主线/旁支验收 a6d6558

范围3c23d84..a6d6558，三笔。完整读rate与audit绑定增量、fixture和归档改动。本机AST抽取现版纯函数、运行开发侧16 rate+17 completeness共33/33 tests PASS，避开缺ROS/bag依赖；未运行真实bag或重新执行host，不冒充89项全部本机实跑。

## 旁支通过

左右邻居先diff再合并，旧跨故障窗长间隔反例关闭；已归档IMU假slow撤回。audit增加每帧payload digest比较，空audit不再BOUND。高load分支要求同时慢发布，状态改CONTENTION_SUSPECTED且未知因素公开，不再直接定因果。

## 主线状态：本轮无新确认实验

旧诊断重算与工程保障有进展，但没有同prefix低负载或独立场景新run。不要把33fixture作为主线机制已确认。下一交付直接执行已选的同prefix确认；若环境不可控制，明确BLOCKED证据并转向预注册独立确认。无需再单独提交收到意见文字。

## 非阻断集中项

check_audit_binding中want=None仍跳过digest并BOUND。本机fixture：per=[ns100,n_kept2]但无sha，与任意payload指纹仍返回BOUND。当前真实audit都有digest，本档无影响；缺字段应UNVERIFIABLE，补fixture集中做，不为其重跑宿主。

rate慢间隔统一100ms对LiDAR100.19ms本来就多数满足，因此“LiDAR slow比例~.888”不是缺输入，需不同topic基线或命名原始阈值比例；目前holes检查另用2*median，连续性结论并非由该比例得出。无当前新根因推论。

## 分工与验收

主线实验角色负责新确认run与host更新/queue/wall记录；旁支角色集中日志/绑定缺字段和自检。先§10.12自检PASS/FAIL/BLOCKED/NA+命令证据，明确实测/归档和对已有400条件修复收益的影响。旧M3条件proxy结论保持，通用安全/部署未完成。无新当前算法阻断，不扩报完整台账。
