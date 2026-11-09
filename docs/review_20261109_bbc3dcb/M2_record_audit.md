# M2 记录契约审计：C3 过滤包 + FAST-LIVO2 重跑

审计对象：`docs/review_20261109_bbc3dcb/run_fixed_input_repair_c0c3.py`、
`fixed_input_repair_filter_report.json`、`fixed_input_repair_c0c3_results.json` 的
`_meta.c3_record`，以及磁盘上由它产出的四个 bag。对应主树 `f2877c3`。
脚本 `m2_record_audit.py`，结果 `M2_record_audit.json`。

**只读审计。** 没有改动主树、对端脚本或其产物；所有判定都可以用
`python -I docs/review_20261109_bbc3dcb/m2_record_audit.py` 重跑。

## 结论

**记录契约基本成立，但有一个阻断项：过滤包没有保留原始 point id。**

其余 19 项全部符合，包括 8,599 条 IMU 与 888 帧图像逐字节相同、四个 bag 的 sha256 与磁盘一致、
宿主二进制/源码 revision/两份配置的 hash 全部对上，以及控制重跑的 0.028 m 偏差可从控制 bag
独立复算到 10⁻⁶。

## 三栏

### 符合（19）

| 项 | 证据 |
|---|---|
| 点布局 x/y/z/intensity/time/ring，24 B | 598 帧全部 `point_step=24`，字段顺序与偏移与源包一致 |
| header stamp + frame_id | 598 帧逐帧按 stamp 精确匹配源帧 |
| ring/time 随保留点保留 | 抽样 25 帧逐行比对，保留行与源行 24 B 完全一致（过滤器只删行、不改行） |
| 保留点数 = 过滤器报告 | 598 帧逐帧与 `per_frame[].kept` 相同，总计 21,198,773 |
| 非 LiDAR 话题逐字节相同 | IMU 8,599/8,599、Image 888/888，wire bytes 全等，message 数一致 |
| bag original_scans | `aa740037…` 与磁盘一致 |
| bag converted_scans | `c90300cb…` 与磁盘一致 |
| bag replay_poses_out | `1109fccf…` 与磁盘一致 |
| bag control_poses_out | `2a3880ad…` 与磁盘一致 |
| 宿主二进制 | `ca1959c4…` 与磁盘一致 |
| 宿主源码 revision | `0d2c034…` 与 `fast_livo2_ws/src/FAST-LIVO2` 一致 |
| `source_dir` 声明 | 与磁盘路径一致且存在 |
| 配置 `m2dgr.yaml` | `47a1bfd9…` 与磁盘一致 |
| 配置 `camera_m2dgr.yaml` | `96867cf9…` 与磁盘一致 |
| 四条命令已记录 | build-filtered-bag、两次 `fl_run_isolated.sh`、measure |
| 标签 | `OFFLINE_NATIVE_REESTIMATION`，且 `label_note` 明确「不称可部署」 |
| 缺位姿帧已列出 | `missing_pose_ids` 为 44 个整数 id 的列表（134, 136, 140, …），不是只给计数 |
| 缺观测 | `missing_observation=0`，`missing_observation_ids=[]` |
| 控制重跑可复现 | 见下节，三窗口 mean/p95/max 全部复算到 6 位小数 |
| M0 key 集 | 记录引用 `f36137b` 版（446/252/132），哈希与重算一致（见「分母」节） |

### 不符合（1）

**原始 point id 未保留。** 过滤包的 `/velodyne_points` 没有 `id`/`index`/`point_id` 字段，
包里也没有并行 id 话题（话题只有 image、imu、velodyne_points 三个）。

- 影响：一个保留点可以按 24 B 值在源帧里找到对应行，但无法按其**原始索引**命名。
  任何需要「第 i 个回波在过滤后被删/被留」的逐点归因、或需要按 id 重放的审计，都要先做
  一次值匹配（同值重复点会退化）。
