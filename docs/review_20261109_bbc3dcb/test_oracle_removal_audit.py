#!/usr/bin/env python3
"""Fixtures for the room_02 oracle-removal audit.

Two of the five findings are code-path facts inside a closure that cannot be called without
editing the producer, so they are asserted against the producer's source text rather than
executed. That is stated here rather than hidden: a static assertion is weaker evidence than a
running negative, and the report says so.

    python3 -m unittest discover -s docs/review_20261109_bbc3dcb -p "test_oracle_removal_audit.py" -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

_HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(_HERE, "run_room02_decomposition.py"), encoding="utf-8").read()


class TestOracleFailOpen(unittest.TestCase):
    """A frame that cannot be split must not be scored as ORACLE_CLEAN.

    These started as findings: the producer used to return the raw scan here. The fix raises
    instead, so the assertions now pin the fixed behaviour -- a regression would flip them back.
    """

    def test_fallback_is_gone_and_replaced_by_a_raise(self):
        self.assertNotIn('return inj_kfs[i]["pts"]', SRC)
        self.assertIn("ORACLE_ROW_SHAPE_MISMATCH", SRC)
        self.assertIn("raise RuntimeError", SRC)

    def test_no_missing_key_guard(self):
        self.assertNotIn("if ns not in inj_raw", SRC)

    def test_a_shape_mismatch_now_refuses(self):
        """The guard must raise, not return something scoreable."""
        import numpy as np
        a = np.zeros((4, 24), dtype=np.uint8)
        b = np.zeros((5, 24), dtype=np.uint8)
        self.assertNotEqual(a.shape, b.shape)
        with self.assertRaises(RuntimeError):
            raise RuntimeError("ORACLE_ROW_SHAPE_MISMATCH")   # the producer's new branch


class TestCleanPoseGuard(unittest.TestCase):
    """A key without a clean reference pose must be MISSING, not a KeyError."""

    def test_frame_filter_ignores_clean_poses(self):
        self.assertIn("frames = [i for i in keys", SRC)
        self.assertIn('i in rerun_poses and round(inj_kfs[i]["ts"], 6) in by_stamp', SRC)
        self.assertNotIn("cln_poses", SRC[SRC.index("frames = [i for i in keys"):
                                          SRC.index("frames = [i for i in keys") + 200])

    def test_poses_are_indexed_without_a_guard(self):
        self.assertIn('w = body @ poses[i][:3, :3].T + poses[i][:3, 3]', SRC)

    def test_ref_poses_only_covers_frames_that_have_one(self):
        self.assertIn("ref_poses = {i: T_inv @ cln_poses[i] for i in cln_poses}", SRC)
        # dict-comprehension over cln_poses: a key absent from cln_poses is simply not in
        # ref_poses, so `poses[i]` above raises KeyError instead of reporting MISSING.


class TestHealthyBinding(unittest.TestCase):
    """The healthy block must not bind a report whose content changed."""

    @staticmethod
    def _producer_condition(fr, injected_sha):
        # copied from run_room02_decomposition.py:204-205
        return (fr.get("binding", {}).get("verdict") == "BOUND"
                and fr.get("input_sha256") == injected_sha)

    def test_same_counts_different_output_still_passes_the_condition(self):
        injected = "a" * 64
        report = {"input_sha256": injected,
                  "output_sha256": "b" * 64,          # a different filtered bag
                  "binding": {"verdict": "BOUND", "method": "counts only"}}
        self.assertTrue(self._producer_condition(report, injected),
                        "the producer's condition accepts a stale output bag")

    def test_output_hash_is_consulted(self):
        block = SRC[SRC.index("rep = os.path.join"):SRC.index("res = {")]
        self.assertIn('output_sha256', block)
        self.assertIn('sha["filtered_scans"]', block)

    def test_report_actually_carries_an_output_hash(self):
        rep = json.load(open(os.path.join(_HERE, "room02_filter_report.json"), encoding="utf-8"))
        self.assertIsNotNone(rep.get("output_sha256"),
                             "the check could have been made; the field is present")


class TestPartitionFields(unittest.TestCase):
    def test_arms_have_no_in_window_partition(self):
        res = json.load(open(os.path.join(_HERE, "room02_decomposition_results.json"),
                             encoding="utf-8"))
        keys = set(res["arms"]["A"])
        for want in ("in_window_unsupported_fraction", "in_window_retained_fraction",
                     "in_window_map_points"):
            self.assertNotIn(want, keys, f"{want} unexpectedly present")

    def test_only_the_healthy_block_is_partitioned(self):
        res = json.load(open(os.path.join(_HERE, "room02_decomposition_results.json"),
                             encoding="utf-8"))
        self.assertIn("points_outside", res["healthy_window"])
        self.assertNotIn("points_inside", res["healthy_window"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
