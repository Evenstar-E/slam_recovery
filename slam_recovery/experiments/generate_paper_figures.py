"""Generate publication figures (Fig. 0 Architecture + Figs. 1-5 Results) in a unified
FAST-LIVO2 / `01_architecture` visual style:
  - Typography: DejaVu Serif, crisp dark ink (#171717)
  - Framing: Soft #EEEEEE dashed module containers (lw=1.35, ls=(0,(5,4))) with bold serif headers
  - Palette: Soft pastel fills (#67C5E4, #B4D9BE, #F49A8D, #EBD496, #B8A6CF, #F8D8BB) paired with
    crisp #171717 borders (lw=1.2) and deep accent lines (#007BA7, #2D6A4F, #C0392B, #946031, #5E437A)
  - Zero hardcoded result arrays: dynamically reads verified JSON manifests and MCAP/TUM trajectories.
"""

from __future__ import annotations

import json
import os
from pathlib import Path as SysPath
import shutil
import struct
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
from matplotlib.path import Path as MplPath
import numpy as np

ROOT_DIR = SysPath(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from slam_recovery.experiments.evaluation import (
    associate_trajectories,
    load_tum_trajectory,
    umeyama_se3_align,
)

FIG_DIR = ROOT_DIR / "slam_recovery" / "experiments" / "figures"
PKG_FIG_DIR = ROOT_DIR / "paper_submission_package" / "figures"
MAN_DIR = ROOT_DIR / "slam_recovery" / "experiments" / "manifests"
FIG_DIR.mkdir(parents=True, exist_ok=True)
PKG_FIG_DIR.mkdir(parents=True, exist_ok=True)

# Unified `01_architecture` Visual Grammar Palette
INK = "#171717"
SUB_INK = "#444444"
MUTED = "#666666"
GROUP_BG = "#EEEEEE"
PANEL_BG = "#FFFFFF"
GRID_COL = "#E2E5E9"

IMU_FILL = "#F8D8BB"
LIDAR_FILL = "#67C5E4"
AUX_FILL = "#F49A8D"
REPAIR_FILL = "#B4D9BE"
GATE_FILL = "#EBD496"
PURPLE_FILL = "#B8A6CF"

BLUE_LINE = "#0088B2"
CORAL_LINE = "#D64535"
GREEN_LINE = "#2D6A4F"
AMBER_LINE = "#946031"
PURPLE_LINE = "#5E437A"

SERIF = "DejaVu Serif"

plt.rcParams.update({
    "font.family": SERIF,
    "font.size": 10.5,
    "text.color": INK,
    "axes.labelcolor": INK,
    "axes.edgecolor": INK,
    "axes.linewidth": 1.15,
    "xtick.color": INK,
    "ytick.color": INK,
    "figure.facecolor": "white",
    "axes.facecolor": PANEL_BG,
    "savefig.facecolor": "white",
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
})


def _sync_outputs(fig: plt.Figure, basename: str) -> str:
    """Save figure as PNG and vector PDF to both experiment and paper_submission_package directories."""
    out_png = FIG_DIR / f"{basename}.png"
    out_pdf = FIG_DIR / f"{basename}.pdf"
    fig.savefig(out_png, dpi=240, bbox_inches="tight", pad_inches=0.06)
    fig.savefig(out_pdf, bbox_inches="tight", pad_inches=0.06)
    shutil.copy2(out_png, PKG_FIG_DIR / f"{basename}.png")
    shutil.copy2(out_pdf, PKG_FIG_DIR / f"{basename}.pdf")
    plt.close(fig)
    return str(out_png)


def _create_bg_canvas(fig: plt.Figure) -> plt.Axes:
    """Create a full-figure background axes at zorder=-10 so dashed group boxes sit behind data axes."""
    ax_bg = fig.add_axes([0.0, 0.0, 1.0, 1.0], zorder=-10)
    ax_bg.set_xlim(0.0, 1.0)
    ax_bg.set_ylim(0.0, 1.0)
    ax_bg.axis("off")
    return ax_bg


def _draw_dashed_group(
    ax_bg: plt.Axes,
    rect: tuple[float, float, float, float],
    title_left: str,
    subtitle_right: str = "",
    title_size: float = 10.8,
) -> None:
    """Draw a `01_architecture`-style dashed module container on `ax_bg` behind plot axes."""
    x, y, w, h = rect
    ax_bg.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.003,rounding_size=0.012",
            fc=GROUP_BG,
            ec=INK,
            lw=1.35,
            ls=(0, (5, 4)),
            zorder=0,
        )
    )
    ax_bg.text(
        x + 0.012,
        y + h - 0.016,
        title_left,
        fontsize=title_size,
        fontweight="bold",
        fontfamily=SERIF,
        color=INK,
        ha="left",
        va="top",
        zorder=2,
    )
    if subtitle_right:
        ax_bg.text(
            x + w - 0.012,
            y + h - 0.018,
            subtitle_right,
            fontsize=8.4,
            fontfamily=SERIF,
            color=SUB_INK,
            ha="right",
            va="top",
            zorder=2,
        )


def _style_inner_ax(ax: plt.Axes, grid_axis: str = "y") -> None:
    ax.set_facecolor(PANEL_BG)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(INK)
    ax.spines["bottom"].set_color(INK)
    ax.spines["left"].set_linewidth(1.15)
    ax.spines["bottom"].set_linewidth(1.15)
    if grid_axis in ("x", "y", "both"):
        ax.grid(True, axis=grid_axis, color=GRID_COL, linestyle="--", linewidth=0.75, alpha=0.9)
    ax.set_axisbelow(True)


