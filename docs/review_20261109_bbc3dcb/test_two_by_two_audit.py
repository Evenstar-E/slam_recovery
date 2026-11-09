#!/usr/bin/env python3
"""Fixtures for the 2x2 audit: the two gaps the review found must not come back.

    python3 -m unittest discover -s docs/review_20261109_bbc3dcb -p "test_two_by_two_audit.py" -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import two_by_two_audit as A  # noqa: E402

MANIFEST = {"arms": {c: {"sha256": f"{i}" * 64} for i, c in enumerate(A.CELLS)}}
BAG = {"O": "/tmp/fastlivo/room02_2x2_O.bag",
       "O_plus_F": "/tmp/fastlivo/room02_2x2_O_plus_F.bag",
       "O_minus_B": "/tmp/fastlivo/room02_2x2_O_minus_B.bag",
       "O_plus_F_minus_B": "/tmp/fastlivo/room02_2x2_O_plus_F_minus_B.bag"}


def _receipt(arm, out_sha="9" * 64, status="OK", script="s" * 64, rev="0d2c034"):
    return {
        "_name": f"{arm}-r",
        "status": status,
        "pre_run": {"paths": {"input_bag": BAG[arm],
                              "host_binary": "/home/R26534/fast_livo2_ws/devel/lib/"
                                             "fast_livo/fastlivo_mapping"},
                    "sha256": {"input_bag": MANIFEST["arms"][arm]["sha256"],
                               "script": script, "config_m2dgr": "m" * 64,
                               "config_camera": "c" * 64},
                    "host_revision": rev},
        "output": {"bag": f"/tmp/out_{arm}.bag", "sha256": out_sha},
    }


def _pair(**kw):
    out = []
    for arm in A.CELLS:
        out += [_receipt(arm, **kw), _receipt(arm, **kw)]
    return out


class TestReceipts(unittest.TestCase):
    def _run(self, receipts, hasher=lambda p: "0" * 64, exists=lambda p: True):
        return A.audit_receipts(MANIFEST, receipts=receipts, hasher=hasher, exists=exists)

    def test_complete_set_passes(self):
        hashes = {BAG[a]: MANIFEST["arms"][a]["sha256"] for a in A.CELLS}
        hashes.update({f"/tmp/out_{a}.bag": "9" * 64 for a in A.CELLS})
        r = A.audit_receipts(MANIFEST, receipts=_pair(),
                             hasher=lambda p: hashes[p], exists=lambda p: True)
        self.assertEqual(r["verdict"], "PASS", r["problems"])

    def test_disk_hash_false_is_a_failure(self):
        hasher = lambda p: "f" * 64 if p in BAG.values() else "9" * 64  # noqa: E731
        r = self._run(_pair(), hasher=hasher)
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("bag sha on disk != manifest" in b for b in r["problems"]))

    def test_output_hash_mismatch_is_a_failure(self):
        hasher = lambda p: MANIFEST["arms"][next(a for a, b in BAG.items()  # noqa: E731
                                                 if b == p)]["sha256"] if p in BAG.values() \
            else "0" * 64
        r = self._run(_pair(), hasher=hasher)
        self.assertTrue(any("output bag sha does not match disk" in b for b in r["problems"]))

    def test_identity_must_be_shared(self):
        receipts = _pair()
        receipts[3]["pre_run"]["sha256"]["config_camera"] = "d" * 64
        hasher = lambda p: "0" * 64  # noqa: E731
        r = self._run(receipts, hasher=hasher)
        self.assertTrue(any("camera config differs across receipts" in b for b in r["problems"]))

    def test_host_revision_must_be_shared(self):
        receipts = _pair()
        receipts[5]["pre_run"]["host_revision"] = "deadbeef"
        r = self._run(receipts)
        self.assertTrue(any("host revision differs" in b for b in r["problems"]))

    def test_missing_output_hash_is_a_failure(self):
        receipts = _pair()
        receipts[0]["output"].pop("sha256")
        r = self._run(receipts)
        self.assertTrue(any("no output hash" in b for b in r["problems"]))

    def test_wrong_bag_is_a_failure(self):
        receipts = _pair()
        receipts[0]["pre_run"]["paths"]["input_bag"] = "/tmp/fastlivo/room02_inj43_O.bag"
        r = self._run(receipts)
        self.assertTrue(any("not a 2x2 cell" in b for b in r["problems"]))


class TestIndependent(unittest.TestCase):
    @staticmethod
    def _results(arms=("O", "O+F", "O-B", "O+F-B")):
        cells = {}
        for a in arms:
            for r in (1, 2):
                cells[f"{a}#{r}"] = {"ate_full_alignment_diagnostic_m": 0.1 * r,
                                     "ate_frozen_prefix_protocol_m": 5.0}
        return {"cells": cells}

    @staticmethod
    def _ev(arms=("O", "O+F", "O-B", "O+F-B")):
        return {"cells": {a: [{"arm": a, "repeat": 1, "ate_rmse_m": 0.1},
                              {"arm": a, "repeat": 2, "ate_rmse_m": 0.2}] for a in arms}}

    def test_empty_evaluation_is_unverifiable(self):
        r = A.audit_independent(self._results(), {})
        self.assertEqual(r["verdict"], "UNVERIFIABLE")

    def test_missing_cell_is_unverifiable(self):
        r = A.audit_independent(self._results(), self._ev(arms=("O", "O+F", "O-B")))
        self.assertEqual(r["verdict"], "UNVERIFIABLE")
        self.assertTrue(any("independent missing" in p for p in r["problems"]))

    def test_complete_set_passes(self):
        r = A.audit_independent(self._results(), self._ev())
        self.assertEqual(r["verdict"], "PASS")

    def test_side_disagreement_fails(self):
        ev = self._ev()
        ev["cells"]["O"][0]["ate_rmse_m"] = 5.0        # host 0.1 -> pass, independent -> fail
        r = A.audit_independent(self._results(), ev)
        self.assertEqual(r["verdict"], "FAIL")


class TestRunIdentity(unittest.TestCase):
    @staticmethod
    def _bist(new=4, earlier=2, drop=None, extra=None, n_runs="auto"):
        cells = ["O", "O+F-B"]
        runs, pav = {}, {}
        for c in cells:
            for i in range(1, new + 1):
                runs[f"{c}#{i}"] = {}
                pav[f"new:{c}#{i}"] = 323
            for i in (1, 2)[:earlier]:
                runs[f"{c}#earlier{i}"] = {}
                pav[f"earlier:{c}#{i}"] = 323
        new_runs = {k: v for k, v in runs.items() if "earlier" not in k}
        old = {k: v for k, v in runs.items() if "earlier" in k}
        if drop:
            new_runs.pop(drop, None)
            pav.pop(f"new:{drop}", None)
        if extra:
            new_runs[extra] = {}
            pav[f"new:{extra}"] = 323
        return {"protocol": {"cells": cells, "repeats_per_cell": new},
                "new_runs": new_runs, "earlier_2x2_runs": old,
                "common_set": {"n": 323, "n_runs": len(new_runs) + len(old)
                               if n_runs == "auto" else n_runs,
                               "per_run_available": pav}}

    def test_complete_set_passes(self):
        self.assertEqual(A.check_run_identity(self._bist())["verdict"], "PASS")

    def test_empty_input_is_unverifiable(self):
        r = A.check_run_identity({})
        self.assertEqual(r["verdict"], "UNVERIFIABLE")
        self.assertEqual(r["runs"], [])

    def test_missing_run_is_rejected(self):
        r = A.check_run_identity(self._bist(drop="O#3"))
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("missing runs" in p for p in r["problems"]))

    def test_unexpected_run_is_rejected(self):
        r = A.check_run_identity(self._bist(extra="O#7"))
        self.assertTrue(any("unexpected runs" in p for p in A.check_run_identity(
            self._bist(extra="O#7"))["problems"]))

    def test_missing_n_runs_is_rejected(self):
        r = A.check_run_identity(self._bist(n_runs=None))
        self.assertTrue(any("n_runs absent" in p for p in r["problems"]))

    def test_wrong_n_runs_is_rejected(self):
        r = A.check_run_identity(self._bist(n_runs=11))
        self.assertTrue(any("n_runs 11" in p for p in r["problems"]))

    def test_missing_batch_prefix_is_rejected(self):
        b = self._bist()
        b["common_set"]["per_run_available"] = {k.replace("new:", "").replace("earlier:", ""): v
                                                for k, v in
                                                b["common_set"]["per_run_available"].items()}
        r = A.check_run_identity(b)
        self.assertEqual(r["verdict"], "FAIL")


class TestReceiptLibrary(unittest.TestCase):
    @staticmethod
    def _rec(lib=None):
        h = {"binary": "/x/fastlivo_mapping", "sha256": "b" * 64}
        if lib:
            h["library_sha256"] = lib
        return {"status": "OK", "host": h, "pre_run": {}, "output": {}}

    def test_receipt_with_library_passes(self):
        self.assertEqual(A.check_receipt_library([self._rec("l" * 64)])["verdict"], "PASS")

    def test_missing_library_without_declared_gap_fails(self):
        r = A.check_receipt_library([self._rec()])
        self.assertEqual(r["verdict"], "FAIL")

    def test_declared_gap_is_retrospective_partial(self):
        results = {"provenance_gap": {"receipt_library_sha256": "ABSENT"}}
        r = A.check_receipt_library([self._rec()], results)
        self.assertEqual(r["verdict"], "RETROSPECTIVE_PARTIAL")

    def test_partial_declaration_does_not_excuse_a_new_receipt(self):
        results = {"provenance_gap": {"receipt_library_sha256": "SOMETHING_ELSE"}}
        self.assertEqual(A.check_receipt_library([self._rec()], results)["verdict"], "FAIL")

    def test_mixed_batch_with_gap_is_partial(self):
        results = {"provenance_gap": {"receipt_library_sha256": "ABSENT"}}
        r = A.check_receipt_library([self._rec("l" * 64), self._rec()], results)
        self.assertEqual(r["verdict"], "RETROSPECTIVE_PARTIAL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
