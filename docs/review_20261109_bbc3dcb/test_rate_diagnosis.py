#!/usr/bin/env python3
"""Fixtures for _segment_stats: the neighbour window must not diff across the fault gap.

The reviewed counterexample is `ts=[0,.066,1,1.066,2,2.066]`, `fault=[.9,1.1]`, where both
sides are a clean 66 ms cadence but the concatenated-sample diff reported 1/3 slow intervals.

    python3 -m unittest discover -s docs/review_20261109_bbc3dcb -p "test_rate_diagnosis.py" -v
"""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import run_rate_diagnosis as R  # noqa: E402

SLOW = 0.100        # an interval above this counts as a skipped publish


class TestNeighbourIntervals(unittest.TestCase):
    def test_reviewed_counterexample_is_not_slow(self):
        ts = np.array([0.0, 0.066, 1.0, 1.066, 2.0, 2.066])
        s = R._segment_stats(ts, 0.9, 1.1)
        self.assertEqual(s["raw_threshold_fraction_neighbours"], 0.0)
        self.assertAlmostEqual(s["median_ms_neighbours"], 66.0, places=6)

    def test_fake_cross_window_interval_is_excluded(self):
        """One point each side, far apart in time: no neighbour interval exists at all."""
        ts = np.array([0.0, 1.0, 2.0])
        s = R._segment_stats(ts, 0.9, 1.1)
        self.assertIsNone(s["raw_threshold_fraction_neighbours"])
        self.assertIsNone(s["median_ms_neighbours"])

    def test_left_slow_gap_is_counted(self):
        ts = np.array([0.0, 0.250, 1.0, 1.066, 2.0, 2.066])
        s = R._segment_stats(ts, 0.9, 1.1)
        self.assertGreater(s["raw_threshold_fraction_neighbours"], 0.0)

    def test_right_slow_gap_is_counted(self):
        ts = np.array([0.0, 0.066, 1.0, 1.066, 2.0, 2.250])
        s = R._segment_stats(ts, 0.9, 1.1)
        self.assertGreater(s["raw_threshold_fraction_neighbours"], 0.0)

    def test_both_sides_slow_reaches_one(self):
        ts = np.array([0.0, 0.300, 1.0, 1.066, 2.0, 2.300])
        s = R._segment_stats(ts, 0.9, 1.1)
        self.assertEqual(s["raw_threshold_fraction_neighbours"], 1.0)

    def test_clean_cadence_both_sides_is_zero(self):
        ts = np.array([0.0, 0.066, 0.132, 1.0, 1.066, 2.0, 2.066, 2.132])
        s = R._segment_stats(ts, 0.9, 1.1)
        self.assertEqual(s["raw_threshold_fraction_neighbours"], 0.0)
        self.assertAlmostEqual(s["median_ms_neighbours"], 66.0, places=6)

    def test_fault_window_samples_are_excluded_from_neighbours(self):
        """A slow pair *inside* the fault window must not leak into the neighbour statistic."""
        # the slow pair sits *inside* [0.9, 1.1]; the neighbours on both sides are clean
        ts = np.array([0.0, 0.066, 0.950, 1.050, 2.0, 2.066])
        s = R._segment_stats(ts, 0.9, 1.1)
        self.assertEqual(s["raw_threshold_fraction_neighbours"], 0.0)
        self.assertEqual(s["n_inside"], 2)

    def test_no_neighbours_at_all(self):
        s = R._segment_stats(np.array([0.95, 1.0, 1.05]), 0.9, 1.1)
        self.assertIsNone(s["raw_threshold_fraction_neighbours"])
        self.assertIsNone(s["median_ms_neighbours"])

    def test_single_sample_per_side_gives_no_intervals(self):
        ts = np.array([0.0, 1.0, 2.0])
        s = R._segment_stats(ts, 0.9, 1.1)
        self.assertIsNone(s["raw_threshold_fraction_neighbours"])

    def test_inside_fraction_and_max(self):
        ts = np.array([0.90, 0.966, 1.066, 1.500])
        s = R._segment_stats(ts, 0.9, 1.1)
        self.assertEqual(s["n_inside"], 3)
        self.assertAlmostEqual(s["max_ms_inside"], 100.0, places=6)
        self.assertEqual(s["raw_threshold_fraction_inside"], 0.5)

    def test_neighbour_window_is_capped_at_fifteen_seconds(self):
        ts = np.array([0.0, 0.066, 20.0, 20.066, 1.0, 1.066, 2.0, 2.066])
        s = R._segment_stats(np.sort(ts), 0.9, 1.1)
        # the 20 s samples are outside lo-15 and hi+15, so they contribute nothing
        self.assertAlmostEqual(s["median_ms_neighbours"], 66.0, places=6)
        self.assertEqual(s["raw_threshold_fraction_neighbours"], 0.0)

    def test_boundary_sample_at_lo_minus_15_is_included(self):
        lo = 100.0
        ts = np.array([lo - 15.0, lo - 14.934, lo - 0.1, lo + 0.5, lo + 20.0, lo + 20.066])
        s = R._segment_stats(ts, lo, lo + 1.0)
        self.assertIsNotNone(s["median_ms_neighbours"])


class TestIntervalStats(unittest.TestCase):
    def test_hole_detection(self):
        ts = np.array([0.0, 0.066, 5.0, 5.066])
        d = R._intervals(ts)
        self.assertEqual(d["n"], 4)
        self.assertEqual(d["n_holes"], 1)
        self.assertAlmostEqual(d["hole_times"][0], 5.0, places=6)

    def test_single_sample_does_not_crash(self):
        d = R._intervals(np.array([1.0]))
        self.assertEqual(d["n"], 1)
        self.assertIsNone(d["median_ms"])
        self.assertEqual(d["n_holes"], 0)

    def test_empty_array_does_not_crash(self):
        d = R._intervals(np.zeros(0))
        self.assertEqual(d["n"], 0)
        self.assertIsNone(d["max_ms"])

    def test_even_cadence_has_no_holes(self):
        d = R._intervals(np.arange(0.0, 2.0, 0.1))
        self.assertEqual(d["n_holes"], 0)
        self.assertEqual(d["n_over_1.5x_median"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