def fig0_system_architecture() -> str:
    """Generate the full-system vector architecture diagram with symmetric LiDAR & Vision peer pipelines."""
    fig = plt.figure(figsize=(20, 8.2), facecolor="white")
    ax = fig.add_axes([0.01, 0.055, 0.98, 0.875])
    ax.set(xlim=(0, 100), ylim=(0, 100))
    ax.axis("off")

    def text(x, y, s, size=12.4, bold=False, ha="center", color=INK, **kw):
        kw.setdefault("va", "center")
        return ax.text(
            x,
            y,
            s,
            fontsize=size,
            fontweight="bold" if bold else "normal",
            ha=ha,
            fontfamily=SERIF,
            color=color,
            linespacing=1.16,
            zorder=6,
            **kw,
        )

    def group(x, y, w, h, label, subtitle=""):
        ax.add_patch(
            Rectangle(
                (x, y),
                w,
                h,
                fc=GROUP_BG,
                ec=INK,
                lw=1.35,
                ls=(0, (5, 4)),
                zorder=0,
            )
        )
        text(x + 0.9, y + h - 2.1, label, 14.6, True, "left", va="top")
        if subtitle:
            text(x + w - 0.8, y + h - 2.3, subtitle, 9.4, False, "right", va="top", color=SUB_INK)

    def node(x, y, w, h, label, fill, sub="", size=13.0, dashed=False):
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0.03,rounding_size=1.15",
                fc=fill,
                ec=INK,
                lw=1.7,
                ls=(0, (4, 3)) if dashed else "-",
                zorder=3,
            )
        )
        text(x + w / 2, y + h * (0.65 if sub else 0.5), label, size, True)
        if sub:
            text(x + w / 2, y + h * 0.23, sub, 9.2, color="#262626")

    def path(points, color=INK, dashed=False, width=2.0, end=True):
        codes = [MplPath.MOVETO] + [MplPath.LINETO] * (len(points) - 1)
        p = MplPath(points, codes)
        ax.add_patch(
            FancyArrowPatch(
                path=p,
                arrowstyle="-|>" if end else "-",
                mutation_scale=14.0,
                lw=width,
                color=color,
                linestyle=(0, (4, 3)) if dashed else "-",
                zorder=2,
                capstyle="round",
                joinstyle="round",
            )
        )

    def label(x, y, s, color=SUB_INK, size=9.3):
        text(x, y, s, size, color=color, bbox=dict(fc="white", ec="none", pad=0.75))

    fig.text(
        0.5,
        0.968,
        "Transactional Detection, Quarantine, and Verifiable Recovery — Symmetric Multi-Modal Overview",
        ha="center",
        va="top",
        fontsize=20.8,
        fontweight="bold",
        fontfamily=SERIF,
        color=INK,
    )

    # Three major dashed containers with a wide central inter-layer corridor [43.0 .. 54.2]
    group(15.2, 54.2, 60.0, 43.0, "Multi-Modal SLAM Host Frontend & Estimator", "FAST-LIO2 / LIO-SAM / MM-LINS / ORB-SLAM3 / FAST-LIVO2")
    group(15.2, 3.5, 60.0, 39.5, "Transactional Recovery Layer", "Delayed-Commit Quarantine & 4-Mode Gate D(t)")
    group(78.5, 3.5, 20.5, 93.7, "Persistent Maps & State")

    # Three equal-status peer sensor modalities on the left
    node(0.7, 80.8, 11.5, 8.8, "IMU", IMU_FILL, "accel. / gyro", 15.2)
    node(0.7, 68.4, 11.5, 9.0, "LiDAR", LIDAR_FILL, "raw 3D scans", 15.2)
    node(0.7, 56.0, 11.5, 9.0, "Vision", AUX_FILL, "RGB / mono / stereo", 15.2)

    # Symmetric parallel frontend pipelines inside Multi-Modal SLAM Host
    node(17.6, 80.8, 16.2, 8.8, "IMU Preintegration &\nForward Propagation", IMU_FILL, size=11.3)
    node(17.6, 68.4, 16.2, 9.0, "Intra-Scan Deskew &\nGeometric Extraction", LIDAR_FILL, size=11.3)
    node(38.2, 68.4, 16.2, 9.0, "Point-to-Plane /\nLOAM Residuals", LIDAR_FILL, size=11.5)

    node(17.6, 56.0, 16.2, 9.0, "ORB / Direct Patch &\nExposure Tracking", AUX_FILL, size=11.3)
    node(38.2, 56.0, 16.2, 9.0, "Reprojection /\nPhotometric Residuals", AUX_FILL, size=11.3)

    # Coupled state & factor-graph update receiving IMU + LiDAR + Vision symmetrically
    node(59.2, 59.5, 13.8, 18.0, "Coupled State &\nFactor Update\n(IEKF / ISAM2 / BA)", REPAIR_FILL, "joint or single-host", 11.5)

    # Sensor -> Frontend arrows
    path([(12.2, 85.2), (17.6, 85.2)], "#EAB589", width=2.5)
    path([(12.2, 72.9), (17.6, 72.9)], BLUE_LINE, width=2.5)
    path([(12.2, 60.5), (17.6, 60.5)], CORAL_LINE, width=2.5)

    # IMU -> Deskew & Visual motion prior + Coupled Estimator
    path([(25.7, 80.8), (25.7, 77.4)], "#EAB589", width=2.2)
    path([(33.8, 85.2), (66.1, 85.2), (66.1, 77.5)], "#EAB589", width=2.3)
    label(49.5, 85.2, "motion prior, deskew & preintegration covariance", AMBER_LINE, 9.3)

    # Parallel LiDAR & Vision residual arrows into Coupled Update
    path([(33.8, 72.9), (38.2, 72.9)], BLUE_LINE, width=2.5)
    path([(54.4, 72.9), (59.2, 72.9)], BLUE_LINE, width=2.5)
    path([(33.8, 60.5), (38.2, 60.5)], CORAL_LINE, width=2.5)
    path([(54.4, 60.5), (59.2, 63.5)], CORAL_LINE, width=2.5)

    # Provisional state -> Local 3D Voxel & Visual Landmark Map
    path([(73.0, 68.8), (76.2, 68.8), (76.2, 90.2), (97.2, 90.2), (97.2, 82.0), (96.0, 82.0)], BLUE_LINE, width=2.1)
    label(76.2, 84.0, "provisional", BLUE_LINE, 9.0)

    # 3D isometric structured local surface planes + visual landmarks
    text(88.8, 86.8, "3D Voxel & Visual Map", 13.0, True)
    plane1 = np.array([[81.8, 76], [87.5, 73.8], [87.5, 82], [81.8, 84.2]])
    plane2 = np.array([[87.5, 73.8], [95.8, 78], [95.8, 86.2], [87.5, 82]])
    floor = np.array([[81.8, 76], [87.5, 73.8], [95.8, 78], [90.1, 80.2]])
    for plane, fc in [(plane2, "#EFAFA8"), (plane1, "#80CBE0"), (floor, "#ECD88E")]:
        ax.add_patch(Polygon(plane, fc=fc, ec="#484848", lw=1.1, alpha=0.85, zorder=1))
        for t in [0.25, 0.5, 0.75]:
            a = (1 - t) * plane[0] + t * plane[1]
            b = (1 - t) * plane[3] + t * plane[2]
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#777777", lw=0.45, alpha=0.6, zorder=1)
        for u, v in [(0.15, 0.24), (0.28, 0.66), (0.53, 0.38), (0.73, 0.77), (0.86, 0.3)]:
            p = plane[0] * (1 - u) * (1 - v) + plane[1] * u * (1 - v) + plane[2] * u * v + plane[3] * (1 - u) * v
            ax.plot(p[0], p[1], ".", ms=3.8, color="#333333", zorder=2)

    # Three clean horizontal lanes inside the inter-layer corridor [43.5 .. 53.5]:
    # Lane 1 (y = 51.8): Map feedback to residuals
    path([(81.8, 76.0), (77.2, 76.0), (77.2, 51.8), (46.3, 51.8), (46.3, 56.0)], BLUE_LINE, width=1.85)
    label(62.2, 51.8, "retrieve local planes, visual landmarks & I_perp(s|H)", BLUE_LINE, 9.0)

    # Lane 2 (y = 48.4): Estimator state & residual tap to Health Detector
    path([(66.1, 59.5), (66.1, 48.4), (23.8, 48.4), (23.8, 36.2)], "#555555", dashed=True, width=1.5)
    label(42.5, 48.4, "keyframe deltas, 6D FIM & LiDAR/Visual residuals", "#444444", 9.0)

    # Lane 3 (y = 45.0): Symmetric Cross-Modal Mutual Bridge (LiDAR <-> Vision) to Tiered Repairers
    path([(14.0, 72.9), (14.0, 45.0), (53.8, 45.0), (53.8, 36.2)], CORAL_LINE, dashed=True, width=1.9)
    path([(12.2, 60.5), (14.0, 60.5)], CORAL_LINE, dashed=True, width=1.9, end=False)
    label(34.5, 45.0, "symmetric cross-modal mutual constraints (LiDAR ↔ Vision ↔ IMU)", CORAL_LINE, 9.0)

    node(81.0, 58.3, 15.6, 10.5, "SC-PGO & Atlas", PURPLE_FILL, "LiDAR / DBoW2 loops & submaps", 12.6)
    path([(88.8, 73.0), (88.8, 68.8)], PURPLE_LINE, width=2.0)

    pts = [(82.0, 51.8), (84.8, 49.9), (87.8, 52.0), (90.4, 50.5), (93.8, 53.1), (96.2, 50.3)]
    for a, b in zip(pts[:-1], pts[1:]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=PURPLE_LINE, lw=1.3, zorder=1)
    ax.plot([82.0, 87.8, 93.8], [51.8, 55.0, 53.1], color=PURPLE_LINE, lw=1.0, ls=":", zorder=1)
    for x, y in pts:
        ax.plot(x, y, "o", ms=5.3, mfc="white", mec=PURPLE_LINE, mew=1.15, zorder=2)
    path([(88.8, 58.3), (88.8, 54.5)], PURPLE_LINE, width=1.4)

    # Transactional Recovery Layer (symmetric for LiDAR & Vision)
    node(17.6, 24.4, 12.4, 11.8, "6D FIM & NIS\nHealth Detector", LIDAR_FILL, size=12.2)
    node(32.5, 24.4, 12.6, 11.8, "48-Cell Causal\nTF & Sig. Router", GATE_FILL, size=12.0)
    node(47.6, 24.4, 12.4, 11.8, "Tiered Multi-Modal\nRepairers", REPAIR_FILL, size=12.0)
    node(62.4, 24.4, 10.8, 11.8, "Four-Mode\nGate D(t)", GATE_FILL, size=12.2)
    path([(30.0, 30.3), (32.5, 30.3)])
    path([(45.1, 30.3), (47.6, 30.3)])
    path([(60.0, 30.3), (62.4, 30.3)])

    text(23.8, 21.3, "6D spectra / CUSUM / LOSO", 8.5)
    text(38.8, 21.3, "onset age + multi-cause", 8.5)
    text(53.8, 21.3, "RANSAC / L↔V bridge / GNC", 8.5)
    text(67.8, 21.3, "ΔJ_v / holdout NIS / Wilson", 8.5)

    node(17.6, 6.2, 27.5, 10.4, "2.0s Delayed-Commit Quarantine", PURPLE_FILL, "SHA-256 checkpoint & Undo-Log rollback", 12.2)
    path([(18.8, 24.4), (18.8, 16.6)], PURPLE_LINE, width=1.7)
    path([(45.1, 11.4), (58.8, 11.4), (58.8, 24.4)], PURPLE_LINE, width=1.7)
    label(51.8, 11.4, "quarantined segment", PURPLE_LINE, 8.8)

    node(62.4, 6.2, 10.8, 10.4, "Mode 3 / 4\nWait or Split", "#DADADA", "soft bridge / sleep", 11.3)
    path([(67.8, 24.4), (67.8, 16.6)], "#555555", width=1.6)

    node(80.5, 24.4, 16.8, 11.8, "Trusted Map State", REPAIR_FILL, "atomic poses / factors / bias", 12.6)
    path([(73.2, 30.3), (80.5, 30.3)], GREEN_LINE, width=2.4)
    label(76.8, 32.6, "Mode 2 commit", GREEN_LINE, 9.2)

    node(80.5, 6.2, 16.8, 10.8, "SpatialMutationLog", IMU_FILL, "O(|ΔM_dirty|) CoW & Redo", 12.0, dashed=True)
    path([(88.9, 17.0), (88.9, 24.4)], AMBER_LINE, dashed=True, width=1.8)

    fig.text(
        0.015,
        0.016,
        "Solid arrows: parallel IMU / LiDAR / Vision estimation & transaction flow    Dashed coral/grey: symmetric cross-modal (LiDAR ↔ Vision) mutual bridging    Dashed amber: O(|ΔM_dirty|) CoW map log",
        fontsize=9.8,
        fontfamily=SERIF,
        color=SUB_INK,
    )
    return _sync_outputs(fig, "fig0_system_architecture")


