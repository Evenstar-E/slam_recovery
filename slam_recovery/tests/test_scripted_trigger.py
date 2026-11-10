"""The controlled interface test opens a quarantine by calling the manager's own entry point.

What has to be true for the label CONTROLLED_INTERFACE_TEST to mean anything: the trigger fires at
the declared time and only then, it goes through ``trigger_quarantine`` (not a private shortcut),
and it never consults the detector. The detector is a fake here and is asserted untouched.
"""

import unittest

import numpy as np

from slam_recovery.ros.recovery_node import NativeClosedLoop
from slam_recovery.tests.test_recovery_node import _FakeLoopNode


def _scan(n=400):
    rng = np.random.default_rng(3)
    pts = rng.normal(size=(n, 3))
    pts[:, 2] = np.abs(pts[:, 2]) * 0.2
    return pts


class _TriggerableTxMgr:
    """Records trigger_quarantine calls; enough of the manager for this path."""

    def __init__(self, inner):
        self._inner = inner
        self.calls = []

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def trigger_quarantine(self, **kwargs):
        self.calls.append(kwargs)
        self._inner.active_quarantine = object()

    def register_quarantined_frame(self, kf_id, ts_ns=0):
        self._inner.register_quarantined_frame(kf_id, ts_ns)


class ScriptedTriggerTest(unittest.TestCase):
    def setUp(self):
        self.node = _FakeLoopNode(trigger_at=10 ** 9)
        self.mgr = _TriggerableTxMgr(self.node.tx_mgr)
        self.node.tx_mgr = self.mgr
        self.loop = NativeClosedLoop(self.node, run_id="run")
        self.pose = np.eye(4)
        self.scan = _scan()

    def test_no_triggers_means_no_forced_segment(self):
        self.assertFalse(self.loop._maybe_scripted_trigger(1, 1_000_000_000, self.pose, self.scan))
        self.assertEqual(self.mgr.calls, [])

    def test_fires_only_at_the_declared_time(self):
        self.loop.scripted_triggers_s = [1.0]
        t0 = 1_000_000_000
        self.assertFalse(self.loop._maybe_scripted_trigger(1, t0, self.pose, self.scan))
        self.assertFalse(self.loop._maybe_scripted_trigger(2, t0 + 900_000_000, self.pose, self.scan))
        self.assertTrue(self.loop._maybe_scripted_trigger(3, t0 + 1_000_000_000, self.pose, self.scan))
        self.assertEqual(len(self.mgr.calls), 1)

    def test_the_entry_point_gets_the_same_arguments_the_detector_path_builds(self):
        self.loop.scripted_triggers_s = [1.0]
        t0 = 1_500_000_000
        self.loop._maybe_scripted_trigger(1, t0, self.pose, self.scan)
        self.loop._maybe_scripted_trigger(2, t0 + 1_000_000_000, self.pose, self.scan)
        call = self.mgr.calls[0]
        for key in ("estimated_onset_ns", "current_ns", "weak_direction_6d", "info_before_6x6",
                    "propagated_cov_norm", "weak_direction_frame", "info_before_frame",
                    "anchor_pose_world"):
            self.assertIn(key, call)
        self.assertEqual(call["estimated_onset_ns"], t0 + 1_000_000_000)
        self.assertEqual(call["info_before_6x6"].shape, (6, 6))
        self.assertEqual(np.asarray(call["anchor_pose_world"]).shape, (4, 4))

    def test_it_fires_once_per_declared_time(self):
        self.loop.scripted_triggers_s = [1.0]
        t0 = 1_000_000_000
        self.loop._maybe_scripted_trigger(1, t0, self.pose, self.scan)
        self.loop._maybe_scripted_trigger(2, t0 + 1_000_000_000, self.pose, self.scan)
        self.loop._maybe_scripted_trigger(3, t0 + 2_000_000_000, self.pose, self.scan)
        self.assertEqual(len(self.mgr.calls), 1)
        self.assertEqual(len(self.loop.scripted_fired), 1)

    def test_the_detector_is_never_asked(self):
        asked = {"n": 0}

        class _Detector:
            def __getattr__(self, name):
                asked["n"] += 1
                raise AttributeError(name)

        self.node.detector = _Detector()
        self.loop.scripted_triggers_s = [0.0]
        self.loop._maybe_scripted_trigger(1, 1_000_000_000, self.pose, self.scan)
        self.assertEqual(asked["n"], 0)


if __name__ == "__main__":
    unittest.main()
