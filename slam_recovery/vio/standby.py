"""Bounded background mirroring for the live native standby."""
from collections import deque
from concurrent.futures import TimeoutError
from itertools import islice
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

    def at_boundary(self, wait_s=None):
        deadline = time.monotonic() + (self.wait_s if wait_s is None else wait_s)
        count = len(self.pending)
        while self.pending:
            self._finish_first(max(0, deadline - time.monotonic()))
        return count

    def retire(self, close):
        for future in self.pending:
            future.cancel()
        self.pending.clear()
        return self.executor.submit(close)


class StandbyRebuild:
    """Recreate a native replica using an immutable recording and one byte per input."""

    views = ("raw", "skip", "fit", "occluded")

    def __init__(self, executor, pairs, limit=2000, replay_features=False, rolling=False,
                 async_mapping=False):
        self.executor = executor
        self.pairs = pairs
        self.limit = limit
        self.entries = bytearray()
        self.rolling = rolling
        self.async_mapping = async_mapping
        self.timestamps = deque(maxlen=limit) if rolling else None
        self.feature_ids = deque(maxlen=limit) if rolling else None
        self.count = 0
        self.floor = 0
        self.base = 0
        self.masked_views = {}
        self.replay_features = replay_features
        self.replayed_frames = 0
        self.overflow = False
        self.pending = None
        self.cancelled = False

    def record(self, view, timestamp=None, features=b""):
        if self.overflow:
            return
        if len(self.entries) == self.limit:
            if not self.rolling:
                self.overflow = True
                return
            del self.entries[0]
            self.masked_views.pop(self.floor, None)
            self.floor += 1
        if isinstance(view, str):
            self.entries.append(self.views.index(view))
        else:
            self.entries.append(len(self.views))
            self.masked_views[self.count] = view
        self.count += 1
        if self.timestamps is not None:
            self.timestamps.append(timestamp)
            self.feature_ids.append(features)

    def _batch(self, offset):
        start = offset - self.floor
        stamps = list(self.timestamps)[start:] if self.timestamps is not None else ()
        codes = self.entries[start:]
        views = [self.views[code] if code < len(self.views) else self.masked_views[offset+i]
                 for i, code in enumerate(codes)]
        return list(zip(views, stamps, list(self.feature_ids)[start:])) if self.rolling else views

    def start(self, new_lane, checkpoint=None):
        self.replayed_frames = 0
        self.base = checkpoint["count"] if checkpoint else 0
        # Pin the initial short batch before native startup so the journal can advance.
        batch = self._batch(self.base)

        def replay_prefix():
            if checkpoint:
                pairs = islice(self.pairs(), self.base - 1, None)
                if next(pairs).timestamp != checkpoint["timestamp"]:
                    raise ValueError("checkpoint input index does not match its physical frame")
            else:
                pairs = iter(self.pairs())
            lane = new_lane()
            return self._replay(lane, pairs, self.base, 0, batch)

        self.pending = self.executor.submit(replay_prefix)

    def _replay(self, lane, pairs, offset, generation, batch):
        for entry in batch:
            if self.cancelled:
                break
            view, timestamp, features = entry if self.rolling else (entry, None, b"")
            name = view
            pair = next(pairs)
            if self.rolling and pair.timestamp != timestamp:
                raise ValueError("checkpoint suffix differs from the physical input journal")
            if self.replay_features and not self.rolling and name == "raw":
                generation += 1
                features = generation
            options = {"async_mapping": True} if self.async_mapping else {}
            if features:
                options["features"] = features
            lane.consume(pair, name, **options)
            offset += 1
            self.replayed_frames = offset - self.base
        return lane, pairs, offset, generation

    def at_tip(self, queue):
        if self.pending is None or not self.pending.done():
            return None
        receipt = self.pending
        self.pending = None
        lane, pairs, offset, generation = receipt.result()
        if self.overflow or offset < self.floor:
            return lane, False, 0
        tail = self._batch(offset)
        if len(tail) > 1:
            self.pending = self.executor.submit(self._replay, lane, pairs, offset, generation, tail)
            return None
        if tail:
            # One missing frame occupies one ordinary mirror slot. Queue it before
            # the next live frame so a constantly advancing journal cannot keep
            # an already-fast replica behind by a single frame indefinitely.
            queue.offer(self._replay, lane, pairs, offset, generation, tail)
        return lane, True, len(tail)
