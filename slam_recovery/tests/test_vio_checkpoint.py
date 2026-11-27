import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from slam_recovery.vio.checkpoint import CheckpointStore, MIN_BLOCK


class VioCheckpointStoreTest(unittest.TestCase):
    def test_generations_write_only_new_map_blocks_and_restore_independently(self):
        class Replica:
            def save_checkpoint(self, prefix):
                prefix.with_suffix(".map").write_bytes(self.map)
                prefix.with_suffix(".state").write_bytes(self.state)
                return True

        with TemporaryDirectory() as folder:
            store = CheckpointStore(Path(folder) / "checkpoint")
            worker = Replica()
            worker.map = b"\x00" * MIN_BLOCK * 8 + b"\x10" * MIN_BLOCK * 8 + b"\x20" * MIN_BLOCK * 8
            original = worker.map
            worker.state = b"one"
            first = store.capture(worker, 10, 100)
            worker.map = b"\x01" + original[1:]
            worker.state = b"two"
            second = store.capture(worker, 20, 200)
            self.assertEqual(first["appended_map_bytes"], len(original))
            self.assertEqual(second["appended_map_bytes"], MIN_BLOCK * 8)
            self.assertEqual(store.pack.stat().st_size, len(original) + MIN_BLOCK * 8)
            for saved, map_data, state in ((first, original, b"one"), (second, worker.map, b"two")):
                with store.restore(saved) as path:
                    self.assertEqual(path.with_suffix(".map").read_bytes(), map_data)
                    self.assertEqual(path.with_suffix(".state").read_bytes(), state)

    def test_unfinished_or_corrupt_data_cannot_restore(self):
        class Replica:
            def save_checkpoint(self, prefix):
                prefix.with_suffix(".map").write_bytes(b"atlas")
                prefix.with_suffix(".state").write_bytes(b"tracking")
                return True

        with TemporaryDirectory() as folder:
            store = CheckpointStore(Path(folder) / "checkpoint")
            saved = store.capture(Replica(), 10, 100)
            with store.pack.open("rb+") as path:
                path.seek(1, os.SEEK_SET)
                path.write(b"x")
            with self.assertRaisesRegex(ValueError, "block failed verification"):
                with store.restore(saved):
                    self.fail("corrupt checkpoint restored")
