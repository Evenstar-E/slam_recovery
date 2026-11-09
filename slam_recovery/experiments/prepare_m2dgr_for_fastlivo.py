#!/usr/bin/env python
"""Prepare an M2DGR bag for FAST-LIVO2.

FAST-LIVO2's Velodyne handler (lidar_type: 2) expects a 24-byte point layout
  x, y, z, intensity (float32), time (float32, seconds from scan start), ring (uint16)
whereas M2DGR ships 22-byte records with ring at 16 and a signed time at 18, and its images are
JPEG-compressed. This rewrites a window of a raw M2DGR bag into

  /velodyne_points              24-byte layout, per-point time >= 0
  /handsfree/imu                passed through unchanged
  /camera/color/image_raw       decoded sensor_msgs/Image (bgr8)

and optionally re-applies the project's plastic-bag near-field occlusion to the LiDAR stream
over a sub-window, leaving the image stream untouched (a LiDAR-only injection).

Usage (ROS1 python):
  /home/R26534/mm/ros/bin/python -m slam_recovery.experiments.prepare_m2dgr_for_fastlivo \
      --bag /home/R26534/M2DGR/raw/room_02.bag --out /tmp/fastlivo/room_02_60s.bag \
      --start-rel 0 --duration 60
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import sys

import numpy as np
import rosbag
from sensor_msgs.msg import Image, PointCloud2, PointField

from ..experiments.injection.injectors import (
    inject_plastic_bag_near_field_occlusion,
    inject_visual_exposure_drop,
    inject_visual_motion_blur,
)

IMG_IN = "/camera/color/image_raw/compressed"
IMG_OUT = "/camera/color/image_raw"
CLOUD = "/velodyne_points"
IMU = "/handsfree/imu"


def decode_jpeg(data: bytes) -> np.ndarray:
    try:
        import cv2

        arr = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if arr is None:
            raise RuntimeError("cv2.imdecode returned None")
        return arr
    except Exception:
        from PIL import Image as PILImage

        with PILImage.open(io.BytesIO(data)) as im:
            return np.asarray(im.convert("RGB"))[:, :, ::-1].copy()


def convert_cloud(msg: PointCloud2, inject: bool, occlusion: float, bag_distance_m: float) -> PointCloud2:
    # PointField.datatype: 4 = UINT16 (ring), 7 = FLOAT32. Reading every field as float32 turns
    # the uint16 ring into NaN, so the dtype has to follow the message.
    _np_for = {1: "i1", 2: "u1", 3: "<i2", 4: "<u2", 5: "<i4", 6: "<u4", 7: "<f4", 8: "<f8"}
    names = [f.name for f in msg.fields]
    src_dtype = np.dtype(
        {"names": names, "formats": [_np_for[f.datatype] for f in msg.fields],
         "offsets": [f.offset for f in msg.fields], "itemsize": msg.point_step}
    )
    raw = np.frombuffer(bytes(msg.data), dtype=src_dtype)
    time_s = raw["time"].astype(np.float64)
    # M2DGR per-point time is a signed offset; FAST-LIVO2 wants seconds from scan start.
    time_s = time_s - float(np.min(time_s))
    ring = raw["ring"].astype(np.uint16)
    pts = np.column_stack([raw["x"], raw["y"], raw["z"], raw["intensity"]]).astype(np.float64)
    if inject:
        pts, _ = inject_plastic_bag_near_field_occlusion(
            np.column_stack([pts, np.zeros(len(pts))]),
            occluded_azimuth_fraction=occlusion,
            bag_distance_m=bag_distance_m,
            seed=42,
        )
        pts = pts[:, :4]

    out = PointCloud2()
    out.header = msg.header
    out.height = 1
    out.width = int(len(pts))
    out.fields = [
        _pf("x", 0), _pf("y", 4), _pf("z", 8), _pf("intensity", 12), _pf("time", 16), _pf("ring", 20)
    ]
    out.is_bigendian = False
    out.point_step = 24
    out.row_step = out.point_step * out.width
    out.is_dense = True

    rec = np.zeros(len(pts), dtype=np.dtype({"names": ["x", "y", "z", "i", "t", "r"],
                                             "formats": ["<f4"] * 5 + ["<u2"],
                                             "offsets": [0, 4, 8, 12, 16, 20], "itemsize": 24}))
    rec["x"], rec["y"], rec["z"] = pts[:, 0], pts[:, 1], pts[:, 2]
    rec["i"] = pts[:, 3]
    rec["t"] = time_s.astype(np.float32)
    rec["r"] = ring
    out.data = rec.tobytes()
    return out


def _pf(name: str, offset: int) -> PointField:
    f = PointField()
    f.name = name
    f.offset = offset
    f.datatype = PointField.FLOAT32 if name != "ring" else PointField.UINT16
    f.count = 1
    return f


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start-rel", type=float, default=0.0)
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--inject-start-rel", type=float, default=None)
    ap.add_argument("--inject-end-rel", type=float, default=None)
    ap.add_argument("--occlusion", type=float, default=0.88)
    ap.add_argument("--bag-distance", type=float, default=4.30,
                    help="occluder distance from the sensor; the repository's other uses of this "
                         "injector pass 4.30 m, where the sheet reads as an ordinary wall")
    ap.add_argument("--visual-gain", type=float, default=None,
                    help="low-light gain applied to the image stream inside the visual window")
    ap.add_argument("--visual-blur", type=int, default=None,
                    help="directional motion-blur kernel length applied inside the visual window")
    ap.add_argument("--visual-seed", type=int, default=42)
    ap.add_argument("--visual-start-rel", type=float, default=None)
    ap.add_argument("--visual-end-rel", type=float, default=None)
    ap.add_argument("--max-frames", type=int, default=100000)
    args = ap.parse_args()

    wants_visual = args.visual_gain is not None or args.visual_blur is not None
    if wants_visual:
        if args.visual_start_rel is None or args.visual_end_rel is None:
            raise SystemExit(
                "--visual-gain/--visual-blur need both --visual-start-rel and --visual-end-rel; "
                "without them the conversion would silently emit clean images."
            )
        if args.visual_end_rel <= args.visual_start_rel:
            raise SystemExit("--visual-end-rel must be greater than --visual-start-rel")
        if args.visual_end_rel < 0 or args.visual_start_rel > args.duration:
            raise SystemExit("the visual window does not overlap the conversion window")
        if args.visual_blur is not None:
            try:
                import cv2  # noqa: F401
            except Exception as exc:
                raise SystemExit(f"--visual-blur needs OpenCV for the blur kernel: {exc}")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    src = rosbag.Bag(args.bag, "r")
    t0 = None
    for _, msg, _ in src.read_messages(topics=[IMU]):
        t0 = msg.header.stamp.to_sec()
        break
    if t0 is None:
        raise RuntimeError("no IMU message to anchor the window")
    lo = t0 + args.start_rel
    hi = lo + args.duration

    counts = {CLOUD: 0, IMU: 0, IMG_OUT: 0}
    injected = 0
    visually_degraded = 0
    n_visual = 0
    with rosbag.Bag(args.out, "w") as dst:
        for topic, msg, t in src.read_messages(topics=[IMU, CLOUD, IMG_IN]):
            ts = msg.header.stamp.to_sec()
            if ts < lo:
                continue
            if ts > hi:
                break
            if topic == IMU:
                dst.write(IMU, msg, t)
            elif topic == CLOUD:
                inject = (
                    args.inject_start_rel is not None
                    and args.inject_end_rel is not None
                    and args.inject_start_rel <= (ts - lo) <= args.inject_end_rel
                )
                injected += int(inject)
                dst.write(CLOUD, convert_cloud(msg, inject, args.occlusion, args.bag_distance), t)
            else:
                arr = decode_jpeg(bytes(msg.data))
                visual_window = (
                    args.visual_start_rel is not None
                    and args.visual_end_rel is not None
                    and args.visual_start_rel <= (ts - lo) <= args.visual_end_rel
                )
                if visual_window and (args.visual_gain is not None or args.visual_blur is not None):
                    visibly = arr
                    if args.visual_gain is not None:
                        # Per-frame seed: a fixed seed would replay the identical shot/read noise
                        # field on every frame, which is a static pattern, not sensor noise.
                        visibly = inject_visual_exposure_drop(
                            visibly, gain_g=args.visual_gain, seed=args.visual_seed + n_visual
                        )
                    if args.visual_blur is not None:
                        visibly = inject_visual_motion_blur(visibly, kernel_len=args.visual_blur, angle_deg=25.0)
                    arr = visibly
                    visually_degraded += 1
                n_visual += 1
                im = Image()
                im.header = msg.header
                im.height, im.width = int(arr.shape[0]), int(arr.shape[1])
                im.encoding = "bgr8"
                im.is_bigendian = 0
                im.step = int(arr.shape[1] * 3)
                im.data = np.ascontiguousarray(arr, dtype=np.uint8).tobytes()
                dst.write(IMG_OUT, im, t)
            counts[topic if topic != IMG_IN else IMG_OUT] += 1
            if counts[CLOUD] >= args.max_frames:
                break
    src.close()

    print(f"wrote {args.out} ({os.path.getsize(args.out) / 1e6:.1f} MB)")
    print(f"  window [{lo:.2f}, {hi:.2f}] s  ({args.duration:.0f} s)")
    import json as _json
    import subprocess

    def _sha256(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as src:
            for chunk in iter(lambda: src.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    try:
        git_commit = subprocess.run(
            ["git", "-C", os.path.dirname(os.path.abspath(__file__)), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except Exception:
        git_commit = None

    with open(os.path.splitext(args.out)[0] + ".conversion.json", "w", encoding="utf-8") as fh:
        _json.dump({
            "source_bag": args.bag,
            # A conversion record that names only the path cannot be replayed: the bag may be
            # replaced, the script may change. Hash both sides and record the code revision.
            "source_bag_bytes": os.path.getsize(args.bag),
            "source_bag_mtime_ns": os.stat(args.bag).st_mtime_ns,
            "source_bag_sha256": _sha256(args.bag),
            "output_bag": args.out,
            "output_bag_bytes": os.path.getsize(args.out),
            "output_bag_sha256": _sha256(args.out),
            "argv": sys.argv,
            "git_commit": git_commit,
            "window_start_sec": lo, "window_end_sec": hi,
            "clouds": counts[CLOUD], "lidar_injected": injected, "imu": counts[IMU],
            "images": counts[IMG_OUT], "visually_degraded": visually_degraded,
            "lidar_injection": {"window_rel": [args.inject_start_rel, args.inject_end_rel],
                                "occluded_azimuth_fraction": args.occlusion,
                                "bag_distance_m": args.bag_distance},
            "visual_degradation": {"window_rel": [args.visual_start_rel, args.visual_end_rel],
                                   "gain": args.visual_gain, "blur_kernel": args.visual_blur,
                                   "seed_base": args.visual_seed, "per_frame_seed": True},
        }, fh, indent=2)
    print(f"  clouds={counts[CLOUD]} (lidar-injected {injected})  imu={counts[IMU]}  "
          f"images={counts[IMG_OUT]} (visually degraded {visually_degraded})")


if __name__ == "__main__":
    main()
