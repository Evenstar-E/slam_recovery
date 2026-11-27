"""EuRoC physical frame identity and native worker transport."""
import contextlib
import csv
import json
import os
import select
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


class InputFault(ValueError):
    def __init__(self, kind, detail):
        self.kind = kind
        super().__init__(detail)


@dataclass(frozen=True)
class Pair:
    timestamp: int
    left: Path
    right: Path
    imu: tuple


def euroc(root: Path):
    def rows(path):
        with path.open(newline="") as stream:
            return list(csv.reader(line for line in stream if not line.startswith("#")))

    cameras = [root / "mav0" / name for name in ("cam0", "cam1")]
    image_rows = [rows(camera / "data.csv") for camera in cameras]
    stamps = [[int(row[0]) for row in side] for side in image_rows]
    if (not stamps[0] or stamps[0] != stamps[1]
            or any(a >= b for a, b in zip(stamps[0], stamps[0][1:]))):
        raise InputFault("image_timing", "stereo timestamps must pair exactly and increase")
    imu = []
    for row in rows(root / "mav0/imu0/data.csv"):
        try:
            gx, gy, gz, ax, ay, az = map(float, row[1:])
            values = (ax, ay, az, gx, gy, gz)
            stamp = int(row[0])
        except (ValueError, IndexError) as error:
            raise InputFault("imu", "invalid IMU row") from error
        if not np.isfinite(values).all() or (imu and stamp <= imu[-1][0]):
            raise InputFault("imu", f"invalid IMU sample at {stamp}")
        imu.append((stamp, *values))

    if not imu or imu[0][0] > stamps[0][0]:
        raise InputFault("imu", "IMU does not cover the start of the stereo stream")
    index = 0
    previous = stamps[0][0]
    for i, stamp in enumerate(stamps[0]):
        start = index
        while index < len(imu) and imu[index][0] <= stamp:
            index += 1
        interval = imu[start:index]
        if i:
            if not interval:
                raise InputFault("imu", f"empty IMU interval ending at {stamp}")
            times = (previous, *(row[0] for row in interval), stamp)
            if max(b - a for a, b in zip(times, times[1:])) > 15_000_000:
                raise InputFault("imu", f"IMU gap >15 ms in interval ending at {stamp}")
        paths = tuple(camera / "data" / image_rows[j][i][1]
                      for j, camera in enumerate(cameras))
        yield Pair(stamp, *paths, tuple(interval) if i else ())
        previous = stamp


def read_pair(pair, view, payload=None):
    if payload is None:
        images = tuple(cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                       for path in (pair.left, pair.right))
    else:
        images = tuple(cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_GRAYSCALE)
                       for image in payload)
    if any(image is None for image in images) or images[0].shape != images[1].shape:
        raise InputFault("image_observation", f"unreadable stereo pair {pair.timestamp}")
    if view == "occluded":
        return tuple(np.zeros_like(image) for image in images)
    if view == "fit":
        for image in images:
            image[:image.shape[0] // 3] = 0
    return images


class Worker:
    def __init__(self, command, log_path, wait_ready=False, feature_protocol=False):
        self.feature_protocol = feature_protocol
        self.last_features = b""
        self.feature_stats = dict(captures=0, replay_requests=0, hit_cameras=0, bytes=0)
        env = os.environ.copy()
        if wait_ready:
            env["ORB_VIO_REPORT_READY"] = "1"
        if feature_protocol:
            env["ORB_VIO_FEATURE_PROTOCOL"] = "1"
        read_end, write_end = os.pipe()
        try:
            with log_path.open("xb") as log:
                self.process = subprocess.Popen(
                    [*map(str, command), str(write_end)], stdin=subprocess.PIPE,
                    stdout=log, stderr=log, pass_fds=(write_end,),
                    env=env,
                )
        except BaseException:
            os.close(read_end)
            raise
        finally:
            os.close(write_end)
        self.responses = os.fdopen(read_end, "rb", buffering=0)
        if wait_ready:
            if not select.select([self.responses], [], [], 60)[0] or self.responses.readline() != b"READY\n":
                self.close()
                raise RuntimeError("native worker did not report readiness")

    def track(self, pair, images, imu, capture=False, features=b""):
        height, width = images[0].shape
        header = struct.pack("<qIII", pair.timestamp, width, height, len(imu))
        payload = b"".join(struct.pack("<q6f", *sample) for sample in imu)
        if self.feature_protocol:
            header += struct.pack("<i", -1 if capture else len(features))
            payload += features
        self.process.stdin.write(header + images[0].tobytes() + images[1].tobytes() + payload)
        self.process.stdin.flush()
        if not select.select([self.responses], [], [], 60)[0]:
            raise TimeoutError(f"native worker timed out on {pair.timestamp}")
        line = self.responses.readline()
        if not line:
            raise RuntimeError(f"native worker stopped on {pair.timestamp} (exit {self.process.poll()})")
        values = line.split()
        if len(values) not in (18, 38) or int(values[0]) != pair.timestamp:
            raise RuntimeError(f"native worker response mismatch on {pair.timestamp}")
        if self.feature_protocol:
            framing = self.responses.readline().split()
            if len(framing) != 2 or not all(field.isdigit() for field in framing):
                raise RuntimeError("invalid ORB feature reply framing")
            hits, size = map(int, framing)
            if not 0 <= hits <= 2 or not 0 <= size <= 512 * 1024:
                raise RuntimeError("invalid ORB feature reply")
            data = bytearray(size)
            remaining = memoryview(data)
            while remaining:
                received = self.responses.readinto(remaining)
                if not received:
                    raise RuntimeError("truncated ORB feature reply")
                remaining = remaining[received:]
            self.last_features = bytes(data)
            self.feature_stats["captures"] += bool(data)
            self.feature_stats["bytes"] += len(data)
            self.feature_stats["replay_requests"] += bool(features)
            self.feature_stats["hit_cameras"] += hits
        fields = np.array([float(value) for value in values[2:9]])
        if not np.isfinite(fields).all():
            raise RuntimeError(f"non-finite native pose on {pair.timestamp}")
        return {
            "timestamp": pair.timestamp, "tracking": int(values[1]),
            "pose_cw": fields.tolist(),
            "imu_initialized": bool(int(values[9])), "map_id": int(values[10]),
            "keyframes": int(values[11]), "maps": int(values[12]),
            "keyframe_queue": int(values[13]),
            "inliers": int(values[14]), "occupied_cells": int(values[15]),
            "reprojection_px": None if values[16] == b"-1" else float(values[16]),
            "inertial": list(map(float, values[18:])) if int(values[17]) else None,
        }

    def close(self):
        with contextlib.suppress(BrokenPipeError):
            self.process.stdin.close()
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        finally:
            self.responses.close()
        return self.process.returncode


class EventLog:
    def __init__(self, stream):
        self.stream = stream

    def emit(self, kind, **data):
        print(json.dumps(dict(type=kind, **data), allow_nan=False),
              file=self.stream, flush=True)
