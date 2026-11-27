"""Native adapter transport. Host replies are tied to physical stereo timestamps."""

from collections import deque
import os
import select
import subprocess
import time

import numpy as np

from ..blind_history import world_camera
from ..vision import in_public_world, rotation


class NativeLane:
    def __init__(self, executable, settings, resource, name, output, calibration,
                 *, cpus=(), blocking_callback=False):
        self.recent = deque(maxlen=16)
        self.gauge = None
        self.calibration = calibration
        self.timing = None
        self.awaiting = deque()
        self.resolved = 0
        self.callback_gaps = 0
        self.late_callbacks = 0
        read, write = os.pipe()
        self.reply = os.fdopen(read, "rb", buffering=0)
        self.buffer = bytearray()
        env = os.environ.copy()
        if blocking_callback:
            env["VIO_BLOCKING_CALLBACK"] = "1"
        command = [str(executable), str(settings), str(resource), str(write), name]
        if cpus:
            command[:0] = ["taskset", "-c", cpus]
        try:
            with (output / f"{name}.log").open("xb") as log:
                self.process = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                    pass_fds=(write,), env=env)
        except BaseException:
            self.reply.close()
            raise
        finally:
            os.close(write)
        try:
            greeting = self.readline(15)
            if greeting not in (b"ready", b"ready callback"):
                raise RuntimeError(f"{name} has an invalid startup reply")
            self.pipelined = greeting == b"ready callback"
        except BaseException:
            self.close()
            raise

    def readline(self, seconds):
        deadline = time.monotonic() + seconds
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.reply], [], [], remaining)[0]:
                raise TimeoutError(f"waiting for native worker {self.process.pid}")
            data = self.reply.read(4096)
            if not data:
                raise RuntimeError(f"native worker {self.process.pid} closed its state stream")
            self.buffer.extend(data)
        line, _, remainder = self.buffer.partition(b"\n")
        self.buffer = remainder
        return bytes(line)

    def write_request(self, stamp, images, imu):
        height, width = images[0].shape if images is not None else (0, 0)
        header = f"{stamp} {len(imu)} {height} {width}\n"
        payload = "".join(" ".join(map(str, row)) + "\n" for row in imu)
        packet = (header + payload).encode()
        send = time.monotonic_ns()
        self.process.stdin.write(packet)
        if images is not None:
            for image in images:
                self.process.stdin.write(memoryview(np.ascontiguousarray(image)))
        self.process.stdin.flush()
        return send

    def decode(self, record, expected):
        stamp = int(record[0])
        if stamp != expected:
            raise RuntimeError(f"native worker returned {stamp} for {expected}")
        if record[1] == b"0" and len(record) == 2:
            self.recent.clear()
            return None
        if record[1] != b"1" or len(record) != 18:
            raise RuntimeError("invalid native pose packet")
        state = np.asarray(list(map(float, record[2:])))
        if not np.isfinite(state).all() or not 0.99 < np.linalg.norm(state[3:7]) < 1.01:
            raise RuntimeError(f"invalid native pose at {stamp}")
        row = in_public_world(
            {"timestamp": stamp, "map_id": 0, "inertial": state[7:].tolist(),
             "pose_cw": world_camera(rotation(state[3:7]), state[:3], self.calibration)},
            self.gauge)
        self.recent.append(row)
        return row

    def read_synchronous(self, stamp, send):
        record = self.readline(8).split()
        self.timing = None
        if record and record[0] == b"timing":
            expected, received, done, frontend, optimization = map(int, record[1:])
            record = self.readline(8).split()
            reply = time.monotonic_ns()
            if expected != stamp or not send <= received <= done <= reply:
                raise RuntimeError("native timing does not match the request")
            self.timing = dict(request_ns=received-send, reply_ns=reply-done,
                               host_ns=done-received, frontend_ns=frontend,
                               optimization_ns=optimization)
        pose = self.decode(record, stamp)
        return [pose] if pose is not None else []

    def expire_callback(self):
        self.resolved = self.awaiting.popleft()
        self.callback_gaps += 1
        self.recent.clear()

    def read_callbacks(self, stamp, send):
        header = self.readline(8).split()
        if len(header) != 5 or header[0] != b"batch":
            raise RuntimeError("invalid native callback batch")
        expected, received, done, count = map(int, header[1:])
        if expected != stamp or not send <= received <= done <= time.monotonic_ns() or not 0 <= count <= 8:
            raise RuntimeError("native callback batch does not match the request")
        records = [self.readline(8).split() for _ in range(count)]
        self.timing = dict(request_ns=received-send, reply_ns=time.monotonic_ns()-done,
                           submission_ns=done-received, callbacks=count)
        poses = []
        for record in records:
            callback_stamp = int(record[0])
            if callback_stamp <= self.resolved:
                self.late_callbacks += 1
                continue
            if callback_stamp not in self.awaiting:
                raise RuntimeError(f"unrequested native callback {callback_stamp}")
            while self.awaiting[0] < callback_stamp:
                self.expire_callback()
            self.resolved = self.awaiting.popleft()
            pose = self.decode(record, self.resolved)
            if pose is not None:
                poses.append(pose)
        # A native frame that never publishes may not hold the input stream hostage.
        # Keep the current solve and the previous publication pending during streaming.
        limit = 2 if stamp else 0
        while len(self.awaiting) > limit:
            self.expire_callback()
        return poses

    def submit(self, pair, images, imu):
        if self.pipelined and images is not None:
            self.awaiting.append(pair.timestamp)
        send = self.write_request(pair.timestamp, images, imu)
        if self.pipelined:
            return self.read_callbacks(pair.timestamp, send)
        return self.read_synchronous(pair.timestamp, send)

    def settle(self):
        if not self.pipelined:
            return []
        return self.read_callbacks(0, self.write_request(0, None, ()))

    def step(self, pair, images, imu):
        poses = self.submit(pair, images, imu)
        if self.pipelined and images is not None:
            poses += self.settle()
        return next((row for row in poses if row["timestamp"] == pair.timestamp), None)

    def close(self):
        try:
            self.process.stdin.close()
        except BrokenPipeError:
            pass
        try:
            return self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                return self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                return self.process.wait()
        finally:
            self.reply.close()