- 不影响：位姿级结论（C3 的 ATE、覆盖、尾部）不依赖点 id。
- 修复成本：过滤时把 `np.flatnonzero(keep)` 写到并行话题即可，不必改 `point_step`
  （改布局会让宿主解码失效）。本地 C3 导出器就是这么做的，可作为参考实现。

### 无法核验（2）

**宿主实际读取了过滤包。** 记录里有文件哈希、命令行、输出哈希，但这些只证明「文件存在且
内容是这些」。没有任何逐消息消费痕迹能证明宿主读的是 `c90300cb…` 而非同路径的旧文件。
缓解措施（不是证据）：命令行显式指向该路径、输出 bag 的哈希在记录里、控制重跑可复现。

**归档位姿包 `res_h1_inj43_vis.bag` 自身的来历。** 记录把它当作 archived reference
去比对，但没有它的生成记录；它是否由同一二进制、同一配置产生，本审计无法判定。

### 需要更新的一条（不计入不符合）

`_meta.freeze` 引用 `docs/milestone_m0_keys.json @ f36137b`，primary **446**；
而任务书里写的冻结是 `7f32cb8` 版，primary **445**。两者不是同一个集合：
`f36137b` 把注入边界改成整数纳秒，第一帧注入扫描从「健康前缀」归入「注入窗」。

记录的做法是对的（引用当前版本、哈希自检通过、并在 `superseded_by_ns_boundary`
里写明 445→446 的原因）。**需要更新的是任务书和任何仍引用 445/259/133 的段落**，
不是这条记录。

## 控制重跑复算（第 5 项）

用与生产者无关的位姿读取（`rosbag`，不是它的 `rosbags` Reader）和独立实现的
Kabsch/Umeyama，从控制 bag `res_h1_inj43_rerun_unfiltered.bag` 复算：

| 窗口 | 记录 n / mean / p95 / max | 复算 n / mean / p95 / max |
|---|---|---|
| pre_onset | 72 / 0.010796 / 0.021682 / 0.029619 | 72 / 0.010796 / 0.021682 / 0.029619 |
| in_window | 299 / 0.028165 / 0.048578 / 0.074235 | 299 / 0.028165 / 0.048578 / 0.074235 |
| post | 370 / 0.488343 / 1.155579 / 1.179271 | 370 / 0.488343 / 1.155579 / 1.179271 |

对齐平移 4.2141 m，archived 868 位姿、rerun 741 位姿、matched 741，全部一致。

**结论：0.028 m 的窗内偏差不是记录者的口径产物。** 未过滤重跑与归档位姿的差异确实在
几厘米量级，远小于米级效应，因此 C3 与 C0 的差别不能归因于重跑抖动。

## 另一个未被记录的依赖（建议补）

四次命令中的两次是 `bash /tmp/fl_run_isolated.sh`。该包装脚本决定了速率（0.5）、
排空时间（60 s）、录制话题（`/aft_mapped_to_init`）、节点启动方式（`rosrun`，
不加载 launch），但它的内容与哈希都**不在记录里**，且位于 `/tmp`。

- 本次被审计版本：`sha256 aba9b27ebc5240706ab22fd058e47d742c6706fa6ca404464fc8de629b588c94`（1,558 B）。
- 它加载的两份 yaml 有哈希（已核对一致），所以配置面是闭合的；
  不闭合的是包装脚本本身：换一个同名脚本，命令列表看起来完全一样。
- 建议：把包装脚本连同哈希收进仓库，或在 `c3_record` 里加
  `commands[].script_sha256`。

## 对 M1/M2 结论的影响

- M1 的 C3 数字（tail 0.0013、coverage 0.9856）不依赖缺失的 point id，**不需要改**。
- M2 若要声称「逐点可归因/可重放」，point id 是阻断项，必须先补。
- 分母（446/252/132）以 `f36137b` 版为准；引用 445 的段落需要统一。
