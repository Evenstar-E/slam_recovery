"""Bounded background mirroring for the live native standby."""
from collections import deque
from concurrent.futures import TimeoutError
import time


class StandbyTimeout(RuntimeError):
    pass


class StandbyQueue:
    def __init__(self, executor, capacity=8, wait_s=0.35):
        self.executor = executor
        self.capacity = capacity
        self.wait_s = wait_s
        self.pending = deque()

    def _finish_first(self, timeout):
        try:
            self.pending[0].result(timeout=timeout)
        except TimeoutError as error:
            raise StandbyTimeout("standby did not reach the requested boundary") from error
        self.pending.popleft()

    def idle(self):
        while self.pending and self.pending[0].done():
            self._finish_first(0)
        return not self.pending

    def offer(self, callback, *args):
        self.idle()
        waited = len(self.pending) >= self.capacity
        if waited:
            self._finish_first(self.wait_s)
        self.pending.append(self.executor.submit(callback, *args))
        return waited

    def at_boundary(self):
        deadline = time.monotonic() + self.wait_s
        count = len(self.pending)
        while self.pending:
            self._finish_first(max(0, deadline - time.monotonic()))
        return count

    def retire(self, close):
        for future in self.pending:
            future.cancel()
        self.pending.clear()
        return self.executor.submit(close)