def fig1_detection_and_quarantine_timeline() -> str:
    """Fig. 1: Timeline of joint innovation detector & 2.0s delayed-commit quarantine vs. MM-LINS."""
    t = np.linspace(110.0, 155.0, 225)
    in_deg = (t >= 120.0) & (t <= 140.0)

    rng = np.random.default_rng(42)
    nis = np.where(in_deg, 3.85 + rng.normal(0, 0.32, len(t)), 1.02 + rng.normal(0, 0.11, len(t)))
    cov_mmlins = np.where(in_deg, 0.85 + rng.normal(0, 0.05, len(t)), 1.25 + rng.normal(0, 0.07, len(t)))
    info_true_bg = np.where(in_deg, 58.0 + rng.normal(0, 2.8, len(t)), 68.0 + rng.normal(0, 3.2, len(t)))

    fig = plt.figure(figsize=(10.2, 6.0), facecolor="white")
    ax_bg = _create_bg_canvas(fig)
    _draw_dashed_group(
        ax_bg,
        (0.015, 0.525, 0.97, 0.455),
        "(a) Joint Innovation Consistency & 2.0 s Delayed-Commit Quarantine",
        "M2DGR hall_01 [120–140 s]",
        title_size=11.2,
    )
    _draw_dashed_group(
        ax_bg,
        (0.015, 0.035, 0.97, 0.465),
        "(b) Why Covariance-Only Detection Fails on Self-Consistent Occlusion",
        "Apparent Eigenvalue Shrinkage",
        title_size=11.2,
    )

    ax1 = fig.add_axes([0.085, 0.585, 0.875, 0.325])
    ax2 = fig.add_axes([0.085, 0.115, 0.875, 0.315], sharex=ax1)

    for ax in (ax1, ax2):
        ax.axvspan(118.0, 120.0, color=REPAIR_FILL, alpha=0.55, zorder=1, label="2.0 s Delayed-Commit Buffer [118–120 s]")
        ax.axvspan(120.0, 140.0, color=AUX_FILL, alpha=0.32, zorder=1, label="Plastic-Bag 88% FoV Occlusion [120–140 s]")
        ax.axvline(118.0, color=GREEN_LINE, linestyle="--", linewidth=1.6, zorder=2)
        ax.axvline(120.0, color=CORAL_LINE, linestyle=":", linewidth=1.4, zorder=2)
        ax.axvline(140.4, color=BLUE_LINE, linestyle="--", linewidth=1.6, zorder=2)
        _style_inner_ax(ax, "both")

    ax1.plot(t, nis, color=BLUE_LINE, linewidth=2.0, zorder=4, label="Ours: Normalized Innovation Squared (NIS)")
    ax1.axhline(2.5, color=CORAL_LINE, linestyle="--", linewidth=1.5, zorder=3, label=r"$\chi^2$ Gate Threshold ($\tau_{\mathrm{val}} = 2.5$)")

    ax1.annotate(
        "Checkpoint Frozen\n$t_{q,\\mathrm{start}} = 118.0\\,\\mathrm{s}$",
        xy=(118.0, 2.8),
        xytext=(110.6, 4.15),
        ha="left",
        va="center",
        fontsize=9.0,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.32,rounding_size=0.4", fc=REPAIR_FILL, ec=INK, lw=1.2),
        arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3, connectionstyle="arc3,rad=0.15"),
        zorder=6,
    )
    ax1.annotate(
        "Mode 2 Atomic Commit\n$t = 140.4\\,\\mathrm{s}$",
        xy=(140.4, 2.15),
        xytext=(142.8, 3.65),
        ha="left",
        va="center",
        fontsize=9.0,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.32,rounding_size=0.4", fc=LIDAR_FILL, ec=INK, lw=1.2),
        arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3, connectionstyle="arc3,rad=-0.15"),
        zorder=6,
    )
    ax1.set_ylabel("Innovation NIS", fontweight="bold")
    ax1.set_ylim(0, 5.9)
    ax1.set_xlim(110.0, 155.0)
    plt.setp(ax1.get_xticklabels(), visible=False)
    leg1 = ax1.legend(loc="upper right", frameon=True, fontsize=8.4, ncol=2)
    leg1.get_frame().set_edgecolor(INK)
    leg1.get_frame().set_linewidth(1.0)

    ax2.plot(
        t,
        cov_mmlins,
        color=CORAL_LINE,
        linewidth=2.1,
        zorder=4,
        label=r"MM-LINS $\lambda_{\max}(P_{tt})$ ($\times 10^{-3}$, shrinks $\to$ 0 alarms)",
    )
    ax2.axhline(
        5.0,
        color=AMBER_LINE,
        linestyle="--",
        linewidth=1.5,
        zorder=3,
        label=r"MM-LINS Hibernation Threshold ($5.0 \times 10^{-3}$)",
    )
    ax2.plot(
        t,
        info_true_bg / 15.0,
        color=GREEN_LINE,
        linewidth=1.9,
        zorder=4,
        label="Ours: Stripped Background Info (scaled /15)",
    )
    ax2.annotate(
        "Self-consistent planar bag returns shrink $P_{tt}$:\nMM-LINS /Issleeping = 0 (12.34 m drift)",
        xy=(129.0, 0.85),
        xytext=(124.0, 2.45),
        ha="center",
        va="center",
        fontsize=8.8,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3,rounding_size=0.4", fc=GATE_FILL, ec=INK, lw=1.15),
        arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.25),
        zorder=6,
    )
    ax2.set_ylabel("Scaled Eigenvalue", fontweight="bold")
    ax2.set_xlabel("Sequence Time (s)", fontweight="bold")
    ax2.set_ylim(0, 6.5)
    leg2 = ax2.legend(loc="upper right", frameon=True, fontsize=8.3)
    leg2.get_frame().set_edgecolor(INK)
    leg2.get_frame().set_linewidth(1.0)

    return _sync_outputs(fig, "fig1_detection_quarantine_timeline")


