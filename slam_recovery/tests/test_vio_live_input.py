from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from slam_recovery.vio.live import LiveInput
from slam_recovery.vio.stream import Pair


class LiveInputTest(unittest.TestCase):
    def test_pacer_does_not_keep_host_stdin_open(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "frame.png"
            image.write_bytes(b"fixture")
            frames = [Pair(1, image, image, ()), Pair(5_000_000_001, image, image, ())]
            with subprocess.Popen(["cat"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL) as host:
                with patch("slam_recovery.vio.live.euroc", return_value=iter(frames)):
                    source = LiveInput(root, None, root / "clock.jsonl")
                try:
                    host.stdin.close()
                    self.assertEqual(host.wait(timeout=1), 0)
                    self.assertTrue(source.process.is_alive())
                finally:
                    source.close()
