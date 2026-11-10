# KITTI备用未见测试集：具体序列与数据清单

日期2026-11-10。目的：方法冻结后的备用新环境测试，不替代当前hall/room原生恢复运行。仅给准备方案，**本次没有下载、登录数据网站、安装转换器或执行KITTI实验**。

## 1. 具体预留哪些子集

建议按**整条原始drive隔离**，预留Odometry **05、07**作为首轮冻结后测试，**08**作为后续不打开的备用。这些是官方Odometry公开参考轨迹的00–10集合中的序列；“官方training”不妨碍它成为本项目未参与开发的测试，但不能称KITTI官方隐藏test。

| 用途 | Odometry序列 | 对应Raw同步drive（常用对应关系，下载后需核时序） | 使用原则 |
|---|---|---|---|
| 首轮备用 | `05` | `2011_09_30_drive_0018_sync` | 整drive留出，不拿前半段调参再把后半段称未见 |
| 首轮备用 | `07` | `2011_09_30_drive_0027_sync` | 第二条独立drive，保持同方法/同门不改参数 |
| 进一步封存 | `08` | `2011_09_30_drive_0028_sync` | 在05/07暴露问题并再次开发后，仍可作为新的封存确认对象；打开后不再保持未见身份 |

标准对应关系中，Odometry08是其Raw drive的**子段，不从Raw第0帧开始**；常见对照为Raw帧1100–5170。05为0–2760，07为0–1100（均含端点）。本次官方页面因登录限制未提供逐drive清单，**这些映射/边界尚未通过本地下载文件独立核验**；转换前用原始timestamps、首末扫描/图像与轨迹对应验证，不凭序列名盲目按下标join。正式manifest以核验后的身份/边界为准，不将这里的帧数当实测人口。

本机仓库搜索只找到SC-PGO通用KITTI helper/config，没有找到这些drive的本项目实验记录；**无法据此保证远端开发历史未使用**。S1/S2/S3/Codex需核现有实验/调参记录：曾用于方法选择、阈值或参数调整的drive不能入本项目未见集；必须按整个drive剔除或另选新drive，不只换帧段。下载/传感器格式核验本身可以准备，但用恢复效果选择方法就属于开发。

## 2. 当前FAST-LIVO2/LIO需要什么——不能只下Odometry

官方Odometry下载提供图像、Velodyne、标定和00–10参考轨迹，**未列IMU包**。若当前宿主依赖IMU，只有Odometry XYZ/reflectance与poses不能直接作为完整LIO/LIVO输入。

**按当前原生LiDAR＋IMU＋相机路线，最低准备：**

| 数据 | 具体下载/保留内容 | 作用 |
|---|---|---|
| Raw同步数据 | `2011_09_30_drive_0018_sync.zip`、`2011_09_30_drive_0027_sync.zip`；封存`2011_09_30_drive_0028_sync.zip` | LiDAR、对应相机、同步OXTS和timestamps；按官网实际可用包名下载并记录hash |
| Raw未同步/未整流原始数据 | 三条drive对应的unsynced/unrectified archive，通常以`*_extract.zip`分发；至少原生OXTS/IMU及其原始timestamps，配合所选图像类型 | 核实真实IMU采样和图像时序，不将10Hz同步OXTS复制/插值成“真实高频IMU” |
| 当日标定 | `2011_09_30_calib.zip`中的`calib_cam_to_cam.txt`、`calib_velo_to_cam.txt`、`calib_imu_to_velo.txt` | camera内参/整流、IMU↔LiDAR↔camera外参。整流图像必须配整流相机模型，不能直接套hall/room YAML |
| 官方Odometry参考 | poses包的`05.txt`、`07.txt`、`08.txt`；各序列calib与`times.txt`（由对应序列数据获取） | 公开轨迹评价与Raw子段对应。参考在camera0坐标表达，须用实际标定转到宿主输出坐标 |
| 身份/时间文件 | `velodyne_points/timestamps*.txt`、所选`image_*/timestamps.txt`、`oxts/timestamps.txt`；原始点索引、源文件/输出bag hash | 数据转换、同步、点身份和复算 |

若官方下载只能整包获取，则保留整包；这里的“最低内容”不是要求网站支持按目录下载。完整Odometry点云/双目包与Raw内容重复时，不必一律两份都下；使用Raw作输入、官方poses作评价，并补实际对应所需的Odometry时间/标定。只有切换到不需要IMU的宿主才考虑Odometry-only路线，这会改变实验能力范围，当前不为KITTI另换宿主。

### 每条Raw drive中需要保留的目录