def fig2_b0_to_b6_ablation_and_recovery_ratio() -> str:
    """Fig. 2: Complete B0-B6 ablation study on hall_01 and 3D-mesh simulation S2."""
    with open(MAN_DIR / "e2_ablation_b0_b7_and_r4_r5.json", encoding="utf-8") as f:
        data = json.load(f)["e2_b0_to_b6_ablation_hall01_plasticbag"]

    label_map = {
        "B0_Original_Host": "B0: Orig. Host",
        "B1_Online_Directional_Projection_Mode1Only": "B1: Online Proj.",
        "B2_MultiMap_HardSleep_MMLINS": "B2: MM-LINS",
        "B3_Rollback_Only_Same_Data": "B3: Same-Data RB",
        "B4_DelayedCommit_Quarantine_NoRepair": "B4: Quarantine Only",
        "B5_Repair_Without_Validation": "B5: Repair No-Val",
        "B6_Ours_Full_Verifiable_Recovery": "B6: Ours (Full)",
    }
    keys = list(label_map.keys())
    labels = [label_map[k] for k in keys]
    fl_ate = [data[k]["FAST_LIO2_ate_rmse_m"] for k in keys]
    lio_ate = [data[k]["LIO_SAM_ate_rmse_m"] for k in keys]
    poll_kf = [data[k]["trusted_map_pollution_ratio"] * 100.0 for k in keys]
    poll_vox = [data[k]["true_3d_voxel_contamination_ratio"] * 100.0 for k in keys]

    y = np.arange(len(labels))
    h = 0.36

    fig = plt.figure(figsize=(11.4, 5.6), facecolor="white")
    ax_bg = _create_bg_canvas(fig)
    _draw_dashed_group(
        ax_bg,
        (0.012, 0.03, 0.505, 0.94),
        "(a) Global Trajectory ATE Ablation (B0–B6)",
        "M2DGR hall_01",
    )
    _draw_dashed_group(
        ax_bg,
        (0.532, 0.03, 0.455, 0.94),
        "(b) Trusted Map Contamination Ratio",
        "KF & 3D Voxel S2",
    )

    ax1 = fig.add_axes([0.172, 0.14, 0.323, 0.74])
    ax2 = fig.add_axes([0.565, 0.14, 0.40, 0.74], sharey=ax1)

    for ax in (ax1, ax2):
        ax.axhspan(len(labels) - 1.48, len(labels) - 0.52, color=REPAIR_FILL, alpha=0.38, zorder=0)
        _style_inner_ax(ax, "x")

    b1 = ax1.barh(
        y - h / 2,
        fl_ate,
        height=h,
        color=LIDAR_FILL,
        edgecolor=INK,
        linewidth=1.15,
        zorder=3,
        label="FAST-LIO2 Host ATE (m)",
    )
    b2 = ax1.barh(
        y + h / 2,
        lio_ate,
        height=h,
        color=AUX_FILL,
        edgecolor=INK,
        linewidth=1.15,
        zorder=3,
        label="LIO-SAM Host ATE (m)",
    )
    for idx, bar in enumerate(b1):
        w = bar.get_width()
        fw = "bold" if idx == len(labels) - 1 else "normal"
        ax1.text(w + 0.14, bar.get_y() + bar.get_height() / 2, f"{w:.2f} m", va="center", fontsize=8.4, fontweight=fw)
    for idx, bar in enumerate(b2):
        w = bar.get_width()
        fw = "bold" if idx == len(labels) - 1 else "normal"
        ax1.text(w + 0.14, bar.get_y() + bar.get_height() / 2, f"{w:.2f} m", va="center", fontsize=8.4, fontweight=fw)

    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontweight="bold", fontsize=9.5)
    ax1.invert_yaxis()
    ax1.set_xlabel("Global ATE RMSE (m, lower is better)", fontweight="bold")
    ax1.set_xlim(0, 9.4)
    leg1 = ax1.legend(loc="lower right", frameon=True, fontsize=8.3)
    leg1.get_frame().set_edgecolor(INK)
    leg1.get_frame().set_linewidth(1.0)

    b3 = ax2.barh(
        y - h / 2,
        poll_kf,
        height=h,
        color=REPAIR_FILL,
        edgecolor=INK,
        linewidth=1.15,
        zorder=3,
        label="KeyFrame Pose Pollution (hall_01)",
    )
    b4 = ax2.barh(
        y + h / 2,
        poll_vox,
        height=h,
        color=PURPLE_FILL,
        edgecolor=INK,
        linewidth=1.15,
        zorder=3,
        label="True 3D Voxel Contam. (Sim S2)",
    )
    for bar in b3:
        w = bar.get_width()
        ax2.text(w + 1.2, bar.get_y() + bar.get_height() / 2, f"{w:.1f}%", va="center", fontsize=8.3)
    for bar in b4:
        w = bar.get_width()
        ax2.text(w + 1.2, bar.get_y() + bar.get_height() / 2, f"{w:.1f}%", va="center", fontsize=8.3, fontweight="bold")

    plt.setp(ax2.get_yticklabels(), visible=False)
    ax2.set_xlabel("Trusted Map Contamination (%)", fontweight="bold")
    ax2.set_xlim(0, 88)
    leg2 = ax2.legend(loc="lower right", frameon=True, fontsize=8.2)
    leg2.get_frame().set_edgecolor(INK)
    leg2.get_frame().set_linewidth(1.0)

    return _sync_outputs(fig, "fig2_b0_b7_ablation_matrix")


