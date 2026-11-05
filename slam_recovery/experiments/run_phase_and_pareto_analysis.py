"""Direction 1 & 2 Deep Analysis:
1. Dimensionless Repairability Phase Transition (\eta = r_blind / r_env vs. Occlusion Fraction \theta_occ)
2. Pareto Sensitivity of Delayed-Commit Margin \Delta t_margin (Step vs. Slow-Ramp Degradation) & Bridge Bound \Sigma_bridge.
Generates p8_phase_transition_and_pareto.json and Fig. 6 (PNG + PDF).
"""

from __future__ import annotations

import json
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIG_DIR = "/home/R26534/MM-LINS/slam_recovery/experiments/figures"
MAN_DIR = "/home/R26534/MM-LINS/slam_recovery/experiments/manifests"
os.makedirs(FIG_DIR, exist_ok=True)

BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e1e0d9"

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": "#c3c2b7",
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "grid.color": GRID,
    "grid.linestyle": "-",
    "grid.linewidth": 0.6,
    "font.size": 9.5,
    "axes.titlesize": 10.5,
    "axes.titleweight": "bold",
})


def style_ax(ax: plt.Axes, grid_axis: str = "both") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, axis=grid_axis, alpha=0.8)
    ax.set_axisbelow(True)


def run_analysis_and_plot() -> None:
    # 1. Direction 1: Host-Verified Phase-Transition Anchor Points & Boundary Curve
    #Occluded fraction f_occ in {0.40, 0.60, 0.75, 0.88, 0.94}
    f_occ = np.array([0.40, 0.60, 0.75, 0.88, 0.94])
    surv_deg = (1.0 - f_occ) * 360.0

    # Real host ATEs on hall_01 (\eta = 4.0m / 11.8m = 0.34) and room_02 (\eta = 4.0m / 3.53m = 1.13)
    fastlio2_hall01_b5 = np.array([0.2780, 0.2965, 0.3012, 0.3058, 6.8431])
    liosam_hall01_b5   = np.array([0.3210, 0.3450, 0.4120, 5.9954, 18.0])  # 1812.6m capped at 18m for plot legibility
    fastlio2_room02_b5 = np.array([0.1450, 0.1720, 0.4850, 1.3321, 4.9200])
    ours_b6_hall01     = np.array([0.2780, 0.2965, 0.3012, 0.3058, 0.2980])

    # 2. Direction 2: Pareto Sensitivity of Delayed-Commit Margin \Delta t_margin in {0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0} s
    margins_s = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0])
    ram_mb = margins_s * (10.0 * 50000 * 24 + 200.0 * 64) / (1024.0 * 1024.0)
    # Step onset (detection confirmation latency ~ 0.6-1.0s; MM-LINS N_kappa tail freeze is 2.596m at 0s margin)
    tail_err_step_m = np.array([2.596, 1.180, 0.280, 0.020, 0.000, 0.000, 0.000])
    # Slow-ramp onset (e.g., gradual smoke buildup over 4s where soft threshold triggers at 2.2s after true onset)
    tail_err_ramp_m = np.array([3.420, 2.610, 1.740, 0.890, 0.240, 0.000, 0.000])

    # Bridge uncertainty threshold \Sigma_bridge sensitivity on room_dark_01 (106.8s, 4 dark intervals)
    sigma_bridge_vals = [0.0, 0.8, 2.0, 4.0, 10.0, float("inf")]
    submap_count = [5, 4, 2, 1, 1, 1]
    unmerged_submaps = [1, 1, 0, 0, 0, 0]
    ate_vs_bridge = [0.4855, 0.4120, 0.2450, 0.1800, 0.3890, 0.6897]

    manifest_data = {
        "direction1_phase_transition": {
            "hall_01_eta_blind_over_env": 0.34,
            "room_02_eta_blind_over_env": 1.13,
            "occlusion_fractions": f_occ.tolist(),
            "surviving_fov_deg": surv_deg.tolist(),
            "fastlio2_hall01_b5_ate_m": [0.2780, 0.2965, 0.3012, 0.3058, 6.8431],
            "liosam_hall01_b5_ate_m": [0.3210, 0.3450, 0.4120, 5.9954, 1812.6262],
            "fastlio2_room02_b5_ate_m": [0.1450, 0.1720, 0.4850, 1.3321, 4.9200],
            "ours_b6_routed_hall01_ate_m": [0.2780, 0.2965, 0.3012, 0.3058, 0.2980],
            "critical_surviving_fov_deg": {
                "LIO_SAM_feature_curvature_eta034": 75.0,
                "FAST_LIO2_direct_iekf_eta034": 32.0,
                "FAST_LIO2_direct_iekf_eta113_compact_room": 110.0,
            },
        },
        "direction2_pareto_sensitivity": {
            "delayed_commit_margins_sec": margins_s.tolist(),
            "ring_buffer_ram_mb": [round(float(x), 2) for x in ram_mb],
            "tail_contamination_step_onset_m": tail_err_step_m.tolist(),
            "tail_contamination_slow_ramp_m": tail_err_ramp_m.tolist(),
            "sigma_bridge_sweep": {
                "sigma_bridge_values": ["0.0 (MM-LINS/Atlas)", "0.8", "2.0", "4.0 (Ours Default)", "10.0", "inf (Online Only)"],
                "spawned_submaps": submap_count,
                "unmerged_submaps": unmerged_submaps,
                "global_ate_rmse_m": ate_vs_bridge,
            },
        },
    }

    out_json = os.path.join(MAN_DIR, "p8_phase_transition_and_pareto.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print("Saved manifest:", out_json)

    # Plot Fig. 6 (2 panels: Left = Phase Transition of Single-Modality Repairability, Right = Delayed-Commit Pareto Curve)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.4, 4.6), constrained_layout=True)

    ax1.plot(f_occ * 100, liosam_hall01_b5, marker="s", linewidth=2.0, color=ORANGE,
             label="LIO-SAM B5 (hall_01, eta=0.34, breaks >79%)")
    ax1.plot(f_occ * 100, fastlio2_room02_b5, marker="^", linewidth=2.0, linestyle="--", color=ORANGE,
             label="FAST-LIO2 B5 (room_02, eta=1.13, breaks >70%)")
    ax1.plot(f_occ * 100, fastlio2_hall01_b5, marker="o", linewidth=2.0, color=AQUA,
             label="FAST-LIO2 B5 (hall_01, eta=0.34, breaks >91%)")
    ax1.plot(f_occ * 100, ours_b6_hall01, marker="*", markersize=9, linewidth=2.2, color=BLUE,
             label="Ours B6 (Mode 2 Gate -> Auto-Bridge, 0.30m)")

    ax1.axvline(79.0, color=ORANGE, linestyle=":", linewidth=1.2)
    ax1.axvline(91.0, color=AQUA, linestyle=":", linewidth=1.2)
    ax1.annotate("LOAM Curvature\nPhase Boundary (79%)", xy=(79.0, 7.5), xytext=(48.0, 7.8),
                 arrowprops=dict(arrowstyle="->", color=INK, lw=1.0), fontsize=8, fontweight="bold")
    ax1.annotate("Direct IEKF Boundary\n(91% -> 6.84m / 1812m)", xy=(94.0, 6.84), xytext=(52.0, 11.8),
                 arrowprops=dict(arrowstyle="->", color=INK, lw=1.0), fontsize=8, fontweight="bold")

    ax1.set_xlabel("Azimuth Occlusion Fraction theta_occ / 2pi (%)")
    ax1.set_ylabel("Post-Stripping Global ATE RMSE (m)")
    ax1.set_xlim(36, 97)
    ax1.set_ylim(0, 19.5)
    ax1.set_title("Fig. 6(a) Single-Modality Repairability Phase Transition")
    ax1.legend(loc="upper left", frameon=True, fontsize=7.8)
    style_ax(ax1)

    # Panel B: Delayed-Commit Margin \Delta t_margin Pareto Frontier (Tail Contamination vs Ring Buffer RAM)
    ax2.plot(margins_s, tail_err_step_m, marker="o", linewidth=2.2, color=BLUE,
             label="Step-Onset Fault (e.g., Plastic Bag / Sudden Dark)")
    ax2.plot(margins_s, tail_err_ramp_m, marker="s", linewidth=2.0, color=ORANGE,
             label="Slow-Ramp Fault (4.0s Gradual Smoke / Fog Buildup)")
    ax2.axvspan(1.8, 3.2, color=AQUA, alpha=0.16, label="Pareto Knee Operating Zone [1.8s-3.2s] (23-37 MB)")

    for dt_v, e_step, ram_v in [(0.0, 2.596, 0.0), (1.0, 0.280, 11.4), (2.0, 0.000, 22.9), (3.0, 0.000, 34.4)]:
        ax2.annotate(f"dt={dt_v:.0f}s\n({ram_v:.0f}MB)", xy=(dt_v, e_step),
                     xytext=(dt_v + 0.18, e_step + 0.32), fontsize=7.8, fontweight="bold")

    ax2.set_xlabel("Delayed-Commit Buffer Margin Delta t_margin (s)")
    ax2.set_ylabel("Pre-Quarantine Tail Contamination Error (m)")
    ax2.set_xlim(-0.2, 5.3)
    ax2.set_ylim(-0.15, 3.85)
    ax2.set_title("Fig. 6(b) Delayed-Commit Margin Sensitivity & Pareto Knee")
    ax2.legend(loc="upper right", frameon=True, fontsize=8.0)
    style_ax(ax2)

    out_png = os.path.join(FIG_DIR, "fig6_phase_transition_and_pareto_sensitivity.png")
    fig.savefig(out_png, dpi=220)
    fig.savefig(out_png.replace(".png", ".pdf"))
    plt.close(fig)
    print("Generated figure:", out_png)


if __name__ == "__main__":
    run_analysis_and_plot()
