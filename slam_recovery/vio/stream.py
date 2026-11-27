"""EuRoC physical frame identity and native worker transport."""
import contextlib
import csv
import json
import os
import select
import struct
import subprocess
from threading import Lock
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


FEATURE_CAPACITY = 512 * 1024


class SharedFeatures:
    """Anonymous Linux ring for passing exact feature packets between child workers."""

    def __init__(self, slots=16):
        self.generation = 0
        self.slots = slots
        self.fd = os.memfd_create("vio-orb-features", os.MFD_CLOEXEC)
        try:
            os.ftruncate(self.fd, slots * (16 + FEATURE_CAPACITY))
        except OSError:
            os.close(self.fd)
            raise

    def next_generation(self):
        self.generation += 1
        return self.generation

    def close(self):
        os.close(self.fd)


class Worker:
    def __init__(self, command, log_path, wait_ready=False, feature_protocol=False,
                 shared_features=None, restore=None, vocabulary_cache=None, boundary_protocol=False):
        self.feature_protocol = feature_protocol
        self.boundary_protocol = boundary_protocol
        wait_ready = wait_ready or boundary_protocol
        self.last_features = b""
        self.shared_features = shared_features
        self.feature_stats = dict(captures=0, replay_requests=0, hit_cameras=0, bytes=0, pipe_bytes=0)
        env = os.environ.copy()
        if boundary_protocol:
            env["ORB_VIO_BOUNDARY_PROTOCOL"] = "1"
        else:
            env.pop("ORB_VIO_BOUNDARY_PROTOCOL", None)
        if wait_ready or restore is not None:
            env["ORB_VIO_REPORT_READY"] = "1"
        if restore is not None:
            env["ORB_VIO_RESTORE_PREFIX"] = str(restore)
            if vocabulary_cache is not None:
                env["ORB_VIO_VOCABULARY_CACHE"] = str(vocabulary_cache)
        if feature_protocol:
            env["ORB_VIO_FEATURE_PROTOCOL"] = "1"
        read_end, write_end = os.pipe()
        inherited = (write_end,)
        if shared_features is not None:
            env["ORB_VIO_FEATURE_FD"] = str(shared_features.fd)
            env["ORB_VIO_FEATURE_SLOTS"] = str(shared_features.slots)
            inherited += (shared_features.fd,)
        try:
            with log_path.open("xb") as log:
                self.process = subprocess.Popen(
                    [*map(str, command), str(write_end)], stdin=subprocess.PIPE,
                    stdout=log, stderr=log, pass_fds=inherited,
                    env=env,
                )
        except BaseException:
            os.close(read_end)
            raise
        finally:
            os.close(write_end)
        self.responses = os.fdopen(read_end, "rb", buffering=0)
        if wait_ready or restore is not None:
            expected = b"READY BOUNDARY_V1\n" if boundary_protocol else b"READY\n"
            if not select.select([self.responses], [], [], 60)[0] or self.responses.readline() != expected:
                self.close()
                raise RuntimeError("native worker did not report readiness")

    def save_checkpoint(self, prefix):
        path = os.fsencode(prefix)
        self.process.stdin.write(struct.pack("<qI", -(1 << 63), len(path)) + path)
        self.process.stdin.flush()
        if not select.select([self.responses], [], [], 60)[0]:
            raise TimeoutError("native checkpoint reply timed out")
        response = self.responses.readline()
        if response not in (b"SAVED\n", b"BUSY\n"):
            raise RuntimeError("native worker failed to save a checkpoint")
        return response == b"SAVED\n"

    def synchronize(self, timestamp):
        if not self.boundary_protocol:
            raise RuntimeError("native worker has no boundary protocol")
        self.process.stdin.write(struct.pack("<q", -(1 << 63) + 2))
        self.process.stdin.flush()
        if not select.select([self.responses], [], [], 2)[0]:
            raise TimeoutError("native boundary reply timed out")
        line = self.responses.readline()
        if line == b"BOUNDARY_BUSY\n":
            return None
        return self._snapshot(line.split(), timestamp)

    def track(self, pair, images, imu, capture=False, features=b"", async_mapping=False):
        height, width = images[0].shape
        header = struct.pack("<qIII", pair.timestamp, width, height, len(imu))
        if async_mapping:
            if not self.boundary_protocol:
                raise RuntimeError("native worker has no asynchronous mapping protocol")
            header = struct.pack("<q", -(1 << 63) + 1) + header
        payload = b"".join(struct.pack("<q6f", *sample) for sample in imu)
        shared_request = self.shared_features is not None and (capture or isinstance(features, int))
        generation = None
        if shared_request:
            generation = self.shared_features.next_generation() if capture else features
            header += struct.pack("<iQ", -2 if capture else -3, generation)
        elif self.feature_protocol:
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
        snapshot = self._snapshot(values, pair.timestamp)
        if self.feature_protocol:
            framing = self.responses.readline().split()
            if len(framing) != 2 or not all(field.isdigit() for field in framing):
                raise RuntimeError("invalid ORB feature reply framing")
            hits, size = map(int, framing)
            if not 0 <= hits <= 2 or not 0 <= size <= FEATURE_CAPACITY:
                raise RuntimeError("invalid ORB feature reply")
            if shared_request:
                self.last_features = generation if capture and size else b""
            else:
                data = bytearray(size)
                remaining = memoryview(data)
                while remaining:
                    received = self.responses.readinto(remaining)
                    if not received:
                        raise RuntimeError("truncated ORB feature reply")
                    remaining = remaining[received:]
                self.last_features = bytes(data)
                self.feature_stats["pipe_bytes"] += size
            self.feature_stats["captures"] += bool(size)
            self.feature_stats["bytes"] += size
            self.feature_stats["replay_requests"] += bool(features)
            self.feature_stats["hit_cameras"] += hits
        return snapshot

    @staticmethod
    def _snapshot(values, timestamp):
        if (len(values) not in (18, 38) or int(values[0]) != timestamp
                or bool(int(values[17])) != (len(values) == 38)):
            raise RuntimeError(f"native worker response mismatch on {timestamp}")
        fields = np.array([float(value) for value in values[2:9]])
        if not np.isfinite(fields).all():
            raise RuntimeError(f"non-finite native pose on {timestamp}")
        return {
            "timestamp": timestamp, "tracking": int(values[1]),
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
        self.lock = Lock()

    def emit(self, kind, **data):
        row = json.dumps(dict(type=kind, **data), allow_nan=False)
        with self.lock:
            print(row, file=self.stream, flush=True)
