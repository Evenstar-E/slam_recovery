"""A refused segment must end, or the run can never see a second event.

Mode 3 (soft bridge / wait) is the normal outcome of a refused candidate on this population.
The manager keeps `active_quarantine` set while waiting so arriving frames still have a home --
but that also means it never returns to HEALTHY, and the detector only opens a new segment from
HEALTHY. A two-event run therefore silently became a one-event run: both hall runs ended in
WAITING_FOR_EVIDENCE after 454/474 further frames, with zero second events.

The declared fix is a bounded wait: when the run sets `wait_limit_ns`, a wait that gets no
evidence inside that window closes as *unresolved* (the frames are recorded as lost, not
committed, and the trusted map stays at its last commit) and the run re-arms. Mode 4 already
left the manager terminal with no segment; the next frame re-arms that too.

Both tests fail on the pre-fix code: the first because `maybe_close_waiting_segment` does not
exist (no answer to "when does the wait end"), the second because frame 2 is registered on a
segment that never closes and never becomes trusted.
"""

import unittest

import numpy as np

from slam_recovery.core import RecoveryMode, RecoveryState, TangentFrame
from slam_recovery.health import DetectorConfig, JointHealthDetector
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode

WORLD = TangentFrame("world", "rot_trans", "world")
V = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
INFO_BEFORE = np.diag([60.0, 60.0, 60.0, 20.0, 40.0, 40.0])


def _open_waiting_segment(mgr, t_end_ns: int = 0):
    mgr.trigger_quarantine(
        t_end_ns, t_end_ns, V, INFO_BEFORE, 1.0,
        weak_direction_frame=WORLD, info_before_frame=WORLD,
        anchor_pose_world=np.eye(4))
    report = mgr.validate_and_resolve(None)   # no candidate -> Mode 3 while the bridge holds
    assert report.mode == RecoveryMode.MODE3_SOFT_BRIDGE_WAIT, report.mode
    assert mgr.state == RecoveryState.WAITING_FOR_EVIDENCE


class TestWaitLimit(unittest.TestCase):
    def test_a_wait_without_evidence_closes_after_the_declared_limit(self):
        mgr = TrustedMapTransactionManager(wait_limit_ns=5_000_000_000)
        _open_waiting_segment(mgr)
        mgr.register_quarantined_frame(7, 1_000_000_000)

        self.assertIsNone(mgr.maybe_close_waiting_segment(4_000_000_000),
                          "the wait closed before its declared limit")
        segment = mgr.maybe_close_waiting_segment(4_000_000_000 + 1_000)
        self.assertIsNone(segment, "3 s into a 5 s wait is not expired")

        segment = mgr.maybe_close_waiting_segment(5_000_000_000)
        self.assertIsNotNone(segment)
        self.assertIs(mgr.state, RecoveryState.ABORTED)
        self.assertIsNone(mgr.active_quarantine)
        self.assertEqual(mgr.unresolved_segments, [segment])
        event = mgr.lifecycle_events[-1]
        self.assertEqual(event["event"], "wait_limit_closed")
        self.assertIn("7", event["frames_unresolved"])
        # The trusted map is untouched: those frames are lost, not committed.
        self.assertEqual(mgr.trusted_poses, {})

    def test_rearm_returns_to_healthy_only_after_a_close(self):
        mgr = TrustedMapTransactionManager(wait_limit_ns=1_000_000_000)
        _open_waiting_segment(mgr)
        self.assertFalse(mgr.rearm(), "re-armed while a segment is still open")
        mgr.maybe_close_waiting_segment(2_000_000_000)
        self.assertTrue(mgr.rearm())
        self.assertIs(mgr.state, RecoveryState.HEALTHY)


class TestNodeRearm(unittest.TestCase):
    def test_a_frame_after_the_wait_is_trusted_and_the_run_is_healthy(self):
        node = OnlineRecoveryTransactionNode(wait_limit_sec=5.0)
        # The detector is not the subject here: switch its alarm legs off so the HEALTHY branch
        # promotes the frame instead of opening another segment. DetectorConfig is frozen, so the
        # detector is replaced rather than mutated.
        node.detector = JointHealthDetector(DetectorConfig(
            lambda_rot_min_th=0.0, lambda_trans_min_th=0.0,
            nis_spike_th=1e9, nis_cusum_h=1e9,
            loso_conflict_th=1e9, loop_spike_th=1e9,
            confirmation_margin_ns=node.tx_mgr.confirmation_margin_ns))

        cloud = np.random.default_rng(0).normal(size=(400, 3)) * 0.16
        body = TangentFrame("body", "rot_trans", "scan:0")
        node.scan_buffer_body[0] = cloud.copy()
        node._kf_timestamps[0] = 0
        node.tx_mgr.trigger_quarantine(
            0, 0, V, INFO_BEFORE, 1.0,
            weak_direction_frame=body, info_before_frame=body,
            anchor_pose_world=np.eye(4))
        node.tx_mgr.validate_and_resolve(None)
        self.assertIs(node.tx_mgr.state, RecoveryState.WAITING_FOR_EVIDENCE)

        # While the wait is open the frame belongs to the segment: registered, not trusted.
        node.step_frame(1, 1_000_000_000, np.eye(4), cloud, 0.5)
        self.assertIs(node.tx_mgr.state, RecoveryState.WAITING_FOR_EVIDENCE)
        self.assertNotIn(1, node.tx_mgr.trusted_poses)

        # Past the limit the same ingest path closes the wait and promotes the frame.
        node.step_frame(2, 8_000_000_000, np.eye(4), cloud, 0.5)
        self.assertIs(node.tx_mgr.state, RecoveryState.HEALTHY)
        self.assertNotIn(1, node.tx_mgr.trusted_poses,
                         "a frame from the closed segment reached the trusted map")
        self.assertEqual(node.tx_mgr.lifecycle_events[0]["event"], "wait_limit_closed")
        self.assertEqual(node.tx_mgr.lifecycle_events[1]["event"], "rearm")
        # A promoted frame needs the confirmation margin to pass; one more frame past it shows
        # the re-armed run is back on the normal trusted path, not just reporting HEALTHY.
        node.step_frame(3, 11_000_000_000, np.eye(4), cloud, 0.5)
        self.assertIn(2, node.tx_mgr.trusted_poses)


if __name__ == "__main__":
    unittest.main(verbosity=2)
