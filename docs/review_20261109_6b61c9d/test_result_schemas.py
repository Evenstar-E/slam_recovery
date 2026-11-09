#!/usr/bin/env python3
"""Key-set guards for the archived result files.

Adding a field once dropped `trajectory.population`; a prose note is not a guard. These tests pin
the top-level and per-block key sets of the results that feed the paper's evidence, so a structure
change that removes a protection fails here instead of surfacing in a later review.

Convention: every check states what must be present (subset) AND, for block maps, that no
unregistered block appears (whitelist). Adding a new block therefore requires editing the
whitelist, and the failure names the unregistered block instead of printing a set diff.

    python3 -B -m unittest docs.review_20261109_6b61c9d.test_result_schemas
"""

from __future__ import annotations

import json
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
_D = os.path.join(_REPO, "docs", "review_20261109_bbc3dcb")


def _load(name):
    with open(os.path.join(_D, name), encoding="utf-8") as fh:
        return json.load(fh)


class Hall01TrajectorySchemaTest(unittest.TestCase):
    def setUp(self):
        self.d = _load("raw_vs_repaired_results.json")

    def test_top_level(self):
        for key in ("protocol", "time_sync", "inputs", "clean_to_gt", "trajectory",
                    "frame_set", "arms", "criterion", "notes"):
            self.assertIn(key, self.d)

    def test_trajectory_blocks(self):
        expected = {"R", "C3", "population"}
        actual = set(self.d["trajectory"])
        self.assertLessEqual(expected, actual, f"missing trajectory blocks: {expected - actual}")
        self.assertLessEqual(actual, expected, f"unregistered trajectory blocks: {actual - expected}")
        self.assertIn("gt_matched", self.d["trajectory"]["population"])
        self.assertIn("gt", self.d["trajectory"]["population"])

    def test_clean_to_gt_is_recomputable(self):
        for key in ("fitted_on", "start_ns", "R_cg", "t_cg", "matched", "residual_rmse_m"):
            self.assertIn(key, self.d["clean_to_gt"])

    def test_inputs_are_hashed(self):
        self.assertEqual(len(self.d["inputs"]), 6)
        for rec in self.d["inputs"].values():
            self.assertRegex(rec["sha256"], r"^[0-9a-f]{64}$")


class Room02FactorialSchemaTest(unittest.TestCase):
    def setUp(self):
        self.d = _load("room02_2x2_results.json")

    def test_top_level(self):
        for key in ("protocol", "inputs", "clean_to_gt", "cells", "summary"):
            self.assertIn(key, self.d)

    def test_cells_keep_both_conventions(self):
        for cell in self.d["cells"].values():
            self.assertIn("ate_full_alignment_diagnostic_m", cell)
            self.assertIn("ate_frozen_prefix_protocol_m", cell)

    def test_receipt_chain_block(self):
        self.assertIn("receipts", self.d["inputs"])
        self.assertEqual(len(self.d["inputs"]["receipts"]), 8)


class SingleFactorReceiptSchemaTest(unittest.TestCase):
    def setUp(self):
        self.d = json.load(open(os.path.join(
            _REPO, "docs", "review_20261109_6b61c9d",
            "single_factor_bags_verified.json"), encoding="utf-8"))

    def test_checks_and_counters(self):
        self.assertIn("checks", self.d)
        self.assertIn("failure_counts", self.d)
        self.assertIn("preregistration", self.d)


class Hall01B4SchemaTest(unittest.TestCase):
    def setUp(self):
        self.d = _load("hall01_b4_cost_and_gap.json")

    def test_reference_and_population(self):
        self.assertIn("reference", self.d)
        self.assertEqual(self.d["reference"]["points"], 8490000)
        self.assertIn("cost", self.d)
        self.assertIn("with_all_400", self.d)
        self.assertIn("without_gap_neighbours", self.d)


if __name__ == "__main__":
    unittest.main()
