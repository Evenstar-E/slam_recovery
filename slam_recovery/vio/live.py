"""Independent 1x input scheduling and acknowledged external pose delivery."""
import hashlib
import json
import multiprocessing as mp
import queue
import socket
import time

from .stream import euroc


def paced_source(pairs, fifo, destination):
    first = pairs[0].timestamp
    start = time.monotonic_ns()
    with destination.open("x") as log:
        for pair in pairs:
            payload = (pair.left.read_bytes(), pair.right.read_bytes())
            digest = [hashlib.sha256(image).hexdigest() for image in payload]
            due = start + pair.timestamp - first
            wait = (due - time.monotonic_ns()) / 1e9
            if wait > 0:
                time.sleep(wait)
            actual = time.monotonic_ns()
            delivered = True
            try:
                fifo.put_nowait((pair, actual, payload))
            except queue.Full:
                delivered = False
            print(json.dumps({"timestamp": pair.timestamp, "scheduled_ns": due,
                              "arrival_ns": actual, "enqueued": delivered,
                              "image_sha256": digest, "image_bytes": sum(map(len, payload)),
                              "imu_count": len(pair.imu)}), file=log)
    fifo.put(None)


class LiveInput:
    def __init__(self, dataset, limit, output, capacity=512):
        from itertools import islice

        pairs = list(islice(euroc(dataset), limit))
        if not pairs:
            raise ValueError("no stereo frames")
        # A fork here would retain the ORB worker's stdin writers and the
        # subscriber socket while the independent replay is still publishing.
        context = mp.get_context("spawn")
        self.fifo = context.Queue(capacity)
        self.process = context.Process(target=paced_source, args=(pairs, self.fifo, output))
        self.process.start()

    def __iter__(self):
        while True:
            try:
                item = self.fifo.get(timeout=5)
            except queue.Empty:
                if not self.process.is_alive():
                    raise RuntimeError("1x source exited without completion")
                continue
            if item is None:
                break
            yield item

    def close(self):
        self.process.join(timeout=1)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join()
        self.fifo.close()


class PosePublisher:
    def __init__(self, address):
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(5)
        try:
            self.socket.connect(str(address))
        except BaseException:
            self.socket.close()
            raise
        self.receipts = self.socket.makefile("rb")
        self.sequence = 0

    def send(self, row):
        self.sequence += 1
        self.socket.sendall(json.dumps(dict(row, delivery_id=self.sequence),
                                       allow_nan=False).encode() + b"\n")
        reply = self.receipts.readline()
        if not reply or int(reply) != self.sequence:
            raise IOError(f"subscriber did not acknowledge delivery {self.sequence}")
        return self.sequence

    def close(self):
        self.receipts.close()
        self.socket.close()
