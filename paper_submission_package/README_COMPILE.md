# IEEE Transactions Manuscript Submission Package

## Contents
- `paper_main.tex`: Main IEEE Transactions two-column LaTeX manuscript (zero overfull `\hbox`, width-locked tables, figure paths normalized to `figures/`).
- `references.bib`: Complete BibTeX bibliography database (17 entries).
- `IEEEtran.cls` & `IEEEtran.bst`: Official IEEE Transactions class and bibliography style files included for 100% self-contained compilation.
- `figures/`: All 6 core publication figures in both vector `.pdf` (referenced by `paper_main.tex`) and 300-DPI `.png` formats:
  - `fig1_detection_quarantine_timeline.{pdf,png}`
  - `fig2_b0_b7_ablation_matrix.{pdf,png}`
  - `fig3_information_gain_and_gate.{pdf,png}`
  - `fig4_multi_scenario_and_campus_recovery.{pdf,png}`
  - `fig5_orbslam3_second_host_transfer.{pdf,png}`
  - `fig6_phase_transition_and_pareto_sensitivity.{pdf,png}`
- `SLAM_RECOVERY_RESEARCH.md`: Full Chinese research, mathematical modeling, and experimental verification master document.

## How to Compile
1. **Overleaf (Recommended for 1-click cloud compilation)**:
   - Upload `paper_submission_package.zip` directly via **New Project -> Upload Project**.
   - It compiles out-of-the-box with `pdfLaTeX`.
2. **Local TeX Live / MiKTeX / MacTeX**:
   ```bash
   pdflatex paper_main.tex
   bibtex paper_main
   pdflatex paper_main.tex
   pdflatex paper_main.tex
   ```
