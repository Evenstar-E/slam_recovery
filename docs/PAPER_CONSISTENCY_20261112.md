# 与论文/研究文档的一致性核对（2026-11-12）

读者：S1/S2 与用户。**本文件不改 `paper_main.tex`**，只列出本轮新证据与论文现有表述的关系，供用户决定是否改稿。

## 1. 论文目前的表述（`paper_main.tex`）

- 摘要（第 38 行）与 §limitations（第 413 行）明确把"单宿主、同输入、原生映射 vs 隔离 vs 无条件准入 vs
  验证准入"的对照列为**尚未完成的实验**，并写明"point-cloud injection also leaves the optical response of a
  physical occluder unmeasured"、"does not demonstrate in-place rollback of the host's complete C++ filter"。

## 2. 本轮新增的证据（`SLAM_RECOVERY_RESEARCH.md` §13.21）

- 真实宿主上的原生写回、接回、同一实例第二事件整链，修复测量逐帧进入重放（23/23），状态/地图停在重放边界；
- 这是**受控注入 + 受控触发**（INJECTION / CONTROLLED_INTERFACE_TEST），不是自然故障；
- 仍无 GT 质量评价，仍无自动检测链；`commit_closed→resume` 不可达。

## 3. 结论

- 论文现有表述**没有被本轮证据推翻**：仍未做"自然故障下的原生映射 vs 隔离 vs 准入"对照；
- 可以在论文中补一句已完成的受控整链（限定 INJECTION/受控触发），但它不替代论文承诺的那个实验；
- 若要改稿，建议只改 §limitations 的最后一句与摘要相应短语，**需要用户确认**；本轮不动 `paper_main.tex`、
  不动 `paper_submission_package/`，避免提交物与未确认结论不一致。
