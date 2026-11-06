"""Calibrate the constant yaw offset between M2DGR `hall_01.bag` IMU orientation (`/handsfree/imu`)
and the Leica MS60 world frame used by `hall_01_plasticbag_comparison.mcap`.

Why this is needed
------------------
`hall_01` is a hand-held M2DGR sequence: the operator walks forward, stops, spins in place and
sometimes walks backwards. Using the trajectory *tangent* (`atan2(dy, dx)`) as the body yaw is
therefore wrong whenever the sensor spins or reverses, which smears the reconstructed walls.

The IMU AHRS quaternion in `/handsfree/imu` does carry the true body yaw up to one constant offset
theta_0 (plus a possible sign convention). We recover theta_0 by maximising wall sharpness:
for the correct theta_0, the wall-band LiDAR returns from different scans collapse onto the
same thin vertical surfaces, minimising the number of occupied 25 cm XY cells.

Run: python slam_recovery/sim/calibrate_hall01_imu_yaw.py
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from slam_recovery.sim.export_hall01_to_isaacsim import (  # noqa: E402
    BAG_PATH,
    MCAP_PBAG,
    _parse_rosbag_header,
    extract_mcap_paths,
    extract_scans_and_imu_from_bag,
)

OUT_DIR = Path(r"D:\REPAIR\isaac_sim_hall_01")
CACHE = OUT_DIR / "hall01_imu_yaw_cache.npz"
CELL_M = 0.25
WALL_Z_LO, WALL_Z_HI = 0.15, 1.50
POINT_STRIDE = 2


def extract_imu_series(bag_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Extract (timestamp, yaw) for every `/handsfree/imu` message (conn=2) via direct chunk seek."""
    ts_out: list[float] = []
    yaw_out: list[float] = []
    with open(bag_path, "rb") as f:
        f.readline()
        hlen = struct.unpack("<I", f.read(4))[0]
        bhdr = _parse_rosbag_header(f.read(hlen))
        index_pos = struct.unpack("<Q", bhdr["index_pos"])[0]
        conn_count = struct.unpack("<I", bhdr["conn_count"])[0]
        chunk_count = struct.unpack("<I", bhdr["chunk_count"])[0]

        f.seek(index_pos)
        for _ in range(conn_count):
            l1 = struct.unpack("<I", f.read(4))[0]
            f.seek(l1, 1)
            l2 = struct.unpack("<I", f.read(4))[0]
            f.seek(l2, 1)

        imu_chunk_offsets: list[int] = []
        for _ in range(chunk_count):
            hlen = struct.unpack("<I", f.read(4))[0]
            hdr = _parse_rosbag_header(f.read(hlen))
            dlen = struct.unpack("<I", f.read(4))[0]
            data = f.read(dlen)
            cpos = struct.unpack("<Q", hdr["chunk_pos"])[0]
            for off in range(0, len(data), 8):
                cid, cnt = struct.unpack_from("<II", data, off)
                if cid == 2 and cnt > 0:
                    imu_chunk_offsets.append(cpos)

        # IMU runs at 150 Hz; every 5th chunk is >20 Hz, ample for yaw interpolation.
        for cpos in imu_chunk_offsets[::5]:
            f.seek(cpos)
            chlen = struct.unpack("<I", f.read(4))[0]
            f.seek(chlen, 1)
            cdlen = struct.unpack("<I", f.read(4))[0]
            cdata = f.read(cdlen)
            coff = 0
            while coff < len(cdata):
                mhlen = struct.unpack_from("<I", cdata, coff)[0]
                mhdr = _parse_rosbag_header(cdata[coff + 4 : coff + 4 + mhlen])
                mdlen = struct.unpack_from("<I", cdata, coff + 4 + mhlen)[0]
                mbody = cdata[coff + 8 + mhlen : coff + 8 + mhlen + mdlen]
                coff += 8 + mhlen + mdlen
                if mhdr.get("op") != b"\x02":
                    continue
                if struct.unpack("<I", mhdr["conn"])[0] != 2:
                    continue
                sec, nsec = struct.unpack("<II", mhdr["time"])
                flen = struct.unpack_from("<I", mbody, 12)[0]
                qx, qy, qz, qw = struct.unpack_from("<dddd", mbody, 16 + flen)
                yaw = float(np.arctan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz)))
                ts_out.append(sec + nsec * 1e-9)
                yaw_out.append(yaw)

    order = np.argsort(ts_out)
    return np.asarray(ts_out, dtype=np.float64)[order], np.asarray(yaw_out, dtype=np.float64)[order]


