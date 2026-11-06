#!/usr/bin/env python
"""Build a point-cloud MCAP that actually shows injection, stripping and the survivors.

The existing `hall_01_plasticbag_comparison.mcap` carries two PointCloud2 topics that are
the *same* scan bytes written with `stride=6` and `stride=2` from two bags whose
`/velodyne_points` payloads are byte-identical (verified by sha256), so it cannot be used to
judge what the near-field mixture filter removes. This script generates a replacement from a
real M2DGR scan:

  /points/clean       the real scan straight out of the bag
  /points/injected    the same scan after inject_plastic_bag_near_field_occlusion()
  /points/removed     exactly the points the mixture filter marked as contaminant
  /points/background  the points that survive the filter

Everything is deterministic (fixed injection seed), and the strip fraction actually achieved
is written to the manifest next to the frames rather than asserted.

Usage (ROS1 python, because rosbag is needed):
  /home/R26534/mm/ros/bin/python -m slam_recovery.experiments.build_pointcloud_injection_mcap
"""

from __future__ import annotations

import json
import os
from typing import List, Tuple

import numpy as np

import rosbag
from mcap_ros1.writer import Writer as Ros1McapWriter
from sensor_msgs.msg import PointCloud2

from ..experiments.injection.injectors import inject_plastic_bag_near_field_occlusion
from ..repair.point_mixture_repairer import (
    MixtureFilterConfig,
    filter_self_consistent_near_field_contaminants,
)

OUT_MCAP = "/home/R26534/MM-LINS/slam_recovery/experiments/hall01_pointcloud_injection_comparison.mcap"
OUT_JSON = "/home/R26534/MM-LINS/slam_recovery/experiments/manifests/hall01_pointcloud_injection_comparison.json"

# Real M2DGR scan source: the room_02 bag carries genuine indoor returns and is small enough
# to read repeatedly. The frames are taken from the first 60 s, outside any injected window.
SRC_BAG = "/home/R26534/M2DGR/raw/room_02.bag"
SRC_TOPIC = "/velodyne_points"

OCCLUDED_AZIMUTH_FRACTION = 0.88
BAG_DISTANCE_M = 0.35
INJECTION_SEED = 42
NUM_FRAMES = 12
FRAME_STRIDE = 6  # decimation applied to every emitted cloud, identically


def read_xyz_i(msg) -> np.ndarray:
    names = [f.name for f in msg.fields]
    dtype = np.dtype(
        {
            "names": names,
            "formats": ["<f4"] * len(names),
            "offsets": [f.offset for f in msg.fields],
            "itemsize": msg.point_step,
        }
    )
    arr = np.frombuffer(bytes(msg.data), dtype=dtype)
    return np.column_stack([arr["x"], arr["y"], arr["z"], arr["intensity"]]).astype(np.float64)


def make_pc2(points_xyzi: np.ndarray, frame_id: str = "lidar") -> PointCloud2:
    pts = np.ascontiguousarray(points_xyzi, dtype=np.float32)
    m = PointCloud2()
    m.header.frame_id = frame_id
    m.height = 1
    m.width = int(pts.shape[0])
    m.fields = [_field("x", 0), _field("y", 4), _field("z", 8), _field("intensity", 12)]
    m.is_bigendian = False
    m.point_step = 16
    m.row_step = m.point_step * m.width
    m.is_dense = True
    m.data = pts.tobytes()
    return m


def _field(name: str, offset: int):
    from sensor_msgs.msg import PointField

    f = PointField()
    f.name = name
    f.offset = offset
    f.datatype = PointField.FLOAT32
    f.count = 1
    return f


def collect_frames(bag_path: str, topic: str, n_frames: int) -> List[Tuple[float, np.ndarray]]:
    out: List[Tuple[float, np.ndarray]] = []
    t_first = None
    with rosbag.Bag(bag_path, "r") as bag:
        for idx, (_, msg, _) in enumerate(bag.read_messages(topics=[topic])):
            t = msg.header.stamp.to_sec()
            if t_first is None:
                t_first = t
            if t - t_first > 90.0:  # keep the window short so the build stays fast
                break
            if idx % 10:  # 1 Hz out of a 10 Hz stream
                continue
            out.append((t, read_xyz_i(msg)))
            if len(out) >= n_frames:
                break
    return out


