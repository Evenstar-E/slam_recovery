"""The independent-reference check must read a PCD and score the frames it was given."""

import gzip
import json
import os
import struct
import tempfile
import unittest

import numpy as np

from slam_recovery.validation.independent_reference import (
    load_rows, read_pcd_xyz, score_rows, summarise)


def _write_pcd(path, points):
    points = np.asarray(points, dtype=np.float32)
    header = ("VERSION .7\nFIELDS x y z intensity\nSIZE 4 4 4 4\nTYPE F F F F\n"
              "COUNT 1 1 1 1\nWIDTH %d\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\n"
              "POINTS %d\nDATA binary\n" % (len(points), len(points)))
    with open(path, "wb") as fh:
        fh.write(header.encode("ascii"))
        for p in points:
            fh.write(struct.pack("<ffff", float(p[0]), float(p[1]), float(p[2]), 0.0))


class TestReadPcd(unittest.TestCase):
    def test_binary_pcd_with_an_extra_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.pcd")
            pts = np.array([[1.0, 2.0, 3.0], [-1.0, 0.5, 0.25]])
            _write_pcd(path, pts)
            got = read_pcd_xyz(path)
        self.assertEqual(got.shape, (2, 3))
        np.testing.assert_allclose(got, pts, atol=1e-6)


class TestScore(unittest.TestCase):
    def _rows(self):
        T = np.eye(4)
        body = [[0.0, 0.0, 0.0], [0.1, 0.0, 0.0], [0.2, 0.0, 0.0]]
        return [{
            "kf_id": 1, "T_wb": [float(v) for v in T.reshape(-1)], "status": "UNAVAILABLE",
            "support": {"points": [{"body": b} for b in body], "supported_fraction": 0.0,
                        "pass": False},
        }]

    def test_a_reference_that_covers_the_scan_flips_the_answer(self):
        ref = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0], [0.2, 0.0, 0.0]])
        scored = score_rows(self._rows(), ref)
        self.assertTrue(scored[0]["independent_pass"])
        self.assertFalse(scored[0]["host_pass"])
        summary = summarise(scored)
        self.assertEqual(summary["host_low_new_reference_pass"], 1)
        self.assertEqual(summary["both_low"], 0)

    def test_a_reference_far_away_keeps_both_low(self):
        ref = np.array([[100.0, 100.0, 100.0]])
        scored = score_rows(self._rows(), ref)
        self.assertFalse(scored[0]["independent_pass"])
        self.assertEqual(summarise(scored)["both_low"], 1)

    def test_rows_without_samples_are_not_counted(self):
        rows = [{"kf_id": 0, "T_wb": [float(v) for v in np.eye(4).reshape(-1)],
                 "support": {"points": []}}]
        scored = score_rows(rows, np.zeros((1, 3)))
        self.assertEqual(summarise(scored)["frames_full_sample"], 0)

    def test_trimmed_frames_are_listed_separately_not_in_the_main_table(self):
        ref = np.array([[0.0, 0.0, 0.0]])
        rows = [{"kf_id": 1, "T_wb": [float(v) for v in np.eye(4).reshape(-1)],
                 "support": {"points": [{"body": [0.0, 0.0, 0.0]}], "points_total": 200,
                             "supported_fraction": 0.0, "pass": False}}]
        scored = score_rows(rows, ref)
        summary = summarise(scored)
        self.assertEqual(summary["frames_full_sample"], 0)
        self.assertEqual(summary["partial_sample_not_evaluable"], 1)
        self.assertEqual(summary["both_low"], 0)


class TestAlignment(unittest.TestCase):
    def test_icp_recovers_a_known_offset_and_reports_coverage(self):
        from slam_recovery.validation.independent_reference import icp_align

        rng = np.random.default_rng(0)
        body = rng.normal(size=(200, 3))
        offset = np.array([0.6, -0.4, 0.2])
        reference = body + offset
        seed = np.eye(4)
        result = icp_align(body, reference, seed)
        self.assertAlmostEqual(result["correction_m"], float(np.linalg.norm(offset)), places=2)
        self.assertGreater(result["fraction_within_1m"], 0.99)


class TestGauge(unittest.TestCase):
    def test_se3_between_two_runs_recovers_a_known_offset(self):
        from slam_recovery.validation.independent_reference import estimate_se3

        rng = np.random.default_rng(5)
        src = rng.normal(size=(40, 3))
        theta = 0.3
        R = np.array([[np.cos(theta), -np.sin(theta), 0.0],
                      [np.sin(theta), np.cos(theta), 0.0], [0.0, 0.0, 1.0]])
        t = np.array([1.0, -2.0, 0.5])
        dst = src @ R.T + t
        result = estimate_se3(src, dst)
        np.testing.assert_allclose(result["T"][:3, :3], R, atol=1e-8)
        np.testing.assert_allclose(result["T"][:3, 3], t, atol=1e-8)
        self.assertLess(result["max_residual_m"], 1e-6)


class TestLoadRows(unittest.TestCase):
    def test_gzip_and_plain(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain = os.path.join(tmp, "a.jsonl")
            with open(plain, "w") as fh:
                fh.write(json.dumps({"kf_id": 1}) + "\n")
            gz = plain + ".gz"
            with open(plain, "rb") as src, gzip.open(gz, "wb") as dst:
                dst.write(src.read())
            self.assertEqual(load_rows(plain)[0]["kf_id"], 1)
            self.assertEqual(load_rows(gz)[0]["kf_id"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
