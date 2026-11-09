# 补验 6c3d6ea：point-ID解码与负例

范围58f1cf3..6c3d6ea（201b9c4、6c3d6ea），上轮并发合并后明确未验收的两笔；本轮远端无额外增量。按第十部分M2审阅。不重复审自己的ff87a48。

## 通过

主审计新增精确话题/类型、scan_ns解码、索引长度/size/stride、递增/范围、source[idx]等于filtered rows及mask hash检查；_iter_clouds改to_nsec。exporter stride=len(idx)、<u4 hash、schema v2修正，原“随便额外topic便PASS”的路径已由新增id_topic_verification替代。

测试由zip顺序改ns join，全帧验证，并明确覆盖first/last/max stripping；文件hash阳性测试实际读文件计算。41/41主测试本机PASS；从当前源码AST抽取validate，实跑正确映射、错ns、越界、错stride四fixture，全部符合预期。无远端bag，因此不宣称新增10个bag测试独立复现。

## 非阻断残留（集中处理，不触发全宿主重跑）

主audit_id_topic返回sidecar两bag hash，但未自行计算比对；新bag身份由另一个test_bags_bound_by_hash核验。要将主审计PASS单独作为完整M2凭证，应将hash核验也接入，或明确依赖测试收据。旧main point_record里topic存在性检查仍保留，优先把权威状态固定为id_topic_verification而非让汇总取旧字段。

test_rejects_source_hash_mismatch只assert当前hash与手工改值不同，没有调用真实validator并断言拒绝；“duplicate mask”负例增加另一stamp而非同stamp重复流。当前loader有dup列表且阳性assert无重复，真实重复拒绝路径存在，但测试名称比覆盖范围宽。下次把源hash校验、重复流、空/missing sidecar与schema异常做无bagfixture即可。

## 里程碑状态

接受point identity验证的实质收口；它不能补旧C3运行的runtime receipt，也不能说明新ID包已被原生宿主消费。旧/新bag分开保留，已有有界几何重算不因索引日志重跑。上轮runner shell返回状态/cleanup断言/启动前hash仍未被这两笔触及；M3只隔离净收益仍待实作。

本轮没有新增算法阻断，建议合并这些审计健壮性小项，并将下一轮优先级放在一条带启动收据的短原生运行和有界评价对照，而非继续修改旧数字。
