# adff0b0：原生恢复入口有实质增量，完整两事件仍未交

2026-11-10，固定`origin/main@adff0b084b55cc29059bf3e91cb71230d6e30a72`，比较已核0edc3d7。跳过本机05f7fc5交接/旧审阅、merge计数和Auto-Review；真正新增为055b200宿主接口选择、590aa50原生checkpoint实现及后续执行快照。独立C研究固定545340f，见[C核验](C_RESEARCH_REVIEW.md)，不混生产门。

已读AGENTS、评分标准、REVIEW§10及历史入口；核Cron为本会话已有任务、旧PID25412不存在，不双写。私人handoff保护。本机不修改算法、不跑ROS/原bag、不调门。合并main到独立review分支时保留两边协作快照，生产源码未手改；继承原件diff有patch空白，不为消除diff --check警告改归档。无完整重评分。

## 1. 主线新增与宿主转向

05f7fc5已由5206027合入main，不能再说未收到宿主转向。S1交实际接口比较，选择FAST-LIVO2的LIO路径：它新实现快照/原生重放，MM-LINS/FAST-LIO组件现成但未验证该路径，机器没有独立FAST-LIO2工作区。选择按接口/新增工作，未按有利ATE选；这是本轮可接受的有限路线选择，不是FAST-LIVO2整体更好。若隔离/修复注入在原预算失败，按已有交接重比较，不无限绑定。

**A4/A6有实质原生实现进展**：C++ `snapshotCheckpoint/restoreCheckpoint`复制/替换宿主`_state`、`state_propagat`、voxel octree和四个IMU跨帧量；树clone实现是深拷贝，不是Python sidecar。`reprocessCheckpoint`从快照经processImu→stateEstimationAndMapping→handleLIO原生重估、内部UpdateVoxelMap。独立源码核未发现树clone已声明成员遗漏的正常问题，不扩全缓存/全异常框架。

但重放仍是捕获的原云，**修复测量注入、隔离期停写图、同时间线持续接回未完成**。双事件包准备是输入产物，不是两事件运行；其E1继承已filtered输入，不能叫完整原始注入正控制。开发明确两事件尚未开始，本轮不发整链完成通知。

## 2. 冒烟报告与原件边界

开发报告210985点快照、0.086s、8帧重放/0.358s，有命令和具体实现；这是开发实测声明，不能抹成无进展。本提交目录却未含所引host_smoke.log/smoke_results.json，仅README/diff/.cpp/.h，实际配置/完整binary receipt也未随包提供。patch规范Git blob sha256为`f5efce7160e45933f84b23c365f08b9a51798aeb9c201c4e48a5ba026e2c2f21`，与报告前缀一致。

现ack只给map计数、3维position，最多支持“恢复统计数量与快照一致”；没有逐点/plane/完整状态比较原件支持“value-for-value/逐值相同”。最低归档已有log/result/config/receipt即可，不为补证新跑矩阵；如旧原件没做完整等价比较就收窄声明，不补假PASS。LIO视觉不适用依实际运行配置声明，不能只从模板推。

smoke脚本为打印式诊断：wait_s循环`10*wait_s`次、每次.02s，实际约标称1/5；任意ack都return0，未校验OK和累计send失败。最低纠正这些几行/自检口径，不以脚本退出0自动验收宿主成功；不要求为文案重跑原实验。

## 3. 当前正常入口的最低保障，不扩框架

### 3.1 SUSPECT也覆盖“可信”检查点；快照与trusted horizon未对齐

`recovery_node.py:958`以active_quarantine=None判quiescent，首次SUSPECT尚未开段仍snapshot。实际node首帧高NIS10→SUSPECT/activeNone，本机driver control服务后发送snapshot，捕获决定状态SUSPECT。快照status说“healthy trusted”不成立。更一般，manager会backdate到onset−confirmation margin，最新host当前快照可能晚于这个可信边界；wall2s周期也不是message-time trusted age保证。

最低：滚动快照至少不在SUSPECT/未确认区覆盖，并绑定实际host stamp和manager所需可信时间界。可先用明确健康prefix快照做CONTROLLED_INTERFACE_TEST，不先造通用快照数据库；自动链不能把“无active段”当全部状态可信。

### 3.2 无新输入/包尾drain时不服务恢复命令

