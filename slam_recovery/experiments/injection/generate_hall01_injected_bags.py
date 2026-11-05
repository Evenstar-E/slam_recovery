"""Generate deterministic P1 fault-injected bags from M2DGR/extracted/hall_01_fl.bag."""

from __future__ import annotations

import os
import sys
import numpy as np
import rosbag
from sensor_msgs.msg import PointCloud2

sys.path.insert(0, "/home/R26534/MM-LINS")
from slam_recovery.experiments.injection import (
    LiDARInjectionParams,
    inject_lidar_attenuation_and_dropout,
    inject_plastic_bag_near_field_occlusion,
)

SRC_BAG = "/home/R26534/M2DGR/extracted/hall_01_fl.bag"
OUT_DIR = "/home/R26534/M2DGR/injected"
os.makedirs(OUT_DIR, exist_ok=True)

BAG_DROPOUT = os.path.join(OUT_DIR, "hall_01_inj_dropout_120_140s.bag")
BAG_PLASTIC = os.path.join(OUT_DIR, "hall_01_inj_plasticbag_120_140s.bag")


def unpack_24b(msg: PointCloud2) -> np.ndarray:
    return np.frombuffer(bytes(msg.data), dtype=np.uint8).reshape(-1, 24).copy()


def pack_24b(template_msg: PointCloud2, raw_24: np.ndarray) -> PointCloud2:
    m = PointCloud2()
    m.header = template_msg.header
    m.height = 1
    m.width = int(raw_24.shape[0])
    m.fields = template_msg.fields
    m.is_bigendian = False
    m.point_step = 24
    m.row_step = 24 * m.width
    m.data = raw_24.tobytes()
    m.is_dense = True
    return m


def main() -> None:
    t0 = None
    n_injected = 0
    with (
        rosbag.Bag(SRC_BAG, "r") as b_in,
        rosbag.Bag(BAG_DROPOUT, "w") as b_drop,
        rosbag.Bag(BAG_PLASTIC, "w") as b_bag,
    ):
        for topic, msg, t in b_in.read_messages():
            ts = msg.header.stamp.to_sec() if hasattr(msg, "header") else t.to_sec()
            if t0 is None:
                t0 = ts
            rel_t = ts - t0

            if topic == "/imu_raw":
                b_drop.write("/imu_raw", msg, t)
                b_drop.write("/handsfree/imu", msg, t)
                b_bag.write("/imu_raw", msg, t)
                b_bag.write("/handsfree/imu", msg, t)
                continue

            if topic == "/velodyne_points":
                if 120.0 <= rel_t <= 140.0:
                    n_injected += 1
                    raw = unpack_24b(msg)
                    xyzi = raw[:, 0:16].view(np.float32).reshape(-1, 4).copy()
                    frame_seed = 42000 + n_injected

                    # 1. Severe dropout + extinction + range noise (95% drop + 0.12m noise)
                    params = LiDARInjectionParams(
                        alpha_extinct=0.05,
                        sigma_range_m=0.12,
                        target_drop_ratio=0.95,
                        seed=frame_seed,
                    )
                    deg_xyzi, kept_mask = inject_lidar_attenuation_and_dropout(xyzi, params)
                    raw_drop = raw[kept_mask].copy()
                    raw_drop[:, 0:16] = deg_xyzi.astype(np.float32).view(np.uint8).reshape(-1, 16)
                    b_drop.write("/velodyne_points", pack_24b(msg, raw_drop), t)

                    # 2. Floating plastic bag / near-field self-consistent occlusion
                    # Placed at 4.3m (> FAST-LIO blind=4.0m and LIO-SAM minRange=1.0m) so both hosts ingest the false plane
                    bag_xyzi, _ = inject_plastic_bag_near_field_occlusion(
                        xyzi,
                        occluded_azimuth_fraction=0.88,
                        bag_distance_m=4.30,
                        bag_Thickness_jitter_m=0.01,
                        seed=frame_seed,
                    )
                    raw_bag = raw.copy()
                    raw_bag[:, 0:16] = bag_xyzi.astype(np.float32).view(np.uint8).reshape(-1, 16)
                    b_bag.write("/velodyne_points", pack_24b(msg, raw_bag), t)
                else:
                    b_drop.write("/velodyne_points", msg, t)
                    b_bag.write("/velodyne_points", msg, t)

    print(f"Done! Injected {n_injected} LiDAR frames in [120s, 140s].")
    print(" ->", BAG_DROPOUT)
    print(" ->", BAG_PLASTIC)


if __name__ == "__main__":
    main()
