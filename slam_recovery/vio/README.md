# ORB-SLAM3 双目惯性恢复 V1

首个故障是短时双目遮挡。故障窗口只由试验入口用于生成图像，恢复器只看实际输入。原生对照保留 ORB-SLAM3 的 Atlas、重定位和新图能力。检测使用当前两路 FAST 支持与上次原生跟踪、内点分布、重投影和惯性旋转差。启动期未建立可靠地图时不隔离。图像时序、图像观测和 IMU 输入错误分别记录。第一帧可疑就扣住，连续两帧才确认故障。

## 运行

使用独立的 ORB-SLAM3 工作目录，来源为 `0df83dde1c85c7ab91a0d47de7a29685d046f637`。构建依赖为 Pangolin、OpenCV、Eigen 及上游 ORB-SLAM3 的依赖。Ubuntu 20.04 本轮使用已有 OpenCV 4.2 构建兼容改动（上游 CMake 最低版本从 4.4 改到 4.2），不改变算法。运行脚本在 Linux 读取 EuRoC ASL 目录，依赖 Python 3、NumPy、OpenCV 和评分所需的 PyYAML。

```bash
bash slam_recovery/vio/build_worker.sh "$orb" "$build" "$pangolin_cmake"
worker="$build/worker/orb_worker"
settings="$orb/Examples/Stereo-Inertial/EuRoC.yaml"
vocab="$orb/Vocabulary/ORBvoc.txt"
python3 -m slam_recovery.vio.run_euroc "$sequence" "$worker" "$vocab" "$settings" clean --mode qualify --qualify-at 24.90
python3 -m slam_recovery.vio.run_euroc "$sequence" "$worker" "$vocab" "$settings" native --mode native --occlude 25 25.35 --occlude 38 39.7
python3 -m slam_recovery.vio.run_euroc "$sequence" "$worker" "$vocab" "$settings" recovery --mode recover --occlude 25 25.35 --occlude 38 39.7
python3 -m slam_recovery.vio.score "$sequence" "$settings" native/events.jsonl recovery/events.jsonl
```

输出目录须为新路径。用 `ORB_VIO_DRAIN_LOCAL_MAPPING=1` 记录局部建图队列排空后的边界。对比臂须使用相同的设置和步进方式。该选项保留 Atlas，实现的是离线输入调度。它不等同于回环线程和地图的原子快照。

## 恢复语义和测量

- 每个物理输入以同一整数纳秒的左右帧配对，IMU 样本按前开后闭区间归属。完全遮挡的图像不会送进私有恢复实例，累积的全部原始 IMU 样本在下一候选帧送入原生预积分。
- 恢复模式下，独立原生备用实例在故障前逐帧处理和主实例相同的输入，滚动保留最近 16 个同物理戳的原生状态。故障第一帧可疑时，主实例与备用实例都停在最后可信边界。确认后校验惯性状态、活动图与关键帧计数，并用一个较早的共同帧绑定世界坐标，其余共同帧用于验证。候选直接用备用实例继续，只处理隔离窗口内 IMU 和保留区域后的图像。接纳后旧主实例重走该窗口成为新备用。若拒绝前备用已尝试视觉拟合，关闭它；之后缺少可验证备用时安全拒绝。该机制用内存中的原生副本保存检查点。整图序列化和掉电后恢复仍待独立验收。前缀重放仅用于独立的 \`--mode qualify\` 诊断。
- 候选阶段左右图顶部保留给独立检查，候选只使用其余观测。在保留区域做独立双目三角化和 PnP，用同样的物理帧验证重投影和相对位姿。三帧连续通过后才把后续输入切到候选的真实 ORB 实例，并把通过的历史位姿送入公开 JSONL 轨迹流。完全遮住的帧用带偏置修正的原始 IMU 推进，在第一个经独立视觉验证的端点闭合。经闭合检验后，以单独的 inertial_history 类型交付。拒绝后原实例继续健康帧，发布的轨迹须标记原坐标未验证。拒绝之后须连续三个健康原生帧才重武装，正在持续的同一次失明不会重新触发。
- 评分只用独立的 Vicon 观测及官方外参。只用故障前数据做等尺度刚体对齐，保留公开轨迹与共同评分人口。启动、自然快速运动、低视差都留在无注入流中。独立留出为 `V2_01_easy`，开发为 `V1_01_easy`。Hilti Exp16 断言是以前的宿主压力反例，不视为本轮 EuRoC 基线。
- 运行使用独立子进程和单写入者切换。惯性历史是区间内的回顾性轨迹估计。完全遮挡时间超过候选窗口、缺少独立视觉端点、或惯性闭合超过 0.20 m／5° 时不交付原坐标历史。全线程状态快照仍需另验。

## 1× 输入与外部订阅

每一臂启动自己的订阅进程。两个命令使用相同的 Unix socket 路径，路径须位于独占的临时目录，且输出目录为新路径。比较两臂时使用同一 ORB 构建、数据集、故障窗和调度开关。下例把复验范围固定在留出序列的前 950 帧。

```bash
python3 -m slam_recovery.vio.subscribe "$socket" "$arm-received.jsonl" &
subscriber_pid=$!
while [ ! -S "$socket" ]; do sleep 0.05; done
ORB_VIO_DRAIN_LOCAL_MAPPING=1 python3 -m slam_recovery.vio.run_euroc \
    "$sequence" "$worker" "$vocab" "$settings" "$arm" --mode "$mode" \
    --limit 950 --occlude 25 25.35 --occlude 38 39.7 --realtime --subscriber "$socket"
