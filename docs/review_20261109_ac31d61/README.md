# M2 point-ID增量验收 ac31d61

范围7e40a9a..ac31d61，两笔、7文件。源码diff和新增130行测试完整核读。本机41/41主测试PASS；AST提取audit_labels/ordered_match运行缺字段与重复记录fixture通过。未运行外部bag依赖的5个point-ID测试，不冒充46条全流程实测。

## 接受

exporter保存flatnonzero(keep)的uint32并行索引、exact scan_ns标签、原/保留数、mask hash和两bag hash，保留point_step24。新包与原C3运行包分开标明，未借新包hash改旧M1结果。实际剥离帧抽样与missing_observation正确字段修复均是进步；缺字段现在UNVERIFIABLE，本机确认。

## P2：主审计仍没有解码point-ID

m2_record_audit.py main的id_evidence['decoded']始终None；cand筛掉三个已知topic后，bool(cand)即PASS。任意无关/debug话题均能冒充point索引。这与“decodes schema”提交说明不符。精确匹配kept_index的msgtype，解码scan_ns，按该键join source/cloud/sidecar，核对数据长度、严格递增、原范围及source[idx]==filtered。缺少任一证据UNVERIFIABLE/FAIL，不看话题存在就通过。

## P2：point-ID测试仍遗漏剥离区和身份关联

test_m2_point_id.py:95按zip云与mask流配对，未检查mask标签等于cloud ns；:96仅前20帧，而filter report前20帧strip全0。sha/排序全帧测试有价值，但实际source[idx]重建须覆盖真正剥离帧，并按scan_ns而非顺序join。:83所谓in_range仅比较idx[-1]与idx.max()，这是递增数组恒等式，并未检查idx<n_original。:61 hash测试只看字符串长度，未计算当前源/输出hash。补坏ns、越界、重复mask帧、源hash不符的负例，不需要为此跑全算法。

## 非阻断格式与审计限定

UInt32MultiArray layout.dim[0].stride=4是字节数，标准stride单位为元素，一维应为len(idx)。当前读data的专用程序可用，但按标准layout消费者会误索引；修schema并版本化即可。mask hash用<i4与uint32小索引同bytes，建议明确<u4避免通用大索引问题。

verify_stripped_frames检查的仍是旧FILT包，不直接核new ID包；新增ordered value matching可证明存在有序子序列，重复值下不能证明实际原index来源。新ID精确映射核验应与该报告明确分开。_iter_clouds仍int(to_sec()*1e9)，应直接to_nsec保持M0身份一致。

## 里程碑

point identity exporter可接受，M2可验证身份契约尚未闭合；实际runtime receipt/runner失败清理、有界地图评价仍是已有开放项，不重报为新缺陷。下一次集中交付按ns映射的负例与filtered-frame审计，保持真实旧运行结果和新ID包运行分开；不因side topic声明修复净收益完成。
