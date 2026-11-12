# 干净参考地图 pass（供独立参考评分）

任务：产出一份**干净运行**的 PCD 参考地图，供 S1 的 `independent_reference.py` 对
`predicted_pose` 的 544 行做离线独立评分。本 pass 只产图，不做可用性诊断、不注入、不触发。

## 1. 运行

| 项 | 值 |
|---|---|
| run | `fl_native_20261112T083858Z_263020` |
| bag | `/tmp/fastlivo/hall01_two_event_v1.bag`，sha `c3e905da…` |
| 模式 | `--detection off`，**无 relay/注入**，**无 scripted 触发**，无 availability log |
| 宿主 | v5，库 sha `9e7d8cdf…`，可执行文件 `0d7e23de…` |
| 驱动源码 sha | `4742dbc1…` |
| 配置 | **副本** `refmap_m2dgr.yaml`（sha `94ffa5db…`），只改 `pcd_save.pcd_save_en: true` 与 `filter_size_pcd: 0.5`；部署 config 本体未动 |
| 终态 | HEALTHY，wiring all_ok |

跑完整 bag（59.99 s）。宿主退出的保存路径需要 SIGINT（`ros::ok()` 变 false 后 `run()` 走到
`savePCD()`）；runner 新增 `SAVE_WAIT` 先发 SIGINT、等待保存、再 TERM/KILL（默认关闭，仅本 pass
使用）。第一次不带等待时 PCD 未生成，第二次带等待后成功——这条记录在此，避免误以为配置无效。

## 2. 产物

| 文件 | 点数 | 大小 | sha256 |
|---|---:|---:|---|
| `all_downsampled_points.pcd`（已归档） | **13,493** | 212 KB | `001bfb45…e30876` |
| `all_raw_points.pcd`（留在磁盘，未入库） | **2,498,791** | 39 MB | `473c6b24…85eb83` |

原始 PCD 路径：`/home/R26534/fast_livo2_ws/src/FAST-LIVO2/Log/pcd/all_raw_points.pcd`
（按 `ROOT_DIR` 写在宿主源码树的 `Log/pcd/` 下）。39 MB 未超过 500 MB，但为避免仓库膨胀，归档里
只放 downsampled；raw 的路径与 sha 在 `pcd_sha256.txt`，需要时可从磁盘取。

`lidar_poses.txt` 也归档（62 KB），用于核对世界系与位姿时间线。

## 3. 供离线评分的使用方式

- 该 PCD 是**世界系**（`type: 0`），由一次干净运行构建，不含注入、不含隔离期修复。
- `independent_reference.py` 用 availability 行的 body 样本 + `T_wb` 做同一支持测试；PCD 只作为
  参考地图。可选 ICP 对齐的种子是宿主位姿，对齐后的 fraction 说明几何覆盖，修正量说明位姿偏差。
- 本 pass **不声称任何质量结论**；PCD 只是参考，不是真值。GT 仍缺。

## 4. 边界

- 不改门/阈值/σ/检测；不做可用性字段；不声称修复收益或定位精度。
- 参考地图来自同一 bag、同一宿主版本；换输入或换宿主需要重新产图，跨 run 不可直接复用。

## 5. 文件

`all_downsampled_points.pcd`、`lidar_poses.txt`、`refmap_m2dgr.yaml`、`pcd_sha256.txt`、
`receipt.json`、`run_summary.json`、`host.log`、`recovery_node.log`、`machine_load.txt`、
`recovery_node_source.sha256`。
