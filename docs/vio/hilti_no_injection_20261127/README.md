# Hilti 五段 VIO 无注入对照证据

[对照报告](REPORT.md)记录 ORB-SLAM3、VINS-Fusion、OKVIS2 在相同的双目和 IMU 输入上原生与接入插件的 15 组配对。两组都按 1× 独立放帧。Campus12 的包索引显示没有相机图像，本轮三套 VIO 均无法运行该录制。结果保留拒绝、提前退出、坐标未验证和评分覆盖不足。

- [指标与配对汇总](SUMMARY.json)包含公开交付、原坐标交付、共同位置 RMSE、同帧耗时、CPU 和内存。[相对位姿误差](DENSE_RPE.json)用于稠密真值录制。
- 每段 `trace.tar.gz` 含实验退出回执、逐帧 CSV、外部订阅收到的位姿、资源采样、实际配置及生命周期事件。启动失败的回执也随归档保存。[归档摘要](TRACE_MANIFEST.json)列出校验值。归档内的 `lifecycle.jsonl` 是从运行日志提取的事件；定时和交付细节见逐帧 CSV、订阅记录与评分 JSON。
- [同源核验](AUDIT.json)记录实际运行中共同观察到的帧内容匹配和完整实验归档的摘要。[配对配置核验](PAIR_CONFIG_CHECK.json)记录每对的配置内容。原始全量采集日志与本文仓库内的逐帧归档具有不同范围和摘要。
- [运行版本](HOST_PROVENANCE.txt)固定远程执行时记录的控制器修订 `203c8475bae3b3ed7214a6273d6caf2cebb246d6` 与三个 worker 的 SHA-256。当前分支的代码提交保存工作区现状，远程冻结修订与这次代码提交的逐文件一致性尚未核验。
- 逐条件回执记录真实命令、CPU 配额与启动配置。 `tools/` 保存冻结实验工具。工具里的远程绝对路径和历史归档布局对应测量时的 WSL 环境，移植时需要对应本机的工作目录、二进制和日志位置。

复现需要 Hilti 2022 的 Exp01、Exp04、Exp05、Exp16、Exp18、官方真值和双目与 IMU 标定。包级 SHA-256 和投影输入回执见 [config](config)，真值摘要见 [REFERENCE_MANIFEST.json](REFERENCE_MANIFEST.json)。各段输入和独立真值可从数据发布方取得。 [Hilti 官方数据与许可](https://hilti-challenge.com/dataset-2022)

本目录保留生成的校正配置、用于生成配置的 Hilti 标定和本项目实验记录。标定来自 Hilti SLAM Challenge 2022，沿用数据发布方的 CC BY-NC-SA 3.0 许可。原始 ROS bag、派生图像、参考轨迹原件和可重建缓存未加入 Git。
