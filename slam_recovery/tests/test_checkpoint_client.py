"""The checkpoint channel is a file protocol, so it can be tested without ROS or a host.

What matters here is the part that would silently corrupt a run: a command must be executed at
most once, and a host that never answers must be visible as a failure rather than as a success.
"""

import os
import threading
import time

from slam_recovery.ros.recovery_node import CheckpointClient


class _FakeHost(threading.Thread):
    """Stands in for the host's poll loop: consume cmd, rename it away, write an ack."""

    def __init__(self, directory, ack="OK {cmd} done", delay=0.0):
        super().__init__(daemon=True)
        self.dir = directory
        self.ack = ack
        self.delay = delay
        self.seen = []
        self._stop_evt = threading.Event()

    def run(self):
        while not self._stop_evt.is_set():
            path = os.path.join(self.dir, "cmd")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    cmd = fh.read().strip()
                os.rename(path, os.path.join(self.dir, "cmd.done"))
                self.seen.append(cmd)
                time.sleep(self.delay)
                with open(os.path.join(self.dir, "ack"), "w", encoding="utf-8") as fh:
                    fh.write(self.ack.format(cmd=cmd) + "\n")
            time.sleep(0.005)

    def stop(self):
        self._stop_evt.set()
        self.join(timeout=2)


def test_one_command_runs_exactly_once(tmp_path):
    host = _FakeHost(str(tmp_path))
    host.start()
    try:
        client = CheckpointClient(str(tmp_path), ack_timeout_s=5.0)
        event = client._send("snapshot")
        assert event["ok"] is True
        assert host.seen == ["snapshot"]
        # A second send must produce a second execution, not a replay of the first ack.
        client._send("restore")
        assert host.seen == ["snapshot", "restore"]
    finally:
        host.stop()


def test_a_silent_host_is_a_failure_not_a_success(tmp_path):
    client = CheckpointClient(str(tmp_path), ack_timeout_s=0.2)
    event = client._send("snapshot")
    assert event["ok"] is False
    assert event["error"] == "ack_timeout"
    assert client.failures == 1
    assert client.snapshots == 0


def test_rolling_snapshot_respects_the_period_and_the_quiescent_flag(tmp_path):
    host = _FakeHost(str(tmp_path))
    host.start()
    try:
        client = CheckpointClient(str(tmp_path), snapshot_period_s=10.0, ack_timeout_s=5.0)
        assert client.tick(100.0, quiescent=False) is None      # a segment is open
        assert client.tick(100.0, quiescent=True) is not None   # first snapshot
        assert client.tick(101.0, quiescent=True) is None       # inside the period
        assert client.tick(110.5, quiescent=True) is not None   # period elapsed
        assert host.seen == ["snapshot", "snapshot"]
    finally:
        host.stop()


def test_a_disabled_client_sends_nothing(tmp_path):
    client = CheckpointClient("")
    assert client.enabled is False
    assert client.tick(1e9, quiescent=True) is None
    assert client.events == []
