#!/usr/bin/env python3
"""Fixtures for the 2x2 bag-acceptance rules, plus a check on the committed receipt.

    python3 -m unittest discover -s docs/review_20261109_6b61c9d -p "test_single_factor_audit_rules.py" -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import single_factor_audit_rules as Q  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _receipt(n_in=199, n_out=400, checks=None, failures=None):
    return {"frames": {"total": n_in + n_out, "in_window": n_in, "outside": n_out},
            "checks": checks if checks is not None else {
                "outside_all_equal_filtered": True,
                "combined_equals_actual_in_window": True,
                "arms_match_original_indices": True, "row_counts_match": True},
            "failures": failures if failures is not None else []}


class TestOutsideEquality(unittest.TestCase):
    def test_compliant_receipt_passes(self):
        self.assertEqual(Q.check_outside_equals_filtered(_receipt()), [])

    def test_no_outside_frames_is_rejected(self):
        """The verifier's boolean is vacuously true when the population is empty."""
        bad = Q.check_outside_equals_filtered(_receipt(n_out=0))
        self.assertTrue(any("vacuously" in b for b in bad), bad)

    def test_a_real_difference_is_rejected(self):
        r = _receipt(failures=[{"ns": 1, "arm": "O",
                                "why": "outside window differs from filtered scan"}])
        self.assertTrue(Q.check_outside_equals_filtered(r))

    def test_false_flag_is_rejected(self):
        c = {"outside_all_equal_filtered": False, "combined_equals_actual_in_window": True,
             "arms_match_original_indices": True, "row_counts_match": True}
        self.assertTrue(Q.check_outside_equals_filtered(_receipt(checks=c)))

    def test_missing_failures_is_unverifiable_not_pass(self):
        r = {"frames": {"outside": 400}, "checks": {"outside_all_equal_filtered": True}}
        self.assertTrue(Q.check_outside_equals_filtered(r))


class TestCombinedCell(unittest.TestCase):
    def test_compliant_receipt_passes(self):
        self.assertEqual(Q.check_combined_equals_filtered(_receipt()), [])

    def test_no_in_window_frames_is_rejected(self):
        self.assertTrue(Q.check_combined_equals_filtered(_receipt(n_in=0)))

    def test_a_differing_combined_cell_is_rejected(self):
        r = _receipt(failures=[{"ns": 1, "arm": "O_plus_F_minus_B",
                                "why": "combined cell differs from actual filtered scan"}])
        self.assertTrue(Q.check_combined_equals_filtered(r))

    def test_false_flag_is_rejected(self):
        c = {"outside_all_equal_filtered": True, "combined_equals_actual_in_window": False,
             "arms_match_original_indices": True, "row_counts_match": True}
        self.assertTrue(Q.check_combined_equals_filtered(_receipt(checks=c)))

    def test_missing_check_key_is_rejected(self):
        c = {"outside_all_equal_filtered": True, "arms_match_original_indices": True,
             "row_counts_match": True}
        self.assertTrue(Q.check_combined_equals_filtered(_receipt(checks=c)))


class TestPreregistration(unittest.TestCase):
    CELLS = ["O", "O_plus_F", "O_minus_B", "O_plus_F_minus_B"]

    def _design(self, **kw):
        d = {"declared_before_results": True, "repetitions_per_cell": 2,
             "failure_threshold_ate_m": 1.0, "cells": self.CELLS}
        d.update(kw)
        return d

    def test_compliant_design_passes(self):
        self.assertEqual(Q.check_preregistration(self._design()), [])

    def test_single_repetition_is_rejected(self):
        self.assertTrue(Q.check_preregistration(self._design(repetitions_per_cell=1)))

    def test_wrong_threshold_is_rejected(self):
        self.assertTrue(Q.check_preregistration(self._design(failure_threshold_ate_m=1.5)))

    def test_undeclared_threshold_is_rejected(self):
        d = self._design()
        del d["failure_threshold_ate_m"]
        self.assertTrue(Q.check_preregistration(d))

    def test_declaring_after_results_is_rejected(self):
        self.assertTrue(Q.check_preregistration(
            self._design(declared_before_results=False)))

    def test_wrong_cell_set_is_rejected(self):
        self.assertTrue(Q.check_preregistration(self._design(cells=["O", "O_plus_F"])))


class TestCommittedReceipt(unittest.TestCase):
    def test_real_receipt_passes_both_equality_rules(self):
        with open(os.path.join(HERE, "single_factor_bags_verified.json"),
                  encoding="utf-8") as fh:
            receipt = json.load(fh)
        self.assertEqual(Q.check_outside_equals_filtered(receipt), [])
        self.assertEqual(Q.check_combined_equals_filtered(receipt), [])
        self.assertEqual(Q.check_all_checks_present(receipt), [])
        self.assertEqual(receipt["frames"]["outside"], 400)
        self.assertEqual(receipt["frames"]["in_window"], 199)


if __name__ == "__main__":
    unittest.main(verbosity=2)
