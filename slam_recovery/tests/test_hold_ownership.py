"""Who owns the map: the driver while it holds, the host otherwise.

The v7 drain run showed both halves of this rule failing in opposite directions. The driver's
hold was never released (its `resume` was queued behind the second event's pre-armed hold for
116 s), and a host `Issleeping` arriving during a driver-held segment would have been read as a
native takeover even though the held host had not reset anything.

These are the two invariants the chain depends on, tested at the level they are implemented:
which signals count as a reset, and when a boundary hold is written.
"""

from __future__ import annotations

import types

from slam_recovery.ros.recovery_node import NativeClosedLoop


class _FakeCheckpoint:
    def __init__(self):
        self.holds = []
        self.snapshots = []
        self.resumes = 0

    def hold(self, apply_stamp_ns=None):
        self.holds.append(apply_stamp_ns)
        return {"command": "hold", "wall": 1.0, "payload": str(apply_stamp_ns or "")}

    def snapshot_now(self, apply_stamp_ns=None):
        self.snapshots.append(apply_stamp_ns)
        return {"command": "snapshot", "wall": 1.0, "payload": str(apply_stamp_ns or "")}

    def resume(self):
        self.resumes += 1
        return {"command": "resume", "wall": 1.0}


def _loop(cp=None, stamps=None, margin_ns=2_000_000_000):
    loop = NativeClosedLoop.__new__(NativeClosedLoop)
    loop.cp = cp
    loop.scripted_trigger_stamps_ns = list(stamps or [])
    loop.confirmation_margin_ns = int(margin_ns)
    loop.arm_lead_ns = 3_000_000_000
    loop._armed_stamps = set()
    loop.armed_boundaries = []
    loop._host_held = False
    loop.host_native_state = "PUBLISHING"
    loop.last_host_signal_wall = None
    loop.host_native_events = []
    loop._open = None
    return loop


def _episode():
    return types.SimpleNamespace(decided=False, meta={})


# ---------------------------------------------------------------------------------------------
# a host signal is not a reset while the driver holds the map
# ---------------------------------------------------------------------------------------------
def test_sleep_while_held_is_an_observation_not_a_takeover():
    cp = _FakeCheckpoint()
    loop = _loop(cp)
    loop._host_held = True
    loop._open = _episode()
    loop.on_host_signal("sleep", 5)
    meta = loop._open.meta
    assert "host_reset_during_quarantine" not in meta
    assert meta["host_signal_while_held"]["signal"] == "sleep"
    # Releasing here would hand the host back the map in the middle of our own recovery.
    assert cp.resumes == 0
    assert loop._host_held is True


def test_sleep_without_a_driver_hold_is_still_a_takeover():
    cp = _FakeCheckpoint()
    loop = _loop(cp)
    loop._open = _episode()
    loop.on_host_signal("build", 7)
    meta = loop._open.meta
    assert meta["host_reset_during_quarantine"]["signal"] == "build"
    assert "host_signal_while_held" not in meta
    assert cp.resumes == 1


# ---------------------------------------------------------------------------------------------
# the boundary hold is written just before its stamp, not at startup
# ---------------------------------------------------------------------------------------------
def test_arming_waits_for_the_lead_and_happens_once():
    cp = _FakeCheckpoint()
    loop = _loop(cp, stamps=[10_000_000_000])          # boundary = 8.0 s, lead 3 s => arm at 5.0 s
    loop._arm_scripted_boundary(4_900_000_000)
    assert cp.holds == [] and cp.snapshots == []
    loop._arm_scripted_boundary(5_000_000_000)
    assert cp.holds == [8_000_000_000]                 # the apply stamp, not the trigger stamp
    assert cp.snapshots == [8_000_000_000]
    assert loop._host_held is True
    loop._arm_scripted_boundary(7_000_000_000)         # already armed
    assert cp.holds == [8_000_000_000]
    assert len(loop.armed_boundaries) == 1
    assert loop.armed_boundaries[0]["lead_s"] == 3.0


def test_arming_does_nothing_without_a_host_or_a_declaration():
    loop = _loop(None, stamps=[10_000_000_000])
    loop._arm_scripted_boundary(9_000_000_000)
    assert loop._armed_stamps == set()
    loop2 = _loop(_FakeCheckpoint(), stamps=[])
    loop2._arm_scripted_boundary(9_000_000_000)
    assert loop2.armed_boundaries == []


# ---------------------------------------------------------------------------------------------
# a refused wait must expire without any input arriving
# ---------------------------------------------------------------------------------------------
class _FakeTx:
    def __init__(self, state, limit_ns=20_000_000_000):
        self.state = state
        self.wait_limit_ns = limit_ns
        self.closed = 0
        self.rearms = 0

    def maybe_close_waiting_segment(self, now_ns, elapsed_s=None):
        if elapsed_s is None or elapsed_s < self.wait_limit_ns / 1e9:
            return None
        self.closed += 1
        return object()

    def rearm(self):
        self.rearms += 1


def _loop_with_tx(state):
    loop = _loop(_FakeCheckpoint())
    tx = _FakeTx(state)
    detector = types.SimpleNamespace(resets=0)
    detector.reset = lambda: setattr(detector, "resets", detector.resets + 1)
    loop.node = types.SimpleNamespace(tx_mgr=tx, detector=detector)
    loop._last_ts_ns = 123
    loop._wait_wall_started = None
    return loop, tx, detector


def test_a_stalled_wait_closes_on_wall_time_without_frames():
    # v8 run: the driver held the host, the host stopped publishing because it was degenerate,
    # and the wait that would have released the hold could never expire. It must expire on the
    # wall clock, not on the next frame's stamp.
    from slam_recovery.core import RecoveryState
    loop, tx, detector = _loop_with_tx(RecoveryState.WAITING_FOR_EVIDENCE)
    loop._close_stalled_wait(100.0)          # starts the timer
    assert tx.closed == 0
    loop._close_stalled_wait(115.0)
    assert tx.closed == 0                    # 15 s < 20 s limit
    loop._close_stalled_wait(121.0)
    assert tx.closed == 1 and tx.rearms == 1 and detector.resets == 1
    assert loop._wait_wall_started is None   # and the timer is cleared for the next wait


def test_a_healthy_manager_is_not_closed():
    from slam_recovery.core import RecoveryState
    loop, tx, _ = _loop_with_tx(RecoveryState.HEALTHY)
    loop._close_stalled_wait(100.0)
    loop._close_stalled_wait(200.0)
    assert tx.closed == 0


def test_a_terminal_manager_is_rearmed_without_waiting_for_a_frame():
    # A Mode 4 refusal leaves the manager ABORTED; the detector path re-arms it on the next
    # frame. A scripted run with detection off takes no such path, so the v9 run fired 1 of its
    # 2 declared events and the second one could never open a segment.
    from slam_recovery.core import RecoveryState
    loop, tx, detector = _loop_with_tx(RecoveryState.ABORTED)
    tx.active_quarantine = None
    loop._close_stalled_wait(100.0)
    assert tx.rearms == 1 and detector.resets == 1