```text
velodyne_points/data/*.bin
velodyne_points/timestamps.txt
velodyne_points/timestamps_start.txt   （若归档提供）
velodyne_points/timestamps_end.txt     （若归档提供）
image_02/data/*.png + image_02/timestamps.txt   （彩色左目路线）
  或 image_00/data/*.png + timestamps.txt      （明确灰度左目路线）
oxts/data/*.txt + oxts/timestamps.txt
当日camera/IMU/Velodyne标定文件
```

FAST-LIVO2单目路线先保留一侧相机即可；不用同时引入左右目。若后续确有双目基线再准备image_01或image_03。如果相机处理只需要RGB/灰度转换，转换要记录，别把两个camera id混同。

## 3. 两个适配限制必须先说明，但不扩防御框架

1. **真实IMU采样，不靠补点。**官网说明同步数据是10Hz，不能据传感器名义频率推断下载包里有100Hz独立样本。读取原始OXTS时间间隔及gyro/acc字段确认实际频率和坐标单位。若高频原件不可获取或当前宿主无法使用该采样，KITTI对该LIO路线标BLOCKED/不适配，不复制10Hz消息充数，也不把该失败当恢复算法失败。
2. **点云格式不是现bag格式。**KITTI Velodyne常见二进制是4个float的XYZ＋reflectance，**不直接提供ring和逐点时间**。当前宿主如依赖这些字段，复用已支持的Velodyne/HDL-64预处理；由角度/扫描周期推导的ring/time需明确标派生近似，不能称原生记录。若需要所配设备校准，保留官方Velodyne校准；不把XYZI直接冒充已有hall/room完整PointCloud2记录。

本仓库[SC-PGO kittiHelper](../SC-PGO/src/kittiHelper.cpp)发布XYZI、图像和GT，未形成当前FAST-LIVO2所需IMU输入链；不能“已有helper”就认定LIO转换已完成。尤其GT话题只作评价，不进入修复器或门。

## 4. 如何保持“未见”，又避免再调参循环

- 先冻结当前方法、已有科学门、输入适配约定和评测方式；KITTI传感器内参/外参和数据格式适配不是算法调参，但要与效果驱动修改分开记录。
- 用非预留drive做传感器适配/健康校准；05/07/08不用于选恢复超参数。若已经使用05或07来改方法，承认其成为开发数据，08仍保持封存；整个Raw drive不得跨开发/测试共享。
- 按预声明的同类故障注入对照与健康数据评估；KITTI新环境可检验转移边界，但人工注入结果不自动证明自然故障恢复。
- 官方11–21是隐藏参考轨迹的test，**不作为首次备用**：不利于本地独立ATE/逐事件复算；不要以无GT测试段替代可检验的05/07。
- OXTS融合位置/姿态与官方reference pose只用于离线评价，不作候选初值/重入锚点/在线标签。输入的原始gyro/acc与OXTS参考可能共享传感器来源，披露参考并非完全独立测量链。
- KITTI轨迹GT不等于稠密地图真值；若以clean run地图作参考继续明确proxy，不用本方法候选自身地图自证。
- 未见测试结果出来后，不在同一05/07上反复调参再称独立确认；按PROJECT_HISTORY§2.1总结规律/上限并决定冻结或换方法。

## 5. 本次准备的优先级

**主线先跑[NATIVE_RECOVERY_RUN_TASK](NATIVE_RECOVERY_RUN_TASK_20261110.md)。KITTI仅备用数据准备，不触发下载/新宿主/新参数实验，不阻塞现有hall两事件运行。**数据网站登录由用户/执行侧使用自己的合法账号，本会话不改认证、不填密码。

官方页面确认了模态、同步/未同步区分、标定与公开GT边界；逐drive映射与实际采样需要下载后核验。没有虚报下载大小、原生IMU率或本项目真正未见状态。

## 来源

- [KITTI Raw官方说明与下载入口](https://www.cvlibs.net/datasets/kitti/raw_data.php)：同步/未同步版本、LiDAR、相机、GPS/IMU、timestamps与标定；当前下载需登录。
- [KITTI Odometry官方说明](https://www.cvlibs.net/datasets/kitti/eval_odometry.php)：00–10公开参考、11–21无公开参考、图像/Velodyne/标定/poses包。
- [KITTI传感器设置](https://www.cvlibs.net/datasets/kitti/setup.php)：LiDAR/相机10Hz与相机触发方式；不能由此假定下载IMU采样率。
- [pykitti Raw loader](https://github.com/utiasSTARS/pykitti/blob/master/pykitti/raw.py)：Raw目录命名、OXTS/时间戳、XYZ/reflectance与标定变换；第三方实现，不是新实验结果。
- [kitti2bag现有转换器](https://github.com/tomas789/kitti2bag/blob/master/scripts/kitti2bag)：Raw的OXTS导出，一条源记录对应一条IMU；Odometry分支不导出IMU。仅参考，未下载执行，不据它宣称兼容FAST-LIVO2。
