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
- 输入日志保存可复算的故障前缀。独立原生实例重放前缀，记录原生位姿、速度、偏置、逐帧预积分、活动图和关键帧计数。若两个实例世界坐标不同，从一个早期共同帧估计单个刚体变换。在其后的共同帧和检查点分别检验。地图或原生惯性复算不一致就拒绝。当前是原生前缀复算，未复制所有 Atlas 图结构、线程工作状态、关键帧或预积分内部协方差。
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

输入进程按原始纳秒时戳发送左右 PNG 字节及其 IMU，控制器重放期间持续送入队列。输入队列最多缓存 512 对，溢出记录丢帧。订阅进程收录位姿和接收时钟后逐条应答。使用以下命令对公开交付做校验，并用 Vicon 进行独立位置评分。

```bash
python3 -m slam_recovery.vio.realtime_score "$sequence" "$settings" \
    native native-received.jsonl recovery recovery-received.jsonl
```

传感器时间、发送／接收墙钟和回填历史使用不同字段。算法不读取真值。实时输入可连续运行，但候选复算仍可能引入较长输出停顿，须按订阅端实测判断。

[ORB-SLAM3 论文](https://arxiv.org/abs/2007.11898) · [EuRoC 官方数据](https://projects.asl.ethz.ch/datasets/euroc-mav/)
