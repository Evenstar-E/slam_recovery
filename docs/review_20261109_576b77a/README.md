# M0验收 576b77a

范围b8d1e2e..576b77a，仅新增协议文档。按交接第十部分审阅。未跑算法测试/真实bag：没有算法变更，不因协议文字重跑全套。

## 结论

接受方向与协议草案，M0尚未完全冻结。明确FAST-LIVO2/hall_01、实际注入窗、oracle标签、proxy非GT、空结果UNAVAILABLE和禁止单NIS归因，均符合交接。不要为此再补泛泛说明；下一笔应交付可执行M0和M1/M2入口。

## 运行前必须落实的四项

1. **集合不能二选一后称冻结**。第13-15行仍允许candidate支持259或全部445，并说结果出来时导出key。支持集取决于候选，不能用它作四控制共同总体。建议全部固定scan ID为主集，缺pose/观测单列；259诊断子集可另外固定并报告。先提交列表/hash、全评价区域和共同健康prefix，然后运行，不能看结果选集合。
2. **C3需实际host输入消费证据**。原始/转换/过滤bag hash、host binary/revision、真正加载配置、命令与输出hash必须在原生重跑时记录。这是M0/M2交付的一部分，不能只挂Open长期延期。第一次从相同健康prefix重跑标OFFLINE_NATIVE_REESTIMATION，不先叫DEPLOYABLE_REPAIR；真实在线checkpoint/宿主地图提交另验。
3. **同源clean pose/proxy只作一致性控制**。C1/C2用clean-run pose并对该clean-map评分有依赖，结果仅是oracle/proxy一致性；不得与C3混称独立GT准确度。C2删污染点不能恢复被遮挡背景，不是普适最优地图的数学上界。C3直接对独立采集/留出参考评估；没有该参考就明确proxy局限，不阻止先连通修复链。
4. **补状态与完整点记录契约**。协议当前只有地图指标，M2需证明filter之后保留ring/time/header/原point ID，实际宿主deskew/估计产生新的完整SE3及地图。共同时间支持的translation/RPE、输出缺失率、恢复尾段/干净窗误干预、耗时一起报。oracle污染identity评分必须仅在实际注入窗，窗外同扇区点是健康背景，不能算污染true positive。

## 建议本轮交付

M0配置+key清单+来源schema+运行命令/依赖检查；C0/C1/C2及C3 filtered-message exporter/host runner可以逐步提交。连通链和失败证据优先，不要求预设收益。连接组件指标可辅助，但需固定体素分辨率/邻接，不能作为拓扑正确性的单一判据。

本轮无代码缺陷反例；以上是预注册协议缺口而非已运行结果错误。保护已有归档，不修改旧数字。后续优先审实现和实跑，不继续围绕每个措辞往返。
