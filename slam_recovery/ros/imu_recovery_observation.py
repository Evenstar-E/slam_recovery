"""Read checkpoint-based IMU predictions from the host's private observation stream."""

import json
from pathlib import Path
from typing import Optional

import numpy as np

from slam_recovery.ros.live_health import score_local_planes


class ImuRecoveryObservations:
    """Read up to the requested original scan stamp, without using any later observation."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0

    def at_scan(self, scan_ns: int) -> Optional[dict]:
        try:
            with self.path.open("rb") as source:
                source.seek(self.offset)
                for line in source:
                    if not line.endswith(b"\n"):
                        return None
                    row = json.loads(line)
                    if row["scan_ns"] > scan_ns + 1024:
                        return None
                    self.offset += len(line)
                    if row["scan_ns"] >= scan_ns - 1024:
                        return row
        except (OSError, ValueError, TypeError, KeyError):
            return None
        return None


def score_imu_observation(row: dict, index, sigma: float, min_holdout: int,
                          boundary_ns: int, max_position_sigma_m: float) -> dict:
    evidence = {
        "checkpoint_ns": int(row["checkpoint_ns"]),
        "position_sigma_m": float(row["position_sigma_m"]),
    }
    points = np.asarray(row["points"], dtype=np.float64)
    if not len(points) or points.ndim != 2 or points.shape[1] != 9 or not np.isfinite(points).all():
        return {**evidence, "status": "INVALID_POINTS"}
    names = ("fused_raw", "imu_raw", "imu_deskewed")
    for i, name in enumerate(names):
        value, count, supported = score_local_planes(index, points[:, i*3:i*3+3], sigma, min_holdout)
        evidence[name] = {"nis": value, "queries": count, "supported": supported}
    if not 0 < evidence["checkpoint_ns"] <= boundary_ns:
        status = "INVALID_CHECKPOINT"
    elif not 0 <= evidence["position_sigma_m"] <= max_position_sigma_m:
        status = "PREDICTION_UNCERTAINTY"
    elif evidence["imu_deskewed"]["nis"] is None:
        status = "NO_OLD_MAP_SUPPORT"
    else:
        status = "AVAILABLE"
    return {**evidence, "status": status}
