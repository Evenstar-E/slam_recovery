# M2DGR `hall_01` → NVIDIA Isaac Sim 5.1 场景包

由真实 `hall_01.bag`（VLP-32C 点云 + `/handsfree/imu` 姿态）与 `hall_01_plasticbag_comparison.mcap`
（Leica MS60 真值、B0/B2 退化、B6 修复轨迹）离线生成，无 ROS 运行依赖。

## 姿态标定（关键）
`hall_01` 为手持序列，操作者会原地旋转与倒退，因此**轨迹切向不能当作机体姿态**。
本场景使用 `/handsfree/imu` 的 AHRS 偏航角 + 常量偏移 `θ₀ = 99.10°`
（sign = +1），按墙面锐度搜索得到：占用 25 cm 栅格从 16524 降到 10927（-33.9 %）。
原始与标定后的对比见 `hall_01_alignment_diagnosis.png`。

## 文件
| 文件 | 说明 |
|---|---|
| `hall_01_isaac_scene.usda` | Isaac Sim 5.1 原生 USD 场景（推荐，直接 `File → Open`） |
| `hall_01_scene_geometry.obj` + `.mtl` | 通用三角网格，可导入 Blender / MeshLab |
| `hall_01_pointcloud_colored.ply` | 分色点云（灰地板 / 蓝可信墙 / 红 B0 污染 / 黄 B2 拖尾） |
| `run_in_isaac_sim_5_1.py` | 一键加载并播放时间线 |
| `hall_01_export_manifest.json` | 体素数、三角形数、标定参数等出处记录 |

## USD 结构
- `/World/Hall01_Trusted_Environment/Colliders` — **带 `PhysicsCollisionAPI` 的地板与墙/柱**，可直接跑 Nav2/机器人
- `/World/Contamination_Overlay/B0_Unprotected` — 按 B0 漂移位姿注册的墙面 + 注入的近场遮挡面（半透明红）
- `/World/Contamination_Overlay/B2_MMLINS_Tail` — MM-LINS 确认延迟尾漂移（半透明黄）
- `/World/Trajectories` — Leica GT / B0 / B2 / B6 四条三维曲线
- `/World/Gate_Beacons` — `t=118.0 s` 检查点（绿）与 `t=140.4 s` Mode-2 原子提交（青）
- `/World/Animated_Robots` — 四台带 0–350 帧关键帧的机器人，按 Play 同步行驶

## 打开方式
- **GUI**：拷到装有 Isaac Sim 5.1 的机器 → `File → Open` → 选 `hall_01_isaac_scene.usda` → 按空格播放
- **命令行**：`/path/to/isaac-sim-5.1/python.sh run_in_isaac_sim_5_1.py`

## 出处声明
墙/地面几何来自真实 `hall_01` 扫描；B0/B2 图层用**同一批真实扫描**按各自退化位姿注册，
并按 `INJECTION` 协议补入 88 % 视场、4.30 m 的近场遮挡面，用于可视化地图污染，
不是新的实验结论。
