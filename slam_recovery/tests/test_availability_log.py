"""The availability stream has to answer "which precondition failed", not repeat the label.

Three things are checked here: the recorder keeps every frame (the summary cap is 2 000), the
support evaluation reports the same fraction it decided on with the sample rows it used, and the
NIS provenance separates computed / carried_forward / unavailable with the raw value class.
"""

import json
import os
import tempfile
import unittest

import numpy as np

from slam_recovery.ros.availability_log import AvailabilityRecorder
from slam_recovery.ros.recovery_node import LiveNis
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode


class TestRecorder(unittest.TestCase):
    def test_every_frame_is_written_past_the_summary_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "availability.jsonl")
            rec = AvailabilityRecorder(path, run_id="r")
            for i in range(2500):
                rec.record({"kf_id": i, "status": "UNAVAILABLE"})
            rec.close()
            with open(path, encoding="utf-8") as fh:
                rows = [json.loads(line) for line in fh]
            self.assertEqual(len(rows), 2500)
            self.assertEqual(rows[-1]["kf_id"], 2499)
            self.assertEqual(rows[0]["run_id"], "r")

    def test_scored_frames_keep_a_sample_and_unsupported_frames_keep_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "availability.jsonl")
            rec = AvailabilityRecorder(path)
            pts = [{"row": i} for i in range(200)]
            rec.record({"status": "AVAILABLE", "support": {"points": list(pts)}})
            rec.record({"status": "UNAVAILABLE", "support": {"points": list(pts)}})
            rec.close()
            with open(path, encoding="utf-8") as fh:
                rows = [json.loads(line) for line in fh]
            self.assertEqual(len(rows[0]["support"]["points"]), 20)
            self.assertEqual(rows[0]["support"]["points_total"], 200)
            self.assertEqual(len(rows[1]["support"]["points"]), 200)
            self.assertNotIn("points_total", rows[1]["support"])


class TestPredictedPoseSupport(unittest.TestCase):
    def test_the_row_carries_the_support_fraction_under_the_predicted_pose(self):
        from slam_recovery.ros.recovery_node import NativeClosedLoop
        from slam_recovery.tests.test_recovery_node import _FakeLoopNode, _scan

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "availability.jsonl")
            node = _FakeLoopNode(trigger_at=10 ** 9)
            loop = NativeClosedLoop(node, run_id="run", availability_log=path)
            loop.on_pair(1_000_000_000, np.eye(4), _scan(200))
            loop.availability.close()
            with open(path, encoding="utf-8") as fh:
                row = json.loads(fh.readline())
        self.assertIn("support_under_predicted_pose", row)
        self.assertIsNotNone(row["support_under_predicted_pose"])
        self.assertIsNotNone(row["prediction"])
        self.assertIsNotNone(row["reference"]["cache_key"])

    def test_prediction_extrapolates_the_last_two_trusted_poses(self):
        from slam_recovery.ros.recovery_node import NativeClosedLoop
        from slam_recovery.tests.test_recovery_node import _FakeLoopNode

        node = _FakeLoopNode(trigger_at=10 ** 9)
        node._kf_timestamps = {1: 0, 2: 1_000_000_000}
        T0, T1 = np.eye(4), np.eye(4)
        T1[0, 3] = 2.0                      # 2 m/s along x
        node.tx_mgr.trusted_poses = {1: T0, 2: T1}
        loop = NativeClosedLoop(node, run_id="run")
        predicted, basis = loop._predicted_pose(2_000_000_000)
        self.assertAlmostEqual(float(predicted[0, 3]), 4.0, places=6)
        self.assertEqual(basis["mode"], "velocity")
        self.assertEqual(basis["horizon_s"], 1.0)
        self.assertAlmostEqual(basis["velocity_mps"][0], 2.0, places=6)


class TestDecisionsUnchanged(unittest.TestCase):
    def test_the_log_does_not_change_decisions(self):
        from slam_recovery.ros.recovery_node import NativeClosedLoop
        from slam_recovery.tests.test_recovery_node import _FakeLoopNode, _scan

        def run(log_path):
            node = _FakeLoopNode(trigger_at=10 ** 9)
            loop = NativeClosedLoop(node, run_id="run", availability_log=log_path)
            for i in range(12):
                loop.on_pair(1_000_000_000 + i * 100_000_000, np.eye(4), _scan(200))
            loop.availability.close()
            diag = [(d["kf_id"], d["detection_status"], d["nis"]) for d in loop.diag]
            return (diag, dict(loop.detection_counts), len(loop.records))

        with tempfile.TemporaryDirectory() as tmp:
            with_log = run(os.path.join(tmp, "a.jsonl"))
            without = run(None)
        self.assertEqual(with_log, without)