wait "$subscriber_pid"
```

输入进程按原始纳秒时戳发送左右 PNG 字节及其 IMU，控制器重放期间持续送入队列。输入队列最多缓存 512 对，溢出记录丢帧。输入源用 spawn 启动，避免继承控制器持有的候选句柄。健康期备用队列上限为 8 个，触发时核对同一物理帧，最多等待 0.35 秒。验证不通过时，候选在后台收尾。订阅进程收录位姿和接收时钟后逐条应答。使用以下命令对公开交付做校验，并用 Vicon 进行独立位置评分。

```bash
python3 -m slam_recovery.vio.realtime_score "$sequence" "$settings" \
    native native-received.jsonl recovery recovery-received.jsonl
```

传感器时间、发送／接收墙钟和回填历史使用不同字段。算法不读取真值。实时源独立送帧。用实际外部接收时钟衡量停发、复明到普通交付的追赶延迟，以及双宿主并行造成的排队开销。

## 备用异步追赶

用新版 worker，在 recover 命令上加上 `--async-recovery`。若需要从持久快照重建备用，同时使用 `--rebuild-standby --native-checkpoints`。保留原实验的 `ORB_VIO_DRAIN_LOCAL_MAPPING=1` 可对照逐帧等待基线。常规跟踪与镜像仍遵循现有调度。私有候选和短窗追赶走异步建图路径。

隔离后，主实例与备用在同一物理帧读取同步状态，再用原有一致性门核验。候选连续通过三帧留出视觉检查后，只在正式接回前同步一次，复验末帧的原生状态与留出几何。同步失败或状态不一致沿现有拒绝路径。可信快照保存继续使用原有原生加锁接口。新开关需要支持边界协议的 worker。

参见 [异步追赶复验](../../docs/vio/ASYNC_RECOVERY_REPORT.md)。

[ORB-SLAM3 论文](https://arxiv.org/abs/2007.11898) · [EuRoC 官方数据](https://projects.asl.ethz.ch/datasets/euroc-mav/)


### Adaptive holdout and stereo host adapters

ORB-SLAM3 accepts `--adaptive-gate` for the VIO experiment. The controller freezes the reserved cells on the first recovery observation. The independent gate needs eight inliers, a 60% inlier ratio, and support in at least two cells in each frame. The original distance, orientation, reprojection limits and three consecutive qualifying frames still govern admission.

`python3 -m slam_recovery.vio.hosts.build_worker --help` builds either native adapter against its pinned host build. `python3 -m slam_recovery.vio.hosts.controller --help` runs the same stereo recovery controller for both adapters. Run `slam_recovery.vio.subscribe` as the external subscriber. The VINS-Fusion adapter needs ROS Noetic and a dedicated ROS master. Use separate estimator output directories through the primary configuration and `VIO_VINS_SPARE_CONFIG`. The OKVIS2 adapter needs the native vocabulary directory. Both use their recorded stereo/IMU settings and an independent EuRoC camera calibration for verification. The fixed experiment and its raw metrics are described in [the remote VIO report](../../docs/vio/REMOTE_ADAPTIVE_GATE_REPORT.md).

The shared controller runs the standby off the foreground path by default. Use
`--serial-standby` to reproduce the previous schedule on the same inputs. Native
adapters record request and response transport, frontend, and optimization time
as `native_stage` events. The [scheduling report](../../docs/vio/FOREGROUND_SCHEDULING_REPORT.md)
defines the measured stages and reports external receipt latency.

Live input is decoded and checked on a separate ordered queue. Use
`--mode detect` to measure detection while retaining normal host output.
`--primary-cpus` and `--standby-cpus` can assign equal, disjoint Linux CPU
budgets for the role swap. `--standby-backlog` bounds the retained original
updates. A delayed replica earns takeover eligibility only after exact
pre-fault boundary verification.

The OKVIS2 adapter consumes the existing optimized graph callback by default.
Use `--blocking-callback` for a paired test that waits for every native solve.
See the [input and callback report](../../docs/vio/PLUGIN_FLOW_REPORT.md)
for the measured configurations and receipt checks.

### Hilti no-injection comparison

The [paired comparison and evidence](../../docs/vio/hilti_no_injection_20261127/README.md)
cover five Hilti recordings and three VIO hosts. The report includes position
RMSE, original-coordinate and local pose delivery, latency, resource use, and
the refusal and timeout cases.
