#!/usr/bin/env python3
"""Fixtures for the trace parser and the pre-declared judgements.

Synthetic CSVs only: the host trace does not exist yet, and the predicates must be settled
before it does. Each test writes a small CSV in the agreed schema and asks the judge a question
whose answer is fixed by the judgement rules, not by the data.

    python3 -m unittest discover -s docs/review_20261109_bbc3dcb -p "test_trace_compare.py" -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trace_compare as T  # noqa: E402

HEADER = ("kind,wall_ns,lid_stamp_ns,n_items,first_stamp_ns,last_stamp_ns,stamps_sha256,extra")


def _sha(seed: str) -> str:
    return f"{seed:0<64}"[:64]


def _write(rows):
    fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    fh.write(HEADER + "\n")
    for r in rows:
        fh.write(",".join("" if v is None else str(v) for v in r) + "\n")
    fh.close()
    return fh.name


def _group(seq, n=3, first=100, last=200, sha="a", mesures=5, img=1):
    return ("GROUP", 1000 + seq, 900 + seq, n, first, last, _sha(sha),
            f"mesures={mesures}|img={img}|img_stamp_ns=950|need_init=0")


def _state(seq, x, stamp=None):
    return ("STATE", 2000 + seq, stamp or (500 + seq), 0, None, None, None,
            f"pos={x}|0|0|diagR=1|1|1")


class TestParser(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        for p in getattr(cls, "_files", []):
            os.unlink(p)

    def _parse(self, rows):
        p = _write(rows)
        self.__class__._files = getattr(self.__class__, "_files", []) + [p]
        return T.parse(p)

    def test_reads_all_four_kinds(self):
        tr = self._parse([
            ("ARRIVE", 10, 11, 1, 11, 11, _sha("1"), "buflen=7"),
            _group(1), ("IMUINIT", 20, 300, 3, 100, 200, _sha("2"), "iter=4|max=20"),
            _state(1, "1.0")])
        self.assertEqual([e.kind for e in tr.events], ["ARRIVE", "GROUP", "IMUINIT", "STATE"])
        self.assertEqual(tr.of("STATE")[0].xyz(), [1.0, 0.0, 0.0])

    def test_unknown_kind_is_an_error(self):
        with self.assertRaises(ValueError):
            self._parse([("BOGUS", 1, 2, 3, 4, 5, _sha("x"), "")])

    def test_float_time_is_an_error(self):
        with self.assertRaises(ValueError):
            self._parse([("STATE", 1.5e9, 2, 0, None, None, None, "pos=0|0|0|diagR=1|1|1")])

    def test_group_without_sha_is_an_error(self):
        with self.assertRaises(ValueError):
            self._parse([("GROUP", 1, 2, 3, 4, 5, None, "")])

    def test_a_file_without_the_header_is_rejected(self):
        """The 2026-11-10 v2 delivery had no header; the first row then reads as kind=''."""
        p = _write([_group(1)])
        body = open(p, encoding="utf-8").read().split("\n", 1)[1]
        fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        fh.write(body)
        fh.close()
        self.__class__._files = getattr(self.__class__, "_files", []) + [fh.name]
        with self.assertRaises(ValueError):
            T.parse(fh.name)

    def test_empty_group_is_a_recorded_event(self):
        """n_items=0 with sha256("") means 'a package with no IMU', not 'no row'."""
        empty = ("GROUP", 1500, 900, 0, -1, -1,
                 "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                 "mesures=1|img=0|img_stamp_ns=-1000000000|need_init=1")
        tr = self._parse([empty])
        ev = tr.of("GROUP")[0]
        self.assertEqual(ev.n_items, 0)
        self.assertEqual(ev.first_stamp_ns, -1)
        self.assertEqual(ev.stamps_sha256[:8], "e3b0c442")
        self.assertTrue(T.compare_groups(tr, self._parse([empty]))["identical"])


class TestGroupComparison(unittest.TestCase):
    def test_identical_groups(self):
        a = _write([_group(1), _group(2)])
        b = _write([_group(1), _group(2)])
        self.assertTrue(T.compare_groups(T.parse(a), T.parse(b))["identical"])

    def test_a_changed_sample_set_is_a_difference(self):
        a = _write([_group(1, sha="a")])
        b = _write([_group(1, sha="b")])
        r = T.compare_groups(T.parse(a), T.parse(b))
        self.assertFalse(r["identical"])
        self.assertEqual(len(r["differences"]), 1)

    def test_a_different_count_is_a_difference(self):
        a = _write([_group(1, n=3)])
        b = _write([_group(1, n=4)])
        self.assertFalse(T.compare_groups(T.parse(a), T.parse(b))["identical"])

    def test_equal_prefix_but_different_length(self):
        a = _write([_group(1), _group(2)])
        b = _write([_group(1)])
        r = T.compare_groups(T.parse(a), T.parse(b))
        self.assertTrue(r["count_mismatch"])


class TestJudgement(unittest.TestCase):
    def test_same_groups_but_states_split_is_unknown(self):
        """The rule the review asked for: do not blame grouping when grouping did not vary."""
        a = _write([_group(1), _group(2), _state(1, "0.0"), _state(2, "0.0")])
        b = _write([_group(1), _group(2), _state(1, "0.0"), _state(2, "5.0")])
        r = T.judge(T.parse(a), T.parse(b))
        self.assertEqual(r["verdict"], "UNKNOWN")
        self.assertIn("cannot be the mechanism", r["why"])

    def test_different_groups_is_a_candidate_not_a_cause(self):
        a = _write([_group(1, sha="a"), _state(1, "0.0"), _state(2, "0.0")])
        b = _write([_group(1, sha="b"), _state(1, "0.0"), _state(2, "5.0")])
        r = T.judge(T.parse(a), T.parse(b))
        self.assertEqual(r["verdict"], "GROUP_COMPOSITION_VARIES")
        self.assertIn("not a cause", r["why"])

    def test_no_divergence(self):
        a = _write([_group(1), _state(1, "1.0")])
        b = _write([_group(1), _state(1, "1.0")])
        self.assertEqual(T.judge(T.parse(a), T.parse(b))["verdict"], "NO_DIVERGENCE")

    def test_control_that_also_diverges_excludes_tracing(self):
        a = _write([_group(1), _state(1, "0.0"), _state(2, "0.0")])
        b = _write([_group(1), _state(1, "0.0"), _state(2, "5.0")])
        c = _write([_state(1, "0.0"), _state(2, "0.0")])
        d = _write([_state(1, "0.0"), _state(2, "7.0")])
        r = T.judge(T.parse(a), T.parse(b), control=(T.parse(c), T.parse(d)))
        self.assertIn("not caused by tracing", r["why"])

    def test_control_that_does_not_diverge_keeps_tracing_as_a_candidate(self):
        a = _write([_group(1), _state(1, "0.0"), _state(2, "0.0")])
        b = _write([_group(1), _state(1, "0.0"), _state(2, "5.0")])
        c = _write([_state(1, "0.0"), _state(2, "0.0")])
        d = _write([_state(1, "0.0"), _state(2, "0.001")])
        r = T.judge(T.parse(a), T.parse(b), control=(T.parse(c), T.parse(d)))
        self.assertIn("live perturbation candidate", r["why"])

    def test_length_mismatch_counts_as_divergence(self):
        a = _write([_state(1, "0.0"), _state(2, "0.0")])
        b = _write([_state(1, "0.0")])
        r = T.first_state_divergence(T.parse(a), T.parse(b))
        self.assertIsNotNone(r)
        self.assertIn("length differs", r["why"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