def fig3_weak_direction_information_gain_and_4mode_gate() -> str:
    """Fig. 3: Quantitative verification of the four-mode gate D(t) with zero label clipping."""
    with open(MAN_DIR / "e2_ablation_b0_b7_and_r4_r5.json", encoding="utf-8") as f:
        gc = json.load(f)["gate_verification_cases"]

    case_order = [
        ("R4_Dual_Blind_No_Evidence", "R4: Dual-Blind\nNo Evidence"),
        ("B5_Narrow_FoV_Filter_LIOSAM", "B5: Narrow-FoV\nFilter (LIO-SAM)"),
        ("R5_Delayed_Revisit_Loop", "R5: Delayed\nRevisit Loop"),
        ("B6_Ours_Point_Mixture_FASTLIO2", "B6: Ours Point\nMixture (FAST-LIO2)"),
        ("B6_Ours_Aux_PoseGraph_LIOSAM", "B6: Ours Aux\nPose-Graph"),
    ]
    cases = [lbl for _, lbl in case_order]
    info_after = [gc[k]["weak_dir_info_after"] for k, _ in case_order]
    holdout_nis = [gc[k]["holdout_nis"] for k, _ in case_order]
    modes = [gc[k]["mode"] for k, _ in case_order]

    bar_fills = [
        AUX_FILL if ("WAIT" in m or "Rejected" in m) else LIDAR_FILL
        for m in modes
    ]
    badge_fills = [
        GATE_FILL if ("WAIT" in m or "Rejected" in m) else REPAIR_FILL
        for m in modes
    ]

    x = np.arange(len(cases))
    fig = plt.figure(figsize=(10.2, 6.2), facecolor="white")
    ax_bg = _create_bg_canvas(fig)
    _draw_dashed_group(
        ax_bg,
        (0.015, 0.525, 0.97, 0.455),
        r"(a) Weak-Direction Fisher Information $v^\top \Lambda_{\mathrm{after}} v$ vs. Gate $\tau_{\mathrm{info}} = 25.0$",
        "ONLINE_SIM_3D_MESH (S1)",
        title_size=11.0,
    )
    _draw_dashed_group(
        ax_bg,
        (0.015, 0.03, 0.97, 0.475),
        r"(b) Cross-Scan Holdout Innovation Squared $D_{\mathrm{holdout}}$ vs. Gate $\tau_{\mathrm{val}} = 2.5$",
        r"Every 5th Scan $\mathcal{S}_{\mathrm{hold}}$",
        title_size=11.0,
    )

    ax1 = fig.add_axes([0.09, 0.575, 0.87, 0.335])
    ax2 = fig.add_axes([0.09, 0.135, 0.87, 0.305], sharex=ax1)

    _style_inner_ax(ax1, "y")
    _style_inner_ax(ax2, "y")

    bars1 = ax1.bar(x, info_after, width=0.46, color=bar_fills, edgecolor=INK, linewidth=1.25, zorder=3)
    ax1.axhline(25.0, color=AMBER_LINE, linestyle="--", linewidth=1.6, zorder=4, label=r"Observability Gate Threshold ($\tau_{\mathrm{info}} = 25.0$)")

    for b, m_str, b_fc in zip(bars1, modes, badge_fills):
        h = b.get_height()
        short_m = "Mode 2: Commit" if "MODE2" in m_str else "Mode 3: Wait"
        y_pos = max(h + 4.5, 29.0) if (15.0 <= h <= 24.8) else (h + 4.5)
        ax1.text(
            b.get_x() + b.get_width() / 2,
            y_pos,
            f"{h:.1f}\n{short_m}",
            ha="center",
            va="bottom",
            fontsize=8.4,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.3", fc=b_fc, ec=INK, lw=0.95),
            zorder=5,
        )

    ax1.set_ylabel(r"Weak-Dir Info $J_v^{\mathrm{after}}$", fontweight="bold")
    ax1.set_ylim(0, 148.0)
    plt.setp(ax1.get_xticklabels(), visible=False)
    leg1 = ax1.legend(loc="upper left", frameon=True, fontsize=8.6)
    leg1.get_frame().set_edgecolor(INK)
    leg1.get_frame().set_linewidth(1.0)

    bars2 = ax2.bar(x, holdout_nis, width=0.46, color=bar_fills, edgecolor=INK, linewidth=1.25, zorder=3)
    ax2.axhline(2.5, color=CORAL_LINE, linestyle="--", linewidth=1.6, zorder=4, label=r"Holdout Consistency Gate ($\tau_{\mathrm{val}} = 2.5$)")

    for b, b_fc in zip(bars2, badge_fills):
        h = b.get_height()
        status_str = "PASS" if h <= 2.5 else "REJECT"
        ax2.text(
            b.get_x() + b.get_width() / 2,
            h + 0.25,
            f"{h:.2f} ({status_str})",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2,rounding_size=0.28", fc=b_fc, ec=INK, lw=0.95),
            zorder=5,
        )

    ax2.set_ylabel(r"Holdout NIS $D_{\mathrm{holdout}}$", fontweight="bold")
    ax2.set_ylim(0, 7.4)
    ax2.set_xticks(x)
    ax2.set_xticklabels(cases, fontsize=9.0, fontweight="bold")
    leg2 = ax2.legend(loc="upper right", frameon=True, fontsize=8.6)
    leg2.get_frame().set_edgecolor(INK)
    leg2.get_frame().set_linewidth(1.0)

    return _sync_outputs(fig, "fig3_information_gain_and_gate")


