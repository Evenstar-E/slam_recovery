# 主线/旁支验收 d798ea3

范围40e7a6d..d798ea3，一笔两份研究文档。仅diff/镜像一致性检查，无算法/实验数据变更，不重复跑单测或host。

接受CONTENTION_SUSPECTED及初始化prefix mismatch限定。关闭过强因果措辞；**本轮主线无新增测量**，不能因文档降级就算完成发布机制确认。旧rate JSON/脚本仍是SCHEDULING_CONTENTION，暂归历史诊断；下次真实确认随结果统一scope，不要求为这段文字另跑全实验。

主线下一次必须实际交付同prefix确认run或说明资源BLOCKED并直接转向已预注册独立序列确认。最小条件：从原bag起点保留状态初始化，input/header/wall及host更新/发布/queue证据；不调75ms成功标准。只“同一台繁忙机器重复一次”仍不能证争用因果。

旁支集中并行修左右邻居跨窗diff与audit绑定，不影响已有400条件proxy修复结果；既有零外窗删除保留单clip限定。开发侧先§10.12自检附适用PASS/FAIL/BLOCKED/NA，报告主线推进和旁支安排。请不要另发纯接受意见提交，下一交付回到运行/确认。
