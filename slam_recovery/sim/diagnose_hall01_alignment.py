"""Diagnostic render comparing wall-band reconstruction quality of `hall_01` under
three attitude sources, all translated by the same Leica GT positions:

  (a) trajectory-tangent yaw (the first export approach -> smeared walls)
  (b) calibrated IMU yaw (`sign=+1`, theta0 from hall01_imu_yaw_calibration.json)
  (c) calibrated IMU yaw coloured by time, to reveal drift rather than structure

Also sweeps a small IMU-vs-LiDAR time offset to check whether residual smear is a
synchronisation artefact. Outputs `hall_01_alignment_diagnosis.png` + a JSON summary.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slam_recovery.sim.calibrate_hall01_imu_yaw import (  # noqa: E402
    CELL_M,
    OUT_DIR,
    WALL_Z_HI,
    WALL_Z_LO,
    load_cached,
    occupancy_count,
)
from slam_recovery.sim.export_hall01_to_isaacsim import (  # noqa: E402
    MCAP_PBAG,
    compute_headings_from_path,
    extract_mcap_paths,
)


def project(scans, imu_ts, imu_yaw, gt_ts, gt_xyz, mode: str, theta0: float, dt: float = 0.0):
    pts_xy, times = [], []
    tangent_yaw = compute_headings_from_path(gt_ts, gt_xyz)
    for t_scan, pts in scans:
        band = pts[(pts[:, 2] > WALL_Z_LO) & (pts[:, 2] < WALL_Z_HI)][::2, :2]
        if len(band) == 0:
            continue
        i_gt = int(np.argmin(np.abs(gt_ts - t_scan)))
        if mode == "tangent":
            yaw = float(tangent_yaw[i_gt])
        else:
            i_imu = int(np.argmin(np.abs(imu_ts - (t_scan + dt))))
            yaw = float(imu_yaw[i_imu]) + theta0
        c, s = np.cos(yaw), np.sin(yaw)
        R2 = np.array([[c, -s], [s, c]])
        pts_xy.append(band @ R2.T + gt_xyz[i_gt, :2])
        times.append(np.full(len(band), t_scan - gt_ts[0]))
    return np.vstack(pts_xy), np.concatenate(times)


def main() -> None:
    paths = extract_mcap_paths(MCAP_PBAG)
    gt_ts, gt_xyz = paths["/gt/path"]
    scans, imu_ts, imu_yaw = load_cached()

    calib = json.loads((OUT_DIR / "hall01_imu_yaw_calibration.json").read_text(encoding="utf-8"))
    theta0 = np.deg2rad(float(calib["best"]["theta0_deg"]))
    print(f"using theta0 = {calib['best']['theta0_deg']} deg")

    xy_tan, _ = project(scans, imu_ts, imu_yaw, gt_ts, gt_xyz, "tangent", theta0)
    xy_imu, t_imu = project(scans, imu_ts, imu_yaw, gt_ts, gt_xyz, "imu", theta0)

    # time-offset sweep on the IMU path
    sweep = {}
    for dt in np.arange(-0.20, 0.201, 0.05):
        xy, _ = project(scans, imu_ts, imu_yaw, gt_ts, gt_xyz, "imu", theta0, dt=float(dt))
        sweep[f"{dt:+.2f}"] = occupancy_count(xy)
    best_dt = min(sweep, key=sweep.get)
    print("time-offset sweep (occupied cells):", sweep, "-> best", best_dt)

    occ_tan = occupancy_count(xy_tan)
    occ_imu = occupancy_count(xy_imu)
    print(f"occupied 25cm cells: tangent={occ_tan}  imu={occ_imu}  "
          f"improvement={100.0 * (occ_tan - occ_imu) / max(occ_tan, 1):.1f}%")

    plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 10})
    fig, axes = plt.subplots(1, 3, figsize=(17.0, 5.6), facecolor="#F4F5F7")

    for ax, xy, title, color in [
        (axes[0], xy_tan, "(a) Trajectory-tangent yaw (previous export) — smeared", "#D64535"),
        (axes[1], xy_imu, f"(b) IMU yaw + θ₀={np.rad2deg(theta0):.1f}° (calibrated)", "#0088B2"),
    ]:
        ax.set_facecolor("#FFFFFF")
        ax.scatter(xy[:, 0], xy[:, 1], s=0.6, c=color, alpha=0.45, linewidths=0)
        ax.set_title(title, fontsize=10.5, fontweight="bold")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.set_xlabel("World X (m)")
    axes[0].set_ylabel("World Y (m)")

    ax = axes[2]
    ax.set_facecolor("#FFFFFF")
    sc = ax.scatter(xy_imu[:, 0], xy_imu[:, 1], s=0.8, c=t_imu, cmap="viridis", alpha=0.6, linewidths=0)
    ax.set_title("(c) Calibrated IMU yaw, coloured by time", fontsize=10.5, fontweight="bold")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_xlabel("World X (m)")
    fig.colorbar(sc, ax=ax, label="t (s)")

    fig.suptitle(
        "hall_01 wall-band reconstruction: attitude source diagnosis "
        f"(occupied {CELL_M*100:.0f} cm cells: tangent {occ_tan} → IMU {occ_imu})",
        fontsize=13.0, fontweight="bold", color="#171717", y=0.99,
    )
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.94])
    out_png = OUT_DIR / "hall_01_alignment_diagnosis.png"
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    summary = {
        "theta0_deg": calib["best"]["theta0_deg"],
        "sign": calib["best"]["sign"],
        "occupied_cells_tangent": occ_tan,
        "occupied_cells_imu": occ_imu,
        "relative_improvement_pct": round(100.0 * (occ_tan - occ_imu) / max(occ_tan, 1), 2),
        "time_offset_sweep_s": sweep,
        "best_time_offset_s": float(best_dt),
        "figure": str(out_png),
    }
    (OUT_DIR / "hall01_alignment_diagnosis.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote {out_png}")


if __name__ == "__main__":
    main()