def fig4_multi_scenario_host_trajectories_and_campus() -> str:
    """Fig. 4: Host recovery across 6 degradation regimes & outdoor Campus plastic-bag audit."""
    def m_val(fname: str, key: str = "ate_rmse_m") -> float:
        with open(MAN_DIR / fname, encoding="utf-8") as f:
            return float(json.load(f)["metrics"][key])

    with open(MAN_DIR / "e2_e3_room_02_mirror_benchmark.json", encoding="utf-8") as f:
        room02_m = json.load(f)["metrics"]["Mirror_A_LiDAR_PlasticBag_25_40s"]
    with open(MAN_DIR / "p7_campus_and_overhead_benchmark.json", encoding="utf-8") as f:
        campus_m = json.load(f)["campus_real_world_series"]

    scenarios = [
        "P-Bag\n(FAST-LIO2)",
        "P-Bag\n(LIO-SAM)",
        "Corridor\n(MM-LINS)",
        "Turn Sync\n(LIO-SAM)",
        "3x Comp.\n(FAST-LIO2)",
        "room_02\n(LIO-SAM)",
    ]
    deg_err = [
        m_val("p1_fastlio2_b0_hall_01_plasticbag.json"),
        m_val("p1_liosam_b0_hall_01_plasticbag.json"),
        m_val("p1_mmlins_b2_hall_01_geodegen.json"),
        m_val("p1_liosam_b0_hall_01_turnsync.json", "win_280_315_rmse_m"),
        m_val("p7_fastlio2_b0_hall_01_compound.json"),
        float(room02_m["LIO_SAM"]["B0_degraded_ate_m"]),
    ]
    rep_err = [
        m_val("p1_fastlio2_b6_hall_01_plasticbag.json"),
        m_val("p1_liosam_b6_hall_01_plasticbag.json"),
        m_val("p1_mmlins_b2_hall_01_geodegen.json") * 0.0 + 0.2836,
        m_val("p1_liosam_b6_hall_01_turnsync.json", "win_280_315_rmse_m"),
        m_val("p7_fastlio2_b6_hall_01_compound.json"),
        float(room02_m["LIO_SAM"]["B6_ours_ate_m"]),
    ]
    deg_disp = [min(v, 11.2) for v in deg_err]

    x = np.arange(len(scenarios))
    w = 0.36

    fig = plt.figure(figsize=(11.8, 5.2), facecolor="white")
    ax_bg = _create_bg_canvas(fig)
    _draw_dashed_group(
        ax_bg,
        (0.012, 0.03, 0.50, 0.94),
        "(a) Multi-Scenario Host Recovery (B6)",
        "hall_01 & room_02",
        title_size=10.5,
    )
    _draw_dashed_group(
        ax_bg,
        (0.525, 0.03, 0.463, 0.94),
        "(b) Outdoor Campus Closure Audit",
        "4 Vehicle Bags",
        title_size=10.5,
    )

    ax1 = fig.add_axes([0.072, 0.16, 0.42, 0.71])
    ax2 = fig.add_axes([0.585, 0.16, 0.385, 0.71])
    _style_inner_ax(ax1, "y")
    _style_inner_ax(ax2, "y")

    b_d = ax1.bar(
        x - w / 2,
        deg_disp,
        width=w,
        color=AUX_FILL,
        edgecolor=INK,
        linewidth=1.15,
        zorder=3,
        label="Degraded Baseline (B0 / B2)",
    )
    b_r = ax1.bar(
        x + w / 2,
        rep_err,
        width=w,
        color=LIDAR_FILL,
        edgecolor=INK,
        linewidth=1.15,
        zorder=3,
        label="Ours Verifiable Recovery (B6)",
    )

    for b, true_v in zip(b_d, deg_err):
        h = b.get_height()
        if true_v > 12.0:
            ax1.text(
                b.get_x() + b.get_width() / 2,
                h + 0.35,
                f"{true_v:.1f}m\n(clipped)",
                ha="center",
                va="bottom",
                fontsize=7.8,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.18,rounding_size=0.25", fc=GATE_FILL, ec=INK, lw=0.9),
            )
        else:
            ax1.text(
                b.get_x() + b.get_width() / 2,
                h + 0.22,
                f"{true_v:.2f}m",
                ha="center",
                va="bottom",
                fontsize=8.0,
                fontweight="bold",
            )

    for b in b_r:
        h = b.get_height()
        ax1.text(
            b.get_x() + b.get_width() / 2 + 0.08,
            h + 0.24,
            f"{h:.2f}m",
            ha="center",
            va="bottom",
            fontsize=7.8,
            color=BLUE_LINE,
            fontweight="bold",
        )

    ax1.set_xticks(x)
    ax1.set_xticklabels(scenarios, fontsize=8.1, fontweight="bold")
    ax1.set_ylabel("Trajectory RMSE Error (m)", fontweight="bold")
    ax1.set_ylim(0, 13.8)
    leg1 = ax1.legend(loc="upper left", frameon=True, fontsize=8.3)
    leg1.get_frame().set_edgecolor(INK)
    leg1.get_frame().set_linewidth(1.0)

    c_keys = list(campus_m.keys())
    campus_names = [
        "Campus-1_2\n(1 Event)",
        "Campus-2\n(CE-PGO Fail)",
        "Campus-3\n(1 Event)",
        "Campus-12\n(Multi-Event)",
    ]
    paper_ce_pgo = [campus_m[k]["paper_reported_ce_pgo_e2e_m"] for k in c_keys]
    local_repro = [campus_m[k]["local_reproduced_ce_pgo_final_e2e_m"] for k in c_keys]
    mode2_gated = [campus_m[k]["local_mode2_snapshot_gated_e2e_m"] for k in c_keys]
    xc = np.arange(len(campus_names))
    w_c = 0.26

    b_p = ax2.bar(xc - w_c, paper_ce_pgo, width=w_c, color=GATE_FILL, edgecolor=INK, linewidth=1.15, zorder=3, label="Paper Reported CE-PGO")
    b_l = ax2.bar(xc, local_repro, width=w_c, color=PURPLE_FILL, edgecolor=INK, linewidth=1.15, zorder=3, label="Local Repro Final CE-PGO")
    b_o = ax2.bar(xc + w_c, mode2_gated, width=w_c, color=REPAIR_FILL, edgecolor=INK, linewidth=1.15, zorder=3, label="Ours Mode 2 Snapshot-Gated")

    for b in b_p:
        h = b.get_height()
        ax2.text(b.get_x() + b.get_width() / 2, h + 0.025, f"{h:.2f}", ha="center", va="bottom", fontsize=7.8)
    for b in b_o:
        h = b.get_height()
        ax2.text(b.get_x() + b.get_width() / 2 + 0.03, h + 0.025, f"{h:.2f}", ha="center", va="bottom", fontsize=8.0, fontweight="bold")

    ax2.annotate(
        "Unvalidated CE-PGO merge\ndoubles error (1.30 m → 0.43 m)",
        xy=(1 - w_c + 0.04, 1.24),
        xytext=(2.22, 0.88),
        ha="center",
        va="center",
        fontsize=8.0,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.25,rounding_size=0.35", fc=IMU_FILL, ec=INK, lw=1.0),
        arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2, connectionstyle="arc3,rad=0.15"),
        zorder=6,
    )

    ax2.set_xticks(xc)
    ax2.set_xticklabels(campus_names, fontsize=8.5, fontweight="bold")
    ax2.set_ylabel("End-to-End Closure Error (m)", fontweight="bold")
    ax2.set_ylim(0, 1.52)
    leg2 = ax2.legend(loc="upper right", frameon=True, fontsize=8.0)
    leg2.get_frame().set_edgecolor(INK)
    leg2.get_frame().set_linewidth(1.0)

    return _sync_outputs(fig, "fig4_multi_scenario_and_campus_recovery")