class TestSupportDetail(unittest.TestCase):
    def test_the_detail_reports_the_fraction_that_decided(self):
        node = OnlineRecoveryTransactionNode()
        rng = np.random.default_rng(0)
        cloud = rng.normal(size=(400, 3)) * 0.1
        node.scan_buffer_body[0] = cloud.copy()
        ref = cloud[:200].copy()
        detail = {}
        passed = node._frame_has_reference_support(
            0, ref, {0: np.eye(4)}, radius_m=0.5, min_supported_fraction=0.6, detail=detail)
        self.assertTrue(passed)
        self.assertEqual(detail["reason"], "ok")
        self.assertEqual(detail["sampled_query_count"], 200)
        self.assertEqual(detail["within_radius_count"], int(np.count_nonzero(
            [p["within_1m"] for p in detail["points"]])))
        self.assertAlmostEqual(detail["supported_fraction"],
                               detail["within_radius_count"] / detail["sampled_query_count"])
        self.assertTrue(detail["pass"])
        # the saved row indexes are the rows the samples came from
        self.assertEqual(detail["points"][0]["row"], 0)
        self.assertEqual(len(detail["points"]), 200)

    def test_a_frame_below_the_threshold_names_the_fraction_branch(self):
        node = OnlineRecoveryTransactionNode()
        rng = np.random.default_rng(4)
        node.scan_buffer_body[0] = rng.normal(size=(400, 3)) * 0.1
        detail = {}
        passed = node._frame_has_reference_support(
            0, np.zeros((10, 3)) + 100.0, {0: np.eye(4)}, detail=detail)
        self.assertFalse(passed)
        self.assertEqual(detail["reason"], "fraction_below_threshold")
        self.assertEqual(detail["supported_fraction"], 0.0)

    def test_a_frame_without_a_scan_says_so(self):
        node = OnlineRecoveryTransactionNode()
        detail = {}
        passed = node._frame_has_reference_support(
            99, np.zeros((10, 3)), {99: np.eye(4)}, detail=detail)
        self.assertFalse(passed)
        self.assertEqual(detail["reason"], "missing_scan")


class TestLoopRows(unittest.TestCase):
    def test_one_row_per_paired_frame_and_the_status_is_derivable(self):
        from slam_recovery.ros.recovery_node import NativeClosedLoop
        from slam_recovery.tests.test_recovery_node import _FakeLoopNode, _scan

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "availability.jsonl")
            node = _FakeLoopNode(trigger_at=10 ** 9)
            loop = NativeClosedLoop(node, run_id="run", availability_log=path)
            for i in range(3):
                loop.on_pair(1_000_000_000 + i * 100_000_000, np.eye(4), _scan(200))
            loop.availability.close()
            with open(path, encoding="utf-8") as fh:
                rows = [json.loads(line) for line in fh]
            self.assertEqual(len(rows), 3)
            for row in rows:
                self.assertEqual(row["run_id"], "run")
                self.assertIsNotNone(row["support_pass"])
                self.assertEqual(row["status"], row["status_from_conditions"])
                self.assertIsNotNone(row["nis"])

    def test_carried_forward_keeps_the_value_and_its_age(self):
        node = OnlineRecoveryTransactionNode()
        nis = LiveNis(node)
        rng = np.random.default_rng(3)
        scan = rng.normal(size=(200, 3))
        # The first frame can only seed the previous-scan fallback; the second frame is scored
        # against it, and only then is there a value that a later frame could carry.
        _v0, source0, _ = nis.measure(np.eye(4), scan, now_ts_ns=0, kf_id=0)
        self.assertEqual(source0, "unavailable")
        first, source1, _ = nis.measure(np.eye(4), scan, now_ts_ns=500_000_000, kf_id=1)
        self.assertEqual(source1, "computed")
        nis._prev_world = None              # next frame cannot reach a reference
        detail = {}
        value, source, _ = nis.measure(np.eye(4), scan, now_ts_ns=1_000_000_000, kf_id=2,
                                       detail=detail)
        self.assertEqual(source, "carried_forward")
        self.assertEqual(value, first)
        self.assertEqual(detail["source"], "carried_forward")
        self.assertEqual(detail["carried"]["kf_id"], 1)
        self.assertEqual(detail["carried"]["age_s"], 0.5)


class TestNisDetail(unittest.TestCase):
    def test_computed_frames_report_the_raw_value_and_its_branch(self):
        node = OnlineRecoveryTransactionNode()
        nis = LiveNis(node)
        rng = np.random.default_rng(1)
        ref = rng.normal(size=(400, 3))
        # Seed the fallback reference with the first frame, then score the second against it.
        nis.measure(np.eye(4), ref, now_ts_ns=0, kf_id=0)
        detail = {}
        value, source, reference = nis.measure(
            np.eye(4), ref + 0.01, now_ts_ns=100_000_000, kf_id=1, detail=detail)
        self.assertEqual(source, "computed")
        self.assertEqual(detail["source"], "computed")
        self.assertEqual(detail["raw_kind"], "finite")
        self.assertIsNotNone(detail["holdout"]["branch"])
        self.assertGreater(detail["holdout"]["query_sampled"], 0)
        self.assertIsNone(detail["carried"])

    def test_a_frame_with_no_reference_reports_unavailable(self):
        node = OnlineRecoveryTransactionNode()
        nis = LiveNis(node)
        rng = np.random.default_rng(2)
        scan = rng.normal(size=(200, 3))
        nis.measure(np.eye(4), scan, now_ts_ns=0, kf_id=0)
        # No trusted map points at all and no previous scan after a reset: unavailable.
        nis._prev_world = None
        detail = {}
        value, source, reference = nis.measure(np.eye(4), scan, now_ts_ns=500_000_000, kf_id=1,
                                               detail=detail)
        self.assertEqual(source, "unavailable")
        self.assertIsNone(value)
        self.assertEqual(detail["source"], "unavailable")
        self.assertIn(detail["raw_kind"], ("not_computed", "inf", "nan"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