def main() -> None:
    frames = collect_frames(SRC_BAG, SRC_TOPIC, NUM_FRAMES)
    if not frames:
        raise RuntimeError(f"no frames read from {SRC_BAG}")

    cfg = MixtureFilterConfig()
    per_frame = []
    os.makedirs(os.path.dirname(OUT_MCAP), exist_ok=True)
    with open(OUT_MCAP, "wb") as fh:
        writer = Ros1McapWriter(output=fh)
        for (t_sec, clean) in frames:
            injected, bag_mask = inject_plastic_bag_near_field_occlusion(
                clean,
                occluded_azimuth_fraction=OCCLUDED_AZIMUTH_FRACTION,
                bag_distance_m=BAG_DISTANCE_M,
                seed=INJECTION_SEED,
            )
            keep, contam_ratio, min_eig, repairable = filter_self_consistent_near_field_contaminants(
                injected, cfg
            )
            removed = injected[~keep]
            background = injected[keep]

            t_ns = int(t_sec * 1e9)
            for topic, pts in (
                ("/points/clean", clean),
                ("/points/injected", injected),
                ("/points/removed", removed),
                ("/points/background", background),
            ):
                sub = pts[::FRAME_STRIDE]
                if len(sub) == 0:
                    continue
                writer.write_message(
                    topic, make_pc2(sub), log_time=t_ns, publish_time=t_ns
                )

            per_frame.append(
                {
                    "t_sec": round(float(t_sec), 3),
                    "clean_points": int(len(clean)),
                    "injected_points": int(len(injected)),
                    "injected_bag_points": int(bag_mask.sum()),
                    "removed_points": int((~keep).sum()),
                    "background_points": int(keep.sum()),
                    "strip_fraction": round(float(np.mean(~keep)), 4),
                    "contam_ratio": round(float(contam_ratio), 4),
                    "min_bg_eigenvalue": round(float(min_eig), 4),
                    "geometrically_repairable": bool(repairable),
                    "bag_points_surviving": int((keep & bag_mask).sum()),
                    "background_points_stripped": int((~keep & ~bag_mask).sum()),
                }
            )
        writer.finish()

    summary = {
        "run_id": "hall01_pointcloud_injection_comparison",
        "purpose": (
            "Replace hall_01_plasticbag_comparison.mcap's point-cloud topics, which were the same "
            "scan bytes written at two decimations and therefore could not show what the filter removes."
        ),
        "source_bag": SRC_BAG,
        "source_topic": SRC_TOPIC,
        "provenance": {
            "/points/clean": "REAL_HOST (M2DGR room_02 raw /velodyne_points)",
            "/points/injected": "INJECTION (inject_plastic_bag_near_field_occlusion, deterministic seed)",
            "/points/removed": "OFFLINE_CONSTRUCT (mixture filter rejection mask applied to the injected cloud)",
            "/points/background": "OFFLINE_CONSTRUCT (mixture filter survivor mask)",
        },
        "injection_params": {
            "occluded_azimuth_fraction": OCCLUDED_AZIMUTH_FRACTION,
            "bag_distance_m": BAG_DISTANCE_M,
            "seed": INJECTION_SEED,
        },
        "filter_config": {
            "near_field_max_range_m": cfg.near_field_max_range_m,
            "plane_inlier_dist_m": cfg.plane_inlier_dist_m,
            "min_occluder_fraction": cfg.min_occluder_fraction,
            "min_remaining_bg_points": cfg.min_remaining_bg_points,
            "min_weak_dir_eigenvalue": cfg.min_weak_dir_eigenvalue,
        },
        "emitted_decimation_stride": FRAME_STRIDE,
        "num_frames": len(per_frame),
        "mean_strip_fraction": round(float(np.mean([f["strip_fraction"] for f in per_frame])), 4),
        "frames": per_frame,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"wrote {OUT_MCAP} ({os.path.getsize(OUT_MCAP) / 1e6:.1f} MB), {len(per_frame)} frames")
    print(f"mean strip fraction {summary['mean_strip_fraction']:.4f}")
    print("first frame:", per_frame[0])


if __name__ == "__main__":
    main()