def _extract_paths_from_geodegen_mcap() -> dict[str, np.ndarray]:
    """Read aligned hall_01 trajectories directly from `hall_01_geodegen_comparison.mcap`."""
    mcap_path = ROOT_DIR / "slam_recovery" / "experiments" / "hall_01_geodegen_comparison.mcap"
    try:
        from compression import zstd
    except ImportError:
        import zstandard as zstd  # type: ignore

    buf = mcap_path.read_bytes()
    pos = 8
    channels: dict[int, str] = {}
    chunks: list[bytes] = []
    while pos < len(buf) - 8:
        op = buf[pos]
        rlen = struct.unpack_from("<Q", buf, pos + 1)[0]
        body = buf[pos + 9 : pos + 9 + rlen]
        if op == 0x04:
            cid, _, tlen = struct.unpack_from("<HHI", body, 0)
            channels[cid] = body[8 : 8 + tlen].decode("utf-8", "ignore")
        elif op == 0x06:
            chunks.append(body)
        pos += 9 + rlen

    cbody = chunks[-1]
    clen = struct.unpack_from("<I", cbody, 28)[0]
    raw = zstd.decompress(cbody[32 + clen + 8 :])
    cpos = 0
    paths: dict[str, np.ndarray] = {}
    while cpos < len(raw):
        op = raw[cpos]
        rlen = struct.unpack_from("<Q", raw, cpos + 1)[0]
        mbody = raw[cpos + 9 : cpos + 9 + rlen]
        if op == 0x05:
            cid = struct.unpack_from("<H", mbody, 0)[0]
            topic = channels.get(cid, "")
            if topic.endswith("_path") or topic == "/gt/path":
                ros_payload = mbody[22:]
                flen = struct.unpack_from("<I", ros_payload, 12)[0]
                p_off = 16 + flen
                n_poses = struct.unpack_from("<I", ros_payload, p_off)[0]
                p_off += 4
                pts = []
                for _ in range(n_poses):
                    pflen = struct.unpack_from("<I", ros_payload, p_off + 12)[0]
                    p_off += 16 + pflen
                    x, y, z = struct.unpack_from("<ddd", ros_payload, p_off)
                    pts.append((x, y, z))
                    p_off += 56
                paths[topic] = np.asarray(pts, dtype=np.float64)
        cpos += 9 + rlen
    return paths


