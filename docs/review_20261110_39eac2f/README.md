# 39eac2f补验：默认配置消费观测成立，状态时间需按事件解释

日期2026-11-10。目标 `39eac2f337eaf2b9df28aa0e9b015b36d0ecf34d`，两笔2aa1afc/39eac2f。旧owner不运行，适用AGENTS/评分/REVIEW10与用户减少工程防御规则不变。只读runner/补丁及归档原CSV/receipt，未编译宿主或运行ROS，不改算法。

## 接受的实际交付

- Git runner原字节14372、SHA59500116…，与默认及ON/OFF receipt记录一致；`bash -n`通过。解决main旧runner与实际收据脚本不一致，非新增防御需求。
- 默认TRACE-only发射点移出DET_SYNC guard；diff可见GROUP在handleFirstFrame/estimation之前、STATE在estimation之后，只增加观察路径。本机没有pre_trace基线文件，不能独立重现patch应用/完整宿主构建；不把文档的byte-identical声明当本机PASS。
- 默认原CSV **Git blob** hash5fcccddc…与原receipt一致，599 ARRIVE、1766 GROUP/STATE、5 IMUINIT，各位置有限，599 ARRIVE单stamp hash全部通过。Windows checkout的4137行被转CRLF，直接hash checkout时断言失败；去掉环境CRLF后逐字节等于原Git blob，这是换行转换，不是实验输入错配。884空组均-1哨兵/空集hash；GROUP完整字段与ON#1逐项相同，IMUINIT摘要也相同。默认运行receipt OK/800odom、planned killafterdrain明确。
- DEFAULT与ON的exe/library均不同，affinity也从taskset0-7变为空；只可作配置间观察，不是唯一DET_SYNC因素或重复分布证明。

## 正常数据口径与最小意见

1. **STATE timestamp不是同一观测阶段。** DEFAULT的GROUP与之后STATE有878/1766行lid_stamp不同，DEFAULT与ON#1 STATE也有878不同；默认STATE在stateEstimationAndMapping之后重新读取LidarMeasures.last_lio_update_time，ON旧记录对应进入package前的值。本机首次逐行同时间断言失败，未称宿主运行失败。

GROUP序列完全一致，可能按同一package处理序号正确关联两边STATE；但必须明确关联是“同消费事件处理后状态”，而非保证两个STATE timestamp同值。先用既有GROUP→STATE事件配对解释/重算，不修改sync、不补一趟宿主。现index75差1.104mm、max424.605314m只已复现为按序号诊断，完成事件绑定前不包装成同物理时刻误差；有3个diagR不代表全状态。不要机械拒绝多子事件的重复lidar stamp。

2. **空组比例应按实际子事件解释。** 默认884空组中883带img=1，另有882非空组也带img=1；是否LIO/VIO两个子阶段造成需消费路径解释，不能从约50%比例直接推坏同步或完整宿主属性。支持的有限结论是“在此序列TRACE-only默认配置也观察到同样的空IMU package摘要”，排除了必须依赖DET_SYNC才出现该现象的简单解释；不推广全部环境、不宣布完整根因。

3. 单生产者ring按当前回调形态理解，不扩假设性并发、恶意格式、内存耗尽检查；未执行的header diff为空有明确说明，不当缺交付。TRACE flush可能调度扰动仍未完全排除，保留支持范围即可，不要求生产级日志框架。

## 分工与验收

- **主线事务：**A5报警帧、A9撤销人口/后来帧时间正常路径修复，负责人仍待开发主会话确认；不能让连续trace交付替代主线。
- **旁支消费：**仅用现CSV解释前后STATE时间/子事件，收窄结论并保留UNKNOWN；到此不继续无假设trace/runner扩展。
- **A7并行：**固定切空间中联合评价direction/info/cov，两正常gauge反例解除后才能验依赖其准入链；不因此重跑trace。
- **Codex独立验证：**见docs/COLLABORATION_STATUS.md，从固定版本/独立分支复算这些事件关系、事务和gauge反例，不抢写现有core/node/runner。

已核：runner语法与receipt SHA、本批CSV/摘要/空组PASS（局部）；跨构建同事件/同时间评价尚待解释；宿主真实编译/新GT/修复净收益NOT_APPLICABLE；不完整重评分、不据一趟默认运行升A/B。开发侧随下一实际交付附自检与分工，不为这段说明再制造“已接受”文字循环。
