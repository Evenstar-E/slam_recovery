#!/usr/bin/env python3
"""Unit tests for original-index row accounting and the single-factor arms.

These cover the two review objections directly: duplicate rows must keep their multiplicity, and an
arm must be built from original indices rather than a set of row hashes.

    python3 -B -m unittest docs.review_20261109_6b61c9d.test_original_index_audit
"""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import room02_original_index_audit as A               # noqa: E402
import build_single_factor_bags as B                  # noqa: E402
import verify_single_factor_bags as V                # noqa: E402
import evaluate_determinism_pairs as E               # noqa: E402


class OrderedSubsequenceTest(unittest.TestCase):
    def test_duplicates_map_to_distinct_indices(self):
        hay = [b"a", b"a", b"b", b"a"]
        idx, unmatched = A._ordered_subsequence([b"a", b"a"], hay)
        self.assertEqual(unmatched, 0)
        self.assertEqual(idx, [0, 1])

    def test_multiplicity_is_not_recovered_from_a_set(self):
        hay = [b"a", b"a"]
        idx, unmatched = A._ordered_subsequence([b"a", b"a"], hay)
        self.assertEqual(len(set(idx)), 2)
        self.assertEqual(unmatched, 0)
        # A second copy is a third occurrence and must be reported as unmatched, not duplicated.
        idx2, unmatched2 = A._ordered_subsequence([b"a", b"a", b"a"], hay)
        self.assertEqual(unmatched2, 1)
        self.assertEqual(idx2, [0, 1, -1])

    def test_order_is_required(self):
        idx, unmatched = A._ordered_subsequence([b"b", b"a"], [b"a", b"b"])
        self.assertEqual(idx, [1, -1])
        self.assertEqual(unmatched, 1)


class BackgroundMaskTest(unittest.TestCase):
    def test_multiset_matching(self):
        mask = A._background_mask([b"a", b"a", b"x"], [b"a"])
        self.assertEqual(list(mask), [1, 0, 0])

    def test_clean_superset_does_not_justify_extra_injected_rows(self):
        mask = A._background_mask([b"a"], [b"a", b"a"])
        self.assertEqual(list(mask), [1])


class ArmIndicesTest(unittest.TestCase):
    def setUp(self):
        self.kept = np.array([0, 2, 3, 5], dtype=np.int32)
        self.bg = np.array([0, 1, 2, 4], dtype=np.int32)

    def test_relations(self):
        arms, chk = B._arm_indices(self.kept, self.bg)
        self.assertEqual(chk, {"bg": 4, "kept": 4, "kept_injected": 2})
        # O = background only
        self.assertEqual(arms["O"].tolist(), [0, 1, 2, 4])
        # O+F = background plus kept injected (1 and 4 are background; 3 and 5 injected)
        self.assertEqual(arms["O_plus_F"].tolist(), [0, 1, 2, 3, 4, 5])
        # O-B = background rows the filter kept
        self.assertEqual(arms["O_minus_B"].tolist(), [0, 2])
        # O+F-B = actual kept rows
        self.assertEqual(arms["O_plus_F_minus_B"].tolist(), [0, 2, 3, 5])

    def test_arms_are_nested_by_construction(self):
        arms, _ = B._arm_indices(self.kept, self.bg)
        # O-B subset O subset O+F; O+F-B subset O+F
        self.assertTrue(set(arms["O_minus_B"]) <= set(arms["O"]))
        self.assertTrue(set(arms["O"]) <= set(arms["O_plus_F"]))
        self.assertTrue(set(arms["O_plus_F_minus_B"]) <= set(arms["O_plus_F"]))
        # O+F and actual differ by exactly the kept injected rows, and O vs O-B by the dropped ones.
        self.assertEqual(len(arms["O_plus_F"]) - len(arms["O_plus_F_minus_B"]), 2)
        self.assertEqual(len(arms["O"]) - len(arms["O_minus_B"]), 2)


class FnrDenominatorTest(unittest.TestCase):
    def test_false_negative_uses_injected_population(self):
        kept_inj, dropped_inj, background = 1265, 9072678, 1186220
        injected = kept_inj + dropped_inj
        self.assertAlmostEqual(kept_inj / injected, 0.0001394101770310878, places=15)
        self.assertNotAlmostEqual(kept_inj / background, kept_inj / injected)
        self.assertAlmostEqual(kept_inj / background, 0.0010664126384650403, places=15)


if __name__ == "__main__":
    unittest.main()


class SidecarArrayTest(unittest.TestCase):
    """No-bag fixtures for the sidecar gates (review 61c99f9 / a0be9598)."""

    def test_valid_array(self):
        self.assertIsNone(V._array_problem(np.array([0, 2, 5], dtype=np.int32), 6))

    def test_negative_index(self):
        self.assertEqual(V._array_problem(np.array([0, -1, 5], dtype=np.int32), 6),
                         "sidecar_bounds")

    def test_out_of_bounds_index(self):
        self.assertEqual(V._array_problem(np.array([0, 2, 6], dtype=np.int32), 6),
                         "sidecar_bounds")

    def test_unsorted_array(self):
        self.assertEqual(V._array_problem(np.array([0, 5, 2], dtype=np.int32), 6),
                         "sidecar_order")

    def test_duplicate_index(self):
        self.assertEqual(V._array_problem(np.array([0, 2, 2], dtype=np.int32), 6),
                         "sidecar_order")

    def test_non_integer_dtype(self):
        self.assertEqual(V._array_problem(np.array([0.0, 2.0], dtype=np.float64), 6),
                         "sidecar_dtype")

    def test_empty_array_is_allowed(self):
        self.assertIsNone(V._array_problem(np.array([], dtype=np.int32), 0))


class ExtraStreamEofTest(unittest.TestCase):
    """A trailing message after the reference stream ends must not pass unseen."""

    def test_clean_eof(self):
        self.assertFalse(V._extra_messages(iter([])))

    def test_trailing_message(self):
        self.assertTrue(V._extra_messages(iter([object()])))


class ReceiptChainGateTest(unittest.TestCase):
    """The gate must reject False and missing comparisons, not just look at status."""

    def _pair(self, m1, m2, status="OK"):
        return {"status": status,
                "receipt_r1_matches_bag": m1, "receipt_r2_matches_bag": m2}

    def test_all_true_passes(self):
        gate = E.receipt_chain({"T1": self._pair(True, True)})
        self.assertTrue(gate["ok"])

    def test_false_with_ok_status_fails(self):
        gate = E.receipt_chain({"T1": self._pair(True, False)})
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["mismatched"], ["T1#2"])

    def test_missing_comparison_is_unverifiable(self):
        gate = E.receipt_chain({"T1": self._pair(True, None)})
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["unverifiable"], ["T1#2"])

    def test_non_ok_record_is_skipped(self):
        gate = E.receipt_chain({"T1": self._pair(None, None, status="TOO_FEW_PREFIX")})
        self.assertTrue(gate["ok"])