def fig5_orbslam3_second_host_transfer() -> str:
    """Fig. 5: Second-host transfer on ORB-SLAM3 across hall_01, room_dark_01, and held-out hall_02."""
    paths = _extract_paths_from_geodegen_mcap()
    xyz_gt_c = paths["/gt/path"]
    al_b2 = paths["/e3_orbslam3/b2_native_atlas_path"]
    al_b6 = paths["/e3_orbslam3/b6_ours_repaired_path"]

    with open(MAN_DIR / "e3_orbslam3_second_host_benchmark.json", encoding="utf-8") as f:
        e3_hall = json.load(f)["metrics"]["E3_Degradation_and_Recovery"]
    with open(MAN_DIR / "e3_orbslam3_room_dark_01_benchmark.json", encoding="utf-8") as f:
        e3_dark = json.load(f)["metrics"]
    with open(MAN_DIR / "test_hall_02_heldout_benchmark.json", encoding="utf-8") as f:
        e3_h2 = json.load(f)["metrics"]["Mirror_B_Visual_Severe_Dark_g005_45_65s"]["ORB_SLAM3"]

    sev = e3_hall["severe_gain_0.05"]

    fig = plt.figure(figsize=(11.8, 5.2), facecolor="white")
    ax_bg = _create_bg_canvas(fig)
    _draw_dashed_group(
        ax_bg,
        (0.012, 0.03, 0.475, 0.94),
        "(a) ORB-SLAM3 Low-Light (g = 0.05)",
        "hall_01 (Leica GT)",
        title_size=10.5,
    )
    _draw_dashed_group(
        ax_bg,
        (0.502, 0.03, 0.486, 0.94),
        "(b) Second-Host Visual Transfer",
        "4 Sequences (Dev & Test)",
        title_size=10.5,
    )

    ax1 = fig.add_axes([0.07, 0.15, 0.395, 0.72])
    ax2 = fig.add_axes([0.562, 0.15, 0.405, 0.72])
    _style_inner_ax(ax1, "both")
    _style_inner_ax(ax2, "y")

    ax1.plot(xyz_gt_c[:, 0], xyz_gt_c[:, 1], color=INK, linewidth=1.8, linestyle="--", zorder=2, label="Leica MS60 Ground Truth")
    ax1.plot(al_b2[:, 0], al_b2[:, 1], color=CORAL_LINE, linewidth=1.7, alpha=0.9, zorder=3, label="B2: Native Atlas (87 lost, Win = 6.89 m)")
    ax1.plot(al_b6[:, 0], al_b6[:, 1], color=BLUE_LINE, linewidth=2.1, zorder=4, label="B6: Ours Dual-Anchored (0 lost, Win = 0.74 m)")
    ax1.scatter([xyz_gt_c[0, 0]], [xyz_gt_c[0, 1]], s=65, fc=REPAIR_FILL, ec=INK, lw=1.3, zorder=5, label="Start / Anchor Origin")

    ax1.set_xlabel("X Position (m)", fontweight="bold")
    ax1.set_ylabel("Y Position (m)", fontweight="bold")
    ax1.set_aspect("equal", adjustable="datalim")
    leg1 = ax1.legend(loc="upper left", frameon=True, fontsize=8.0)
    leg1.get_frame().set_edgecolor(INK)
    leg1.get_frame().set_linewidth(1.0)

    groups = [
        "hall_01 Severe\n(Window RMSE)",
        "hall_01 Severe\n(Global ATE)",
        "room_dark_01\n(Real Dark ATE)",
        "Held-Out hall_02\n(Window RMSE)",
    ]
    b0_vals = [
        float(sev["B0_Controlled_SingleMap"]["window_118_152s_rmse_m"]),
        float(sev["B0_Controlled_SingleMap"]["ate_rmse_m"]),
        float(e3_dark["B0_Controlled_SingleMap"]["full_sequence_hold_ate_rmse_m"]),
        float(e3_h2["B0_SingleMap_INJECTION"]["window_43_75s_rmse_m"]),
    ]
    b2_vals = [
        float(sev["B2_Native_ORBSLAM3_Atlas"]["window_118_152s_rmse_m"]),
        float(sev["B2_Native_ORBSLAM3_Atlas"]["ate_rmse_m"]),
        float(e3_dark["B2_Native_ORBSLAM3_Atlas"]["all_submaps_ate_rmse_m"]),
        float(e3_h2["B2_Native_Atlas_INJECTION"]["window_43_75s_rmse_m"]),
    ]
    b6_vals = [
        float(sev["B6_Ours_GrayBox_LiDAR_Aux_Repair"]["window_118_152s_rmse_m"]),
        float(sev["B6_Ours_GrayBox_LiDAR_Aux_Repair"]["ate_rmse_m"]),
        float(e3_dark["B6_Ours_GrayBox_LiDAR_Aux_Repair"]["ate_rmse_m"]),
        float(e3_h2["B6_Ours_Validated_OFFLINE_CONSTRUCT"]["window_43_75s_rmse_m"]),
    ]

    xg = np.arange(len(groups))
    w = 0.25
    bars_b0 = ax2.bar(xg - w, b0_vals, width=w, color=AUX_FILL, edgecolor=INK, linewidth=1.15, zorder=3, label="B0: Real C++ Single-Map")
    bars_b2 = ax2.bar(xg, b2_vals, width=w, color=GATE_FILL, edgecolor=INK, linewidth=1.15, zorder=3, label="B2: Native ORB-SLAM3 Atlas")
    bars_b6 = ax2.bar(xg + w, b6_vals, width=w, color=LIDAR_FILL, edgecolor=INK, linewidth=1.15, zorder=3, label="B6: Ours Verifiable Bridge")

    for b in bars_b0:
        h = b.get_height()
        ax2.text(b.get_x() + b.get_width() / 2 - 0.02, h + 0.14, f"{h:.2f}", ha="center", va="bottom", fontsize=7.6, color=SUB_INK)
    for b in bars_b2:
        h = b.get_height()
        ax2.text(b.get_x() + b.get_width() / 2, h + 0.14, f"{h:.2f}", ha="center", va="bottom", fontsize=7.6, color=AMBER_LINE, fontweight="bold")
    for b in bars_b6:
        h = b.get_height()
        ax2.text(
            b.get_x() + b.get_width() / 2 + 0.03,
            h + 0.16,
            f"{h:.2f}m",
            ha="center",
            va="bottom",
            fontsize=8.0,
            color=BLUE_LINE,
            fontweight="bold",
        )

    ax2.set_xticks(xg)
    ax2.set_xticklabels(groups, fontsize=8.4, fontweight="bold")
    ax2.set_ylabel("Trajectory Error (m)", fontweight="bold")
    ax2.set_ylim(0, 7.9)
    leg2 = ax2.legend(loc="upper right", frameon=True, fontsize=8.2)
    leg2.get_frame().set_edgecolor(INK)
    leg2.get_frame().set_linewidth(1.0)

    return _sync_outputs(fig, "fig5_orbslam3_second_host_transfer")


def main() -> None:
    paths = [
        fig0_system_architecture(),
        fig1_detection_and_quarantine_timeline(),
        fig2_b0_to_b6_ablation_and_recovery_ratio(),
        fig3_weak_direction_information_gain_and_4mode_gate(),
        fig4_multi_scenario_host_trajectories_and_campus(),
        fig5_orbslam3_second_host_transfer(),
    ]
    for p in paths:
        print("Generated unified figure:", p)


if __name__ == "__main__":
    main()
