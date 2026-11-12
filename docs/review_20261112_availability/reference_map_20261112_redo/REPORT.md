# 重做 clean pass：bag 播到尾、位姿随轨迹移动，但与诊断 run 的轨迹分叉

按审阅三个不可用原因重做一次（不追加第三次）。同 bag、`--detection off`、无 relay/注入/
scripted；宿主 v5（`9e7d8cdf…`）、驱动 `4742dbc1…`；配置副本 `refmap_m2dgr.yaml`
（sha `94ffa5db…`，只开 `pcd_save`、`filter_size_pcd: 0.5`）；drain 60 s + `SAVE_WAIT=180`
（SIGINT 让宿主进 `savePCD()`）。

## 1. 三个原因的复核

| 原因 | 本次结果 |
|---|---|
| **只覆盖前 ~54 s** | **已修**：`rosbag play` Duration **59.981/59.994**、`Done.`；paired **544**、最后 paired ts **1627785320.909**；`lidar_poses.txt` **819 行**到 320.909。 |
| **位姿日志近似静止** | **不成立（上一 pass 的读法问题）**：pose log 的 x 0.00–8.81、y −0.12–8.80；且与诊断 run 同一帧的 `state_pos` 一致（诊断 kf 22 T_wb = 1.3605,−0.1215，clean pose 同一时间 = 1.3605,−0.1215，**逐位相同**）。 |
| **地图与扫描 gauge 不一致** | **PCD/位姿自洽**：用 availability 的 body 样本 + T_wb 对 clean downsampled PCD 做同一 1 m 测试，kf 22（AVAILABLE）**20/20 within 1 m，median 0.25 m**。地图没有 gauge 问题。 |

## 2. 真正断点：两个 run 的宿主轨迹分叉

用同一份 544 行 availability（诊断 run `070801Z`）的 T_wb：

| 诊断帧 | 诊断 T_wb 位置 | clean run 同一 bag 时刻位置 | 对 clean PCD 的 within 1 m |
|---|---|---|---|
| kf 22 | 1.36, −0.12, −0.01 | **1.3605, −0.1215, −0.0086** | **100%（20/20），median 0.25 m** |
| kf 157 | **−25.78, −18.47, 0.47** | 6.80, 4.56, 0.17 | **0%，median 18.44 m** |
| kf 228 | **−19.93, −10.40, −1.80** | 6.75, 8.77, 0.29 | **0%，median 9.0 m** |

诊断 run 自己的 ack 也确认它去过那里：bag 283.48 的 snapshot ack `state_pos=-19.55,-10.40,-1.67`。
clean run 的轨迹范围只有 x 0–8.8 / y −0.12–8.8。**两个 run 在约 15 s 后分叉到 30–40 m 之外**，
因此 clean PCD 只覆盖 clean 轨迹，不覆盖诊断 run 后期的位姿；0 通过是**轨迹分叉**，不是地图或
gauge 的 bug。

## 3. 产物

| 文件 | 值 |
|---|---|
| raw PCD（留磁盘） | `/home/R26534/fast_livo2_ws/src/FAST-LIVO2/Log/pcd/all_raw_points.pcd`，**2,889,123 点**，45 MB，sha `776427a9…dda90b` |
| downsampled PCD（归档） | `all_downsampled_points.pcd`，**15,647 点**，245 KB，sha `f1367c1c…ecb9bb` |
| `lidar_poses.txt` | 819 行，到 bag 末 320.909 |
| 播完时间 | `play.log` Duration **59.981/59.994**，`Done.` |
| 配置 | `refmap_m2dgr.yaml`，sha `94ffa5db…` |
| paired | **544** |

## 4. 断点与选项（停，不追加）

独立参考需要**与诊断 run 同一轨迹**的地图；clean pass 是另一次独立运行，宿主 LIO 在这条输入上
对负载/时序敏感，轨迹会分叉。可行方向：

1. **同 run 地图**：给诊断 run 自己开 `pcd_save`，用它的地图做参考——但那是宿主自己的地图，
   不是独立参考（只能检验日志与自身地图的一致性）。
2. **固定轨迹**：在 clean pass 中使用记录的位姿/gauge（例如把诊断 run 的 `T_wb` 作为 `set_state`
   驱动，或回放带位姿的包），让两次轨迹一致——属于新的运行设计，需要用户决定。
3. **真值**：用 GT 轨迹/地图做参考；本机没有该 bag 的同步 GT。

本次按"仍不可用就停、不追加第三次"结束。门/阈值/σ/检测未动，不声称质量结论。

## 5. 文件

`all_downsampled_points.pcd`、`lidar_poses.txt`、`refmap_m2dgr.yaml`、`pcd_sha256.txt`、
`receipt.json`、`run_summary.json`、`play.log`、`host.log`、`recovery_node.log`、
`machine_load.txt`、`recovery_node_source.sha256`。
