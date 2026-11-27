"""Durable native checkpoint generations backed by an append-only map block file."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import time


# Content anchors let unchanged regions realign after insertion in the native archive.
ANCHOR = re.compile(rb"[\x21-\x24][\x71-\x74]")
MIN_BLOCK = 4096
MAX_BLOCK = 32768


def blocks(data):
    begin = 0
    for match in ANCHOR.finditer(data):
        end = match.start()
        if end - begin < MIN_BLOCK:
            continue
        while end - begin > MAX_BLOCK:
            yield data[begin:begin + MAX_BLOCK]
            begin += MAX_BLOCK
        if end > begin:
            yield data[begin:end]
            begin = end
    while begin < len(data):
        yield data[begin:begin + MAX_BLOCK]
        begin += MAX_BLOCK


def digest(data):
    return hashlib.sha256(data).hexdigest()


def durable_file(path, data):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def durable_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class CheckpointStore:
    """One writer. A reader can use any published manifest while the pack grows."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir()
        self.pack = self.directory / "map.pack"
        self.index = {}
        self.latest = None

    @classmethod
    def open_existing(cls, directory):
        """Open a published pack for readback only."""
        store = cls.__new__(cls)
        store.directory = Path(directory)
        store.pack = store.directory / "map.pack"
        return store

    @contextmanager
    def staging(self):
        # Full native archives are staged in RAM. Only incremental bytes go to disk.
        with TemporaryDirectory(prefix="vio-checkpoint-", dir="/dev/shm") as folder:
            yield Path(folder) / "native"

    def capture(self, worker, count, timestamp):
        prepared = self.stage(worker)
        return self.commit(prepared, count, timestamp) if prepared is not None else None

    def stage(self, worker):
        started = time.monotonic_ns()
        with self.staging() as prefix:
            if not worker.save_checkpoint(prefix):
                return None
            captured = time.monotonic_ns()
            state = prefix.with_suffix(".state").read_bytes()
            map_data = prefix.with_suffix(".map").read_bytes()
        return started, captured, state, map_data

    def commit(self, prepared, count, timestamp):
        started, captured, state, map_data = prepared
        index = []
        appended = {}
        new_bytes = 0
        with self.pack.open("ab") as stream:
            for part in blocks(map_data):
                key = digest(part)
                location = self.index.get(key) or appended.get(key)
                if location is None:
                    location = stream.tell(), len(part)
                    stream.write(part)
                    appended[key] = location
                    new_bytes += len(part)
                index.append([key, *location])
            stream.flush()
            os.fsync(stream.fileno())
        self.index.update(appended)
        state_file = f"state-{count}.bin"
        manifest = dict(version=1, count=count, timestamp=timestamp, map_bytes=len(map_data),
                        appended_map_bytes=new_bytes, state_bytes=len(state),
                        blocks=index, state=state_file, state_sha256=digest(state),
                        native_capture_s=(captured - started) / 1e9)
        durable_file(self.directory / state_file, state)
        # The generation becomes visible only after the referenced data is durable.
        manifest["durable_s"] = (time.monotonic_ns() - started) / 1e9
        temp = self.directory / f"pending-{count}.json"
        durable_file(temp, json.dumps(manifest, separators=(",", ":")).encode())
        os.replace(temp, self.directory / f"checkpoint-{count}.json")
        durable_directory(self.directory)
        self.latest = manifest
        return manifest

    @contextmanager
    def restore(self, manifest):
        with self.staging() as target:
            with self.pack.open("rb") as source, target.with_suffix(".map").open("xb") as out:
                for key, offset, length in manifest["blocks"]:
                    source.seek(offset)
                    part = source.read(length)
                    if len(part) != length or digest(part) != key:
                        raise ValueError("checkpoint map block failed verification")
                    out.write(part)
                if out.tell() != manifest["map_bytes"]:
                    raise ValueError("checkpoint map length differs")
            state = (self.directory / manifest["state"]).read_bytes()
            if len(state) != manifest["state_bytes"] or digest(state) != manifest["state_sha256"]:
                raise ValueError("checkpoint tracking state failed verification")
            target.with_suffix(".state").write_bytes(state)
            yield target