def load_cached() -> tuple[list, np.ndarray, np.ndarray]:
    if CACHE.exists():
        d = np.load(CACHE, allow_pickle=True)
        scans = [(float(t), p) for t, p in zip(d["scan_ts"], d["scan_pts"])]
        print(f"[cache] loaded {len(scans)} scans / {len(d['imu_ts'])} imu samples")
        return scans, d["imu_ts"], d["imu_yaw"]

    print("[bag] extracting scans from hall_01.bag ...")
    scans, _, _ = extract_scans_and_imu_from_bag(BAG_PATH, scan_stride=35)
    print(f"[bag] {len(scans)} VLP-32C keyframes")

    print("[bag] extracting /handsfree/imu yaw series ...")
    imu_ts, imu_yaw = extract_imu_series(BAG_PATH)
    print(f"[bag] {len(imu_ts)} imu orientation samples")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        CACHE,
        scan_ts=np.asarray([t for t, _ in scans], dtype=np.float64),
        scan_pts=np.asarray([p for _, p in scans], dtype=object),
        imu_ts=imu_ts,
        imu_yaw=imu_yaw,
    )
    return scans, imu_ts, imu_yaw


def wall_points_world(
    scans: list,
    imu_ts: np.ndarray,
    imu_yaw: np.ndarray,
    gt_ts: np.ndarray,
    gt_xyz: np.ndarray,
    sign: float,
    theta0: float,
) -> np.ndarray:
    """Register wall-band LiDAR returns into the Leica world frame for a given (sign, theta0)."""
    chunks = []
    for t_scan, pts in scans:
        band = pts[(pts[:, 2] > WALL_Z_LO) & (pts[:, 2] < WALL_Z_HI)][::POINT_STRIDE, :2]
        if len(band) == 0:
            continue
        i_imu = int(np.argmin(np.abs(imu_ts - t_scan)))
        i_gt = int(np.argmin(np.abs(gt_ts - t_scan)))
        yaw = sign * float(imu_yaw[i_imu]) + theta0
        c, s = np.cos(yaw), np.sin(yaw)
        R2 = np.array([[c, -s], [s, c]], dtype=np.float64)
        chunks.append(band @ R2.T + gt_xyz[i_gt, :2])
    return np.vstack(chunks) if chunks else np.zeros((0, 2))


def occupancy_count(xy: np.ndarray) -> int:
    if len(xy) == 0:
        return 1 << 30
    cells = np.floor(xy / CELL_M).astype(np.int64)
    return int(len(np.unique(cells, axis=0)))


def main() -> None:
    paths = extract_mcap_paths(MCAP_PBAG)
    gt_ts, gt_xyz = paths["/gt/path"]
    scans, imu_ts, imu_yaw = load_cached()

    results = {}
    for sign in (1.0, -1.0):
        best_theta, best_occ = 0.0, 1 << 30
        for theta_deg in np.arange(-180.0, 180.0, 1.0):
            theta = np.deg2rad(theta_deg)
            xy = wall_points_world(scans, imu_ts, imu_yaw, gt_ts, gt_xyz, sign, theta)
            occ = occupancy_count(xy)
            if occ < best_occ:
                best_occ, best_theta = occ, theta
        # refine around the coarse optimum
        for theta_deg in np.arange(np.rad2deg(best_theta) - 2.0, np.rad2deg(best_theta) + 2.0, 0.1):
            theta = np.deg2rad(theta_deg)
            xy = wall_points_world(scans, imu_ts, imu_yaw, gt_ts, gt_xyz, sign, theta)
            occ = occupancy_count(xy)
            if occ < best_occ:
                best_occ, best_theta = occ, theta
        results[f"sign_{int(sign)}"] = {
            "theta0_deg": round(float(np.rad2deg(best_theta)), 2),
            "occupied_25cm_cells": best_occ,
        }
        print(f"sign={sign:+.0f}  theta0={np.rad2deg(best_theta):8.2f} deg  cells={best_occ}")

    best_key = min(results, key=lambda k: results[k]["occupied_25cm_cells"])
    summary = {
        "cell_m": CELL_M,
        "wall_band_z": [WALL_Z_LO, WALL_Z_HI],
        "num_scans": len(scans),
        "num_imu_samples": int(len(imu_ts)),
        "candidates": results,
        "best": {"sign": 1.0 if best_key.endswith("1") else -1.0, **results[best_key]},
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "hall01_imu_yaw_calibration.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary["best"], indent=2))
    print(f"saved -> {OUT_DIR / 'hall01_imu_yaw_calibration.json'}")


if __name__ == "__main__":
    main()
