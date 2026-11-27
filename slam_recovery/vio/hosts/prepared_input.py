"""Decode and check live stereo observations ahead of the foreground worker."""

from dataclasses import dataclass
from queue import Full, Queue
from threading import Event, Thread
import time

from ..stream import Pair, read_pair
from ..vision import input_support


@dataclass(frozen=True)
class PreparedFrame:
    pair: Pair
    arrival_ns: int
    images: tuple
    weak: bool
    decode_ns: int
    detector_ns: int
    ready_ns: int


class PreparedInput:
    """An ordered bounded queue between the original input clock and the host."""

    def __init__(self, source, faults, detect):
        self.queue = Queue(maxsize=6)
        self.stop = Event()
        self.thread = Thread(target=self._prepare, args=(source, faults, detect), name="vio-input")
        self.thread.start()

    def _put(self, item):
        while not self.stop.is_set():
            try:
                self.queue.put(item, timeout=.05)
                return True
            except Full:
                pass
        return False

    def _prepare(self, source, faults, detect):
        origin = None
        try:
            for pair, arrival, payload in source:
                if self.stop.is_set():
                    break
                if origin is None:
                    origin = pair.timestamp
                seconds = (pair.timestamp - origin) / 1e9
                obscured = any(start <= seconds < stop for start, stop in faults)
                started = time.monotonic_ns()
                images = read_pair(pair, "occluded" if obscured else "raw", payload)
                decoded = time.monotonic_ns()
                weak = detect and min(input_support(images)) < 12
                checked = time.monotonic_ns()
                # The native input window only uses IMU through image time +25 ms.
                ahead = (arrival + 25_000_000 - checked) / 1e9
                if ahead > 0 and self.stop.wait(ahead):
                    break
                frame = PreparedFrame(pair, arrival, images, weak, decoded-started,
                                      checked-decoded if detect else 0, time.monotonic_ns())
                if not self._put(frame):
                    break
        except Exception as error:
            self._put(error)
            return
        self._put(None)

    def __iter__(self):
        while True:
            item = self.queue.get()
            if item is None:
                return
            if isinstance(item, Exception):
                raise item
            yield item

    def close(self):
        self.stop.set()
        self.thread.join()
