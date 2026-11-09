#!/usr/bin/env python3
"""Fixtures for the five oracle/hybrid audit rules, plus acceptance checks on the real
artefacts. Fixtures always run; the artefact checks are marked `expectedFailure` where the
producer has not been fixed yet, so a fix shows up as an unexpected success and the marker can
be removed deliberately rather than being forgotten.

    python3 -m unittest discover -s docs/review_20261109_bbc3dcb -p "test_oracle_audit_rules.py" -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import oracle_audit_rules as Q  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


class TestR1Multiplicity(unittest.TestCase):
    """Repeated rows must be counted repeatedly."""

    def test_repeats_are_counted_with_multiplicity(self):
        inj = [b"A", b"A", b"B", b"C"]
        cln = [b"C"]                       # C is background, A/A/B were injected
        kept = [b"A", b"B"]                # the filter kept two of the three injected rows
        c = Q.count_rows_by_index(inj, cln, kept)
        self.assertEqual(c["kept_injected"], 2)
        self.assertEqual(c["background_present"], 1)

    def test_set_based_count_loses_a_repeat(self):
        inj = [b"A", b"A"]
        kept = [b"A", b"A"]
        self.assertEqual(Q.check_multiplicity(inj, kept)[0].split()[0], "1")
        # the set-based view would see one row and report a 50 % loss where there is none
        self.assertEqual(len(set(kept)), 1)
        self.assertEqual(len(kept), 2)

    def test_no_repeats_means_no_violation(self):
        self.assertEqual(Q.check_multiplicity([b"A", b"B"], [b"A"]), [])


class TestR2HybridReport(unittest.TestCase):
    def test_compliant_report_passes(self):
        rep = {"status": "OK", "input_sha256": "a" * 64, "hybrid_with_sha256": "b" * 64,
               "original_index_sidecar": {"topic": "/velodyne_points/kept_index"}}
        self.assertEqual(Q.check_hybrid_report(rep), [])

    def test_missing_borrowed_bag_hash(self):
        rep = {"status": "OK", "input_sha256": "a" * 64,
               "original_index_sidecar": {"topic": "x"}}
        self.assertTrue(any("hybrid_with_sha256" in v for v in Q.check_hybrid_report(rep)))

    def test_missing_index_sidecar(self):
        rep = {"status": "OK", "input_sha256": "a" * 64, "hybrid_with_sha256": "b" * 64}
        self.assertTrue(any("original_index_sidecar" in v for v in Q.check_hybrid_report(rep)))


class TestR3WindowProvenance(unittest.TestCase):
    def test_derived_window_is_tautological(self):
        rep = {"window": {"onset_ns": 1, "end_ns": 2,
                          "derived_from": "min/max of differing frames"}}
        self.assertTrue(Q.check_window_provenance(rep))

    def test_undeclared_window_is_rejected(self):
        self.assertTrue(Q.check_window_provenance({"window": {"onset_ns": 1, "end_ns": 2}}))

    def test_declared_window_that_matches_passes(self):
        rep = {"window": {"onset_ns": 1, "end_ns": 2,
                          "declared_from": "docs/milestone_m0_keys.json",
                          "derived_from": "min/max of differing frames"}}
        self.assertEqual(Q.check_window_provenance(rep, declared_window=(1, 2)), [])

    def test_declared_window_that_disagrees_fails(self):
        rep = {"window": {"onset_ns": 1, "end_ns": 2, "declared_from": "declared.json"}}
        self.assertTrue(Q.check_window_provenance(rep, declared_window=(1, 3)))


class TestR4OracleAcceptance(unittest.TestCase):
    def test_status_ok_with_mismatched_hashes_fails(self):
        rep = {"status": "OK", "input_sha256": "a" * 64, "output_sha256": "b" * 64}
        bad = Q.check_oracle_acceptance(rep, "0" * 64, "b" * 64)
        self.assertTrue(any("input hash" in v for v in bad))

    def test_status_ok_without_any_hash_fails(self):
        self.assertTrue(Q.check_oracle_acceptance({"status": "OK"}, "a" * 64, "b" * 64))

    def test_matching_hashes_pass(self):
        rep = {"status": "OK", "input_sha256": "a" * 64, "output_sha256": "b" * 64}
        self.assertEqual(Q.check_oracle_acceptance(rep, "a" * 64, "b" * 64), [])

    def test_pre_run_and_output_blocks_are_read(self):
        rep = {"status": "OK", "pre_run": {"sha256": {"input_bag": "a" * 64}},
               "output": {"sha256": "b" * 64}}
        self.assertEqual(Q.check_oracle_acceptance(rep, "a" * 64, "b" * 64), [])


class TestR5FalseNegativeRate(unittest.TestCase):
    def test_correct_definition_passes(self):
        agg = {"kept_injected": 1265, "dropped_injected": 9072678,
               "false_negative_rate": 1265 / (1265 + 9072678)}
        self.assertEqual(Q.check_fnr(agg), [])

    def test_background_normalised_rate_is_rejected(self):
        agg = {"kept_injected": 1265, "dropped_injected": 9072678,
               "false_negative_rate": 1265 / 1186220}
        self.assertTrue(Q.check_fnr(agg))

    def test_no_injected_rows(self):
        self.assertEqual(Q.check_fnr({"kept_injected": 0, "dropped_injected": 0,
                                      "false_negative_rate": 0.0}), [])


class TestRealArtefacts(unittest.TestCase):
    """Acceptance on what is committed today."""

    def test_r5_real_row_audit_is_correct(self):
        """The script and the committed JSON now agree.

        room02_filter_row_audit.py divides by kept_injected + dropped_injected and the JSON was
        regenerated, so the marker this test used to carry has been removed.
        """
        agg = _load("room02_filter_row_audit.json")["in_window"]
        self.assertEqual(agg["kept_injected"] + agg["dropped_injected"], 9073943)
        self.assertAlmostEqual(agg["false_negative_rate"], 0.0001394101770310878, places=12)
        self.assertEqual(Q.check_fnr(agg), [])
        # and the old quantity is still available under its own name
        self.assertAlmostEqual(agg["kept_injected_over_background_present"],
                               0.0010664126384650403, places=12)

    @unittest.expectedFailure
    def test_r2_real_hybrid_report_is_incomplete(self):
        rep = _load("room02_hybrid_bag_report.json")
        self.assertEqual(Q.check_hybrid_report(rep), [])

    @unittest.expectedFailure
    def test_r3_real_hybrid_window_is_derived(self):
        rep = _load("room02_hybrid_bag_report.json")
        self.assertEqual(Q.check_window_provenance(rep), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
