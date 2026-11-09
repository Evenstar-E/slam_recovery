#!/usr/bin/env python3
"""Fixtures for run_m4_completeness: no bag access, no host rerun.

The three reviewed defects were all in branches that never execute on the current archive —
a frame with a pose but no scan, a missing bracketing pair, and a stale audit. Testing them
against the archive alone would prove nothing, so they are exercised directly.

    python3 -m unittest discover -s docs/review_20261109_bbc3dcb -p "test_m4_completeness.py" -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import run_m4_completeness as M  # noqa: E402

NEAR_DT = 0.02      # R.POSE_NEAR_DT
MAX_GAP = 0.075     # R.POSE_MAX_GAP


class TestSuccessDefinition(unittest.TestCase):
    """success = pose AND nonempty observation."""

    def test_pose_and_scan_is_success(self):
        v = M.classify_key(True, 1200, dt_near=0.003, gap=0.066, near_dt=NEAR_DT, max_gap=MAX_GAP)
        self.assertTrue(v["ok"])
        self.assertIsNone(v["reason"])

    def test_pose_without_scan_is_not_success(self):
        v = M.classify_key(True, None, dt_near=0.003, gap=0.066, near_dt=NEAR_DT, max_gap=MAX_GAP)
        self.assertFalse(v["ok"])
        self.assertEqual(v["reason"], "MISSING_SCAN")

    def test_pose_with_empty_scan_is_not_success(self):
        v = M.classify_key(True, 0, dt_near=0.003, gap=0.066, near_dt=NEAR_DT, max_gap=MAX_GAP)
        self.assertFalse(v["ok"])
        self.assertEqual(v["reason"], "EMPTY_SCAN")
        self.assertIn("EMPTY_SCAN", v["reasons"])

    def test_no_pose_with_scan_and_big_gap_is_pairing_rule(self):
        v = M.classify_key(False, 1200, dt_near=0.9, gap=0.40, near_dt=NEAR_DT, max_gap=MAX_GAP)
        self.assertFalse(v["ok"])
        self.assertEqual(v["reason"], "PAIRING_RULE_MISSING")
        self.assertEqual(v["cause"], "PAIRING_RULE_MISSING (bracketing gap over the 75 ms limit)")

    def test_no_pose_and_no_scan_lists_both(self):
        v = M.classify_key(False, None, dt_near=None, gap=None, near_dt=NEAR_DT, max_gap=MAX_GAP)
        self.assertFalse(v["ok"])
        self.assertEqual(v["reason"], "NO_POSE")
        self.assertEqual(v["reasons"], ["NO_POSE", "MISSING_SCAN"])


class TestRecoverabilityText(unittest.TestCase):
    """gap=None must report UNKNOWN, not raise."""

    def test_missing_gap_does_not_raise(self):
        rec_frozen, rec_relax, why = M.describe_recoverability(1200, 0.005, None)
        self.assertFalse(rec_frozen)
        self.assertFalse(rec_relax)
        self.assertIn("n/a", why)

    def test_gap_formats_when_present(self):
        # 66 ms is inside the 75 ms pairing limit but inside the 150 ms relaxed limit, so this
        # frame is refused now and would be recoverable only by relaxing the rule.
        _f, rec_relax, why = M.describe_recoverability(1200, 0.005, 0.066)
        self.assertTrue(rec_relax)
        self.assertIn("66.0 ms", why)

    def test_gap_beyond_relaxed_limit_is_not_recoverable(self):
        _f, rec_relax, why = M.describe_recoverability(1200, 0.005, 0.300)
        self.assertFalse(rec_relax)
        self.assertIn("300.0 ms", why)

    def test_relaxable_gap_is_flagged(self):
        _f, rec_relax, why = M.describe_recoverability(1200, 0.005, 0.120)
        self.assertTrue(rec_relax)
        self.assertIn("relaxing the gap limit", why)

    def test_no_scan_reason(self):
        _f, _r, why = M.describe_recoverability(None, 0.005, 0.066)
        self.assertIn("no filtered scan", why)


class TestAuditBinding(unittest.TestCase):
    """A stored audit is evidence only for the run whose bag it read."""

    H = "f" * 64

    @classmethod
    def _audit(cls, sha="a" * 64, path="/tmp/fastlivo/hall01_inj43.bag", kept=(10, 20),
               rows=None):
        rows = rows or ([cls.H, cls.H] if len(kept) == 2 else [cls.H] * len(kept))
        return {"input": path, "input_sha256": sha,
                "per_frame": [{"ns": 100 + i, "n_kept": k, "output_sha256": rows[i]}
                              for i, k in enumerate(kept)]}

    @classmethod
    def _fp(cls, kept=(10, 20), rows=None):
        rows = rows or ([cls.H, cls.H] if len(kept) == 2 else [cls.H] * len(kept))
        return {100 + i: (k, rows[i]) for i, k in enumerate(kept)}

    def test_binds_when_everything_matches(self):
        r = M.check_audit_binding(self._audit(), "a" * 64, "/tmp/fastlivo/hall01_inj43.bag",
                                  self._fp())
        self.assertEqual(r["status"], "BOUND")
        self.assertEqual(r["problems"], [])

    def test_stale_on_source_hash(self):
        r = M.check_audit_binding(self._audit(sha="b" * 64), "a" * 64,
                                  "/tmp/fastlivo/hall01_inj43.bag", self._fp())
        self.assertEqual(r["status"], "STALE_AUDIT")
        self.assertTrue(any("sha256" in p for p in r["problems"]))

    def test_stale_on_path(self):
        r = M.check_audit_binding(self._audit(path="/other.bag"), "a" * 64,
                                  "/tmp/fastlivo/hall01_inj43.bag", self._fp())
        self.assertEqual(r["status"], "STALE_AUDIT")
        self.assertTrue(any("path" in p for p in r["problems"]))

    def test_stale_on_count_mismatch(self):
        r = M.check_audit_binding(self._audit(), "a" * 64, "/tmp/fastlivo/hall01_inj43.bag",
                                  self._fp(kept=(10, 99)))
        self.assertEqual(r["status"], "STALE_AUDIT")
        self.assertTrue(any("different count" in p for p in r["problems"]))

    def test_stale_when_a_frame_is_absent_from_the_bag(self):
        r = M.check_audit_binding(self._audit(), "a" * 64, "/tmp/fastlivo/hall01_inj43.bag",
                                  {100: (10, self.H)})
        self.assertEqual(r["status"], "STALE_AUDIT")

    def test_stale_on_same_count_different_payload(self):
        """The case the count-only check missed: identical n_kept, different rows."""
        fp = self._fp(rows=["0" * 64, self.H])
        r = M.check_audit_binding(self._audit(), "a" * 64,
                                  "/tmp/fastlivo/hall01_inj43.bag", fp)
        self.assertEqual(r["status"], "STALE_AUDIT")
        self.assertTrue(any("different rows" in p for p in r["problems"]))

    def test_missing_digest_is_not_bound(self):
        """Counts alone are not evidence: a record with no payload hash must not bind."""
        audit = {"input": "/tmp/fastlivo/hall01_inj43.bag", "input_sha256": "a" * 64,
                 "per_frame": [{"ns": 100, "n_kept": 2}]}
        r = M.check_audit_binding(audit, "a" * 64, "/tmp/fastlivo/hall01_inj43.bag",
                                  {100: (2, "9" * 64)})
        self.assertNotEqual(r["status"], "BOUND")
        self.assertEqual(r["status"], "UNVERIFIABLE")
        self.assertTrue(any("no payload digest" in p for p in r["problems"]))

    def test_one_digest_missing_among_many_is_not_bound(self):
        audit = self._audit(kept=(10, 20))
        del audit["per_frame"][1]["output_sha256"]
        r = M.check_audit_binding(audit, "a" * 64, "/tmp/fastlivo/hall01_inj43.bag",
                                  self._fp())
        self.assertNotEqual(r["status"], "BOUND")

    def test_empty_audit_is_not_bound(self):
        """An audit with no frames agrees with nothing and must not pass."""
        r = M.check_audit_binding({"input": "/tmp/fastlivo/hall01_inj43.bag",
                                   "input_sha256": "a" * 64, "per_frame": []},
                                  "a" * 64, "/tmp/fastlivo/hall01_inj43.bag", {})
        self.assertNotEqual(r["status"], "BOUND")
        self.assertEqual(r["status"], "UNVERIFIABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