宿主patch约547–555在sync_packages=false立即continue，pollCheckpointControl仅约659在成功处理group后调用。包尾最后输出引发恢复或暂停输入时，将不ack；这是正常生命周期，不是异常注入。最低沿现主循环无组分支也服务控制，不新线程/ROS service框架。恢复状态时间仍需与后续输入一致。

### 3.3 原生重放公开旧点云，静默声明不完整

patch对odometry/path/mavros/effect加replay_mode guard，但基准handleLIO的publish_frame_world仍未guard；ONLY_LIO会公开旧scan，header取当前wall time，plane/输出文件也未全面静默。最低在现重放公开输出入口门控，保留内部状态重估/map更新；原内部重放不应被当成新消息消费。不要据此猜driver必错配，当前具体问题是公开旧云/输出一致性A8尚未闭合。

### 3.4 写图隔离/修复注入/接回时间是现主链真实缺口

开发已识别隔离期间仍UpdateVoxelMap；restore只恢复当下，下一受污染group再写回。仅restore还把IMU传播起点退回checkpoint而直接继续未来输入，必须明确捕获段如何按同时间线处置，不能用ack替代持续状态一致性。接纳路径源码实际是先restore后reprocess，不是README说“不restore”；不应为了匹配旧文字再把ICP位姿直接塞进_state。需要的是**经过验证的真实修复测量支配宿主重估/地图写回**及接回语义，复用已有过滤保留完整点记录/IMU。

旧0edc3d7三个生命周期反例相关manager/node源码未变，沿[已发布最低修](../review_20261110_0edc3d7/README.md)保留，不重跑旧suite。runner此次已接wait-limit，关闭旧“runner未传”范围，不继续索要同修。完整E2仍需新事件身份与真实输入/输出，不把首故障重开称第二事件。

## 4. 本机测试与host结果不能混

`driver_controls.py`只运行两项不依赖pytest的客户端函数（silent-host failure、disabled client）并做实际node SUSPECT→driver snapshot正常控制。模拟accepted gate report加失败native ack时，row.accepted仍true、episode已decided；这是gate与宿主执行事实分离，**不得把gate接纳数当原生提交成功数**。该control不是成功候选真实实测，也不据此要求通用分布式事务重构；最低正确分别报告native动作/失败且不能宣称接回完成。

开发文件test_checkpoint_client是pytest风格，unittest discover计0已明确回报；本机未安装pytest、不把“0 tests OK”称验证，也未运行fake host重复rename控制（Windows/Linux行为不同不作为算法阻断）。本次两函数通过不证明原生执行。

## 5. 下一唯一主线及分工/验收

S1集成：沿旧最小生命周期修，检查点可信stamp与candidate/原生动作归属；S2：现host隔离写图、实际修复输入重估/写回/同时间线接回，并使包尾控制/重放输出正确，先有限受控原生接口两事件可行性，继而真实自动链。不等S3研究/新阈值，预算沿原task、失败也归档，不能为看Mode2放门。

下一交付是选定单宿主的**实际修复测量→原生状态/地图写回→接回→第二事件**运行（受控与自动明确分开），或上述具体入口的有限失败及最低解除；不是继续增加审计表。附同host/source/config/input、E1/E2动作和时间、完整帧归属/失败/缺测、尾段输出及实际成本，PASS/FAIL/BLOCKED/NOT_APPLICABLE自检。首次真实完整链完成后单独向用户汇报。

S3门研究并行：C有新增，不再称未交；坐标控制FAIL/候选效果未证，A/B旧错误未纠正，仓库“A不删/B搁置/C重导floor/S3收口”只是开发侧状态，不是本会话用户选型/部署授权。生产不集成、不启动floor重导，参数手调暂停。缺候选先BLOCKED，复用主线自然产物，不让主线为研究重复宿主。

状态与A/B：PASS_LOCAL为两个客户端函数和源码入口存在；FAIL_LOCAL为SUSPECT覆盖及C坐标控制；BLOCKED为完整状态等价原件、实际修复写回/接回/E2、独立方案效果；NOT_APPLICABLE为ROS/原包、pytest全套、full A/B总分、调参。A4/A6局部实现推进，A8/A9/A10/B2/B11仍未闭合；不把测试数或报告计数提升全项。主要工程接口/时间归属，算法净收益与参数上限UNKNOWN。
